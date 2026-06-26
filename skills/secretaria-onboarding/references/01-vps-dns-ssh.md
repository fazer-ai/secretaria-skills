# 01: VPS + DNS + SSH

## VPS

A VPS fornecida pelo usuário (`<VPS_IP>`; ver `guardrails.md`). O orquestrador (Coolify, Portainer, outro painel, ou nenhum) já instalado (brownfield) ou a instalar no deploy do tier (escolhido em 1c). Nunca tocar em outra VPS da conta.

## SSH (comando exato)

```sh
ssh -o IdentitiesOnly=yes -o IdentityAgent=none -o ConnectTimeout=12 -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new -i ~/.ssh/<sua-chave> root@<VPS_IP>
```
Bash com rede → `dangerouslyDisableSandbox: true`. Scripts/SQL longos: base64 local → pipe → `base64 -d` no destino.

## DNS (MCP Hostinger, domínio `<seu-dominio>`)

A-records apontando pra `<VPS_IP>` (os três da app são o contrato; ver 1c):
- `agentes.<seu-dominio>`: Secretária V4
- `chatwoot.<seu-dominio>`: Chatwoot (Pro ou OSS)
- `langfuse.<seu-dominio>`: Langfuse (recomendado)
- **painel do orquestrador** (se houver e você quiser um domínio limpo): `coolify.` (Tier A) / `portainer.` (Tier B); outro painel usa o próprio; no compose genérico (Tier C) pode não haver painel.

Tools do `hostinger-dns`: `DNS_getDNSRecordsV1` (inspecionar), `DNS_updateDNSRecordsV1` (setar). **Monitore a propagação** antes de prosseguir: o ACME (Traefik do Coolify, Caddy do Portainer, ou o proxy do tier) só emite o certificado quando o A-record resolve. Sem isso, os serviços sobem mas ficam 503/sem TLS.

Os subdomínios acima são a convenção de onboarding; os nomes de exibição/projeto (orquestrador/Langfuse/branding) vêm do usuário.

## Outro provider (VPS/DNS fora da Hostinger)

Se o usuário usa outro provider de VPS e/ou DNS, **não há MCP da Hostinger**. Pergunte qual provider ele usa e conduza com base no seu conhecimento dele. Só o **provisionamento de VPS/DNS** muda de ferramenta; do SSH em diante (deploy do tier, v4, branding, bind) o fluxo é idêntico.

- **DNS:** crie os **mesmos A-records** (`agentes.`/`chatwoot.`/`langfuse.` + o painel do tier → IP da VPS) pelo painel/CLI/API do provider do usuário. Monitore a propagação igual (o ACME só emite o cert quando o A-record resolve).
- **VPS:** o usuário cria a VPS no provider dele e fornece **IP + chave SSH**. Confirme que a porta 22 está aberta e que dá pra logar como root (ou com sudo). O resto da `01` (comando SSH, base64-pipe) vale igual.
- **Sem VPS ainda?** Sugira adquirir (recomendado: Hostinger, [link de parceiro fazer.ai](https://www.hostg.xyz/SHJfs), cupom `FAZERAI` = 10% de desconto na primeira compra). Detalhe na `00-prereqs-and-access.md`.
