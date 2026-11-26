# PLAN.md: "Test-Obuna" Telegram boti

## 0. Agent uchun yo'riqnoma
Foydalanuvchi "keyingi" desa, quyidagi qadamlar ro'yxatidan birinchi `[ ]` qadamni bajar.
Tugagach `[x]` qil va to'xta. Batafsil qoidalar: `AGENTS.md`.

## 1. Maqsad
Bot telegram kanalga obunachi yig'adi:
1. Admin botga test PDF faylini yuboradi.
2. Bot PDFning boshidagi 1-2 sahifani rasmga aylantirib post tayyorlaydi (rasm + test haqida ma'lumot + kanal havolasi + bot havolasi + test kodi).
3. Post kanalga chiqadi. Post ostida inline tugma bor: «📝 Testni ishlash».
4. Tugma bosilsa, bot ochiladi va foydalanuvchiga **eng oxirgi e'lon qilingan faol test** PDF yuboriladi.
5. Testni olish uchun **kanalga obuna bo'lish shart**.
6. Foydalanuvchi javoblarini botga `KOD 1a,2b,3d,...` ko'rinishida yuboradi. Obuna bo'lmasa, obunaga yo'naltiriladi.
7. **Ixtiyoriy funksiya (admin yoqadi):** javobni tekshirish uchun foydalanuvchi botga admin belgilagan sondagi odamni taklif qilgan bo'lishi kerak (referral).
8. Admin testni kim olganini, kim javob topshirganini ko'radi, natijalarni Excelga yuklaydi va boshqa keng imkoniyatlarga ega.

## 2. Qabul qilingan qarorlar (savol bermasdan shularga amal qil)
- Bir foydalanuvchi bir testga **1 marta** javob beradi (admin test yaratishda `max_attempts` ni o'zgartira oladi, standart 1).
- To'g'ri javoblar test tugaguncha **ko'rsatilmaydi**, faqat ball va foiz ko'rsatiladi. Admin yopgandan keyin kalit ochilishi mumkin (sozlama).
- Standart: bitta majburiy kanal, lekin DB va kod **bir nechta kanalni** qo'llab-quvvatlaydi.
- Til: o'zbek (lotin). Matnlar `texts.py` da, keyin ru qo'shish oson bo'lsin.
- Bir nechta sahifa rasmi Pillow bilan **bitta rasmga** birlashtiriladi (media group ga inline tugma qo'yib bo'lmaydi).
- Caption limiti 1024 belgi. Oshsa, qisqartir.
- Referral: taklif qilingan odam yangi foydalanuvchi, o'zi emas va kanalga obuna bo'lgan bo'lsa hisoblanadi.
- Webhook (prod), polling (dev).

- Test kodi faqat ASCII raqamlarda 1000–9999; qo'lda yoki «🎲 Avtomatik». String(4), raqam CHECK va WHERE status IN ('draft','active') partial unique index. Yopilgan kod qayta ishlatiladi; yangi faol test ustun, faqat eski yopilgan test qolsa «Bu test yopilgan».
- Admin kaliti faqat raqam+harf va vergul bilan: `1a,2b,3c` yoki `1a, 2b, 3c`. Vergul majburiy, bo'sh joy ixtiyoriy; yaratish va kalitni tahrirlash bir xil tekshiriladi.
- Javoblar va kalit faqat a, b, c, d; katta harflar kichikka o'tadi. Mustaqil to'rt xonali token kod, raqam+harf esa javob. Takror, yetishmagan/ortiqcha savol va noto'g'ri variant aniq ko'rsatiladi.
- Asosiy va bo'lim menyulari persistent ReplyKeyboardMarkup; navigation FSM data da. Har bo'limda Orqaga/Bosh menyu, kiritishda Bekor qilish/Orqaga. Adminlar /start da rol bo'yicha aniqlanadi, oddiy user admin tugmasini yozib huquq olmaydi.
- Inline faqat kanal posti, obuna, tasdiqlash/bekor qilish, sahifalash, test tanlash va test kartasi amallari uchun. Reply klaviaturalar keyboards/reply.py, inline keyboards/inline.py, navigatsiya services/nav_service.py, barcha matnlar locales/texts.py da.


## 3. Texnologiyalar
Python 3.12, aiogram 3, SQLAlchemy 2 (async) + asyncpg, Alembic, PostgreSQL 16, Redis 7,
PyMuPDF, Pillow, openpyxl, APScheduler, pydantic-settings, pytest + pytest-asyncio, ruff, Docker Compose.

## 4. Loyiha tuzilmasi

```
test-obuna-bot/
├─ AGENTS.md
├─ PLAN.md
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ .gitignore
├─ Dockerfile
├─ docker-compose.yml
├─ alembic.ini
├─ migrations/
│   ├─ env.py
│   └─ versions/
├─ storage/                      # (gitignore) vaqtinchalik PDF/rasm fayllar
│   ├─ pdf/
│   └─ previews/
├─ tests/
│   ├─ conftest.py
│   ├─ test_answer_parser.py
│   ├─ test_grading_service.py
│   ├─ test_pdf_service.py
│   ├─ test_referral_service.py
│   └─ test_subscription_service.py
└─ app/
    ├─ __init__.py
    ├─ main.py                   # bot yaratish, routerlar, polling/webhook
    ├─ config.py                 # pydantic-settings
    ├─ texts.py                  # barcha matnlar
    ├─ constants.py              # callback prefikslari, limitlar
    ├─ db/
    │   ├─ base.py               # Base, engine, session factory
    │   └─ models/
    │       ├─ __init__.py
    │       ├─ user.py
    │       ├─ channel.py
    │       ├─ test.py
    │       ├─ submission.py
    │       ├─ referral.py
    │       ├─ access_log.py
    │       ├─ admin.py
    │       ├─ broadcast.py
    │       └─ setting.py
    ├─ repositories/             # DB so'rovlari (CRUD)
    │   ├─ users.py
    │   ├─ tests.py
    │   ├─ submissions.py
    │   ├─ referrals.py
    │   ├─ channels.py
    │   └─ stats.py
    ├─ services/                 # biznes-mantiq
    │   ├─ subscription_service.py
    │   ├─ pdf_service.py
    │   ├─ post_service.py
    │   ├─ answer_parser.py
    │   ├─ grading_service.py
    │   ├─ referral_service.py
    │   ├─ ranking_service.py
    │   ├─ export_service.py
    │   ├─ broadcast_service.py
    │   └─ settings_service.py
    ├─ handlers/
    │   ├─ __init__.py           # routerlarni yig'ish
    │   ├─ user/
    │   │   ├─ start.py          # /start, deep link (test_<id>, ref_<id>)
    │   │   ├─ get_test.py       # testni yuborish
    │   │   ├─ submit_answers.py # javoblarni qabul qilish
    │   │   ├─ referral.py       # shaxsiy havola, progress
    │   │   ├─ my_results.py
    │   │   └─ common.py         # /help, noma'lum xabar
    │   └─ admin/
    │       ├─ menu.py           # /admin
    │       ├─ add_test.py       # FSM: yangi test
    │       ├─ tests_manage.py
    │       ├─ stats.py
    │       ├─ results.py
    │       ├─ export.py
    │       ├─ broadcast.py
    │       ├─ channels.py
    │       ├─ users.py          # ban/unban, qidiruv
    │       ├─ admins.py
    │       └─ settings.py
    ├─ keyboards/
    │   ├─ user.py
    │   └─ admin.py
    ├─ states/
    │   ├─ add_test.py
    │   ├─ broadcast.py
    │   └─ admin_misc.py
    ├─ middlewares/
    │   ├─ db_session.py
    │   ├─ user_upsert.py        # foydalanuvchini DBga yozish/yangilash
    │   ├─ ban_check.py
    │   ├─ antiflood.py
    │   └─ subscription.py
    ├─ filters/
    │   ├─ is_admin.py
    │   └─ is_private.py
    ├─ scheduler/
    │   ├─ setup.py
    │   └─ jobs.py               # muddat yopish, rejalashtirilgan post, obuna qayta tekshiruv
    └─ utils/
        ├─ deeplink.py
        ├─ files.py
        ├─ formatting.py
        └─ logging.py
```

## 5. Ma'lumotlar bazasi (qisqacha)

| Jadval | Maydonlar |
|---|---|
| users | id, tg_id (unique), username, full_name, lang, joined_at, last_active, is_banned, referrer_id, is_subscribed, left_channel_at |
| channels | id, tg_chat_id (unique), title, username, invite_link, is_required, is_main |
| tests | id, code (String(4), draft/active orasida partial unique), title, description, pdf_file_id, pdf_path, preview_file_id, questions_count, answer_key (JSON: {"1":"a",...}), status (draft/active/closed), start_at, end_at, referral_required (bool), referral_count (int), max_attempts, prizes_count, show_key_after_close, channel_id, channel_post_id, scheduled_at, created_by, created_at |
| submissions | id, test_id, user_id, answers (JSON), correct_count, wrong_count, score_percent, submitted_at, rank. Unique(test_id, user_id, attempt_no) |
| referrals | id, inviter_id, invited_id (unique), test_id (null bo'lishi mumkin), created_at, is_valid |
| test_access_log | id, test_id, user_id, got_at. Unique(test_id, user_id) |
| admins | id, tg_id (unique), role (owner/admin/moderator), added_by |
| broadcasts | id, text, media_file_id, audience, status, total, sent, failed, created_at |
| settings | key, value |

## 6. Callback data konvensiyasi
`prefix:action:id`, masalan `t:view:12`, `t:close:12`, `adm:stats`, `sub:check`, `ref:progress`.
Prefikslar `constants.py` da. 64 baytdan oshmasin.

## 7. Javob formati (parser talablari)
Kirish misollari (hammasi qabul qilinsin):
- `4829 1a,2b,3d,4a`
- `4829\n1a 2b 3d 4a`
- `4829 1-a, 2-b, 3-d`
- `4829 abcdabcd` (faqat harflar, tartib bo'yicha)
- Katta/kichik harf farqsiz, faqat `a-d` oralig'idagi variantlar
- Kod keyin ham kelishi mumkin: `1a,2b,3d 4829`
Xatolarda foydalanuvchiga aniq tushuntirish: nechta javob kutilgan, qaysi raqam yetishmayapti.
Kod ko'rsatilmasa, eng oxirgi faol test olinadi (foydalanuvchiga ayt).

## 8. Qadamlar

### [ ] 1-qadam. Loyiha skeleti va muhit
**Qil:**
- Yuqoridagi tuzilmadagi papkalar va bo'sh `__init__.py` fayllar.
- `pyproject.toml` (bog'liqliklar, ruff, pytest sozlamalari).
- `.env.example`: `BOT_TOKEN, ADMIN_IDS, DATABASE_URL, REDIS_URL, WEBHOOK_URL, WEBHOOK_SECRET, MAIN_CHANNEL_ID, BOT_USERNAME, TZ=Asia/Tashkent`.
- `app/config.py` (pydantic-settings), `app/utils/logging.py`.
- `Dockerfile`, `docker-compose.yml` (bot, postgres, redis), `.gitignore`, `README.md` (ishga tushirish yo'riqnomasi).
**Qabul mezonlari:** `docker compose up -d postgres redis` ishlaydi, `python -c "from app.config import settings"` xatosiz o'tadi, `ruff check` toza.

### [ ] 2-qadam. DB modellari va migratsiya
**Qil:** 5-bo'limdagi barcha modellar (SQLAlchemy 2 async, `Mapped[...]`), `db/base.py`, Alembic sozlash (async), birinchi migratsiya.
**Qabul mezonlari:** `alembic upgrade head` toza bazada ishlaydi, `alembic downgrade base` ham. Barcha FK va unique cheklovlar bor.

### [ ] 3-qadam. Bot yadrosi, middleware va /start
**Qil:**
- `main.py`: Bot, Dispatcher, Redis storage (FSM), polling rejimi.
- Middleware: `db_session`, `user_upsert`, `ban_check`, `antiflood` (Redis, 1 soniyada ~3 so'rov).
- `/start` oddiy salomlashish, `/help`.
- Barcha handlerlar faqat private chatda ishlasin (`is_private`).
**Qabul mezonlari:** bot ishga tushadi, `/start` foydalanuvchini `users` ga yozadi, ban qilingan foydalanuvchiga javob bermaydi.

### [ ] 4-qadam. Obuna tekshiruvi
**Qil:**
- `subscription_service.check(user_id)`: barcha `is_required` kanallar bo'yicha `getChatMember`, natija Redisda 45 soniya keshlanadi. Statuslar: member, administrator, creator = obuna.
- `subscription.py` middleware/dekorator: obuna talab qilinadigan handlerlarga qo'llanadi.
- Obuna bo'lmasa: «📢 Kanalga obuna bo'ling» xabari (har bir kanal uchun URL tugma) + «✅ Tekshirish» callback. Tekshirishdan keyin to'xtagan amalni davom ettir (masalan, deep link dagi testni yubor).
- Bot kanalda admin emas bo'lsa, adminga ogohlantirish xabari yubor (xato tutish).
**Qabul mezonlari:** obuna bo'lmagan foydalanuvchi blok qilinadi, obuna bo'lgach «Tekshirish» orqali o'tadi, kesh ishlaydi, testlar bor.

### [ ] 5-qadam. Admin kirish va menyu
**Qil:** `is_admin` filtri (admins jadvali + `ADMIN_IDS` dan avtomatik seed, birinchisi owner), `/admin` menyu (reply tugmalar, 7-bo'limdagi tuzilma), rollar bo'yicha ruxsat dekoratori. Kanal qo'shish/o'chirish (`channels.py`): admin kanal ID yoki username yuboradi, bot adminligini tekshiradi.
**Qabul mezonlari:** oddiy foydalanuvchi `/admin` ni ocholmaydi, owner kanal qo'sha oladi, noto'g'ri kanal uchun tushunarli xato chiqadi.

**Yangi talab va qabul mezoni:** Admin va user bosh menyulari reply; /start rolni tekshiradi. Admin bo‘lmagan yuborgan admin tugmasi rad etiladi. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 6-qadam. PDF servis
**Qil:** `pdf_service.py`
- `render_preview(pdf_path, pages=2, zoom=2.0) -> bytes|path`: PyMuPDF bilan boshidagi 1-2 sahifani rasmga aylantir.
- 2 sahifa bo'lsa, Pillow bilan yonma-yon yoki ketma-ket **bitta rasmga** birlashtir (kenglik ~1600px dan oshmasin, JPEG sifat 85, hajmi 10 MB dan oshmasin).
- Sahifalar soni 1 bo'lsa, bitta rasm. Shifrlangan/buzilgan PDF uchun aniq xato.
**Qabul mezonlari:** `tests/test_pdf_service.py` (namunaviy PDF yaratib sinash) o'tadi, natija Telegram `send_photo` talablariga mos (o'lchamlar yig'indisi <= 10000, hajm <= 10MB).

### [ ] 7-qadam. Admin: yangi test yaratish (FSM)
**Qil:** `add_test.py` + `states/add_test.py`. Oqim:
1. Admin PDF yuboradi (`document`, mime `application/pdf`). Faylni `storage/pdf/` ga yuklab ol (20 MB limit, undan kattasiga tushunarli xabar) va `file_id` ni saqla.
2. Savollar: test nomi, **test kodi** (unikal, avtotaklif beradi), qisqa tavsif, savollar soni, **to'g'ri javoblar** (7-bo'limdagi parser bilan; soni savollar soniga teng bo'lishi shart), tugash muddati (sana-vaqt yoki "cheksiz"), sovrinlar soni, referral talab (yoq/o'chir va N), urinishlar soni (standart 1), kanal tanlash.
3. Preview (6-qadamdagi rasm + caption) ko'rsatiladi: «✅ Tasdiqlash», «✏️ Tahrirlash», «❌ Bekor».
4. Tasdiqlansa, test `draft` holatida saqlanadi. Keyingi qadamda nashr qilinadi.
**Qabul mezonlari:** barcha validatsiyalar ishlaydi (dublikat kod, noto'g'ri kalit formati), bekor qilish FSM ni tozalaydi, DBda test to'g'ri saqlanadi.

**Yangi talab va qabul mezoni:** Kod 1000–9999, Avtomatik yoki qo'lda; draft/active bandlik tekshiruvi. Kalit a–d parseridan. FSM Orqaga/Bekor; Cheksiz va referral yoqish/o‘chirish tugmalari; preview nashr/reja/menga/tahrir. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 8-qadam. Post generator va kanalga nashr
**Qil:** `post_service.py`
- Caption shabloni: sarlavha, qisqa tavsif, 🔑 Test kodi, muddat, sovrinlar, 📢 kanal havolasi, 🤖 bot havolasi. Limit 1024 belgi.
- Inline tugma: «📝 Testni ishlash» URL = `https://t.me/<BOT>?start=test_<id>`.
- Rejimlar: «Hozir kanalga yuborish» (bot o'zi), «Menga yuborish» (admin o'zi nusxalab joylaydi), «Rejalashtirish» (vaqt tanlanadi, 16-qadamda job bog'lanadi).
- Nashrdan keyin: `status=active`, `channel_post_id` saqlanadi, `start_at` qo'yiladi.
**Qabul mezonlari:** kanalda rasm + caption + tugma to'g'ri chiqadi, tugma botni deep link bilan ochadi, `tests.status` yangilanadi.

**Yangi talab va qabul mezoni:** Caption «🔑 Test kodi: 4829». Nashr/reja/menga inline test kartasi amallari. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 9-qadam. Foydalanuvchi: testni olish (deep link)
**Qil:** `start.py`, `get_test.py`
- `/start test_<id>`: obunani tekshir, so'ng PDFni `file_id` orqali yubor (sozlamaga qarab `protect_content`). `test_access_log` ga yoz (unikal).
- `/start` (parametrsiz) yoki «📝 Oxirgi test» tugmasi: **eng oxirgi e'lon qilingan faol** test yuboriladi.
- Test faol bo'lmasa/muddati o'tgan bo'lsa, tushunarli xabar.
- PDF yuborilgach: test kodi va javob formati ko'rsatmasi (`4829 1a,2b,3d`) yuboriladi.
- `/start ref_<user_id>` ni ham shu yerda ushla (10-qadamda mantiq to'ldiriladi).
**Qabul mezonlari:** obunasiz foydalanuvchi PDF olmaydi, obunadan keyin avtomatik oladi, access log takrorlanmaydi, oxirgi test to'g'ri tanlanadi.

**Yangi talab va qabul mezoni:** User reply: Oxirgi test, Javob yuborish (FSM), Natijalarim, Do'st taklif qilish, Yordam. Misol 4829 1a,2b. Admin /start panelga. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 10-qadam. Javoblarni qabul qilish va tekshirish
**Qil:** `answer_parser.py`, `grading_service.py`, `submit_answers.py`
- Parser 7-bo'limdagi barcha formatlarni qo'llab-quvvatlasin, xatolarni aniq qaytarsin. Birinchi `tests/test_answer_parser.py` ni yoz.
- Tekshiruv zanjiri: obuna, test kodi, test faolligi va muddati, urinishlar limiti, referral sharti (11-qadamgacha stub: har doim o'tadi), javoblar soni.
- Baholash: to'g'ri soni, xato soni, foiz. To'g'ri javoblar ochiq ko'rsatilmaydi (2-bo'limdagi qaror).
- Natija `submissions` ga yoziladi (unique cheklov himoyasi, poyga holatlariga tayyor).
- «📊 Mening natijalarim» (`my_results.py`).
**Qabul mezonlari:** parser va grading testlari o'tadi, takroriy yuborish rad etiladi, muddati o'tgan testga javob qabul qilinmaydi.

**Yangi talab va qabul mezoni:** Faqat a–d; kod alohida 4 xonali token. Kod boshida/oxirida, ko‘p qator, raqamli va ixcham format. Takror, bo'sh, chegara, yetishmagan savollar testlari. Yopilgan kod uchun aniq xabar. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 11-qadam. Referral tizimi (ixtiyoriy funksiya)
**Qil:** `referral_service.py`, `referral.py`, 10-qadamdagi stubni almashtir.
- Shaxsiy havola: `https://t.me/<BOT>?start=ref_<user_id>`.
- Taklif faqat shartlar bajarilganda `is_valid=True`: yangi foydalanuvchi, o'zi emas, bir marta, **kanalga obuna bo'lgan**. Obuna bo'lmasa, «pending», obuna bo'lgach avtomatik hisobga o'tadi.
- Test `referral_required=True` bo'lsa: foydalanuvchi `referral_count` ta valid taklif to'plamaguncha javob qabul qilinmaydi. «3/5 ta do'st qo'shildi» progress va havola tugmasi ko'rsatiladi.
- Taklif qilingan odam kanaldan chiqsa, taklif bekor bo'ladi (16-qadamdagi davriy job bilan).
- Taklif qilganga yangi odam qo'shilgani haqida xabar yuboriladi.
**Qabul mezonlari:** `test_referral_service.py` o'tadi (o'zini taklif qilish, ikki marta hisoblash, obunasiz taklif), funksiya o'chiq bo'lsa hech narsa o'zgarmaydi.

### [ ] 12-qadam. Admin: testlarni boshqarish
**Qil:** `tests_manage.py`: testlar ro'yxati (faol / qoralama / yopilgan, sahifalash), test kartasi, tugmalar: to'xtatish/davom ettirish, yopish, muddatni uzaytirish, kanalga qayta yuborish, javob kalitini tahrirlash (**natijalarni avtomatik qayta hisoblash**), tavsifni tahrirlash, o'chirish (tasdiq bilan).
**Qabul mezonlari:** kalit o'zgarganda barcha `submissions` qayta hisoblanadi va reyting yangilanadi, yopilgan testga javob qabul qilinmaydi.

**Yangi talab va qabul mezoni:** Reply holat filtrlari va kod qidiruvi; inline sahifalash/test kartasi. Yopilgan kod qayta ishlatiladi; kalit a–d. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 13-qadam. Admin: statistika va reyting
**Qil:** `stats.py`, `results.py`, `ranking_service.py`, `repositories/stats.py`
- Umumiy: foydalanuvchilar soni, bugun/hafta/oy o'sishi, kanaldan chiqqanlar.
- Test bo'yicha: **nechta kishi testni oldi**, nechta kishi **javob topshirdi**, o'rtacha ball, har bir savol bo'yicha to'g'ri javob foizi (qiyin savollar).
- Reyting: TOP-10/50 (ball bo'yicha kamayish, teng bo'lsa `submitted_at` bo'yicha oldin yuborgan yuqori), `rank` ni yozish.
- Referral statistikasi: eng ko'p taklif qilganlar TOP.
**Qabul mezonlari:** raqamlar DB bilan mos, reyting tartibi to'g'ri, katta ro'yxatlar sahifalanadi.

**Yangi talab va qabul mezoni:** Statistika va Natijalar reply bo‘limlari: Umumiy/Test/Kunlik/Referral TOP, TOP-10/50/g‘olib/natijalar posti. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 14-qadam. Admin: Excel eksport
**Qil:** `export_service.py`, `export.py` (openpyxl, xotirada `BytesIO`, `send_document`).
Fayllar (.xlsx), har birida sarlavha qatori qotirilgan, ustun kengligi avtomoslangan:
- Test natijalari: №, F.I.O, username, tg_id, to'g'ri, xato, foiz, vaqt, o'rin.
- Testni olganlar ro'yxati.
- Barcha foydalanuvchilar (obuna holati, qo'shilgan sana, referrer).
- Referral hisoboti.
Katta ro'yxatlar uchun write-only rejim.
**Qabul mezonlari:** fayl Excelda ochiladi, ma'lumotlar to'g'ri, 10 000+ qator bilan ishlaydi.

**Yangi talab va qabul mezoni:** Excel reply: natijalar, olganlar, barcha userlar, referral; kerak bo'lsa inline test tanlash. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 15-qadam. G'oliblarni aniqlash va natijalar posti
**Qil:** Test yopilganda (qo'lda yoki avtomatik) `prizes_count` bo'yicha g'oliblar aniqlanadi. Admin ko'rib chiqib tasdiqlaydi. Natijalar posti kanalga yuboriladi (TOP ro'yxat, g'oliblar). G'oliblarga bot shaxsiy xabar yuboradi. Kalit ochish sozlamasi yoqilgan bo'lsa, to'g'ri javoblar ham yuboriladi.
**Qabul mezonlari:** teng ballarda tartib qoidasi ishlaydi, g'oliblarga xabar boradi, post kanalga chiqadi.

### [ ] 16-qadam. Scheduler va avtomatik vazifalar
**Qil:** `scheduler/` (APScheduler, `Asia/Tashkent`, vazifalar bazada saqlansin yoki qayta ishga tushganda tiklansin).
- Rejalashtirilgan postni vaqtida nashr qilish.
- Muddati tugagan testlarni avtomatik yopish (+ adminga xabar).
- Tugashiga 1 soat/24 soat qolganda ishtirok etmaganlarga eslatma (sozlamada yoqiladi).
- Har kuni obunani qayta tekshirish: kanaldan chiqqanlarni `left_channel_at` bilan belgilash, referral larni bekor qilish.
**Qabul mezonlari:** bot qayta ishga tushsa vazifalar yo'qolmaydi, ikki marta ishlamaydi.

### [ ] 17-qadam. Broadcast (ommaviy xabar)
**Qil:** `broadcast_service.py`, `broadcast.py`. Auditoriya: hamma / test qatnashchilari / testni olib javob bermaganlar / kanaldan chiqqanlar. Matn, rasm, tugma bilan. Oldindan ko'rish va tasdiq. Tezlik ~20-25 xabar/s, `TelegramRetryAfter` va `TelegramForbiddenError` (bloklaganlar) ishlovi. Jarayon progressi va yakuniy hisobot (yuborildi/xato).
**Qabul mezonlari:** bloklagan foydalanuvchilar belgilanadi, jarayon bekor qilinadi, adminga yakuniy statistika keladi.

**Yangi talab va qabul mezoni:** Reply auditoriyalar: hamma/qatnashchilar/olib topshirmaganlar/chiqqanlar; FSM Bekor/Orqaga. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 18-qadam. Foydalanuvchilar, adminlar, ban va sozlamalar
**Qil:** `users.py` (qidirish tg_id/username bo'yicha, ban/unban, foydalanuvchi kartasi: natijalar, takliflar), `admins.py` (rol berish: owner/admin/moderator, ruxsatlar jadvali), `settings.py` (global sozlamalar: `protect_content`, referral standart qiymati, eslatmalar, kalitni ko'rsatish, til), `channels.py` ni yakunlash.
**Qabul mezonlari:** moderator faqat ruxsat etilgan bo'limlarni ko'radi, ban darhol ta'sir qiladi, sozlamalar Redis/DB orqali yangilanadi.

**Yangi talab va qabul mezoni:** Users, Kanallar, Sozlamalar, Adminlar reply ichki menyulari; owner-only sozlama/admin, sozlama holati tugmada. Orqaga ota menyuga; noma'lum matn joriy menyuni qaytaradi. Menyu holati va ruxsatlar test bilan tekshirilsin.

### [ ] 19-qadam. Ishonchlilik va xavfsizlik
**Qil:**
- Global error handler: xatolar logga va owner ga xabar sifatida.
- Barcha tashqi chaqiruvlarga retry/timeout.
- Poyga holatlari: javob yuborish va referral hisoblashda DB tranzaksiya + unique cheklov.
- Rate limit (antiflood) sinovdan o'tkaz.
- Foydalanuvchi kiritishlarini tozalash (HTML escape, uzunlik limiti).
- Sirlar logga tushmasin.
**Qabul mezonlari:** ataylab xato qilish stsenariylari (takroriy bosish, parallel yuborish) buzmaydi.

### [ ] 20-qadam. (Ixtiyoriy) Ko'p tillilik va sertifikat
**Qil:** `texts.py` ni `locales/uz.json`, `locales/ru.json` ga o'tkaz, foydalanuvchi tilini tanlash, kerak bo'lsa Pillow bilan ishtirokchi sertifikati rasmi.
**Qabul mezonlari:** til almashtirilsa barcha matnlar o'zgaradi, yo'q kalit uchun zaxira (uz) ishlaydi.

### [ ] 21-qadam. Testlar va sifat
**Qil:** `tests/` dagi barcha fayllarni to'ldir (parser, grading, referral, subscription (mock), pdf, export). Kamida asosiy xizmatlar uchun qamrov 70%+. `ruff` va `pytest` CI skripti (`Makefile` yoki GitHub Actions).
**Qabul mezonlari:** `pytest` va `ruff check` toza.

### [ ] 22-qadam. Deploy
**Qil:** Docker Compose (bot, postgres, redis, nginx), webhook rejimi (`WEBHOOK_URL`, secret token), HTTPS yo'riqnomasi, kunlik `pg_dump` backup skripti (cron), `healthcheck`, `README.md` da to'liq deploy bosqichlari va birinchi sozlash (bot kanalga admin qilinadi, `.env`, `alembic upgrade head`, owner ni belgilash).
**Qabul mezonlari:** `docker compose up -d` bilan noldan ishga tushadi, qayta yuklashdan keyin ma'lumotlar saqlanadi, backup fayl hosil bo'ladi.

## 9. Yakuniy qabul tekshiruvi (smoke test)
1. Admin PDF yuboradi, test yaratadi, kanalga post chiqadi.
2. Yangi foydalanuvchi postdagi tugmani bosadi, obuna bo'lmagani uchun obunaga yo'naltiriladi.
3. Obuna bo'lgach, PDF oladi.
4. `4829 1a,2b,...` yuboradi, natija oladi. Takroran yuborsa rad etiladi.
5. Referral yoqilgan testda taklifsiz tekshirmaydi. Do'st qo'shilgach tekshiradi.
6. Admin statistika, reyting va Excel oladi, testni yopadi, g'oliblar postini chiqaradi.

## 10. Tuzatishlar

Ushbu faylda [x] qadamlar yo‘q; mavjud kodga yangi talablar moslashtiriladi, qadamlar holati o‘zgartirilmaydi.

## 11. Reply navigatsiya xaritasi

Bosh menyularda Orqaga/Bosh menyu bo'lmaydi. Ichki bo'limlarda pastki qatorda
«⬅️ Orqaga» va «🏠 Bosh menyu», FSM da «⬅️ Orqaga» va «❌ Bekor qilish» mavjud.
Menyu FSM data dagi `nav_menu` da saqlanadi, bekor qilish ota bo'limga qaytaradi.

| Menyu | Tugmalar |
|---|---|
| Foydalanuvchi | 📝 Oxirgi test; ✍️ Javob yuborish; 📊 Natijalarim; 👥 Do'st taklif qilish; ℹ️ Yordam |
| Admin | ➕ Yangi test; 📋 Testlar; 📊 Statistika; 🏆 Natijalar; 📥 Excel hisobotlar; 📢 Xabar yuborish; 👥 Foydalanuvchilar; 📺 Kanallar; ⚙️ Sozlamalar; 👮 Adminlar; 🔙 Foydalanuvchi rejimi |
| Testlar | 🟢 Faol testlar; 📝 Qoralamalar; 🔴 Yopilganlar; 🔎 Kod bo'yicha qidirish |
| Statistika | 📈 Umumiy; 🧪 Test bo'yicha; 🗓 Kunlik o'sish; 🔗 Referral TOP |
| Natijalar | 🥇 TOP-10; 🥈 TOP-50; 🏁 G'oliblarni aniqlash; 📣 Natijalarni kanalga yuborish |
| Excel | 📄 Test natijalari; 📄 Testni olganlar; 📄 Barcha foydalanuvchilar; 📄 Referral hisoboti |
| Xabar yuborish | 👥 Hammaga; ✅ Qatnashchilarga; ⏳ Olib topshirmaganlarga; 🚪 Chiqib ketganlarga |
| Foydalanuvchilar | 🔎 Qidirish; 🚫 Ban qilish; ♻️ Unban; 🚫 Banlanganlar ro'yxati |
| Kanallar | ➕ Kanal qo'shish; 📋 Kanallar ro'yxati; 🗑 Kanal o'chirish |
| Sozlamalar | 🔗 Referral standarti; 🔒 Kontentni himoya qilish; 🔔 Eslatmalar; 🔑 Javob kalitini ochish; 🌐 Til |
| Adminlar | ➕ Admin qo'shish; 📋 Adminlar ro'yxati; 🗑 O'chirish |

Sozlamalar va Adminlar faqat owner uchun. Boshqa bo'limlar ham mavjud rol ruxsatlari
bo'yicha yashiriladi va service darajasida tekshiriladi. Sozlama tugmasida ✅/❌ holat ko'rinadi.
Javob yuborish FSM misoli `4829 1a,2b,3d`; bevosita yozilgan javob ham qabul qilinadi.
