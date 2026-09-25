import os, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
endpoint = os.environ["NEMOCLAW_ENDPOINT_URL"].rstrip("/")
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *args): pass
    def do_GET(self): self.forward()
    def do_POST(self): self.forward()
    def forward(self):
        if not self.path.startswith("/v1/"):
            self.send_error(404); return
        data = self.rfile.read(int(self.headers.get("Content-Length", "0"))) if self.command == "POST" else None
        headers = {"Content-Type": "application/json", "Authorization": self.headers.get("Authorization", "Bearer " + os.environ.get("COMPATIBLE_API_KEY", "unused"))}
        req = urllib.request.Request(endpoint + self.path[3:], data=data, headers=headers, method=self.command)
        try:
            try: response = urllib.request.urlopen(req, timeout=1200)
            except urllib.error.HTTPError as error: response = error
            with response:
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = response.read1(65536)
                    if not chunk: break
                    self.wfile.write(chunk); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception:
            self.close_connection = True
        finally:
            self.close_connection = True
ThreadingHTTPServer(("172.17.0.1", 18080), Handler).serve_forever()
