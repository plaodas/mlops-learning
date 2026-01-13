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
[原因の原因] ImagePullBackOff が発生している。
[対策] imagePullPolicy を IfNotPresent に設定し、古い ReplicaSet を削除後、kind ノードにイメージをロードし直してから Deployment を再起動する。
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



## 使うモデル models:/argo-dag-demo/1 を MLflow に登録
```bash
# 手動でバックグラウンド起動（ログを /tmp/mlflow-pf.log に保存）
nohup kubectl -n mlflow port-forward svc/mlflow-svc 5005:5000 --address 127.0.0.1 > /tmp/mlflow-pf.log 2>&1 & echo $!

# models:/argo-dag-demo/1 を登録するスクリプトを実行
python - <<'PY'
import os
import mlflow
from mlflow.tracking import MlflowClient
import tempfile
import shutil

mlflow.set_tracking_uri('http://127.0.0.1:5005')
client = MlflowClient()
exp = mlflow.get_experiment_by_name('argo-dag-demo')
exp_id = exp.experiment_id if exp else client.create_experiment('argo-dag-demo')
runs = client.search_runs([exp_id], order_by=["attributes.start_time DESC"], max_results=50)

for r in runs:
    run_id = r.info.run_id
    print('Inspecting run', run_id)
    arts = client.list_artifacts(run_id, path='model')
    if not arts:
        print(' no model artifact in run')
        continue
    for a in arts:
        if a.path.endswith('model.pkl') or a.path == 'model.pkl':
            print(' found model file at', a.path)
            tmpdir = tempfile.mkdtemp(prefix='mlflow_register_')
            new_run_id = None
            try:
                dl = client.download_artifacts(run_id, a.path, dst_path=tmpdir)
                print(' downloaded to', dl)
                save_dir = os.path.join(tmpdir, 'pyfunc_model')
                os.makedirs(save_dir, exist_ok=True)
                from mlflow.pyfunc import PythonModel
                import joblib

                class WrapperModel(PythonModel):
                    def load_context(self, context):
                        import joblib
                        self.model = joblib.load(context.artifacts['model'])
                    def predict(self, context, model_input):
                        return self.model.predict(model_input)

                artifact_path = os.path.join(tmpdir, os.path.basename(dl))
                mlflow.pyfunc.save_model(path=save_dir, python_model=WrapperModel(), artifacts={'model': artifact_path})
                print('Saved pyfunc model to', save_dir)
                # create temp run to upload artifact
                new_run = client.create_run(exp_id)
                new_run_id = new_run.info.run_id
                print('Created temp run', new_run_id)
                client.log_artifacts(new_run_id, save_dir, artifact_path='model')
                print('Logged artifacts to run')
                model_uri = f'runs:/{new_run_id}/model'
                print('Registering model from', model_uri)
                mv = mlflow.register_model(model_uri, 'argo-dag-demo')
                print('Registered model version', mv.version)
                client.transition_model_version_stage('argo-dag-demo', mv.version, stage='None')
            finally:
                # 必ずランを終了させる（例外が起きても残さない）
                if new_run_id:
                    try:
                        client.set_terminated(new_run_id, status='FINISHED')
                        print('Terminated temp run', new_run_id)
                    except Exception as e:
                        print('Failed to terminate temp run', new_run_id, e)
                shutil.rmtree(tmpdir)
                # 終了後は次の候補を探したければ continue する（元コードは早期終了していた）
print('Done')
PY


# ログ確認
tail -f /tmp/mlflow-pf.log

# プロセス停止（PIDがわかれば kill <PID>、簡易に）
pkill -f "kubectl -n mlflow port-forward .*5005:5000"

# ポート確認
ss -ltnp | grep 5005


# 👆で登録したmodelのRunsがrunningのまままの場合、下記で強制終了させる
python - <<'PY'
from mlflow.tracking import MlflowClient
import mlflow
mlflow.set_tracking_uri('http://127.0.0.1:5005')
client = MlflowClient()
exp = client.get_experiment_by_name('argo-dag-demo')
if not exp:
    print('Experiment argo-dag-demo not found')
    raise SystemExit(1)
exp_id = exp.experiment_id
runs = client.search_runs([exp_id], filter_string="attributes.status='RUNNING'", max_results=500)
if not runs:
    print('No RUNNING runs found')
else:
    print('Found', len(runs), 'RUNNING runs:')
    for r in runs:
        rid = r.info.run_id
        print('-', rid)
    for r in runs:
        rid = r.info.run_id
        try:
            client.set_terminated(rid, status='FINISHED')
            print('Terminated', rid)
        except Exception as e:
            print('Failed to terminate', rid, e)
# show summary
runs2 = client.search_runs([exp_id], order_by=["attributes.start_time DESC"], max_results=200)
print('--- runs after update ---')
for r in runs2[:20]:
    print(r.info.run_id, r.info.status)
PY

```
