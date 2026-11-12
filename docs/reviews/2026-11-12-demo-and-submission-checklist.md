# Reclaim: demo and submission checklist

**Date:** 2026-11-12 (submission day)
**Demo laptop:** Farhan's laptop. All keys live in `apps/api/.env` there.

Sources: docs/10_HACKATHON_DEMO.md (demo script), docs/01 §1.12 (acceptance
criteria), apps/web/README.md (run sheet), and the setup guide
docs/reviews/2026-11-11-integration-setup-guide.md.

---

## 0. Fill these in from the hackathon's own page

The docs don't say how or where to submit. Check the hackathon page and fill in:

- [ ] Submission platform and link: ______________________
- [ ] Deadline (with time zone): ______________________
- [ ] Required fields (tick what applies): repo link / demo video / live URL /
      slides / project description / screenshots / team members
- [ ] Video limits (length, YouTube or upload): ______________________
- [ ] Does the repo have to be public? Do judges need a live URL they can open?
- [ ] Live presentation or video only? How many minutes?

---

## 1. Code freeze and GitHub (go-live)

**Freeze the code**
- [ ] The UI/UX chat is finished, and its full e2e run passes (77 passed,
      1 phone-only skip), along with `npx tsc --noEmit`, `npx eslint` and `npm run build`.
- [ ] Re-check the demo labels below (section 4) after the UI pass. Button text
      may have changed.
- [ ] Update the stale "Known gap" line at the end of the run sheet in
      `apps/web/README.md`: the overview cards now follow the location selector.

**Commit and push** (no AI-tool attribution lines in commits)
- [ ] Commit the UI/UX work, the root README update, and these two guides if
      you want them public (see the warning under "Make the repo public").
- [ ] Decide on `docs/reviews/2026-11-08-api-stub-review.md`: commit it or leave it out.
- [ ] Push `main` (includes `1066dae`, the overview location filter).
- [ ] Jumana updates `apps/api/README.md`: Groq instead of Grok, Tailscale
      instead of ngrok, and `check_ai.py`'s 1x1 test image is too small for Groq.

**Make the repo public** (Jumana owns it: `github.com/jumanak825-lang/ReClaim`, currently **PRIVATE**)
- [x] Secret scan of the full git history: no PayPal, Groq, xAI or Zapier keys,
      no private keys, no `.env` files ever committed. `apps/api/.env` is ignored.
- [ ] Re-run the scan after the final commit (grep for `gsk_`,
      `hooks.zapier.com/hooks/catch`, `PAYPAL_CLIENT_SECRET=`).
- [x] The real Funnel address and laptop name are replaced with placeholders in
      both guides. Never commit the real address: anyone with it can reach the
      demo API while Funnel is on.
- [ ] Jumana: **Settings → General → Danger Zone → Change visibility → Public**.
      If public isn't allowed or wanted, add the judges as collaborators instead
      (**Settings → Collaborators**).
- [ ] Add a repo description and website (**About** gear on the repo page), e.g.
      "AI-assisted lost-and-found recovery network. Next.js, FastAPI, PostgreSQL,
      PayPal Sandbox, Zapier."
- [ ] Optional: delete merged branches (`api-stub`, `backend-postgres`,
      `backend-remaining-setup`, `web-foundation`).

**README for judges** (root `README.md`)
- [ ] One-paragraph pitch at the top (see section 6).
- [ ] Demo video link.
- [ ] 3 to 5 screenshots: report wizard with AI suggestions, matches, claim
      review, PayPal confirmation, Operations grid.
- [ ] "What's real and what's simulated" list: PayPal **Sandbox** (no real money),
      **simulated courier**, **seeded demo data**, AI by a **Qwen vision model on
      Groq** with a keyword fallback.
- [ ] Team: Farhan (frontend), Jumana (backend).

**If judges need a live URL** (only if section 0 says so)
- [ ] The app runs on the laptop, and Funnel exposes only the API (port 8000),
      not the website. A public link to the website needs extra setup (a
      production build, Funnel on port 3000, and `APP_BASE_URL` changed for PayPal
      return links). Plan it first; it isn't a 5-minute change.

---

## 2. Before the demo (T-30 minutes)

**Servers** (see the setup guide, section 0)
- [ ] Docker Desktop running, then `docker compose up -d`.
- [ ] Funnel **off** while resetting: `tailscale funnel --https=443 off`.
- [ ] Reset demo data: `.venv/Scripts/python -m app.seed` (in `apps/api`).
- [ ] Start the API: `.venv/Scripts/python -m uvicorn app.main:app --port 8000 --env-file .env`.
- [ ] Start the website: `npm run dev` in `apps/web`. Open each page once so the
      first load on stage isn't slow.
- [ ] Funnel **on**: `tailscale funnel --bg 8000`.
- [ ] Check `https://<funnel-address>/api/v1/ready` says `ready`, and
      `/api/v1/dev/demo-accounts` gives **404** (dev routes off).
- [ ] `.env` has `ENABLE_DEV_ROUTES=false`, `PAYPAL_MODE=sandbox`,
      `RATE_LIMITS_ENABLED=true`, `RATE_LIMIT_AUTH=60/60`,
      `SIMULATED_COURIER_SECONDS=10`.

**Integrations**
- [ ] Integrations page (as `manager@harbourview.example`) shows Zapier **Configured**.
- [ ] Both Zaps are **On** in Zapier, and the trial hasn't expired.
- [ ] Delete test rows from the Google Sheet so the live row is obviously new.
- [ ] Groq key still works (the lost wizard's step 4 says "AI suggestions").

**Screen and browser**
- [ ] Two separate browser profiles (or one normal and one private window) so the
      owner and staff stay signed in side by side. Cookies are shared within one profile.
- [ ] Tabs ready: the app, your email inbox (Zap 1), the Google Sheet (Zap 2).
- [ ] PayPal Sandbox **Personal** buyer email and password at hand (not on screen).
- [ ] A laptop photo on the desktop for the upload (HP worked well with the AI).
- [ ] Notifications off (Windows Focus), browser zoom about 125%, bookmarks bar hidden.
- [ ] No terminal or editor showing `.env` while screen sharing.
- [ ] Wi-Fi checked, laptop on charge.

Demo accounts (password `reclaim-demo`): `owner@reclaim.example` (Dana),
`staff@harbourview.example`, `reviewer@harbourview.example`,
`manager@harbourview.example`.

---

## 3. Run of show (4 to 6 minutes)

| # | Time | Who | What to click | What to say |
|---|---|---|---|---|
| 1 | 0:00 | owner | **Report lost** → Electronics, "Laptop", mention *silver* and *sticker*, colour silver → "Terminal 1, airport", yesterday → upload the photo, add a private mark → **step 4: AI suggestions** (click "Use this" on brand) → privacy summary → submit | "The traveller reports once. They don't need to know which desk or organisation has the item. AI suggests details from the photo; the user confirms them." |
| 2 | 1:00 | staff | **Operations** grid → open the Terminal 1 laptop case (storage reference visible to staff only) → show **Log found item** | "The organisation keeps its custody workflow, while Reclaim makes the record discoverable across the network." |
| 3 | 1:45 | owner | Report → **View possible matches** → the Terminal 1 laptop. Point at "not proof of ownership" and the hidden details | "AI compares visual, text, time and location signals. It ranks candidates; it doesn't decide who owns an item." |
| 4 | 2:30 | owner, then reviewer | **Claim this item** → describe the sticker and dent privately → submit. Reviewer: **Claims** → open it → AI assistance → **Approve** with a reason → **Audit log** | "The owner proves knowledge privately. An authorised person makes the decision, and it's audited." |
| 5 | 3:30 | owner | Bell → "Claim approved" → **Choose collection or delivery** → delivery → address → price → **Pay with PayPal (Sandbox)** → log in as the sandbox buyer → approve → "Payment confirmed" | "PayPal handles the delivery payment. Reclaim verifies it with PayPal on the server; the browser redirect isn't trusted." |
| 6 | 4:30 | all | Show the **email** (Zap 1) and the **sheet row** (Zap 2). Staff: recovery → **Dispatch (simulated courier)**, which moves to in transit after 10s. Owner: **I've received my item** → case closed | "Zapier connects the organisation's existing tools without becoming the source of truth. The courier is simulated for the demo." |

Zap 1 fires in act 1 (the strong match), and Zap 2 fires in act 4 (claim
submitted). Glance at the inbox and sheet then, and show them in act 6.

---

## 4. Say this, not that (docs/10 §10.7)

Say:
- "PayPal **Sandbox**, no real money."
- "**Simulated** courier."
- "**Seeded** demo data."
- "AI by a **Qwen vision model on Groq**, with a keyword fallback if it's unavailable."
- "AI ranks and suggests; **people decide** ownership."

Don't say:
- Grok or xAI (we switched to Groq).
- Guaranteed recovery, or any AI accuracy figure (nothing is measured).
- Escrow, or that Reclaim holds money.
- Real courier tracking, or coverage of real organisations.
- That finder reward payouts work (not built).

---

## 5. Backup plan

- [ ] **Record one full clean run** (Win + Alt + R, or OBS) before the
      presentation. It doubles as the submission video if one is needed.
- [ ] Screenshots of each act, including "Payment confirmed", the Zapier email
      and the sheet row.
- If PayPal is down: show the recorded act 5 clip.
- If Groq is down: carry on. The wizard shows keyword suggestions instead and
  says AI is unavailable, which is the intended fallback.
- If Zapier is slow: show the email and sheet row from the rehearsal.
- If the laptop or Wi-Fi fails: play the full recording.

---

## 6. Submission text (draft)

> **Reclaim** connects people who lose things with the organisations that find
> them. Lost-property systems are fragmented: travellers don't know where to
> search, and staff reconcile reports by hand. With Reclaim, an owner reports
> once, organisations log found items in their own workflow, and AI suggests
> details from photos and ranks likely matches across the network. AI never
> decides ownership: the owner proves it privately, and authorised staff approve
> the claim with a full audit trail. Recovery is by collection or by delivery,
> paid through PayPal (Sandbox) and verified on the server, and events flow to
> the organisation's existing tools through Zapier.
>
> Built with Next.js, FastAPI, PostgreSQL, PayPal REST APIs (Sandbox), Zapier
> webhooks and a Qwen vision model on Groq. The courier and demo data are simulated.

---

## 7. After the demo

- [ ] Funnel off: `tailscale funnel --https=443 off`.
- [ ] Stop the API and website.
- [ ] Optional: revoke the Groq key, and turn the Zaps off.
- [ ] The Zapier trial ends by itself (no card was entered).
