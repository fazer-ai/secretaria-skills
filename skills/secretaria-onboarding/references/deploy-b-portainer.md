# Deploy Tier B: Portainer

Adapter de deploy **Tier B**. O agente, da máquina do operador, dirige um **Portainer** pela HTTP API:
gera os secrets, deploya cada stack a partir de uma string de compose, e sobe um **Caddy bundled** que
termina TLS com certificado real automático (sem labels Traefik, sem polling do socket). É o companion
por-plataforma do [contrato (1c)](01c-pick-tier.md); os invariantes (duas roles de DB, pgvector, réplica
única) valem igual. Para BYO-proxy use `docker-compose.prod.yml`; o Tier B usa o Caddy-bundled
`docker-compose.portainer.yml`.

## Artefatos (incluídos nesta skill, relativos à raiz dela)

| Artefato | Papel |
| --- | --- |
| `docker-compose.portainer.yml` | v4 + Postgres + **Caddy bundled** (auto-HTTPS). Self-contained (uma string pro Portainer). |
| `scripts/gen-onboarding-env.ts` | Gera o `.env` (duas roles de DB, JWT/ENCRYPTION, `CADDY_DOMAIN`, `ACME_EMAIL` opcional). |
| `deploy/chatwoot/` | Stack do Chatwoot, Pro (Harbor) ou OSS (público): um compose genérico, edição por env. Ver [`03-chatwoot-pro.md`](03-chatwoot-pro.md). |
| `deploy/langfuse/` | Langfuse opcional (tracing); inclui o MinIO que a ingestion v3 exige. Ver [`05-langfuse.md`](05-langfuse.md). |
| `scripts/portainer-brownfield.py` | Descoberta brownfield read-only (inventário + decisão por serviço) via a API do Portainer. |

## Por que self-contained + Caddy bundled

A API "deploy from string" do Portainer recebe **um** documento de compose, então o
`docker-compose.portainer.yml` repete app + postgres e adiciona um serviço `caddy`. O Caddy monta o
Caddyfile a partir do env no boot (`CADDY_DOMAIN` → o app; `PORTAINER_DOMAIN` opcional → o painel via
`host.docker.internal:9443`) e obtém certs via ACME (tls-alpn-01 / http-01).

## Pré-requisitos

- **DNS**: A-records pro FQDN do app (ex. `agentes.<domínio>`) e, se quiser o painel num domínio limpo,
  `portainer.<domínio>` → o IP do VPS. O ACME valida contra eles, então têm que resolver **antes** do deploy.
- **Credenciais de registry** pras imagens privadas (configure uma vez no Portainer, passe `Registries:[id]`):
  - `ghcr.io` pra `ghcr.io/fazer-ai/secretaria-v4` (e pgvector/baileys). Token do GitHub com `read:packages`.
  - `harbor.fazer.ai` pro Chatwoot **Pro**: a registry credential da licença (no hub, `generate_install_script`
    revela). Chatwoot OSS não precisa de registry privado.

## 1. Instalar o Portainer (headless)

```sh
docker volume create portainer_data
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data \
  portainer/portainer-ce:lts
```

O Portainer 2.39+ protege a API de primeiro-admin atrás de um **setup token impresso nos logs** (e tranca
a inicialização ~5 min após o start; reinicie o container pra um token novo se perder a janela):

```sh
STOK=$(docker logs portainer 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g' | grep -oE 'setup_token=[a-f0-9]{64}' | tail -1 | cut -d= -f2)
curl -sk -X POST https://localhost:9443/api/users/admin/init \
  -H 'Content-Type: application/json' -H "X-Setup-Token: $STOK" \
  -d '{"Username":"admin","Password":"<≥12 chars>"}'
```

> No fluxo **real** do produto o operador cria o primeiro admin **no browser** (`https://<ip>:9443`). O
> `admin/init` headless acima é o atalho de teste/automação.

Depois minte uma API key e ache o endpoint id (o ambiente Docker local, geralmente `1`):

```sh
JWT=$(curl -sk -X POST https://localhost:9443/api/auth -d '{"Username":"admin","Password":"..."}' | jq -r .jwt)
# endpoint local (crie se GET /api/endpoints estiver vazio):
curl -sk -X POST https://localhost:9443/api/endpoints -H "Authorization: Bearer $JWT" -F Name=local -F EndpointCreationType=1
# X-API-Key de longa duração:
curl -sk -X POST https://localhost:9443/api/users/1/tokens -H "Authorization: Bearer $JWT" \
  -d '{"password":"...","description":"onboarding"}' | jq -r .rawAPIKey
```

## 2. Registrar os registries privados (uma vez)

```sh
curl -sk -X POST https://localhost:9443/api/registries -H "X-API-Key: <api-key>" -H 'Content-Type: application/json' \
  -d '{"Name":"ghcr","Type":3,"URL":"ghcr.io","Authentication":true,"Username":"<gh-user>","Password":"<gh-token>"}'
# Só Pro:
curl -sk -X POST https://localhost:9443/api/registries -H "X-API-Key: <api-key>" -H 'Content-Type: application/json' \
  -d '{"Name":"harbor","Type":3,"URL":"harbor.fazer.ai","Authentication":true,"Username":"robot$...","Password":"<secret>"}'
```

`Type:3` é registry Custom (serve pra qualquer). Capture cada `Id` e passe no array `Registries` do stack
pra o `pull_policy: always` autenticar.

## 3. Deploy do stack v4

Gere o env, depois crie o stack a partir da string de compose:

```sh
bun scripts/gen-onboarding-env.ts --public-url https://agentes.<domínio> --acme-email voce@<domínio>
# -> .env com CADDY_DOMAIN, as duas URLs de role do DB, JWT_SECRET, ENCRYPTION_KEY. Adicione
#    PORTAINER_DOMAIN pra também servir o painel pelo mesmo Caddy.

curl -sk -X POST "https://localhost:9443/api/stacks/create/standalone/string?endpointId=1" \
  -H "X-API-Key: <api-key>" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg c "$(cat docker-compose.portainer.yml)" --argjson env "$ENV_JSON" \
        '{Name:"secretaria-v4", StackFileContent:$c, Env:$env, Registries:[<ghcr-id>]}')"
```

`Env` é um array de `{name,value}` do `.env` gerado. O entrypoint da imagem roda **db-bootstrap →
migrate → serve**; o Caddy obtém o(s) cert(s) no primeiro boot. Atualize um stack depois com
`PUT /api/stacks/{id}?endpointId=1` (`{StackFileContent, Env, PullImage:true, Prune:false}`).

## 4. Verificar

```sh
curl -sS -o /dev/null -w '%{http_code} verify=%{ssl_verify_result}\n' https://agentes.<domínio>/api/health   # 200 verify=0
echo | openssl s_client -connect agentes.<domínio>:443 -servername agentes.<domínio> 2>/dev/null \
  | openssl x509 -noout -issuer   # issuer= ... O=Let's Encrypt
```

Um "stack deployed" verde no Portainer não basta: confirme que o issuer do cert é Let's Encrypt e que
`/api/auth/me` retorna JSON (`setupRequired:true` num DB novo). HTTP→HTTPS é um 308 do Caddy.

## 5. Chatwoot + Langfuse

Deploye `deploy/chatwoot/` (Pro vs OSS por edição, ver [`03-chatwoot-pro.md`](03-chatwoot-pro.md)) e, se
selecionado, `deploy/langfuse/` (ver [`05-langfuse.md`](05-langfuse.md)) do mesmo jeito (stack-create from
string + `Env[]` + os `Registries` relevantes). Frontear `chatwoot.<domínio>` / `langfuse.<domínio>` com
TLS: aponte um site Caddy pra porta publicada de cada um, ou dê a cada um seu stack e deixe o Caddy
compartilhado fazer o proxy.

## Brownfield: o Portainer já tem serviços

Quando o operador escolheu Portainer mas **já roda Portainer + alguns serviços** (ex. Chatwoot), sonde
antes de instalar e decida **por serviço**, nunca destrua dados do operador. A sondagem é nativa da API do
Portainer (o equivalente Coolify é a etapa [`01b-brownfield.md`](01b-brownfield.md)):

```sh
PORTAINER_API_KEY=$KEY PORTAINER_ENDPOINT_ID=1 python3 scripts/portainer-brownfield.py
```

Ele lista os stacks, faz fingerprint de cada container por imagem, sinaliza **quem ocupa 80/443** (um
ingress existente faz o stack Caddy-bundled conflitar → reuse-o ou troque pro `docker-compose.prod.yml`
BYO-proxy) e imprime uma matriz de decisão: `secretaria-v4` saudável → reusa; Chatwoot presente → reusa
(`chatwoot-pro` Harbor e OSS são ambos válidos); Chatwoot ausente → instala Pro se há assinatura no hub,
senão OSS; Langfuse ausente → instala só se selecionado.

## Gotcha: o header de auth do Chatwoot pelo Caddy bundled

O Chatwoot documenta o header de auth da API como `api_access_token` (underscores), mas reverse proxies
descartam headers com underscore no nome (nginx tem `underscores_in_headers off`; o Caddy bundled do
Chatwoot também descarta). Efeito: o mesmo admin token enviado ao Chatwoot **pelo Caddy** como
`api_access_token` é rejeitado (401), enquanto **direto no puma** (sem proxy) autentica (200). O Rails
(Rack) mapeia `-` e `_` pra mesma env var, então a grafia com **hífen** `api-access-token` é lida igual
pelo Chatwoot **e** sobrevive ao Caddy (200). A v4 **manda o hífen** por padrão, então `deployment_connect`
e as tools HTTP do agente funcionam contra a URL pública fronteada pelo Caddy sem workaround. Se você
escrever uma integração Chatwoot à mão, use `api-access-token`, nunca o underscore.

## O que entrega ao contrato

Os 5 outputs do [contrato (1c)](01c-pick-tier.md): `agentes.`/`chatwoot.`/`langfuse.` em HTTPS, v4 com as
duas roles + token de `/setup`, admin token do Chatwoot, Langfuse+MinIO. → siga pra **etapa 6**.
