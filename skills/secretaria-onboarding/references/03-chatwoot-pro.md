# 03: Deploy do Chatwoot (Pro ou OSS)

## Primeiro: leia o marcador e ramifique (Pro vs OSS)

Leia `~/.fazer-ai/onboarding.json` → `chatwootTier`. Eixo **independente** da edição da Secretária V4 (`secretariaEdition`, etapa 4). Marcador ausente → fallback pelo hub (`list_licenses`): licença CHATWOOT disponível → Pro; senão OSS.

- **`community` (OSS)** → imagem **pública** `ghcr.io/fazer-ai/chatwoot:latest` (nosso fork), `COMPOSE_PROFILES` vazio (sem `baileys-api`). **NÃO** rode `docker login` nem `generate_install_script` (não há licença e o pull é público). Deploy pelo compose genérico (`deploy/chatwoot/`, ver `deploy/chatwoot/README.md`); no Coolify, setar `CHATWOOT_IMAGE=ghcr.io/fazer-ai/chatwoot:latest` no `docker-compose.coolify.yml` e **remover** o `baileys-api`. **Pule a etapa 9b** (licenciar). O resto deste doc é **só Pro**.
- **`pro`** → siga abaixo (Harbor + Coolify API + `docker login` + etapa 9b).

## Imagem privada (Harbor): use a licença/cred do usuário

`harbor.fazer.ai/chatwoot/fazer-ai/chatwoot-pro:latest`.
- Hub MCP: `generate_install_script` na licença do Chatwoot Pro (`<LICENSE_ID>`) → retorna `curlCommand` + `dockerLoginCommand` (login no Harbor com a robot account). Aplicar (`dry_run:false`) só com OK do usuário. **Nunca** logar o secret do Harbor.
- Dele se **extrai o compose** (heredoc `COMPOSE_EOF`).

## Deploy via API do Coolify

O `scripts/coolify.py create-service` lê o compose, faz o **base64** (raw → 422 "should be base64 encoded") e POSTa em `/api/v1/services` com `instant_deploy:false`; depois você deploya:
```sh
python3 scripts/coolify.py create-service --base-url http://<VPS_IP>:8000 --token-file coolify.token \
  --name chatwoot --project-uuid <PROJ_UUID> --server-uuid <SRV_UUID> --environment-name production \
  --compose-file deploy/chatwoot/docker-compose.coolify.yml   # → {uuid}
python3 scripts/coolify.py api-post --base-url http://<VPS_IP>:8000 --token-file coolify.token --path /services/<uuid>/start
```
- Logue no Harbor com `scripts/harbor-login.py login` **antes** do `start` (o pull da privada precisa do login): roda `docker login --password-stdin` por SSH (secret fora do argv) e protege o `$` do usuário robot. `username`/`secret` vêm do `generate_install_script`; grave o secret num arquivo `0600`:
```sh
python3 scripts/harbor-login.py login --ssh root@<VPS_IP> --username '<robot-user>' --secret-file harbor.secret
```

## Admin + conta + token (Rails runner via SSH)

`scripts/chatwoot-admin.py provision` roda o Rails runner **dentro** do container (base64-piped por SSH, então o nome com acento/espaço e as aspas do script não tocam o shell), idempotente (`find_or_create` de account/user/token). A **senha é gerada no container** (SecureRandom): nenhum segredo entra por argv.
```sh
python3 scripts/chatwoot-admin.py provision --ssh root@<VPS_IP> --container <chatwoot-rails-container> \
  --account-name 'Clínica Moreira' --email <email-do-admin> --out chatwoot-admin.json
```
Grava `api_access_token` (+ a senha, se o user nasceu agora) num arquivo `0600`; só metadados são impressos. Esse `api_access_token` vai no header `api-access-token: <token>` (hífen: sobrevive a proxies, ver `deploy-b-portainer.md`) das chamadas REST do Chatwoot **e** no `deployment_connect` da etapa 9 (transitório, nunca persistido em repo/log).

## FQDN + 503

Ver `gotchas.md`: setar `service_applications.fqdn` no `coolify-db` + restart (o `SERVICE_FQDN_*` env **não** dirige o Traefik).

## Inbox API (pro E2E)

`POST https://chatwoot.<seu-dominio>/api/v1/accounts/1/inboxes` (header `api_access_token`) body:
```json
{"name":"Atendimento (teste)","channel":{"type":"api","webhook_url":""}}
```
→ inbox `Channel::Api`. O bind do agente (etapa 9) provisiona o webhook do bot; **não** precisa setar `webhook_url` à mão.
