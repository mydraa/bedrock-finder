# Minecraft Bedrock Pattern Finder & Reverse-Engineering Engine

A high-performance, standalone Python tool to locate exact $(X, Y, Z)$ coordinates of bedrock formations in Minecraft Java Edition from world seeds, pattern matrices, or screenshots.

---

## Features

- **Bit-Exact Java LCG PRNG Emulation:** Replicates `java.util.Random` 48-bit Linear Congruential Generator.
- **LCG Jump Tables:** $O(1)$ computation of LCG states for arbitrary block offsets within chunks.
- **High-Throughput Vectorization:** NumPy-accelerated scanning capable of processing millions of chunks per second.
- **Parallel Multiprocessing Engine:** Multi-core search with cascaded early-exit filters (80% rejection on 1st anchor, 96% on 2nd, 99.2% on 3rd).
- **Coordinate Random & Texture Rotation:** Emulates `MathHelper.getCoordinateRandom(x, y, z)` to extract and match block texture rotations (0°, 90°, 180°, 270°).
- **Flexible Input Formats:**
  - Text grids: numeric depths (`0..4`, `123..127`) or binary presence (`#` for bedrock, `.` for hole/air, `?` for wildcard).
  - JSON format (`[[...], [...]]`).
  - Image / Screenshot analysis via PIL & NumPy (automatic brightness thresholding & normalized cross-correlation for texture rotation).
- **Orientation Invariance (`--all-rotations`):** Automatically tests all 4 cardinal orientations (0°, 90°, 180°, 270°).

---

## Installation

```bash
git clone https://github.com/mydraa/bedrock-finder.git
cd bedrock-finder
pip install -r requirements.txt
```

---

## Usage

### 1. Search with a Text Matrix
```bash
python3 bedrock.py --matrix "# . # . .
# . # . .
# # # . .
# # # # #
. # . . ." --mode nether-roof --layer 125 --radius 5000
```

### 2. Search with All Cardinal Rotations (0°, 90°, 180°, 270°)
```bash
python3 bedrock.py --matrix pattern.txt --mode overworld --radius 10000 --all-rotations
```

### 3. Search from a Screenshot / Cropped Image
```bash
python3 bedrock.py --image screenshot.png --grid-size 8 8 --mode nether-roof --layer 127 --radius 20000
```

### 4. Search with Texture Rotation Detection
```bash
python3 bedrock.py --image crop.png --detect-textures --radius 10000
```

### 5. Inspect / Export a Chunk Bedrock Map
```bash
python3 bedrock.py --export-chunk 85 30 --mode nether-roof --layer 125
```

### 6. Performance Benchmark
```bash
python3 bedrock.py --benchmark
```

---

## CLI Options

| Option | Description |
|---|---|
| `--matrix`, `-p` | Pattern as inline string or file path (`.txt` / `.json`) |
| `--image`, `-i` | Path to screenshot or cropped bedrock image |
| `--seed`, `-s` | World Seed (optional in pre-1.18 deterministic mode) |
| `--mode`, `-m` | Target dimension: `nether-roof` (default), `nether-floor`, `overworld` |
| `--layer`, `-y` | Target Y layer (e.g. 127, 126, 4, 3...) |
| `--radius`, `-r` | Search radius in blocks around center (default: 10000) |
| `--radius-chunks` | Search radius in chunks |
| `--center`, `-c` | Search center `X Z` (default: 0 0) |
| `--bounds` | Custom bounding box `MIN_X MIN_Z MAX_X MAX_Z` |
| `--threads`, `-t` | Worker process count (default: CPU core count) |
| `--all-rotations`, `-R` | Test all 4 cardinal orientations (0°, 90°, 180°, 270°) |
| `--detect-textures` | Enable texture rotation analysis on image input |
| `--grid-size` | Image grid size `ROWS COLS` |
| `--export-chunk` | Print ASCII map of a chunk `CHUNK_X CHUNK_Z` |
| `--benchmark` | Run scanner performance benchmark |

---

## License

MIT License.
