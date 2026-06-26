# 10: Validar E2E

## Pré-condições

- Agente importado e habilitado (`enabled:true`, `mode:production`), modelo religado a uma vault key real (etapa 8).
- KB com docs **READY** (etapa 8).
- Inbox do Chatwoot bound ao agente, bot `active` (etapa 9).
- Langfuse com ingestion **207** + wired na v4 (etapas 5 e 8).

## 1. Playground (modelo real, sem Chatwoot)

Via MCP (preferido): `agent_playground` (mcp:read; aceita texto ou `attachment` base64/url, e `reply_with_audio`). Via REST: `POST /api/v1/agents/:id/playground`. O agente responde com o modelo real. Cheque **grounding**: pergunte algo coberto pela KB e confirme que a resposta usa o conteúdo indexado (não uma resposta genérica).

## 2. Integração Chatwoot → v4 via Inbox API (obrigatório, headless)

Prova a ponta `incoming → webhook → turn → reply` **sem aparelho**, com um inbox `Channel::Api`:
- Crie um inbox `Channel::Api` no Chatwoot e benda ao agente (`inbox_bind`, etapa 9), que auto-provisiona o Agent Bot + webhook.
- Injete uma mensagem **incoming** pela API do Chatwoot (criar conversa + `POST .../messages` com `message_type: incoming`).
- Cadeia esperada: incoming → webhook (`/api/v1/chatwoot/webhook/:routeToken`) → **debounce** → turn → modelo real → resposta **outgoing** na conversa. Confirme a resposta + o `ExecutionLog`/trace no Langfuse.

Este é o teste que **não pode ficar pendente**: é o que prova que bind + webhook funcionam.

## 2b. WhatsApp real (opcional, confirma o transporte)

Pareie a inbox real (Baileys via QR) com um número que o usuário controle e mande uma mensagem: mesma cadeia do passo 2, exercitando o transporte WhatsApp de verdade. Pode ficar pendente sem invalidar o core (a integração já foi provada no 2).

## 3. Traces no Langfuse

- Confirme que o turn aparece no Langfuse (env `production-playground` ou `production`, session = threadId da v4). A ingestion já foi validada em 207 na etapa 5.

## Critério de aceite

Responde no **playground** (com **KB grounding** confirmado) E na **integração via Inbox API**; **trace** no Langfuse. O **WhatsApp físico** é confirmação opcional (a integração já foi provada via Inbox API). O **Kanban** segue o passo 9b: happy-path quando há licença, ausente no OSS.
