# 06: `/setup` da v4 + conectar o MCP

## `/setup` (cria o 1º admin = SUPER_ADMIN)

- Quando o banco está sem usuários, a v4 abre o `/setup`. No boot ela loga um token único e a URL pronta `${PUBLIC_URL}/setup?token=...` (a menos que `SETUP_TOKEN_REQUIRED=false`).
- O 1º admin é criado como **SUPER_ADMIN** (`tenant_id` NULL) via `POST /api/auth/setup`.
- O **usuário** abre a URL `/setup` (com o token do boot) e cria o 1º admin. Você entrega a URL e **espera**; não cria por conta própria.
- Config de boot relevante (defaults): `setupTokenRequired:true`, `signupEnabled:false`.

### O tenant nasce do `companyName` do `/setup`: confira depois

O `/setup` cria **um** tenant a partir do `companyName` que quem preenche o form digita. No **real**, é o usuário que digita: pode sair diferente do nome combinado (numa run real saiu `fazer.ai`/`fazer-ai` em vez de `Clínica Moreira`). Depois de conectar o MCP, rode **`tenant_list`** e **confira** o `name`/`slug`:
- bate com o escolhido → siga.
- divergiu → **NÃO crie outro tenant** (`tenant_create` é proibido, ver abaixo): siga com o que existe e **avise o usuário** da divergência. Renomear, se ele quiser, é `tenant_update` (não um tenant novo).

## Conectar o MCP da v4 (OAuth). GATE: sem as tools, PARE, não contorne

Toda a config da v4 (import do agente, vault, tenant-settings, KB, deployment/bind) é **exclusivamente via MCP tools**: elas carregam dry-run + audit + o fence de tenant. As tools de MCP só carregam no **boot** da sessão, e a **ordem do reinício muda por harness**: o Claude autentica na TUI (`/mcp`), que exige o server já carregado no boot, então reinicia **antes** de autenticar; Codex/Hermes autenticam por comando de CLI, então reiniciam **depois**. Endpoint da v4: `https://agentes.<seu-dominio>` (discovery/caminho exato em `docs/mcp.md`).

**Claude Code** (reinicie ANTES de autenticar):
1. **Adicione:** `claude mcp add` (transport HTTP) pro endpoint. O server entra no config, mas **não** aparece na sessão atual nem no `/mcp` (a sessão leu o config no boot).
2. **Reinicie a sessão** (feche e reabra o `claude` no mesmo dir). Só agora o `/mcp` lista `fazer-ai` como **"Needs authentication"** (esperado, não é falha).
3. **Autentique:** `/mcp` → `fazer-ai` → **Authenticate** → browser; o usuário loga com o admin do `/setup` (SUPER_ADMIN) e aprova os escopos (`mcp:read/write/admin`). Ao voltar **"Connected"**, as tools carregam **na mesma sessão, sem 2º reinício**.

**Codex / Hermes** (autentique por CLI, depois reinicie):
1. **Adicione + logue:** `codex mcp add` + `codex mcp login` (ou o equivalente do Hermes), que abre o browser pro mesmo login SUPER_ADMIN.
2. **Reinicie a sessão.** As tools carregam no boot seguinte.

O access token fica no store de MCP do harness, não conosco (`guardrails.md`).

**GATE DURO. Se as tools `fazer-ai` (`whoami`, `tenant_list`, `agent_import`, …) NÃO estão expostas nesta sessão:**

- **PARE e peça ao usuário pra completar o passo do harness dele** (Claude: **reiniciar → `/mcp` Authenticate**; Codex/Hermes: **`mcp login` → reiniciar**), confirmando o Authenticate/login **e** o reinício. Espere ele voltar. Esse é o **único** caminho.
- **NUNCA contorne.** É **proibido**, para qualquer config da v4: chamar a **API REST direto** (mintar API key, cookie + `x-tenant-id`); fazer requisições ao endpoint `/mcp` **por fora do harness**; **ler o código-fonte/bundle da v4** (`/app/src`, `/app/dist`) pra descobrir endpoints internos; montar **OAuth manual**. Esses bypasses pulam dry-run/audit/fence, são frágeis, e **não provam o MCP**, que é o produto que esta run existe pra validar.
- **Sinal de que você entrou no anti-padrão:** se você se pegou grepando `agents.controller.ts`, procurando `POST /api/v1/agents/import`, ou mintando uma API key pra "equivalente REST" porque "a tool não apareceu" → **PARE imediatamente** e peça o reinício. Não existe "fallback REST transitório" para config da v4. **Idem pra achar uma rota/deeplink do console:** não baixe+grepe o bundle da SPA; as rotas que a skill usa estão nas refs (ex.: o deeplink de credencial em `08-agent-import.md` §2), e o bundle é minificado/hasheado (frágil).

## Alvo de tenant nas MCP tools (SUPER_ADMIN)

O admin do `/setup` é **SUPER_ADMIN** (`tenant_id` NULL), então o token MCP é **fleet-level**: `whoami` mostra `tenantId: null`. Ele **não** carrega um tenant embutido; você escolhe o tenant **por chamada**:

1. Logo após conectar, rode **`tenant_list`**: há **um** tenant (o criado pelo `/setup`, a partir do `companyName`). Anote o **slug** (ou o id).
2. Em **toda tool per-tenant** (`agent_import`, `agent_*`, `vault_*`/`credential_create`, `tenant_settings_*`, `deployment_connect`/`inbox_bind`, `knowledge_*`, …) passe o argumento **`tenant`** com esse slug (ou id). O campo só aparece para tokens SUPER_ADMIN; para um token de tenant (API key) ele nem existe e o tenant é implícito.
3. **NUNCA chame `tenant_create`.** O tenant já existe (o do `/setup`); criar outro gera um tenant **órfão**, e o agente/credenciais importados cairiam no lugar errado. Se uma per-tenant tool reclamar de *"fleet-level … pass `tenant`"* ou *"no tenant target"*, a causa é **faltar o argumento `tenant`**, não faltar um tenant: rode `tenant_list` e passe o `tenant`.

## Prefixo dos paths (referência factual, NÃO um convite a usar REST)

Onde estas refs citam `/v1/...` (ex.: `/v1/vault`, `/v1/chatwoot/deployment`), o path HTTP real é `/api/v1/...`. Isto é só pra você **ler** as refs corretamente e casar com as MCP tools equivalentes; **não** é autorização pra chamar REST: a config da v4 vai por MCP (acima). A API key (`POST /api/v1/api-keys { "displayName": "..." }`, o campo é `displayName` não `name`) existe para integrações externas do usuário, não para a skill contornar o MCP.
