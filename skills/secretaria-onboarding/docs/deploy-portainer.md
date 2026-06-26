# Deploy: Portainer (Tier B)

The onboarding's **Tier B** deploy adapter. The agent, on the operator's machine, drives a **Portainer**
instance over its HTTP API: it generates the secrets, deploys each stack from a compose string, and
brings up a bundled **Caddy** that terminates TLS with a real certificate automatically (no Traefik
labels, no Docker-socket polling). Everything below was validated end-to-end on a live VPS
(2026-06-25): real Let's Encrypt certs for the app **and** the Portainer panel, v4 two-role bootstrap,
and brownfield reuse of a pre-existing Chatwoot.

This is the per-platform companion to [`deploy.md`](deploy.md) (the load-bearing invariants — two DB
roles, pgvector, single replica — apply unchanged). For the bring-your-own-proxy variant see
[`../docker-compose.prod.yml`](../docker-compose.prod.yml); Tier B uses the Caddy-bundled
[`../docker-compose.portainer.yml`](../docker-compose.portainer.yml).

## Artifacts

| Artifact | Role |
| --- | --- |
| [`../docker-compose.portainer.yml`](../docker-compose.portainer.yml) | v4 app + Postgres + **bundled Caddy** (auto-HTTPS). Self-contained (one string for Portainer). |
| [`../scripts/gen-onboarding-env.ts`](../scripts/gen-onboarding-env.ts) | Generates the `.env` (two DB roles, JWT/ENCRYPTION secrets, `CADDY_DOMAIN`, optional `ACME_EMAIL`). |
| [`../deploy/chatwoot/`](../deploy/chatwoot/) | Chatwoot stack, **Pro** (Harbor, hub subscription) or **OSS** (public) — one generic compose, edition by env. |
| [`../deploy/langfuse/`](../deploy/langfuse/) | Optional Langfuse (tracing); bundles the MinIO that v3 ingestion requires. |
| [`../scripts/portainer-brownfield.py`](../scripts/portainer-brownfield.py) | Read-only brownfield discovery (inventory + per-service decision) via the Portainer API. |

## Why self-contained + bundled Caddy

Portainer's "deploy from string" API takes **one** compose document, so `docker-compose.portainer.yml`
repeats the app + postgres and adds a `caddy` service. Caddy builds its Caddyfile from env at start
(`CADDY_DOMAIN` → the app; optional `PORTAINER_DOMAIN` → the Portainer panel via `host.docker.internal:9443`)
and obtains certs over ACME (tls-alpn-01 / http-01). This is the plan's "agent brings up Caddy,
HTTPS auto, no labels/polling".

## Prerequisites

- **DNS**: A-records for the app FQDN (e.g. `agentes.<domain>`) and, if you want the panel on a clean
  domain, `portainer.<domain>` → the VPS IP. ACME validates against these, so they must resolve to the
  box **before** you deploy.
- **Registry credentials** for the private images (configure once in Portainer, pass `Registries:[id]`):
  - `ghcr.io` for `ghcr.io/fazer-ai/secretaria-v4` (and `pgvector`/`baileys`). A GitHub token with
    `read:packages`.
  - `harbor.fazer.ai` for Chatwoot **Pro** — the license registry credential (hub:
    `generate_install_script` reveals it). OSS Chatwoot needs no private registry.

## 1. Install Portainer (headless)

```sh
docker volume create portainer_data
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data \
  portainer/portainer-ce:lts
```

Portainer 2.39+ gates the first-admin API behind a **setup token printed in the logs** (and locks
initialization ~5 min after start — restart the container to get a fresh token if you miss the window):

```sh
STOK=$(docker logs portainer 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g' | grep -oE 'setup_token=[a-f0-9]{64}' | tail -1 | cut -d= -f2)
curl -sk -X POST https://localhost:9443/api/users/admin/init \
  -H 'Content-Type: application/json' -H "X-Setup-Token: $STOK" \
  -d '{"Username":"admin","Password":"<≥12 chars>"}'
```

> In the **real** product flow the operator creates the first admin **in the browser** (`https://<ip>:9443`).
> The headless `admin/init` above is the test/automation shortcut.

Then mint an API key and find the endpoint id (the local Docker environment, usually `1`):

```sh
JWT=$(curl -sk -X POST https://localhost:9443/api/auth -d '{"Username":"admin","Password":"..."}' | jq -r .jwt)
# local endpoint (create it if GET /api/endpoints is empty):
curl -sk -X POST https://localhost:9443/api/endpoints -H "Authorization: Bearer $JWT" -F Name=local -F EndpointCreationType=1
# long-lived X-API-Key:
curl -sk -X POST https://localhost:9443/api/users/1/tokens -H "Authorization: Bearer $JWT" \
  -d '{"password":"...","description":"onboarding"}' | jq -r .rawAPIKey
```

## 2. Register the private registries (once)

```sh
curl -sk -X POST https://localhost:9443/api/registries -H "X-API-Key: <api-key>" -H 'Content-Type: application/json' \
  -d '{"Name":"ghcr","Type":3,"URL":"ghcr.io","Authentication":true,"Username":"<gh-user>","Password":"<gh-token>"}'
# Pro only:
curl -sk -X POST https://localhost:9443/api/registries -H "X-API-Key: <api-key>" -H 'Content-Type: application/json' \
  -d '{"Name":"harbor","Type":3,"URL":"harbor.fazer.ai","Authentication":true,"Username":"robot$...","Password":"<secret>"}'
```

`Type:3` is a Custom registry (works for any). Capture each `Id` and pass them in the stack's
`Registries` array so `pull_policy: always` authenticates.

## 3. Deploy the v4 stack

Generate the env, then create the stack from the compose string:

```sh
bun scripts/gen-onboarding-env.ts --public-url https://agentes.<domain> --acme-email you@<domain>
# -> .env with CADDY_DOMAIN, the two DB-role URLs, JWT_SECRET, ENCRYPTION_KEY. Add PORTAINER_DOMAIN to
#    also serve the panel through the same Caddy.

curl -sk -X POST "https://localhost:9443/api/stacks/create/standalone/string?endpointId=1" \
  -H "X-API-Key: <api-key>" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg c "$(cat docker-compose.portainer.yml)" --argjson env "$ENV_JSON" \
        '{Name:"secretaria-v4", StackFileContent:$c, Env:$env, Registries:[<ghcr-id>]}')"
```

`Env` is an array of `{name,value}` from the generated `.env`. The image entrypoint runs
**db-bootstrap → migrate → serve**; Caddy obtains the cert(s) on first start. Update a stack later with
`PUT /api/stacks/{id}?endpointId=1` (`{StackFileContent, Env, PullImage:true, Prune:false}`).

## 4. Verify

```sh
curl -sS -o /dev/null -w '%{http_code} verify=%{ssl_verify_result}\n' https://agentes.<domain>/api/health   # 200 verify=0
echo | openssl s_client -connect agentes.<domain>:443 -servername agentes.<domain> 2>/dev/null \
  | openssl x509 -noout -issuer   # issuer= ... O=Let's Encrypt
```

A green Portainer "stack deployed" is not enough — confirm the cert issuer is Let's Encrypt and
`/api/auth/me` returns JSON (`setupRequired:true` on a fresh DB). HTTP→HTTPS is a 308 from Caddy.

## 5. Chatwoot + Langfuse

Deploy [`../deploy/chatwoot/`](../deploy/chatwoot/) (Pro vs OSS by edition — see its README) and, if
selected, [`../deploy/langfuse/`](../deploy/langfuse/) the same way (stack-create from string + `Env[]`
+ the relevant `Registries`). Front `chatwoot.<domain>` / `langfuse.<domain>` with a TLS proxy — point a
Caddy site at their published host port, or give each its own stack and let the shared Caddy proxy it.

## Brownfield: Portainer already has services

When the operator selected Portainer but **already runs Portainer + some target services** (e.g.
Chatwoot), probe before installing and decide **per service** — never clobber the operator's data. The
discovery is Portainer-API-native (the Coolify equivalent is the skill's step 1b):

```sh
PORTAINER_API_KEY=$KEY PORTAINER_ENDPOINT_ID=1 python3 scripts/portainer-brownfield.py
```

It lists the Portainer stacks, fingerprints every container by image, flags **who owns 80/443** (an
existing ingress means the bundled-Caddy stack would conflict → reuse it or switch to
`docker-compose.prod.yml` BYO-proxy), and prints a decision matrix:

- **secretaria-v4 present+healthy** → reuse.
- **Chatwoot present** → reuse. `chatwoot-pro` (Harbor) and **OSS** (`chatwoot/chatwoot`) are **both**
  valid — OSS is not incompatible, it only lacks Pro features (Baileys WhatsApp, Kanban). An **absent**
  Chatwoot installs Pro if the operator has a hub subscription, else OSS.
- **langfuse absent** → install only if selected.

Validated live: against a box already running the v4 stack + a Chatwoot Pro stack, the probe correctly
reported `secretaria-v4=REUSE`, `chatwoot(pro)=REUSE`, `langfuse=install`, and the occupied 80/443.

## Gotcha (Tier B): the Chatwoot auth header through the bundled Caddy

Chatwoot documents its API auth header as `api_access_token` (underscores), but reverse proxies drop
request headers whose names contain underscores (nginx ships `underscores_in_headers off`; the Caddy
bundled with Chatwoot drops them too). Observed on this stack: the same admin token sent to Chatwoot
**through the bundled Caddy** as `api_access_token` is rejected (401), while sent **directly to puma**
(no proxy) it authenticates (200). Rails (Rack) maps both `-` and `_` to the same env var, so the
**hyphen** spelling `api-access-token` is read identically by Chatwoot **and** survives Caddy (200).

**v4 sends the hyphen** (`CHATWOOT_AUTH_HEADER` in `src/modules/chatwoot/constants.ts`, shared by the
client and the `chatwoot_api_token` vault injection), so `deployment_connect` and agent HTTP tools work
against the **public Caddy-fronted URL** out of the box — no internal-network or `SSRF_ALLOW_PRIVATE_TARGETS`
workaround is needed. Verified end-to-end against a live Chatwoot Pro: hyphen returns 200 both via Caddy
and direct; underscore 401s via Caddy and 200s direct (proving the proxy, not Chatwoot, drops it). If you
hand-write a Chatwoot integration, use `api-access-token`, never the underscore spelling.

The Chatwoot **OSS vs Pro** edition and the agent import (credential refs resolve by name; create matching
vault entries) are covered in [`../deploy/chatwoot/README.md`](../deploy/chatwoot/README.md) and
[`../samples/agents/`](../samples/agents/).

## Validated (2026-06-25, VPS srv1043961)

Greenfield: Portainer CE 2.39 headless → v4 stack via `POST /stacks/create/standalone/string` (private
ghcr image via a Portainer registry) → app healthy (bootstrap+migrate+serve) → bundled Caddy obtained
**real Let's Encrypt** certs for `agentes.fazerai.cloud` **and** `portainer.fazerai.cloud` (the panel
fronted through Caddy). Brownfield: a Chatwoot Pro stack (Harbor image) deployed via the same API and
the discovery reused it. This closes the plan's open validation "Portainer + Caddy headless: ACME
end-to-end".

Full journey on the same box (Tier B parity with the Coolify run): v4 `/setup` (admin created from the
`${PUBLIC_URL}/setup?token=…` link in the boot logs — automated here; the operator does it in the real
flow) → agent import (`maria-clinica-moreira`) + OpenAI vault + enable → **playground responds** with the
real model → Chatwoot Pro deployed + admin/account/token (Rails runner) → v4 deployment connect + account
sync + **inbox bind (Agent Bot active, webhook → v4)** → Langfuse deployed (with MinIO) + vault + tenant
setting → **ingestion 207 and a playground trace visible** in Langfuse. The v4 ↔ Chatwoot link used the
internal-network option above (see the gotcha).
