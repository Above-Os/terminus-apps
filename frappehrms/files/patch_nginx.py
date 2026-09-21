from pathlib import Path

API = """
location /api/ {
 proxy_http_version 1.1;
 proxy_set_header X-Forwarded-For $remote_addr;
 proxy_set_header X-Forwarded-Proto $proxy_x_forwarded_proto;
 proxy_set_header X-Frappe-Site-Name frontend;
 proxy_set_header Host $host;
 proxy_read_timeout 120;
 proxy_redirect off;
 proxy_pass http://backend-server;
}
"""

LOGIN = """
location = / { return 302 /login; }
location = /login { default_type text/html; charset utf-8; try_files /frontend/public/login =404; }
"""

WEB = """location @webserver {
 proxy_hide_header Content-Type;
 add_header Content-Type "application/xhtml+xml; charset=utf-8" always;
 proxy_hide_header Link;"""

conf_dir = Path("/etc/nginx/conf.d")
patched = False
for path in conf_dir.glob("*.conf"):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    text = text.replace("gzip on;", "gzip off;")
    if "location /api/" not in text:
        if "location /assets {" not in text:
            raise SystemExit(f"cannot insert /api/ into {path}")
        text = text.replace("location /assets {", API + "\nlocation /assets {")
    if "location = /login" not in text:
        if "location / {" not in text:
            raise SystemExit(f"cannot insert /login into {path}")
        text = text.replace("location / {", LOGIN + "\nlocation / {", 1)
    if "application/xhtml+xml" not in text:
        if "location @webserver {" not in text:
            raise SystemExit(f"cannot patch @webserver in {path}")
        text = text.replace("location @webserver {", WEB, 1)
    path.write_text(text, encoding="utf-8")
    patched = True
    print(f"patched {path.name}")

if not patched:
    raise SystemExit("no nginx conf files found")
if not any("application/xhtml+xml" in p.read_text(encoding="utf-8") for p in conf_dir.glob("*.conf")):
    raise SystemExit("xhtml content-type rewrite missing after patch")
print("patched nginx conf")
