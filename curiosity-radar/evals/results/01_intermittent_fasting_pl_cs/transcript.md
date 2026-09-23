# 01_intermittent_fasting_pl_cs

**Model:** nvidia/nemotron-3-super-120b-a12b:free  
**Run at:** 2026-09-23T20:10:36.746808+00:00

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

За останні два роки (2024‑09‑23 – 2026‑09‑23) інтерес до інтервального голодування зростає як у польській, так і у чеській Вікіпедії, проте темп і довіра до тенденції різні.

**Польська Вікіпедія (pl)**  
- Theil‑Sen скількість: +1,81 × 10⁻⁸ нормалізованих переглядів на день  
- Mann‑Kendall τ = 0,88, p‑значення ≈ 1,5 × 10⁻²⁷⁷  
- Високий рівень впізнавання: **“strong evidence of growth”** (сильні свідчення про зростання)  
- Виявлено один викид (2025‑10‑28, z‑MAD ≈ 21), але тренд залишається сильним і без урахування викидів.  

**Чеська Вікіпедія (cs)**  
- Theil‑Sen скількість: +1,87 × 10⁻⁹ нормалізованих переглядів на день  
- Mann‑Kendall τ = 0,19, p‑значення ≈ 1,05 × 10⁻¹⁴  
- Визначений рівень впізнавання: **“likely growing”** (Ймовірно зростає)  
- Викидів не виявлено.  

Обидві мови мають достатньо даних для аналізу (730 днів, без нульових днів, `sufficient_for_trend: true`). Плацебо‑баскет наразі не може надати надійної через недостатньо даних про порівняння (згідно з відомою обмеженням інструменту), тому довіру слід покладати на вищезазначені мітки впізнавання.

**Висновок:** У польській Вікіпедії спостерігається більш явне та швидке зростання інтересу до інтервального голодування, тоді як у чеській – помірне, однак статистично значиме збільшення. Обидві тенденції підтверджено у перевіреному jedno‑сторінковому PDF‑звіті, що доступний за шляхом:  
`/home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data/reports/intermittent_fasting_pl_cs_2026-09-23.pdf`.

## Generated PDFs

- `evals/results/01_intermittent_fasting_pl_cs/data/reports/intermittent_fasting_pl_cs_2026-09-23.pdf`

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.