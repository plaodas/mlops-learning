import http.client, json
c = http.client.HTTPConnection('127.0.0.1', 8000, timeout=10)
payload = json.dumps({'sepal length (cm)':5.1,'sepal width (cm)':3.5,'petal length (cm)':1.4,'petal width (cm)':0.2})
c.request('POST', '/predict/1', payload, {'Content-Type':'application/json'})
r = c.getresponse()
print('status', r.status)
print(r.read().decode())
