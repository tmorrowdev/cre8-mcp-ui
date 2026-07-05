# Vendored, self-contained UI assets

The MCP App shell inlines these files so the sandboxed iframe makes **zero
external network requests** — no CDN, so no dependency on the host sandbox
allowing `cdn.jsdelivr.net` / `esm.sh` in its CSP. This is what makes the app
render reliably inside strict hosts (e.g. claude.ai), where external loads may
be blocked regardless of the resource's `_meta.ui.csp` hints.

| File | Source | Purpose |
| --- | --- | --- |
| `cre8-wc.min.js` | `@tmorrow/cre8-wc@2.0.4` (only the components used) | Registers the form + dashboard components: `cre8-card`, `cre8-field`, `cre8-button`, `cre8-list`, `cre8-list-item`, `cre8-inline-alert`, `cre8-heading`, `cre8-badge`, `cre8-grid`, `cre8-grid-item`, the `cre8-table*` family, `cre8-divider`, and `cre8-chart` (bundles Chart.js) |
| `ext-apps.globalized.js` | `@modelcontextprotocol/ext-apps@1.7.4/app-with-deps` | MCP Apps `App` bridge; its `export {…}` is rewritten to `globalThis.__cre8ExtApps = {…}` so an inline module can expose it without a dynamic `import()` (no `blob:` needed in the CSP) |
| `tokens.css` | `@tmorrow/cre8-wc@2.0.4` `lib/design-tokens/brands/cre8-a2ui/css/tokens_brand.css` | The `:root` `--cre8-*` design tokens |

## Regenerate

```bash
cd cre8_mcp_ui/assets/vendor
npm init -y
npm install @tmorrow/cre8-wc@2.0.4 esbuild@0.24 @modelcontextprotocol/ext-apps@1.7.4
node build.mjs            # -> cre8-min.js (rename to cre8-wc.min.js)
# ext-apps.globalized.js: take node_modules/@modelcontextprotocol/ext-apps/dist/src/app-with-deps.js
# and rewrite its trailing `export{…}` into `globalThis.__cre8ExtApps={…}`.
# tokens.css: copy node_modules/@tmorrow/cre8-wc/lib/design-tokens/brands/cre8-a2ui/css/tokens_brand.css
```

`build.mjs` bundles only the used components and includes a plugin that handles
cre8-wc's `?raw` SVG imports and their case-sensitivity (the package imports
`Add.svg` but ships `add.svg`, which only breaks on case-sensitive filesystems).
