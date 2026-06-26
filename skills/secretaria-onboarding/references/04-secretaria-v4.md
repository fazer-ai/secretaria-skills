# 04: Deploy da Secretária V4

## Compose

Use o `docker-compose.coolify.yml` do repo (`POST /api/v1/services`, `docker_compose_raw` base64). Topologia: `secretaria-v4` (`ghcr.io/fazer-ai/secretaria-v4:latest`) + `postgres` (`pgvector/pgvector:pg17`: NÃO postgres puro: o schema precisa de `CREATE EXTENSION vector`). Volume `storage:/app/storage`. Healthcheck `wget -qO- http://localhost:3000/api/health`.

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

## Duas roles (por design, com fail-fast)

Superuser roda `scripts/db-bootstrap.ts` (cria a app role NON-superuser/NOBYPASSRLS, extensão `vector`, schema `langgraph`) + `prisma migrate deploy`. A app role é a runtime, com RLS por tenant. O boot **falha rápido** se a runtime role for superuser (`assertRuntimeRoleIsNotSuperuser`; escape de dev `ALLOW_SUPERUSER_RUNTIME`).

## Boot = CMD da imagem (NÃO sobrescrever `command`)

A sequência `bootstrap → migrate deploy → serve` é o CMD do Dockerfile. **Não** adicione `command:` no compose: já derivou pra um `./server` obsoleto (era da era `bun build --compile`) e crash-loopou com `exec: ./server: not found`.

## FQDN + 503 + verificação

Ver `gotchas.md` (FQDN-via-psql). Antes do DNS resolver, verifique o routing por sslip.io:
```sh
curl http://secretaria_v4-<service-uuid>.<VPS_IP>.sslip.io/api/health
```
Depois do `/setup` (etapa 6) o app responde em `https://agentes.<seu-dominio>`.
