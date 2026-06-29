---
name: secretaria-onboarding
description: "Conduz a jornada de onboarding 'do zero ao agente de atendimento' da Secretária V4 num VPS, escolhendo o orquestrador de deploy (Tier A Coolify, B Portainer, C compose genérico para VM crua ou qualquer painel). Provisiona DNS/SSH pelo MCP Hostinger, faz deploy de Chatwoot + Secretária V4 + Langfuse com TLS, roda o /setup, configura branding e importa o agente via MCP, pluga o Agent Bot do Chatwoot e valida ponta a ponta (playground + WhatsApp + traces no Langfuse). Use quando o usuário quiser subir/onboardar uma instância nova da Secretária V4 a partir do zero num VPS, em qualquer um desses orquestradores."
---

# Onboarding Secretária V4: do zero ao agente (multi-plataforma)

Leva uma VPS de "nada" até "agente de atendimento de IA rodando, testado e plugado numa caixa de entrada real". Esta skill é o **bundle executado pelo agente** (você): opera o VPS via SSH + a API do orquestrador escolhido (Coolify / Portainer / compose genérico), e controla a Secretária V4 via **MCP** (OAuth, dry-run + audit).

## Antes de qualquer coisa

1. **Leia [`guardrails.md`](guardrails.md) inteiro.** Tem fronteiras duras (VPS única de teste, licença única do hub, MCP dry-run, nada de produção, nada de segredo em log). Cruzar qualquer uma é parar e perguntar.
2. **Leia [`gotchas.md`](gotchas.md).** São as armadilhas conhecidas que, se ignoradas, fazem você redescobrir do jeito difícil (FQDN que não dirige o Traefik, embedding por-tenant, Langfuse sem blob storage, persistência de branding etc.).
3. Confira pré-requisitos em [`references/00-prereqs-and-access.md`](references/00-prereqs-and-access.md): MCPs ligados (Hostinger ×3 + hub `app-fazer-ai`), acesso SSH, e o contrato do ambiente de teste.

## Como operar (princípios)

- **Uma pergunta de cada vez, pela ferramenta de pergunta estruturada (NUNCA um questionário em texto):** quando o agente tiver uma ferramenta de pergunta multiple-choice — **Claude Code: `AskUserQuestion`; Hermes: `clarify`** (setas + opções) — **use-a, uma pergunta por mensagem**. Sem ela (Codex/genérico), pergunte em texto, ainda **1-2 itens por vez** (só junte 2 se correlatos, ex.: IP do VPS + caminho da chave SSH). Pergunte na ordem do fluxo, só quando a etapa precisar; **espere a resposta** antes de avançar. Despejar 5-6 campos numa mensagem é o anti-padrão.
- **Leia o que o CLI já entregou — NUNCA re-pergunte o que já foi decidido:** antes de perguntar qualquer coisa, cheque o contexto que o CLI deixou: (1) os **MCPs conectados** — se `hostinger-dns`/`hostinger-vps`/`hostinger-domains` estão presentes, o **provider JÁ é Hostinger** (escolhido no CLI); use-os, nunca pergunte "se for Hostinger"; (2) o marcador **`~/.fazer-ai/onboarding.json`** (`chatwootTier` + `chatwootLicenseId` já escolhidos, ver [`references/00-prereqs-and-access.md`](references/00-prereqs-and-access.md)). Re-perguntar provider/tier/licença já definidos é erro.
- **Listar NÃO é escolher — input do usuário você SEMPRE pergunta:** separe três categorias e trate cada uma certo. **(a) Decidido pelo CLI** (provider/tier/licença) → não re-pergunte (acima). **(b) Sondável tecnicamente** (há acesso SSH? qual orquestrador já está instalado? o A-record propagou?) → sonde, não pergunte. **(c) Escolha do usuário** — **qual VPS, qual domínio raiz, nome de exibição, quais credenciais**: **SEMPRE pergunte**, e **mesmo (especialmente) quando o MCP lista várias opções, apresente-as e deixe o usuário escolher — NUNCA infira nem chute**. Ter o MCP da conta conectado é pra você **listar e perguntar melhor**, não pra decidir pelo usuário; escolher uma VPS/um domínio por conta própria ("só tinha que escolher uma") é **erro**: pare e pergunte. Autonomia é nos **passos técnicos** (deploy, config, comandos), nunca nos **inputs** do usuário.
- **Deploy por tier, espinha compartilhada:** o *deploy* (subir Chatwoot + v4 + Langfuse com TLS) muda por orquestrador; depois dele, a espinha (etapas 6-10: `/setup` → MCP → branding → import → bind → E2E) é **idêntica** em qualquer tier. A etapa 1c escolhe o tier e fixa o **contrato** que o deploy entrega à espinha.
- **MCP-first** para tudo que é config da v4 (branding, import, vault, plugar Chatwoot). SSH/psql/Rails runner só para infra (orquestrador, Chatwoot internals) e de forma **transitória**.
- **Idempotência / brownfield:** a VPS pode já ter um orquestrador (Coolify, Portainer, ou outro painel) e/ou outros serviços, em qualquer combinação. Antes de instalar, **sonde e decida por serviço** (etapa 1b, [`references/01b-brownfield.md`](references/01b-brownfield.md)): reaproveite o que está saudável, **nunca destrua** dados do usuário.
- **Nomes nunca hardcoded:** o nome de exibição/projeto vem do usuário (passo 1) e alimenta o projeto do orquestrador, a org/projeto do Langfuse e o branding da v4.
- **Dry-run primeiro:** toda write tool de MCP previewa; só aplica com `dry_run:false` após OK.

## A jornada (ordem importa)

Abra a referência da etapa **antes** de executá-la (carga sob demanda). O fluxo é **0 → 1 → 1b → 1c**, então o **deploy do tier** escolhido em 1c (Tier A = etapas 2-5; B/C = o doc do tier), convergindo na **espinha 6-10** (igual em todos). As trilhas A (Coolify) e B (Portainer) são as maduras; a C (compose genérico) é mais nova, então trate-a como primeira run guiada (ver [`references/01c-pick-tier.md`](references/01c-pick-tier.md)).

| # | Etapa | Referência |
|---|-------|-----------|
| 0 | Pré-requisitos, MCPs, acesso | [`references/00-prereqs-and-access.md`](references/00-prereqs-and-access.md) |
| 1 | VPS + DNS (A-records `agentes./chatwoot./langfuse.` + painel do tier) + SSH | [`references/01-vps-dns-ssh.md`](references/01-vps-dns-ssh.md) |
| 1b | **Inventário brownfield**: sondar (read-only) e decidir por-serviço (reusar/instalar/sinalizar) | [`references/01b-brownfield.md`](references/01b-brownfield.md) |
| 1c | **Selecionar o tier** de deploy + fixar o **contrato** (o que o deploy entrega à espinha) | [`references/01c-pick-tier.md`](references/01c-pick-tier.md) |
| 2 | **Tier A** · Coolify: reusar/instalar, API Access, **Instance Domain** (`coolify.<root>`) | [`references/02-coolify.md`](references/02-coolify.md) |
| 3 | Deploy **Chatwoot** (Pro **ou** OSS pelo marcador; Pro: API do Coolify, login Harbor) | [`references/03-chatwoot-pro.md`](references/03-chatwoot-pro.md) |
| 4 | Deploy **Secretária V4** (edição Free/Pro pelo marcador, `docker-compose.coolify.yml`, bootstrap 2-roles + migrate) | [`references/04-secretaria-v4.md`](references/04-secretaria-v4.md) |
| 5 | Deploy **Langfuse** (+ **MinIO S3 obrigatório**) | [`references/05-langfuse.md`](references/05-langfuse.md) |
| 6 | v4 `/setup` (cria admin SUPER_ADMIN) → conectar **MCP** (OAuth) | [`references/06-setup-and-mcp.md`](references/06-setup-and-mcp.md) |
| 7 | **Branding** via MCP (`branding_set` nome + cores padrão; `branding_asset_set` logo/favicon) | [`references/07-branding.md`](references/07-branding.md) |
| 8 | **Import do agente** (`agent_import`; padrão **Maria**/Clínica Moreira, vendorado em `samples/agents/maria-clinica-moreira.json`) + embedding por-tenant + reindex/retry da KB | [`references/08-agent-import.md`](references/08-agent-import.md) |
| 8b | **Pós-import (gate)**: resolver avisos (KB→READY + grounding; STT/TTS/visão) + features opcionais (voz, Google OAuth) | [`references/agent-features.md`](references/agent-features.md) |
| 9 | Plugar Chatwoot na v4 (`deployment_connect` → `set_accounts` → `inbox_bind`) | [`references/09-chatwoot-bind.md`](references/09-chatwoot-bind.md) |
| 9b | **Licenciar Chatwoot no hub** (Kanban/Pro): com licença disponível (CLI/`list_licenses`) é **happy-path** (`create_instance → attach_license → Refresh`); sem licença → OSS sem Kanban | [`references/chatwoot-hub-register.md`](references/chatwoot-hub-register.md) |
| 10 | Validar **E2E** (playground + grounding → **integração via Inbox API** → traces; WhatsApp real opcional) | [`references/10-validate-e2e.md`](references/10-validate-e2e.md) |

**O deploy (etapa 2) ramifica por tier.** As linhas 2-5 acima são a trilha do **Tier A (Coolify)**. Para os outros, escolha em 1c, **substitua 2-5** pelo doc único do tier e convirja direto no **6** (todos entregam o mesmo [contrato](references/01c-pick-tier.md)):

- **Tier B** (Portainer): [`references/deploy-b-portainer.md`](references/deploy-b-portainer.md)
- **Tier C** (compose genérico, VM crua ou qualquer painel): [`references/deploy-c-compose.md`](references/deploy-c-compose.md)

## Gates de conta (real vs teste)

No **produto real**, o usuário cria o 1º admin de cada ferramenta no browser (o orquestrador, Chatwoot, v4 `/setup`); você só entrega link + instrução. No **teste**, esses gates são pulados para a run ser headless. Sempre deixe explícito qual modo está rodando. Detalhes em `guardrails.md`.

## Fora de escopo desta skill (por enquanto)

- **Trilhas dedicadas por painel** (Easypanel/Dokploy/CapRover/etc.): por escolha, não existem. Use o **Tier C** (compose genérico) e adapte ao painel com seu conhecimento dele.
- Migração/atualização de serviços incompatíveis (a etapa 1b **detecta e sinaliza**; a migração em si é decisão do usuário).
- Caminho manual (sem IA) e adapters de agente não-Claude-Code (Codex/Hermes).

Os três tiers de deploy (A/B/C) estão **dentro** do escopo (a etapa 1c roteia).

## Critério de aceite (E2E, objetivo final)

A run está **provada** quando: o agente responde no **playground** E numa **mensagem real de WhatsApp** (incoming → webhook → debounce → turn → modelo real → resposta entregue na conversa do Chatwoot); a KB está **grounding** (docs READY, resposta usa o conteúdo indexado); e os **traces aparecem no Langfuse** (ingestion 207). Detalhe e checklist em [`references/10-validate-e2e.md`](references/10-validate-e2e.md).
