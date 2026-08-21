/**
 * Web Worker for High-Speed Client-Side Bedrock Scanning
 */

importScripts('engine.js');

self.onmessage = function(e) {
    const data = e.data;
    const {
        workerId,
        taskId,
        minCx,
        maxCx,
        minCz,
        maxCz,
        constraints,
        modeVal,
        versionStr,
        worldSeed,
        rotDeg,
        targetY
    } = data;

    if (!constraints || constraints.length === 0) {
        self.postMessage({ type: 'done', taskId, workerId, matches: [], chunksScanned: 0 });
        return;
    }

    const mode = (modeVal === 1) ? 'nether-roof' : (modeVal === 2) ? 'nether-floor' : 'overworld';
    const stepMult = (modeVal === 3) ? 1 : 2;
    const stepOffset = (modeVal === 2) ? 2 : 1;
    const worldSeedVal = (worldSeed !== null && worldSeed !== undefined) ? BigInt(worldSeed) : 0n;

    const numConstraints = constraints.length;
    const matches = [];
    let chunksScanned = 0;

    const reportInterval = 5000;
    let nextReport = reportInterval;

    for (let cx = minCx; cx <= maxCx; cx++) {
        const bcx = BigInt(cx);
        for (let cz = minCz; cz <= maxCz; cz++) {
            const bcz = BigInt(cz);
            chunksScanned++;

            let baseSeed;
            if (versionStr === '1.13-1.17' && worldSeedVal !== 0n && modeVal === 3) {
                baseSeed = (worldSeedVal + bcx * CHUNK_X_MULT + bcz * CHUNK_Z_MULT) & LCG_MASK;
            } else {
                baseSeed = (bcx * CHUNK_X_MULT + bcz * CHUNK_Z_MULT) & LCG_MASK;
            }
            const s0 = (baseSeed ^ LCG_MULT) & LCG_MASK;

            for (let inX = 0; inX < 16; inX++) {
                for (let inZ = 0; inZ < 16; inZ++) {
                    // Fast filter on up to 3 intra-chunk constraints
                    let passFast = true;
                    let checks = 0;

                    for (let c = 0; c < numConstraints && checks < 3; c++) {
                        const con = constraints[c];
                        const ix = inX + con.dx;
                        const iz = inZ + con.dz;

                        if (ix >= 0 && ix < 16 && iz >= 0 && iz < 16) {
                            if (con.expectedDepth !== undefined || con.minDepth !== undefined || con.maxDepth !== undefined) {
                                const step = (ix * 16 + iz) * stepMult + stepOffset;
                                const sK = (s0 * AK_TABLE[step] + BK_TABLE[step]) & LCG_MASK;
                                const depth = Number((sK >> 17n) % 5n);

                                if (con.expectedDepth !== undefined && depth !== con.expectedDepth) {
                                    passFast = false;
                                    break;
                                }
                                if (con.minDepth !== undefined && depth < con.minDepth) {
                                    passFast = false;
                                    break;
                                }
                                if (con.maxDepth !== undefined && depth > con.maxDepth) {
                                    passFast = false;
                                    break;
                                }
                                checks++;
                            }

                            if (con.expectedRotation !== undefined) {
                                const wx = (cx << 4) + ix;
                                const wz = (cz << 4) + iz;
                                const rot = getTextureRotationIndex(wx, targetY, wz);
                                if (rot !== con.expectedRotation) {
                                    passFast = false;
                                    break;
                                }
                                checks++;
                            }
                        }
                    }

                    if (!passFast) continue;

                    // Fully verify all constraints
                    let ok = true;
                    const x0 = (cx << 4) + inX;
                    const z0 = (cz << 4) + inZ;

                    for (let c = 0; c < numConstraints; c++) {
                        const con = constraints[c];
                        const wx = x0 + con.dx;
                        const wz = z0 + con.dz;
                        const ncx = wx >> 4;
                        const ncz = wz >> 4;
                        const nix = wx & 15;
                        const niz = wz & 15;

                        if (con.expectedDepth !== undefined || con.minDepth !== undefined || con.maxDepth !== undefined) {
                            let nBase;
                            const bNcx = BigInt(ncx);
                            const bNcz = BigInt(ncz);
                            if (versionStr === '1.13-1.17' && worldSeedVal !== 0n && modeVal === 3) {
                                nBase = (worldSeedVal + bNcx * CHUNK_X_MULT + bNcz * CHUNK_Z_MULT) & LCG_MASK;
                            } else {
                                nBase = (bNcx * CHUNK_X_MULT + bNcz * CHUNK_Z_MULT) & LCG_MASK;
                            }

                            let ns = (nBase ^ LCG_MULT) & LCG_MASK;
                            const step = (nix * 16 + niz) * stepMult + stepOffset;
                            ns = (ns * AK_TABLE[step] + BK_TABLE[step]) & LCG_MASK;
                            const depth = Number((ns >> 17n) % 5n);

                            if (con.expectedDepth !== undefined && depth !== con.expectedDepth) {
                                ok = false;
                                break;
                            }
                            if (con.minDepth !== undefined && depth < con.minDepth) {
                                ok = false;
                                break;
                            }
                            if (con.maxDepth !== undefined && depth > con.maxDepth) {
                                ok = false;
                                break;
                            }
                        }

                        if (con.expectedRotation !== undefined) {
                            const rot = getTextureRotationIndex(wx, targetY, wz);
                            if (rot !== con.expectedRotation) {
                                ok = false;
                                break;
                            }
                        }
                    }

                    if (ok) {
                        matches.push({
                            x: x0,
                            y: targetY,
                            z: z0,
                            chunkX: x0 >> 4,
                            chunkZ: z0 >> 4,
                            rotationDeg: rotDeg
                        });
                        self.postMessage({
                            type: 'match',
                            taskId,
                            workerId,
                            match: {
                                x: x0,
                                y: targetY,
                                z: z0,
                                chunkX: x0 >> 4,
                                chunkZ: z0 >> 4,
                                rotationDeg: rotDeg
                            }
                        });
                    }
                }
            }

            if (chunksScanned >= nextReport) {
                self.postMessage({
                    type: 'progress',
                    taskId,
                    workerId,
                    scannedDelta: reportInterval
                });
                nextReport += reportInterval;
            }
        }
    }

    self.postMessage({
        type: 'done',
        taskId,
        workerId,
        matches,
        chunksScanned
    });
};
