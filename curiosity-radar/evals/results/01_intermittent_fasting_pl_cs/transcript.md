# 01_intermittent_fasting_pl_cs

**Model:** nvidia/nemotron-3-super-120b-a12b:free  
**Run at:** 2026-09-26T20:32:51.249479+00:00

## Prompt

Порівняй зростання інтересу до інтервального голодування в польськомовній та чеськомовній Wikipedia за останні два роки.

## Commands run

- `uv run curiosity-radar resolve --topic "intermittent fasting" --languages pl,cs --save-as intermittent_fasting_pl_cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar fetch --project intermittent_fasting_pl_cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar analyze --project intermittent_fasting_pl_cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar chart --project intermittent_fasting_pl_cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar report --project intermittent_fasting_pl_cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar verify --project intermittent_fasting_pl_cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`

## Final answer

**Intermittent fasting – interest growth on Polish vs. Czech Wikipedia (last 2 years)**  

| Language | Normalized Theil‑Sen slope (per day) | Mann‑Kendall trend | τ (Kendall’s tau) | p‑value | Confidence label | Spike(s) detected | Data quality |
|----------|--------------------------------------|--------------------|-------------------|---------|------------------|-------------------|--------------|
| **Polish (pl)** | **1.81 × 10⁻⁸** | increasing | **0.88** | 1.53 × 10⁻²⁷⁷ | **Strong evidence of growth** | 1 spike (2025‑10‑28, z‑MAD ≈ 21) | 731 days, 0 zero‑view days → sufficient |
| **Czech (cs)** | 1.87 × 10⁻⁹ | increasing | 0.19 | 1.05 × 10⁻¹⁴ | **Likely growing** | none | 731 days, 0 zero‑view days → sufficient |

### What the numbers mean
- **Both language editions show a statistically significant upward trend** in normalized page‑views for the article “intermittent fasting” over the period 2024‑09‑23 to 2026‑09‑23.
- **Polish Wikipedia exhibits a much stronger growth signal**: its slope is about **10× larger** than the Czech slope, and the Kendall τ of 0.88 indicates a very strong monotonic increase (near‑perfect rank correlation). The Mann‑Kendall p‑value is astronomically small, leading to the confidence label **“strong evidence of growth.”**
- **Czech Wikipedia also rises**, but more modestly: slope ≈ 1.9 × 10⁻⁹ per day, τ ≈ 0.19 (a weak‑to‑moderate monotonic increase). The confidence label is **“likely growing.”**
- A single **spike** appears in the Polish series on 2025‑10‑28 (a day with unusually high views, > 20 MAD above the median). Removing that spike does not change the trend conclusion for Polish (still strong evidence of growth). Czech shows no spikes.

### Cross‑language ranking
The analysis ranks the languages by trend strength:
1. **Polish** – strong evidence of growth  
2. **Czech** – likely growing  

### Visual output (generated charts)
- Trend chart (Polish): `/home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data/charts/intermittent_fasting_pl_cs/trend_pl.png`
- Trend chart (Czech): `/home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data/charts/intermittent_fasting_pl_cs/trend_cs.png`
- Spike chart (Polish): `/home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data/charts/intermittent_fasting_pl_cs/spike_pl.png`
- Cross‑language bar chart: `/home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data/charts/intermittent_fasting_pl_cs/cross_lang.png`

### One‑page PDF report
A verified, shareable report summarizing these findings is available at:  
`/home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data/reports/intermittent_fasting_pl_cs_2026-09-26.pdf`  
(The report’s numeric claims were verified against the underlying data; verification status: **verified**.)

### Bottom line for a B2C founder
- **Interest in intermittent fasting is growing on both Polish and Czech Wikipedia**, but the **growth is markedly stronger and more robust in the Polish edition**.  
- If you are considering localization or content creation, the Polish‑speaking audience shows a clearer, faster‑rising demand, while the Czech audience also presents a positive, albeit slower, upward trend that may merit a smaller‑scale test or a later rollout.  
- The observed spike in Polish (late October 2025) could be tied to a media event or seasonal interest; monitoring such spikes can help time marketing pushes.  

*Methodological note:* The trend estimates use Theil‑Sen slope and Mann‑Kendall test on daily normalized page‑views (views divided by the median views of that article over the whole series). The “confidence_label” reflects the strength of the statistical evidence (see the skill’s `references/stats-methods.md`). The placebo basket check is currently unavailable (insufficient comparison data), so rely on the confidence labels above.

## Generated PDFs

- `evals/results/01_intermittent_fasting_pl_cs/data/reports/intermittent_fasting_pl_cs_2026-09-26.pdf`

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.