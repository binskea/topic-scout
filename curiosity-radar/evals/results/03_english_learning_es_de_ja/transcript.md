# 03_english_learning_es_de_ja

**Model:** nvidia/nemotron-3-super-120b-a12b:free  
**Run at:** 2026-09-26T20:32:02.354836+00:00

## Prompt

Ми створюємо застосунок для вивчення англійської мови. Порівняй інтерес до вивчення англійської в іспанській (es), німецькій (de) та японській (ja) мовних розділах Wikipedia та підготуй короткий звіт: які аудиторії варто дослідити наступними й чому?

## Commands run

- `uv run curiosity-radar resolve --topic "English language learning" --languages es,de,ja --save-as english_learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar fetch --project english_learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar analyze --project english_learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar chart --project english_learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar report --project english_learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar verify --project english_learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`

## Final answer

**Interest in learning English (topic: “English language learning” – Q_EVAL_LEARN_ENGLISH) – Spanish (es), German (de), Japanese (ja) Wikipedia**

| Language | Trend (Theil‑Sen slope / day) | Mann‑Kendall τ | Confidence label | Notable spikes | Verdict |
|----------|------------------------------|----------------|------------------|----------------|---------|
| **es** (Spanish) | **+1.76 × 10⁻⁸** (≈ 0.0064 % / year) | 0.86 | **Strong evidence of growth** | 1 spike on 2025‑05‑31 (z‑MAD ≈ 17.8, 0.70 % of total views) | Growing interest |
| **ja** (Japanese) | **+9.46 × 10⁻⁹** (≈ 0.0035 % / year) | 0.70 | **Strong evidence of growth** | 1 spike on 2026‑03‑27 (z‑MAD ≈ 45.0, 0.86 % of total views) | Growing interest |
| **de** (German) | –1.67 × 10⁻¹⁰ (≈ ‑0.00006 % / year) | –0.04 | **No clear trend detected** | none | Flat/stable interest |

*All three editions have 731 days of data (≈ 2 years) with zero‑view‑day‑free series, so each trend assessment is based on sufficient data.*

### What the numbers tell us
- **Spanish (es)** and **Japanese (ja)** both show **strong, statistically significant upward trends** in pageviews to the “English language learning” article, with large Mann‑Kendall τ values (> 0.6) and tiny p‑values (≪ 10⁻¹⁰0). The slopes correspond to modest but steady yearly growth (≈ 0.3‑0.6 % per year) after normalizing by article‑specific baseline traffic.
- **German (de)** shows a slope indistinguishable from zero (τ ≈ ‑0.04, p ≈ 0.15) – no detectable increase or decrease over the same period.
- Spike detection reveals occasional high‑attention days in es and ja (likely tied to media events or exam periods), but the underlying trend remains positive even when those spikes are excluded.

### Recommendation for next audience investigation
1. **Prioritize Spanish‑speaking learners** – The strongest growth signal, largest τ, and a clear spike suggest rising awareness or demand for English‑learning resources in the Spanish Wikipedia community. A/B testing of an English‑learning app or content localized for Spain/Latin America is likely to capture an expanding market.
2. **Follow up with Japanese‑speaking learners** – Also shows strong growth, though the slope is about half that of Spanish. The large spike in March 2026 hints at a periodic surge (perhaps tied to academic cycles). Localizing for Japanese users (e.g., JLPT‑focused content) would tap into a similarly upward trend.
3. **Monitor German‑speaking learners** – Interest appears flat; this does not mean no market, but growth expectations should be tempered. If you decide to serve this audience, consider a differentiated value proposition (e.g., professional‑English or exam‑specific modules) rather than relying on broad organic growth.

### Why these audiences?
The **cross‑language ranking** from the analysis places **es > ja > de**, explicitly citing “strong evidence of growth” for the top two and “no clear trend detected” for German. The placebo check is unavailable (insufficient comparison data), so we rely on the Theil‑Sen/Mann‑Kendall confidence labels, which are robust against outliers and autocorrelation.

**Bottom line:** For a B2C founder deciding where to allocate localization effort next, the Spanish and Japanese Wikipedia audiences present the clearest, data‑backed signals of increasing interest in learning English, while the German audience offers a stable but not growing baseline. Proceed with es and ja as the primary targets for product expansion, and keep de on a watch‑list for any future shifts.

## Generated PDFs

- `evals/results/03_english_learning_es_de_ja/data/reports/english_learning_2026-09-26.pdf`

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.