from http.server import BaseHTTPRequestHandler
import mimetypes
import os

class handler(BaseHTTPRequestHandler):
    """Serves the frontend Web UI (index.html, JS, CSS, assets) on Vercel."""

    def do_GET(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = self.path.split('?')[0].strip('/')

        if not path or path == 'index.html':
            target_file = os.path.join(base_dir, 'index.html')
        else:
            target_file = os.path.join(base_dir, path)

        if os.path.isfile(target_file):
            mime_type, _ = mimetypes.guess_type(target_file)
            if not mime_type:
                if target_file.endswith('.js'):
                    mime_type = 'application/javascript'
                elif target_file.endswith('.css'):
                    mime_type = 'text/css'
                elif target_file.endswith('.html'):
                    mime_type = 'text/html'
                else:
                    mime_type = 'application/octet-stream'

            self.send_response(200)
            self.send_header('Content-Type', f"{mime_type}; charset=utf-8" if 'text' in mime_type or 'javascript' in mime_type else mime_type)
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            with open(target_file, 'rb') as f:
                self.wfile.write(f.read())
            return

        # Fallback to index.html for SPA routes
        index_file = os.path.join(base_dir, 'index.html')
        if os.path.isfile(index_file):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            with open(index_file, 'rb') as f:
                self.wfile.write(f.read())
            return

        self.send_response(404)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'404 Not Found')
