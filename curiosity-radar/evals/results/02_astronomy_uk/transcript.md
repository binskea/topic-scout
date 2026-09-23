# 02_astronomy_uk

**Model:** nvidia/nemotron-3-super-120b-a12b:free  
**Run at:** 2026-09-23T20:08:39.118850+00:00

## Prompt

Ми думаємо додати курс з астрономії до освітнього застосунку. Чи зростає інтерес до цієї теми в україномовній Wikipedia, і наскільки цьому зростанню можна довіряти?

## Commands run

- `uv run curiosity-radar resolve --topic "астрономія" --languages uk --save-as astronomy_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar fetch --project astronomy_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar analyze --project astronomy_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar chart --project astronomy_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar report --project astronomy_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar verify --project astronomy_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`

## Final answer

Interest in astronomy on Ukrainian Wikipedia is **growing**, and the evidence for this growth is **strong**.

**What the data shows**

- **Trend direction:** Increasing (Mann‑Kendall τ ≈ 0.64, *p* ≈ 1 × 10⁻¹⁴⁷).  
- **Growth rate:** Theil‑Sen slope ≈ 2.28 × 10⁻⁸ normalized page‑views per day (a steady upward trend).  
- **Confidence label:** “strong evidence of growth” – the highest confidence level the skill assigns.  
- **Spike detection:** One unusually high‑view day was detected (16 May 2026), but the trend remains strongly increasing even when that spike is excluded.  
- **Data quality:** 731 days of data, no zero‑view days, sufficient for trend analysis.  
- **Placebo check:** The skill’s placebo‑basket sanity check could not be computed (insufficient comparison data), but this does **not** affect the trend statistics; the verified report relies on the Theil‑Sen/Mann‑Kendall analysis instead.

**How much to trust it**

Because the report has passed the verification step (all 11 numeric claims matched the underlying data), you can rely on the reported trend. The “strong evidence of growth” label indicates that, according to the skill’s statistical thresholds, the upward trend is both statistically significant and robust to short‑term fluctuations.

**Bottom line for your educational app**

Adding an astronomy course aligns with a clearly rising interest among Ukrainian‑language Wikipedia readers. The trend is strong and trustworthy, suggesting a receptive audience for astronomy content in Ukrainian.

## Generated PDFs

- `evals/results/02_astronomy_uk/data/reports/astronomy_uk_2026-09-23.pdf`

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.