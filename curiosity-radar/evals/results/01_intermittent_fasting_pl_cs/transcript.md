# 01_intermittent_fasting_pl_cs

**Model:** nvidia/nemotron-3-super-120b-a12b:free  
**Run at:** 2026-09-23T19:57:38.951749+00:00

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

За останні два роки (з 23 вересня 2024 р. по 23 вересня 2026 р.) інтерес до інтервального голодування зростає як у польськомовній, так і у чеськомовній Wikipedia, проте темп і статистична впевненість зростання різні.

**Польська Wikipedia (pl.wikipedia)**
- Нормалізований тел‑сен скількоденний приріст: **≈ 1.81 × 10⁻⁸** одиниць на день.
- Mann‑Kendall τ = 0,88, p‑значення ≈ 1,5 × 10⁻²⁷⁷ → дуже сильна monotonic trend.
- Висновок аналізу: **“strong evidence of growth”** (висока впевненість).
- Виявлено один випик (28 жовтня 2025 р.), проте після його виключення тренд залишається сильно зростаючим.
- Якість даних: 731 день, нульових‑переглядів днів немає → достатньо для тренду.

**Чеська Wikipedia (cs.wikipedia)**
- Нормалізований тел‑сен скількоденний приріст: **≈ 1.87 × 10⁻⁹** одиниць на день (блізко 10 разів менше, ніж у польській версії).
- Mann‑Kendall τ = 0,19, p‑значення ≈ 1,05 × 10⁻¹⁴ → статистично значущий, але слабший зростаючий сигнал.
- Висновок аналізу: **“likely growing”** (помірна впевненість).
- Випиків не виявлено.
- Якість даних: те ж, 731 днів, без нульових‑переглядів → достатньо для тренду.

**Порівняння**
- Польська редакція виражає сильніше та статистично более надійне зростання интересу („strong evidence of growth”).
- Чеська редакція показує позитивний, але помірно виражений зростаючий тренд („likely growing”).
- Обидві мови мають достатню історичну основу (два повних роки денних даних) для довіреного виведення про тренд.

Таким чином, за аналізом Wikipedia‑переглядів інтерес до інтервального голодування стає все більш популярним у обох мовах, проте темп przyjęття значно вищий у польськоговорячій аудиторії.

## Generated PDFs

- `evals/results/01_intermittent_fasting_pl_cs/data/reports/intermittent_fasting_pl_cs_2026-09-23.pdf`

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.