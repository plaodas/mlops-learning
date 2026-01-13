import json, urllib.request, urllib.error
payload = json.dumps({"some_feature":0}).encode('utf-8')
req = urllib.request.Request("http://127.0.0.1:8000/predict/15", data=payload, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        resp = r.read().decode('utf-8')
        status = r.getcode()
except Exception as e:
    resp = str(e)
    status = 0
with open('/tmp/predict15.out', 'w') as f:
    f.write(json.dumps({'status': status, 'resp': resp}, ensure_ascii=False))
