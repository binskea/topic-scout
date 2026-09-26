# 02_astronomy_uk

**Model:** nvidia/nemotron-3-super-120b-a12b:free  
**Run at:** 2026-09-26T20:30:56.194231+00:00

## Prompt

Ми думаємо додати курс з астрономії до освітнього застосунку. Чи зростає інтерес до цієї теми в україномовній Wikipedia, і наскільки цьому зростанню можна довіряти?

## Commands run

- `uv run curiosity-radar resolve --topic "astronomy" --languages uk --save-as astro_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar fetch --project astro_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`
- `uv run curiosity-radar analyze --project astro_uk --data-dir /home/user/topic-scout/curiosity-radar/evals/results/02_astronomy_uk/data`

## Final answer

Так, інтерес до астрономії в україномовній Wikipedia зростає, і цьому зростанню можна довіляти з високою ступінлю впевненості.

**Що показують дані**

- **Період аналізу:** 731 день (з 2024‑09‑23 по 2026‑09‑23), без днів з нульовими переглядами – достатньо для надійного визначального тренду.
- **Тренд:** Манн‑Кендалл показує статистично значущий збільшення інтересу (τ ≈ 0,64, p‑значення ≈ 1×10⁻¹⁴⁷). Теіл‑Сен скіл ≈ 2,3 × 10⁻⁸ нормованих переглядів на день.
- **Віра в тренд:** Мітка довіри — **“strong evidence of growth”** (сильні докази зростання). Це означає, що комбінація строгих статистичних тестів (Теіл‑Сен + Манн‑Кендалл) дає високий рівень впевненosti у зростанні.
- **Спike:** Виявлено один výrazний спайк 2026‑05‑16 (z‑MAD ≈ 49,6), але навіть після його виключення тренд залишається збільшуючимся з тією ж міткою довіри.
- **Плацебо‑перевірка:** Через недостатньо схожих статей для формування бакету порівняння, плацебо‑вердикт неможливо отримати (потрібно ≥10 статей, знайдено 0). За recommendations skill, у такому випадку reliance pokладається саме на мітку довіри з Теіл‑Сен/Манн‑Кендалл, а не на плацебо‑відсоток.

**Висновок**

Астрономія усвідомлено привертає все більше уваги читачів україномовної Вікіпедії, і цей зростаючий тренд підтримується надійними статистичними показниками. Тому додання курсу з астрономії до освітнього застосунку має хорошу потенційну аудиторію, особливо серед українською мовою користувачів, які вже проявляють стійке зростаюче Interesse до цієї теми.

## Generated PDFs

(none)

## Review checklist (PLAN.md Milestone 11)

- [ ] Follows the intended command sequence (resolve -> fetch -> analyze -> chart -> report -> verify) without needing hand-holding beyond what SKILL.md provides.
- [ ] The final report's numeric claims pass `verify`.
- [ ] A same-session follow-up tweak stays cheap (no unnecessary refetching) and produces a coherent updated answer.