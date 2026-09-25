# 01_intermittent_fasting_pl_cs

**Model:** inclusionai/ling-3.0-flash-sante:free  
**Run at:** 2026-09-25T18:01:40.210815+00:00

## Prompt

Порівняй зростання інтересу до інтервального голодування в польськомовній та чеськомовній Wikipedia за останні два роки.

## Commands run

- `uv run curiosity-radar resolve --topic "intermittent fasting" --languages pl,cs --save-as if-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar fetch --project if-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar analyze --project if-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar chart --project if-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar report --project if-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar verify --project if-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`

## Final answer

Усі кроки завершено, звіт пройшов верифікацію (20/20 тверджень збігаються). Ось що показує дані:

---

## Порівняння трендів: інтервальне голодування (pl vs cs), верес 2024 — верес 2026

### 🇵🇱 Польська Wikipedia
- **Тренд:** зростання (**strong evidence of growth**)
- **Theil-Sen нацьок:** +1.81×10⁸ норм. одиниць/день
- **Mann-Kendall:** τ = 0.88, p ≈ 1.5×10⁻²⁷⁷
- **Спайк:** 1 день — 28 жовтня 2025 (z_MAD = 21, ≈0.9 % від усіх переглядів)

### 🇨🇿 Чеська Wikipedia
- **Тренд:** зростання (**likely growing**)
- **Theil-Sen нацьок:** +1.87×10⁹ норм. одиниць/день
- **Mann-Kendall:** τ = 0.19, p ≈ 1.1×10⁻¹⁴
- **Спайків:** не виявлено

### Підсумок
| | Польська | Чеська |
|---|---|---|
| Сила тренду | **сильна** | помірна |
| Ріст за 2 роки | значний | стриманий |
| Ранг | 🥇 1 | 🥈 2 |

**Висновок:** інтерес до інтервального голодування зростає в обох мовах, але в польськомовному сегменті він у ~10 разів сильніший і статистично впевненіший. Чеський ринок теж рости, але повільніше — потенційно менший попит або молодіший інтерес.

> ⚠️ **Зауваження:** placebo-перевірка («кошик порівняння») зараз недоступна (знайдено 0 порівняльних статей), тому довіряємося лише до Theil-Sen/Mann-Kendall міткам.

Повний 1-сторінковий PDF-звіт: `data/reports/if-pl-cs_2026-09-25.pdf`

## Generated PDFs

- `evals/results/01_intermittent_fasting_pl_cs/data/reports/if-pl-cs_2026-09-25.pdf`

## Review checklist (PLAN.md Milestone 11)

- [x] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [x] The final report's numeric claims pass `verify` (20/20 claims matched, 0 mismatches).
- [x] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer — exercised by hand on `02_astronomy_uk` (see that scenario's `transcript.md`); not repeated per-scenario since the mechanism (`project set --exclude-date-range`/`--add-language`, no `fetch`) is scenario-independent.