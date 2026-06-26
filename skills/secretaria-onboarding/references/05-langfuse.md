# 05: Deploy do Langfuse (com MinIO obrigatório)

## NÃO use o one-click do Coolify

O template one-click declara os `LANGFUSE_S3_*` mas sobe **sem MinIO e com creds vazias**. Resultado: `POST /api/public/ingestion` dá **HTTP 500** (`Could not load credentials from any providers` → `Failed to upload events to blob storage`) e os traces **somem em silêncio**. Pior: `GET /api/public/projects` lê só o Postgres e retorna 200, então um "test connection" ingênuo **passa** e mascara a ingestion quebrada. **Não é bug da v4** (o handler dela monta, enfileira e POSTa correto).

## Use o compose vendorado do repo

`deploy/langfuse/docker-compose.coolify.yml`: topologia `langfuse` (web) + `langfuse-worker` + `postgres` + `redis` + `clickhouse` + **`minio`**, com as 3 famílias S3 (`EVENT_UPLOAD`/`MEDIA_UPLOAD`/`BATCH_EXPORT`) apontando pra `http://minio:9000` via as magic vars `SERVICE_USER_MINIO`/`SERVICE_PASSWORD_MINIO`. Deploy via `POST /api/v1/services` (base64) e set Domain.
- Org/projeto via `LANGFUSE_INIT_ORG_NAME`/`LANGFUSE_INIT_PROJECT_NAME` (nome do usuário).
- Semeie `LANGFUSE_INIT_PROJECT_PUBLIC_KEY`/`LANGFUSE_INIT_PROJECT_SECRET_KEY` pra já nascer com um par de API keys (o one-click cria org/projeto/usuário mas NÃO cria chave).
- Detalhes e mapa magic-var↔env genérico: `deploy/langfuse/README.md`.

## FQDN (preserve a porta)

`service_applications.fqdn = https://langfuse.<seu-dominio>:3000` (o template mapeia o FQDN pra porta 3000 do container; dropar o `:3000` quebra o routing). Ver `gotchas.md`.

## Verifique a ingestion (health verde NÃO basta)

```sh
PK=<pk-lf>; SK=<sk-lf>; BASE=https://langfuse.<seu-dominio>:3000
curl -s -u "$PK:$SK" -H 'Content-Type: application/json' -X POST "$BASE/api/public/ingestion" \
  -d '{"batch":[{"id":"t1","type":"trace-create","timestamp":"2026-01-01T00:00:00.000Z","body":{"id":"verify-1","name":"verify"}}]}' \
  -w '\n[http %{http_code}]\n'
```
Espere **207/200**, não 500. O wiring na v4 é a etapa 8/10: `POST /v1/vault {name, kind:"langfuse", value:{publicKey, secretKey}, baseUrl:"https://..."}` (atenção: no vault o campo é `baseUrl` camelCase, ver `gotchas.md`) + `PUT /v1/tenant-settings/langfuse {enabled:true, credentialRef:"vault:<id>"}`.
