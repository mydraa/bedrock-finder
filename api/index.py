from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import os
import sys

# Add parent directory to path so bedrock module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from bedrock import (
        BedrockPattern,
        BedrockSearchEngine,
        DimensionMode,
        MinecraftVersion,
        get_chunk_bedrock_grid
    )
except ImportError:
    pass


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Python Handler in api/"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/api/chunk-preview", "/chunk-preview"):
            try:
                query = urllib.parse.parse_qs(parsed.query)
                cx = int(query.get("cx", [0])[0])
                cz = int(query.get("cz", [0])[0])
                mode_str = query.get("mode", ["nether-roof"])[0]
                ver_str = query.get("version", ["1.12"])[0]

                mode = DimensionMode(mode_str)
                version = MinecraftVersion.parse(ver_str)
                grid = get_chunk_bedrock_grid(cx, cz, mode, version)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"grid": grid}).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ready", "engine": "Minecraft Bedrock Finder Serverless"}).encode("utf-8"))

    def do_POST(self):
        if self.path in ("/api/search", "/search"):
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len)
                data = json.loads(body.decode("utf-8"))

                mode = DimensionMode(data.get("mode", "nether-roof"))
                version = MinecraftVersion.parse(data.get("version", "1.12"))
                layer = data.get("layer")
                seed_val = int(data["seed"]) if data.get("seed") else None
                radius = int(data.get("radius", 3000))
                center_x = int(data.get("center_x", 0))
                center_z = int(data.get("center_z", 0))
                all_rotations = bool(data.get("all_rotations", True))
                matrix = data.get("matrix", [])

                clean_mat = [[None if cell == 2 else cell for cell in row] for row in matrix]
                pattern = BedrockPattern(mode=mode, version=version, target_layer=layer, binary_matrix=clean_mat)

                min_x = center_x - radius
                max_x = center_x + radius
                min_z = center_z - radius
                max_z = center_z + radius

                engine = BedrockSearchEngine(pattern=pattern, world_seed=seed_val, all_rotations=all_rotations)
                matches = engine.search_bounds(min_x, min_z, max_x, max_z)

                response_data = {
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
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
