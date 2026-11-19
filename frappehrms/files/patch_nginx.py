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

# Desk embeds its boot data in HTML. Use the same case-insensitive media type
# without triggering the Olares HTML decoration filter's full-response buffer.
DESK_CONTENT_TYPE = """
map "$uri|$upstream_http_content_type" $frappe_content_type {
 default $upstream_http_content_type;
 "~^/app(?:/[^|]*)?[|]text/html(.*)$" "text/HTML$1";
}
"""

WEB = """location @webserver {
 include /etc/nginx/snippets/security_headers.conf;
 proxy_hide_header Content-Type;
 add_header Content-Type $frappe_content_type always;"""

conf_dir = Path("/etc/nginx/conf.d")
patched = False
for path in conf_dir.glob("*.conf"):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "location @webserver {" not in text:
        continue
    text = text.replace("gzip on;", "gzip off;")
    if "location /api/" not in text:
        if "location /assets {" not in text:
            raise SystemExit(f"cannot insert /api/ into {path}")
        text = text.replace("location /assets {", API + "\nlocation /assets {")
    if "location = /login" not in text:
        if "location / {" not in text:
            raise SystemExit(f"cannot insert /login into {path}")
        text = text.replace("location / {", LOGIN + "\nlocation / {", 1)
    if "add_header Content-Type $frappe_content_type always;" not in text:
        text = DESK_CONTENT_TYPE + text.replace("location @webserver {", WEB, 1)
    path.write_text(text, encoding="utf-8")
    patched = True
    print(f"patched {path.name}")

if not patched:
    raise SystemExit("no Frappe webserver config found")
print("patched nginx conf")
