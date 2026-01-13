#!/bin/sh
# POST a simple payload to FastAPI /predict/15 and save output
curl -sS -X POST -H "Content-Type: application/json" -d '{"some_feature":0}' http://127.0.0.1:8000/predict/15 -w "\nHTTP_STATUS:%{http_code}\n" > /tmp/predict15.out 2>&1
echo "EXIT:$?" > /tmp/predict15.exit
