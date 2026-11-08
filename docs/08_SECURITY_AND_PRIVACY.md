# 8. Security, Privacy and Abuse Prevention

## 8.1 Security objectives

Protect: - User accounts and personal information. - Hidden item
attributes and ownership evidence. - Organisation inventory and custody
locations. - Payment credentials and financial state. -
Cross-organisation boundaries. - Audit records and operational
integrity.

## 8.2 Threat model

  -----------------------------------------------------------------------
  Threat                  Risk                    Required mitigation
  ----------------------- ----------------------- -----------------------
  Fake owner claims       Wrong person receives   Private questions,
                          item                    evidence, human review

  Fake finder report      Scam or theft           Rate limits, custody
                                                  verification,
                                                  suspicious activity
                                                  review

  Data scraping           Exposure of valuable    Rate limits, safe
                          items                   public fields, no exact
                                                  storage details

  Organisation data       Cross-tenant exposure   Backend membership
  leakage                                         checks, tenant-scoped
                                                  queries, tests

  Fake payment success    Unpaid delivery         Server-side capture
                                                  verification and signed
                                                  webhooks

  Duplicate payment       Double charge           Idempotency and unique
                                                  provider references

  Malicious upload        Malware/content abuse   MIME/signature checks,
                                                  size limits, scanning

  Account takeover        Claim theft             Secure auth, password
                                                  reset protections,
                                                  optional MFA

  Insider misuse          Unauthorised item       Least privilege, audit
                          release                 logs, approval policy

  Prompt injection in     AI tool misuse          Treat user content as
  descriptions                                    untrusted data; no tool
                                                  authority

  Zapier replay/spoofing  False external event    HMAC signatures,
                                                  timestamps, event IDs

  Pickup token theft      Unauthorised collection One-time hashed token,
                                                  expiry, staff
                                                  validation
  -----------------------------------------------------------------------

## 8.3 Authentication

-   Use a maintained auth library/provider or securely hashed passwords
    (Argon2id/bcrypt).
-   Secure, HttpOnly, SameSite cookies where using cookie sessions.
-   CSRF protection where applicable.
-   Rate-limit login, registration and password reset.
-   Avoid account enumeration in auth responses.
-   Support session revocation.
-   Consider MFA for organisation admins and reviewers.

## 8.4 Authorisation

Use role-based permissions plus organisation/location scope. Example
permissions: - `report:create_own` - `report:read_own` -
`found_report:create_location` - `case:read_location` -
`claim:review_location` - `recovery:update_location` -
`organisation:manage` - `integration:manage` - `audit:read` -
`network:admin`

Never trust a role, organisation ID or user ID supplied by the client
without resolving it against the authenticated identity and database
membership.

## 8.5 Sensitive data classification

### Public-safe

-   Broad item category.
-   General colour/type.
-   Approximate location.
-   Approximate time window.
-   Sanitised description.

### Restricted

-   Private distinctive marks.
-   Serial numbers and purchase proof.
-   Full delivery address.
-   Exact storage/custody location.
-   Claim answers and evidence.
-   Internal reviewer notes.
-   Payment provider details beyond safe references.

Use separate DTOs and permissions. Do not return one giant object and
rely on frontend hiding.

## 8.6 AI safety

-   Treat all descriptions, filenames, image OCR and user-provided text
    as untrusted input.
-   AI output must be schema-validated.
-   AI cannot execute actions or call privileged tools.
-   AI cannot approve claims or issue payments/payouts.
-   Do not reveal hidden attributes in public match explanations.
-   Do not treat AI confidence as proof.
-   Provide deterministic fallback and human escalation.

## 8.7 Payment security

-   PayPal client secret and access token are backend-only.
-   Verify order/capture amount and currency.
-   Verify webhook signatures.
-   Enforce idempotency.
-   Store provider IDs and minimal reconciliation data.
-   Never store card data.
-   Never trust browser redirects as proof.
-   Separate payment capture, refund and finder payout workflows.
-   Use Sandbox in demo and label it clearly.

## 8.8 File security

-   Allow-list image/document types.
-   Check actual file signatures.
-   Enforce file-size limits.
-   Rename files with random storage keys.
-   Strip metadata when appropriate.
-   Store private evidence separately.
-   Use short-lived signed URLs.
-   Apply malware scanning where available.
-   Do not render uploaded SVG/HTML as trusted content.

## 8.9 Audit logging

Audit: - Report create/edit/withdraw. - Private evidence access where
feasible. - Claim submit/review/decision. - Custody changes. - Pickup
token validation. - Recovery status changes. - Payment
create/capture/refund. - Payout create/status. - Organisation
membership/permission changes. - Integration configuration and
retries. - Super-admin access.

Audit records should be append-only from application workflows. Redact
secrets and unnecessary personal data.

## 8.10 Privacy and retention

-   Collect only what is needed to recover the item.
-   Explain why private evidence is requested and who can access it.
-   Provide user access, correction and deletion workflows where
    applicable.
-   Define retention periods for reports, evidence, payments and audit
    records.
-   Do not expose personal contact details directly between owner and
    finder by default.
-   Use in-platform messaging or mediated contact in later phases if
    needed.
-   Assess applicable privacy/data-protection obligations before
    production launch, including relevant jurisdictions where Reclaim
    operates.

## 8.11 Security test checklist

-   [ ] User cannot access another user's private report.
-   [ ] Staff cannot access an unassigned organisation.
-   [ ] Staff cannot access a location outside their scope.
-   [ ] Public match response excludes private attributes.
-   [ ] Finder cannot read claimant answers.
-   [ ] Non-reviewer cannot decide claim.
-   [ ] AI response cannot change claim status.
-   [ ] Payment amount cannot be changed by client.
-   [ ] Invalid PayPal webhook signature is rejected.
-   [ ] Duplicate PayPal webhook is idempotent.
-   [ ] Duplicate capture request does not double charge.
-   [ ] Zapier signature/replay checks work.
-   [ ] Expired pickup token is rejected.
-   [ ] Upload validation rejects disguised executable files.
-   [ ] Secrets and evidence do not appear in logs.
