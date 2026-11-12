# Reclaim: PayPal Sandbox, Zapier and AI extraction setup guide

**Date:** 2026-11-11, updated 2026-11-12
**Goal:** finish the hard requirements before submission: a real PayPal
Sandbox payment verified by the API, two Zaps firing from real Reclaim events,
and AI extraction working (with the keyword fallback still working).

**Status on 2026-11-12 (the demo laptop):**
- PayPal Sandbox: done. A real Sandbox payment was captured, and both webhooks
  were verified (`CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`).
- Zapier: done. Both Zaps are published and fired from real events (email sent,
  Google Sheets row added). It runs on a 14-day Zapier trial: cancel it in time.
- AI extraction: switched from xAI Grok to **Groq** running
  `qwen/qwen3.8-27b` (free tier, OpenAI-compatible, accepts images). No code
  change, only `.env`. Don't call it "Grok" in the pitch or docs.
- Tunnel: ngrok login didn't work, so the API is public through
  **Tailscale Funnel** at `https://<your-funnel-address>` (fixed address).
- Skipped on purpose: Test 2 (buyer never returns). Jumana's automated test
  `test_order_approved_webhook_captures_when_buyer_never_returns` covers it.

Whoever runs the demo needs these keys on **their** laptop, in `apps/api/.env`.
If you do all of this on the demo laptop, nobody else has to repeat it.

Menu names below may differ slightly if a provider has redesigned its dashboard.
If a label doesn't match, pick the closest one.

Never commit keys, or paste them into Slack, WhatsApp or chat. `.env` is already
ignored by git.

---

## 0. Setup on your laptop (once)

### Keys file

Create `apps/api/.env` and fill in the blanks as you go:

```
APP_BASE_URL=http://localhost:3000
ENABLE_DEV_ROUTES=false
RATE_LIMITS_ENABLED=true
RATE_LIMIT_AUTH=60/60
SIMULATED_COURIER_SECONDS=10

PAYPAL_MODE=sandbox
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_WEBHOOK_ID=

ZAPIER_WEBHOOK_SECRET=
ZAPIER_URL_MATCH_HIGH_PRIORITY=
ZAPIER_URL_CLAIM_CREATED=

AI_PROVIDER=xai
AI_BASE_URL=https://api.groq.com/openai/v1
AI_API_KEY=
AI_VISION_MODEL=
```

### Starting everything

Use **Git Bash** terminals in VS Code. After every change to `.env`, stop the API
(Ctrl+C) and start it again.

```bash
# Terminal 1: database, fresh demo data, then the API
cd ~/Desktop/ReClaim && docker compose up -d
cd apps/api
.venv/Scripts/python -m app.seed      # reset demo data. Run it BEFORE turning Funnel on
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --env-file .env

# Terminal 2: the website
cd ~/Desktop/ReClaim/apps/web && npm run dev

# Terminal 3: run the check scripts with the keys loaded
cd ~/Desktop/ReClaim/apps/api && set -a && . ./.env && set +a
```

Docker Desktop must be running before `docker compose up -d`.

All demo accounts use the password `reclaim-demo`.

---

## 1. PayPal Sandbox

### A. Test accounts

1. Go to **developer.paypal.com**, log in, and make sure the **Sandbox** toggle
   at the top left is on (not Live).
2. Go to **Testing Tools → Sandbox Accounts**.
3. You need a **Business** account in the **US**, because the demo charges in
   USD. The default Business account is in AE, so use the **US Business**
   account you created (it shows `Business · US`). This is the merchant that
   receives the money.
4. For the buyer, use the **Personal** account. On its row, click **⋮** →
   **View/Edit account** and note its **email and password**. You log in as this
   account on PayPal's page when you pay during the demo.
   - Optional: if PayPal ever refuses the payment because of the buyer's
     country, click **Create account**, choose **Personal** and
     **United States**, and use that one instead.

### B. Create the app and get the keys

1. Go to **Apps & Credentials** (still in Sandbox) and click **Create App**.
2. Name it `Reclaim`, choose **Merchant**, and for the sandbox account pick the
   **US Business** account from step A (not the AE default). Click
   **Create App**.
3. Copy the **Client ID** into `PAYPAL_CLIENT_ID`.
4. Under **Secret key 1**, click **Show**, and copy it into
   `PAYPAL_CLIENT_SECRET`.
5. In terminal 3, reload the keys and check them:
   ```bash
   set -a && . ./.env && set +a
   .venv/Scripts/python scripts/check_paypal.py
   ```
   You should see **"OAuth OK"**. The script never prints the keys.

### C. Make your laptop reachable with Tailscale Funnel

PayPal needs a public web address to send payment notifications ("webhooks")
to. Tailscale Funnel gives your laptop one, with a fixed address. (ngrok was
the original plan, but its login didn't work.)

1. Install the Tailscale app (`winget install --id Tailscale.Tailscale`) and sign
   in from the tray icon.
2. In **login.tailscale.com/admin → DNS**, make sure **MagicDNS** is on and click
   **Enable HTTPS**.
3. Turn the tunnel on (it keeps running in the background, even after a reboot):
   ```bash
   tailscale funnel --bg 8000
   ```
   The first time, it prints a link to allow Funnel for your account. Open it and
   click **Enable**.
4. Check it: `tailscale funnel status`. It looks like
   `https://<your-funnel-address>`.
5. Turn it off when you're not using it: `tailscale funnel --https=443 off`.

While Funnel is on, the API is public on the internet. That's why `.env`
has `ENABLE_DEV_ROUTES=false`, which turns off the demo reset and fake-payment
shortcuts. Reset demo data with `python -m app.seed` before turning Funnel on.
**Turn Funnel off before running the e2e tests**: they start an API with dev
routes on.

### D. Register the webhook

1. Go to **Apps & Credentials** → click your **Reclaim** app → scroll to
   **Sandbox Webhooks** → **Add Webhook**.
2. Webhook URL:
   ```
   https://<your-funnel-address>/api/v1/payments/paypal/webhook
   ```
3. Tick these three events, then click **Save**:
   - **Payment capture completed** (`PAYMENT.CAPTURE.COMPLETED`)
   - **Payment capture denied** (`PAYMENT.CAPTURE.DENIED`)
   - **Checkout order approved** (`CHECKOUT.ORDER.APPROVED`)
4. Copy the **Webhook ID** shown in the list into `PAYPAL_WEBHOOK_ID`, then
   restart the API.

Don't test with **Testing Tools → Webhook Simulator**. As far as I know,
simulator events can't pass PayPal's signature check, so the API rejects them
with 400. That's correct behaviour. Use a real Sandbox checkout instead.

### E. Test 1: a normal payment

Follow acts 1, 4 and 5 of the run sheet in `apps/web/README.md`:

1. As `owner@reclaim.example`, report the silver laptop (Electronics, "Laptop",
   silver, sticker, Terminal 1).
2. As the owner, claim the Terminal 1 laptop. Then, as
   `reviewer@harbourview.example`, open the claim and **Approve** it.
3. As the owner: bell → "Claim approved" → **Choose collection or delivery** →
   **delivery** → enter an address → **Pay with PayPal (Sandbox)**.
4. On PayPal's page, log in as the **Personal** sandbox buyer and approve.

**It worked if:**
- You see "Payment confirmed", and the recovery shows **Paid** with the Sandbox
  badge.
- The API's log shows `POST /api/v1/payments/paypal/webhook` with status
  **200**. PayPal can take a minute to send it.
- This query, run from the repo root, shows the event as `processed` (or
  `ignored` if the browser captured first):
  ```bash
  docker compose exec db psql -U reclaim -d reclaim -c "select event_type, processing_status, received_at from webhook_events order by received_at desc limit 5;"
  ```

### F. Test 2: the buyer never comes back to the site

1. Stop the API, run `.venv/Scripts/python -m app.seed`, and start the API
   again.
2. Repeat Test 1 up to PayPal's approval page.
3. **Just before** you click approve on PayPal, stop the website (Ctrl+C in
   terminal 2). The return page can't load, which mimics a buyer who closed the
   tab.
4. Wait about **45 seconds**, then start the website again with `npm run dev`.
   Log in as the owner: the recovery should now show **Paid**, because the
   server took the payment by itself.
5. Optional: in the PayPal dashboard, go to **Event Logs**, open a webhook event
   and click **Resend**. Run the query from Test 1 again: the new row should say
   `duplicate`, and nothing else should change.

---

## 2. Zapier (two Zaps)

**Check this first.** As far as I know, Zapier treats **Webhooks by Zapier** as
a premium app that needs a paid plan, so the API README's "works on the free
plan" may be wrong. New Zapier accounts come with a free trial of the paid
features, which covers a hackathon. If the editor shows a lock or an upgrade
prompt, start the trial.

**Shared secret.** Run this in Git Bash and put the result in
`ZAPIER_WEBHOOK_SECRET`:

```bash
openssl rand -hex 32
```

### Zap 1: high-priority match → email to staff

1. Go to **zapier.com** → **+ Create → Zaps**.
2. **Trigger:** search **Webhooks by Zapier** → event **Catch Hook** →
   **Continue**. Copy the **webhook URL** it shows into
   `ZAPIER_URL_MATCH_HIGH_PRIORITY`.
3. Restart the API, then fire a real event: as the owner, report the silver
   laptop at Terminal 1 (act 1). That creates a strong match, which sends
   `match.high_priority`.
4. Back in Zapier, click **Test trigger** and pick the request that arrived.
5. **Action:** **Email by Zapier** → **Send Outbound Email** (built in, nothing
   to connect), or **Slack** → **Send Channel Message**.
   - **To:** your own email address.
   - **Subject:** `High-priority match: {{data item_label}}`
   - **Body:** `score`, `label`, `category`. Don't map anything else.
6. Click **Test step**, then **Publish**.

### Zap 2: new claim → Google Sheets row

1. Create a Google Sheet called `Reclaim claims` with the headers
   `case_reference | status | occurred_at`.
2. Create a new Zap: trigger **Webhooks by Zapier → Catch Hook**. Copy its URL
   into `ZAPIER_URL_CLAIM_CREATED`, then restart the API.
3. Fire a real event: as the owner, submit a claim (act 4). That sends
   `claim.created`.
4. Click **Test trigger**.
5. **Action:** **Google Sheets** → **Create Spreadsheet Row** → connect your
   Google account → pick the sheet.
   - Map **only** `data case_reference`, `data status` and `occurred_at`. Never
     map private details; the spec forbids it (docs/07 §7.3).
6. Click **Test step**, then **Publish**.

### Check both

1. Log in as `manager@harbourview.example` → **Integrations**. Status should say
   **Configured**.
2. Click **Send test event**. It goes to both Zaps, and **Last delivery** should
   show success.
3. Run acts 1 and 4 once more: an email should arrive and a new row should
   appear in the sheet.

---

## 3. AI extraction (Groq)

The code was written for xAI Grok, but it calls a standard OpenAI-compatible chat
API, so Groq works with only `.env` changes. Keep `AI_PROVIDER=xai` (that is the
only provider name the code accepts).

1. Go to **console.groq.com**, sign in, open **API Keys** → **Create API Key**,
   and copy it (it starts with `gsk_`) into `AI_API_KEY`.
2. Set `AI_BASE_URL=https://api.groq.com/openai/v1` and
   `AI_VISION_MODEL=qwen/qwen3.8-27b`.
3. In terminal 3, reload the keys and list the models:
   ```bash
   set -a && . ./.env && set +a
   .venv/Scripts/python scripts/check_ai.py
   ```
   Groq doesn't mark which models accept images, and the script's built-in test
   image is 1x1 pixel, which Groq rejects ("Image must have at least 32 pixels").
   That error means the model **does** accept images. Real photos are fine.
   `qwen/qwen3.8-27b` was tested with a 64x64 image: extraction OK in 1.7s.
4. Restart the API. In the lost-item report form, step 4 should now say
   **"AI suggestions"**.
5. Check the fallback: blank out `AI_API_KEY`, restart the API, and step 4
   should show the keyword suggestions instead. Then put the key back.

---

## What's needed from Jumana

None of her code needs to change. Just:

1. **Agree that Farhan's laptop runs the demo.** The webhook only works for the
   laptop whose Funnel address is registered. If she presents, she needs the
   `.env` values, sent through a password manager or another private channel.
2. **Update `apps/api/README.md`**: it still describes xAI Grok and ngrok. It
   should say Groq (`qwen/qwen3.8-27b`) and Tailscale Funnel, and note that
   `check_ai.py`'s 1x1 test image is too small for Groq.
3. **Be on call during the demo rehearsal.** If the API returns an error, it's
   backend code for her to fix.

---

## Done when

- [x] `check_paypal.py` prints "OAuth OK"
- [x] Test 1: a Sandbox payment is captured and the webhook shows `processed` or `ignored`
- [ ] Test 2: the recovery becomes Paid without the return page (skipped, covered by backend tests)
- [x] Integrations page shows Configured (test event skipped: it would send a blank email and sheet row)
- [x] Zap 1 sends an email for a high-priority match
- [x] Zap 2 adds a sheet row for a new claim
- [x] Groq extraction OK from a script
- [ ] The wizard shows "AI suggestions"
- [ ] The fallback works with the key removed
- [ ] The 6-act demo runs cleanly twice in a row with these settings
- [ ] Backup video or screenshots recorded
