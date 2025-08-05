# celery_beat_web.py

import os
import subprocess
from multiprocessing import Process
from http.server import BaseHTTPRequestHandler, HTTPServer

def start_dummy_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Celery beat is alive.")

    port = int(os.environ.get("PORT", 8000))
    with HTTPServer(("", port), Handler) as httpd:
        print(f"Dummy HTTP server running on port {port}")
        httpd.serve_forever()

def start_celery_beat():
    subprocess.call(["celery", "-A", "Horal_Backend", "beat", "--loglevel=info"])

if __name__ == "__main__":
    # Run Celery worker in a separate process
    p = Process(target=start_celery_beat)
    p.start()

    # Run dummy web server to satisfy Render
    start_dummy_server()
