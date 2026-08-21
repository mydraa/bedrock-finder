#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
MINECRAFT BEDROCK PATTERN FINDER - MODERN WEB GUI
================================================================================
Author  : Antigravity (Google DeepMind)
Version : 1.0.0
"""

import os
import sys
import time
import json
import base64
import io
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

from PIL import Image
import numpy as np

# Import core engine
from bedrock import (
    BedrockPattern,
    BedrockSearchEngine,
    DimensionMode,
    MinecraftVersion,
    ImagePatternExtractor,
    get_chunk_bedrock_grid,
    get_default_layer
)

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Minecraft Bedrock Pattern Finder</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0d1117;
            color: #c9d1d9;
        }
        .code-font {
            font-family: 'Fira Code', monospace;
        }
        .cell {
            transition: all 0.15s ease;
            user-select: none;
        }
        .cell-solid {
            background-color: #3b4252;
            border-color: #4c566a;
            color: #eceff4;
        }
        .cell-hole {
            background-color: #1a1b26;
            border-color: #24283b;
            color: #7982a9;
        }
        .cell-wildcard {
            background-color: #2e3440;
            border-color: #434c5e;
            color: #88c0d0;
            opacity: 0.6;
        }
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #161b22;
        }
        ::-webkit-scrollbar-thumb {
            background: #30363d;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #484f58;
        }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Header -->
    <header class="bg-[#161b22] border-b border-[#30363d] px-6 py-4 flex items-center justify-between sticky top-0 z-50 shadow-md">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/20">
                <i class="fa-solid fa-cube text-white text-xl"></i>
            </div>
            <div>
                <h1 class="text-lg font-bold text-white tracking-wide">Minecraft Bedrock Finder</h1>
                <p class="text-xs text-gray-400">Reverse-engineering & coordinate locator (1.0 to 1.21+)</p>
            </div>
        </div>
        <div class="flex items-center space-x-4">
            <span class="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-1 rounded-full font-medium flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                Engine Ready
            </span>
            <a href="https://github.com/mydraa/bedrock-finder" target="_blank" class="text-xs bg-[#21262d] hover:bg-[#30363d] text-gray-300 px-3 py-1.5 rounded-lg border border-[#30363d] transition flex items-center gap-2">
                <i class="fa-brands fa-github"></i> GitHub
            </a>
        </div>
    </header>

    <!-- Main Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">

        <!-- Left Column: Settings & Input (5 cols) -->
        <div class="lg:col-span-5 space-y-6">

            <!-- World & Version Configuration Card -->
            <div class="bg-[#161b22] border border-[#30363d] rounded-xl p-5 shadow-sm space-y-4">
                <h2 class="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                    <i class="fa-solid fa-sliders text-indigo-400"></i> World Configuration
                </h2>

                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">Minecraft Version</label>
                        <select id="versionSelect" class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">
                            <option value="1.12" selected>1.12.2 / Legacy (1.0-1.12)</option>
                            <option value="1.13-1.17">1.13 - 1.17.1</option>
                            <option value="1.18+">1.18+ (Caves & Cliffs)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">Dimension / Mode</label>
                        <select id="modeSelect" class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">
                            <option value="nether-roof" selected>Nether Roof (Y=123..127)</option>
                            <option value="nether-floor">Nether Floor (Y=0..4)</option>
                            <option value="overworld">Overworld Floor</option>
                        </select>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">Target Y Layer</label>
                        <input type="number" id="layerInput" value="125" class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white code-font focus:outline-none focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">World Seed (Optional)</label>
                        <input type="text" id="seedInput" placeholder="Auto / None (1.12)" class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white code-font focus:outline-none focus:border-indigo-500">
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">Search Radius (Blocks)</label>
                        <input type="number" id="radiusInput" value="5000" step="1000" class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white code-font focus:outline-none focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">Center Coordinates (X Z)</label>
                        <div class="grid grid-cols-2 gap-1.5">
                            <input type="number" id="centerX" value="0" placeholder="X" class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-2 py-2 text-sm text-white code-font focus:outline-none focus:border-indigo-500">
                            <input type="number" id="centerZ" value="0" placeholder="Z" class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-2 py-2 text-sm text-white code-font focus:outline-none focus:border-indigo-500">
                        </div>
                    </div>
                </div>

                <div class="pt-2 border-t border-[#30363d]/50 flex items-center justify-between">
                    <label class="flex items-center space-x-2 text-xs text-gray-300 cursor-pointer">
                        <input type="checkbox" id="allRotationsCheck" checked class="rounded bg-[#0d1117] border-[#30363d] text-indigo-600 focus:ring-0">
                        <span>Test all 4 rotations (0°, 90°, 180°, 270°)</span>
                    </label>
                </div>
            </div>

            <!-- Pattern Mode Selector (Grid vs Image vs Text) -->
            <div class="bg-[#161b22] border border-[#30363d] rounded-xl p-5 shadow-sm space-y-4">
                <div class="flex items-center justify-between">
                    <h2 class="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-shapes text-indigo-400"></i> Pattern Input
                    </h2>
                    <div class="flex bg-[#0d1117] p-1 rounded-lg border border-[#30363d] text-xs">
                        <button id="tabGridBtn" onclick="switchTab('grid')" class="px-3 py-1 rounded-md font-medium text-white bg-indigo-600 transition">Grid Editor</button>
                        <button id="tabImageBtn" onclick="switchTab('image')" class="px-3 py-1 rounded-md font-medium text-gray-400 hover:text-white transition">Image Upload</button>
                        <button id="tabTextBtn" onclick="switchTab('text')" class="px-3 py-1 rounded-md font-medium text-gray-400 hover:text-white transition">Raw Text</button>
                    </div>
                </div>

                <!-- Tab 1: Interactive Grid Editor -->
                <div id="tabGrid" class="space-y-3">
                    <div class="flex items-center justify-between text-xs text-gray-400">
                        <div class="flex items-center space-x-2">
                            <span>Grid Size:</span>
                            <select id="gridSizeSelect" onchange="resizeGrid()" class="bg-[#0d1117] border border-[#30363d] rounded px-2 py-1 text-white font-medium">
                                <option value="4">4 x 4</option>
                                <option value="5">5 x 5</option>
                                <option value="6">6 x 6</option>
                                <option value="8">8 x 8</option>
                                <option value="10" selected>10 x 10 (CTF Standard)</option>
                                <option value="12">12 x 12</option>
                                <option value="16">16 x 16 (Full Chunk)</option>
                            </select>
                        </div>
                        <div class="flex items-center space-x-3 text-[11px]">
                            <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-[#3b4252] border border-[#4c566a]"></span> Solid (#)</span>
                            <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-[#1a1b26] border border-[#24283b]"></span> Hole (.)</span>
                            <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-[#2e3440] border border-[#434c5e] opacity-60"></span> Unknown (?)</span>
                        </div>
                    </div>

                    <!-- Visual Grid Canvas Container -->
                    <div class="bg-[#0d1117] border border-[#30363d] rounded-xl p-4 flex items-center justify-center min-h-[220px]">
                        <div id="gridContainer" class="grid gap-1.5"></div>
                    </div>

                    <div class="flex justify-between items-center text-xs">
                        <button onclick="clearGrid()" class="text-gray-400 hover:text-rose-400 transition">
                            <i class="fa-solid fa-trash-can mr-1"></i> Reset Grid
                        </button>
                        <button onclick="fillGrid('solid')" class="text-gray-400 hover:text-indigo-400 transition">
                            Fill All Solid
                        </button>
                    </div>
                </div>

                <!-- Tab 2: Image Upload & Crop -->
                <div id="tabImage" class="hidden space-y-4">
                    <div id="dropZone" class="border-2 border-dashed border-[#30363d] hover:border-indigo-500/50 rounded-xl p-6 text-center cursor-pointer transition bg-[#0d1117]/50">
                        <input type="file" id="imageInput" accept="image/*" class="hidden" onchange="handleImageUpload(event)">
                        <i class="fa-solid fa-cloud-arrow-up text-3xl text-gray-400 mb-2"></i>
                        <p class="text-xs text-gray-300 font-medium">Click or drag & drop a Minecraft bedrock screenshot</p>
                        <p class="text-[11px] text-gray-500 mt-1">PNG, JPG, WebP supported</p>
                    </div>
                    <div id="imagePreviewContainer" class="hidden space-y-2">
                        <div class="flex items-center justify-between text-xs">
                            <span class="text-gray-400">Preview & Detection</span>
                            <button onclick="removeImage()" class="text-rose-400 hover:text-rose-300"><i class="fa-solid fa-xmark mr-1"></i> Remove</button>
                        </div>
                        <img id="imagePreview" class="max-h-48 rounded-lg mx-auto border border-[#30363d]" />
                    </div>
                </div>

                <!-- Tab 3: Raw Text Input -->
                <div id="tabText" class="hidden space-y-2">
                    <label class="block text-xs text-gray-400">Enter matrix lines (# = solid, . = hole, ? = wildcard or numbers 0..4):</label>
                    <textarea id="rawTextInput" rows="5" class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-sm text-white code-font focus:outline-none focus:border-indigo-500 resize-none"># . # . .
# . # . .
# # # . .
# # # # #
. # . . .</textarea>
                </div>
            </div>

            <!-- Run Button -->
            <button id="searchBtn" onclick="runSearch()" class="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold py-3.5 px-6 rounded-xl shadow-lg shadow-indigo-600/20 transition flex items-center justify-center space-x-2 text-sm tracking-wide">
                <i class="fa-solid fa-magnifying-glass"></i>
                <span>START SCANNING COORDINATES</span>
            </button>
        </div>

        <!-- Right Column: Results & Chunk Visualizer (7 cols) -->
        <div class="lg:col-span-7 space-y-6">

            <!-- Real-time Status Card -->
            <div class="bg-[#161b22] border border-[#30363d] rounded-xl p-5 shadow-sm space-y-3">
                <div class="flex items-center justify-between">
                    <h2 class="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-bolt text-indigo-400"></i> Search Status & Metrics
                    </h2>
                    <span id="statusBadge" class="text-xs px-2.5 py-0.5 rounded-full bg-gray-800 text-gray-400 border border-gray-700">Idle</span>
                </div>

                <div class="grid grid-cols-3 gap-3 text-center">
                    <div class="bg-[#0d1117] border border-[#30363d] rounded-lg p-3">
                        <div class="text-[11px] text-gray-400">Scanned Chunks</div>
                        <div id="statChunks" class="text-base font-bold text-white code-font mt-0.5">0</div>
                    </div>
                    <div class="bg-[#0d1117] border border-[#30363d] rounded-lg p-3">
                        <div class="text-[11px] text-gray-400">Throughput</div>
                        <div id="statSpeed" class="text-base font-bold text-emerald-400 code-font mt-0.5">0 c/s</div>
                    </div>
                    <div class="bg-[#0d1117] border border-[#30363d] rounded-lg p-3">
                        <div class="text-[11px] text-gray-400">Matches Found</div>
                        <div id="statMatches" class="text-base font-bold text-indigo-400 code-font mt-0.5">0</div>
                    </div>
                </div>

                <div class="space-y-1">
                    <div class="flex justify-between text-xs text-gray-400">
                        <span id="progressText">Ready to start search</span>
                        <span id="progressPercent">0%</span>
                    </div>
                    <div class="w-full bg-[#0d1117] h-2 rounded-full overflow-hidden border border-[#30363d]">
                        <div id="progressBar" class="bg-gradient-to-r from-indigo-500 to-purple-500 h-full w-0 transition-all duration-300"></div>
                    </div>
                </div>
            </div>

            <!-- Matches List Card -->
            <div class="bg-[#161b22] border border-[#30363d] rounded-xl p-5 shadow-sm space-y-4">
                <div class="flex items-center justify-between">
                    <h2 class="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-location-dot text-emerald-400"></i> Found Coordinates
                    </h2>
                    <span id="matchesCount" class="text-xs text-gray-400">0 results</span>
                </div>

                <div id="matchesContainer" class="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                    <div class="text-center py-8 text-gray-500 text-xs">
                        <i class="fa-solid fa-crosshairs text-2xl mb-2 opacity-40"></i>
                        <p>No matches yet. Click "Start Scanning" to search.</p>
                    </div>
                </div>
            </div>

            <!-- Chunk 2D Visualizer Card -->
            <div class="bg-[#161b22] border border-[#30363d] rounded-xl p-5 shadow-sm space-y-3">
                <div class="flex items-center justify-between">
                    <h2 class="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-map text-purple-400"></i> Chunk Bedrock Inspector (16x16)
                    </h2>
                    <div class="flex items-center space-x-2 text-xs">
                        <input type="number" id="inspectChunkX" value="85" placeholder="CX" class="w-16 bg-[#0d1117] border border-[#30363d] rounded px-2 py-1 text-white code-font">
                        <input type="number" id="inspectChunkZ" value="30" placeholder="CZ" class="w-16 bg-[#0d1117] border border-[#30363d] rounded px-2 py-1 text-white code-font">
                        <button onclick="loadChunkPreview()" class="bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded transition font-medium">Load</button>
                    </div>
                </div>

                <div class="bg-[#0d1117] border border-[#30363d] rounded-xl p-3 flex items-center justify-center">
                    <div id="chunkCanvasContainer" class="grid grid-cols-16 gap-0.5"></div>
                </div>
            </div>

        </div>
    </main>

    <script>
        let currentTab = 'grid';
        let gridState = [];
        let gridSize = 10;
        let uploadedImageBase64 = null;

        // Initialize grid on load
        function initGrid() {
            gridSize = parseInt(document.getElementById('gridSizeSelect').value);
            gridState = [];
            const container = document.getElementById('gridContainer');
            container.innerHTML = '';
            container.style.gridTemplateColumns = `repeat(${gridSize}, minmax(0, 1fr))`;

            // Responsive cell size class
            let cellSizeClass = 'w-9 h-9 text-xs';
            if (gridSize >= 16) {
                cellSizeClass = 'w-4 h-4 text-[8px]';
            } else if (gridSize >= 12) {
                cellSizeClass = 'w-5 h-5 text-[9px]';
            } else if (gridSize >= 10) {
                cellSizeClass = 'w-6 h-6 text-[10px]';
            } else if (gridSize >= 8) {
                cellSizeClass = 'w-7 h-7 text-xs';
            }

            for (let r = 0; r < gridSize; r++) {
                gridState[r] = [];
                for (let c = 0; c < gridSize; c++) {
                    const defaultVal = 1; // Default Solid Bedrock
                    gridState[r][c] = defaultVal;

                    const cell = document.createElement('div');
                    cell.className = `${cellSizeClass} rounded flex items-center justify-center font-bold border cursor-pointer cell`;
                    cell.dataset.row = r;
                    cell.dataset.col = c;
                    cell.onclick = () => cycleCellState(r, c);
                    updateCellDOM(cell, defaultVal);
                    container.appendChild(cell);
                }
            }
        }

        function cycleCellState(r, c) {
            // Cycle: 1 (Solid) -> 0 (Hole) -> 2 (Wildcard) -> 1
            if (gridState[r][c] === 1) gridState[r][c] = 0;
            else if (gridState[r][c] === 0) gridState[r][c] = 2;
            else gridState[r][c] = 1;

            const cell = document.querySelector(`[data-row="${r}"][data-col="${c}"]`);
            if (cell) updateCellDOM(cell, gridState[r][c]);
        }

        function updateCellDOM(cell, val) {
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

        function resizeGrid() {
            initGrid();
        }

        function clearGrid() {
            for (let r = 0; r < gridSize; r++) {
                for (let c = 0; c < gridSize; c++) {
                    gridState[r][c] = 2; // Wildcard
                    const cell = document.querySelector(`[data-row="${r}"][data-col="${c}"]`);
                    if (cell) updateCellDOM(cell, 2);
                }
            }
        }

        function fillGrid(type) {
            const val = (type === 'solid') ? 1 : 0;
            for (let r = 0; r < gridSize; r++) {
                for (let c = 0; c < gridSize; c++) {
                    gridState[r][c] = val;
                    const cell = document.querySelector(`[data-row="${r}"][data-col="${c}"]`);
                    if (cell) updateCellDOM(cell, val);
                }
            }
        }

        function switchTab(tab) {
            currentTab = tab;
            ['grid', 'image', 'text'].forEach(t => {
                document.getElementById(`tab${t.charAt(0).toUpperCase() + t.slice(1)}`).classList.add('hidden');
                document.getElementById(`tab${t.charAt(0).toUpperCase() + t.slice(1)}Btn`).className = 'px-3 py-1 rounded-md font-medium text-gray-400 hover:text-white transition';
            });
            document.getElementById(`tab${tab.charAt(0).toUpperCase() + tab.slice(1)}`).classList.remove('hidden');
            document.getElementById(`tab${tab.charAt(0).toUpperCase() + tab.slice(1)}Btn`).className = 'px-3 py-1 rounded-md font-medium text-white bg-indigo-600 transition';
        }

        // Image Handling
        function handleImageUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (evt) => {
                uploadedImageBase64 = evt.target.result;
                document.getElementById('imagePreview').src = uploadedImageBase64;
                document.getElementById('imagePreviewContainer').classList.remove('hidden');
                document.getElementById('dropZone').classList.add('hidden');
            };
            reader.readAsDataURL(file);
        }

        function removeImage() {
            uploadedImageBase64 = null;
            document.getElementById('imageInput').value = '';
            document.getElementById('imagePreviewContainer').classList.add('hidden');
            document.getElementById('dropZone').classList.remove('hidden');
        }

        // Mode change adapter
        document.getElementById('modeSelect').addEventListener('change', (e) => {
            const mode = e.target.value;
            const ver = document.getElementById('versionSelect').value;
            const layerInput = document.getElementById('layerInput');
            if (mode === 'nether-roof') layerInput.value = 125;
            else if (mode === 'nether-floor') layerInput.value = 3;
            else if (mode === 'overworld') layerInput.value = (ver === '1.18+') ? -62 : 3;
        });

        // Search Executor
        async function runSearch() {
            const searchBtn = document.getElementById('searchBtn');
            const statusBadge = document.getElementById('statusBadge');
            const matchesContainer = document.getElementById('matchesContainer');

            searchBtn.disabled = true;
            searchBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> SCANNING IN PROGRESS...';
            statusBadge.className = 'text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse';
            statusBadge.innerText = 'Scanning';

            // Gather parameters
            const payload = {
                version: document.getElementById('versionSelect').value,
                mode: document.getElementById('modeSelect').value,
                layer: parseInt(document.getElementById('layerInput').value),
                seed: document.getElementById('seedInput').value.trim() || null,
                radius: parseInt(document.getElementById('radiusInput').value),
                center_x: parseInt(document.getElementById('centerX').value) || 0,
                center_z: parseInt(document.getElementById('centerZ').value) || 0,
                all_rotations: document.getElementById('allRotationsCheck').checked,
                tab: currentTab
            };

            if (currentTab === 'grid') {
                payload.matrix = gridState;
            } else if (currentTab === 'text') {
                payload.raw_text = document.getElementById('rawTextInput').value;
            } else if (currentTab === 'image') {
                payload.image_b64 = uploadedImageBase64;
                payload.grid_rows = gridSize;
                payload.grid_cols = gridSize;
            }

            try {
                const res = await fetch('/api/search', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                // Update UI Stats
                document.getElementById('statChunks').innerText = (data.total_chunks || 0).toLocaleString();
                document.getElementById('statSpeed').innerText = Math.round(data.speed || 0).toLocaleString() + ' c/s';
                document.getElementById('statMatches').innerText = (data.matches || []).length;
                document.getElementById('matchesCount').innerText = `${(data.matches || []).length} result(s)`;
                document.getElementById('progressBar').style.width = '100%';
                document.getElementById('progressPercent').innerText = '100%';
                document.getElementById('progressText').innerText = `Finished in ${data.elapsed.toFixed(2)}s`;

                // Render matches
                matchesContainer.innerHTML = '';
                if (!data.matches || data.matches.length === 0) {
                    matchesContainer.innerHTML = `
                        <div class="text-center py-6 text-gray-400 text-xs">
                            <i class="fa-solid fa-circle-question text-xl mb-1 text-gray-500"></i>
                            <p>No matching coordinates found in the specified radius.</p>
                        </div>
                    `;
                } else {
                    data.matches.forEach((m, idx) => {
                        const card = document.createElement('div');
                        card.className = 'bg-[#0d1117] border border-[#30363d] hover:border-indigo-500/50 rounded-lg p-3.5 flex items-center justify-between transition cursor-pointer';
                        card.onclick = () => {
                            document.getElementById('inspectChunkX').value = m.chunk_x;
                            document.getElementById('inspectChunkZ').value = m.chunk_z;
                            loadChunkPreview();
                        };
                        card.innerHTML = `
                            <div class="flex items-center space-x-3">
                                <div class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center font-bold text-xs">
                                    #${idx + 1}
                                </div>
                                <div>
                                    <div class="text-sm font-bold text-white code-font">
                                        X: ${m.x.toLocaleString()}, Y: ${m.y}, Z: ${m.z.toLocaleString()}
                                    </div>
                                    <div class="text-xs text-gray-400">
                                        Chunk: (${m.chunk_x}, ${m.chunk_z}) | Rotation: ${m.rotation_deg}°
                                    </div>
                                </div>
                            </div>
                            <button class="text-xs bg-[#21262d] hover:bg-[#30363d] text-gray-300 px-2.5 py-1.5 rounded border border-[#30363d]">
                                <i class="fa-solid fa-eye mr-1 text-purple-400"></i> Inspect Chunk
                            </button>
                        `;
                        matchesContainer.appendChild(card);
                    });
                }

                statusBadge.className = 'text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
                statusBadge.innerText = 'Completed';

            } catch (err) {
                console.error(err);
                alert('Error during search: ' + err.message);
                statusBadge.className = 'text-xs px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20';
                statusBadge.innerText = 'Error';
            } finally {
                searchBtn.disabled = false;
                searchBtn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i><span>START SCANNING COORDINATES</span>';
            }
        }

        // Chunk Inspector Preview
        async function loadChunkPreview() {
            const cx = parseInt(document.getElementById('inspectChunkX').value);
            const cz = parseInt(document.getElementById('inspectChunkZ').value);
            const mode = document.getElementById('modeSelect').value;
            const version = document.getElementById('versionSelect').value;
            const layer = parseInt(document.getElementById('layerInput').value);

            try {
                const res = await fetch(`/api/chunk-preview?cx=${cx}&cz=${cz}&mode=${mode}&version=${version}&layer=${layer}`);
                const data = await res.json();
                const container = document.getElementById('chunkCanvasContainer');
                container.innerHTML = '';
                container.style.gridTemplateColumns = 'repeat(16, minmax(0, 1fr))';

                data.grid.forEach((depth, idx) => {
                    const cell = document.createElement('div');
                    cell.className = 'w-4 h-4 rounded-[2px] transition';
                    const isSolid = (mode === 'nether-roof') ? (127 - depth <= layer) : (depth >= layer);
                    cell.style.backgroundColor = isSolid ? '#4c566a' : '#1a1b26';
                    cell.title = `Index ${idx} (Depth ${depth})`;
                    container.appendChild(cell);
                });
            } catch (err) {
                console.error(err);
            }
        }

        // Init on startup
        window.onload = () => {
            initGrid();
            loadChunkPreview();
        };
    </script>
</body>
</html>
"""


class BedrockHTTPHandler(BaseHTTPRequestHandler):
    """Custom HTTP Server handler serving the UI and JSON APIs."""

    def log_message(self, format, *args):
        # Silence standard HTTP logs for clean CLI
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/chunk-preview":
            query = parse_qs(parsed.query)
            cx = int(query.get("cx", [0])[0])
            cz = int(query.get("cz", [0])[0])
            mode_str = query.get("mode", ["nether-roof"])[0]
            ver_str = query.get("version", ["1.12"])[0]

            mode = DimensionMode(mode_str)
            version = MinecraftVersion.parse(ver_str)
            grid = get_chunk_bedrock_grid(cx, cz, mode, version)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"grid": grid}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/search":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len)
                data = json.loads(body.decode("utf-8"))

                mode = DimensionMode(data.get("mode", "nether-roof"))
                version = MinecraftVersion.parse(data.get("version", "1.12"))
                layer = data.get("layer")
                seed_val = int(data["seed"]) if data.get("seed") else None
                radius = int(data.get("radius", 5000))
                center_x = int(data.get("center_x", 0))
                center_z = int(data.get("center_z", 0))
                all_rotations = bool(data.get("all_rotations", True))
                tab = data.get("tab", "grid")

                if tab == "grid":
                    matrix = data.get("matrix", [])
                    # Replace 2 (wildcard) with None
                    clean_mat = []
                    for row in matrix:
                        clean_mat.append([None if cell == 2 else cell for cell in row])
                    pattern = BedrockPattern(mode=mode, version=version, target_layer=layer, binary_matrix=clean_mat)
                elif tab == "text":
                    raw_text = data.get("raw_text", "")
                    from bedrock import parse_pattern_from_string_or_file
                    pattern = parse_pattern_from_string_or_file(raw_text, mode=mode, version=version, target_layer=layer)
                elif tab == "image" and data.get("image_b64"):
                    b64_data = data["image_b64"].split(",")[-1]
                    img_bytes = base64.b64decode(b64_data)
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    temp_path = "/tmp/uploaded_bedrock.png"
                    img.save(temp_path)
                    pattern = ImagePatternExtractor.extract_from_image(
                        image_path=temp_path,
                        grid_rows=int(data.get("grid_rows", 5)),
                        grid_cols=int(data.get("grid_cols", 5)),
                        mode=mode,
                        version=version,
                        target_layer=layer
                    )

                min_x = center_x - radius
                max_x = center_x + radius
                min_z = center_z - radius
                max_z = center_z + radius

                min_cx = min_x >> 4
                max_cx = max_x >> 4
                min_cz = min_z >> 4
                max_cz = max_z >> 4
                total_chunks = (max_cx - min_cx + 1) * (max_cz - min_cz + 1)

                t0 = time.perf_counter()
                engine = BedrockSearchEngine(
                    pattern=pattern,
                    world_seed=seed_val,
                    all_rotations=all_rotations
                )
                matches = engine.search_bounds(min_x, min_z, max_x, max_z)
                elapsed = time.perf_counter() - t0
                speed = total_chunks / elapsed if elapsed > 0 else 0

                response_data = {
                    "total_chunks": total_chunks,
                    "elapsed": elapsed,
                    "speed": speed,
                    "matches": [
                        {
                            "x": m.x, "y": m.y, "z": m.z,
                            "chunk_x": m.chunk_x, "chunk_z": m.chunk_z,
                            "rotation_deg": m.rotation_deg
                        } for m in matches
                    ]
                }

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))

            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))


def start_web_gui(port: int = 5000, open_browser: bool = True):
    """Starts the local Web UI server and opens the browser."""
    server_address = ("127.0.0.1", port)
    try:
        httpd = HTTPServer(server_address, BedrockHTTPHandler)
    except OSError:
        # Fallback to next available port if port is busy
        port += 1
        server_address = ("127.0.0.1", port)
        httpd = HTTPServer(server_address, BedrockHTTPHandler)

    url = f"http://localhost:{port}"
    print("\n" + "=" * 70)
    print("  MINECRAFT BEDROCK PATTERN FINDER - MODERN WEB GUI")
    print("=" * 70)
    print(f"[*] Web GUI successfully started at : {url}")
    print(f"[*] Opening browser automatically...")
    print(f"[*] Press Ctrl+C in this terminal to stop the server.")
    print("=" * 70 + "\n")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Web server stopped.")


if __name__ == "__main__":
    start_web_gui()
