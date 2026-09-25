import importlib.util
import pathlib
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

spec = importlib.util.spec_from_file_location("webui", pathlib.Path(__file__).parents[1] / "files/check-webui.py")
webui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(webui)

class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.responses = {
            "/health": (200, "application/json", b'{"ok":true}'),
            "/": (200, "text/html", b'<openclaw-app></openclaw-app><script src="./assets/app.js"></script><link rel="stylesheet" href="./assets/app.css">'),
            "/assets/app.js": (200, "text/javascript", b'customElements.define("openclaw-app", class {});'),
            "/assets/app.css": (200, "text/css", b'body { color: white; }'),
        }
        responses = self.responses
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, kind, body = responses.get(self.path, (404, "text/plain", b"missing"))
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args): pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%s/" % self.server.server_port
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
    def test_complete_webui_is_ready(self):
        webui.check(self.url)
    def test_unavailable_pages_are_not_ready(self):
        for status, body in [(503,b""),(502,b"bad gateway"),(200,b""),(200,b"installing")]:
            with self.subTest(status=status, body=body):
                self.responses["/"] = (status,"text/html",body)
                with self.assertRaises(Exception): webui.check(self.url)
    def test_missing_or_html_script_is_not_ready(self):
        for response in [(404,"text/plain",b"missing"),(200,"text/html",b"<html>fallback</html>"),(200,"text/javascript",b"")]:
            with self.subTest(response=response):
                self.responses["/assets/app.js"] = response
                with self.assertRaises(Exception): webui.check(self.url)
    def test_gateway_not_healthy_is_not_ready(self):
        self.responses["/health"] = (200,"application/json",b'{"ok":false}')
        with self.assertRaises(ValueError): webui.check(self.url)
    def test_missing_css_is_not_ready(self):
        del self.responses["/assets/app.css"]
        with self.assertRaises(Exception): webui.check(self.url)

if __name__ == "__main__":
    unittest.main()
