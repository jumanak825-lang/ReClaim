# 10. Hackathon Demo Plan

## 10.1 Demo objective

Show that Reclaim is a connected recovery network with a complete
workflow, not just a search page. The demo must visibly prove: -
Cross-report discovery. - AI-assisted matching. - Private ownership
verification. - Organisation operations. - PayPal Sandbox payment. -
Zapier automation. - Collection/delivery recovery tracking.

## 10.2 Main story

**Scenario:** A traveller loses a silver laptop at an airport. Airport
staff later logs a found laptop. The traveller does not know the item
was handed to airport lost property. Reclaim connects the reports.

### Demo cast

-   Traveller: individual owner account.
-   Airport staff: organisation account.
-   Reclaim: matching and recovery network.

## 10.3 Run of show (approximately 4--6 minutes)

### Act 1 --- Report lost

1.  Open individual dashboard.
2.  Create a lost laptop report.
3.  Enter description, approximate time and Terminal 1 location.
4.  Upload image.
5.  Show AI extraction and user confirmation.
6.  Submit and show matching state.

Narration: "The traveller reports once. They do not need to know which
desk or organisation may have the item."

### Act 2 --- Organisation reports found item

1.  Switch to airport staff.
2.  Open found inventory.
3.  Create found laptop report with photo and found time/location.
4.  Show AI extraction.
5.  Submit.
6.  Open AG Grid operations view.

Narration: "The organisation keeps its custody workflow, while Reclaim
makes the record discoverable across the network."

### Act 3 --- AI surfaces a candidate

1.  Show candidate match with relevance score and feature explanations.
2.  Show that score is not ownership proof.
3.  Return to owner account and show notification.
4.  Open candidate and start claim.

Narration: "The AI compares visual, semantic, time and location signals.
It ranks candidates; it does not decide who owns an item."

### Act 4 --- Verify ownership

1.  Show private verification questions.
2.  Submit distinctive detail/evidence.
3.  Switch to reviewer.
4.  Show AI evidence summary/flags.
5.  Human reviewer approves.
6.  Show audit entry.

Narration: "The public listing hides identifying details. The owner
proves knowledge privately, and authorised staff makes the final
decision."

### Act 5 --- Recover with PayPal

1.  Owner chooses delivery.
2.  Show delivery quote and currency.
3.  Click PayPal Sandbox checkout.
4.  Complete Sandbox approval.
5.  Show backend-verified payment status.
6.  Show delivery workflow created.

Narration: "PayPal handles the delivery payment. Reclaim verifies the
transaction server-side; the browser redirect is not trusted."

### Act 6 --- Zapier and completion

1.  Show Zapier notification/task generated from the event.
2.  Show recovery timeline.
3.  Move simulated courier through dispatch/in-transit/delivered.
4.  Owner confirms receipt.
5.  Case closes.

Narration: "Reclaim coordinates the recovery. Zapier connects the
organisation's existing tools without becoming the source of truth."

## 10.4 Seed data

Seed at least: - 3 organisations: airport, hotel, university. - 5
locations. - 20 lost reports. - 20 found reports. - 5 labelled matching
pairs. - 3 pending claims. - 2 completed recoveries. - 1 delivery
quote/payment scenario. - 1 high-priority match for Zapier trigger. -
Several hard-negative pairs.

The main demo pair should be deterministic and clearly labelled in seed
data. The real matcher should still run; seed known attributes so it
ranks the expected pair. Do not hardcode a fake match response.

## 10.5 Demo reliability checklist

-   Reset script works.
-   Individual and staff accounts are ready.
-   Images are pre-uploaded or load reliably.
-   AI API key and quota are available; deterministic fallback exists.
-   PayPal Sandbox buyer and merchant accounts are tested.
-   PayPal webhook endpoint is reachable and signature verification
    passes.
-   Zapier webhook is configured and tested.
-   Network access and Wi-Fi are checked.
-   Simulated courier is labelled.
-   No private real-world personal data is used.
-   Backup screenshots/video are ready in case an external provider is
    unavailable.

## 10.6 Judging narrative

**Problem:** Lost-property systems are fragmented. People do not know
where to search, and staff manually reconcile reports.

**Solution:** Reclaim connects individuals and organisations through a
shared recovery network.

**Why AI:** People describe the same object differently. Reclaim uses
visual, semantic, location and time signals to find candidates.

**Why trust:** AI does not decide ownership. Private evidence and
authorised human review protect the handover.

**Why PayPal:** Recovery can require a delivery payment and, in a future
supported model, a separate finder reward. Financial operations are
explicit and auditable.

**Why Zapier:** Existing organisations already use many tools. Reclaim
emits events so workflows can be automated without replacing every
system.

**Business model:** Organisation subscriptions and event/enterprise
plans, while basic individual reporting remains free.

## 10.7 Avoid these claims

Do not claim: - Guaranteed recovery. - 99% AI accuracy unless
measured. - Escrow or guaranteed custody of money. - Global organisation
coverage before partners exist. - Real courier tracking if simulated. -
Production PayPal payout availability before account eligibility is
confirmed.
