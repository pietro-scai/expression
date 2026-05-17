"""
Anthropic Revenue, Compute & Valuation Model (2025–2030)
=========================================================
Top-down estimation structured across four interlocking views:

  1. REVENUE    — ARR trajectory anchored to confirmed actuals, then projected
                  with geometrically decelerating growth.
  2. COMPUTE    — Infrastructure capacity ramp (GW) vs the fraction generating
                  inference revenue. Tracks the "productive" utilization path
                  as Anthropic absorbs its massive new capacity pipeline.
  3. MARKET     — Global LLM electricity demand (Goldman Sachs / IEA baseline)
                  converted to GW, used to size the total market and compute
                  Anthropic's implied share.
  4. VALUATION  — P/S multiple compression as revenue scales, anchored to two
                  observed data points.

─── Key anchors (all confirmed public data) ──────────────────────────────────
  Revenue
    EOY 2025 ARR:   $9 B    Anthropic confirmed
    Apr 2026 ARR:  $44 B    SemiAnalysis; treated as conservative EOY 2026 floor
                             (actual EOY 2026 will likely be higher)
  Valuation
    Dec 2025:     $350 B    implied pre-Series G
    Apr 2026:    ~$900 B    pre-money, prospective $50 B round (TechCrunch/Reuters)
  Compute (secured, from Anthropic blog May 2026)
    2025 live:    ~0.10 GW  AWS Trainium + Google TPU cloud allocations (est.)
    2026 EOY:     ~1.30 GW  + SpaceX Colossus 300 MW + Amazon ~1 GW tranche
    2027+:        5–14 GW   Google/Broadcom 5 GW (from 2027), Amazon up to 5 GW total,
                             Azure $30 B allocation
  Global LLM market
    2025:          448 TWh  global data-center electricity (IEA confirmed)
    2030:          945 TWh  Goldman Sachs base-case forecast

─── Units ────────────────────────────────────────────────────────────────────
  Monetary values : $B (billions USD)
  Capacity        : GW (gigawatts, average continuous load)
  Power/energy    : TWh/year
"""

from expression import Model, glob, periods, row


class LlmRevenueCompute(Model):
    time = periods(2025, 2030)

    # ═══════════════════════════════════════════════════════════════════════
    # GLOBALS — the dials you'll reach for most often
    # ═══════════════════════════════════════════════════════════════════════

    # ── Revenue ─────────────────────────────────────────────────────────────
    arr_base            = glob(9.0,  doc="EOY 2025 ARR ($B, actual)")
    # 2026 is pinned: (44/9) - 1 = 3.89 → arr[2026] = $44 B
    arr_growth_2026     = glob(3.89, doc="2026 YoY growth — anchors arr[2026] to $44 B (SemiAnalysis)")
    arr_growth_2027_seed = glob(0.80, doc="2027 growth rate; decays geometrically each subsequent year")
    arr_growth_decay    = glob(0.70, doc="Annual decay multiplier on growth rate from 2028 onward")

    # ── Compute capacity — one glob per year, tunable via overrides ──────────
    # Sources: Anthropic blog (May 2026), public deal announcements.
    # "Deployed" means physically online and allocatable, not just contracted.
    cap_2025 = glob(0.10,  doc="GW deployed, 2025 — AWS Trainium + Google TPU cloud (est.)")
    cap_2026 = glob(1.30,  doc="GW deployed, EOY 2026 — SpaceX 0.3 GW + Amazon ~1 GW first tranche")
    cap_2027 = glob(5.00,  doc="GW deployed, 2027 — Google/Broadcom 5 GW begins; Amazon scaling")
    cap_2028 = glob(8.50,  doc="GW deployed, 2028 — Amazon (toward 5 GW total) + Azure $30 B ramp")
    cap_2029 = glob(11.00, doc="GW deployed, 2029")
    cap_2030 = glob(14.00, doc="GW deployed, 2030 — all major tranches substantially online")

    # ── Compute utilization ──────────────────────────────────────────────────
    # "Utilization" here = inference revenue-generating fraction of total capacity.
    # The remainder is training workloads + ramp-up idle + headroom buffer.
    # In 2025 Anthropic ran mostly pay-per-use cloud (no idle); as dedicated
    # infrastructure scales from 2026, utilization starts low and ramps.
    util_start   = glob(0.35, doc="Revenue-generating fraction of capacity, 2025")
    util_ceiling = glob(0.75, doc="Utilization ceiling by 2030 (training overhead + buffer)")

    # ── Global LLM market — Goldman Sachs / IEA baseline ───────────────────
    dc_twh_2025    = glob(448.0, doc="Global data-center electricity, 2025 (TWh/yr, IEA confirmed)")
    dc_twh_2030    = glob(945.0, doc="Global data-center electricity, 2030 (TWh/yr, GS base case)")
    llm_share_2025 = glob(0.25,  doc="LLM share of data-center power, 2025")
    llm_share_2030 = glob(0.45,  doc="LLM share of data-center power, 2030 (AI displaces conventional)")

    # ── Valuation ────────────────────────────────────────────────────────────
    val_anchor_2025 = glob(350.0, doc="Valuation ($B), Dec 2025 — implied pre-Series G")
    multiple_2026   = glob(20.5,  doc="P/S multiple, 2026 — ~$900 B / $44 B ARR")
    multiple_floor  = glob(8.0,   doc="P/S multiple floor, 2030 — mature hyper-growth SaaS comp")

    # ═══════════════════════════════════════════════════════════════════════
    # BLOCK 1: REVENUE
    # ═══════════════════════════════════════════════════════════════════════

    @row
    def arr_growth_rate(self, t):
        """
        YoY ARR growth rate.

        2025  base year — no prior period, returns 0.
        2026  pinned so arr[2026] = arr_base × (1 + 3.89) = $44 B.
        2027  arr_growth_2027_seed (default 80%).
        2028+ geometric decay: seed × decay^(years past 2027).

        The decay model reflects the natural S-curve of hyper-growth companies:
        80% → 56% → 39% → 27% maps to the AWS / Azure growth deceleration
        trajectory, shifted right to account for AI market tailwinds.
        """
        if t == self.time.first:
            return 0.0
        if t == 2026:
            return self.arr_growth_2026
        # 2027: exponent = 0, so returns seed unchanged; 2028+: decays each year
        years_past_2027 = t - 2027
        return self.arr_growth_2027_seed * (self.arr_growth_decay ** years_past_2027)

    @row
    def arr(self, t):
        """
        Annualized Revenue Run-Rate at year-end ($B).

        Anchored to $9 B (2025) and $44 B (2026), then projected.
        Note: $44 B was the SemiAnalysis figure from late April 2026;
        EOY 2026 will likely exceed this as growth continued.
        """
        if t == self.time.first:
            return self.arr_base
        return self.arr(t - 1) * (1 + self.arr_growth_rate(t))

    # ═══════════════════════════════════════════════════════════════════════
    # BLOCK 2: COMPUTE CAPACITY & UTILIZATION
    # ═══════════════════════════════════════════════════════════════════════

    @row
    def capacity_gw(self, t):
        """
        Anthropic's deployed compute capacity in GW (inference + training combined).

        Each value is sourced from disclosed infrastructure deals:
          2025  Cloud era: AWS Trainium + Google TPU allocations (~100 MW est.)
          2026  SpaceX Colossus (300 MW, 220 K H100s) + Amazon ~1 GW first tranche
          2027  Google/Broadcom 5 GW agreement begins; Amazon scaling toward 5 GW total
          2028  Amazon approaching 5 GW; Azure $30 B ramp materializes
          2029/30  All tranches at scale; possible additional deals not yet announced
        """
        if t == 2025: return self.cap_2025
        if t == 2026: return self.cap_2026
        if t == 2027: return self.cap_2027
        if t == 2028: return self.cap_2028
        if t == 2029: return self.cap_2029
        return self.cap_2030

    @row
    def util_rate(self, t):
        """
        Fraction of capacity_gw generating inference revenue (not training or idle).

        Linear ramp from util_start (2025) to util_ceiling (2030).
        Utilization is suppressed in 2025 because Anthropic was on pay-per-use cloud
        (no idle capacity concept); it stays moderate through 2027 because the
        Google/Broadcom capacity arrives faster than inference demand can absorb it.

        Override specific years when you know a major model training run is scheduled
        (e.g. `expression overrides add util_rate[2027]=0.40`).
        """
        span = self.time.last - self.time.first   # 5 years
        progress = (t - self.time.first) / span
        return self.util_start + progress * (self.util_ceiling - self.util_start)

    @row
    def revenue_gw(self, t):
        """GW actively generating inference revenue = capacity_gw × util_rate."""
        return self.capacity_gw(t) * self.util_rate(t)

    @row
    def arr_per_revenue_gw(self, t):
        """
        $B of ARR per GW of revenue-generating inference compute.

        Tracks Anthropic's pricing power and inference efficiency over time.
        The sharp drop from 2026→2027 ($79→$31 /GW) reflects the capacity
        explosion as Google/Broadcom 5 GW comes online ahead of demand —
        a deliberate "build ahead" strategy. The gradual decline thereafter
        reflects token price compression (~80% per 18 months industry-wide)
        partially offset by volume growth.
        """
        return self.arr(t) / self.revenue_gw(t)

    # ═══════════════════════════════════════════════════════════════════════
    # BLOCK 3: GLOBAL LLM MARKET (Goldman Sachs / IEA baseline)
    # ═══════════════════════════════════════════════════════════════════════

    @row
    def global_dc_twh(self, t):
        """
        Global data-center electricity consumption (TWh/year).

        Linear interpolation between two GS/IEA anchors:
          448 TWh (2025, IEA confirmed) → 945 TWh (2030, GS base case).
        GS also has an accelerated case at ~1,050 TWh; the base case is used here.
        Override dc_twh_2030 to stress-test bull/bear scenarios.
        """
        span = self.time.last - self.time.first
        progress = (t - self.time.first) / span
        return self.dc_twh_2025 + progress * (self.dc_twh_2030 - self.dc_twh_2025)

    @row
    def llm_dc_share(self, t):
        """
        LLM workloads as fraction of total data-center electricity.

        Grows from 25% (2025) to 45% (2030) as AI inference and training
        displace traditional web/database workloads. At 45%, LLMs alone
        would consume ~425 TWh — comparable to all of France today.
        """
        span = self.time.last - self.time.first
        progress = (t - self.time.first) / span
        return self.llm_share_2025 + progress * (self.llm_share_2030 - self.llm_share_2025)

    @row
    def global_llm_twh(self, t):
        """Total electricity consumed by LLM inference + training globally (TWh/year)."""
        return self.global_dc_twh(t) * self.llm_dc_share(t)

    @row
    def global_llm_gw(self, t):
        """
        Global LLM compute expressed as average continuous load (GW).

        Conversion: TWh/year ÷ 8.76 = average GW
        (8,760 hours in a year; the ÷1000 from TWh→GWh cancels with the GW unit).

        This is the total installed/running LLM compute in the world at any moment —
        including Google's internal Gemini fleet, Meta's Llama inference, Chinese LLMs,
        and all open-source deployments, not just commercial API providers.
        """
        return self.global_llm_twh(t) / 8.76

    @row
    def anthropic_compute_share(self, t):
        """
        Anthropic's revenue_gw as a fraction of global_llm_gw.

        IMPORTANT: this is compute market share, not revenue market share.
        Anthropic reports ~40% of *enterprise API spend*, but enterprise API
        is a small, premium slice of global LLM compute. The much larger base
        includes Google/Meta internal workloads, open-source self-hosting, and
        Chinese deployments — none of which pay Anthropic.

        A large gap between this metric and the 40% spend share confirms that
        Anthropic earns a significant revenue premium per GW vs the market average.
        Watch this converge as token prices commoditize.
        """
        return self.revenue_gw(t) / self.global_llm_gw(t)

    # ═══════════════════════════════════════════════════════════════════════
    # BLOCK 4: VALUATION
    # ═══════════════════════════════════════════════════════════════════════

    @row
    def revenue_multiple(self, t):
        """
        EV / ARR (P/S multiple).

        Two observed anchors:
          Dec 2025:  val_anchor_2025 / arr[2025]  ≈ 38.9×  ($350 B / $9 B)
          Apr 2026:  multiple_2026               = 20.5×  (~$900 B / $44 B)
        This 2025→2026 compression (39× → 20×) is already confirmed — the market
        re-rated as revenue scaled.

        2027–2030: linear compression from multiple_2026 to multiple_floor (8×).
        Even at 8× in 2030, this implies a premium multiple for a $200 B+ ARR business.
        A mature SaaS comps like Salesforce or ServiceNow trade at 7–10× revenue.
        """
        if t == self.time.first:
            # Falls out of the two anchors — not an input
            return self.val_anchor_2025 / self.arr(t)
        if t <= 2026:
            return self.multiple_2026
        span = self.time.last - 2026   # 4 years to compress to floor
        progress = (t - 2026) / span
        return self.multiple_2026 + progress * (self.multiple_floor - self.multiple_2026)

    @row
    def valuation(self, t):
        """
        Implied enterprise valuation ($B) = ARR × revenue_multiple.

        2025 is the anchor ($350 B); all subsequent years are model output.
        The peak implied by this model (~$1.9 T in 2029) reflects high growth
        multiples on a $170 B ARR base — compares to Apple at ~$3.8 T on ~$400 B revenue.
        """
        if t == self.time.first:
            return self.val_anchor_2025
        return self.arr(t) * self.revenue_multiple(t)
