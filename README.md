# Minecraft Bedrock Pattern Finder & Reverse-Engineering Engine

A high-performance, standalone Python tool & Web Interface to locate exact $(X, Y, Z)$ coordinates of bedrock formations in Minecraft Java Edition across multiple versions (1.0 to 1.21+) from world seeds, pattern matrices, or screenshots.

---

## Interactive Web GUI

Launch the built-in modern interactive Web User Interface (zero external dependencies):

```bash
python3 bedrock.py --gui
# or
python3 web_gui.py
```

This opens an interactive interface in your browser (`http://localhost:5000`) featuring:
- **Interactive Visual Grid Editor:** Click cells to toggle Solid Bedrock (`#`), Hole (`.`), or Wildcard/Unknown (`?`).
- **Image / Screenshot Drag & Drop:** Upload screenshots with auto-detection of holes and block texture rotations.
- **Live Search Status & Metrics:** Real-time throughput (chunks/sec), scanned chunk counter, progress bar.
- **Coordinates & Chunk Map Inspector:** View found coordinates and explore 16x16 chunk bedrock layers.

---

## Supported Minecraft Versions

| Version Flag | Version Range | Nether Roof ($Y=123..127$) | Nether Floor ($Y=0..4$) | Overworld Floor |
|---|---|---|---|---|
| `--version 1.12` *(default)* | 1.0 - 1.12.2 (Legacy) | ❌ Seed-independent | ❌ Seed-independent | ❌ Seed-independent ($Y=0..4$) |
| `--version 1.13-1.17` | 1.13 - 1.17.1 | ❌ Seed-independent | ❌ Seed-independent |  World seed dependent ($Y=0..4$) |
| `--version 1.18+` | 1.18 - 1.21+ (Caves & Cliffs) | ❌ Seed-independent | ❌ Seed-independent |  Negative depths ($Y=-64..-60$) |

---

## Features

- **Interactive Web Interface:** Modern web UI with clickable grid editor and image drag & drop.
- **Multi-Version Architecture:** Seamlessly adapt bedrock layers, depths, and coordinate spaces between legacy (1.12-), intermediate (1.13-1.17), and modern (1.18+) Minecraft versions.
- **Bit-Exact Java LCG PRNG Emulation:** Replicates `java.util.Random` 48-bit Linear Congruential Generator.
- **LCG Jump Tables:** $O(1)$ computation of LCG states for arbitrary block offsets within chunks.
- **High-Throughput Vectorization:** NumPy-accelerated scanning capable of processing millions of chunks per second.
- **Parallel Multiprocessing Engine:** Multi-core search with cascaded early-exit filters (80% rejection on 1st anchor, 96% on 2nd, 99.2% on 3rd).
- **Coordinate Random & Texture Rotation:** Emulates `MathHelper.getCoordinateRandom(x, y, z)` to extract and match block texture rotations (0°, 90°, 180°, 270°).
- **Flexible Input Formats:**
  - Interactive clickable grid.
  - Text grids: numeric depths (`0..4`, `123..127`, `-64..-60`) or binary presence (`#` for bedrock, `.` for hole/air, `?` for wildcard).
  - JSON format (`[[...], [...]]`).
  - Image / Screenshot analysis via PIL & NumPy.
- **Orientation Invariance (`--all-rotations`):** Automatically tests all 4 cardinal orientations (0°, 90°, 180°, 270°).

---

## Installation

```bash
git clone https://github.com/mydraa/bedrock-finder.git
cd bedrock-finder
pip install -r requirements.txt
```

---

## CLI Usage Examples

### 1. Launch Web GUI
```bash
python3 bedrock.py --gui
```

### 2. Search in Minecraft 1.12 Nether Roof (Seed-Independent)
```bash
python3 bedrock.py --version 1.12 --mode nether-roof --layer 125 --matrix "# . # . .
# . # . .
# # # . .
# # # # #
. # . . ." --radius 5000
```

### 3. Search in Minecraft 1.18+ Overworld (Negative Y: -64..-60)
```bash
python3 bedrock.py --version 1.18+ --mode overworld --layer -62 --matrix "# . . #
# # # #
# # . #" --radius 10000
```

### 4. Search with All Cardinal Rotations (0°, 90°, 180°, 270°)
```bash
python3 bedrock.py --matrix pattern.txt --version 1.12 --mode overworld --radius 10000 --all-rotations
```

### 5. Search from a Screenshot / Cropped Image
```bash
python3 bedrock.py --image screenshot.png --version 1.12 --grid-size 8 8 --mode nether-roof --layer 127 --radius 20000
```

### 6. Search with Texture Rotation Detection
```bash
python3 bedrock.py --image crop.png --detect-textures --radius 10000
```

### 7. Inspect / Export a Chunk Bedrock Map
```bash
# Export 1.18+ Overworld chunk at Y=-62
python3 bedrock.py --export-chunk 85 30 --version 1.18+ --mode overworld --layer -62

# Export 1.12 Nether roof chunk at Y=125
python3 bedrock.py --export-chunk 85 30 --version 1.12 --mode nether-roof --layer 125
```

### 8. Performance Benchmark
```bash
python3 bedrock.py --benchmark
```

---

## CLI Options

| Option | Description |
|---|---|
| `--gui` | Launch the interactive Modern Web User Interface |
| `--version`, `-v` | Minecraft version: `1.12` (default), `1.13-1.17`, `1.18+`, `1.16.5`, `1.20`, etc. |
| `--matrix`, `-p` | Pattern as inline string or file path (`.txt` / `.json`) |
| `--image`, `-i` | Path to screenshot or cropped bedrock image |
| `--seed`, `-s` | World Seed (optional in seed-independent modes like 1.12-) |
| `--mode`, `-m` | Target dimension: `nether-roof` (default), `nether-floor`, `overworld` |
| `--layer`, `-y` | Target Y layer (e.g. 127, 126, 4, 3, -64, -63...) |
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
