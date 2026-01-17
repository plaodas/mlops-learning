# メトリクスの設定

### Grafana のポートフォワード
export POD_NAME=$(kubectl --namespace monitoring get pod -l "app.kubernetes.io/name=grafana,app.kubernetes.io/instance=kube-prometheus-stack" -oname)
kubectl --namespace monitoring port-forward $POD_NAME 3000

### Prometheus のポートフォワード
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090

curl -v http://127.0.0.1:9090/metrics || true


### serviceMonitor/monitoring/argo-workflows/0 のエンドポイントhttps://10.244.0.26:9090/metricsにブラウザからアクセスする方法

```bash
# UIで serviceMonitor/monitoring/argo-workflows/0 のLabelsを確認
container="workflow-controller"
endpoint="metrics"
instance="10.244.0.26:9090"
job="workflow-controller-metrics"
namespace="argo"
pod="workflow-controller-5f774db4d5-hgkwk"
service="workflow-controller-metrics"



# Pod をリストして確認
kubectl -n argo get pods -l app=workflow-controller -o wide

#  Pod の詳細を確認
kubectl -n argo describe pod workflow-controller-5f774db4d5-hgkwk

# workflow-controller-metrics Service がどの Pod をターゲットにしているか確認を確認
kubectl -n argo get svc workflow-controller-metrics -o yaml

# workflow-controllerのPod をリストして確認
kubectl -n argo get pods -l app=workflow-controller -o wide

# workflow-controller-metrics Service がどのエンドポイントにルーティングしているかを確認
kubectl -n argo get endpoints workflow-controller-metrics -o yaml
export POD_NAME=$(kubectl -n argo get endpoints workflow-controller-metrics -o jsonpath="{.subsets[0].addresses[0].targetRef.name}")
kubectl -n argo port-forward pod/$POD_NAME 9090:9090

curl -v http://localhost:9090/metrics || true
```


### serviceMonitor/monitoring/mlflow-exporter/0 のエンドポイントhttp://10.244.0.59:8000/metrics にブラウザからアクセスする方法

```bash
# UIで serviceMonitor/monitoring/mlflow-exporter/0 のLabelsを確認
container="exporter"
endpoint="metrics"
instance="10.244.0.59:8000"
job="mlflow-exporter"
namespace="mlflow"
pod="mlflow-exporter-7866946c9c-bmrmv"
service="mlflow-exporter"

# Pod をリストして確認
kubectl -n mlflow get pods -l app=mlflow-exporter -o wide

#  Pod の詳細を確認
kubectl -n mlflow describe pod mlflow-exporter-7866946c9c-bmrmv

# mlflow-exporter Service がどの Pod をターゲットにしているか確認を確認
kubectl -n mlflow get svc mlflow-exporter -o yaml

# mlflow-exporterのPod をリストして確認
kubectl -n mlflow get pods -l app=mlflow-exporter -o wide

# mlflow-exporter Service がどのエンドポイントにルーティングしているかを確認
kubectl -n mlflow get endpoints mlflow-exporter -o yaml

# mlflow-exporter Service がどのエンドポイントにルーティングしているかを確認
kubectl -n mlflow get endpoints mlflow-exporter -o yaml
export POD_NAME=$(kubectl -n mlflow get endpoints mlflow-exporter -o jsonpath="{.subsets[0].addresses[0].targetRef.name}")
kubectl -n mlflow port-forward pod/$POD_NAME 8001:8000

curl -v http://localhost:8001/metrics || true

```



### Argo Workflows → Prometheus → Grafana で accuracy / loss を可視化する仕組み

ステップ 1：Pushgateway をデプロイ
```bash
helm install pushgateway prometheus-community/prometheus-pushgateway -n monitoring

# Service 名は
# pushgateway.monitoring.svc.cluster.local:9091
```

ステップ 2：Argo Workflow の中で accuracy/loss を Push
pipelines/dag/mlflow-dag-workflow.yaml の中に以下のステップを追加
```yaml
  - name: push-metrics
    container:
      image: python:3.10
      command: ["python", "-c"]
      args:
        - |
          import requests
          accuracy = {{inputs.parameters.accuracy}}
          loss = {{inputs.parameters.loss}}
          data = f"""
          model_accuracy {accuracy}
          model_loss {loss}
          """
          requests.post(
            "http://pushgateway.monitoring.svc.cluster.local:9091/metrics/job/model_training",
            data=data
          )
    inputs:
      parameters:
        - name: accuracy
        - name: loss
```
```bash
docker build -t registry5001:5000/mlflow-dag:latest -f pipelines/dag/Dockerfile pipelines/dag
docker tag registry5001:5000/mlflow-dag:latest localhost:5001/mlflow-dag:latest
kind load docker-image localhost:5001/mlflow-dag:latest --name agritech-mlops
kubectl -n argo delete workflow mlflow-dag || true
kubectl -n argo create -f pipelines/dag/mlflow-dag-workflow.yaml
```


### トラブルシューティング
```bash
# Service の確認
kubectl -n monitoring get svc

# Pushgateway の Service 詳細を確認
kubectl -n monitoring describe svc pushgateway-prometheus-pushgateway

kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9091:9091

echo "model_accuracy 0.95" | curl --data-binary @- http://localhost:9091/metrics/job/model_training


kubectl -n monitoring port-forward svc/pushgateway-prometheus-pushgateway 9091:9091
http://localhost:9091/
#でつながったがmetricsメニューの表示は空だった

echo "model_accuracy 0.95" | curl --data-binary @- http://localhost:9091/metrics/job/model_training
# でmetricsメニューに表示された
# -> Pushgateway の設定は正しい
# -> Argo Workflow の push-metrics ステップの確認が必要 -> requests モジュールが入っていなかった

```

ステップ 3：Prometheus でメトリクスを拾う

ステップ 4：Grafana ダッシュボードを作成
