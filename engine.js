/**
 * Minecraft Bedrock Generation & PRNG Engine in Modern JavaScript (ES6 / BigInt)
 * Bit-exact reproduction of Minecraft Java Edition (1.0 -> 1.21+) bedrock algorithms.
 */

const LCG_MULT = 0x5DEECE66Dn;
const LCG_ADD = 0xBn;
const LCG_MASK = (1n << 48n) - 1n;

const CHUNK_X_MULT = 341873128712n;
const CHUNK_Z_MULT = 132897987541n;

const COORD_RAND_X_MULT = 3129871n;
const COORD_RAND_Z_MULT = 116129781n;
const COORD_RAND_SQ_MULT = 42317861n;
const COORD_RAND_LIN_MULT = 11n;
const UINT64_MASK = 0xFFFFFFFFFFFFFFFFn;

// Precompute LCG Jump Tables: S_k = (S_0 * A_k + B_k) mod 2^48
const AK_TABLE = new BigUint64Array(513);
const BK_TABLE = new BigUint64Array(513);

(function initJumpTables() {
    let curA = 1n;
    let curB = 0n;
    for (let k = 0; k <= 512; k++) {
        AK_TABLE[k] = curA & LCG_MASK;
        BK_TABLE[k] = curB & LCG_MASK;
        curA = (curA * LCG_MULT) & LCG_MASK;
        curB = (curB * LCG_MULT + LCG_ADD) & LCG_MASK;
    }
})();

/**
 * Emulates Java 32-bit signed integer multiplication and overflow.
 */
function toInt32(val) {
    const num = Number(BigInt.asIntN(32, BigInt(val)));
    return BigInt(num);
}

/**
 * MathHelper.getCoordinateRandom(x, y, z) in Java Minecraft
 */
function getCoordinateRandom(x, y, z) {
    const bx = BigInt(x);
    const by = BigInt(y);
    const bz = BigInt(z);

    // Java does: (long)(x * 3129871) ^ (long)z * 116129781L ^ (long)y;
    const xPart = toInt32(bx * COORD_RAND_X_MULT);
    let l = (xPart ^ (bz * COORD_RAND_Z_MULT) ^ by) & UINT64_MASK;
    l = (l * l * COORD_RAND_SQ_MULT + l * COORD_RAND_LIN_MULT) & UINT64_MASK;
    return (l >> 16n) & UINT64_MASK;
}

/**
 * Texture rotation index (0: 0°, 1: 90°, 2: 180°, 3: 270°)
 */
function getTextureRotationIndex(x, y, z) {
    const rnd = getCoordinateRandom(x, y, z);
    return Number((rnd >> 16n) & 3n);
}

/**
 * Default Y level according to dimension mode and version
 */
function getDefaultLayer(mode, version) {
    if (mode === 'nether-roof') return 127;
    if (mode === 'nether-floor') return 0;
    if (mode === 'overworld') {
        return (version === '1.18+') ? -64 : 0;
    }
    return 127;
}

/**
 * Computes the 256-element bedrock height/depth grid for a single chunk.
 * Indexing: index = x * 16 + z (x in 0..15, z in 0..15).
 */
function getChunkBedrockGrid(chunkX, chunkZ, mode = 'nether-roof', version = '1.12', worldSeed = null) {
    const cx = BigInt(chunkX);
    const cz = BigInt(chunkZ);

    let baseSeed;
    if (version === '1.13-1.17' && worldSeed !== null && mode === 'overworld') {
        const ws = BigInt(worldSeed);
        baseSeed = (ws + cx * CHUNK_X_MULT + cz * CHUNK_Z_MULT) & LCG_MASK;
    } else {
        baseSeed = (cx * CHUNK_X_MULT + cz * CHUNK_Z_MULT) & LCG_MASK;
    }

    let s = (baseSeed ^ LCG_MULT) & LCG_MASK;
    const grid = new Int32Array(256);

    const LCG_2POW31 = 1n << 31n;

    if (mode === 'nether-roof') {
        for (let i = 0; i < 256; i++) {
            // Roof PRNG roll
            s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
            let bits = s >> 17n;
            let val = bits % 5n;
            while ((bits - val + 4n) >= LCG_2POW31) {
                s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
                bits = s >> 17n;
                val = bits % 5n;
            }
            grid[i] = Number(val);

            // Skip floor PRNG roll
            s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
            bits = s >> 17n;
            val = bits % 5n;
            while ((bits - val + 4n) >= LCG_2POW31) {
                s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
                bits = s >> 17n;
                val = bits % 5n;
            }
        }
    } else if (mode === 'nether-floor') {
        for (let i = 0; i < 256; i++) {
            // Skip roof PRNG roll
            s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
            let bits = s >> 17n;
            let val = bits % 5n;
            while ((bits - val + 4n) >= LCG_2POW31) {
                s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
                bits = s >> 17n;
                val = bits % 5n;
            }

            // Floor PRNG roll
            s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
            bits = s >> 17n;
            val = bits % 5n;
            while ((bits - val + 4n) >= LCG_2POW31) {
                s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
                bits = s >> 17n;
                val = bits % 5n;
            }
            grid[i] = Number(val);
        }
    } else { // Overworld
        for (let i = 0; i < 256; i++) {
            s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
            let bits = s >> 17n;
            let val = bits % 5n;
            while ((bits - val + 4n) >= LCG_2POW31) {
                s = (s * LCG_MULT + LCG_ADD) & LCG_MASK;
                bits = s >> 17n;
                val = bits % 5n;
            }
            grid[i] = Number(val);
        }
    }

    return grid;
}

/**
 * BedrockPattern class representing constraints to search for.
 */
class BedrockPattern {
    constructor(options = {}) {
        this.mode = options.mode || 'nether-roof';
        this.version = options.version || '1.12';
        this.targetLayer = options.targetLayer !== undefined && options.targetLayer !== null 
            ? options.targetLayer 
            : getDefaultLayer(this.mode, this.version);
        this.constraints = [];
        this.height = 0;
        this.width = 0;

        if (options.heightMatrix) {
            this.loadFromHeights(options.heightMatrix);
        } else if (options.binaryMatrix) {
            this.loadFromBinary(options.binaryMatrix, this.targetLayer);
        }

        if (options.rotationMatrix) {
            this.applyRotations(options.rotationMatrix);
        }
    }

    loadFromHeights(matrix) {
        this.height = matrix.length;
        this.width = matrix[0] ? matrix[0].length : 0;
        for (let r = 0; r < this.height; r++) {
            for (let c = 0; c < this.width; c++) {
                const val = matrix[r][c];
                if (val === null || val === undefined || val === -1 || val === '?' || val === 'x') continue;
                let d = parseInt(val, 10);
                if (isNaN(d)) continue;

                if (this.mode === 'nether-roof' && d >= 120) {
                    d = 127 - d;
                } else if (this.mode === 'overworld' && this.version === '1.18+' && d < 0) {
                    d = d - (-64);
                }
                this.constraints.push({ dx: r, dz: c, expectedDepth: d });
            }
        }
    }

    loadFromBinary(matrix, layer) {
        this.height = matrix.length;
        this.width = matrix[0] ? matrix[0].length : 0;
        for (let r = 0; r < this.height; r++) {
            for (let c = 0; c < this.width; c++) {
                const val = matrix[r][c];
                if (val === null || val === undefined || val === '?' || val === 'x') continue;

                const isBedrock = (val === 1 || val === true || val === '#' || val === 'B' || val === '1' || val === 'b');
                const isHole = (val === 0 || val === false || val === '.' || val === ' ' || val === '0' || val === '-' || val === '_');

                if (!isBedrock && !isHole) continue;

                let requiredDepth;
                if (this.mode === 'nether-roof') {
                    requiredDepth = 127 - layer;
                } else if (this.mode === 'overworld' && this.version === '1.18+') {
                    requiredDepth = layer - (-64);
                } else {
                    requiredDepth = layer;
                }

                if (isBedrock) {
                    this.constraints.push({ dx: r, dz: c, minDepth: requiredDepth });
                } else {
                    this.constraints.push({ dx: r, dz: c, maxDepth: requiredDepth - 1 });
                }
            }
        }
    }

    applyRotations(rotMatrix) {
        const h = rotMatrix.length;
        const w = rotMatrix[0] ? rotMatrix[0].length : 0;
        if (this.height === 0) {
            this.height = h;
            this.width = w;
        }

        const map = new Map();
        for (const c of this.constraints) {
            map.set(`${c.dx},${c.dz}`, c);
        }

        for (let r = 0; r < h; r++) {
            for (let c = 0; c < w; c++) {
                const val = rotMatrix[r][c];
                if (val !== null && val !== undefined && val !== -1 && val !== '?' && val !== 'x') {
                    const rotIdx = parseInt(val, 10);
                    if (!isNaN(rotIdx)) {
                        const key = `${r},${c}`;
                        if (map.has(key)) {
                            map.get(key).expectedRotation = rotIdx;
                        } else {
                            const cObj = { dx: r, dz: c, expectedRotation: rotIdx };
                            this.constraints.push(cObj);
                            map.set(key, cObj);
                        }
                    }
                }
            }
        }
    }

    getRotated(k) {
        k = ((k % 4) + 4) % 4;
        if (k === 0) return this;

        if (this.height === 0 && this.constraints.length > 0) {
            this.height = Math.max(...this.constraints.map(c => c.dx)) + 1;
            this.width = Math.max(...this.constraints.map(c => c.dz)) + 1;
        }

        const newPattern = new BedrockPattern({
            mode: this.mode,
            version: this.version,
            targetLayer: this.targetLayer
        });

        let newH = this.height;
        let newW = this.width;

        if (k === 1) { // 90° clockwise
            newH = this.width;
            newW = this.height;
            for (const c of this.constraints) {
                newPattern.constraints.push({
                    dx: c.dz,
                    dz: this.height - 1 - c.dx,
                    expectedDepth: c.expectedDepth,
                    minDepth: c.minDepth,
                    maxDepth: c.maxDepth,
                    expectedRotation: c.expectedRotation !== undefined ? (c.expectedRotation + 1) % 4 : undefined
                });
            }
        } else if (k === 2) { // 180°
            newH = this.height;
            newW = this.width;
            for (const c of this.constraints) {
                newPattern.constraints.push({
                    dx: this.height - 1 - c.dx,
                    dz: this.width - 1 - c.dz,
                    expectedDepth: c.expectedDepth,
                    minDepth: c.minDepth,
                    maxDepth: c.maxDepth,
                    expectedRotation: c.expectedRotation !== undefined ? (c.expectedRotation + 2) % 4 : undefined
                });
            }
        } else if (k === 3) { // 270° clockwise
            newH = this.width;
            newW = this.height;
            for (const c of this.constraints) {
                newPattern.constraints.push({
                    dx: this.width - 1 - c.dz,
                    dz: c.dx,
                    expectedDepth: c.expectedDepth,
                    minDepth: c.minDepth,
                    maxDepth: c.maxDepth,
                    expectedRotation: c.expectedRotation !== undefined ? (c.expectedRotation + 3) % 4 : undefined
                });
            }
        }

        newPattern.height = newH;
        newPattern.width = newW;
        return newPattern;
    }
}

/**
 * Parses a pattern string (JSON, numeric depths, or ASCII grid).
 */
function parsePatternFromString(content, mode = 'nether-roof', version = '1.12', targetLayer = null) {
    content = content.replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n').trim();

    if (content.startsWith('[') || content.startsWith('{')) {
        try {
            const data = JSON.parse(content);
            if (Array.isArray(data)) {
                const firstRow = data[0] || [];
                const firstVal = firstRow[0] || 0;
                if (typeof firstVal === 'number') {
                    return new BedrockPattern({ mode, version, targetLayer, heightMatrix: data });
                } else {
                    return new BedrockPattern({ mode, version, targetLayer, binaryMatrix: data });
                }
            } else if (typeof data === 'object') {
                const hMat = data.heights || data.pattern;
                const bMat = data.binary;
                const rotMat = data.rotations;
                const lay = data.layer !== undefined ? data.layer : targetLayer;
                if (hMat) {
                    return new BedrockPattern({ mode, version, targetLayer: lay, heightMatrix: hMat, rotationMatrix: rotMat });
                } else if (bMat) {
                    return new BedrockPattern({ mode, version, targetLayer: lay, binaryMatrix: bMat, rotationMatrix: rotMat });
                }
            }
        } catch (e) {
            // fallback to text parse
        }
    }

    const rawLines = content.split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0 && !l.startsWith('//'));

    if (rawLines.length === 0) {
        throw new Error("No valid pattern lines found in input.");
    }

    const hasBinarySymbols = rawLines.some(line => /[#\.Bb]/.test(line));
    const tokenGrid = rawLines.map(line => (line.includes(' ') || line.includes('\t')) ? line.split(/\s+/) : line.split(''));

    const hasHigherNumbers = tokenGrid.some(row =>
        row.some(tok => {
            const num = parseInt(tok, 10);
            return !isNaN(num) && num !== 0 && num !== 1;
        })
    );

    if (hasHigherNumbers || (!hasBinarySymbols && tokenGrid.some(row => row.some(tok => !isNaN(parseInt(tok, 10)))))) {
        const grid = [];
        for (const row of tokenGrid) {
            const gridRow = [];
            for (const tok of row) {
                if (tok === '?' || tok === 'x' || tok === '*' || tok === 'None' || tok === 'null') {
                    gridRow.append ? gridRow.append(null) : gridRow.push(null);
                } else {
                    const d = parseInt(tok, 10);
                    gridRow.push(isNaN(d) ? null : d);
                }
            }
            grid.push(gridRow);
        }
        return new BedrockPattern({ mode, version, targetLayer, heightMatrix: grid });
    } else {
        const grid = [];
        for (const row of tokenGrid) {
            const gridRow = [];
            for (const ch of row) {
                if (ch === '#' || ch === 'B' || ch === '1' || ch === 'b') {
                    gridRow.push(1);
                } else if (ch === '.' || ch === ' ' || ch === '0' || ch === '-' || ch === '_') {
                    gridRow.push(0);
                } else {
                    gridRow.push('?');
                }
            }
            grid.push(gridRow);
        }
        return new BedrockPattern({ mode, version, targetLayer, binaryMatrix: grid });
    }
}

// Export module for browser & node
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        LCG_MULT, LCG_ADD, LCG_MASK,
        CHUNK_X_MULT, CHUNK_Z_MULT,
        AK_TABLE, BK_TABLE,
        getCoordinateRandom,
        getTextureRotationIndex,
        getDefaultLayer,
        getChunkBedrockGrid,
        BedrockPattern,
        parsePatternFromString
    };
}
