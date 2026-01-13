import sys, json, urllib.request
if len(sys.argv)<2:
    print('usage: smoke_predict.py <version>')
    sys.exit(2)
version=sys.argv[1]
payload = json.dumps({
    "sepal length (cm)":5.1,
    "sepal width (cm)":3.5,
    "petal length (cm)":1.4,
    "petal width (cm)":0.2
}).encode('utf-8')
url=f'http://127.0.0.1:8000/predict/{version}'
req=urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print(json.dumps({'status': r.getcode(), 'resp': r.read().decode('utf-8')}))
except Exception as e:
    print(json.dumps({'status':0,'error':str(e)}))
