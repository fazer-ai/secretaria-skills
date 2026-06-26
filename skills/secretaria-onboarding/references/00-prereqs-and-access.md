# 00: Pré-requisitos e acesso

## MCPs (ligar ANTES de começar; reiniciar a sessão cedo)

- **Hostinger** (3 servers via npx, stdio, `HOSTINGER_API_TOKEN`): `hostinger-dns`, `hostinger-vps`, `hostinger-domains`. DNS é o uso central (etapa 1: A-records); VPS/domains pra descoberta/gestão. **Só quando a infra é Hostinger**: em outro provider não há esses MCPs (ver "Outro provider" na `01-vps-dns-ssh.md`).
- **Hub `app-fazer-ai`** (OAuth; escopos `mcp:read`+`write`+`admin`): licenças/instâncias/registry credential do Chatwoot Pro. Use a licença do Chatwoot Pro e a registry credential da conta do usuário (`<LICENSE_ID>` / `<REGISTRY_CRED_ID>`); os limites de uso estão em `guardrails.md`.
- **v4** (OAuth): conectado SÓ na etapa 6, depois do `/setup` (antes disso a instância nem existe).
- Depois de adicionar os MCPs, **reinicie a sessão do harness** pra eles ficarem disponíveis na execução.

## Estado do CLI de onboarding (em disco, `~/.fazer-ai/`)

O CLI `@fazer-ai/secretaria` roda ANTES do handoff e deixa marcadores que você deve **ler em vez de re-perguntar**:

- **`onboarding.json`** — `{ chatwootTier: "pro" | "community", chatwootLicenseId? }`. Decide a edição do Chatwoot no deploy (ver `chatwoot-hub-register.md` e `deploy/chatwoot/README.md`). É a escolha **explícita** do operador; respeite-a (inclusive `community` = seguir sem Pro, mesmo que haja licença no hub).
- **`hostinger.json`** — `{ token }` da API Hostinger (quando o provider é Hostinger); o CLI também já o injeta nos MCPs.
- **`preferences.json`** — defaults de UX do CLI (agente/provider/última licença); informativo, não load-bearing.

Marcador ausente (fallback por token, ou outro ponto de entrada) → decida pelo hub (`list_licenses`/`whoami`).

## Acesso (fornecido pelo usuário)

- **VPS:** `root@<VPS_IP>` (no Hostinger, o id da VM é `<VPS_ID>`), com uma chave SSH utilizável (`~/.ssh/<sua-chave>`). Coolify pode já estar instalado (brownfield) ou não. Comando SSH exato na `01-vps-dns-ssh.md`.
- **Sem VPS ainda?** Sugira adquirir uma. Recomendado: Hostinger, pelo [link de parceiro fazer.ai](https://www.hostg.xyz/SHJfs) (cupom `FAZERAI` = 10% de desconto na primeira compra). Em **outro provider**, o usuário cria a VPS lá e fornece IP + chave SSH; o fluxo segue igual (ver `01-vps-dns-ssh.md`).
- **Domínio:** `<seu-dominio>`, com os subdomínios de onboarding livres pra apontar (`agentes.`, `chatwoot.`, `coolify.`, `langfuse.`).
- **Chave do provedor de modelo** (OpenAI ou outro): o usuário fornece pra preencher o vault do agente (playground/E2E). As demais credenciais entram via deeplink (pending).
- **Número de WhatsApp** que o usuário controle, se for validar o transporte real no E2E (etapa 10).

## Operacional (comandos remotos)

- Chamadas de rede via Bash (ssh/curl) precisam de `dangerouslyDisableSandbox: true`.
- Pra evitar inferno de aspas em SSH/psql/Rails runner: **base64 local → pipe → `base64 -d`** no destino. É o padrão recorrente de todo o fluxo (ex.: `echo <B64> | base64 -d | docker exec -i coolify-db psql ...`).

## Gates de conta (padrão vs operador testando)

- **Padrão (usuário real):** o usuário cria o 1º admin de Coolify/Chatwoot/v4 no browser; você só entrega link + instrução.
- **Operador testando a própria infra:** você pode criar headless. Deixe sempre explícito qual modo está rodando. Detalhe em `guardrails.md`.
