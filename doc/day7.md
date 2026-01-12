# Day 7: Deploying FastAPI with Kubernetes
このドキュメントでは、Kubernetes クラスター上に FastAPI アプリケーションをデプロイする手順を説明します。FastAPI は、MLflow で管理されている機械学習モデルの推論 API を提供します。

## 全体像：FastAPI 推論サービスの構成
- MLflow で保存されたモデルをロード
- FastAPI アプリケーションで推論エンドポイントを提供
- Kubernetes 上で動かして
http://fastapi.local

でアクセスできるようにする。

### Step 1：FastAPI アプリを作る
`app.py` を作成し、FastAPI アプリケーションを実装します

### Step 2：Dockerfile を作成
Dockerfile を作成し、FastAPI アプリをコンテナ化します。
```bash
docker build -t registry5001:5000/fastapi-iris:latest -f api/Dockerfile api
docker tag registry5001:5000/fastapi-iris:latest localhost:5001/fastapi-iris:latest
docker push localhost:5001/fastapi-iris:latest
```

### Step 3：Kubernetes Deployment を作成
Kubernetes マニフェストを作成し、FastAPI アプリをデプロイします。
Kubernetes Deployment, Kubernetes Service, Kubernetes Ingress を作成しアクセスを可能にします。
```bash
kubectl apply -f api/fastapi-deploy.yaml
kubectl apply -f api/fastapi-svc.yaml
kubectl apply -f api/fastapi-ingress.yaml
```

### host の /etc/hosts に`api.local`を追加
```bash
sudo sh -c 'echo "127.0.0.1 api.local" >> /etc/hosts'
```

### Step 4：kind ノードにイメージをロード
```bash
# ワークフローが参照しているイメージ名を確認する
kind load docker-image localhost:5001/fastapi-iris:latest --name agritech-mlops
docker exec -it agritech-mlops-control-plane ctr -n k8s.io images ls | grep fastapi-iris || true
# Deployment を再起動する
kubectl -n mlflow rollout restart deployment/fastapi
kubectl -n mlflow rollout status deployment/fastapi
```





## トラブルシューティング
### FastAPI アプリにアクセスできない
- kubectl -n mlflow rollout status deployment/fastapi => replicas are pending termination... のまま固まってしまう
[原因] 古い ReplicaSet が残っていて、新しい Pod がスケジュールされない。
[対策] 古い ReplicaSet を削除し、kind ノードにイメージをロードし直してから Deployment を再起動する。
```bash
kubectl -n mlflow get deployment fastapi -o wide; echo '---'; kubectl -n mlflow describe deployment fastapi; echo '---'; kubectl -n mlflow get rs -o wide --sort-by=.metadata.creationTimestamp; echo '---'; kubectl -n mlflow get pods -o wide; echo '---'; kubectl -n mlflow get events --sort-by='.lastTimestamp' | tail -n 40

kubectl -n mlflow get deployment fastapi -o wide; echo '---'; kubectl -n mlflow describe deployment fastapi | sed -n '1,240p'; echo '---'; kubectl -n mlflow get pods -o wide --show-labels; echo '---'; kubectl -n mlflow get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.ownerReferences[0].name}{"\n"}{end}'


# fastapi デプロイの「NewReplicaSet」は fastapi-b6d6d5574。ただし古い RS fastapi-5cb87cffb8 にもポッドがあり、両方のポッドは ImagePullBackOff で Ready になっていない。
# DESIRED/CURRENT/READY が 0 の RS は削除してよい。-> デプロイを正常化してから削除。直接削ると稼働中の Pod を消してしまう可能性があり

# 完全に不要な ReplicaSet を削除
kubectl -n mlflow get rs -o jsonpath='{range .items[?(@.status.replicas==0)]}{.metadata.name}{"\n"}{end}'
kubectl -n mlflow delete rs <rs-name1> <rs-name2> ...

# Deployment の履歴を 2 に制限して古い RS を自動削除する設定
kubectl -n mlflow patch deployment fastapi -p '{"spec":{"revisionHistoryLimit":2}}'

# kind ノードにイメージをロードし直す
kind load docker-image localhost:5001/fastapi-iris:latest --name agritech-mlops
kubectl -n mlflow rollout restart deployment/fastapi; kubectl -n mlflow rollout status deployment/fastapi --timeout=90s
# => timeout...

# api/fastapi-deploy.yaml に imagePullPolicy: IfNotPresent 追加して再デプロイ
# kubectl apply -f api/fastapi-deploy.yaml
# または下記コマンドでパッチ適用
kubectl -n mlflow patch deployment fastapi -p '{"spec":{"template":{"spec":{"containers":[{"name":"fastapi","imagePullPolicy":"IfNotPresent"}]}}}}'

# Deployment 再起動
kubectl -n mlflow rollout restart deployment/fastapi; kubectl -n mlflow rollout status deployment/fastapi --timeout=90s
# => OK
```

