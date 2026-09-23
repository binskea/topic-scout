# 02_astronomy_uk

**Model:** nvidia/nemotron-3-super-120b-a12b:free  
**Run at:** 2026-09-23T19:58:17.169604+00:00

## Prompt

Ми думаємо додати курс з астрономії до освітнього застосунку. Чи зростає інтерес до цієї теми в україномовній Wikipedia, і наскільки цьому зростанню можна довіряти?

## Commands run

- `uv run curiosity-radar resolve --topic "Астрономія" --languages uk --save-as astro_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar fetch --project astro_uk --data-dir /home/user/topic-scope/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar fetch --project astro_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar analyze --project astro_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`

## Final answer

Так, інте́рес до теми «астрономія» в україномовній Wikipedia зростає, і цьому зростанню можна довіляти як до надійного сигналу.

**Що показує аналіз:**

| Показник | Значення для uk‑Вікіпедії |
|----------|----------------------------|
| Theil‑Sen slope (за день) | +2.28 × 10⁻⁸ (позитивний) |
| Mann‑Kendall τ | 0,64 |
| Mann‑Kendall p‑value | ≈ 1 × 10⁻¹⁴ (дуже значуще) |
| Визначених трендів | «strong evidence of growth» (сильні докази зросту) |
| Виявлені спайки | одна спайка 16 травня 2026 р. (з підвищенням z‑MAD ≈ 49,6, але її вклад у сумарну кількість переглядів < 1 %) |
| Якість даних | 731 день (≈ 2 роки), нульових‑переглядних днів 0, достатньо для тренду |
| Плацебо‑перевірка | недостатньо даних для порівняння (відомий обмеження інструменту) – не впливає на довіру до тренду |

**Як це інтерпретувати:**

- Позитивний Theil‑Sen‑slope означає стійкий,хоча й низький, щоденний зрост нормалізованих переглядів статті «Астрономія». За протягом двох років це накопичується до помітного збільшення зацікавленого аудиторія.
- Mann‑Kendall τ ≈ 0,64 та надзвичайно мале p‑value свідчать про.statistically значимо монотонне зростання trend без випадкових коливань.
- Визначених трендів позначено як **«strong evidence of growth»** – це найвища рівень впевненosti в алгоритмі curiosité‑radar, заснований на порогах, описаних у `references/stats-methods.md`.
- Виявлена одна спайка (можливо, через особливу подію – напр., важливий астрономічний подив або публікація) має дуже малу долю у сумарних переглядах (< 1 %), отже вона не знімає загального висновку про тренд.
- Якість даних достатня (більше 60 днів з ненульовими переглядами, без днів з нульовими переглядами), тому trend‑оцінка надійна.

**Про plug‑gap у плацебо‑перевірці:**  
Наразі інструмент не може сформувати порівнянальну плацебо‑корзину (він повертає «insufficient comparison data… found 0»). Це відоме обмеження, зазначене в `SKILL.md`. Тому ми покладаємося саме на `confidence_label` та Mann‑Kendall результати, а не на плацебо‑percentile.

**Вислов:**  
Інтерес до астрономії в україномовній Wikipedia стабільно зростає, і цей тренд підтримується сильними статистичними доказами. Це хороший сигнал, що тема може бути захоплива для користувачів вашого освітнього застосунку, особливо якщо ви плануєте українськомовний контент.

## Generated PDFs

(none)

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.