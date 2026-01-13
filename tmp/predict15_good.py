import json, urllib.request, urllib.error
payload = json.dumps({
    "sepal length (cm)":5.1,
    "sepal width (cm)":3.5,
    "petal length (cm)":1.4,
    "petal width (cm)":0.2
}).encode('utf-8')
req = urllib.request.Request("http://127.0.0.1:8000/predict/15", data=payload, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        resp = r.read().decode('utf-8')
        status = r.getcode()
except Exception as e:
    resp = str(e)
    status = 0
with open('/tmp/predict15_good.out', 'w') as f:
    f.write(json.dumps({'status': status, 'resp': resp}, ensure_ascii=False))
