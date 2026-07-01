# 08: Import do agente + credenciais + embedding + KB

## 1. Importar (`agent_import`, mcp:write)

A skill traz o **agente padrão** vendorado em `samples/agents/maria-clinica-moreira.json` ("Maria", recepção da Clínica Moreira fictícia: agendamento, FAQ via KB, voz, Asaas). **Importe-o por padrão**; só use outro export se o usuário trouxer o dele. Leia o arquivo e passe o conteúdo como `export`:

```jsonc
agent_import { "export": <conteúdo de samples/agents/maria-clinica-moreira.json>, "tenant": "<slug do tenant_list>" }   // dry_run:true → preview, depois dry_run:false
```

- **SUPER_ADMIN:** inclua `tenant` (o slug/id de `tenant_list`); o token é fleet-level. **NUNCA** `tenant_create`: o tenant do `/setup` já existe; criar outro joga o agente no tenant errado (ver etapa 6).
- O agente é **sempre** criado **disabled + test mode** (nunca vai ao ar pra cliente por acidente); componentes (KB/tools/etc.) recriados/reusados **por nome**.
- Credenciais faltantes (os nomes não existem no tenant novo): o import cria uma entrada **pending** (mantendo o ref wired) e emite o aviso `credentialPending`; o usuário preenche no vault.
- **Exceções** que não viram pending no import → `credentialNotFound`: (a) OAuth gerenciado (`google_oauth`, `mcp_oauth`), que nunca pode ser pending (vem de connect flow); (b) kinds que exigem `base_url`/`param_name`, porque o import não tem esses valores pra passar. Pra (b), crie explicitamente com `credential_create` passando `base_url`/`param_name` (ex.: `openai_compatible`); pra (a), trate o OAuth à parte.

## 2. Preencher credenciais (segredo NUNCA passa pelo agente)

- **Sempre entregue o deeplink**, nunca só "vá em Configurações → Credenciais". Cada pending abre direto pelo `fillAt = ${PUBLIC_URL}/resources/vault?fill=<vaultId>` (o `?fill=<id>` abre o modal de preenchimento da entrada). É o caminho canônico das credenciais do **usuário** (OpenAI/ElevenLabs/Gemini/Asaas).
- **De onde vem o `fillAt`:** um `credential_create` **real** (`dry_run:false`) devolve o `fillAt` na resposta. Mas o **dry-run não devolve**, e re-criar uma que já existe **duplica**. Pra uma pending que **já existe** (import/brownfield/run anterior), **não re-crie**: pegue o `id` no `vault_list` e monte a URL você mesmo (`${PUBLIC_URL}/resources/vault?fill=<id>`).
- A chave OpenAI e as demais do **usuário** (ElevenLabs/Gemini/Asaas) o usuário preenche por esse deeplink; o segredo nunca passa pelo agente. Acompanhe pelo `vault_list` até o status sair de `pending`. (Exceção: o Langfuse, cujas keys **você** provisiona ao semear o projeto, não é segredo do usuário; ligue na v4 via `langfuse_connect` com as keys inline, ver `references/05-langfuse.md`.)

## 3. Religar o modelo + habilitar (`agent_update`)

Habilite o agente **mantendo o test mode** (como ele foi importado). Habilitar liga o bot; o `mode:"test"` faz ele responder só em conversas ativadas com `/teste` (etapa 10) e ficar em silêncio nas demais (com uma nota privada), então ele **não** atende cliente real ainda. Ligar pra produção é o **passo final do usuário** (abaixo).

```jsonc
agent_update {
  "agent_id": "<id>", "enabled": true,
  "model_config": { "provider":"openai", "model":"gpt-5.4-mini", "temperature":0.3, "credentialRef":"<nome da vault entry>" }
}
```

- **Não** mande `mode` aqui: o import já criou em `test` e a validação (etapa 10) roda nesse modo via `/teste`. Não promova pra `production` por conta própria.
- Via MCP, `model_config.credentialRef` aceita o **nome** da entrada do vault (resolvido server-side). Via REST é a forma `"vault:<id>"`.
- Mande o `model_config` **completo** pra não clobberar campos. (O STT pode reusar a mesma chave.)

### Ir pra produção é decisão do usuário

Depois do E2E aprovado (etapa 10), **o usuário** decide quando o agente vai ao ar pra clientes reais: aí sim `agent_update { "agent_id":"<id>", "mode":"production" }`. Entregue o agente validado em test mode e deixe esse flip pro usuário; não o faça no fluxo automático.

## 4. Embedding é por-tenant (senão a KB falha)

Ligue a credencial de embedding no tenant **via MCP**: `tenant_settings_update { embedding: { credential_ref: "<nome da entry>" } }` (provider/model default a `openai`/`text-embedding-3-small`). Sem isso os docs vão pra FAILED (`embedding credential not configured`). É no nível do **tenant**, não por-KB.

## 5. Indexar a KB + retry dos FAILED

- Os docs do import entram **UNINDEXED**. Com o embedding já ligado (passo 4), eles precisam ser indexados, mas **não há MCP tool de reindex ainda** (gap conhecido): o **usuário** clica **Indexar** no alerta pós-import da KB (tela `/knowledge`, o mesmo aviso "documentos que precisam ser indexados"). É um passo de browser dele, como a criação das contas.
- Docs que já foram pra **FAILED** (o embedding faltava no momento do import) não são pegos pelo reindex; re-enfileire por doc **via MCP**: `knowledge_document_retry { document_id }`.

## 6. Gate antes de seguir

Não declare o import pronto com aviso aberto: **todos os docs da KB READY** + **grounding verificado** no playground (pergunte algo que só a KB sabe); STT/TTS/visão sinalizados → conectar credencial ou desligar a feature. Detalhe + features opcionais (voz, Google OAuth) em [`agent-features.md`](agent-features.md).
