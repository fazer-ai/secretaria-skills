# 02: Coolify (reusar/instalar, API, Instance Domain)

## Brownfield: reusar se já existe e está saudável

A VPS pode já vir com Coolify (brownfield). Nesse caso, reaproveite o existente: **nunca** destrua dados do usuário. O inventário brownfield completo (todos os serviços, com a matriz reusar/instalar/sinalizar) está na etapa 1b (`references/01b-brownfield.md`); aqui é só a parte do Coolify.

### Reinstalação limpa: só num recurso descartável

Para um teste do zero, reinstale: wipe do Docker + `/data/coolify` + instalador oficial do Coolify. **Só faça isso numa VPS confirmada como descartável** (`guardrails.md`); é destrutivo. Resultado esperado: instalador sai `0`, "Your instance is ready to use!", 4 containers core Up+healthy (`coolify`, `coolify-db`, `coolify-redis`, `coolify-realtime`).

## 1º admin (browser: único passo de browser no Tier A)

Real: o usuário cria. Teste: você cria. A partir daqui, tudo é API/SSH.

## Instance Domain (fecha o gap do IP cru)

Settings → general → **Instance Domain** = `https://coolify.<seu-dominio>`. Exige o A-record da etapa 1. Sem isso o painel fica só em `http://<VPS_IP>:8000` (HTTP puro, sem TLS).

## API Access

Settings → Advanced → **API Access**; gere um token root. Guarde transitoriamente (scratchpad), **nunca** em repo/log/commit.
- Base da API: `http://<VPS_IP>:8000/api/v1`, header `Authorization: Bearer <token>`.

## DB do Coolify (necessário pro fix de FQDN; ver gotchas)

```sh
docker exec -i coolify-db psql -U coolify -d coolify
```

## Projeto + ambiente

Crie (ou reaproveite) um projeto com o **nome de exibição do usuário** (ex.: `clinica-moreira`) e o ambiente `production`. Os UUIDs (server/projeto/env/serviços) são **gerados a cada instalação**: descubra-os pela API/DB; nunca chumbe UUIDs de outra instalação.
