# LlmRevenueCompute model

## Purpose
Top-down estimation of Anthropic's revenue, compute utilization, and implied
valuation from 2025 to 2030, cross-referenced against the global LLM electricity
market (Goldman Sachs / IEA baseline).

## Key anchors

| Metric | Value | Source |
|---|---|---|
| EOY 2025 ARR | $9 B | Anthropic confirmed |
| Apr 2026 ARR | $44 B | SemiAnalysis (used as EOY 2026 floor) |
| Dec 2025 valuation | $350 B | Implied pre-Series G |
| Apr 2026 valuation | ~$900 B | TechCrunch / Reuters ($50 B round pre-money) |
| 2025 compute live | ~100 MW | AWS Trainium + Google TPU allocations (est.) |
| 2026 compute EOY | ~1.3 GW | SpaceX Colossus 300 MW + Amazon ~1 GW |
| 2027+ compute | 5–14 GW | Google/Broadcom 5 GW + Amazon 5 GW + Azure $30 B |
| Global DC electricity 2025 | 448 TWh | IEA confirmed |
| Global DC electricity 2030 | 945 TWh | Goldman Sachs base case |

## Inputs (globals)

### Revenue
- `arr_base` (9.0) — EOY 2025 ARR in $B
- `arr_growth_2026` (3.89) — pins `arr[2026]` to $44 B
- `arr_growth_2027_seed` (0.80) — 2027 growth before decay
- `arr_growth_decay` (0.70) — geometric decay on growth rate from 2028+

### Compute capacity
- `cap_2025`, `cap_2026`, `cap_2027`, `cap_2028`, `cap_2029`, `cap_2030` — deployed GW per year (see code for sourcing)

### Compute utilization
- `util_start` (0.35) — inference revenue fraction of capacity, 2025
- `util_ceiling` (0.75) — fraction ceiling by 2030

### Global LLM market
- `dc_twh_2025` (448.0), `dc_twh_2030` (945.0) — GS/IEA electricity anchors
- `llm_share_2025` (0.25), `llm_share_2030` (0.45) — LLM share of DC power

### Valuation
- `val_anchor_2025` (350.0) — Dec 2025 valuation in $B
- `multiple_2026` (20.5) — observed P/S multiple at $44 B ARR / $900 B val
- `multiple_floor` (8.0) — P/S floor by 2030

## Outputs

### Block 1 — Revenue
- `arr_growth_rate[year]` — YoY ARR growth rate
- `arr[year]` — Annualized Revenue Run-Rate at year-end ($B)

### Block 2 — Compute
- `capacity_gw[year]` — total deployed compute (inference + training, GW)
- `util_rate[year]` — fraction generating inference revenue
- `revenue_gw[year]` — GW actively billing customers
- `arr_per_revenue_gw[year]` — $B ARR per revenue-generating GW (pricing power proxy)

### Block 3 — Global LLM market
- `global_dc_twh[year]` — global data-center electricity (TWh/yr)
- `llm_dc_share[year]` — LLM fraction of data-center power
- `global_llm_twh[year]` — electricity attributable to LLM workloads
- `global_llm_gw[year]` — equivalent average continuous GW load
- `anthropic_compute_share[year]` — Anthropic `revenue_gw` ÷ `global_llm_gw`

### Block 4 — Valuation
- `revenue_multiple[year]` — EV / ARR (P/S)
- `valuation[year]` — implied enterprise value ($B)

## Headline outputs (base case)

| Year | ARR ($B) | Revenue GW | Compute share | Valuation ($B) | P/S |
|---|---|---|---|---|---|
| 2025 | 9 | 0.04 | 0.3% | 350 | 38.9× |
| 2026 | 44 | 0.56 | 3.1% | 902 | 20.5× |
| 2027 | 79 | 2.55 | 10.5% | 1,376 | 17.4× |
| 2028 | 124 | 5.0 | 15.9% | 1,761 | 14.3× |
| 2029 | 172 | 7.4 | 18.6% | 1,914 | 11.1× |
| 2030 | 219 | 10.5 | 21.6% | 1,754 | 8.0× |

## Key interpretations

**Compute share vs revenue share**: `anthropic_compute_share` is a *compute*
market share (Anthropic GW ÷ all LLM GW globally), not the ~40% enterprise API
spend share. The gap confirms Anthropic earns a large revenue premium per GW vs
open-source/internal deployments. Watch this converge as token prices commoditize.

**2026→2027 capacity jump**: `capacity_gw` leaps from 1.3 → 5.0 GW as Google/
Broadcom's 5 GW tranche begins. `arr_per_revenue_gw` drops from $79 → $31/GW —
Anthropic is deliberately building ahead of demand, accepting short-term under-
utilization to secure long-term capacity in a constrained GPU market.

**Valuation peak**: The model peaks at ~$1.9 T in 2029, then dips to $1.75 T in
2030 as multiple compression ($11× → $8×) outpaces revenue growth (~27%).
Adjusting `multiple_floor` upward (e.g. 10×) pushes 2030 valuation above $2 T.

## Scenarios to explore
- `expression overrides add arr_growth_2027_seed=1.0` — bull case: 2027 growth stays at 100%
- `expression overrides add util_ceiling=0.60` — bear case: capacity never fully monetizes
- `expression overrides add multiple_floor=5.0` — multiple compresses to pre-AI SaaS norms
- `expression overrides add cap_2027=3.0` — capacity delays (permitting, power grid constraints)
- `expression overrides add dc_twh_2030=1050` — GS accelerated scenario for global LLM market

## Known issues / open questions
- [ ] Gross margin not modeled (expanded from 38% to 70%+ in 2025-2026; affects FCF/valuation)
- [ ] No explicit competitor dynamics (OpenAI, Google Gemini API, DeepSeek)
- [ ] Token price deflation not directly modeled (captured implicitly in arr_growth_decay)
- [ ] 2025 capacity estimate is rough — pre-SpaceX cloud allocations are not publicly disclosed
- [ ] Azure $30 B deal GW-equivalent not calculable without pricing data

## Overrides
None.

## Changelog
- 2026-05-10: created; anchored to SemiAnalysis $44 B ARR, GS DC electricity forecast,
              Anthropic infrastructure blog (SpaceX/Amazon/Google deals).
