# 02: Coolify (reusar/instalar, API, Instance Domain)

## Brownfield: reusar se já existe e está saudável

A VPS pode já vir com Coolify (brownfield). Nesse caso, reaproveite o existente: **nunca** destrua dados do usuário. O inventário brownfield completo (todos os serviços, com a matriz reusar/instalar/sinalizar) está na etapa 1b (`references/01b-brownfield.md`); aqui é só a parte do Coolify.

### Reinstalação limpa: só num recurso descartável

Para um teste do zero, reinstale: wipe do Docker + `/data/coolify` + instalador oficial do Coolify. **Só faça isso numa VPS confirmada como descartável** (`guardrails.md`); é destrutivo. Resultado esperado: instalador sai `0`, "Your instance is ready to use!", 4 containers core Up+healthy (`coolify`, `coolify-db`, `coolify-redis`, `coolify-realtime`).

## 1º admin (o ÚNICO passo do usuário no Tier A)

Real: **o usuário cria** o 1º admin pelo browser em `http://<VPS_IP>:8000` (gate de conta). Teste: você cria. **Esse é o único passo manual do Tier A.** Depois do admin, **NÃO peça mais nada ao usuário** — o token e o Instance Domain você faz por SSH (abaixo). **Nunca** mande o usuário abrir "Settings → …".

## API Access (token) — você faz por SSH, não pela UI

Dois passos, ambos por SSH, **sem o usuário** (validado E2E no Coolify 4.1.2):

**1. Habilite a API** — vem **desabilitada** por padrão; sem isto todo request dá `403 {"message":"API is disabled."}`:
```sh
docker exec coolify-db psql -U coolify -d coolify -tc "UPDATE instance_settings SET is_api_enabled = true;"
```
Pega na hora, sem restart. `allowed_ips` vazio (default) = sem restrição de origem; **não mexa** (o agente acessa de fora).

**2. Gere o token root.** O Coolify sobrescreve o `createToken` do Sanctum e exige `session('currentTeam')` (a tabela `personal_access_tokens` tem `team_id` NOT NULL) — o `createToken` cru falha com `team_id null`, então **semeie a sessão** antes. O snippet tem aspas: use o base64-pipe da `00`.
```sh
docker exec coolify php artisan tinker --execute='$u = App\Models\User::first(); session(["currentTeam" => $u->teams()->first()]); echo $u->createToken("fazer-ai-onboarding", ["*"])->plainTextToken;'
```
A saída `<id>|<token>` é o Bearer (ability `*` = root). Guarde transitoriamente (scratchpad), **nunca** em repo/log/commit.
- Base da API: `http://<VPS_IP>:8000/api/v1`, header `Authorization: Bearer <token>`. Valide: `GET /api/v1/servers` → 200.

## Instance Domain — você seta por SSH (cosmético: NÃO bloqueia o deploy)

Só troca o acesso ao **painel** de `http://<VPS_IP>:8000` para `https://coolify.<seu-dominio>` (TLS). **O deploy não depende disto** (API e serviços rodam pelo IP cru), então é polimento: faça por SSH, sem o usuário, e **não trave** o onboarding se falhar. Exige o A-record `coolify.` (etapa 1). Validado E2E (Coolify 4.1.2):
```sh
docker exec coolify-db psql -U coolify -d coolify -tc "UPDATE instance_settings SET fqdn='https://coolify.<seu-dominio>';"
docker restart coolify
```
O `UPDATE` **sozinho não regenera** o proxy; é o **`restart coolify`** (o app, **NÃO** `coolify-proxy`) que reescreve `/data/coolify/proxy/dynamic/coolify.yaml` com a rota `Host(coolify.<seu-dominio>)`. Derruba painel+API ~30-40s (o token já gerado **sobrevive**; faça este passo logo após o token ou por último, nunca no meio de uma chamada à API). Depois **valide**:
```sh
curl -so /dev/null -w "%{http_code} ssl=%{ssl_verify_result}\n" https://coolify.<seu-dominio>
```
→ `200`/`302` com `ssl=0` (cert válido; o ACME emite quando o A-record resolve).

## DB do Coolify (acesso direto; ver gotchas)

```sh
docker exec -i coolify-db psql -U coolify -d coolify
```

## Projeto + ambiente

Crie (ou reaproveite) um projeto com o **nome de exibição do usuário** (ex.: `clinica-moreira`) e o ambiente `production`. Os UUIDs (server/projeto/env/serviços) são **gerados a cada instalação**: descubra-os pela API/DB; nunca chumbe UUIDs de outra instalação.

## Registry privado do Harbor (só Pro)

Imagens **Pro** (Chatwoot `chatwoot-pro`; Secretária V4 no projeto `secretaria`) são privadas no Harbor: o Coolify precisa da credencial registrada **antes** de puxar, senão o deploy falha (pull denied / 401). Só no caminho Pro:

1. Pegue a credencial **per-user** no hub MCP `app-fazer-ai` (`create_registry_credential`, **sem** `license_id`; dry-run → apply com OK). Uma robot cobre todos os projetos Pro do usuário (Chatwoot + Secretária).
2. Registre no Coolify (Servers → Registries, ou via API) apontando pra `harbor.fazer.ai` com o `username`/`secret`. **Nunca** logue o secret.

No caminho **OSS** (imagem pública), pule isto inteiro.
