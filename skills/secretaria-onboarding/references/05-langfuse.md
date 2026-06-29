# 05: Deploy do Langfuse (com MinIO obrigatório)

## NÃO use o one-click do Coolify

O template one-click declara os `LANGFUSE_S3_*` mas sobe **sem MinIO e com creds vazias**. Resultado: `POST /api/public/ingestion` dá **HTTP 500** (`Could not load credentials from any providers` → `Failed to upload events to blob storage`) e os traces **somem em silêncio**. Pior: `GET /api/public/projects` lê só o Postgres e retorna 200, então um "test connection" ingênuo **passa** e mascara a ingestion quebrada.

## Use o compose vendorado do repo

`deploy/langfuse/docker-compose.coolify.yml`: topologia `langfuse` (web) + `langfuse-worker` + `postgres` + `redis` + `clickhouse` + **`minio`**, com as 3 famílias S3 (`EVENT_UPLOAD`/`MEDIA_UPLOAD`/`BATCH_EXPORT`) apontando pra `http://minio:9000` via as magic vars `SERVICE_USER_MINIO`/`SERVICE_PASSWORD_MINIO`. Deploy via `scripts/coolify.py create-service` (base64) + `set-fqdn` (abaixo).
- Org/projeto via `LANGFUSE_INIT_ORG_NAME`/`LANGFUSE_INIT_PROJECT_NAME` (nome do usuário).
- Semeie `LANGFUSE_INIT_PROJECT_PUBLIC_KEY`/`LANGFUSE_INIT_PROJECT_SECRET_KEY` pra já nascer com um par de API keys (o one-click cria org/projeto/usuário mas NÃO cria chave).
- Detalhes e mapa magic-var↔env genérico: `deploy/langfuse/README.md`.

## FQDN (preserve a porta)

`scripts/coolify.py set-fqdn --ssh root@<VPS_IP> --app-id <id> --fqdn https://langfuse.<seu-dominio>:3000` (ache o id com `list-apps`). O template mapeia o FQDN pra porta 3000 do container; **dropar o `:3000` quebra o routing**. Ver `gotchas.md`.

## Verifique a ingestion (health verde NÃO basta)

`scripts/langfuse-verify.py` POSTa um batch em `/api/public/ingestion` e exige **207/200** (não 500); as chaves vêm de um arquivo `0600` (a secret key fora do argv):
```sh
echo '{"publicKey":"<pk-lf>","secretKey":"<sk-lf>"}' > langfuse.keys && chmod 600 langfuse.keys
python3 scripts/langfuse-verify.py ingestion --base-url https://langfuse.<seu-dominio>:3000 --keys-file langfuse.keys
```
Status 500 = quase sempre MinIO/S3 ausente. O wiring na v4 é a etapa 8/10: `POST /v1/vault {name, kind:"langfuse", value:{publicKey, secretKey}, baseUrl:"https://..."}` (atenção: no vault o campo é `baseUrl` camelCase, ver `gotchas.md`) + `PUT /v1/tenant-settings/langfuse {enabled:true, credentialRef:"vault:<id>"}`.
