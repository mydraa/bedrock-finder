/**
 * Minecraft Bedrock Finder — Main Frontend Application Logic
 */

// Application State
let currentGridSize = 5;
let gridState = []; // 0: Hole, 1: Solid Bedrock, 2: Wildcard
let currentTab = 'grid';
let uploadedImage = null;

// Search Orchestration State
let isSearching = false;
let workers = [];
let searchStartTime = 0;
let timerInterval = null;
let totalChunksToScan = 0;
let totalChunksScanned = 0;
let foundMatches = [];
let currentTaskId = 0;

// Chunk Inspector State
let currentChunkGrid = null;

// Presets
const PRESETS = {
    nether5x5: {
        size: 5,
        matrix: [
            [0, 1, 0, 0, 1],
            [1, 1, 0, 1, 0],
            [1, 0, 1, 1, 1],
            [1, 0, 0, 1, 1],
            [1, 1, 1, 0, 0]
        ],
        mode: 'nether-roof',
        version: '1.12',
        layer: 125
    },
    hole4x4: {
        size: 4,
        matrix: [
            [1, 0, 0, 1],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [1, 0, 0, 1]
        ],
        mode: 'nether-roof',
        version: '1.12',
        layer: 126
    },
    cross5x5: {
        size: 5,
        matrix: [
            [2, 2, 1, 2, 2],
            [2, 2, 1, 2, 2],
            [1, 1, 1, 1, 1],
            [2, 2, 1, 2, 2],
            [2, 2, 1, 2, 2]
        ],
        mode: 'nether-roof',
        version: '1.12',
        layer: 125
    },
    overworld4x4: {
        size: 4,
        matrix: [
            [1, 1, 0, 0],
            [1, 1, 1, 0],
            [0, 1, 1, 1],
            [0, 0, 1, 1]
        ],
        mode: 'overworld',
        version: '1.18+',
        layer: -62
    }
};

// Initialize Application on Page Load
document.addEventListener('DOMContentLoaded', () => {
    initGrid(currentGridSize);
    updateThreadInfo();
    onConfigChange();
    renderChunkMap();
    initDropZone();
});

function updateThreadInfo() {
    const cores = navigator.hardwareConcurrency || 4;
    document.getElementById('threadInfo').innerText = `${cores} CPU Cores Detected`;
    document.getElementById('workersActive').innerText = `${cores}`;
}

// ==============================================================================
// 1. INTERACTIVE GRID EDITOR
// ==============================================================================

function initGrid(size) {
    currentGridSize = size;
    gridState = Array.from({ length: size }, () => Array(size).fill(1)); // Default all solid

    // Default sample hole pattern for 5x5
    if (size === 5) {
        gridState = [
            [0, 1, 0, 0, 1],
            [1, 1, 0, 1, 0],
            [1, 0, 1, 1, 1],
            [1, 0, 0, 1, 1],
            [1, 1, 1, 0, 0]
        ];
    }

    renderGrid();
}

function resizeGrid(newSize) {
    const oldState = gridState;
    const oldSize = currentGridSize;
    currentGridSize = newSize;

    gridState = Array.from({ length: newSize }, (_, r) =>
        Array.from({ length: newSize }, (_, c) => {
            if (r < oldSize && c < oldSize && oldState[r] && oldState[r][c] !== undefined) {
                return oldState[r][c];
            }
            return 1; // Solid default
        })
    );

    renderGrid();
}

function renderGrid() {
    const container = document.getElementById('visualGrid');
    container.innerHTML = '';
    container.style.gridTemplateColumns = `repeat(${currentGridSize}, minmax(0, 1fr))`;

    let isMouseDown = false;
    let dragVal = null;

    container.onmouseleave = () => { isMouseDown = false; };
    window.onmouseup = () => { isMouseDown = false; };

    for (let r = 0; r < currentGridSize; r++) {
        for (let c = 0; c < currentGridSize; c++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell rounded-lg flex items-center justify-center text-xs code-font shadow-sm';
            cell.dataset.r = r;
            cell.dataset.c = c;

            updateCellElement(cell, gridState[r][c]);

            cell.onmousedown = (e) => {
                e.preventDefault();
                isMouseDown = true;
                // Cycle: 1 (Solid #) -> 0 (Hole .) -> 2 (Wildcard ?) -> 1
                gridState[r][c] = (gridState[r][c] + 2) % 3; // 1->0->2->1
                if (gridState[r][c] === 3) gridState[r][c] = 0;
                dragVal = gridState[r][c];
                updateCellElement(cell, gridState[r][c]);
            };

            cell.onmouseenter = () => {
                if (isMouseDown && dragVal !== null) {
                    gridState[r][c] = dragVal;
                    updateCellElement(cell, gridState[r][c]);
                }
            };

            container.appendChild(cell);
        }
    }
}

function updateCellElement(cell, val) {
    cell.classList.remove('cell-solid', 'cell-hole', 'cell-wildcard');
    if (val === 1) {
        cell.classList.add('cell-solid');
        cell.innerText = '#';
    } else if (val === 0) {
        cell.classList.add('cell-hole');
        cell.innerText = '.';
    } else {
        cell.classList.add('cell-wildcard');
        cell.innerText = '?';
    }
}

function clearGrid(val) {
    for (let r = 0; r < currentGridSize; r++) {
        for (let c = 0; c < currentGridSize; c++) {
            gridState[r][c] = val;
        }
    }
    renderGrid();
}

function loadPreset(name) {
    if (!name || !PRESETS[name]) return;
    const p = PRESETS[name];

    document.getElementById('modeSelect').value = p.mode;
    document.getElementById('versionSelect').value = p.version;
    document.getElementById('layerInput').value = p.layer;
    document.getElementById('gridSizeSelect').value = p.size;

    onConfigChange();

    currentGridSize = p.size;
    gridState = p.matrix.map(row => [...row]);
    renderGrid();
    switchTab('grid');
    document.getElementById('presetSelect').value = '';
}

// ==============================================================================
// 2. CONFIGURATION & DIMENSION HANDLERS
// ==============================================================================

function onConfigChange() {
    const mode = document.getElementById('modeSelect').value;
    const version = document.getElementById('versionSelect').value;
    const layerInput = document.getElementById('layerInput');
    const layerHint = document.getElementById('layerHint');
    const seedHint = document.getElementById('seedHint');
    const slider = document.getElementById('chunkLayerSlider');

    if (mode === 'nether-roof') {
        layerHint.innerText = 'Roof: 123..127';
        seedHint.innerText = 'Seed-Independent';
        slider.min = 123;
        slider.max = 127;
        if (slider.value < 123 || slider.value > 127) slider.value = 125;
    } else if (mode === 'nether-floor') {
        layerHint.innerText = 'Floor: 0..4';
        seedHint.innerText = 'Seed-Independent';
        slider.min = 0;
        slider.max = 4;
        if (slider.value < 0 || slider.value > 4) slider.value = 2;
    } else { // Overworld
        if (version === '1.18+') {
            layerHint.innerText = 'Floor: -64..-60';
            seedHint.innerText = 'Seed-Independent';
            slider.min = -64;
            slider.max = -60;
            if (slider.value < -64 || slider.value > -60) slider.value = -62;
        } else {
            layerHint.innerText = 'Floor: 0..4';
            seedHint.innerText = (version === '1.13-1.17') ? 'Seed Dependent' : 'Seed-Independent';
            slider.min = 0;
            slider.max = 4;
            if (slider.value < 0 || slider.value > 4) slider.value = 2;
        }
    }

    document.getElementById('chunkLayerValue').innerText = slider.value;
    renderChunkMap();
}

// ==============================================================================
// 3. TAB SWITCHING & IMAGE UPLOAD
// ==============================================================================

function switchTab(tab) {
    currentTab = tab;
    ['tabGrid', 'tabImage', 'tabText'].forEach(t => document.getElementById(t).classList.add('hidden'));
    ['tabGridBtn', 'tabImageBtn', 'tabTextBtn'].forEach(b => {
        const btn = document.getElementById(b);
        btn.classList.remove('text-white', 'bg-indigo-600', 'shadow-sm');
        btn.classList.add('text-gray-400');
    });

    if (tab === 'grid') {
        document.getElementById('tabGrid').classList.remove('hidden');
        document.getElementById('tabGridBtn').classList.add('text-white', 'bg-indigo-600', 'shadow-sm');
    } else if (tab === 'image') {
        document.getElementById('tabImage').classList.remove('hidden');
        document.getElementById('tabImageBtn').classList.add('text-white', 'bg-indigo-600', 'shadow-sm');
    } else if (tab === 'text') {
        document.getElementById('tabText').classList.remove('hidden');
        document.getElementById('tabTextBtn').classList.add('text-white', 'bg-indigo-600', 'shadow-sm');
    }
}

function initDropZone() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('imageInput');

    dropZone.onclick = () => fileInput.click();

    dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.classList.add('border-indigo-500', 'bg-indigo-500/10');
    };

    dropZone.ondragleave = () => {
        dropZone.classList.remove('border-indigo-500', 'bg-indigo-500/10');
    };

    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-indigo-500', 'bg-indigo-500/10');
        if (e.dataTransfer.files.length > 0) {
            processImageFile(e.dataTransfer.files[0]);
        }
    };
}

function handleImageUpload(e) {
    if (e.target.files.length > 0) {
        processImageFile(e.target.files[0]);
    }
}

function processImageFile(file) {
    const reader = new FileReader();
    reader.onload = (event) => {
        const img = new Image();
        img.onload = () => {
            uploadedImage = img;
            document.getElementById('imagePreview').src = event.target.result;
            document.getElementById('dropZone').classList.add('hidden');
            document.getElementById('imagePreviewContainer').classList.remove('hidden');
        };
        img.src = event.target.result;
    };
    reader.readAsDataURL(file);
}

function clearImage() {
    uploadedImage = null;
    document.getElementById('imageInput').value = '';
    document.getElementById('imagePreviewContainer').classList.add('hidden');
    document.getElementById('dropZone').classList.remove('hidden');
}

// ==============================================================================
// 4. MULTI-THREADED SEARCH ENGINE CONTROLLER
// ==============================================================================

function toggleSearch() {
    if (isSearching) {
        stopSearch();
    } else {
        startSearch();
    }
}

function startSearch() {
    const mode = document.getElementById('modeSelect').value;
    const version = document.getElementById('versionSelect').value;
    const layer = parseInt(document.getElementById('layerInput').value, 10);
    const seedStr = document.getElementById('seedInput').value.trim();
    const worldSeed = seedStr ? parseInt(seedStr, 10) : null;
    const radius = parseInt(document.getElementById('radiusInput').value, 10) || 5000;
    const centerX = parseInt(document.getElementById('centerX').value, 10) || 0;
    const centerZ = parseInt(document.getElementById('centerZ').value, 10) || 0;
    const allRotations = document.getElementById('allRotationsCheck').checked;

    let pattern;
    try {
        if (currentTab === 'grid') {
            const cleanMatrix = gridState.map(row => row.map(cell => cell === 2 ? null : cell));
            pattern = new BedrockPattern({
                mode,
                version,
                targetLayer: layer,
                binaryMatrix: cleanMatrix
            });
        } else if (currentTab === 'text') {
            const rawText = document.getElementById('rawTextInput').value.trim();
            pattern = parsePatternFromString(rawText, mode, version, layer);
        } else if (currentTab === 'image') {
            if (!uploadedImage) {
                alert('Please upload an image first.');
                return;
            }
            const rows = parseInt(document.getElementById('imgRows').value, 10) || 5;
            const cols = parseInt(document.getElementById('imgCols').value, 10) || 5;
            pattern = extractPatternFromImage(uploadedImage, rows, cols, mode, version, layer);
        }
    } catch (err) {
        alert('Pattern error: ' + err.message);
        return;
    }

    if (pattern.constraints.length === 0) {
        alert('Pattern has no valid constraints. Please place at least one Solid block (#) or Hole (.).');
        return;
    }

    // Set UI State
    isSearching = true;
    currentTaskId++;
    foundMatches = [];
    totalChunksScanned = 0;
    searchStartTime = performance.now();

    const searchBtn = document.getElementById('searchBtn');
    searchBtn.innerHTML = `<i class="fa-solid fa-stop text-sm animate-pulse"></i> <span>Stop Bedrock Scan</span>`;
    searchBtn.classList.replace('from-indigo-600', 'from-red-600');
    searchBtn.classList.replace('to-purple-600', 'to-rose-600');

    document.getElementById('scanStatusBadge').className = 'text-xs bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 px-2.5 py-0.5 rounded-full font-medium';
    document.getElementById('scanStatusBadge').innerText = 'Scanning...';
    document.getElementById('resultsTableBody').innerHTML = `
        <tr>
            <td colspan="5" class="py-6 text-center text-indigo-300">
                <i class="fa-solid fa-spinner fa-spin text-xl mr-2"></i> Multi-core scanner actively searching...
            </td>
        </tr>
    `;

    // Compute Search Bounds in Chunks
    const minX = centerX - radius;
    const maxX = centerX + radius;
    const minZ = centerZ - radius;
    const maxZ = centerZ + radius;

    const minCx = minX >> 4;
    const maxCx = maxX >> 4;
    const minCz = minZ >> 4;
    const maxCz = maxZ >> 4;

    const totalChunksX = maxCx - minCx + 1;
    const totalChunksZ = maxCz - minCz + 1;
    totalChunksToScan = totalChunksX * totalChunksZ * (allRotations ? 4 : 1);

    document.getElementById('chunksScannedText').innerText = `0 / ${totalChunksToScan.toLocaleString()} Chunks`;
    document.getElementById('matchesCount').innerText = '0';

    // Prepare Patterns (with rotations if checked)
    const patternsToTest = [];
    if (allRotations) {
        [0, 90, 180, 270].forEach((deg, k) => {
            patternsToTest.push({ pat: pattern.getRotated(k), deg });
        });
    } else {
        patternsToTest.push({ pat: pattern, deg: 0 });
    }

    const modeVal = (mode === 'nether-roof') ? 1 : (mode === 'nether-floor') ? 2 : 3;
    const threadCount = navigator.hardwareConcurrency || 4;

    // Spawn Workers
    workers.forEach(w => w.terminate());
    workers = [];

    let completedTasks = 0;
    const totalWorkerTasks = patternsToTest.length * threadCount;

    // Start Timer
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(updateTimerMetrics, 100);

    patternsToTest.forEach(({ pat, deg }) => {
        const serializedConstraints = pat.constraints.map(c => ({
            dx: c.dx,
            dz: c.dz,
            expectedDepth: c.expectedDepth,
            minDepth: c.minDepth,
            maxDepth: c.maxDepth,
            expectedRotation: c.expectedRotation
        }));

        const chunkXSpan = Math.ceil(totalChunksX / threadCount);

        for (let t = 0; t < threadCount; t++) {
            const threadMinCx = minCx + t * chunkXSpan;
            const threadMaxCx = Math.min(minCx + (t + 1) * chunkXSpan - 1, maxCx);
            if (threadMinCx > threadMaxCx) {
                completedTasks++;
                continue;
            }

            const worker = new Worker('worker.js');
            workers.push(worker);

            worker.onmessage = (e) => {
                const msg = e.data;
                if (msg.taskId !== currentTaskId) return;

                if (msg.type === 'match') {
                    addMatchResult(msg.match);
                } else if (msg.type === 'progress') {
                    totalChunksScanned += msg.scannedDelta;
                    updateProgressUI();
                } else if (msg.type === 'done') {
                    completedTasks++;
                    if (completedTasks >= totalWorkerTasks) {
                        finishSearch();
                    }
                }
            };

            worker.postMessage({
                workerId: t,
                taskId: currentTaskId,
                minCx: threadMinCx,
                maxCx: threadMaxCx,
                minCz,
                maxCz,
                constraints: serializedConstraints,
                modeVal,
                versionStr: version,
                worldSeed,
                rotDeg: deg,
                targetY: pattern.targetLayer
            });
        }
    });
}

function updateProgressUI() {
    const percent = Math.min(100, Math.round((totalChunksScanned / totalChunksToScan) * 100)) || 0;
    document.getElementById('progressBar').style.width = `${percent}%`;
    document.getElementById('progressPercent').innerText = `${percent}%`;
    document.getElementById('chunksScannedText').innerText = `${Math.min(totalChunksScanned, totalChunksToScan).toLocaleString()} / ${totalChunksToScan.toLocaleString()} Chunks`;
}

function updateTimerMetrics() {
    if (!isSearching) return;
    const elapsed = (performance.now() - searchStartTime) / 1000;
    document.getElementById('elapsedTime').innerText = `${elapsed.toFixed(2)}s`;

    if (elapsed > 0) {
        const speed = totalChunksScanned / elapsed;
        document.getElementById('speedChunks').innerText = Math.round(speed).toLocaleString();
        document.getElementById('speedBlocks').innerText = `~${Math.round(speed * 256).toLocaleString()} blk/s`;
    }
}

function addMatchResult(m) {
    // Avoid duplicate matches
    const key = `${m.x},${m.y},${m.z},${m.rotationDeg}`;
    if (foundMatches.some(item => `${item.x},${item.y},${item.z},${item.rotationDeg}` === key)) return;

    foundMatches.push(m);
    document.getElementById('matchesCount').innerText = foundMatches.length;

    const tbody = document.getElementById('resultsTableBody');
    if (foundMatches.length === 1) {
        tbody.innerHTML = '';
    }

    const idx = foundMatches.length;
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-[#1a233a]/50 transition';
    tr.innerHTML = `
        <td class="py-2.5 px-3 text-gray-400">${idx}</td>
        <td class="py-2.5 px-3 font-bold text-white">X=${m.x.toLocaleString()}, Y=${m.y}, Z=${m.z.toLocaleString()}</td>
        <td class="py-2.5 px-3 text-indigo-300">CX=${m.chunkX}, CZ=${m.chunkZ}</td>
        <td class="py-2.5 px-3 text-purple-300">${m.rotationDeg}°</td>
        <td class="py-2.5 px-3 text-right space-x-1.5">
            <button onclick="copyTpCommand(${m.x}, ${m.y}, ${m.z})" class="bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 px-2 py-1 rounded text-[11px] border border-indigo-500/30 transition">
                <i class="fa-solid fa-copy mr-1"></i> /tp
            </button>
            <button onclick="inspectChunkCoords(${m.chunkX}, ${m.chunkZ})" class="bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 px-2 py-1 rounded text-[11px] border border-purple-500/30 transition">
                <i class="fa-solid fa-eye mr-1"></i> View
            </button>
        </td>
    `;
    tbody.appendChild(tr);
}

function stopSearch() {
    isSearching = false;
    workers.forEach(w => w.terminate());
    workers = [];
    if (timerInterval) clearInterval(timerInterval);

    const searchBtn = document.getElementById('searchBtn');
    searchBtn.innerHTML = `<i class="fa-solid fa-magnifying-glass text-sm"></i> <span>Start Bedrock Scan</span>`;
    searchBtn.classList.replace('from-red-600', 'from-indigo-600');
    searchBtn.classList.replace('to-rose-600', 'to-purple-600');

    document.getElementById('scanStatusBadge').className = 'text-xs bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2.5 py-0.5 rounded-full font-medium';
    document.getElementById('scanStatusBadge').innerText = 'Stopped';
}

function finishSearch() {
    isSearching = false;
    workers.forEach(w => w.terminate());
    workers = [];
    if (timerInterval) clearInterval(timerInterval);

    totalChunksScanned = totalChunksToScan;
    updateProgressUI();
    updateTimerMetrics();

    const searchBtn = document.getElementById('searchBtn');
    searchBtn.innerHTML = `<i class="fa-solid fa-magnifying-glass text-sm"></i> <span>Start Bedrock Scan</span>`;
    searchBtn.classList.replace('from-red-600', 'from-indigo-600');
    searchBtn.classList.replace('to-rose-600', 'to-purple-600');

    document.getElementById('scanStatusBadge').className = 'text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2.5 py-0.5 rounded-full font-medium';
    document.getElementById('scanStatusBadge').innerText = `Finished (${foundMatches.length} Found)`;

    if (foundMatches.length === 0) {
        document.getElementById('resultsTableBody').innerHTML = `
            <tr>
                <td colspan="5" class="py-6 text-center text-gray-500">
                    <i class="fa-solid fa-circle-xmark text-xl mb-1 block text-gray-600"></i>
                    No matches found in the specified radius. Try increasing the search radius or enabling all rotations.
                </td>
            </tr>
        `;
    }
}

function copyTpCommand(x, y, z) {
    const cmd = `/tp @s ${x} ${y} ${z}`;
    navigator.clipboard.writeText(cmd).then(() => {
        alert(`Copied to clipboard: ${cmd}`);
    });
}

function exportResultsJSON() {
    if (foundMatches.length === 0) {
        alert('No matches to export.');
        return;
    }
    const blob = new Blob([JSON.stringify(foundMatches, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bedrock_matches_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

// ==============================================================================
// 5. IMAGE PATTERN EXTRACTOR
// ==============================================================================

function extractPatternFromImage(img, gridRows, gridCols, mode, version, targetLayer) {
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);

    const imgData = ctx.getImageData(0, 0, img.width, img.height);
    const data = imgData.data;

    const blockW = img.width / gridCols;
    const blockH = img.height / gridRows;

    const blockMeans = [];
    for (let r = 0; r < gridRows; r++) {
        const rowMeans = [];
        for (let c = 0; c < gridCols; c++) {
            const y1 = Math.floor(r * blockH);
            const y2 = Math.floor((r + 1) * blockH);
            const x1 = Math.floor(c * blockW);
            const x2 = Math.floor((c + 1) * blockW);

            let sum = 0;
            let count = 0;
            for (let y = y1; y < y2; y++) {
                for (let x = x1; x < x2; x++) {
                    const idx = (y * img.width + x) * 4;
                    // Grayscale standard: 0.299R + 0.587G + 0.114B
                    const gray = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
                    sum += gray;
                    count++;
                }
            }
            rowMeans.push(count > 0 ? sum / count : 0);
        }
        blockMeans.push(rowMeans);
    }

    const flat = blockMeans.flat();
    const minV = Math.min(...flat);
    const maxV = Math.max(...flat);
    const threshold = (minV + maxV) / 2.0;

    const binaryMatrix = blockMeans.map(row => row.map(v => v >= threshold ? 1 : 0));

    return new BedrockPattern({
        mode,
        version,
        targetLayer,
        binaryMatrix
    });
}

// ==============================================================================
// 6. 16x16 CHUNK BEDROCK INSPECTOR
// ==============================================================================

function inspectChunkCoords(cx, cz) {
    document.getElementById('inspectCx').value = cx;
    document.getElementById('inspectCz').value = cz;
    renderChunkMap();
    document.getElementById('chunkCanvas').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function onLayerSliderChange(val) {
    document.getElementById('chunkLayerValue').innerText = val;
    renderChunkMap();
}

function renderChunkMap() {
    const canvas = document.getElementById('chunkCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const cx = parseInt(document.getElementById('inspectCx').value, 10) || 0;
    const cz = parseInt(document.getElementById('inspectCz').value, 10) || 0;
    const mode = document.getElementById('modeSelect').value;
    const version = document.getElementById('versionSelect').value;
    const layer = parseInt(document.getElementById('chunkLayerSlider').value, 10);
    const seedStr = document.getElementById('seedInput').value.trim();
    const worldSeed = seedStr ? parseInt(seedStr, 10) : null;

    currentChunkGrid = getChunkBedrockGrid(cx, cz, mode, version, worldSeed);

    const cellSize = canvas.width / 16;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let x = 0; x < 16; x++) {
        for (let z = 0; z < 16; z++) {
            const depth = currentChunkGrid[x * 16 + z];

            let isSolid;
            if (mode === 'nether-roof') {
                isSolid = (127 - depth <= layer);
            } else if (mode === 'overworld' && version === '1.18+') {
                isSolid = (-64 + depth >= layer);
            } else {
                isSolid = (depth >= layer);
            }

            if (isSolid) {
                // Bedrock style dark textured block
                const shade = 45 + depth * 8;
                ctx.fillStyle = `rgb(${shade}, ${shade + 4}, ${shade + 10})`;
            } else {
                // Hole / Air
                ctx.fillStyle = '#0f172a';
            }

            ctx.fillRect(x * cellSize, z * cellSize, cellSize, cellSize);

            // Subtle grid border
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
            ctx.strokeRect(x * cellSize, z * cellSize, cellSize, cellSize);
        }
    }
}

function onCanvasHover(e) {
    if (!currentChunkGrid) return;
    const canvas = document.getElementById('chunkCanvas');
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const mouseX = (e.clientX - rect.left) * scaleX;
    const mouseY = (e.clientY - rect.top) * scaleY;

    const inX = Math.floor(mouseX / (canvas.width / 16));
    const inZ = Math.floor(mouseY / (canvas.height / 16));

    if (inX < 0 || inX >= 16 || inZ < 0 || inZ >= 16) return;

    const cx = parseInt(document.getElementById('inspectCx').value, 10) || 0;
    const cz = parseInt(document.getElementById('inspectCz').value, 10) || 0;
    const mode = document.getElementById('modeSelect').value;
    const version = document.getElementById('versionSelect').value;
    const layer = parseInt(document.getElementById('chunkLayerSlider').value, 10);

    const worldX = (cx << 4) + inX;
    const worldZ = (cz << 4) + inZ;
    const depth = currentChunkGrid[inX * 16 + inZ];

    let isSolid;
    if (mode === 'nether-roof') {
        isSolid = (127 - depth <= layer);
    } else if (mode === 'overworld' && version === '1.18+') {
        isSolid = (-64 + depth >= layer);
    } else {
        isSolid = (depth >= layer);
    }

    const rot = getTextureRotationIndex(worldX, layer, worldZ);

    document.getElementById('hoverCoords').innerText = `X=${worldX}, Y=${layer}, Z=${worldZ}`;
    document.getElementById('hoverState').innerText = isSolid ? 'SOLID BEDROCK (#)' : 'AIR / HOLE (.)';
    document.getElementById('hoverState').className = isSolid ? 'text-gray-300 font-bold' : 'text-amber-400 font-bold';
    document.getElementById('hoverDepth').innerText = `${depth} (k=${depth})`;
    document.getElementById('hoverRot').innerText = `${rot * 90}° (idx=${rot})`;
}

function onCanvasLeave() {
    document.getElementById('hoverCoords').innerText = '-';
    document.getElementById('hoverState').innerText = '-';
    document.getElementById('hoverDepth').innerText = '-';
    document.getElementById('hoverRot').innerText = '-';
}
