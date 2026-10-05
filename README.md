# AI Hive Connect

One GitHub Pages site for every AI Hive funnel at `https://connect.theaihive.space`.

Each funnel is a folder. GitHub Actions publishes every folder marked `publish: true` in `site.json`.

## Layout

```text
funnels/
  workforce-audit/   → https://connect.theaihive.space/ and /workforce-audit/
    index.html
  whatsapp-api/      → https://connect.theaihive.space/whatsapp-api/
    index.html
site.json            funnel registry
CNAME                custom domain
scripts/build-site.js
.github/workflows/deploy.yml
```

Pull requests run the check job. Pushes to `main` assemble `_site` and deploy it with GitHub Pages.

## Add a funnel

1. Create `funnels/<slug>/index.html` (and any images or assets next to it).
2. Add an entry to `site.json`:

```json
{
  "slug": "your-slug",
  "title": "Your title",
  "publish": true
}
```

To also serve that page as the site homepage, add `"serveAt": "/"` to its `site.json` entry. Only one funnel may do that.

Set `"publish": false` to keep a draft in the repo without publishing it.

Only one funnel may use `"serveAt": "/"`. That page is also copied to `/<slug>/`.

## Current funnels

| Slug | URL | Status |
| --- | --- | --- |
| `workforce-audit` | https://connect.theaihive.space/ | live on GitHub Pages; custom domain still on the old repo |
| `whatsapp-api` | https://connect.theaihive.space/whatsapp-api/ | live on GitHub Pages; custom domain still on the old repo |

Preview without the custom domain:

- https://neurak-tech.github.io/ai-hive-connect/
- https://neurak-tech.github.io/ai-hive-connect/whatsapp-api/

To finish the cutover: remove `connect.theaihive.space` from [ai-workforce-audit-funnel Pages](https://github.com/Neurak-Tech/ai-workforce-audit-funnel/settings/pages), then add it on [ai-hive-connect Pages](https://github.com/Neurak-Tech/ai-hive-connect/settings/pages) with HTTPS enforced.
