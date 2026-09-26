# 03_english_learning_es_de_ja

**Model:** nvidia/nemotron-3-ultra-550b-a55b:free  
**Run at:** 2026-09-26T11:52:48.718101+00:00

## Prompt

Ми створюємо застосунок для вивчення англійської мови. Порівняй інтерес до вивчення англійської в іспанській (es), німецькій (de) та японській (ja) мовних розділах Wikipedia та підготуй короткий звіт: які аудиторії варто дослідити наступними й чому?

## Commands run

- `uv run curiosity-radar resolve --topic "English language learning" --languages es,de,ja --save-as english-learning-es-de-ja --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar fetch --project english-learning-es-de-ja --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar analyze --project english-learning-es-de-ja --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar chart --project english-learning-es-de-ja --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar report --project english-learning-es-de-ja --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`
- `uv run curiosity-radar verify --project english-learning-es-de-ja --data-dir /home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data`

## Final answer

Звіт готовий і перевірено (всі 29 числових тверджень у PDF збігаються з обрахованими даними). PDF: `/home/user/topic-scout/curiosity-radar/evals/results/03_english_learning_es_de_ja/data/reports/english-learning-es-de-ja_2026-09-26.pdf`

---

### Короткий підсумок для вашого додатка вивчення англійської

| Мова | Стаття | Тренд (Theil-Sen / Mann-Kendall) | Довіра | Спіки |
|------|--------|----------------------------------|--------|-------|
| **es** (Іспанська) | *Aprendizaje del inglés* | **Зростання** (slope 1.76·10⁻⁸/день, τ=0.86, p≈0) | **Strong evidence of growth** | 1 спік 2025-05-31 (z=17.8) |
| **ja** (Японська) | *英語学習* | **Зростання** (slope 9.46·10⁻⁹/день, τ=0.70, p≈0) | **Strong evidence of growth** | 1 спік 2026-03-27 (z=45.0) |
| **de** (Німецька) | *Englischunterricht* | **Без тренду** (slope ≈0, τ=−0.036, p=0.15) | No clear trend detected | — |

Усі три мови мають 731 день історії (2 роки) без пропусків днів.

---

### Які аудиторії дослідити наступними — і чому

1. **Іспанська (es) — пріоритет №1**  
   Найсильніший і найстабільніший зростаючий інтерес. tau=0.86 — це дуже висока монотонність тренду. Іспанською мовою говорять ~500 млн людей, а Wikipedia ES — одна з найбільших редакцій. Це найбільший ринок із чітким сигналом попиту.

2. **Японська (ja) — пріоритет №2**  
   Також чітке зростання (τ=0.70), хоч і з меншим нахилом. Японська аудиторія платоспроможна, високо оцифрована, і англійська є обов’язковою в школі/бізнесі — гарний fit для преміум/підписної моделі. Спік у березні 2026 р. варто перевірити на кореляцію з сезонністю (наприклад, початок навчального/фінансового року).

3. **Німецька (de) — низький пріоритет на цьому етапі**  
   Тренд відсутній (p=0.15). Німецька Wikipedia велика, але інтерес до теми «вивчення англійської» стагнаційний. Це може значити: (а) ринок насичений, (б) німецькомовні користувачі шукають інше (наприклад, *Business English*, *Englisch lernen* як пошуковий запит, а не енциклопедичну статтю), або (в) вони використовують інші платформи. Не відкладайте локалізацію під німецьку повністю, але **не робіть це першою** на основі цього сигналу.

---

### Важливі застереження (обов’язково зверніть увагу)

- **Placebo-верифікація недоступна** — у всіх трьох мовах `placebo.verdict = "insufficient comparison data..."` (знайдено 0 схожих статей для кошика). Це відома обмеженість інструменту (немає механізму автоматичного підбору кошика). **Не використовуйте placebo-перцентиль як доказ довіри** — покладайтеся на `confidence_label` (Theil-Sen / Mann-Kendall).
- Співвідношення нахилів (slope) нормалізоване, тому його абсолютні значення малі — дивіться на **rang** (es > ja > de) і **confidence_label**.
- Спіки (один на ES, один на JA) — це одноденні вибухи трафіку (вероятно, новини/вірусний контент/сезонність). Вони не змінюють висновок про тренд (виключення спіків дає той самий `confidence_label`).

---

### Наступні кроки для вас

1. **Глибший дайв у ES** — перевірте пов’язані статті (напр. *Inglés como segunda lengua*, *Cursos de inglés*), пошукових запитів у Google Trends для іспанською мовою країн (Мексика, Колумбія, Аргентина, Іспанія).
2. **Японська — сегментуйте** — розділіть B2C (споживачі) і B2B (корпоративне навчання), перевірте сезонність (березень/квітень — початок року).
3. **Німецька — не ігноруйте, а переформулюйте гіпотезу** — перевірте альтернативні назви статей (*Englisch lernen*, *Business English*, *Englischkurs*) або погляньте на сторінки-перенаправлення, які `fetch` не охопив.

PDF з графіками та повною методологією лежить за шляхом вище — його можна віддати інвесторам або команді локалізації.

## Generated PDFs

- `evals/results/03_english_learning_es_de_ja/data/reports/english-learning-es-de-ja_2026-09-26.pdf`

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.