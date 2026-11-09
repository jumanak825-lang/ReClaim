# Reclaim: remaining setup before the demo

**For:** Jumana
**From:** Farhan (frontend)
**State of `main`:** `a6d56da`

The frontend is complete. Every MVP screen runs against your Postgres API, and
77 Playwright tests pass, including the full demo story
(`apps/web/e2e/demo.spec.ts`). So far it has all run on the **PayPal mock**,
with **no Zapier URL** and the **keyword fallback** for extraction.

The MVP acceptance criteria (docs/01 §1.12) need a **real PayPal Sandbox
payment verified by the backend** and a **real Zapier automation**. That's
what's left, plus two small backend items. Nothing below needs frontend
changes; the frontend already handles each flow.

All variables are in the root `.env.example`. Never commit real values.

---

## 1. PayPal Sandbox

**Accounts**
- [ ] On developer.paypal.com, create a **Sandbox REST app**. Use a **US
      business account** as the merchant (agreed currency: **USD**). Also
      create a **Sandbox personal (buyer) account** for the demo.

**API environment**
- [ ] `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and
      `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`.
- [ ] Leave `PAYPAL_MODE=auto`, which switches to Sandbox once the ID and
      secret are set. Or set `PAYPAL_MODE=sandbox` to be explicit.
- [ ] Check the credentials with `python scripts/check_paypal.py`, which
      doesn't print them.

**Webhook (needs a public URL)**
- [ ] ngrok, using the **free static domain** (agreed in docs/11):
      `ngrok http --url=<static-domain> 8000`.
- [ ] In the Sandbox app, add the webhook
      `https://<static-domain>/api/v1/payments/paypal/webhook` for at least
      `PAYMENT.CAPTURE.COMPLETED` and `CHECKOUT.ORDER.APPROVED`.
- [ ] `PAYPAL_WEBHOOK_ID` = the ID PayPal shows for that webhook. Webhooks
      return 503 until all three PayPal variables are set.

**Return URLs**
- [ ] Keep `APP_BASE_URL=http://localhost:3000`. PayPal returns the browser
      to `/checkout/paypal/return?recovery_id=…&token=…` and
      `/checkout/paypal/cancel?recovery_id=…`, which the frontend already
      handles. The demo browser runs on the same laptop, so localhost works.

**Check it**
- [ ] Approve the owner's claim, choose **delivery**, then **Pay with PayPal
      (Sandbox)**. You should land on PayPal's real Sandbox page; approve
      with the buyer account. You should see "Payment confirmed", the
      recovery should show **Paid** with the Sandbox badge, and the webhook
      should be logged as processed.
- [ ] Repeat the capture or resend the webhook from the PayPal dashboard.
      There should be no duplicate effect.

## 2. Zapier (two automations required)

- [ ] Create **two Zaps**, each triggered by **Webhooks by Zapier → Catch
      Hook**, filtering on `event_type`:
  1. `match.high_priority` → Slack message or email to staff.
  2. `claim.created` → add a row to a controlled Google Sheet. Include
     `case_reference` and `status` only, never private data.
- [ ] Set `ZAPIER_WEBHOOK_URL` (the catch-hook URL) and
      `ZAPIER_WEBHOOK_SECRET` (any long random string). Events are skipped
      until both are set.
- [ ] **Check it:** as `manager@harbourview.example`, go to **Integrations**
      → **Send test event**. The page shows the last delivery and any
      error. Then trigger each event for real:
  - **High-priority match:** report the demo silver laptop at Terminal 1.
  - **Claim:** submit a claim.
- [ ] Confirm the payloads contain no evidence, addresses or private details
      (docs/07 §7.3).

## 3. Grok extraction

- [ ] Set `AI_API_KEY`, and set `AI_VISION_MODEL` to the current vision
      model ID from docs.x.ai (still unconfirmed). Keep
      `AI_PROVIDER=xai` and `AI_BASE_URL=https://api.x.ai/v1`.
- [ ] **Check it:** in the lost wizard, step 4 should show **"AI
      suggestions"** instead of "Suggestions (basic keyword matching, AI
      unavailable)". Then unset the key and confirm the fallback still works.

## 4. Backend items

- [ ] **`GET /organisations/{id}/overview?location_id=`** (item 4b from the
      first review). Validate it against the caller's assigned locations,
      return 404 for a location outside their scope, apply it to every
      count, and regenerate `openapi.json`. Tell me when it's in: the
      frontend change is one line, and until then the cards say "Across all
      locations".
- [ ] Update the root `README.md` API row. It still says "PayPal orders are
      still mocked".
- [ ] Optional: delete the merged `backend-postgres` branch on GitHub.

## 5. Demo-day configuration

ngrok makes the API public, which changes two of the settings we use
locally.

| Setting | Local dev / e2e | Demo with ngrok |
|---|---|---|
| `ENABLE_DEV_ROUTES` | `true` | **`false`**: otherwise anyone with the URL can reset data or use the mock checkout |
| Reset demo data | `POST /api/v1/dev/reset` | `python -m app.seed`, **before** starting ngrok |
| Simulated courier | Dev shortcut, or wait | Moves to in-transit on its own after `SIMULATED_COURIER_SECONDS` (set it to e.g. `10`) |
| Rate limits | `RATE_LIMITS_ENABLED=false` | Keep them on, but raise `RATE_LIMIT_AUTH` (e.g. `60/60`). We switch accounts many times from one laptop, and the default `10/60` can trip mid-demo. |
| `PAYPAL_MODE` | `mock` (e2e pins this) | `sandbox` |

- [ ] Rehearse the run sheet in `apps/web/README.md` (6 acts) on the demo
      laptop with these settings.
- [ ] Record backup screenshots or a short video of a full successful run,
      in case Wi-Fi, PayPal or Zapier fails on the day (docs/10 §10.5).
- [ ] Use seeded demo data only, with no real personal data. Make sure no
      secrets appear in the logs or on screen.

## Definition of done

- A real **PayPal Sandbox** payment is captured and verified by the API, and
  its webhook is verified and deduplicated.
- **Two Zaps** fire from real Reclaim events.
- **Grok** suggestions appear, and the fallback still works without the key.
- The overview location filter is in `openapi.json`.
- The 6-act demo runs cleanly twice in a row with demo-day settings.

When the overview filter lands and PayPal and Zapier are confirmed, let me
know and I'll re-run the frontend e2e suite against your setup.
