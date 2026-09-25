# 03_english_learning_es_de_ja

**Model:** inclusionai/ling-3.0-flash-sante:free  
**Run at:** 2026-09-25T18:02:43.544056+00:00

## Prompt

Ми створюємо застосунок для вивчення англійської мови. Порівняй інтерес до вивчення англійської в іспанській (es), німецькій (de) та японській (ja) мовних розділах Wikipedia та підготуй короткий звіт: які аудиторії варто дослідити наступними й чому?

## Commands run

- `uv run curiosity-radar resolve --topic "learning English" --languages es,de,ja --save-as english-learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar fetch --project english-learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar analyze --project english-learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar chart --project english-learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar report --project english-learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar verify --project english-learning --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`

## Final answer

Звіт перевірено — 29/29 тверджень збігаються. Ось результати:

---

## 📊 Порівняння інтересу до вивчення англійської: es vs de vs ja

### Тренди (Wikipedia pageview, вересень 2024 — вересень 2026)

| Мова | Тренд | Theil-Sen на день | Tau | Впевненість |
|------|-------|-------------------|-----|-------------|
| 🇪🇸 **es** | 📈 Зростання | +1.76×10⁻⁸ | 0.858 | **Сильна** |
| 🇯🇵 **ja** | 📈 Зростання | +9.46×10⁻⁹ | 0.699 | **Сильна** |
| 🇩🇪 **de** | ➡️ Без тренду | −1.67×10⁻¹⁰ | −0.036 | Немає чіткого |

### Піки активності
- **es**: 31 травня 2025 (z=17.8, 0.7% переглядів)
- **ja**: 27 березня 2026 (z=45.0, 0.86% переглядів) — найсильніший спайк із трьох

### Рекомендації для вашого застосунку

1. **🎯 Пріоритет №1 — іспанськомовна аудиторія (es)**. Найстабільніше зростання інтересу до вивчення англійської серед трьох мов. Високий tau (0.858) свідчить про сталий тренд, а не разовий імпульс.

2. **🎯 Пріоритет №2 — японськомовна аудиторія (ja)**. Теж чітке зростання (tau=0.699), з дуже вираженим піком у березні 2026. Може вказувати на сезонний попит або вплив зовнішнього події — варто досліджувати глибше.

3. **🔍 Дослідити далі — німецькомовна аудиторія (de)**. Статистично немає тренду — ні зростання, ні падіння. Це може означати насичений ринок або те, що німці шукають англійську через інші канали (не Wikipedia). Рекомендується додаткове дослідження (опитування, конкурентний аналіз) перед інвестиціями.

### ⚠️ Зауваження
- Placebo-перевірка недоступна (потрібно ≥10 порівняних статей — це відома обмеження наразі).
- Оцінку надійності тренду покладено на Theil-Sen/Mann-Kendall, а не на placebo.
- Повний 1-сторінковий PDF звіту: `reports/english-learning_2026-09-25.pdf`

## Generated PDFs

- `evals/results/03_english_learning_es_de_ja/data/reports/english-learning_2026-09-25.pdf`

## Review checklist (PLAN.md Milestone 11)

- [x] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [x] The final report's numeric claims pass `verify` (29/29 claims matched, 0 mismatches).
- [x] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer — exercised by hand on `02_astronomy_uk` (see that scenario's `transcript.md`); not repeated per-scenario since the mechanism (`project set --exclude-date-range`/`--add-language`, no `fetch`) is scenario-independent.