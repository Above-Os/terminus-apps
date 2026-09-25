"""Readiness check for the real OpenClaw page, assets and gateway health."""
import json
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import ProxyHandler, build_opener

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.app = False
        self.assets = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.app |= tag == "openclaw-app"
        if tag == "script" and attrs.get("src"):
            self.assets.append((attrs["src"], "javascript"))
        if tag == "link" and attrs.get("rel") == "stylesheet" and attrs.get("href"):
            self.assets.append((attrs["href"], "css"))

def check(base):
    base = base.rstrip("/") + "/"
    opener = build_opener(ProxyHandler({}))
    def fetch(path, limit):
        url = urljoin(base, path)
        if urlsplit(url).netloc != urlsplit(base).netloc:
            raise ValueError("UI asset is outside the application")
        with opener.open(url, timeout=3) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("Unexpected HTTP response")
            return response.read(limit), response.headers.get_content_type()
    health, _ = fetch("health", 4096)
    if json.loads(health).get("ok") is not True:
        raise ValueError("Gateway is not healthy")
    html, content_type = fetch("", 131072)
    page = Page()
    page.feed(html.decode("utf-8"))
    if content_type != "text/html" or not page.app or not page.assets:
        raise ValueError("OpenClaw UI is not installed")
    if not any(kind == "javascript" for _, kind in page.assets):
        raise ValueError("OpenClaw UI script is missing")
    for path, kind in page.assets:
        body, content_type = fetch(path, 512)
        if not body or kind not in content_type or body.lstrip().startswith(b"<"):
            raise ValueError("OpenClaw UI asset is unavailable")

if __name__ == "__main__":
    try:
        check(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18790/")
    except Exception as error:
        print("WebUI not ready:", error, file=sys.stderr)
        raise SystemExit(1)
