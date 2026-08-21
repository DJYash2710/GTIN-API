# PRD: GTIN Product Data API

**Status:** Draft v1
**Owner:** [TBD]
**Last updated:** 2026-08-20

---

## 1. Overview & Problem Statement

Internal teams frequently need three core data points for a product given only its GTIN (Global Trade Item Number — UPC/EAN/JAN, 8/12/13/14 digits): **Product Name**, **Price**, and **Weight**. Today this data is either missing, manually looked up, or inconsistently sourced across teams.

This service will expose a single internal API endpoint that accepts a GTIN and returns these three fields, resolved automatically behind the scenes by orchestrating multiple third-party data sources (official registries and web-scraping providers like Apify), extracting and normalizing the results, and returning a clean, consistent response — without the caller needing to know or care which source the data came from.

## 2. Goals & Non-Goals

**Goals**
- Given a valid GTIN, return Product Name, Price, and Weight with high accuracy and reasonable latency.
- Abstract away the complexity of "which provider do we call and in what order" from consumers.
- Minimize third-party API/scraping cost per lookup through smart source selection and caching.
- Be resilient to any single source being unavailable, rate-limited, or returning bad data.

**Non-Goals (v1)**
- Full product catalog data (images, descriptions, reviews, categories, variants).
- Real-time price tracking / price history over time.
- Support for external (non-internal) consumers, multi-tenant auth, or public rate-limit tiers.
- Guaranteed data for every GTIN in existence — coverage is expected to be partial and will be tracked as a metric.

## 3. Users & Use Cases

**Consumers:** Internal services and teams only (v1). Examples:
- Catalog/PIM systems backfilling missing product attributes.
- Pricing/finance tools needing a quick price check by GTIN.
- Logistics/shipping tools needing product weight for freight calculations.
- Internal dashboards/BI tools doing ad-hoc lookups.

Since consumers are internal, auth can be a lightweight internal service token/API key (or mTLS if that's the org standard) rather than a full OAuth/tiered-access system — see Section 10.

## 4. API Contract

### Endpoint

```
GET /v1/products/{gtin}
```

### Request

| Param | Type | Required | Notes |
|---|---|---|---|
| `gtin` | string (path) | Yes | 8/12/13/14-digit GTIN. Validated against GTIN checksum. |
| `force_refresh` | boolean (query) | No | Bypasses cache, forces a fresh lookup. Default `false`. |

Headers: `Authorization: Bearer <internal-service-token>`

### Response — 200 OK

```json
{
  "gtin": "00012345678905",
  "product_name": "Acme Wireless Mouse M220",
  "price": {
    "amount": 24.99,
    "currency": "USD"
  },
  "weight": {
    "value": 95,
    "unit": "g"
  },
  "confidence": "high",
  "source": "apify:amazon",
  "resolved_at": "2026-08-20T09:14:00Z",
  "cache": "miss"
}
```

### Response — Partial Data

If only some fields could be resolved, return them with explicit `null` for the rest rather than failing the whole request:

```json
{
  "gtin": "00012345678905",
  "product_name": "Acme Wireless Mouse M220",
  "price": null,
  "weight": null,
  "confidence": "low",
  "source": "apify:walmart",
  "resolved_at": "2026-08-20T09:14:00Z",
  "cache": "miss"
}
```

### Error Codes

| Code | Meaning |
|---|---|
| `400` | Invalid GTIN format / failed checksum |
| `401` | Missing/invalid internal auth token |
| `404` | No data found for this GTIN across all attempted sources |
| `429` | Internal consumer rate limit exceeded |
| `503` | All source attempts failed (timeout/error) — includes `Retry-After` header |

## 5. System Architecture

The service is composed of the following stages (see diagram above):

1. **API Gateway** — validates GTIN format/checksum, authenticates the internal caller, applies rate limits.
2. **Cache Layer** — checks for existing fresh data before doing any paid/expensive lookups.
3. **Source Orchestrator (Priority Engine)** — decides which source(s) to call and in what order, based on a dynamically computed priority score (Section 6).
4. **Source Adapters** — one adapter per third-party source, each responsible for calling that source and returning raw data in a common intermediate format. Initial adapters:
   - **Official registry** (e.g. GS1-affiliated data, brand APIs where available) — highest trust, tried first when available for a given GTIN prefix.
   - **Apify actors**, one per major retailer (e.g. Amazon, Walmart, target brand sites) — general-purpose scraping fallback.
   - **Backup scraping API** — secondary vendor, used when Apify sources are exhausted or rate-limited.
5. **Extraction & Normalization Engine** — parses each source's raw output (structured data like schema.org/JSON-LD when present, HTML selectors otherwise) into the three target fields, and normalizes units/currency/formatting.
6. **Validation & Confidence Scoring** — assigns a confidence level to the resolved data; in validation mode, cross-checks multiple sources and resolves conflicts.
7. **Response Formatter** — builds the final JSON response and writes the result back to cache.

Adapters share a common interface so new sources can be added without touching the orchestrator or extraction logic:

```
interface SourceAdapter {
  id: string
  fetch(gtin: string): RawSourceResult | NotFound | Error
  costPerCallEstimate: number
}
```

## 6. Source Prioritization Engine (Dynamic)

Rather than a fixed, hand-maintained order, each source gets a **priority score** recomputed on a rolling basis from observed performance:

```
priority_score(source) =
    w1 * success_rate_30d
  - w2 * normalized_avg_cost
  - w3 * normalized_avg_latency
  + w4 * data_completeness_rate
```

- **`success_rate_30d`** — % of calls in the last 30 days that returned usable data (rolling window, exponentially weighted to favor recent performance).
- **`normalized_avg_cost`** — average cost per successful call (Apify usage cost, vendor API fees), normalized 0–1 across sources.
- **`normalized_avg_latency`** — average response time, normalized 0–1.
- **`data_completeness_rate`** — % of calls where all 3 fields (not just some) were extracted.
- Weights (`w1..w4`) start with reasonable defaults and are configurable — this lets the team tune "cheap and fast" vs "complete and accurate" without a code change.

**Circuit breaker:** if a source's rolling success rate drops below a configurable threshold (e.g. 20%), it's automatically deprioritized/skipped for a cooldown period rather than continuing to eat latency/cost on a broken source.

**Stats storage:** a lightweight per-source stats table (success count, failure count, total cost, total latency, completeness count) updated after every call, with scores recomputed on a schedule (e.g. hourly) rather than per-request, to keep the hot path fast.

## 7. Call Strategy (MVP)

**Sequential fallback, ordered by dynamic priority score, with a confidence threshold:**

1. Call the highest-priority source for this GTIN.
2. If it returns data at or above the confidence threshold (all 3 fields present, extracted from structured data), return immediately.
3. If it fails, times out, or returns low-confidence/partial data, fall through to the next source in priority order.
4. Cap attempts at a configurable max (e.g. top 3 sources) before returning a partial/404 response.
5. Per-source timeout (e.g. 5s) so one slow source doesn't blow the overall request budget.

This keeps steady-state cost and latency low. A separate **validation mode** (calling 2+ sources in parallel and cross-checking) is reserved for cases where higher confidence is worth the extra cost — e.g. first-time GTIN lookups that will be cached long-term, or a scheduled reconciliation job — rather than being the default per-request behavior.

## 8. Data Extraction & Normalization

**Extraction:**
- Prefer structured data when present in scraped pages (schema.org/JSON-LD, Open Graph product tags) — most reliable and cheapest to parse.
- Fall back to per-adapter HTML selectors tuned to each retailer's page layout.
- For unstructured/inconsistent pages, consider an LLM-based extraction fallback (given raw text, extract name/price/weight) — higher cost, used only when structured/selector extraction fails.

**Normalization rules:**
- **Price:** store `{amount, currency}`; do not silently convert currencies — return as-observed, let consumers convert if needed.
- **Weight:** normalize to grams as the canonical stored unit; convert from whatever unit the source provides (oz, lb, kg) using standard conversion factors; return both canonical and original unit if useful.
- **Product name:** trim whitespace, strip marketing filler (e.g. "FREE SHIPPING", excessive emoji/symbols) via a lightweight cleanup pass.

## 9. Conflict Resolution & Confidence Scoring

Confidence is `high | medium | low`, derived from:
- Whether data came from structured markup vs. best-effort HTML parsing.
- Whether the source is historically high-accuracy (from the same stats used in prioritization).
- In validation mode: whether multiple sources agree.

When multiple sources disagree (validation mode or a retry after a low-confidence result):
- Prefer the source with the higher historical accuracy score.
- If scores are close, prefer the most recently updated data.
- Flag the response with `confidence: "low"` if disagreement can't be resolved with reasonable certainty, rather than guessing silently.

## 10. Caching Strategy

| Field | Suggested TTL | Rationale |
|---|---|---|
| Product name | 30–90 days | Rarely changes |
| Weight | 30–90 days | Effectively static per GTIN |
| Price | 6–24 hours | Changes frequently |

Since price and weight/name have very different volatility, cache them as separate keys or with independent TTLs within the same record rather than one blanket TTL — otherwise you either refetch weight unnecessarily often or serve stale prices.

- Cache key: `gtin`.
- `force_refresh=true` bypasses cache and forces a fresh lookup (writes back on success).
- Manual invalidation endpoint/admin tool for correcting bad cached data.

## 11. Non-Functional Requirements

- **Latency:** target p95 < 300ms on cache hit; p95 < 3–5s on cache miss (bounded by sequential source attempts + per-source timeout).
- **Cost budget:** define a max acceptable cost per lookup (blended across cache hits/misses); alert if trending over budget.
- **Rate limiting:** per internal consumer/service, to protect against runaway usage driving up third-party costs.
- **Availability:** target 99.5%+ for the service itself (independent of third-party source uptime, which is handled via fallback).

## 12. Error Handling & Edge Cases

- **Invalid GTIN format/checksum** → `400` immediately, no source calls made.
- **GTIN not found anywhere** → `404` after exhausting the attempt cap.
- **All sources fail (timeout/error, not "not found")** → `503` with `Retry-After`.
- **Ambiguous match** (source returns multiple candidate products for the GTIN) → return best match with `confidence: "low"` and a flag rather than guessing silently.
- **Partial data** → return what was found with explicit nulls for missing fields, not a hard failure.

## 13. Security & Compliance

- Internal-only auth: service token or mTLS, scoped to internal network/VPC.
- Review scraping ToS for each targeted retailer/source before adding an adapter — this is a legal/compliance checkpoint, not just an engineering one.
- Define data retention policy for cached scraped data.
- No PII expected in this data path, but confirm nothing in scraped pages (e.g. seller contact info) leaks into responses.

## 14. Monitoring & Observability

Key metrics to track per source and in aggregate:
- Success rate, average cost, average latency, data completeness rate (the same signals feeding the priority engine).
- Overall **GTIN coverage rate** — % of requested GTINs successfully resolved.
- Cache hit ratio.
- Response confidence distribution (high/medium/low over time).
- Sampled extraction accuracy (periodic manual QA against a sample of responses).

Alert on: source success rate crossing circuit-breaker threshold, cost per lookup trending above budget, coverage rate dropping.

## 15. Rollout Plan

**Phase 1 (MVP):**
- 2–3 source adapters (e.g. one official/registry source if available + 1–2 Apify retailer actors).
- Sequential fallback with bootstrapped/default priority weights (dynamic scoring starts adjusting once enough call history accumulates).
- Basic caching with the TTLs above.
- Core API contract as specified.

**Phase 2:**
- Additional source adapters.
- Fully matured dynamic prioritization with tuned weights.
- Validation mode for high-value/first-time lookups.
- Admin tooling/dashboard for managing sources, weights, and viewing stats.

## 16. Open Questions / Risks

- Do we have access to an official GTIN/GS1 registry, or are we scraping-only for v1?
- What's the acceptable cost ceiling per lookup, and who owns that budget?
- Legal review needed on scraping ToS for each target retailer before launch.
- How do we handle GTINs with regional variants (same product, different GTIN per market)?
- What's an acceptable "not found" rate before it's considered a coverage problem worth escalating?

---

## Appendix: Example Request/Response

**Request:**
```
GET /v1/products/00012345678905
Authorization: Bearer <token>
```

**Response:**
```json
{
  "gtin": "00012345678905",
  "product_name": "Acme Wireless Mouse M220",
  "price": { "amount": 24.99, "currency": "USD" },
  "weight": { "value": 95, "unit": "g" },
  "confidence": "high",
  "source": "apify:amazon",
  "resolved_at": "2026-08-20T09:14:00Z",
  "cache": "miss"
}
```
