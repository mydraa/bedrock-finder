#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>

#define LCG_MULT 0x5DEECE66DLL
#define LCG_ADD  0xBLL
#define LCG_MASK ((1ULL << 48) - 1)

#define CHUNK_X_MULT 341873128712LL
#define CHUNK_Z_MULT 132897987541LL

typedef struct {
    int dx;
    int dz;
    int exp_d;   // -1 if None
    int min_d;   // -1 if None
    int max_d;   // -1 if None
    int exp_rot; // -1 if None
} Constraint;

typedef struct {
    int64_t x;
    int64_t y;
    int64_t z;
    int64_t cx;
    int64_t cz;
    int rot_deg;
} Match;

static inline uint64_t get_coord_rand(int64_t x, int64_t y, int64_t z) {
    // In Minecraft Java Edition:
    // (long)(x * 3129871) ^ (long)z * 116129781L ^ (long)y;
    // x * 3129871 is 32-bit signed int multiplication before promotion to long
    int32_t x_part = (int32_t)(x * 3129871);
    uint64_t l = ((int64_t)x_part ^ (z * 116129781LL) ^ y);
    l = l * l * 42317861LL + l * 11LL;
    return (l >> 16);
}

// Precomputed jump tables
static uint64_t AK[513];
static uint64_t BK[513];
static bool tables_init = false;

static void init_tables() {
    if (tables_init) return;
    uint64_t cur_a = 1;
    uint64_t cur_b = 0;
    for (int k = 0; k <= 512; k++) {
        AK[k] = cur_a & LCG_MASK;
        BK[k] = cur_b & LCG_MASK;
        cur_a = (cur_a * LCG_MULT) & LCG_MASK;
        cur_b = (cur_b * LCG_MULT + LCG_ADD) & LCG_MASK;
    }
    tables_init = true;
}

int scan_chunk_range(
    int64_t min_cx, int64_t max_cx,
    int64_t min_cz, int64_t max_cz,
    const Constraint* constraints, int num_constraints,
    int mode_val, int ver_val, int64_t world_seed,
    int rot_deg, int target_y,
    Match* out_matches, int max_matches
) {
    init_tables();
    if (num_constraints <= 0) return 0;

    int match_count = 0;
    int step_mult = (mode_val == 3) ? 1 : 2;
    int step_offset = (mode_val == 2) ? 2 : 1;

    #pragma omp parallel for schedule(dynamic, 32)
    for (int64_t cx = min_cx; cx <= max_cx; cx++) {
        for (int64_t cz = min_cz; cz <= max_cz; cz++) {
            if (match_count >= max_matches) continue;

            uint64_t base_seed;
            if (ver_val == 2 && world_seed != 0 && mode_val == 3) {
                base_seed = (world_seed + cx * CHUNK_X_MULT + cz * CHUNK_Z_MULT) & LCG_MASK;
            } else {
                base_seed = (cx * CHUNK_X_MULT + cz * CHUNK_Z_MULT) & LCG_MASK;
            }
            uint64_t s0 = (base_seed ^ LCG_MULT) & LCG_MASK;

            for (int in_x = 0; in_x < 16; in_x++) {
                for (int in_z = 0; in_z < 16; in_z++) {
                    
                    // Fast intra-chunk check (up to 3 constraints)
                    bool pass_fast = true;
                    int checks = 0;
                    for (int c = 0; c < num_constraints && checks < 3; c++) {
                        int ix = in_x + constraints[c].dx;
                        int iz = in_z + constraints[c].dz;
                        if (ix >= 0 && ix < 16 && iz >= 0 && iz < 16) {
                            if (constraints[c].exp_d != -1 || constraints[c].min_d != -1 || constraints[c].max_d != -1) {
                                int step = (ix * 16 + iz) * step_mult + step_offset;
                                uint64_t s_k = (s0 * AK[step] + BK[step]) & LCG_MASK;
                                int depth = (int)((s_k >> 17) % 5);

                                if (constraints[c].exp_d != -1 && depth != constraints[c].exp_d) { pass_fast = false; break; }
                                if (constraints[c].min_d != -1 && depth < constraints[c].min_d) { pass_fast = false; break; }
                                if (constraints[c].max_d != -1 && depth > constraints[c].max_d) { pass_fast = false; break; }
                                checks++;
                            }
                            if (constraints[c].exp_rot != -1) {
                                int64_t wx = (cx << 4) + ix;
                                int64_t wz = (cz << 4) + iz;
                                uint64_t r = get_coord_rand(wx, target_y, wz);
                                int rot = (int)((r >> 16) & 3);
                                if (rot != constraints[c].exp_rot) { pass_fast = false; break; }
                                checks++;
                            }
                        }
                    }
                    if (!pass_fast) continue;

                    // Fully verify all constraints
                    bool ok = true;
                    int64_t x0 = (cx << 4) + in_x;
                    int64_t z0 = (cz << 4) + in_z;

                    for (int c = 0; c < num_constraints; c++) {
                        int64_t wx = x0 + constraints[c].dx;
                        int64_t wz = z0 + constraints[c].dz;
                        int64_t ncx = wx >> 4;
                        int64_t ncz = wz >> 4;
                        int nix = (int)(wx & 15);
                        int niz = (int)(wz & 15);

                        if (constraints[c].exp_d != -1 || constraints[c].min_d != -1 || constraints[c].max_d != -1) {
                            uint64_t n_base;
                            if (ver_val == 2 && world_seed != 0 && mode_val == 3) {
                                n_base = (world_seed + ncx * CHUNK_X_MULT + ncz * CHUNK_Z_MULT) & LCG_MASK;
                            } else {
                                n_base = (ncx * CHUNK_X_MULT + ncz * CHUNK_Z_MULT) & LCG_MASK;
                            }
                            uint64_t ns = (n_base ^ LCG_MULT) & LCG_MASK;
                            int step = (nix * 16 + niz) * step_mult + step_offset;
                            ns = (ns * AK[step] + BK[step]) & LCG_MASK;
                            int depth = (int)((ns >> 17) % 5);

                            if (constraints[c].exp_d != -1 && depth != constraints[c].exp_d) { ok = false; break; }
                            if (constraints[c].min_d != -1 && depth < constraints[c].min_d) { ok = false; break; }
                            if (constraints[c].max_d != -1 && depth > constraints[c].max_d) { ok = false; break; }
                        }

                        if (constraints[c].exp_rot != -1) {
                            uint64_t r = get_coord_rand(wx, target_y, wz);
                            int rot = (int)((r >> 16) & 3);
                            if (rot != constraints[c].exp_rot) { ok = false; break; }
                        }
                    }

                    if (ok) {
                        #pragma omp critical
                        {
                            if (match_count < max_matches) {
                                out_matches[match_count].x = x0;
                                out_matches[match_count].y = target_y;
                                out_matches[match_count].z = z0;
                                out_matches[match_count].cx = x0 >> 4;
                                out_matches[match_count].cz = z0 >> 4;
                                out_matches[match_count].rot_deg = rot_deg;
                                match_count++;
                            }
                        }
                    }
                }
            }
        }
    }
    return match_count;
}
