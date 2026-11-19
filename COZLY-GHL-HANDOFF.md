# Cozly GHL — Handoff (Nov 19, 2026)

Paste this into a new Cowork / desktop Claude Code session to pick up cold.

---

## Context

Marc runs Cozly Media. Meta ads -> `apply.cozlymedia.com` funnel -> GoHighLevel books a
sales call. **Markuss Boyd is the closer and takes all sales calls.** Marc takes client
and onboarding calls.

GHL Location ID: `hk1aNvq7l95EzYuX7141`

| Person | GHL user ID | Email |
|---|---|---|
| Marc Hera | `NL4sngzyU6myMVssrcfK` | info@cozlymedia.com |
| Markuss Boyd | `Chw27Pvkgbv43kDLCZ6m` | markuss@cozlymedia.com |

---

## The bug we just fixed

**Symptom:** Bookings produced alerts and contact records but **no appointment**.

**Cause:** The `#1 Book appointment` action in workflow **Cozly Funnel: New Lead** had
**Team Member blank**. GHL fell back to the account owner (Marc). Marc had been removed
from the calendar team when the owner changed to Markuss. GHL returned:

```
Internal Action Error - [HTTP 422] The user id not part of calendar team.
```

The step logged as **Skipped**, not Failed, so nothing looked broken.

**Blast radius:** 6 failures, Nov 15 5:28pm -> Nov 18 4:16pm.
Clarice Johnson, Delores Amison, LaDonna Shaw-Wragg, Lulu, Dana Whitfield,
plus one Markuss test. **Only Clarice was rescued** — Marc said skip the rest.

**Fix applied:** Team Member pinned explicitly to **Markuss Boyd**. Published.

**Second cause found:** Markuss had **no Google Calendar connected** to GHL.
Meet links are generated from the assigned user's Google account, so bookings
assigned to him produced no Meet link AND no availability sync. Marc connected it
on Nov 18. Verify it is still connected.

---

## Calendars

| Calendar | ID | Length | Team | Slug | Purpose |
|---|---|---|---|---|---|
| Cozly Media - Growth Plan | `lVN0gspXw8iYaWja2km9` | 45 min | Markuss | `cozly-consult` | Meta ads -> sales. Wired to funnel + Worker. **Do not repoint.** |
| Cozly Media - Client Calls | `kdFA5baxLRm2Yo18zCtQ` | 30 min | Marc | `cozly-client-call` | Onboarding + client calls. Created Nov 18 via API. |

Client Calls config: Mon-Fri 09:00-16:00, hourly slots, max 6/day, 3h lead time,
bookable 14 days out, Google Meet, auto-confirm. **Notifications not yet verified** —
Marc has previously had GHL send emails branded "Hera Solutions". Check before use.

---

## Open items

1. **Clarice Johnson** — appt `1sRscaYgHfIEWMLzfy7M`, Thu Nov 19 3:00-3:45pm MT,
   assigned Markuss, Meet link `https://meet.google.com/dhn-jake-vok`.
   Her confirmation SMS went out with a **blank** Meet link (sent 1 min after
   creation, before the link existed). Confirm Marc resent it.
2. **Is the blank-link race general?** Open Jennifer Anyanwu's or Matti's conversation
   and check whether their "here's your Google Meet link" SMS carried a link.
   If blank, real prospects have been getting dead texts.
   Proposed hardening: add **Wait 2 minutes** at the top of `Cozly Funnel: Booked`
   before the SMS.
3. **Nov 19's other 4 appointments are assigned to Marc**, not Markuss —
   Elie 9:00, Rahma 12:00, Matti 13:00, Jennifer 16:00. Reassigning may
   regenerate Meet links and invalidate invites already sent. Recommendation was
   to leave them with Marc and let Markuss start clean from Nov 20.
4. **Run one real test booking** through apply.cozlymedia.com and confirm the
   appointment lands WITH a Meet link. Not yet done.
5. **Messaging mismatch** — confirmation SMS says "Marc here from Cozly Media"
   but appointments are assigned to Markuss and the invite title reads
   "& Markuss | Growth Plan".
6. **Many strikethrough (cancelled/no-show) appointments** Nov 15-18. Worth a
   look at show-rate separately.
7. **Delete the `Claude Ops` Private Integration token** once API work is done —
   it was pasted into a chat transcript.

---

## Hard limits

- **GHL has no workflow API.** Workflow edits are dashboard-only, always.
- Appointments created via API (`source: third_party`) do **not** reliably get a
  Meet link at creation; GHL backfills it later.
- The funnel's free slots come from a Cloudflare Worker (`cozly-slots`) holding a
  GHL token and reading `CALENDAR_ID` = the Growth Plan calendar.
