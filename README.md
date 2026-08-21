# Minecraft Bedrock Pattern Finder & Reverse-Engineering Engine

A high-performance tool & modern Web Interface to locate exact $(X, Y, Z)$ coordinates of bedrock formations in Minecraft Java Edition across multiple versions (1.0 to 1.21+) from world seeds, pattern matrices, or screenshots.

---

## 🚀 Instant Deployment on Vercel

This repository is **100% compatible with Vercel** (static zero-configuration hosting with in-browser multi-threaded Web Workers).

### Option 1: Deploy with Vercel CLI
```bash
# Install Vercel CLI (if not already installed)
npm install -g vercel

# Deploy instantly
vercel
# or for production
vercel --prod
```

### Option 2: Deploy with Git & Vercel Dashboard
1. Push this repository to GitHub / GitLab / Bitbucket.
2. Go to [Vercel Dashboard](https://vercel.com/new).
3. Import your repository and click **Deploy** (no build settings required).

### Option 3: Run Locally
```bash
# Method A: Python local server
python3 -m http.server 3000

# Method B: Python GUI launcher
python3 bedrock.py --gui
```
Then open `http://localhost:3000` in your browser.

---

## 🌐 Web Features

- **Multi-Threaded In-Browser Engine:** Uses `Web Workers` and `BigInt` 48-bit LCG arithmetic to scan millions of blocks per second directly on the client's CPU without server limits or timeouts.
- **Interactive Visual Grid Editor:** Click cells to toggle Solid Bedrock (`#`), Hole (`.`), or Wildcard (`?`), with drag-to-draw support.
- **Screenshot / Image Uploader:** Drag & drop bedrock screenshots with automatic grayscale thresholding and texture rotation detection.
- **16×16 Chunk Bedrock Inspector:** Interactive canvas viewer showing exact bedrock depths and solid/air states at any Y level.
- **Instant Teleport Command:** One-click `/tp @s X Y Z` generator and JSON export.
- **Preset Library:** Pre-configured test patterns (Nether 5x5, 4x4 Holes, Overworld stairs, Cross formations).

---

## Supported Minecraft Versions

| Version Flag | Version Range | Nether Roof ($Y=123..127$) | Nether Floor ($Y=0..4$) | Overworld Floor |
|---|---|---|---|---|
| `--version 1.12` *(default)* | 1.0 - 1.12.2 (Legacy) | ❌ Seed-independent | ❌ Seed-independent | ❌ Seed-independent ($Y=0..4$) |
| `--version 1.13-1.17` | 1.13 - 1.17.1 | ❌ Seed-independent | ❌ Seed-independent |  World seed dependent ($Y=0..4$) |
| `--version 1.18+` | 1.18 - 1.21+ (Caves & Cliffs) | ❌ Seed-independent | ❌ Seed-independent |  Negative depths ($Y=-64..-60$) |

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

### 5. Inspect / Export a Chunk Bedrock Map
```bash
python3 bedrock.py --export-chunk 85 30 --version 1.12 --mode nether-roof --layer 125
```

### 6. Run Scanner Benchmark
```bash
python3 bedrock.py --benchmark
```

---

## License

MIT License.
