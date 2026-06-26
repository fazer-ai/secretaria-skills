# 07: Branding via MCP (nome + cores + logo/favicon)

> Branding é **fleet-level** (GLOBAL, não por-tenant), gateado a SUPER_ADMIN (`mcp:admin`), dry-run por padrão. Duas tools: `branding_set` (nome + cores) e `branding_asset_set` (logo/favicon).

## Pré-condição

`BRANDING_STORAGE_DIR` apontando pro volume `storage` (etapa 4, já no compose). Sem isso, logo/favicon somem no redeploy.

## Nome + cores (`branding_set`)

```jsonc
// nome do usuário (passo 1); cores no PADRÃO (recomendado) = NÃO passar color_mode/brand_color
branding_set { "brand_name": "<nome de exibição do usuário>" }            // dry_run:true → preview, depois dry_run:false
```

- `brand_name`: nome white-label (título + rodapé de auth; `null` = default).
- Cores (opcional, só se o usuário pedir): `color_mode:"SIMPLE"` + `brand_color:"#rrggbb"` (paleta derivada), ou `color_mode:"ADVANCED"` + `tokens_light`/`tokens_dark`.

## Logo + favicon (`branding_asset_set`): sem round de UI

O agente lê o arquivo no PC do usuário (Claude Code lê arquivos locais), base64-encoda e sobe:

```jsonc
branding_asset_set {
  "kind": "logo",            // ou "favicon"
  "variant": "dark",         // um variant basta: fallback por tema
  "content_base64": "<bytes do arquivo em base64>",   // prefixo data: é tolerado
  "mime": "image/png"        // png | jpeg | webp | svg+xml | x-icon
}                            // dry_run:true → preview, depois dry_run:false
```

- Caps: logo **1 MB**, favicon **512 KB**.
- Via MCP não há o sniff de magic-bytes do upload multipart, então **SVG passa** (servido sandboxed).

## Refino opcional (UI)

`/admin/branding` tem cropper + preview + PUT multipart, pra ajustar recorte/variante por tema. É refino, não pré-requisito.
