# 08: Import do agente + credenciais + embedding + KB

## 1. Importar (`agent_import`, mcp:write)

```jsonc
agent_import { "export": <conteúdo do maria.json> }   // dry_run:true → preview, depois dry_run:false
```

- O agente é **sempre** criado **disabled + test mode**; componentes (KB/tools/etc.) recriados/reusados **por nome**.
- Credenciais faltantes (os nomes não existem no tenant novo): o import cria uma entrada **pending** (mantendo o ref wired) e emite o aviso `credentialPending`; o usuário preenche no vault.
- **Exceções** que não viram pending no import → `credentialNotFound`: (a) OAuth gerenciado (`google_oauth`, `mcp_oauth`), que nunca pode ser pending (vem de connect flow); (b) kinds que exigem `base_url`/`param_name`, porque o import não tem esses valores pra passar. Pra (b), crie explicitamente com `credential_create` passando `base_url`/`param_name` (ex.: `openai_compatible`); pra (a), trate o OAuth à parte.

## 2. Preencher credenciais (segredo NUNCA passa pelo agente)

- Cada credencial pending tem um **deeplink** (`fillAt`) que leva o usuário direto à entrada no console pra colar o segredo. Esse é o caminho canônico das credenciais do **usuário** (OpenAI/ElevenLabs/Gemini/Asaas).
- `credential_create { name, kind?, base_url?, param_name? }` declara uma pending nova (sem segredo) e devolve o deeplink: útil pra wirar config agora e o usuário preencher depois.
- No **teste**, a chave OpenAI fornecida pode ser posta direto no vault por REST (`POST /v1/vault {name, kind, value}`), já que o operador a tem em mãos. No fluxo real, prefira o deeplink.

## 3. Religar o modelo + habilitar (`agent_update`)

```jsonc
agent_update {
  "agent_id": "<id>", "enabled": true, "mode": "production",
  "model_config": { "provider":"openai", "model":"gpt-5.4-mini", "temperature":0.3, "credentialRef":"<nome da vault entry>" }
}
```

- Via MCP, `model_config.credentialRef` aceita o **nome** da entrada do vault (resolvido server-side). Via REST é a forma `"vault:<id>"`.
- Mande o `model_config` **completo** pra não clobberar campos. (O STT pode reusar a mesma chave.)

## 4. Embedding é por-tenant (senão a KB falha): REST

```sh
PUT /v1/tenant-settings/embedding { "provider":"openai", "model":"text-embedding-3-small", "credentialRef":"vault:<id>" }
```

Sem isso os docs vão pra FAILED (`embedding credential not configured`). É no nível do **tenant**, não por-KB.

## 5. Indexar a KB (reindex) + retry dos FAILED

- Os docs do import entram **UNINDEXED**. Com o embedding já configurado (passo 4), `POST /v1/knowledge/bases/:id/reindex` (REST, TENANT_ADMIN) os indexa de primeira.
- `reindex` **não** re-enfileira docs já em **FAILED** (retorna `{queued:0}`): é o que acontece se o embedding faltava no momento do import. Pra esses, retry por doc: `POST /v1/knowledge/documents/:id/retry` (REST) ou a MCP tool `knowledge_document_retry { document_id }`.

## 6. Gate antes de seguir

Não declare o import pronto com aviso aberto: **todos os docs da KB READY** + **grounding verificado** no playground (pergunte algo que só a KB sabe); STT/TTS/visão sinalizados → conectar credencial ou desligar a feature. Detalhe + features opcionais (voz, Google OAuth) em [`agent-features.md`](agent-features.md).
