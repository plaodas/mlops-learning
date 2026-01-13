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



### Step 5：FastAPI アプリの修正と再デプロイ
```bash
docker build -t registry5001:5000/fastapi-iris:latest -f api/Dockerfile api
docker tag registry5001:5000/fastapi-iris:latest localhost:5001/fastapi-iris:latest
kind load docker-image localhost:5001/fastapi-iris:latest --name agritech-mlops
kubectl -n mlflow rollout restart deployment/fastapi
```


### Step 6：FastAPI アプリにアクセスして推論を試す
```bash
curl -X POST http://api.local/predict/27 -H "Content-Type: application/json" -d '{"sepal length (cm)":5.1,"sepal width (cm)":3.5,"petal length (cm)":6.4,"petal width (cm)":2.2}'

{"prediction":2} <== 推論結果

```


## トラブルシューティング
### FastAPI アプリにアクセスできない kubectl -n mlflow rollout status deployment/fastapi => replicas are pending termination... のまま固まってしまう
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

# 🌟api/fastapi-deploy.yaml に imagePullPolicy: IfNotPresent 追加して再デプロイ
# kubectl apply -f api/fastapi-deploy.yaml
# または下記コマンドでパッチ適用
kubectl -n mlflow patch deployment fastapi -p '{"spec":{"template":{"spec":{"containers":[{"name":"fastapi","imagePullPolicy":"IfNotPresent"}]}}}}'

# Deployment 再起動
kubectl -n mlflow rollout restart deployment/fastapi; kubectl -n mlflow rollout status deployment/fastapi --timeout=90s
# => OK
```

### モデルの artifact 内容を確認したい
```bash
# FastAPI Pod 内でモデルのartifact URIを表示
kubectl -n mlflow exec fastapi-85d4b7cf5f-vbgjp  -- python -c "from mlflow.tracking import MlflowClient; print(MlflowClient().get_model_version_download_uri('argo-dag-demo','23'))"

# artifact をダウンロードして中身確認（Pod内で実行）
kubectl -n mlflow exec fastapi-85d4b7cf5f-vbgjp  -- python - <<'PY'
import mlflow, tempfile, os
uri='runs:/abaf2bf898f84206a4e34f0b4f363b84/model'
dst=tempfile.mkdtemp()
print('dst',dst)
p=mlflow.artifacts.download_artifacts(uri, dst_path=dst)
for r,d,f in os.walk(dst):
    print(r, d, f)
PY

# MLflow レジストリの argo-dag-demo バージョン一覧と MinIO の model.tgz をチェック
bash -lc "kubectl -n mlflow exec -i fastapi-85d4b7cf5f-vbgjp -- python - <<'PY'
from mlflow.tracking import MlflowClient
c = MlflowClient('http://mlflow-svc.mlflow.svc.cluster.local:5000')
# fallback: search all and filter
all_mvs = c.search_model_versions()
for mv in all_mvs:
    if mv.name == 'argo-dag-demo':
        print(mv.version, mv.source, mv.run_id)
PY
"
# MinIO 上の argo-artifacts バケット内を確認
bash -lc "kubectl -n argo exec mc-client -- sh -c \"mc ls --recursive myminio/argo-artifacts || true\""
```

### FastAPI アプリへのポートフォワード手順
```bash
# 手動でバックグラウンド起動（ログを /tmp/mlflow-pf.log に保存）
nohup kubectl -n mlflow port-forward svc/mlflow-svc 5005:5000 --address 127.0.0.1 > /tmp/mlflow-pf.log 2>&1 & echo $!
# ログ確認
tail -f /tmp/mlflow-pf.log

# プロセス停止（PIDがわかれば kill <PID>、簡易に）
pkill -f "kubectl -n mlflow port-forward .*5005:5000"

# ポート確認
ss -ltnp | grep 5005
```


### FastAPI アプリのトラブルシューティング
```bash
# Ingressログの確認
kubectl -n ingress-nginx logs -l app.kubernetes.io/name=ingress-nginx --tail=200

# FastAPI Pod の状態確認
kubectl -n mlflow get pods
kubectl -n mlflow describe pod fastapi-85d4b7cf5f-vbgjp

# FastAPI Pod 内で FastAPI アプリにアクセスできるか確認
kubectl -n mlflow exec pod/fastapi-85d4b7cf5f-vbgjp -- python -c 'import http.client; c=http.client.HTTPConnection("127.0.0.1",8000,timeout=5); c.request("GET","/"); r=c.getresponse(); print(r.status)'
```


### Deployment / ReplicaSet /Pod /Events を一括で調べ、古い ReplicaSet や残留 Pod を特定
```bash
kubectl -n mlflow get deployment fastapi -o wide; echo '---'; kubectl -n mlflow describe deployment fastapi | sed -n '1,240p'; echo '---'; kubectl -n mlflow get rs -o wide --sort-by=.metadata.creationTimestamp; echo '---'; kubectl -n mlflow get pods -o wide --show-labels; echo '---'; kubectl -n mlflow get events --sort-by='.lastTimestamp' | tail -n 40

# ReplicaSet ごとの Pod 状態とログをまとめて確認
kubectl -n mlflow get pods -o wide; echo '--- rs ---'; kubectl -n mlflow get rs -o wide --sort-by=.metadata.creationTimestamp; echo '--- logs new pods ---'; for p in $(kubectl -n mlflow get pods -l app=fastapi -o jsonpath='{.items[*].metadata.name}'); do echo '***' $p; kubectl -n mlflow logs $p --tail=200 || true; done

# FastAPI Pod のログ確認
kubectl -n mlflow logs pod/fastapi-85d4b7cf5f-vbgjp --tail=500 || true; echo '--- previous ---'; kubectl -n mlflow logs pod/fastapi-85d4b7cf5f-vbgjp --previous --tail=500 || true

```


### 再起動後の環境確認手順
```bash
# 1) 基本状況確認
sudo systemctl status docker    # Docker が動いているか
kubectl cluster-info
kubectl get nodes
kubectl get pods -A

# 2) kindクラスタを使っているか確認
kind get clusters

# 3) ローカル registry が必要なら確認/起動
docker ps --filter "name=registry" --format '{{.Names}} {{.Status}}'
# 無ければ（例）:
docker run -d -p 5001:5000 --name registry registry:2

# 4) Pod が ImagePullBackOff ならイメージを再ロード
kind load docker-image localhost:5001/fastapi-iris:latest --name agritech-mlops

# 5) デプロイの再起動（必要なら）
kubectl -n mlflow rollout restart deployment/fastapi
kubectl -n mlflow rollout status deployment/fastapi --timeout=120s

```



### mlflowモデルの永続化 ー＞ kind クラスタが StorageClass を提供してるか確認
提供していない場合、PersistentVolumeClaim がバインドされない。その場合は一時的に hostPath ベースの PersistentVolume を作るか、mlflow-deploy.yaml を hostPath に書き換える。
```bash
#  StorageClass の確認
kubectl get storageclass

# 詳細確認
kubectl get sc -o yaml
kubectl get sc -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.annotations.storageclass\\.kubernetes\\.io/is-default-class}{"\n"}{end}'

# PersistentVolume / PVC 状態確認
kubectl get pv
kubectl -n mlflow get pvc mlflow-pvc -o wide

kubectl get pv pvc-b851f2e6-d4c7-46cd-ac4b-1d50312bbcd2 -o yaml
kubectl describe pv pvc-b851f2e6-d4c7-46cd-ac4b-1d50312bbcd2

# kind ノードにストレージプロビジョナーが動いているか確認
kubectl get pods -A | grep -E 'local-path|hostpath|storage-provisioner' || true

# PersistentVolume を手動で作成する例（hostPath ベース）
POD=$(kubectl -n mlflow get pod -l app=mlflow -o jsonpath='{.items[0].metadata.name}')
kubectl -n mlflow exec $POD -- sh -c "echo persisted > /mlflow/persistence-check.txt"
kubectl -n mlflow delete pod $POD
# 新しい Pod が Ready になったら確認:
NEWPOD=$(kubectl -n mlflow get pod -l app=mlflow -o jsonpath='{.items[0].metadata.name}')
kubectl -n mlflow exec $NEWPOD -- cat /mlflow/persistence-check.txt


## ARGO workflow resubmit後
## 登録済みモデルの確認する

# 手動で MLflow サーバーにポートフォワード
# 登録済みモデルの一覧を確認
kubectl -n mlflow port-forward svc/mlflow-svc 5005:5000 --address 127.0.0.1 > /tmp/mlflow-pf.log 2>&1 & echo $!

python - <<'PY'
from mlflow.tracking import MlflowClient
client = MlflowClient(tracking_uri="http://127.0.0.1:5005")
# Try multiple listing APIs for compatibility
rms = None
for fn in ("search_registered_models","list_registered_models","search_registered_models"):
    if hasattr(client, fn):
        try:
            rms = getattr(client, fn)()
            break
        except TypeError:
            # some methods require args
            try:
                rms = getattr(client, fn)(filter_string=None)
                break
            except Exception:
                pass
        except Exception:
            pass
if not rms:
    print("No registered models (or failed to list)")
else:
    for rm in rms:
        # support both object and dict-like
        name = getattr(rm, 'name', None) or (rm.get('name') if isinstance(rm, dict) else str(rm))
        print("Model:", name)
        versions = getattr(rm, 'latest_versions', None) or (rm.get('latest_versions') if isinstance(rm, dict) else [])
        for v in versions:
            if hasattr(v, 'version'):
                print(" ", v.version, v.current_stage, v.source)
            else:
                print(" ", v.get('version'), v.get('current_stage'), v.get('source'))
PY

# モデルを Production に移行し、fastapi を再起動して推論を1回実行
# **DEPRECATED** モデルのステージを Production に変更（ Stages have been deprecated in the new Model Registry UI. Learn how to migrate models ）
python - <<'PY'
from mlflow.tracking import MlflowClient
client = MlflowClient(tracking_uri="http://127.0.0.1:5005")
# transition to Production, archive existing versions
client.transition_model_version_stage("argo-dag-demo", "7", stage="Production", archive_existing_versions=True)
print('Transitioned argo-dag-demo v1 to Production')
PY

# fastapi を再起動
kubectl -n mlflow rollout restart deployment/fastapi && kubectl -n mlflow rollout status deployment/fastapi --timeout=120s
# ポートフォワードしてアクセス
kubectl -n mlflow port-forward svc/fastapi-svc 8000:8000 --address 127.0.0.1 > /tmp/fastapi-pf.log 2>&1 & echo $!
# 推論リクエストを実行
curl -sS -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" -d '{"sepal length (cm)":5.1,"sepal width (cm)":3.5,"petal length (cm)":1.4,"petal width (cm)":0.2}'




# ポートフォワードを開始し、argo-dag-demo の version=1 の source とダウンロード URI を取得
kubectl -n mlflow port-forward svc/mlflow-svc 5005:5000 --address 127.0.0.1 > /tmp/mlflow-pf.log 2>&1 & echo $!
python - <<'PY'
from mlflow.tracking import MlflowClient
client = MlflowClient(tracking_uri='http://127.0.0.1:5005')
name='argo-dag-demo'
version='1'
try:
    mv = client.get_model_version(name, version)
    print('model_version.source:', mv.source)
    print('model_version.run_id:', getattr(mv,'run_id',None))
    print('model_version.status:', getattr(mv,'status',None))
except Exception as e:
    print('get_model_version failed:', e)
try:
    uri = client.get_model_version_download_uri(name, version)
    print('download_uri:', uri)
except Exception as e:
    print('get_model_version_download_uri failed:', e)
# list all versions
try:
    vs = client.get_latest_versions(name)
    for v in vs:
        print('latest:', v.version, v.current_stage, v.source)
except Exception:
    pass
PY

#-------
model_version.source: runs:/1761d31b71cf49c48abdf6e247fff447/model
model_version.run_id: 1761d31b71cf49c48abdf6e247fff447
model_version.status: READY
download_uri: runs:/1761d31b71cf49c48abdf6e247fff447/model
#-------
# FastAPI Pod 内で指定の artifact URI をダウンロードして中身を確認
POD=$(kubectl -n mlflow get pod -l app=fastapi -o jsonpath='{.items[0].metadata.name}'); echo Pod:$POD; kubectl -n mlflow exec $POD -- python - <<'PY'
import mlflow, os, traceback
uri='runs:/1761d31b71cf49c48abdf6e247fff447/model'
dst='/tmp/mlflow_art'
try:
    print('MLflow version:', mlflow.__version__)
    print('Attempting download:', uri)
    p = mlflow.artifacts.download_artifacts(artifact_uri=uri, dst_path=dst)
    print('downloaded_to:', p)
    for r,d,f in os.walk(dst):
        print('WALK', r, d, f)
except Exception:
    traceback.print_exc()
PY
