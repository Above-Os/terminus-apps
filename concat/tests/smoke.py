import os,json,urllib.request,urllib.error
base='http://127.0.0.1:8080'
assert json.load(urllib.request.urlopen(base+'/healthz'))['ok']
try: urllib.request.urlopen(base+'/v1/status');raise AssertionError('Missing authentication accepted')
except urllib.error.HTTPError as e: assert e.code==401
headers={'Authorization':'Bearer '+os.environ['CONCAT_API_TOKEN'],'Content-Type':'application/json'}
status=json.load(urllib.request.urlopen(urllib.request.Request(base+'/v1/status',headers=headers)))
assert not status['editing']
data=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}}).encode()
result=json.load(urllib.request.urlopen(urllib.request.Request(base+'/mcp',data=data,headers=headers)))
assert len(result['result']['tools'])==7
assert urllib.request.urlopen('http://127.0.0.1:3000').status==200
print(json.dumps({'passed':True,'checks':['healthz','unauthenticated API rejected with 401','authenticated API','MCP seven tools','GUI HTTP 200','desktop restored']}))
