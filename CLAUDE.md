# AGENTS.md (Claude Code uchun CLAUDE.md deb nomlang)

Bu loyiha: Telegram bot, sovrinli test orqali kanalga obunachi yig'adi.
To'liq reja: `PLAN.md`. Har doim avval uni o'qi.

## Ish tartibi
- Foydalanuvchi "keyingi" yoki "next" desa: `PLAN.md` dagi birinchi belgilanmagan `[ ]` qadamni ol va faqat shuni bajar.
- Qadam tugagach: "Qabul mezonlari"ni tekshir, testlarni yurgiz, qadamni `[x]` qil, 3-5 qatorli hisobot ber va to'xta. Keyingi qadamga o'zboshimcha o'tma.
- "N-qadam" desa, aynan o'sha qadamni bajar.
- Tushunarsiz joy bo'lsa, `PLAN.md` dagi "Qabul qilingan qarorlar"ga tayan. U yerda yo'q bo'lsa, 1 ta qisqa savol ber.

## Texnik qoidalar
- Python 3.12, aiogram 3 (to'liq async), SQLAlchemy 2 (async, asyncpg), Alembic, Redis, PyMuPDF, Pillow, openpyxl, APScheduler.
- Barcha sirlar `.env` da. Kodga token yozma.
- Handler ichida biznes-mantiq yozma: u `services/` da bo'lsin. Handler faqat chaqiradi.
- Foydalanuvchiga ko'rinadigan barcha matnlar `texts.py` (yoki `locales/`) da, o'zbek tilida.
- Har bir yangi jadval/maydon uchun Alembic migratsiya yarat.
- Har bir service uchun kamida asosiy holatlarga pytest yoz.
- Type hint va docstring (qisqa) yoz. `ruff` va `pytest` toza o'tishi shart.
- Ortiqcha kutubxona qo'shma. Qo'shsang, sababini hisobotda yoz.
