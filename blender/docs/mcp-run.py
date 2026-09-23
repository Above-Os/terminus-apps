"""Send a Python file to the blender-mcp addon socket and print the reply.

Runs inside the Blender container: python3 mcp-run.py <script.py>
The addon enforces BLENDER_MCP_SAFE_MODE, so this exercises the same
restrictions an MCP client such as Lares would hit.
"""
import json
import socket
import sys

path = sys.argv[1]
with open(path, "r") as handle:
    code = handle.read()

payload = json.dumps({"type": "execute_code", "params": {"code": code}}).encode()

sock = socket.create_connection(("127.0.0.1", 9876), timeout=600)
sock.settimeout(600)
sock.sendall(payload)

buffer = b""
while True:
    try:
        chunk = sock.recv(65536)
    except socket.timeout:
        break
    if not chunk:
        break
    buffer += chunk
    try:
        json.loads(buffer.decode("utf-8"))
        break
    except ValueError:
        continue

sock.close()
print(buffer.decode("utf-8", "replace")[:6000])
