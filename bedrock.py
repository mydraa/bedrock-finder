#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
MINECRAFT BEDROCK PATTERN FINDER & REVERSE-ENGINEERING ENGINE
================================================================================
Author   : Antigravity (Google DeepMind)
Version  : 2.1.0 (Multi-version Support: 1.0 -> 1.21+)

Description:
------------
This script locates the exact (X, Y, Z) coordinates of a bedrock formation
in Minecraft Java Edition from:
  1. Minecraft Version (1.0-1.12.2 legacy, 1.13-1.17, 1.18+ modern).
  2. World seed (when required by the version/dimension).
  3. Target pattern:
     - Text/Numeric matrix (depths 0..4, Y levels 123..127, 0..4, -64..-60, or presence # / .).
     - Screenshot/image cropped into a grid (brightness analysis and/or texture rotation).
  4. Block texture orientation and rotation (via MathHelper.getCoordinateRandom).

Supported Minecraft Versions:
-----------------------------
- 1.12 / legacy (1.0 - 1.12.2):
    * Nether roof (Y=123..127) & floor (Y=0..4): 100% seed-independent.
    * Overworld floor (Y=0..4): 100% seed-independent.
- 1.13 - 1.17 (1.13 to 1.17.1):
    * Nether roof & floor: 100% seed-independent in vanilla.
    * Overworld floor (Y=0..4): supports world seed mixing (WorldGenRandom).
- 1.18+ / modern (1.18 to 1.21+ Caves & Cliffs):
    * Overworld floor shifted to Y=-64..-60 (negative Y levels).
    * Nether roof (Y=123..127) & floor (Y=0..4).
"""

import os
import sys
import time
import math
import json
import argparse
from typing import List, Tuple, Optional, Dict, Any, Union
import multiprocessing as mp
from dataclasses import dataclass
from enum import Enum

import numpy as np
from PIL import Image


# ==============================================================================
# 1. MATHEMATICAL CONSTANTS & JAVA LCG PRNG
# ==============================================================================

LCG_MULTIPLIER = 0x5DEECE66D
LCG_ADDEND = 0xB
LCG_MASK = (1 << 48) - 1

# Minecraft constants for chunk seed calculation (ChunkProviderHell / ChunkProviderGenerate)
CHUNK_SEED_X_MULT = 341873128712
CHUNK_SEED_Z_MULT = 132897987541

# MathHelper.getCoordinateRandom constants
COORD_RAND_X_MULT = 3129871
COORD_RAND_Z_MULT = 116129781
COORD_RAND_SQ_MULT = 42317861
COORD_RAND_LIN_MULT = 11
UINT64_MASK = 0xFFFFFFFFFFFFFFFF


class JavaRandom:
    """Bit-exact emulator for java.util.Random."""

    def __init__(self, seed: int = 0):
        self.seed = (seed ^ LCG_MULTIPLIER) & LCG_MASK

    def set_seed(self, seed: int) -> None:
        self.seed = (seed ^ LCG_MULTIPLIER) & LCG_MASK

    def next(self, bits: int) -> int:
        self.seed = (self.seed * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
        return self.seed >> (48 - bits)

    def next_int(self, bound: int) -> int:
        """Exact reproduction of java.util.Random.nextInt(bound)."""
        if bound <= 0:
            raise ValueError("Bound must be positive")
        if (bound & -bound) == bound:  # bound is a power of 2
            return (bound * self.next(31)) >> 31

        bits = self.next(31)
        val = bits % bound
        while (bits - val + (bound - 1)) < 0:
            bits = self.next(31)
            val = bits % bound
        return val


# Precompute LCG Jump Tables
# S_k = (S_0 * A_k + B_k) mod 2^48
def compute_lcg_jump_tables(max_steps: int = 512) -> Tuple[np.ndarray, np.ndarray]:
    """Precomputes coefficients (A_k, B_k) to jump k LCG steps in O(1)."""
    ak = np.zeros(max_steps + 1, dtype=np.uint64)
    bk = np.zeros(max_steps + 1, dtype=np.uint64)
    cur_a = 1
    cur_b = 0
    for k in range(max_steps + 1):
        ak[k] = np.uint64(cur_a & LCG_MASK)
        bk[k] = np.uint64(cur_b & LCG_MASK)
        cur_a = (cur_a * LCG_MULTIPLIER) & LCG_MASK
        cur_b = (cur_b * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
    return ak, bk


AK_TABLE, BK_TABLE = compute_lcg_jump_tables(512)


# ==============================================================================
# 2. COORDINATE HASHING & TEXTURE ROTATION (getCoordinateRandom)
# ==============================================================================

def get_coordinate_random(x: int, y: int, z: int) -> int:
    """
    Exact equivalent of net.minecraft.util.math.MathHelper.getCoordinateRandom(x, y, z).
    Used by Minecraft (1.8 to 1.21+) to select block model variants and texture rotations.
    """
    l = ((x * COORD_RAND_X_MULT) ^ (z * COORD_RAND_Z_MULT) ^ y) & UINT64_MASK
    l = (l * l * COORD_RAND_SQ_MULT + l * COORD_RAND_LIN_MULT) & UINT64_MASK
    return (l >> 16) & UINT64_MASK


def get_texture_rotation_index(x: int, y: int, z: int) -> int:
    """
    Returns rotation index (0, 1, 2, 3) corresponding to (0°, 90°, 180°, 270°)
    for a block located at world coordinates (x, y, z).
    """
    rnd = get_coordinate_random(x, y, z)
    return int((rnd >> 16) & 3)


# ==============================================================================
# 3. MINECRAFT VERSION & DIMENSION SYSTEM
# ==============================================================================

class MinecraftVersion(Enum):
    V1_12 = "1.12"            # 1.0 to 1.12.2 (Legacy, seed-independent bedrock)
    V1_13_1_17 = "1.13-1.17"  # 1.13 to 1.17.1 (WorldGenRandom decoration seed support)
    V1_18_PLUS = "1.18+"      # 1.18 to 1.21+ (Caves & Cliffs, negative Y Overworld)

    @classmethod
    def parse(cls, ver_str: str) -> 'MinecraftVersion':
        v = ver_str.strip().lower()
        if v in ("1.12", "1.12.2", "1.11", "1.10", "1.9", "1.8", "1.7", "legacy", "old"):
            return cls.V1_12
        elif v in ("1.13", "1.14", "1.15", "1.16", "1.16.5", "1.17", "1.17.1", "1.13-1.17", "1.14-1.17"):
            return cls.V1_13_1_17
        elif v in ("1.18", "1.18.2", "1.19", "1.20", "1.21", "1.18+", "modern", "new"):
            return cls.V1_18_PLUS
        else:
            # Fallback parse numeric
            try:
                parts = [int(p) for p in v.split(".") if p.isdigit()]
                if len(parts) >= 2:
                    minor = parts[1]
                    if minor <= 12:
                        return cls.V1_12
                    elif minor <= 17:
                        return cls.V1_13_1_17
                    else:
                        return cls.V1_18_PLUS
            except Exception:
                pass
            return cls.V1_12


class DimensionMode(Enum):
    NETHER_ROOF = "nether-roof"      # Y=123..127 (Nether ceiling)
    NETHER_FLOOR = "nether-floor"    # Y=0..4 (Nether floor)
    OVERWORLD = "overworld"          # Y=0..4 (pre-1.18) or Y=-64..-60 (1.18+)


def get_default_layer(mode: DimensionMode, version: MinecraftVersion) -> int:
    """Returns the default base Y layer according to dimension and version."""
    if mode == DimensionMode.NETHER_ROOF:
        return 127
    elif mode == DimensionMode.NETHER_FLOOR:
        return 0
    else:  # OVERWORLD
        return -64 if version == MinecraftVersion.V1_18_PLUS else 0


def get_chunk_bedrock_grid(
    chunk_x: int,
    chunk_z: int,
    mode: DimensionMode = DimensionMode.NETHER_ROOF,
    version: MinecraftVersion = MinecraftVersion.V1_12,
    world_seed: Optional[int] = None
) -> List[int]:
    """
    Generates the flat 256-element list of bedrock depths/heights for a chunk.
    Indexing: index = x * 16 + z (x in 0..15, z in 0..15).
    """
    # Seed calculation according to version
    if version == MinecraftVersion.V1_13_1_17 and world_seed is not None and mode == DimensionMode.OVERWORLD:
        base_seed = (world_seed + (chunk_x * CHUNK_SEED_X_MULT) + (chunk_z * CHUNK_SEED_Z_MULT)) & LCG_MASK
    else:
        # Classic deterministic chunk seed (1.12- and Nether 1.12-1.17)
        base_seed = (chunk_x * CHUNK_SEED_X_MULT + chunk_z * CHUNK_SEED_Z_MULT) & LCG_MASK

    s = (base_seed ^ LCG_MULTIPLIER) & LCG_MASK
    grid = [0] * 256

    if mode == DimensionMode.NETHER_ROOF:
        for i in range(256):
            s = (s * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
            bits = s >> 17
            val = bits % 5
            while bits - val + 4 < 0:
                s = (s * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
                bits = s >> 17
                val = bits % 5
            grid[i] = val
            # skip floor random
            s = (s * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
    elif mode == DimensionMode.NETHER_FLOOR:
        for i in range(256):
            # skip roof random
            s = (s * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
            # floor random
            s = (s * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
            bits = s >> 17
            val = bits % 5
            while bits - val + 4 < 0:
                s = (s * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
                bits = s >> 17
                val = bits % 5
            grid[i] = val
    else:  # OVERWORLD
        for i in range(256):
            s = (s * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
            bits = s >> 17
            val = bits % 5
            while bits - val + 4 < 0:
                s = (s * LCG_MULTIPLIER + LCG_ADDEND) & LCG_MASK
                bits = s >> 17
                val = bits % 5
            grid[i] = val

    return grid


# ==============================================================================
# 4. TARGET PATTERN STRUCTURE & CONSTRAINTS (BedrockPattern)
# ==============================================================================

@dataclass
class PatternConstraint:
    dx: int
    dz: int
    expected_depth: Optional[int] = None       # Relative depth (0..4) if known
    min_depth: Optional[int] = None           # Minimum required depth (e.g. d >= 1)
    max_depth: Optional[int] = None           # Maximum required depth (e.g. d < 1)
    expected_rotation: Optional[int] = None    # Expected texture rotation (0..3)


class BedrockPattern:
    """Represents a target bedrock pattern to search for."""

    def __init__(
        self,
        mode: DimensionMode = DimensionMode.NETHER_ROOF,
        version: MinecraftVersion = MinecraftVersion.V1_12,
        target_layer: Optional[int] = None,
        height_matrix: Optional[Union[List[List[Any]], np.ndarray]] = None,
        binary_matrix: Optional[Union[List[List[Any]], np.ndarray]] = None,
        rotation_matrix: Optional[Union[List[List[Any]], np.ndarray]] = None,
    ):
        self.mode = mode
        self.version = version
        self.target_layer = target_layer if target_layer is not None else get_default_layer(mode, version)
        self.constraints: List[PatternConstraint] = []
        self.width = 0
        self.height = 0

        if height_matrix is not None:
            self._load_from_heights(height_matrix)
        elif binary_matrix is not None:
            self._load_from_binary(binary_matrix, self.target_layer)

        if rotation_matrix is not None:
            self._apply_rotations(rotation_matrix)

    def _load_from_heights(self, matrix: Union[List[List[Any]], np.ndarray]) -> None:
        mat = np.array(matrix)
        self.height, self.width = mat.shape
        for r in range(self.height):
            for c in range(self.width):
                val = mat[r, c]
                if val is None or val == -1 or val == "?" or str(val).strip() == "?":
                    continue
                d = int(val)
                if self.mode == DimensionMode.NETHER_ROOF and d >= 120:
                    d = 127 - d  # Y=127 -> depth 0, Y=126 -> depth 1, etc.
                elif self.mode == DimensionMode.OVERWORLD and self.version == MinecraftVersion.V1_18_PLUS and d < 0:
                    d = d - (-64)  # Y=-64 -> depth 0, Y=-63 -> depth 1, etc.
                self.constraints.append(PatternConstraint(dx=r, dz=c, expected_depth=d))

    def _load_from_binary(self, matrix: Union[List[List[Any]], np.ndarray], layer: int) -> None:
        mat = np.array(matrix)
        self.height, self.width = mat.shape
        for r in range(self.height):
            for c in range(self.width):
                val = mat[r, c]
                if val is None or val == "?" or str(val).strip() == "?":
                    continue

                is_bedrock = (val in (1, True, "#", "B", "1", "b"))
                is_hole = (val in (0, False, ".", " ", "0", "-", "_"))

                if not (is_bedrock or is_hole):
                    continue

                if self.mode == DimensionMode.NETHER_ROOF:
                    required_depth = 127 - layer
                elif self.mode == DimensionMode.OVERWORLD and self.version == MinecraftVersion.V1_18_PLUS:
                    required_depth = layer - (-64)
                else:
                    required_depth = layer

                if is_bedrock:
                    self.constraints.append(PatternConstraint(dx=r, dz=c, min_depth=required_depth))
                else:
                    self.constraints.append(PatternConstraint(dx=r, dz=c, max_depth=required_depth - 1))

    def _apply_rotations(self, rot_matrix: Union[List[List[Any]], np.ndarray]) -> None:
        mat = np.array(rot_matrix)
        h, w = mat.shape
        constraint_map = {(c.dx, c.dz): c for c in self.constraints}
        for r in range(h):
            for c in range(w):
                val = mat[r, c]
                if val is not None and val != -1 and val != "?":
                    rot_idx = int(val)
                    if (r, c) in constraint_map:
                        constraint_map[(r, c)].expected_rotation = rot_idx
                    else:
                        c_obj = PatternConstraint(dx=r, dz=c, expected_rotation=rot_idx)
                        self.constraints.append(c_obj)
                        constraint_map[(r, c)] = c_obj

    def get_rotated(self, k: int) -> 'BedrockPattern':
        """Returns a pattern rotated clockwise by k * 90 degrees."""
        k = k % 4
        if k == 0:
            return self

        new_h, new_w = self.height, self.width
        new_pattern = BedrockPattern(mode=self.mode, version=self.version, target_layer=self.target_layer)
        if k == 1:
            new_h, new_w = self.width, self.height
            for c in self.constraints:
                new_dx = c.dz
                new_dz = self.height - 1 - c.dx
                new_rot = (c.expected_rotation + 1) % 4 if c.expected_rotation is not None else None
                new_pattern.constraints.append(PatternConstraint(
                    dx=new_dx, dz=new_dz,
                    expected_depth=c.expected_depth,
                    min_depth=c.min_depth, max_depth=c.max_depth,
                    expected_rotation=new_rot
                ))
        elif k == 2:
            new_h, new_w = self.height, self.width
            for c in self.constraints:
                new_dx = self.height - 1 - c.dx
                new_dz = self.width - 1 - c.dz
                new_rot = (c.expected_rotation + 2) % 4 if c.expected_rotation is not None else None
                new_pattern.constraints.append(PatternConstraint(
                    dx=new_dx, dz=new_dz,
                    expected_depth=c.expected_depth,
                    min_depth=c.min_depth, max_depth=c.max_depth,
                    expected_rotation=new_rot
                ))
        elif k == 3:
            new_h, new_w = self.width, self.height
            for c in self.constraints:
                new_dx = self.width - 1 - c.dz
                new_dz = c.dx
                new_rot = (c.expected_rotation + 3) % 4 if c.expected_rotation is not None else None
                new_pattern.constraints.append(PatternConstraint(
                    dx=new_dx, dz=new_dz,
                    expected_depth=c.expected_depth,
                    min_depth=c.min_depth, max_depth=c.max_depth,
                    expected_rotation=new_rot
                ))

        new_pattern.height = new_h
        new_pattern.width = new_w
        return new_pattern


# ==============================================================================
# 5. IMAGE ANALYSIS & PATTERN EXTRACTION (PIL / NumPy)
# ==============================================================================

class ImagePatternExtractor:
    """Image processing module to extract bedrock patterns and texture rotations."""

    @staticmethod
    def extract_from_image(
        image_path: str,
        grid_rows: int = 0,
        grid_cols: int = 0,
        mode: DimensionMode = DimensionMode.NETHER_ROOF,
        version: MinecraftVersion = MinecraftVersion.V1_12,
        target_layer: Optional[int] = None,
        detect_textures: bool = False,
        reference_texture_path: Optional[str] = None
    ) -> BedrockPattern:
        """
        Loads an image and automatically extracts binary presence/hole pattern and/or rotations.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        img = Image.open(image_path).convert("RGB")
        w, h = img.size

        if grid_cols <= 0:
            grid_cols = max(1, w // 16)
        if grid_rows <= 0:
            grid_rows = max(1, h // 16)

        block_w = w / grid_cols
        block_h = h / grid_rows

        img_gray = np.array(img.convert("L"), dtype=np.float32)

        block_means = np.zeros((grid_rows, grid_cols), dtype=np.float32)
        for r in range(grid_rows):
            for c in range(grid_cols):
                y1 = int(r * block_h)
                y2 = int((r + 1) * block_h)
                x1 = int(c * block_w)
                x2 = int((c + 1) * block_w)
                block = img_gray[y1:y2, x1:x2]
                block_means[r, c] = float(np.mean(block))

        min_v = float(np.min(block_means))
        max_v = float(np.max(block_means))
        threshold = (min_v + max_v) / 2.0

        binary_matrix = np.where(block_means >= threshold, 1, 0)

        rotation_matrix = None
        if detect_textures:
            rotation_matrix = ImagePatternExtractor._detect_rotations(
                img_gray, grid_rows, grid_cols, block_w, block_h, reference_texture_path
            )

        pattern = BedrockPattern(
            mode=mode,
            version=version,
            target_layer=target_layer,
            binary_matrix=binary_matrix,
            rotation_matrix=rotation_matrix
        )

        return pattern

    @staticmethod
    def _detect_rotations(
        img_gray: np.ndarray,
        grid_rows: int,
        grid_cols: int,
        block_w: float,
        block_h: float,
        reference_path: Optional[str] = None
    ) -> np.ndarray:
        """Detects texture orientation (0, 90, 180, 270 degrees) of each block."""
        if reference_path and os.path.exists(reference_path):
            ref_img = Image.open(reference_path).convert("L").resize((16, 16))
            ref_block = np.array(ref_img, dtype=np.float32)
        else:
            r_idx, c_idx = 0, 0
            y1 = int(r_idx * block_h)
            y2 = int((r_idx + 1) * block_h)
            x1 = int(c_idx * block_w)
            x2 = int((c_idx + 1) * block_w)
            ref_block = Image.fromarray(img_gray[y1:y2, x1:x2]).resize((16, 16))
            ref_block = np.array(ref_block, dtype=np.float32)

        ref_rotations = [np.rot90(ref_block, -k) for k in range(4)]
        rot_matrix = np.full((grid_rows, grid_cols), -1, dtype=np.int32)

        for r in range(grid_rows):
            for c in range(grid_cols):
                y1 = int(r * block_h)
                y2 = int((r + 1) * block_h)
                x1 = int(c * block_w)
                x2 = int((c + 1) * block_w)
                block = Image.fromarray(img_gray[y1:y2, x1:x2]).resize((16, 16))
                block_arr = np.array(block, dtype=np.float32)

                scores = []
                b_norm = block_arr - np.mean(block_arr)
                b_std = np.std(block_arr)
                for k in range(4):
                    ref_k = ref_rotations[k]
                    r_norm = ref_k - np.mean(ref_k)
                    r_std = np.std(ref_k)
                    denom = b_std * r_std
                    if denom > 1e-5:
                        ncc = float(np.mean(b_norm * r_norm) / denom)
                    else:
                        ncc = -float(np.mean((block_arr - ref_k) ** 2))
                    scores.append(ncc)

                best_rot = int(np.argmax(scores))
                rot_matrix[r, c] = best_rot

        return rot_matrix


# ==============================================================================
# 6. TEXT PATTERN & FILE PARSER
# ==============================================================================

def parse_pattern_from_string_or_file(
    content: str,
    mode: DimensionMode = DimensionMode.NETHER_ROOF,
    version: MinecraftVersion = MinecraftVersion.V1_12,
    target_layer: Optional[int] = None
) -> BedrockPattern:
    """
    Parses a pattern from an inline string or file path (JSON / plain text).
    """
    if os.path.exists(content):
        with open(content, "r", encoding="utf-8") as f:
            content = f.read()

    content = content.strip()

    if content.startswith("[") or content.startswith("{"):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                first_row = data[0] if data else []
                first_val = first_row[0] if first_row else 0
                if isinstance(first_val, (int, float)):
                    return BedrockPattern(mode=mode, version=version, target_layer=target_layer, height_matrix=data)
                else:
                    return BedrockPattern(mode=mode, version=version, target_layer=target_layer, binary_matrix=data)
            elif isinstance(data, dict):
                h_mat = data.get("heights") or data.get("pattern")
                b_mat = data.get("binary")
                rot_mat = data.get("rotations")
                lay = data.get("layer", target_layer)
                if h_mat:
                    return BedrockPattern(mode=mode, version=version, target_layer=lay, height_matrix=h_mat, rotation_matrix=rot_mat)
                elif b_mat:
                    return BedrockPattern(mode=mode, version=version, target_layer=lay, binary_matrix=b_mat, rotation_matrix=rot_mat)
        except Exception:
            pass

    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("//")]
    if not lines:
        raise ValueError("No valid pattern found in input.")

    first_tokens = lines[0].split()
    is_numeric = any(tok.lstrip("-").isdigit() for tok in first_tokens if tok) and len(first_tokens) > 1

    if is_numeric:
        grid: List[List[Any]] = []
        for line in lines:
            row = []
            for tok in line.split():
                if tok == "?" or tok == "x":
                    row.append(None)
                else:
                    row.append(int(tok))
            grid.append(row)
        return BedrockPattern(mode=mode, version=version, target_layer=target_layer, height_matrix=grid)
    else:
        grid = []
        for line in lines:
            row = []
            tokens = line.split() if " " in line else list(line)
            for ch in tokens:
                if ch in ("#", "B", "1", "b"):
                    row.append(1)
                elif ch in (".", " ", "0", "-", "_"):
                    row.append(0)
                else:
                    row.append("?")
            grid.append(row)
        return BedrockPattern(mode=mode, version=version, target_layer=target_layer, binary_matrix=grid)


# ==============================================================================
# 7. PARALLEL MULTIPROCESSING SEARCH ENGINE
# ==============================================================================

@dataclass
class MatchResult:
    x: int
    y: int
    z: int
    chunk_x: int
    chunk_z: int
    rotation_deg: int = 0


def _worker_scan_chunk_batch(
    args: Tuple[
        int, int, int, int,                  # min_cx, max_cx, min_cz, max_cz
        List[Dict[str, Any]],                # serialized constraints
        int,                                 # mode_val (1: NETHER_ROOF, 2: NETHER_FLOOR, 3: OVERWORLD)
        str,                                 # version_val ("1.12", "1.13-1.17", "1.18+")
        Optional[int],                       # world_seed
        int                                  # rotation_deg
    ]
) -> List[Tuple[int, int, int, int, int, int]]:
    """Worker process function scanning a batch of chunks."""
    min_cx, max_cx, min_cz, max_cz, serialized_constraints, mode_val, version_str, world_seed, rot_deg = args

    constraints = [
        PatternConstraint(
            dx=c["dx"], dz=c["dz"],
            expected_depth=c.get("expected_depth"),
            min_depth=c.get("min_depth"),
            max_depth=c.get("max_depth"),
            expected_rotation=c.get("expected_rotation")
        ) for c in serialized_constraints
    ]

    if not constraints:
        return []

    mode = (
        DimensionMode.NETHER_ROOF if mode_val == 1
        else DimensionMode.NETHER_FLOOR if mode_val == 2
        else DimensionMode.OVERWORLD
    )
    version = MinecraftVersion(version_str)

    chunk_cache: Dict[Tuple[int, int], List[int]] = {}

    def get_chunk(cx: int, cz: int) -> List[int]:
        k = (cx, cz)
        g = chunk_cache.get(k)
        if g is None:
            g = get_chunk_bedrock_grid(cx, cz, mode, version, world_seed)
            chunk_cache[k] = g
        return g

    anchor = constraints[0]
    matches: List[Tuple[int, int, int, int, int, int]] = []

    target_y = get_default_layer(mode, version)

    for cx in range(min_cx, max_cx + 1):
        for cz in range(min_cz, max_cz + 1):
            grid = get_chunk(cx, cz)

            for in_x in range(16):
                for in_z in range(16):
                    x0 = (cx << 4) + in_x - anchor.dx
                    z0 = (cz << 4) + in_z - anchor.dz

                    # 1. Fast intra-chunk early exit
                    intra_failed = False
                    for c in constraints:
                        ix = in_x - anchor.dx + c.dx
                        iz = in_z - anchor.dz + c.dz
                        if 0 <= ix < 16 and 0 <= iz < 16:
                            depth = grid[ix * 16 + iz]
                            if c.expected_depth is not None and depth != c.expected_depth:
                                intra_failed = True
                                break
                            if c.min_depth is not None and depth < c.min_depth:
                                intra_failed = True
                                break
                            if c.max_depth is not None and depth > c.max_depth:
                                intra_failed = True
                                break
                    if intra_failed:
                        continue

                    # 2. Inter-chunk boundary check
                    inter_failed = False
                    for c in constraints:
                        ix = in_x - anchor.dx + c.dx
                        iz = in_z - anchor.dz + c.dz
                        if not (0 <= ix < 16 and 0 <= iz < 16):
                            wx = x0 + c.dx
                            wz = z0 + c.dz
                            neighbor_grid = get_chunk(wx >> 4, wz >> 4)
                            depth = neighbor_grid[(wx & 15) * 16 + (wz & 15)]
                            if c.expected_depth is not None and depth != c.expected_depth:
                                inter_failed = True
                                break
                            if c.min_depth is not None and depth < c.min_depth:
                                inter_failed = True
                                break
                            if c.max_depth is not None and depth > c.max_depth:
                                inter_failed = True
                                break
                    if inter_failed:
                        continue

                    # 3. Texture rotation validation if specified
                    rot_failed = False
                    for c in constraints:
                        if c.expected_rotation is not None:
                            wx = x0 + c.dx
                            wz = z0 + c.dz
                            actual_rot = get_texture_rotation_index(wx, target_y, wz)
                            if actual_rot != c.expected_rotation:
                                rot_failed = True
                                break
                    if rot_failed:
                        continue

                    matches.append((x0, target_y, z0, x0 >> 4, z0 >> 4, rot_deg))

        if len(chunk_cache) > 4000:
            chunk_cache.clear()

    return matches


class BedrockSearchEngine:
    """Parallel search engine orchestrating scanning processes."""

    def __init__(
        self,
        pattern: BedrockPattern,
        world_seed: Optional[int] = None,
        all_rotations: bool = False,
        threads: Optional[int] = None
    ):
        self.pattern = pattern
        self.world_seed = world_seed
        self.all_rotations = all_rotations
        self.threads = threads or max(1, os.cpu_count() or 1)

    def search_bounds(
        self,
        min_x: int,
        min_z: int,
        max_x: int,
        max_z: int,
        batch_size: int = 128
    ) -> List[MatchResult]:
        """
        Executes exhaustive search within the bounds [min_x..max_x, min_z..max_z].
        """
        min_cx = min_x >> 4
        max_cx = max_x >> 4
        min_cz = min_z >> 4
        max_cz = max_z >> 4

        total_chunks_x = max_cx - min_cx + 1
        total_chunks_z = max_cz - min_cz + 1
        total_chunks = total_chunks_x * total_chunks_z

        print(f"\n" + "=" * 70)
        print(f"[*] STARTING PARALLEL BEDROCK SCAN")
        print(f"[*] Minecraft Ver  : {self.pattern.version.value}")
        print(f"[*] Dimension/Mode : {self.pattern.mode.value} (Base Layer Y={self.pattern.target_layer})")
        print(f"[*] World Seed     : {self.world_seed if self.world_seed is not None else 'None (Deterministic / Seed-Independent)'}")
        print(f"[*] Block Bounds   : X:[{min_x:,} .. {max_x:,}], Z:[{min_z:,} .. {max_z:,}]")
        print(f"[*] Chunk Bounds   : CX:[{min_cx:,} .. {max_cx:,}], CZ:[{min_cz:,} .. {max_cz:,}]")
        print(f"[*] Total Chunks   : {total_chunks:,} (~{total_chunks * 256:,} blocks)")
        print(f"[*] Active Threads : {self.threads}")
        print(f"[*] Rotations      : {'All 4 orientations (0°, 90°, 180°, 270°)' if self.all_rotations else 'Original orientation (0°)'}")
        print("=" * 70)

        patterns_to_test: List[Tuple[BedrockPattern, int]] = []
        if self.all_rotations:
            for k, deg in enumerate([0, 90, 180, 270]):
                patterns_to_test.append((self.pattern.get_rotated(k), deg))
        else:
            patterns_to_test.append((self.pattern, 0))

        mode_val = (
            1 if self.pattern.mode == DimensionMode.NETHER_ROOF
            else 2 if self.pattern.mode == DimensionMode.NETHER_FLOOR
            else 3
        )
        version_str = self.pattern.version.value

        tasks = []
        for pat, deg in patterns_to_test:
            serialized_constraints = [
                {
                    "dx": c.dx, "dz": c.dz,
                    "expected_depth": c.expected_depth,
                    "min_depth": c.min_depth,
                    "max_depth": c.max_depth,
                    "expected_rotation": c.expected_rotation
                } for c in pat.constraints
            ]

            for cx in range(min_cx, max_cx + 1, batch_size):
                cx_end = min(cx + batch_size - 1, max_cx)
                for cz in range(min_cz, max_cz + 1, batch_size):
                    cz_end = min(cz + batch_size - 1, max_cz)
                    tasks.append((cx, cx_end, cz, cz_end, serialized_constraints, mode_val, version_str, self.world_seed, deg))

        start_time = time.perf_counter()
        results: List[MatchResult] = []
        total_tasks_chunks = total_chunks * len(patterns_to_test)

        with mp.Pool(processes=self.threads) as pool:
            for batch_matches in pool.imap_unordered(_worker_scan_chunk_batch, tasks):
                for m in batch_matches:
                    res = MatchResult(
                        x=m[0], y=m[1], z=m[2],
                        chunk_x=m[3], chunk_z=m[4],
                        rotation_deg=m[5]
                    )
                    results.append(res)
                    print(f"\n[+] MATCH FOUND!")
                    print(f"    --> Block Coordinates : X={res.x:,}, Y={res.y}, Z={res.z:,}")
                    print(f"    --> Chunk Coordinates : CX={res.chunk_x:,}, CZ={res.chunk_z:,}")
                    print(f"    --> Orientation       : {res.rotation_deg}°")

        elapsed = time.perf_counter() - start_time
        speed = total_tasks_chunks / elapsed if elapsed > 0 else 0

        print("\n" + "=" * 70)
        print(f"[*] SCAN FINISHED IN {elapsed:.2f}s")
        print(f"[*] Average Speed  : {speed:,.0f} chunks/sec (~{speed * 256:,.0f} blocks/sec)")
        print(f"[*] Total Matches  : {len(results)}")
        print("=" * 70)

        return results


# ==============================================================================
# 8. VISUALIZATION & BENCHMARK UTILITIES
# ==============================================================================

def print_chunk_bedrock_map(
    chunk_x: int,
    chunk_z: int,
    mode: DimensionMode,
    version: MinecraftVersion,
    layer: Optional[int] = None
) -> None:
    """Prints the ASCII map of a chunk's bedrock layer."""
    if layer is None:
        layer = get_default_layer(mode, version)
    grid = get_chunk_bedrock_grid(chunk_x, chunk_z, mode, version)
    print(f"\nChunk ({chunk_x}, {chunk_z}) Map - Mode: {mode.value} | Version: {version.value} (Y={layer}):")
    print("    " + " ".join(f"{z:X}" for z in range(16)))
    print("   +" + "-" * 32)
    for x in range(16):
        row_chars = []
        for z in range(16):
            depth = grid[x * 16 + z]
            if mode == DimensionMode.NETHER_ROOF:
                is_solid = (127 - depth <= layer)
            elif mode == DimensionMode.OVERWORLD and version == MinecraftVersion.V1_18_PLUS:
                is_solid = (-64 + depth >= layer)
            else:
                is_solid = (depth >= layer)
            row_chars.append("# " if is_solid else ". ")
        print(f"{x:2X} |" + "".join(row_chars))


def run_benchmark(threads: int = 4, n_chunks: int = 1_000_000) -> None:
    """Runs a throughput benchmark for chunk generation and jump table filtering."""
    print(f"\n[*] HIGH PERFORMANCE BENCHMARK ({n_chunks:,} chunks on {threads} cores)...")

    start = time.perf_counter()
    cx = np.random.randint(-10000, 10000, size=n_chunks, dtype=np.int64)
    cz = np.random.randint(-10000, 10000, size=n_chunks, dtype=np.int64)

    s0 = ((cx.astype(np.uint64) * np.uint64(CHUNK_SEED_X_MULT) + cz.astype(np.uint64) * np.uint64(CHUNK_SEED_Z_MULT)) ^ np.uint64(LCG_MULTIPLIER)) & np.uint64(LCG_MASK)

    k0 = 5 * 16 + 5 + 1
    s_k0 = (s0 * AK_TABLE[k0] + BK_TABLE[k0]) & np.uint64(LCG_MASK)
    v0 = (s_k0 >> np.uint64(17)) % np.uint64(5)
    mask = (v0 == np.uint64(3))

    s_cand = s0[mask]
    k1 = 5 * 16 + 6 + 1
    s_k1 = (s_cand * AK_TABLE[k1] + BK_TABLE[k1]) & np.uint64(LCG_MASK)
    v1 = (s_k1 >> np.uint64(17)) % np.uint64(5)
    mask2 = (v1 == np.uint64(4))

    elapsed = time.perf_counter() - start
    rate = n_chunks / elapsed
    print(f"[+] Result : {n_chunks:,} chunks processed in {elapsed*1000:.2f}ms")
    print(f"[+] Vectorized Throughput : {rate:,.0f} chunks/sec (~{rate * 256:,.0f} blocks/sec)")


# ==============================================================================
# 9. CLI INTERFACE (ARGPARSE)
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Minecraft Bedrock Reverse-Engineering & Coordinate Finder (Java Edition).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported Versions:
-------------------
  1.12, 1.12.2, legacy  : Minecraft 1.0 - 1.12.2 (Nether & Overworld bedrock is 100% seed-independent).
  1.13-1.17, 1.16.5     : Minecraft 1.13 - 1.17.1 (Nether seed-independent, Overworld uses decoration seed).
  1.18+, 1.20, modern   : Minecraft 1.18 - 1.21+ (Caves & Cliffs, Overworld bedrock at Y=-64..-60).

Usage Examples:
---------------
1. Search in Minecraft 1.12 Nether roof (seed-independent):
   python3 bedrock.py --version 1.12 --mode nether-roof --matrix "# . # . .\\n# . # . .\\n# # # . ." --radius 5000

2. Search in Minecraft 1.18+ Overworld at negative Y (Y=-64):
   python3 bedrock.py --version 1.18+ --mode overworld --matrix "4 3 2 1 0" --radius 10000

3. Search from a screenshot with automatic rotation testing:
   python3 bedrock.py --image screenshot.png --version 1.12 --mode nether-roof --all-rotations

4. Inspect chunk bedrock map:
   python3 bedrock.py --export-chunk 85 30 --version 1.12 --mode nether-roof --layer 125

5. Run performance benchmark:
   python3 bedrock.py --benchmark
        """
    )

    parser.add_argument("--version", "-v", type=str, default="1.12", help="Minecraft version (e.g. '1.12', '1.16.5', '1.18+', '1.20', 'legacy'). Default: 1.12.")
    parser.add_argument("--matrix", "-p", type=str, help="Pattern as inline string or file path (.txt / .json).")
    parser.add_argument("--image", "-i", type=str, help="Path to bedrock screenshot or crop image.")
    parser.add_argument("--seed", "-s", type=int, default=None, help="World Seed (optional in seed-independent modes like 1.12-).")
    parser.add_argument("--mode", "-m", type=str, choices=["nether-roof", "nether-floor", "overworld"], default="nether-roof", help="Target dimension / layer (default: nether-roof).")
    parser.add_argument("--layer", "-y", type=int, default=None, help="Target Y layer (e.g. 127, 126, 4, 3, -64, -63...).")
    parser.add_argument("--radius", "-r", type=int, default=10000, help="Search radius in blocks around center (default: 10000).")
    parser.add_argument("--radius-chunks", type=int, default=None, help="Search radius in chunks.")
    parser.add_argument("--center", "-c", type=int, nargs=2, default=[0, 0], metavar=("X", "Z"), help="Search center X Z (default: 0 0).")
    parser.add_argument("--bounds", type=int, nargs=4, metavar=("MIN_X", "MIN_Z", "MAX_X", "MAX_Z"), help="Custom bounding box coordinates.")
    parser.add_argument("--threads", "-t", type=int, default=None, help="Number of worker processes (default: CPU core count).")
    parser.add_argument("--all-rotations", "-R", action="store_true", help="Automatically test all 4 cardinal orientations (0°, 90°, 180°, 270°).")
    parser.add_argument("--detect-textures", action="store_true", help="Enable texture rotation detection on provided image.")
    parser.add_argument("--reference-texture", type=str, default=None, help="Path to a 16x16 reference bedrock texture.")
    parser.add_argument("--grid-size", type=int, nargs=2, metavar=("ROWS", "COLS"), help="Grid dimensions for image extraction (e.g. 8 8).")
    parser.add_argument("--export-chunk", type=int, nargs=2, metavar=("CHUNK_X", "CHUNK_Z"), help="Prints ASCII map of a chunk for inspection.")
    parser.add_argument("--benchmark", action="store_true", help="Runs scanner performance benchmark.")
    parser.add_argument("--gui", action="store_true", help="Launches the interactive Modern Web User Interface.")

    args = parser.parse_args()

    # GUI Launcher
    if args.gui:
        from web_gui import start_web_gui
        start_web_gui()
        return

    # Benchmark
    if args.benchmark:
        run_benchmark(threads=args.threads or (os.cpu_count() or 4))
        return

    # Parse version & dimension mode
    version = MinecraftVersion.parse(args.version)
    mode = DimensionMode(args.mode)

    # Export a chunk
    if args.export_chunk:
        cx, cz = args.export_chunk
        print_chunk_bedrock_map(cx, cz, mode, version, args.layer)
        return

    # Check inputs
    if not args.matrix and not args.image:
        print("[!] Error: You must provide either a pattern via --matrix or an image via --image.")
        parser.print_help()
        sys.exit(1)

    # Load pattern
    if args.matrix:
        pattern = parse_pattern_from_string_or_file(args.matrix, mode=mode, version=version, target_layer=args.layer)
    else:
        grid_rows, grid_cols = args.grid_size if args.grid_size else (0, 0)
        pattern = ImagePatternExtractor.extract_from_image(
            image_path=args.image,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            mode=mode,
            version=version,
            target_layer=args.layer,
            detect_textures=args.detect_textures,
            reference_texture_path=args.reference_texture
        )

    # Determine search bounds
    if args.bounds:
        min_x, min_z, max_x, max_z = args.bounds
    elif args.radius_chunks is not None:
        cx0, cz0 = args.center[0] >> 4, args.center[1] >> 4
        min_x = (cx0 - args.radius_chunks) << 4
        max_x = (cx0 + args.radius_chunks) << 4
        min_z = (cz0 - args.radius_chunks) << 4
        max_z = (cz0 + args.radius_chunks) << 4
    else:
        cx, cz = args.center
        min_x = cx - args.radius
        max_x = cx + args.radius
        min_z = cz - args.radius
        max_z = cz + args.radius

    # Launch search engine
    engine = BedrockSearchEngine(
        pattern=pattern,
        world_seed=args.seed,
        all_rotations=args.all_rotations,
        threads=args.threads
    )

    matches = engine.search_bounds(min_x, min_z, max_x, max_z)

    # Final summary
    print("\n" + "=" * 70)
    print(f"[*] SEARCH SUMMARY: {len(matches)} match(es) found")
    for i, m in enumerate(matches, 1):
        print(f"  [{i}] Block: ({m.x}, {m.y}, {m.z}) | Chunk: ({m.chunk_x}, {m.chunk_z}) | Rotation: {m.rotation_deg}°")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
