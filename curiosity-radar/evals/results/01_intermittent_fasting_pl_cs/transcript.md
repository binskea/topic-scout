# 01_intermittent_fasting_pl_cs

**Model:** nvidia/nemotron-3-ultra-550b-a55b:free  
**Run at:** 2026-09-26T11:50:35.588664+00:00

## Prompt

Порівняй зростання інтересу до інтервального голодування в польськомовній та чеськомовній Wikipedia за останні два роки.

## Commands run

- `uv run curiosity-radar resolve --topic "intermittent fasting" --languages pl,cs --save-as intermittent-fasting-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar fetch --project intermittent-fasting-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar analyze --project intermittent-fasting-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar chart --project intermittent-fasting-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar report --project intermittent-fasting-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`
- `uv run curiosity-radar verify --project intermittent-fasting-pl-cs --data-dir /home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data`

## Final answer

Ось результати аналізу зростання інтересу до інтервального голодування в польській та чеській Вікіпедіях за останні 2 роки (731 день, з 23.09.2024 по 23.09.2026):

## 📊 Основні висновки

| Мова | Стаття | Тренд | Сила зростання (Theil-Sen slope) | Mann-Kendall τ | P-value | Оцінка впевненості |
|------|--------|-------|----------------------------------|----------------|---------|-------------------|
| **Польська (pl)** | *Głodówka przerywana* | **Зростає** | **1.81×10⁻⁸ / день** | 0.88 | ~10⁻²⁷⁷ | **Сильні докази зростання** |
| **Чеська (cs)** | *Přerušovaný půст* | **Зростає** | 1.87×10⁻⁹ / день | 0.19 | 1.05×10⁻¹⁴ | **Скоріш за все зростає** |

### Ключові спостереження:

1. **Польська Вікіпедія показує набагато сильніше зростання** — близько **в 10 разів вищий нормалізований нахил** (slope), і дуже високий τ=0.88 (сильний монотонний тренд).

2. **Чеська Вікіпедія також зростає**, але значно повільніше (τ=0.19 — слабкий монотонний тренд), хоча статистично значуще (p < 0.001).

3. **Сплеск у польській Вікіпедії**: виявлено один аномальний день — **28.10.2025** (z-score 21.0, ~0.88% від загальних переглядів). Без цього сплеску тренд залишається "strong evidence of growth".

4. **Перехресна мова**: Польська мова на 1-му місці за силою тренду, Чеська — на 2-м.

---

## 📈 Графіки та звіт

- **Графіки трендів** (з позначеними сплесками): `trend_pl.png`, `trend_cs.png`
- **Сплеск польської Вікіпедії**: `spike_pl.png`
- **Порівняльний барплот**: `cross_lang.png`
- **Односторінковий PDF-звіт** (перевірений, 20 числових тверджень — всі збігаються):  
  `/home/user/topic-scout/curiosity-radar/evals/results/01_intermittent_fasting_pl_cs/data/reports/intermittent-fasting-pl-cs_2026-09-26.pdf`

---

## ⚠️ Важливі застереження

- **Плацебо-баскет не спрацював** (знайдено 0 статей для порівняння) — це відома обмеження інструменту. Впевненість у тренді базується **виключно на Theil-Sen / Mann-Kendall `confidence_label`** ("strong evidence of growth" та "likely growing"), а не на перцентилі плацебо.
- Обидві мови мають **повні 731 день даних без нульових днів** — `sufficient_for_trend: true`.

---

### 💡 Рекомендація для B2C-фаундера
Якщо ви вирішуєте, куди локалізувати продукт/контент про інтервальне голодування — **польський ринок демонструє значно сильніший та стабільніший органічний інтерес** (пошук/читання статті) за останні 2 роки. Чеський ринок теж зростає, але набагато повільніше.

## Generated PDFs

- `evals/results/01_intermittent_fasting_pl_cs/data/reports/intermittent-fasting-pl-cs_2026-09-26.pdf`

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.