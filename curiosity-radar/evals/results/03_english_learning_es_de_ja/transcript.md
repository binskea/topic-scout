# 03_english_learning_es_de_ja

**Model:** nvidia/nemotron-3-super-120b-a12b:free  
**Run at:** 2026-09-23T19:58:50.998808+00:00

## Prompt

Ми створюємо застосунок для вивчення англійської мови. Порівняй інтерес до вивчення англійської в іспанській (es), німецькій (de) та японській (ja) мовних розділах Wikipedia та підготуй короткий звіт: які аудиторії варто дослідити наступними й чому?

## Commands run

- `uv run curiosity-radar resolve --topic "learning English" --languages es,de,ja --save-as english_learning`
- `uv run curiosity-radar fetch --project english_learning`
- `uv run curiosity-radar analyze --project english_learning`
- `uv run curiosity-radar chart --project english_learning`
- `uv run curiosity-radar report --project english_learning`
- `uv run curiosity-radar verify --project english_learning`

## Final answer

**Короткий звіт про інтерес до вивчення англійської мови в Вікіпедії (es, de, ja)**  

| Мова | Тренд (Theil‑Sen slope/день) | Mann‑Kendall p‑value | τ (Kendall) | Виснадійкість тренду | Коментар |
|------|------------------------------|----------------------|------------|----------------------|----------|
| **іспанська (es)** | **+1.76 × 10⁻⁸** | 6.98 × 10⁻²⁶⁴ | 0.858 | **strong evidence of growth** | Стабільний зростаючий інтерес, виявлено один резкий спайк (2025‑05‑31), але він не змінює целомудренний висновок про зростання. |
| **японська (ja)** | **+9.46 × 10⁻⁹** | 7.38 × 10⁻¹⁷⁶ | 0.699 | **strong evidence of growth** | Також чітке зростання; один výrazний спайк (2026‑03‑27). |
| **німецька (de)** | **‑1.67 × 10⁻¹⁰** (практично нуль) | 0.148 | –0.036 | **no clear trend detected** | Дані не показують_statistically значимого зростання чи спаду; інтерес практично стабільний. |

### Висновок для бізнесу
- **Періоритетні аудиторії для наступного дослідження:** **іспанська** та **японська** мовні групи. У обох випадках тренд виявляється як “strong evidence of growth” з дуже маленькими p‑values (< 10⁻¹⁶) та високими τ‑коефіцієнтами, що свідчить про стабільне та výrazне збільшення числа переглядів статей про вивчення англійської мови за останні два роки.
- **Друга аудиторія (німецька):** Наразі немає очевидного зростання; якщо ви плануєте входь на німецькоязычний ринок, варто провести додаткові опитування або тестування, щоб зрозуміти, чи є прихований попит, який не відображається у переглядах Вікіпедії.

### Чому саме ці аудиторії?
1. **Статистична значущість** – Mãнн‑Кендалл тести показують ekstremálně маловірожну нульову гіпотезу (p ≪ 0.001) для es та ja.
2. **Ефект розміру** – Коефіцієнт τ > 0.65 указыває на сильну monotonic залежність між часом та нормалізованим інтересом.
3. **Консистентність після видалення спайків** – Тренд залишається “strong evidence of growth” і після виключення виявлених anomalous spikes, що свідчить про його стійкість.
4. **Практична relevance** – Зростане інтерес у Вікіпедії часто correлює з реальним попитом на освітні ресурси (курси, додатки, репетиторство).

### Рекомендація
Сфокусуйте наступний етап вивчення ринку на **іспанською та японською мовами** (наприклад, локалізація інтерфейсу, контенту та маркетингових кампаній). Для німецькоговорячого сегменту слід спочатку провести пілотне опитування або A/B‑тест, щоб перевірити чи прихований попит існує, прежде ніж робити великі інвестиції.

*Джерело: curiosité‑radar аналіз (Theil‑Sen/Mann‑Kendall) для проекту “english_learning”, дані за 2024‑09‑23 – 2026‑09‑23, перевірено (verify status: verified).*

## Generated PDFs

- `evals/results/03_english_learning_es_de_ja/data/reports/english_learning_2026-09-23.pdf`

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.