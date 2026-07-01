# 05: Deploy do Langfuse (com MinIO obrigatório)

## NÃO use o one-click do Coolify

O template one-click declara os `LANGFUSE_S3_*` mas sobe **sem MinIO e com creds vazias**. Resultado: `POST /api/public/ingestion` dá **HTTP 500** (`Could not load credentials from any providers` → `Failed to upload events to blob storage`) e os traces **somem em silêncio**. Pior: `GET /api/public/projects` lê só o Postgres e retorna 200, então um "test connection" ingênuo **passa** e mascara a ingestion quebrada.

## Use o compose vendorado do repo

`templates/langfuse/docker-compose.coolify.yml`: topologia `langfuse` (web) + `langfuse-worker` + `postgres` + `redis` + `clickhouse` + **`minio`**, com as 3 famílias S3 (`EVENT_UPLOAD`/`MEDIA_UPLOAD`/`BATCH_EXPORT`) apontando pra `http://minio:9000` via as magic vars `SERVICE_USER_MINIO`/`SERVICE_PASSWORD_MINIO`. Deploy via `scripts/coolify.py create-service` (base64) + `set-fqdn` (abaixo). Detalhes e mapa magic-var↔env genérico: `templates/langfuse/README.md`.

## Fluxo headless-seed (você provisiona TUDO num deploy; o usuário só faz login)

Padrão oficial de headless-init do Langfuse, **validado empiricamente** (stack local com o compose deste template: o `LANGFUSE_INIT_USER` vira **OWNER** da org, o signup fica fechado desde o boot, o user semeado loga com `role:OWNER`, e as keys ingerem `207`). **Não deixe o signup aberto**: o Langfuse **não tem** o gate "primeiro-admin-depois-fecha" do Coolify/v4 (`AUTH_DISABLE_SIGNUP=true` devolve `422` sempre, sem exceção pro 1º usuário), então signup aberto seria uma janela real pra qualquer um se cadastrar na instância exposta. Semeie tudo de uma vez:

1. **Gere os valores do seed.** Um par de keys `pk-lf-…`/`sk-lf-…`, um id de org e um de projeto (strings únicas), e uma **senha forte pro usuário com um símbolo** (a política do Langfuse exige um caractere não-alfanumérico em signup/troca; o seed e o login aceitam sem, mas gere com pra robustez). O **e-mail é o do operador** (você já tem do onboarding).
2. **Semeie TUDO num deploy só** (o signup já nasce fechado: `AUTH_DISABLE_SIGNUP=true` é o default do template). Set na env do serviço (Coolify) ou no `.env` (genérico) e **deploy uma vez**:
   - `LANGFUSE_INIT_USER_EMAIL` (operador), `LANGFUSE_INIT_USER_NAME`, `LANGFUSE_INIT_USER_PASSWORD` (a senha gerada)
   - `LANGFUSE_INIT_ORG_ID`, `LANGFUSE_INIT_ORG_NAME`
   - `LANGFUSE_INIT_PROJECT_ID`, `LANGFUSE_INIT_PROJECT_NAME`, `LANGFUSE_INIT_PROJECT_PUBLIC_KEY` (`pk-lf-…`), `LANGFUSE_INIT_PROJECT_SECRET_KEY` (`sk-lf-…`)

   No boot o Langfuse cria o **usuário (OWNER da org) + org + projeto + keys**. O USER exige a ORG (por isso vão juntos); upsert **por id**, então re-deploy não duplica.
3. **Entregue o login ao operador.** A URL do Langfuse em **`/auth/sign-in`** (login, **não** signup), com o **e-mail dele + a senha gerada**; peça pra ele **trocar a senha** no 1º acesso. Ele nunca abre "Settings → API Keys" nem copia key nenhuma.

Como **você gerou** as keys no passo 1, elas já estão na sua mão pra ligar na v4 (abaixo). Um deploy, sem redeploy, sem ler `org_id` no Postgres, e o signup **nunca** ficou aberto.

## FQDN (preserve a porta)

`scripts/coolify.py set-fqdn --ssh root@<VPS_IP> --app-id <id> --fqdn https://langfuse.<seu-dominio>:3000` (ache o id com `list-apps`). O template mapeia o FQDN pra porta 3000 do container; **dropar o `:3000` quebra o routing**. Ver `gotchas.md`.

## Verifique a ingestion (health verde NÃO basta)

`scripts/langfuse-verify.py` POSTa um batch em `/api/public/ingestion` e exige **207/200** (não 500); as chaves são o par que você semeou, lidas de um arquivo `0600` (a secret key fora do argv):
```sh
echo '{"publicKey":"<pk-lf>","secretKey":"<sk-lf>"}' > langfuse.keys && chmod 600 langfuse.keys
python3 scripts/langfuse-verify.py ingestion --base-url https://langfuse.<seu-dominio>:3000 --keys-file langfuse.keys
```
Status 500 = quase sempre MinIO/S3 ausente.

## Ligue na v4 (por MCP, `langfuse_connect`)

O wiring é **por MCP**, num tool só: `langfuse_connect` recebe `public_key`/`secret_key`/`base_url` **inline** (as keys que você semeou), cria a credencial no vault **já preenchida** (`kind:"langfuse"`, `{publicKey, secretKey}` + `baseUrl`) e liga o tracing no tenant-settings. É dry-run por padrão: revise o preview (keys redigidas) e reenvie com `dry_run:false` pra aplicar. Mesmo padrão do `deployment_connect` do Chatwoot (segredo de infra inline). Como as keys já existem, a credencial nasce **preenchida** (NÃO `pending`): uma entry pending não resolve o segredo e o tenant-settings rejeita com `credential ref not found`. (No vault o campo é `baseUrl` camelCase, ver `gotchas.md`; doc do tool em `docs/mcp.md`.)
