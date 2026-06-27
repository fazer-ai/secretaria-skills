# 03: Deploy do Chatwoot (Pro ou OSS)

## Primeiro: leia o marcador e ramifique (Pro vs OSS)

Leia `~/.fazer-ai/onboarding.json` → `chatwootTier`. Eixo **independente** da edição da Secretária V4 (`secretariaEdition`, etapa 4). Marcador ausente → fallback pelo hub (`list_licenses`): licença CHATWOOT disponível → Pro; senão OSS.

- **`community` (OSS)** → imagem **pública** `ghcr.io/fazer-ai/chatwoot:latest` (nosso fork), `COMPOSE_PROFILES` vazio (sem `baileys-api`). **NÃO** rode `docker login` nem `generate_install_script` (não há licença e o pull é público). Deploy pelo compose genérico (`deploy/chatwoot/`, ver `deploy/chatwoot/README.md`); no Coolify, setar `CHATWOOT_IMAGE=ghcr.io/fazer-ai/chatwoot:latest` no `docker-compose.coolify.yml` e **remover** o `baileys-api`. **Pule a etapa 9b** (licenciar). O resto deste doc é **só Pro**.
- **`pro`** → siga abaixo (Harbor + Coolify API + `docker login` + etapa 9b).

## Imagem privada (Harbor): use a licença/cred do usuário

`harbor.fazer.ai/chatwoot/fazer-ai/chatwoot-pro:latest`.
- Hub MCP: `generate_install_script` na licença do Chatwoot Pro (`<LICENSE_ID>`) → retorna `curlCommand` + `dockerLoginCommand` (login no Harbor com a robot account). Aplicar (`dry_run:false`) só com OK do usuário. **Nunca** logar o secret do Harbor.
- O install script é um gerenciador Coolify-aware (~1200 linhas). Dele se **extrai o compose** (heredoc `COMPOSE_EOF`).

## Deploy via API do Coolify

`POST http://<VPS_IP>:8000/api/v1/services` com `docker_compose_raw` **base64** (raw → 422 "should be base64 encoded"). `instant_deploy:false` na criação; deploya depois.
- Faça `docker login harbor.fazer.ai` na VPS (o `dockerLoginCommand`) antes do pull da imagem privada.

## Admin + conta + token (Rails runner, base64-piped via SSH)

Rode dentro do container do Chatwoot: `docker exec -i <container> bundle exec rails runner -` com o script base64-decodificado. Script (senha vem do scratchpad, NUNCA daqui):
```ruby
acc = Account.find_or_create_by!(name: 'Clínica Moreira')                      # → id 1
u = User.find_or_initialize_by(email: '<email-do-admin>')
u.password = <senha-admin>; u.confirmed_at = Time.current; u.save!
AccountUser.find_or_create_by!(account_id: acc.id, user_id: u.id).update!(role: 1)  # admin
tok = u.access_token || u.create_access_token                                   # api_access_token do admin
```
O `api_access_token` resultante é usado como header `api_access_token: <token>` nas chamadas REST do Chatwoot (transitório, nunca persistido).

## FQDN + 503

Ver `gotchas.md`: setar `service_applications.fqdn` no `coolify-db` + restart (o `SERVICE_FQDN_*` env **não** dirige o Traefik).

## Inbox API (pro E2E)

`POST https://chatwoot.<seu-dominio>/api/v1/accounts/1/inboxes` (header `api_access_token`) body:
```json
{"name":"Atendimento (teste)","channel":{"type":"api","webhook_url":""}}
```
→ inbox `Channel::Api`. O bind do agente (etapa 9) provisiona o webhook do bot; **não** precisa setar `webhook_url` à mão.
