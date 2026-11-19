# Cozly GHL — Build Spec (Nov 19, 2026)

Three pieces of work, specified to be built in the GHL dashboard.
**GHL exposes no workflow or pipeline API** — all of this is dashboard-only.

Decisions already made by Marc:
- SMS name swap: **sales-side only** (client/onboarding messaging stays "Marc")
- Cold pipeline: **4 stages**
- Cold leads: **fully separate** from Meta ad automations
- No-show: **3 touches over 48 hours**, **Growth Plan calendar only**
- Dialing: **GHL built-in dialer**
- Cold pipeline sends **no SMS** (CASL — list has not opted in)
- **One phone number** for the whole account

Reference IDs:
| | |
|---|---|
| Location | `hk1aNvq7l95EzYuX7141` |
| Marc Hera | `NL4sngzyU6myMVssrcfK` |
| Markuss Boyd | `Chw27Pvkgbv43kDLCZ6m` |
| Growth Plan calendar (sales) | `lVN0gspXw8iYaWja2km9` |
| Client Calls calendar (Marc) | `kdFA5baxLRm2Yo18zCtQ` |

---

# PART 1 — Swap sales SMS from Marc to Markuss

Scope: every SMS in **Cozly Funnel: New Lead** and **Cozly Funnel: Booked**.
Do **not** touch messaging for the Client Calls calendar or onboarding.

### Rewritten copy

**First touch** (New Lead workflow, "Lead" branch):
```
Hey {{contact.first_name}}, Markuss here from Cozly Media. Saw you requested
info on getting more private pay families for your agency. I'll be reaching
out shortly!
```

**Booking confirmation** (Booked workflow):
```
Hi {{contact.first_name}}, it's Markuss from Cozly Media. You're booked for
{{appointment.start_time}}.

Here's your Google Meet link:
{{appointment.address}}
```

**Rule for any other sales SMS:** replace "Marc" with "Markuss". Leave the
company name, the offer language and the merge fields exactly as they are.

### Also check
- Calendar invite title already reads `{{contact.name}} & Markuss | Growth Plan` — correct, leave it.
- Internal notification actions name Markuss as recipient where relevant.
- Any email templates carrying "Marc" on the sales side.

---

# PART 2 — Automation audit

Run this before building anything new. A second calendar now exists, which
changes the blast radius of every unfiltered appointment trigger.

1. **Calendar leakage.** List every workflow with an appointment trigger and
   record whether it is filtered to a specific calendar. Any trigger NOT
   filtered will now also fire on **Client Calls** bookings — meaning
   onboarding clients could receive "Private-Pay Plan Call" messaging.
   Every sales workflow must filter to `Cozly Media - Growth Plan`.

2. **Meet link race.** Open the conversations for **Jennifer Anyanwu** and
   **Matti** and check whether their "here's your Google Meet link" SMS
   rendered a link or came through blank. If blank, real prospects have been
   receiving dead texts.
   **Hardening regardless of result:** add a **Wait 2 minutes** step at the top
   of `Cozly Funnel: Booked`, before the SMS. GHL may attach the Meet link
   asynchronously after the appointment is created; two minutes removes the race
   permanently at negligible cost.

3. **Book appointment action.** Confirm Team Member is still pinned to
   **Markuss Boyd**, not blank. Blank falls back to the account owner and
   throws HTTP 422 if that user is not on the calendar team.

4. **Client Calls notifications.** Calendars -> Cozly Media - Client Calls ->
   Notifications. This account has previously sent mail branded "Hera
   Solutions". Verify before the calendar goes into use.

5. **Markuss's Google Calendar** is still connected (Calendars -> Connections ->
   My staff: Markuss Boyd). If it disconnects, bookings silently lose their
   Meet links and availability sync.

---

# PART 3 — Cold-call pipeline

1,000 leads, imported by Marc, dialed by Markuss through the GHL built-in dialer.
**No SMS in this pipeline** — the list has not opted in, and cold texting under
CASL risks penalties plus carrier filtering that would damage the funnel's
deliverability on the same number.

### Pipeline: `Cold Outreach - Markuss`

| # | Stage | How a lead gets here |
|---|---|---|
| 1 | Not Contacted | On import |
| 2 | Contacted | Automatic — outbound call logged |
| 3 | Interested | Manual — Markuss drags, or tag `cold-interested` |
| 4 | Booked | Automatic — appointment created on Growth Plan |

### Import
Tag every imported lead **`cold-outreach`**. This tag is the separation
mechanism and the key every workflow below filters on.

### Workflow: `Cold: mark contacted`
- **Trigger:** Call Status -> Completed, direction Outbound
- **Filter:** Contact tag includes `cold-outreach`
- **Action:** Update Opportunity -> stage **Contacted**

Set the dialer to log calls automatically, or this never fires.

### Workflow: `Cold: mark booked`
- **Trigger:** Appointment Status -> Confirmed
- **Filters:** Calendar = `Cozly Media - Growth Plan` AND tag includes `cold-outreach`
- **Action:** Update Opportunity -> stage **Booked**

### Separation from Meta leads
Mostly automatic — the funnel workflows trigger on **Inbound Webhook**, which a
cold lead never hits. Two things to verify:
- Cold leads must not land in the **B2B ADs Sales Pipeline**. That opportunity is
  created by the New Lead workflow, which cold leads don't enter. Confirm.
- A cold lead who books **should** receive the normal booking confirmation and
  reminders. That copy is appropriate for them. No change needed.

---

# PART 4 — No-show recovery

### Workflow: `Cozly: No-Show Recovery`

- **Trigger:** Appointment Status
- **Filters:** Calendar = `Cozly Media - Growth Plan` AND Status = **No Show**

Growth Plan only. A no-show on a client onboarding call should not receive
rebooking sales copy.

### Sequence

**Step 1 — immediately**
- Add tag `no-show`
- Assign conversation to **Markuss Boyd** (one shared number — replies are
  invisible otherwise)
- Internal notification to Markuss
- SMS:
```
Hey {{contact.first_name}}, Markuss from Cozly Media — looks like we missed
each other just now. No stress, things come up.

Want to grab another time? {{BOOKING_LINK}}
```

**Step 2 — wait until 9:00 AM next day**
- SMS:
```
Morning {{contact.first_name}} — still happy to walk you through how we're
filling private-pay cases for home care agencies. Takes 30 minutes.

Here's my calendar: {{BOOKING_LINK}}
```

**Step 3 — wait until 48 hours from trigger**
- SMS:
```
{{contact.first_name}}, I won't chase you past this one. If getting more
private-pay families is still on your list, the door's open:

{{BOOKING_LINK}}

If the timing's wrong, no hard feelings.
```
- Move opportunity to **No Show** stage (add this stage to the B2B ADs Sales
  Pipeline if it doesn't exist)

### Exit condition
Add a **Remove from workflow** on appointment created for this contact, so
anyone who rebooks stops receiving the sequence. Without it, someone who
rebooks after step 1 still gets steps 2 and 3.

### BOOKING_LINK
Grab from Calendars -> Cozly Media - Growth Plan -> the widget URL
(slug `cozly-consult`). Use the same link in all three messages.

---

# Build order

1. Part 2 audit — know what you have before changing it
2. Part 1 SMS swap — quick, and stops the Marc/Markuss mismatch on live calls
3. Part 4 no-show — highest revenue recovery per hour of build
4. Part 3 cold pipeline — largest piece, and gated on Marc's import anyway
