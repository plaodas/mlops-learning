# Prometheus / Grafana を入れて “運用監視” を完成させる
Prometheus はメトリクス収集と監視アラートの仕組みを提供し、Grafana は収集したメトリクスの可視化を行います。
このドキュメントでは、Kubernetes クラスターに Prometheus と Grafana をインストールし、基本的な監視ダッシュボードを設定する手順を説明します。


## 前提条件
- Kubernetes クラスターが稼働していること
- Helm がインストールされていること
- kubectl がインストールされていること

## 手順

### Prometheus Operator を入れる
```bash
# Helm リポジトリの追加と更新
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# kube-prometheus-stack のインストール
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring --create-namespace

# インストールの確認
kubectl --namespace monitoring get pods -l "release=kube-prometheus-stack"

# Grafana の初期パスワードの取得
kubectl get secrets --namespace monitoring kube-prometheus-stack-grafana -o jsonpath="{.data.admin-password}" | base64 -d ; echo

# Grafana ダッシュボードへのアクセス
export POD_NAME=$(kubectl --namespace monitoring get pod -l "app.kubernetes.io/name=grafana,app.kubernetes.io/instance=kube-prometheus-stack" -oname)
kubectl --namespace monitoring port-forward $POD_NAME 3000

kubectl get secret --namespace monitoring -l app.kubernetes.io/component=admin-secret -o jsonpath="{.items[0].data.admin-password}" | base64 --decode ; echo
```

http://localhost:3000
にブラウザでアクセスし、ユーザー名 "admin" と上記で取得したパスワードでログインします。


### Argo Workflows のメトリクスを Prometheus に流す
Argo Workflows のメトリクスエンドポイントを有効にするために、
Argo の ConfigMap に追加：

```yaml
metricsConfig:
  enabled: true
  path: /metrics
  port: 9090
```

ServiceMonitor を作る：
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: argo-workflows
  namespace: argo
spec:
  selector:
    matchLabels:
      app: argo-server
  endpoints:
    - port: metrics
      interval: 15s
```

### 変更の適用とデプロイの再起動
```bash
kubectl apply -f argo-artifact-config.yaml
kubectl apply -f monitoring/argo-servicemonitor.yaml
# ConfigMap の変更を反映するためにデプロイを再起動
kubectl rollout restart deployment argo-server -n argo
kubectl rollout restart deployment workflow-controller -n argo
```

### MLflow のメトリクスを Prometheus に流す
MLflow Prometheus exporter をデプロイします。
mlflow-exporter-deployment.yaml を作成：
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-exporter
  namespace: mlflow
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mlflow-exporter
  template:
    metadata:
      labels:
        app: mlflow-exporter
    spec:
      containers:
      - name: exporter
        image: ghcr.io/canonical/mlflow-prometheus-exporter:latest
        args:
          - "--mlflow-url=http://mlflow-svc.mlflow.svc.cluster.local:5000"
        ports:
        - containerPort: 8000
```

mlflow-exporter-service.yaml を作成：
```yaml
apiVersion: v1
kind: Service
metadata:
  name: mlflow-exporter
  namespace: mlflow
spec:
  selector:
    app: mlflow-exporter
  ports:
  - port: 8000
    targetPort: 8000
```

mlflow-exporter-servicemonitor.yaml を作成：
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: mlflow-exporter
  namespace: mlflow
spec:
  selector:
    matchLabels:
      app: mlflow-exporter
  endpoints:
  - port: 8000
    interval: 15s
```

### 変更の適用とデプロイ
```bash
kubectl apply -f monitoring/mlflow-exporter-deployment.yaml
kubectl apply -f monitoring/mlflow-exporter-service.yaml
kubectl apply -f monitoring/mlflow-exporter-servicemonitor.yaml
```

### Prometheus ターゲットの確認
```bash
# Prometheus ターゲットの確認（ポートフォワード中のローカル環境向け）
curl -s 'http://127.0.0.1:9090/api/v1/targets' | jq '.data.activeTargets[] | select(.discoveredLabels.__meta_kubernetes_namespace=="mlflow")'

# 重要フィールドだけ抜き出す（見やすい）
curl -s 'http://127.0.0.1:9090/api/v1/targets' \
  | jq '.data.activeTargets[] | select(.discoveredLabels.__meta_kubernetes_namespace=="mlflow") | {scrapeUrl:.scrapeUrl, health:.health, lastError:.lastError, labels:.labels}'

# mlflow を含む scrapeUrl のみ確認
curl -s 'http://127.0.0.1:9090/api/v1/targets' \
  | jq -r '.data.activeTargets[] | .scrapeUrl + "  (" + .health + ")"' | grep mlflow || true
```

### Grafana ダッシュボードの設定
Grafana にログインし、以下のようなダッシュボードを作成します。

ログイン情報（デフォルト）
- user: admin
- pass: prom-operator



 ダッシュボード 1：Argo Workflows Overview
- workflow 実行数
- 成功率
- 平均 duration
- ステップごとの duration
- 失敗 workflow の一覧
→ パイプラインの健康状態が一目でわかる


ダッシュボード 2：MLflow Overview
- Run 数
- Model Registry のバージョン数
- artifact サイズ
- accuracy の分布
- 最新モデルの accuracy 推移
→ モデルの品質が可視化される


ダッシュボード 3：FastAPI 推論 API
FastAPI は uvicorn のメトリクスを Prometheus に出せる。
- QPS
- latency
- error rate
- メモリ/CPU
- Pod 数
→ 推論 API の安定性がわかる


### アラート設定（Alertmanager）
最低限これだけ入れれば OK。
- Argo workflow 失敗率 > 10%
- MLflow の accuracy が急落
- FastAPI の latency > 500ms
- MinIO の容量が 80% 超え
- PostgreSQL の接続エラー

これで 運用事故を未然に防止 できます！








## トラブルシューティング
Prometheus がどの ServiceMonitor を監視しているか確認するため、Prometheus CR と全 ServiceMonitor、及び mlflow 名前空間の Service をチェック
```bash
kubectl get servicemonitor -A
kubectl get servicemonitor mlflow-exporter -n mlflow -o yaml || true
kubectl get servicemonitor mlflow-exporter -n monitoring -o yaml || true
kubectl get prometheus -n monitoring -o yaml || true
kubectl get svc -n mlflow || true

# 監視対象の ServiceMonitor の namespaceSelector と selector を確認
kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o jsonpath='{.spec.serviceMonitorNamespaceSelector}' ; echo
kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o jsonpath='{.spec.serviceMonitorSelector}' ; echo
kubectl -n mlflow get servicemonitor mlflow-exporter -o yaml || true
kubectl -n monitoring get servicemonitor mlflow-exporter -o yaml || true

# 監視対象の ServiceMonitor の namespaceSelector と selector を確認
kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o jsonpath='{.spec.serviceMonitorNamespaceSelector.matchNames}' ; echo
kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o jsonpath='{.spec.serviceMonitorSelector.matchLabels}' ; echo

kubectl -n monitoring get servicemonitor mlflow-exporter -o yaml || true
kubectl -n mlflow get servicemonitor mlflow-exporter -o yaml || true

```
-> xxx-servicemonitor.yaml に namespaceSelector を追加
```bash
kubectl apply -f monitoring/mlflow-exporter-deployment.yaml
kubectl apply -f monitoring/mlflow-exporter-service.yaml
kubectl apply -f monitoring/mlflow-exporter-servicemonitor.yaml
kubectl apply -f monitoring/argo-servicemonitor.yaml

kubectl -n mlflow get deploy,svc,pods -o wide || true
kubectl -n monitoring get servicemonitor -o wide || true
kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o jsonpath='{.spec.serviceMonitorNamespaceSelector}' ; echo || true
kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o jsonpath='{.spec.serviceMonitorSelector}' ; echo || true
curl -s 'http://127.0.0.1:9090/targets?search=mlflow' | sed -n '1,200p' || true

# Prometheus ターゲットの確認（ポートフォワード中のローカル環境向け）
# (既にポートフォワード済みなら次を実行)
xdg-open \"http://127.0.0.1:9090/targets?search=mlflow\"



kubectl -n mlflow get events --sort-by='.metadata.creationTimestamp' | sed -n '1,200p'
#  -> Back-off pulling image "ghcr.io/canonical/mlflow-prometheus-exporter:latest がでてるので、イメージのバージョンを確認
# イメージのバージョンを確認
curl -I -H "Accept: application/vnd.docker.distribution.manifest.v2+json" https://ghcr.io/v2/canonical/mlflow-prometheus-exporter/manifests/latest -s -S -D - | sed -n '1,120p'
  -> 401 Unauthorized がでてるので、パブリックイメージではない可能性あり


# Kind に直接載せる場合、イメージをローカルに pull してから kind load docker-image で Kind クラスターにロードする
git clone https://github.com/canonical/mlflow-prometheus-exporter.git ./docker/mlflow-prometheus-exporter

docker build -t registry5001:5000/mlflow-prometheus-exporter:local -f docker/mlflow-prometheus-exporter/Dockerfile docker/mlflow-prometheus-exporter
docker tag registry5001:5000/mlflow-prometheus-exporter:local localhost:5001/mlflow-prometheus-exporter:local
docker push localhost:5001/mlflow-prometheus-exporter:local
# Kind クラスターにロード
kind load docker-image localhost:5001/mlflow-prometheus-exporter:local --name agritech-mlops
kubectl -n mlflow rollout restart deployment/mlflow-exporter
kubectl -n mlflow get pods -w

kubectl apply -f monitoring/argo-servicemonitor.yaml

kubectl apply -f monitoring/mlflow-exporter-deployment.yaml
kubectl apply -f monitoring/mlflow-exporter-service.yaml
kubectl apply -f monitoring/mlflow-exporter-servicemonitor.yaml
kubectl -n mlflow rollout restart deployment/mlflow-exporter
kubectl -n mlflow get pods -o wide
kubectl -n mlflow describe pod -l app=mlflow-exporter








# クラスタ名がデフォルトなら --name は不要
kind load docker-image localhost:5001/mlflow-prometheus-exporter:local --name agritech-mlops
# 確認
kind get clusters

# imagePullPolicy を IfNotPresent にしておくと確実
kubectl -n mlflow set image deployment/mlflow-exporter exporter=localhost:5001/mlflow-prometheus-exporter:local
kubectl -n mlflow rollout restart deployment/mlflow-exporter
kubectl -n mlflow get pods -w


# クローン→ビルド→Kindへロード→デプロイ差し替えを順に実行するスクリプト
set -e
rm -rf /tmp/mlflow-prometheus-exporter
git clone https://github.com/canonical/mlflow-prometheus-exporter.git /tmp/mlflow-prometheus-exporter
cd /tmp/mlflow-prometheus-exporter
# Build image
if ! docker build -t localhost:5001/mlflow-prometheus-exporter:local .; then
  echo "docker build failed" >&2
  exit 1
fi
# Load into kind cluster (try with --name then without)
if ! kind load docker-image localhost:5001/mlflow-prometheus-exporter:local --name agritech-mlops; then
  kind load docker-image localhost:5001/mlflow-prometheus-exporter:local || true
fi
# Update deployment image
kubectl -n mlflow set image deployment/mlflow-exporter exporter=localhost:5001/mlflow-prometheus-exporter:local || true
# Ensure imagePullPolicy IfNotPresent
kubectl -n mlflow patch deployment mlflow-exporter --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]' 2>/dev/null ||
kubectl -n mlflow patch deployment mlflow-exporter --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]' || true
kubectl -n mlflow rollout restart deployment/mlflow-exporter || true
# Wait a bit and print status
sleep 5
kubectl -n mlflow get pods -o wide || true
POD=$(kubectl -n mlflow get pods -l app=mlflow-exporter -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$POD" ]; then
  kubectl -n mlflow describe pod "$POD" || true
fi
# Show Prometheus targets for mlflow (requires port-forward active)
curl -s 'http://127.0.0.1:9090/targets?search=mlflow' | sed -n '1,200p' || true


kubectl apply -f monitoring/mlflow-exporter-deployment.yaml
kubectl -n mlflow rollout restart deployment/mlflow-exporter
kubectl -n mlflow get pods -o wide
kubectl -n mlflow describe pod -l app=mlflow-exporter
# 確認用（Prometheus をローカルでポートフォワード済みの場合）
curl -s 'http://127.0.0.1:9090/targets?search=mlflow' | sed -n '1,200p'
#   -> まだターゲットに出てこない


# デプロイをローカルイメージに差し替え
kubectl -n mlflow set image deployment/mlflow-exporter exporter=localhost:5001/mlflow-prometheus-exporter:local

# 再起動して状態確認
kubectl -n mlflow rollout restart deployment/mlflow-exporter
kubectl -n mlflow get pods -o wide

# Pod が立ち上がらない場合はログ確認
POD=$(kubectl -n mlflow get pods -l app=mlflow-exporter -o jsonpath='{.items[0].metadata.name}')
kubectl -n mlflow logs $POD -c exporter --tail=200

# Prometheus のターゲット（API）を直接確認する（HTMLではなくAPIを使う）
curl -s 'http://127.0.0.1:9090/api/v1/targets?search=mlflow' | sed -n '1,200p'


# 1) デプロイをローカルイメージに差し替え
kubectl -n mlflow set image deployment/mlflow-exporter exporter=localhost:5001/mlflow-prometheus-exporter:local

# 2) imagePullPolicy を確実に IfNotPresent にする（既にあれば replace が失敗して add を試す）
kubectl -n mlflow patch deployment mlflow-exporter --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]' 2>/dev/null || \
kubectl -n mlflow patch deployment mlflow-exporter --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]' || true

# 3) 古い Pod を削除して新しい Pod を作らせる
kubectl -n mlflow delete pods -l app=mlflow-exporter

# 4) 状態を監視（Ready になるまで）
kubectl -n mlflow get pods -o wide -w

# 5) 起動後にログ確認（必要なら）
kubectl -n mlflow logs -l app=mlflow-exporter -c exporter --tail=200

# 6) Prometheus ターゲット確認（ローカルで port-forward 中なら）
curl -s 'http://127.0.0.1:9090/api/v1/targets?search=mlflow' | sed -n '1,200p'



# Service、ServiceMonitor、Prometheus CR、そして Prometheus のターゲットを確認
kubectl -n mlflow get svc mlflow-exporter -o yaml || true
kubectl -n monitoring get servicemonitor mlflow-exporter -o yaml || true
kubectl -n mlflow get servicemonitor mlflow-exporter -o yaml || true
kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o yaml || true
curl -s 'http://127.0.0.1:9090/api/v1/targets' | jq '.data.activeTargets[] | select(.discoveredLabels.__meta_kubernetes_namespace=="mlflow")' || true

kubectl -n monitoring get servicemonitor mlflow-exporter -o yaml || true
kubectl -n mlflow get servicemonitor mlflow-exporter -o yaml || true

kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o yaml || true

kubectl apply -f monitoring/mlflow-exporter-servicemonitor.yaml
kubectl apply -f monitoring/argo-servicemonitor.yaml
kubectl -n monitoring get servicemonitor -o wide
# give Prometheus a moment and then check targets for mlflow
sleep 5
curl -s 'http://127.0.0.1:9090/api/v1/targets' | jq '.data.activeTargets[] | select(.discoveredLabels.__meta_kubernetes_namespace=="mlflow")' || true
```




### argo workflows のメトリクス有効化
```bash
# 1) ServiceMonitor の存在と内容確認
kubectl get servicemonitor -A
kubectl -n monitoring get servicemonitor argo-servicemonitor -o yaml

# 2) Prometheus CR の selector / namespaceSelector を確認
kubectl -n monitoring get prometheus -o name
kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o yaml | yq '.spec.serviceMonitorSelector, .spec.serviceMonitorNamespaceSelector'

# 3) Argo の Service を確認（ServiceMonitor の selector に合致するか）
kubectl -n argo get svc -o wide
kubectl -n argo get svc argo-server -o yaml

# 4) Prometheus がターゲットとして認識しているか確認（port-forward してから）
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090 &
curl -s 'http://127.0.0.1:9090/api/v1/targets' \
  | jq '.data.activeTargets[] | select(.discoveredLabels.__meta_kubernetes_namespace=="argo")'

# 代替（targets UI をブラウザで開く）
xdg-open 'http://127.0.0.1:9090/targets?search=argo'
```


### grafanaでargo workflows のメトリクスが見えない場合の確認手順
```bash
# 1) Prometheus がターゲットとして認識しているか確認（port-forward してから）
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090 &
curl -s 'http://127.0.0.1:9090/api/v1/targets' \
  | jq '.data.activeTargets[] | select(.discoveredLabels.__meta_kubernetes_namespace=="argo")'

kubectl -n monitoring get servicemonitor argo-workflows -o yaml || kubectl -n monitoring get servicemonitor -o wide | sed -n '1,200p'
 kubectl -n argo get svc argo-server -o yaml || true
 kubectl -n argo get endpoints argo-server -o yaml || true
 kubectl -n argo get pods -l app=argo-server -o wide || true
 kubectl -n argo exec -it argo-server-58f945f8b7-xmn59 -- curl -sS -D - http://127.0.0.1:2746/metrics | sed -n '1,120p'

# workflow-controller-service.yamlを作成
```
