# Cozly slots proxy

Gives the funnel page GoHighLevel's real calendar availability.

## Why

`index.html` is a static page on `cozlymedia.com`. It cannot ask GHL for
availability directly:

- GHL's API needs a private token, which must never appear in page source.
- GHL sends no CORS headers, so a browser on another origin is refused.

Without this Worker the page generates slots from fixed rules written in
its own config. That works, but the rules and the GHL calendar are two
separate copies of the same truth, and they drift: block a day in GHL and
the funnel keeps offering it, so a prospect books a slot that never
becomes an appointment.

With this Worker, GHL is the only source of truth. Change hours, block a
day, take a booking — the funnel reflects it on the next page load.

## Setup

1. **GHL token.** Settings → Private Integrations → create one with
   calendar read scope. Copy the token.

2. **Deploy.**
   ```bash
   cd cozly/worker
   npx wrangler login
   npx wrangler secret put GHL_TOKEN     # paste the token
   npx wrangler deploy
   ```
   Wrangler prints a URL like `https://cozly-slots.<you>.workers.dev`.

3. **Check it.** In a browser:
   ```
   https://cozly-slots.<you>.workers.dev/?days=21
   ```
   Expect `{"ok":true,"count":N,"slots":[...]}`. If `ok` is false, add
   `&debug=1` to see GHL's own response.

4. **Point the page at it.** In `index.html`:
   ```js
   slotsApi: "https://cozly-slots.<you>.workers.dev/",
   ```

5. **Lock down origins.** In `wrangler.toml`, `ALLOWED_ORIGINS` must list
   the domains serving the funnel. Redeploy after changing it.

## Fallback

If the Worker is unreachable, errors, or returns no slots, the page
silently falls back to the rules in `CONFIG.calendar`. A Worker outage
degrades the page, it never breaks it. So keep those rules roughly
accurate even after the Worker is live.

## Config

| Where | Name | Purpose |
|---|---|---|
| `wrangler.toml` | `CALENDAR_ID` | Which GHL calendar to read |
| `wrangler.toml` | `TIMEZONE` | Zone your availability is defined in |
| `wrangler.toml` | `ALLOWED_ORIGINS` | Domains allowed to call the Worker |
| secret | `GHL_TOKEN` | Private Integration token. Never commit this |

## Notes

- Responses are cached 30 seconds, so a change in GHL can take that long
  to appear. Raise it if you hit GHL rate limits.
- The Worker only reads. It cannot create or change appointments; the
  booking itself still goes through the webhook into a GHL workflow.
- `extractSlots` walks whatever JSON GHL returns and pulls out anything
  that parses as a timestamp, rather than assuming one response shape,
  because the shape has changed between API versions.

## Deploying the page

Cloudflare Pages project `cozly-apply`, serving `apply.cozlymedia.com`,
builds from this repo: branch `claude/marketing-agency-website-kkc8qh`, no
build command, output directory `cozly`. That is why the page is named
`index.html` — Pages serves the index of the output directory. Pushing to
that branch deploys it; nothing is uploaded by hand.

The Worker is separate and still manual: paste `slots-worker.js` into the
Cloudflare dashboard and deploy. Its `GHL_TOKEN` is a Cloudflare secret and
is never in this repo.
