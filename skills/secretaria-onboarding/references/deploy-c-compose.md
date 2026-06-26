# Deploy Tier C: Compose genérico (VM crua ou painel sem trilha dedicada)

> ⚠️ **Estruturado a partir dos artefatos; E2E completo não rodado.** Os composes são os mesmos validados
> nos Tiers A/B; o que não foi rodado ponta a ponta é a sequência **manual** numa VM avulsa. Trate como
> primeira run guiada.

O caminho catch-all: tudo que não é Coolify (Tier A) nem Portainer (Tier B). Cobre dois casos com a mesma
base de artefatos:

- **VM crua**, só Docker + `docker compose`: você sobe cada stack à mão e cuida do TLS.
- **Painel sem trilha dedicada** (Easypanel, Dokploy, CapRover, etc.): **não há doc específico na skill, por
  escolha.** Pegue os passos genéricos abaixo e adapte ao painel com o que você já sabe dele (como ele cria
  um projeto Compose, injeta env, e anexa domínio + emite TLS). O alvo é sempre o
  [contrato](01c-pick-tier.md); o painel é só o meio.

## Tem um painel? Adapte, não procure trilha

O padrão de qualquer painel PaaS (Easypanel/Dokploy/CapRover/…) é o mesmo:

- O **proxy do painel** (Traefik/nginx embutido) detém 80/443 e emite Let's Encrypt ao **anexar um domínio**
  a um serviço. Logo, use [`docker-compose.prod.yml`](../docker-compose.prod.yml) (BYO-proxy, **sem**
  o Caddy bundled) e deixe o painel rotear + certificar. Um Caddy nosso brigaria pelas portas.
- O env vem do **`.env` que você controla** (não há magic vars do Coolify): gere com o `gen-onboarding-env.ts`
  e cole as vars no serviço pelo painel.
- Cada stack (v4, Chatwoot, Langfuse) vira um projeto Compose; anexe `agentes.`/`chatwoot.`/`langfuse.` a
  cada um. Detalhes de UI/API (anexar domínio, rede do proxy, `expose` vs `ports`) variam por produto e
  versão: resolva com seu conhecimento do painel da run.

Daqui em diante os passos são os mesmos da VM crua; só muda o "como" você aplica o compose + env.

## TLS na VM crua: duas opções

- **Caddy bundled** (recomendado se a VM tem 80/443 **livres**): use
  [`docker-compose.portainer.yml`](../docker-compose.portainer.yml) pra v4. Ele já traz um Caddy que
  emite Let's Encrypt automático a partir de `CADDY_DOMAIN`/`ACME_EMAIL` (gerados no `.env`).
- **BYO-proxy** (se já há nginx/Caddy/Traefik na 443, ou é um painel): use
  [`docker-compose.prod.yml`](../docker-compose.prod.yml) (sem Caddy) e aponte o proxy pra porta
  publicada do app. O inventário (1b) diz quem ocupa 80/443.

## Passos

1. **DNS primeiro** (A-records resolvendo antes do ACME; ver [1c](01c-pick-tier.md)).
2. **Env:** `bun scripts/gen-onboarding-env.ts --public-url https://agentes.<domínio> --acme-email
   voce@<domínio>` gera o `.env` (duas roles, secrets, URLs, `CADDY_DOMAIN`). Chatwoot/Langfuse têm env
   próprio (READMEs em [`deploy/chatwoot/`](../deploy/chatwoot/) e
   [`deploy/langfuse/`](../deploy/langfuse/)).
3. **Suba cada stack** (na raiz do repo na VM, com o `.env` ao lado; num painel, o equivalente é criar cada
   projeto Compose):
   ```sh
   docker compose -f docker-compose.portainer.yml up -d       # v4 + postgres + Caddy (ou .prod.yml + proxy)
   docker compose -f deploy/chatwoot/docker-compose.yml up -d  # Pro vs OSS pelo env (README)
   docker compose -f deploy/langfuse/docker-compose.yml up -d  # com MinIO (obrigatório)
   ```
4. **Boot da v4:** o CMD da imagem faz `bootstrap → migrate → serve`; **não** sobrescreva `command:`.
5. **Token do `/setup`** e **admin token do Chatwoot** saem dos logs (`docker compose logs`) / Rails runner,
   igual aos outros tiers.
6. **Verifique** (200 + cert Let's Encrypt) e **siga pra etapa 6**.

## Brownfield

Se a VM/painel já roda algum serviço, sonde com a etapa [1b](01b-brownfield.md) (a sondagem via
`docker ps`/`ss` cobre o caso sem painel; num painel, use a API/UI dele pra inventariar) e **reuse** o que
estiver saudável.

## O que entrega ao contrato

Os 5 outputs do [1c](01c-pick-tier.md). **Lacuna conhecida:** quando você usa o Caddy bundled só pra v4, o
fronting TLS de `chatwoot.`/`langfuse.` precisa de um site Caddy/proxy adicional apontando pra porta
publicada de cada um (a seção 5 de [`docs/deploy-portainer.md`](../docs/deploy-portainer.md)
descreve esse mesmo padrão).
