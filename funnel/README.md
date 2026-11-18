# Per-client funnels

One funnel, many clients. A fix to the funnel is one edit to
`template.html` and reaches every client on their next build.

```
funnel/template.html     the funnel: markup, styles, behaviour. Shared.
funnel/build.py          template + client JSON -> dist/<slug>/index.html
clients/<slug>.json      what differs per client, and nothing else
dist/<slug>/index.html   generated, not committed
```

## Building

```
python3 funnel/build.py                  # every client
python3 funnel/build.py homecareaide     # one client
python3 funnel/build.py --draft homecareaide   # render TODOs too, to look at locally
```

No packages to install; the script uses the standard library only.

## Deploying (Cloudflare Pages)

One Pages project per client, all building from this repo and branch:

| Setting | Value |
|---|---|
| Build command | `python3 funnel/build.py` |
| Build output directory | `dist/<slug>` |
| Custom domain | the client's, e.g. `homecareaide.cozlymedia.com` |

Every project builds every client, which takes well under a second, and
serves only its own folder.

## TODO values block a client, not the build

Any string in a client's JSON that contains `TODO` marks a value we don't
have yet. That client is **skipped**: `dist/<slug>` is never written, so its
Pages build fails and the previous deploy stays live. Other clients still
build. A half-filled page never reaches an ad.

A config that is *wrong* rather than incomplete -- a question routing to a
disqualify screen that doesn't exist, an `http://` webhook, a bad colour --
fails the whole build, because that is a bug.

## What goes in a client's JSON

Only what differs between clients. If you find yourself wanting to change
how something *works* for one client, change the template for everyone, or
add a config value that the template reads.

| Key | What it is |
|---|---|
| `slug` | Must match the filename. Also the sessionStorage prefix. |
| `agency`, `domain` | Business name (logo alt text, iframe title), live domain. |
| `meta` | `<title>` and description. |
| `brand` | `logoUrl` (https URL, or a file under `clients/` that gets copied next to the page), optional `logoHeight` in px (for a tall logo with the name inside it; default 34-48px by screen width), text `wordmark`/`wordmarkSub` shown until the logo loads, `faviconLetter`. |
| `theme` | Six colours. Defaults are the Cozly palette. |
| `phone` | `{"display": "(707) 555-0100"}` or `null`. Shows a "Prefer to talk?" line on the landing, calendar, thank-you and disqualify steps. |
| `media` | `vsl`, `thankYou`: `.mp4` URL, embed markup, or `""` for none. An empty one is removed from the page, not shown as a placeholder. |
| `copy` | Every visible sentence. Strings are HTML (`&amp;`, `<u>`), so they may carry markup. `{agency}` and `{phone}` are written in from `agency` and `phone` at build time. `copy.form.subhead`, `copy.thankYou.subhead`, `copy.thankYou.stepsHead` and `copy.disclaimer` may be `""`, which leaves that line off the page. |
| `startWithQuestions` | `true` drops the landing screen: the visit opens on question 1, with `copy.vsl` eyebrow/headline/subhead above it, and bounced deep links land there. `copy.vsl.cta` isn't used and `media.vsl` must be `""`. Default `false`. |
| `showQuestionCount` | `true` shows "2 of 4" under each question's options. Default `false`. |
| `questions` | The qualifying questions in order. Each `{key, title, options}`; an option with `"dq": "<key>"` routes to that disqualify screen, otherwise it moves on. `key` is the answer's name; the CRM gets the question text and option label. |
| `disqualify` | One screen per reason: `{key: {title, body: [paragraphs]}}`. |
| `form.extraField` | Optional fourth field after name/email/phone, e.g. Cozly's `company`. Its `key` is also the webhook payload key. Optional `pattern` (a regex the value must match; otherwise 2+ characters), `inputmode`, `maxlength`. `null` for none. |
| `form.consent` | `{label, error}`: a consent checkbox, unticked by default and required to submit. The payload gets `consent: true` and `consent_text` (the label as plain text). `null` for none. |
| `serviceArea` | `{field, zips, dq}`: after submit, the ZIP typed into the extra field (`field` must be its key) is checked against `zips`. Outside it, the lead is still posted with `in_service_area: false`, no pixel `Lead` fires, and the visitor ends on the `dq` screen instead of the thank-you. `null` for no check. |
| `calendar` | GHL calendar `id`, its `timezone`, and the fallback rules (see below). `null` for no calendar: the form goes straight to the thank-you and the client calls the lead back. `copy.calendar` is then not needed. |
| `slotsApi` | The slots Worker URL, or `""` to use the rules only. |
| `webhookUrl` | GHL inbound webhook. Gets `event: "lead"` on form submit and `event: "booking"` on confirm. |
| `funnelMeta` | `source`/`funnel`/`funnel_slug` stamped on every webhook post. |
| `pixelId` | Meta pixel, or `""` for none. |
| `_notes` | Free text for humans. Never shipped. |

### Calendar

`calendar.timezone` is the **GHL calendar's** zone, not necessarily the
client's. GHL's Book appointment action reads `booking_time_ghl` as wall
clock in that zone, and the fallback hours are written in it too.

Leave `utcOffsetHours` as `null` for any zone that changes its clocks
(Pacific does). Pinning exists only for a zone that stopped changing
before browsers' timezone data caught up, as Alberta did for Cozly.

The rules (`days`, `startHour`, `endHour`, `durationMin`,
`slotIntervalMin`, `bookUpTo`, `leadTimeMin`, `blockedDates`) must match
the GHL calendar's own settings. They are only used when the slots Worker
is missing or fails, but then they are what visitors book against, and a
slot GHL doesn't have never becomes an appointment.

## Fixes the template carries -- read before changing

These were found the hard way on the live Cozly funnel. Each has a comment
at the spot.

- **Back-button booking lock** (`show()`): once booked, every step
  redirects to the thank-you, or Back lands on a live calendar and a second
  confirm books twice. Without a calendar it locks once the lead is in,
  on whichever screen ended the visit (thank-you or out-of-area).
- **`[hidden] { display: none !important }`**: without `!important`, any
  rule that sets `display` silently un-hides the element.
- **Pinned-offset clock handling** (`usePinnedDisplay()`): a visitor inside
  a pinned zone whose device still has the old DST rule is shown the clock
  the appointment is actually made on.
- **Adaptive day strip** (`buildDays()`): if the Worker has nothing in the
  next seven days the strip slides to the first open day instead of
  showing a dead week.
- **Double-tap guard** (option clicks): an option only counts on the
  visible step, and not in its first 350ms, so a double-tap can't answer
  the next question too.

## Testing

Drive the built page in headless Chromium with the webhook and slots
Worker stubbed (request interception), and check the posted payloads
rather than reasoning about them. Cover: each disqualify route, form
validation, deep links (`#form`, `#calendar`, ... on load and mid-visit),
rapid clicks on options/submit/confirm, Back after booking, the Worker
unreachable / erroring / timing out / returning nothing, several visitor
timezones against the calendar's, DST boundaries in rules mode, and
360px / 390px / desktop for horizontal overflow and console errors.
