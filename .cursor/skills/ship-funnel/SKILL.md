---
name: ship-funnel
description: Adds conversion events to a funnel folder, then checks and runs ./ship to publish it. Use when the user says ship funnel, drop a funnel, publish a funnel, add tracking to a funnel, or run ship.
---

# Ship Funnel

Project skill for AIHive Funnels. One folder under `funnels/` becomes `https://connect.theaihive.space/<folder-name>/`. The site root redirects to https://theaihive.io/.

## Do this

1. Identify the funnel folder. Prefer the path the user named. Otherwise use a folder just dropped on the repo root, or `funnels/<slug>/`.
2. Read this skill, then run ship. Do not hand-edit tracking snippets, pixels, or analytics IDs.
3. Conversion events are added by `./ship` (forms, `cta` / `data-cta`, WhatsApp, Calendly, `tel:`, `mailto:`). If the page is missing any of those, ship injects them. Replace placeholder WhatsApp, phone, email, and Calendly URLs in `funnel.json` when the user supplies real ones.
4. Check, then publish:

```bash
./ship path/to/folder
```

If the folder is already in `funnels/<slug>/`:

```bash
./ship funnels/<slug>
```

`./ship` moves the drop into `funnels/`, fills `index.html` / `app.js` / `style.css` / `funnel.json`, injects `/shared/bootstrap.js`, adds missing conversion events, runs protection and the conversion audit, assembles `_site`, commits, and pushes `origin`. GitHub Actions deploys Pages from `main`.

5. If protection fails, fix the funnel (restore bootstrap, do not paste vendor pixels) and run `./ship` again. Never commit analytics ID changes unless `rules/analytics-lock.json` matches and the commit message includes `Analytics-Lock-Update: approved`.
6. Confirm the live URL: `https://connect.theaihive.space/<slug>/`. Preview without the custom domain: `https://neurak-tech.github.io/ai-hive-connect/<slug>/`.

## Do not

- Add `gtag`, `fbq`, GTM, Clarity, or LinkedIn snippets to a funnel. Bootstrap loads those from `shared/config.json`.
- Serve a funnel at `/`. `/` always redirects to theaihive.io.
- Skip `./ship` after editing a dropped folder.
