# Guardrails: fronteiras que NÃO se cruzam

Valem em qualquer execução desta skill. Cruzar qualquer uma é **parar e perguntar**.

## Escopo de operação

- **Opere SÓ na infraestrutura que o usuário forneceu e autorizou para este onboarding:** a VPS indicada (`<VPS_IP>`), o domínio indicado (`<seu-dominio>`), e a licença + registry credential do Chatwoot Pro indicadas (`<LICENSE_ID>` / `<REGISTRY_CRED_ID>`). Tudo isso é dado de entrada; as refs usam placeholders.
- **Nunca toque em outras VPS, domínios, instâncias ou licenças da conta do usuário.** A mesma conta (provedor de VPS, DNS, hub `app-fazer-ai`) pode hospedar **produção de terceiros**. Uma write tool errada derruba o serviço de outro cliente, e o token do hub costuma ter `mcp:admin`. Antes de qualquer write no hub (ou ação destrutiva na VPS), **confirme que o alvo é o recurso certo**; na dúvida, pare e pergunte.
- **Ações destrutivas** (recreate/stop/restart/firewall/reset de VPS, reinstalar Coolify, wipe de volume) **só com OK explícito** e só no recurso confirmado como descartável. Em brownfield (VPS já populada), **nunca** destrua dados do usuário: detecte e reaproveite.

## Produção e mutações

- **Nunca** modificar produção a menos que o usuário peça aquela mudança específica. Autorização a um objetivo não é autorização para tocar produção nem para escolher o método.
- **Nunca** editar o DB de produção direto para mudar estado de aplicação: usar a UI/API da própria app. (Durante o provisionamento inicial, antes da app estar no ar, mexer no DB/console via `psql`/Rails runner é aceitável e transitório; uma vez em produção, use a UI/API.)
- **Writes do hub** (via proxy `bunx @fazer-ai/secretaria hub …`) e **write tools de MCP** são **dry-run por padrão**. Aplicar (`--apply` / `dry_run:false`) só com OK explícito do usuário para aquela ação.

## Segredos

- **Nenhum segredo em repo, log, commit ou arquivo plano.** Cada segredo vive no destino final: env do serviço no Coolify / DB do Chatwoot / **vault da v4** / store de MCP do harness (o token da v4 fica no harness do agente).
- **Nunca `cat`/imprima arquivos de credencial locais** do CLI/agente: `~/.fazer-ai/oauth.json` (refresh token do hub), `*.token`, `*.keys.json`, `/root/.docker/config.json`. Para checar presença, teste só a existência (`Test-Path` / `[ -f … ]`) ou um `grep -q` **sem** imprimir o conteúdo; despejar o arquivo no output coloca o segredo no transcript (que persiste em disco). Mesma regra dos logs: redija (`sed -E 's/(token=|password=|secret=)[^ ]+/\1[REDACTED]/'`) antes de mostrar.
- Segredos de infra usados pelo agente são **buscados transitoriamente** no momento do uso (token do Chatwoot via Rails runner, senha do Coolify-db via env do container), nunca persistidos em disco.
- Credenciais do **usuário** (OpenAI/ElevenLabs/Gemini/Asaas) entram como **pending + deeplink**: o usuário preenche no console; nunca passam pelo agente.

## Gates de criação de conta

- O **usuário** cria o 1º admin no browser do orquestrador (Coolify/Portainer), do Chatwoot e da v4 (`/setup`). O agente **entrega o link + a instrução e espera** o usuário criar; **nunca** cria essas contas por conta própria (não há atalho: nada de CLI/console/auto-seed criando esses admins). Na v4, a URL `/setup` com o token impresso no boot. Depois da conta criada, o agente segue (obtém o token via Rails runner transitório, deploy, config).
- **Exceção: o Langfuse** é provisionado **headless** (`LANGFUSE_INIT_*`, etapa 5): o agente semeia usuário (OWNER) + org + projeto + keys num deploy só, com signup fechado desde o boot. O usuário **não cria conta** lá, só faz **login** na conta semeada (`/auth/sign-in`) e troca a senha. É o padrão oficial do Langfuse e evita a janela de signup aberto (o Langfuse não tem o gate primeiro-admin-depois-fecha do Coolify/v4).

## Estilo

- PT-BR com acentuação correta. Nada de em-dash (use vírgula/ponto/dois-pontos). `fazer.ai` sempre minúsculo (slugs `fazer-ai` ok).
