# 06: `/setup` da v4 + conectar o MCP

## `/setup` (cria o 1º admin = SUPER_ADMIN)

- Quando o banco está sem usuários, a v4 abre o `/setup`. No boot ela loga um token único e a URL pronta `${PUBLIC_URL}/setup?token=...` (a menos que `SETUP_TOKEN_REQUIRED=false`).
- O 1º admin é criado como **SUPER_ADMIN** (`tenant_id` NULL) via `POST /api/auth/setup`. É exatamente o role que o branding (fleet-level) e as MCP tools `mcp:admin` exigem.
- **Real:** o usuário abre a URL e cria. **Teste:** você cria (headless), pegando o token do log de boot.
- Config de boot relevante (defaults): `setupTokenRequired:true`, `signupEnabled:false`.

## Conectar o MCP da v4 (OAuth)

- Claude Code: `claude mcp add` apontando pro endpoint MCP da v4 em `https://agentes.<seu-dominio>` (caminho/discovery em `docs/mcp.md`). O usuário libera o **OAuth** uma vez; daí pra frente a config da v4 é **via MCP** (dry-run + audit).
- O access token da v4 fica no store de MCP do harness, não conosco (`guardrails.md`).
- Se o MCP não aparecer na sessão, reinicie o harness.

## Chave de API (fallback transitório)

- Algumas chamadas REST diretas (TENANT_ADMIN) usam uma API key (`Authorization: Bearer <v4-api-key>`); as duas de deployment (SUPER_ADMIN) usam cookie de sessão + header `x-tenant-id`.
- Mintar a API key: `POST /api/v1/api-keys { "displayName": "..." }` (o campo é `displayName`, NÃO `name` → 422; o `token` aparece só uma vez).
- **Prefixo dos paths REST:** tudo monta sob `/api`. Onde estas refs abreviam `/v1/...` (ex.: `/v1/vault`, `/v1/chatwoot/deployment`, `/v1/knowledge/...`), o path HTTP real é `/api/v1/...` (ex.: `POST /api/v1/vault`). Em curl/fetch use sempre o `/api`.
- No fluxo **MCP-first**, prefira as MCP tools; a API key/cookie é fallback quando não há tool equivalente.
