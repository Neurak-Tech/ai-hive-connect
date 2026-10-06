# AIHive Funnels

AIHive Funnels publishes one static page per folder. A folder at `funnels/<folder-name>` becomes:

`https://connect.theaihive.space/<folder-name>/`

The hostname is lowercase because DNS is. The brand name stays AIHive. There is no build step and no framework. GitHub Actions copies each funnel to the site root and deploys that folder to GitHub Pages.

`https://connect.theaihive.space/` redirects to [theaihive.io](https://theaihive.io/). Funnels are only served at `/<folder-name>/`.

`funnels/strategy-session` is the reference funnel. `funnels/whatsapp-api` and `funnels/workforce-audit` are live offers. WhatsApp, phone, email, and calendar links added by ship are placeholders until you replace them.

## One-shot: drop a folder and ship

Drop the funnel folder onto this project (the repo root, or `funnels/`), then run:

```bash
./ship
```

The script:

1. Moves a root-level drop into `funnels/<folder-name>/` and slugifies the name (`My Offer` becomes `my-offer`).
2. Creates any missing `index.html`, `app.js`, `style.css`, and `funnel.json`.
3. Injects `/shared/bootstrap.js` plus the `style.css` and `app.js` links if they are missing.
4. Adds any missing conversion events (form, CTA, WhatsApp, Calendly, phone, email).
5. Runs protection, the conversion audit, and a local assemble.
6. Commits and pushes to `origin`. GitHub Actions deploys Pages from `main`.

Or pass the folder:

```bash
./ship ~/Desktop/my-offer
./ship ~/Desktop/my-offer --slug waitlist
./ship --no-push
./ship --no-git
```

This repository is not a git remote yet. After `./ship` creates the first commit:

```bash
git remote add origin git@github.com:<owner>/aihive-funnels.git
git push -u origin main
```

Later drops only need `./ship`.

## Create a new funnel

1. Create `funnels/<folder-name>/`. Use lowercase letters, numbers, and hyphens. The folder name is the URL.
2. Add these three files:

`index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Offer name — AIHive</title>
  <meta name="description" content="One sentence that says what this page asks the visitor to do.">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main>
    <h1>Offer name</h1>
    <p><a class="cta" href="#request">Request it</a></p>
    <form id="request" novalidate>
      <label for="email">Email</label>
      <input id="email" name="email" type="email" required>
      <button type="submit">Send</button>
    </form>
  </main>
  <script src="/shared/bootstrap.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

`app.js` can be only the behavior this page needs. `style.css` is the page's own stylesheet. Both have to be linked from `index.html`.

3. Add the bootstrap script and no other analytics or pixel snippets:

```html
<script src="/shared/bootstrap.js"></script>
```

4. Optional `funnel.json` in the same folder controls the title, description, and form delivery:

```json
{
  "title": "Offer name — AIHive",
  "description": "One sentence that says what this page asks the visitor to do.",
  "image": "",
  "formAction": "",
  "formMethod": "POST"
}
```

`image` is optional. Use a root-relative path such as `/offer-name/og.png` or a full `https://` URL. A 1200×630 PNG is what social crawlers expect. Leave `formAction` empty until you have an endpoint that should receive the form. A full URL posts the form there after the conversion event is sent. With an empty action, the reference page records the request in the browser and tells the visitor to use WhatsApp, phone, or the calendar.

5. Put the conversion actions in the HTML. The tracker reads the markup. You do not call a tracking function yourself.

| Action | How to mark it | Event |
| --- | --- | --- |
| Form | a `<form>` | `form_submit` |
| Call to action | `class="cta"` or `data-cta` on a link or button | `cta_click` |
| WhatsApp | `href` containing `wa.me`, `api.whatsapp.com`, or `whatsapp.com/send` | `whatsapp_click` |
| Calendar | `href` containing `calendly.com` | `calendly_click` |
| Phone | `href` starting with `tel:` | `phone_click` |
| Email | `href` starting with `mailto:` | `email_click` |

A submit button inside a form is counted as `form_submit`, not as a second click. Add `data-track-ignore` to a link that should not count, such as a logo back to the route list. Add `data-honeypot` to a hidden field that spam bots fill. A filled honeypot is not tracked.

Title and description priority is `funnel.json`, then the `<title>` and meta description already in the HTML, then the fallbacks in `shared/config.json`.

## Deploy a funnel

Push the folder to `main`.

1. `Protect funnels` rejects the push if bootstrap, pixels, or conversion tracking were removed, or if analytics IDs changed without the approval trailer.
2. `Audit conversion registry` reads the changed funnel and updates `registry/conversion-status.json`.
3. `Deploy GitHub Pages` copies `funnels/<folder-name>` to `/<folder-name>/` in the published site, copies `/shared/`, writes `funnels.json` and `sitemap.xml`, and deploys the artifact.

The page is then live at `https://connect.theaihive.space/<folder-name>/`.

Before the first deploy, in the GitHub repository:

1. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
2. Add a DNS CNAME record: `connect` points at `<github-owner>.github.io`.
3. The `CNAME` file in this repository sets the Pages hostname to `connect.theaihive.space`.

This has to be served from the domain root. Absolute paths such as `/shared/bootstrap.js` do not resolve on a project site URL like `username.github.io/repo-name/`.

Preview the same layout locally:

```bash
python3 scripts/assemble-site.py
python3 -m http.server 8080 --directory _site
```

Open `http://127.0.0.1:8080/` and `http://127.0.0.1:8080/strategy-session/`. Serving the repository root instead of `_site` keeps funnels under `/funnels/<folder-name>/`. Bootstrap still loads, and canonical URLs strip that `/funnels` prefix so they match production.

## Tracking architecture

A funnel includes one script. `shared/bootstrap.js` loads `shared/config.json`, then optional `funnel.json`, then these files in order:

1. `shared/meta.js` sets the title, description, canonical URL, Open Graph tags, and Twitter tags.
2. `shared/analytics.js` loads GA4, Google Tag Manager, and Microsoft Clarity when their IDs are set, and defines `AIHIVE.track`.
3. `shared/pixels.js` loads the Meta Pixel and the LinkedIn Insight Tag when their IDs are set, and forwards each event to those pixels.
4. `shared/conversion-tracker.js` listens for forms, CTA controls, WhatsApp, Calendly, phone, and email, and fires the events above.

Empty IDs are off. An ID that does not match the expected shape is ignored and a warning is written to the console. The page still loads.

`AIHIVE.track` sends three copies of each event:

- `dataLayer` for Google Tag Manager
- `gtag` when GA4 created it
- `clarity("event", ...)` when Clarity is loaded

Meta standard events are `Lead` for a form, `Schedule` for Calendly, and `Contact` for a CTA, WhatsApp, phone, or email. LinkedIn conversion IDs are per event, under `linkedinConversions` in `shared/config.json`. An empty LinkedIn conversion ID still loads the Insight Tag page view, and skips the conversion call.

If both `ga4` and `gtm` are set, and the Tag Manager container also fires GA4, page views are counted twice. Use Tag Manager or the GA4 field, not both, unless you intend both hits.

Set `"debug": true` under `tracking` in `shared/config.json` to log each event. The last 50 events are also on `window.AIHIVE.events`. Debug is not an analytics ID, so changing it does not require the approval trailer.

The registry at `registry/conversion-status.json` stores one object per funnel:

| Field | Meaning |
| --- | --- |
| `funnel` | Folder name |
| `status` | `tracked`, `no_conversions`, `missing_bootstrap`, or `bypass` |
| `events` | Conversion events found in the HTML, JS, and `funnel.json` |
| `last_scan` | UTC time of the last audit of that folder |
| `signals` | How many times each event pattern matched |

The homepage reads `/funnels.json` and this registry after deploy and lists every route.

Social crawlers that do not run JavaScript still see titles and Open Graph tags. The deploy step writes those tags into the published HTML from `funnel.json` and `shared/config.json`. `meta.js` sets the same tags again in the browser.

## Adding analytics IDs

IDs live in `shared/config.json`:

```json
{
  "analytics": {
    "ga4": "G-XXXXXXXX",
    "gtm": "GTM-XXXXXXX",
    "metaPixel": "123456789012345",
    "linkedinPartnerId": "1234567",
    "clarity": "abcdefghij"
  },
  "linkedinConversions": {
    "form_submit": "",
    "cta_click": "",
    "whatsapp_click": "",
    "calendly_click": "",
    "phone_click": "",
    "email_click": ""
  }
}
```

Accepted shapes:

| Key | Shape |
| --- | --- |
| `ga4` | `G-` plus letters and digits |
| `gtm` | `GTM-` plus letters and digits |
| `metaPixel` | 5 to 20 digits |
| `linkedinPartnerId` | 5 to 12 digits |
| `clarity` | letters and digits |
| each LinkedIn conversion | digits, or empty |

An empty string leaves that product unloaded.

These values are locked. `rules/analytics-lock.json` must contain the same `analytics` and `linkedinConversions` objects. A pull request or push that changes an ID fails `Protect funnels` until both files match and the commit message contains this trailer on its own line:

```text
Analytics-Lock-Update: approved
```

Example:

```bash
git commit -m "Point GA4 at the production property

Analytics-Lock-Update: approved"
```

Install the local hook so the same check runs before the commit is created:

```bash
git config core.hooksPath rules/git-hooks
```

Require the `Protect funnels` check in branch protection so a local `--no-verify` cannot merge.

Site name, domain, default title, description, locale, and Twitter handle are in `shared/config.json` under `site`. Those fields are not locked.

## Troubleshooting

**The new folder 404s.** The folder needs `index.html`. The workflow deploys only pushes to `main`. In GitHub, the Pages source must be GitHub Actions, and DNS for `connect` must point at the GitHub Pages host. The public path is `/<folder-name>/`, not `/funnels/<folder-name>/`.

**Styles or `app.js` do not load.** Link them as `style.css` and `app.js` from the funnel folder. Do not prefix those two with `/shared/`.

**`/shared/bootstrap.js` 404s locally.** You are not serving the repository root or the assembled `_site` directory. Open the site from one of those two roots.

**A conversion does not appear in analytics.** Confirm the markup matches the table above. Confirm the ID is non-empty and matches the shape. Turn on `tracking.debug` and inspect `window.AIHIVE.events` in the console. Ad blockers drop GA4, Tag Manager, Meta, LinkedIn, and Clarity even when the event is recorded locally. Submit buttons are `form_submit` only. Invalid forms are not tracked.

**The form says it stayed in the browser.** `formAction` in `funnel.json` is empty. Set it to the endpoint that should receive the POST. The conversion event still fires without that endpoint.

**The protection check rejected an ID edit.** Copy the new IDs into `rules/analytics-lock.json` in the same commit and add the trailer `Analytics-Lock-Update: approved`.

**The protection check says bootstrap or a pixel marker is missing.** Every funnel `index.html`, plus the site `index.html` and `404.html`, must include `/shared/bootstrap.js`. `shared/bootstrap.js` must still load `meta.js`, `analytics.js`, `pixels.js`, and `conversion-tracker.js`. Do not paste `gtag`, `fbq`, Tag Manager, Clarity, Meta, or LinkedIn snippets into a funnel. That is treated as a bypass, along with `AIHIVE_DISABLE_TRACKING` and `data-aihive-bypass`.

**The registry did not update.** The audit workflow runs when files under `funnels/` change. It needs permission to push to the branch. A registry-only commit does not scan again.

**Page views doubled.** GA4 is set in `shared/config.json` and the Tag Manager container also sends GA4. Clear one of them.

**The route list is empty locally.** `funnels.json` is created by `python3 scripts/assemble-site.py`. It is not stored in the repository.

## Repository map

```text
funnels/                 one folder per live URL
shared/                  bootstrap, meta, analytics, pixels, conversion tracker, config
rules/                   lock file, policy, git hook
registry/                conversion-status.json
scripts/                 assemble, audit, and protection checks
.github/workflows/       validate.yml, audit.yml, deploy.yml
```

Local checks:

```bash
python3 scripts/validate-protection.py
python3 scripts/audit-funnels.py --all
python3 scripts/test-rules.py
```
