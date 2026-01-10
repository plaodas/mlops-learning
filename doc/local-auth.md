# ローカル向け：Argo 認証を一時的に無効化する手順

このドキュメントはローカル学習用途向けです。公開環境では絶対に実行しないでください。

## 認証を無効化（例）
Argo Server の起動引数を変更して SSO/クライアント認証を無効化します。

```bash
# Argo Server を認証なし（client 認証無効）で起動
kubectl patch deployment argo-server -n argo --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/args","value":["server","--auth-mode=server"]}]'
kubectl rollout status deployment/argo-server -n argo
```

ログに `You are running without client authentication` が表示されれば認証が無効化されています。

## 動作確認
```bash
# 自己署名証明書のため -k を付ける
curl -v -k --resolve "argo.local:443:127.0.0.1" "https://argo.local/api/v1/info" -i
```

`200 OK` が返れば Argo API にアクセス可能です。

## 元に戻す（ロールバック）
```bash
# 引数を元に戻す
kubectl patch deployment argo-server -n argo --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/args","value":["server"]}]'
kubectl rollout status deployment/argo-server -n argo

# 必要なら oauth2-proxy 用の Ingress/Service を再作成
kubectl apply -f argo/oauth2-ingress.yaml -n argo || true
kubectl apply -f argo/oauth2-proxy-mock.yaml -n argo || true
```

## 注意
- 本手順はローカル学習専用です。公開サービスや共有クラスターでは認証を無効化しないでください。
- 認証情報や証明書の取り扱いには注意してください。
