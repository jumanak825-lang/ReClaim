# 6. AI and Matching Specification

## 6.1 Objective

Find plausible lost/found pairs across the network, even when the owner
and finder describe the same object differently. The matcher produces
ranked candidates and explanations. It does not establish ownership.

## 6.2 Pipeline

1.  **Input validation:** validate text, image types, size and malware
    scan status.
2.  **Attribute extraction:** classify object and extract
    visible/declared attributes.
3.  **Normalisation:** standardise category, brand, colour, time and
    location fields.
4.  **Candidate generation:** retrieve a manageable set using category,
    text, embeddings and geographic/time constraints.
5.  **Feature comparison:** compare category, semantic text, visual
    similarity, attributes, time and distance.
6.  **Ranking:** compute score and confidence band.
7.  **Explanation:** produce short grounded reasons using actual matched
    features.
8.  **Human feedback:** capture confirmed, dismissed and inconclusive
    candidates.
9.  **Evaluation:** measure precision/recall on a labelled dataset and
    tune weights.

## 6.3 Extraction schema

Suggested structured output:

``` json
{
  "category": "electronics",
  "object_type": "laptop",
  "brand": "Example",
  "model": null,
  "colours": ["silver"],
  "visible_features": ["dark keyboard", "small sticker"],
  "text_features": ["silver laptop found near seating area"],
  "possible_identifiers": [],
  "uncertainties": ["model not visible"],
  "sensitive_or_private_candidates": [],
  "confidence_by_field": {
    "category": 0.96,
    "brand": 0.62,
    "colour": 0.91
  }
}
```

Never invent an identifier or claim certainty where an image is unclear.
Preserve original user text alongside extracted attributes.

## 6.4 Candidate generation

Use multiple retrieval paths: - Exact/normalised category and selected
attributes. - Text search over descriptions. - Embedding similarity over
descriptions and image captions. - Image embedding similarity where
provider/model supports it. - Geographic proximity using coordinates
where available. - Time-window overlap/proximity.

Do not hard-filter solely by exact brand, model or time; users may not
know those values and reports may contain mistakes. Apply configurable
eligibility filters for closed/withdrawn reports and custody states.

## 6.5 Initial ranking model

Initial illustrative weights: - Visual similarity: 30% - Category
compatibility: 20% - Brand/attributes: 20% - Location proximity: 15% -
Time compatibility: 15%

Normalise each feature to 0--1, then calculate weighted score × 100. If
a feature is missing, redistribute its weight across available features
or mark the candidate as low-information. Never treat missing data as a
mismatch automatically.

Initial bands: - 85--100: high-priority candidate - 65--84.99: possible
candidate - below 65: low-priority candidate / normally not surfaced

These are starting values for demo tuning, not scientifically validated
thresholds. Store `matcher_version` and score components to permit
evaluation.

## 6.6 Location and time

-   If coordinates exist, use a distance function and configurable decay
    curve.
-   If only text locations exist, use geocoding only if configured;
    otherwise compare normalised location terms cautiously.
-   Respect timezone when interpreting user-entered local times.
-   A lost-time interval should compare against found time, not a
    fabricated exact timestamp.
-   A location/time mismatch should lower rank, not automatically
    disqualify unless logically impossible.

## 6.7 Explanations

Generate explanations from actual feature values: - "Both reports
describe a silver laptop." - "The found report is within the reported
time window." - "The reported locations are approximately 600 metres
apart."

Do not produce unsupported statements such as "same serial number"
unless the private values were securely compared and the explanation is
appropriate for the viewer. Public explanation must not reveal hidden
values.

## 6.8 Ownership verification assistant

After claim initiation: - Select private verification questions based on
hidden attributes. - Ask questions that the legitimate owner is likely
to answer. - Do not reveal the answer or hidden attribute in the
question. - Avoid questions answerable from public listing. - Allow "I
don't remember" where appropriate. - Flag contradictions and suspicious
patterns for human review. - Keep claimant answers private from finder
and unauthorised staff.

Example: if private detail is "small dent on left rear corner," ask
"Describe any damage or distinctive marks on the item." Do not show the
answer in a hint.

## 6.9 Risk indicators

Potential indicators: - Repeated claims against unrelated items. -
Conflicting descriptions of a distinctive feature. - Evidence image
appears reused across unrelated claims. - Claim submitted from a newly
created account with unusual activity. - Attempts to obtain hidden
storage details. - Repeated report spam.

These are review signals only. Do not automatically accuse a user or
reject a claim based on a model score.

## 6.10 Human review interface

Reviewer should see: - Safe report comparison. - Private verification
responses and evidence if authorised. - AI-generated summary clearly
labelled. - Individual inconsistency flags with source references. -
Approve/reject/escalate actions. - Required decision reason. - Audit
history.

## 6.11 Evaluation plan

Build a labelled fixture dataset with: - True matching pairs. - Hard
negatives (same category/colour but different item). - Near matches
(same brand/model but different item). - Missing/ambiguous
descriptions. - Image-only and text-only examples. - Different locations
and time intervals.

Measure: - Precision@1 and precision@5. - Recall on known pairs. -
False-positive rate. - Performance by category and missing-data
pattern. - Reviewer override rate.

Do not publish an accuracy number until measured on a representative
labelled test set.

## 6.12 Cost and resilience

-   Make model provider configurable.
-   Cache extraction/embeddings by image content hash and model version
    where permitted.
-   Use deterministic fallback matching if AI provider is unavailable.
-   Rate-limit user submissions and image processing.
-   Set maximum image size and supported formats.
-   Log model/version/latency/cost metadata without storing sensitive
    prompts unnecessarily.
-   Provide a demo mode with seeded known matches so the core story
    remains reliable.
