# secretaria-onboarding

Skill que conduz o onboarding da **Secretária V4** num VPS, do zero ao agente de
atendimento de IA: deploy por tier (Coolify / Portainer / compose genérico),
Chatwoot + Langfuse com TLS, branding, import do agente via MCP e validação ponta a
ponta (playground + WhatsApp + traces no Langfuse).

Esta é a skill **executada pelo agente**: ela opera o VPS via SSH + a API do
orquestrador escolhido e controla a Secretária V4 via MCP. Funciona em **Claude
Code**, **Codex** e **Hermes**, a partir da mesma fonte (a pasta `skills/`).

## Instalação

Normalmente você **não** roda os comandos abaixo à mão: o instalador
`npx @fazer-ai/secretaria` detecta o seu agente e faz tudo (login, MCPs, licença,
skill e handoff). Veja [app.fazer.ai](https://app.fazer.ai). Para instalar a skill
manualmente:

### Claude Code

```sh
claude plugin marketplace add fazer-ai/secretaria-onboarding
claude plugin install secretaria-onboarding@secretaria
```

### Codex

```sh
codex plugin marketplace add fazer-ai/secretaria-onboarding
codex plugin add secretaria-onboarding@secretaria
```

### Hermes

```sh
hermes skills tap add fazer-ai/secretaria-onboarding
hermes skills install secretaria-onboarding --yes
```

## Estrutura

- `skills/secretaria-onboarding/` — a skill (SKILL.md + `guardrails.md`,
  `gotchas.md`, `references/`, `scripts/` e o deploy kit: composes, `deploy/`,
  `docs/`). É a fonte que os três agentes consomem.
- `.claude-plugin/` — manifesto do marketplace + do plugin para Claude Code e Codex
  (`source: "./"`, plugin co-localizado). O Hermes ignora isto e lê direto de
  `skills/`.

O conteúdo é gerado a partir da fonte única da skill; edições devem ser feitas lá,
não neste repositório.

## Licença

Proprietária (EULA). Ver [`LICENSE`](LICENSE).
