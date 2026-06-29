# 04: Deploy da Secretária V4

## Edição: Free ou Pro (lê o marcador PRIMEIRO)

Leia `~/.fazer-ai/onboarding.json` → `secretariaEdition` (`free` | `pro`; ausente = `free`). É a escolha **explícita** do CLI; respeite-a. Eixo **independente** do `chatwootTier` (etapa 3).

- **`free`** → imagem **pública** (default do compose). **Sem** `docker login`, não seta `SECRETARIA_V4_IMAGE`. (Hoje o default é o placeholder `ghcr.io/fazer-ai/secretaria-free:latest` — a imagem pública Free ainda não foi publicada.)
- **`pro`** → imagem **privada** no Harbor: `harbor.fazer.ai/secretaria/fazer-ai/secretaria-v4:latest`. Provisione a credencial **per-user** no hub MCP `app-fazer-ai` (`create_registry_credential`, **sem** `license_id`; dry-run → apply com OK), logue com `scripts/harbor-login.py login` (secret via `--secret-file`, stdin; protege o `$` do robot), e setar `SECRETARIA_V4_IMAGE` pra esse path. **Nunca** logar o secret.
  - **Reuso (per-user):** se o Chatwoot também for Pro (etapa 3), é o **mesmo** `docker login`, não logar duas vezes.
  - **Tier A (Coolify):** setar a env `SECRETARIA_V4_IMAGE` no serviço + registrar a Harbor registry credential no Coolify (igual ao Chatwoot Pro).
  - **Tier B/C (compose):** `export SECRETARIA_V4_IMAGE=<imagem>` (ou no `.env`) antes do `docker compose up`.

## Compose

Use o `docker-compose.coolify.yml` do repo via `scripts/coolify.py create-service` (lê o compose, base64-encoda, POSTa em `/api/v1/services`). Topologia: `secretaria-v4` (imagem conforme a **edição** acima; o compose default é a Free) + `postgres` (`pgvector/pgvector:pg17`: NÃO postgres puro: o schema precisa de `CREATE EXTENSION vector`). Volume `storage:/app/storage`. Healthcheck `wget -qO- http://localhost:3000/api/health`.

## Magic vars (Coolify gera; NÃO setar à mão)

- `SERVICE_URL_SECRETARIA_V4` → `PUBLIC_URL` e `CDN_URL`.
- `SERVICE_USER_DBUSER` / `SERVICE_PASSWORD_64_DBPASSWORD` → **superuser** (dono do Postgres) → `MIGRATION_DATABASE_URL`.
- `SERVICE_USER_APPDBUSER` / `SERVICE_PASSWORD_64_APPDBPASSWORD` → **app role** (não-superuser) → `DATABASE_URL` + `LANGGRAPH_DATABASE_URL`.
- `SERVICE_PASSWORD_64_JWTSECRET` → `JWT_SECRET`; `SERVICE_PASSWORD_64_ENCRYPTIONKEY` → `ENCRYPTION_KEY`.

## Persistência de branding/quotes (fix: já no compose)

```
BRANDING_STORAGE_DIR=/app/storage/branding
QUOTES_STORAGE_DIR=/app/storage/quotes
```
Sem isso caem em `./data/*` (FS efêmero do container) e logo/favicon (+ PDFs de quote) somem no redeploy. Já corrigido no `docker-compose.coolify.yml`; **confira que está lá** antes da etapa 7 (branding).

## Boot = CMD da imagem (NÃO sobrescrever `command`)

A sequência `bootstrap → migrate deploy → serve` é o CMD do Dockerfile. **Não** declare `command:` no compose (sobrescrever crash-loopa). Detalhe em `gotchas.md`.

## FQDN + 503 + verificação

O `SERVICE_FQDN_*` não dirige o Traefik; quem roteia é a linha em `service_applications` (ver `gotchas.md`). Ache o id e seta o FQDN:
```sh
python3 scripts/coolify.py list-apps --ssh root@<VPS_IP>            # ache o id do secretaria-v4
python3 scripts/coolify.py set-fqdn  --ssh root@<VPS_IP> --app-id <id> --fqdn https://agentes.<seu-dominio>
python3 scripts/coolify.py api-post  --base-url http://<VPS_IP>:8000 --token-file coolify.token --path /services/<uuid>/restart
```
Antes do DNS resolver, verifique o routing por sslip.io: `curl http://secretaria_v4-<service-uuid>.<VPS_IP>.sslip.io/api/health`. Depois do `/setup` (etapa 6) o app responde em `https://agentes.<seu-dominio>`.
