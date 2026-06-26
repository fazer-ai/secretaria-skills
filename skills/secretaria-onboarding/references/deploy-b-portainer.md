# Deploy Tier B: Portainer

**Validado E2E** (2026-06-25, VPS real): Portainer headless, v4 + Postgres + **Caddy bundled** (ACME
automático), brownfield reuse de um Chatwoot existente. O passo-a-passo completo vive em
[`docs/deploy-portainer.md`](../docs/deploy-portainer.md). **Siga aquele doc**; este aqui é só a
cola com a jornada.

## Como encaixa

O agente, da máquina do operador, dirige o Portainer pela **HTTP API**: gera os secrets
([`gen-onboarding-env.ts`](../scripts/gen-onboarding-env.ts)), registra os registries privados
(ghcr + Harbor pro Chatwoot Pro), e cria cada stack a partir de uma **string de compose**
(`POST /api/stacks/create/standalone/string`). O Caddy bundled do
[`docker-compose.portainer.yml`](../docker-compose.portainer.yml) termina TLS com cert real, sem
labels Traefik nem polling do socket.

**Brownfield:** [`scripts/portainer-brownfield.py`](../scripts/portainer-brownfield.py)
(API-native) inventaria as stacks, faz fingerprint por imagem e sinaliza **quem ocupa 80/443**: se já há
ingress, troque o Caddy bundled por [`docker-compose.prod.yml`](../docker-compose.prod.yml)
(BYO-proxy). É o equivalente Portainer da etapa 1b.

## O que entrega ao contrato (1c)

Seguindo o doc, ao fim você tem os 5 outputs do [contrato](01c-pick-tier.md): `agentes.`/`chatwoot.`/
`langfuse.` em HTTPS, v4 com as duas roles + token de `/setup`, admin token do Chatwoot, Langfuse+MinIO.
→ siga pra **etapa 6**.
