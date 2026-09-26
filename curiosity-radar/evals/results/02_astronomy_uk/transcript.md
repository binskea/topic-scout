# 02_astronomy_uk

**Model:** nvidia/nemotron-3-ultra-550b-a55b:free  
**Run at:** 2026-09-26T11:51:37.860746+00:00

## Prompt

Ми думаємо додати курс з астрономії до освітнього застосунку. Чи зростає інтерес до цієї теми в україномовній Wikipedia, і наскільки цьому зростанню можна довіряти?

## Commands run

- `uv run curiosity-radar resolve --topic "astronomy" --languages uk --save-as astronomy-uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar fetch --project astronomy-uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar analyze --project astronomy-uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar chart --project astronomy-uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar report --project astronomy-uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar verify --project astronomy-uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`

## Final answer

**Так, інтерес до астрономії в україномовній Вікіпедії зростає, і цьому зростанню можна довіряти з високою ступенем впевненості.**

## Основні результати аналізу

| Показник | Значення |
|----------|----------|
| **Тренд (Theil-Sen)** | +2.28·10⁻⁸ нормалізованих переглядів на день (позитивний) |
| **Mann-Kendall τ** | 0.64 (сильний монотонний тренд) |
| **p-value** | 1.3·10⁻¹⁴⁷ (екстремально значущий) |
| **Confidence label** | **strong evidence of growth** (найвищий рівень довіри) |
| **Якість даних** | 731 день (≈2 роки), 0 днів з нульовими переглядами, `sufficient_for_trend: true` |

### Що це означає для вашого продукту
- Українське читання статті **«Астрономія»** (`uk.wikipedia.org/wiki/Астрономія`) демонструє **стійке, статистично надійне зростання** за останні 2 роки.
- Тренд залишається **"strong evidence of growth"** навіть після виключення одного виявленого спайку (16 травня 2026 р., з-оцінка 49.6, 0.84% від сумарних переглядів) — тобто це не разовий хайп, а фонова динаміка.

### Наскільки цьому довіряти
- **Theil-Sen / Mann-Kendall** — робастні методи, стійкі до викидів та автокореляції. `confidence_label = "strong evidence of growth"` — це найвищий із чотирьох рівнів довіри (порівняно з `moderate`, `weak`, `insufficient data`).
- **Placebo-вірдикт** — наразі не працює (механізм порівняння з «кошиком» схожих статей ще не реалізований, `basket_size: 0`). Тому **опіратися слід саме на `confidence_label`**, а не на відсутній percentile-оцінку.
- Дані перевірені: звіт пройшов `verify` (11/11 числових тверджень співпали з вихідними обчисленнями).

---

**Звіт (PDF, 1 сторінка, верифікований):**  
`/home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data/reports/astronomy-uk_2026-09-26.pdf`

**Графіки:**  
- Тренд із позначеними спайками: `.../charts/astronomy-uk/trend_uk.png`  
- Деталізація спайка: `.../charts/astronomy-uk/spike_uk.png`

---

**Висновок для B2C-рішення:** Український аудиторійний сегмент показує **чіткий, довірливий рост інтересу** до астрономії. Це сильний сигнал, що локалізація астрономічного курсу українською мовою матиме попит, і ризик «переоцінити хайп» мінімальний.

## Generated PDFs

- `evals/results/02_astronomy_uk/data/reports/astronomy-uk_2026-09-26.pdf`

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.