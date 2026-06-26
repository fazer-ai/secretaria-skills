# Gotchas: armadilhas conhecidas

Cada uma é uma armadilha conhecida. Leia a da etapa antes de executá-la.

## Infra / Coolify

### FQDN não dirige o Traefik (503 em todo serviço)

Pra um **service** do Coolify, o Traefik lê `service_applications.fqdn` no DB; o env `SERVICE_FQDN_*` é **derivado** dele e NÃO move a rota. Sintoma: o serviço sobe mas dá 503 (cert 000), e a v4 bootou com `publicUrl` sslip.io.

Fix:

```sh
docker exec -i coolify-db psql -U coolify -d coolify
  -- ache o id:  SELECT id, name, fqdn FROM service_applications;
  UPDATE service_applications SET fqdn='https://agentes.<seu-dominio>' WHERE id=<id>;
```

depois reinicie o serviço: `curl -H "Authorization: Bearer <token>" http://<VPS_IP>:8000/api/v1/services/<uuid>/restart`. **Preserve a porta** quando o template tem (Langfuse: `...:3000`). Verifique por sslip.io enquanto o DNS não propaga.

### `docker_compose_raw` precisa ser base64

`POST /api/v1/services` com o compose cru → 422 "should be base64 encoded". Base64-encode antes de POSTar.

### NÃO sobrescrever `command:` no compose da v4

O boot (`bootstrap → migrate → serve`) é o CMD da imagem. Um `command:` override já derivou pro `./server` obsoleto e crash-loopou (`exec: ./server: not found`). Não declare `command:` no compose da v4.

### Instance Domain do Coolify

Sem setar o Instance Domain (`coolify.<seu-dominio>`) o painel fica só em `http://IP:8000` (HTTP puro, sem TLS). Exige o A-record.

### `prisma migrate reset` quebra a runtime role (local/dev)

Reset recria o schema `public` e leva junto os grants da app role → próximo boot dá `42501 permission denied for schema public`. Nunca rode bare `migrate reset`; use `bun db:reset` (ou re-rode `bun db:bootstrap`).

## Langfuse

### One-click sem MinIO = traces somem em silêncio

Langfuse v3 exige S3 blob storage na ingestion. O one-click sobe sem MinIO e com `LANGFUSE_S3_*` vazias → `POST /ingestion` dá HTTP 500 e os traces nunca chegam; o `GET /projects` (só Postgres) retorna 200 e mascara. **Use `deploy/langfuse/docker-compose.coolify.yml`** (com MinIO) e valide a ingestion (espere 207). Detalhe em `references/05-langfuse.md`.

## Config da v4 (pós-import)

### Embedding é por-tenant (senão os docs vão pra FAILED)

Sem `PUT /v1/tenant-settings/embedding {provider, model, credentialRef}`, os docs da KB vão pra FAILED (`embedding credential not configured`). É no nível do **tenant**, não por-KB nem da chave do modelo do agente.

### `reindex` não recupera docs FAILED

Depois de configurar o embedding, `POST /v1/knowledge/bases/:id/reindex` retorna `{queued:0}` se os docs já estão FAILED. Use `POST /v1/knowledge/documents/:id/retry` por doc.

### agent_import resolve credenciais por nome

O export referencia tudo **por nome**, e os nomes não existem no tenant novo. O `agent_import` cria as credenciais faltantes como **pending + deeplink** e emite o aviso `credentialPending`: o usuário só preenche o segredo. Exceções que não viram pending: kinds de OAuth gerenciado (`google_oauth`, `mcp_oauth`) e kinds que exigem `baseURL`/`paramName` → caem em `credentialNotFound`. Detalhe em `references/08-agent-import.md`.

### Chatwoot bind: `POST /deployment` registra o deployment; quem conecta as CONTAS é o `/accounts`

`POST /v1/chatwoot/deployment` valida o token (via `/profile`), **persiste o deployment** (baseUrl + adminToken criptografado na linha do deployment) e retorna as contas alcançáveis. O que ele **não** faz é conectar/sincronizar as contas individuais: isso é o `PUT /v1/chatwoot/deployment/accounts {accountIds:[...]}`. Depois `PATCH /v1/chatwoot/inboxes/:id {agentId}` provisiona o Agent Bot + webhook (não precisa setar `webhook_url` à mão). Detalhe em `references/09-chatwoot-bind.md`.

## Footguns de API (campos exatos)

### `POST /api/v1/api-keys`: o campo é `displayName`

Mintar a API key da v4 com `{ "name": ... }` → 422. O campo é `displayName`. O `token` vem só uma vez.

### vault POST usa `baseUrl` (camelCase)

`POST /v1/vault` espera `baseUrl` (camelCase); mandar `baseURL` faz a entrada nascer sem base URL e o wiring do Langfuse falha ("requires a base URL"). Atenção: o endpoint `PUT /v1/tenant-settings/embedding` usa a forma `baseURL` (maiúsculo), os dois diferem.

## Pendências conhecidas (não bloqueiam o core)

- **TTS:** precisa de chave ElevenLabs real.
- **Visão:** precisa de chave Gemini válida.
- **WhatsApp físico:** opcional; exige um número que o usuário controle. A integração Chatwoot→v4 já é provada headless via Inbox API (etapa 10); o físico só confirma o transporte real.
- **Kanban:** condicional à licença, **não** "opcional". Com licença disponível (CLI/`list_licenses`), habilitar é **happy-path** (licenciar no hub + Refresh; ver `references/chatwoot-hub-register.md`); imagem Pro sozinha não basta. Sem licença → OSS, sem Kanban.
