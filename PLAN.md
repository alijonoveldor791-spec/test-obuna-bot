# PLAN.md: "Test-Obuna" Telegram boti

## 0. Agent uchun yo'riqnoma
Foydalanuvchi "keyingi" yoki "next" desa, faqat "Tuzatishlar va soddalashtirish"
bo'limidagi birinchi belgilanmagan `[ ]` R qadamni bajar.
**Yangi topshiriq holati:** foydalanuvchining «barchasini hozir bajar» ko'rsatmasi
bilan R11 to'liq bajarildi. R9 ham hujjat va sifat tekshiruvlari bilan yakunlandi. R11 ning barcha talablari
bitta qadam sifatida tekshirildi; qo'shimcha "keyingi" buyrug'i kutilmadi.
Eski 1–22 qadamlar audit
uchun saqlangan; ularning ochiq bandlari avtomatik navbatga kirmaydi.
Har R qadamda faqat o'sha ish bajariladi, yangi/o'zgargan xatti-harakat uchun test
qo'shiladi, `ruff check .` va `pytest` toza o'tadi. Shundan keyin `[x]` belgilanadi,
o'zgargan fayllar ro'yxati bilan qisqa hisobot beriladi va to'xtaladi.
Sirlar logga yozilmaydi. R9 da `TEST_INFRA=1` integratsiya tekshiruvi ham majburiy.
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

## 2. Qabul qilingan qarorlar (yangi talablar)

- Kanal postidagi tugma: https://t.me/BOT?start=test . Bosilsa EN OXIRGI FAOL test
  yuboriladi. Eski test_<id> havolalari ham shu mantiqqa tushsin (eng oxirgi faol test).
- ~~Test hayot sikli: qoralama -> faol -> yopiq. "To'xtatib turish" (pause/resume),
  "rejalashtirilgan post" (schedule), urinishlar sonini so'rash OLIB TASHLANSIN.~~
  **R11 bilan almashtirilgan:** rejalashtirish `draft` + `scheduled_at=start_at`
  orqali qaytadi; pause/resume va urinish savoli qaytmaydi.
  max_attempts ustuni qolsin, qiymati doim 1.
- **R11 ustuvor:** yangi test 5 qadamdan iborat; boshlanish va tugash alohida.
  Sovrinlar va g'oliblar logikasi olib tashlanadi; yopilgan test natijalari TOP-10
  sifatida bir marta e'lon qilinadi. To'liq talablar R11 da. Eski bo'limlardagi
  chizilgan bandlar amaldagi talab emas; tarixiy `[x]` belgilar R11 bajarilganini anglatmaydi.
- Referral har bir test uchun ALOHIDA hisoblanadi: faqat test.start_at dan keyin
  yaratilgan va hozir obuna bo'lgan takliflar sanaladi (migratsiyasiz).
- Faqat o'zbek tili. /language, "Til" sozlamasi va ru tanlovi UI dan olib tashlansin
  (locales/ru.json fayli qolsin, lekin ishlatilmasin).
- Buyruqlar faqat: /start va /admin. /test, /results, /referral, /help, /cancel,
  /language olib tashlansin (hammasi reply tugmalarda mavjud).
- Inline tugmalar FAQAT ikkita joyda: (1) kanal postidagi "📝 Testni ishlash";
  (2) obuna so'rovidagi kanal URL tugmalari + "✅ Tekshirish". Qolgan hamma narsa
  ReplyKeyboardMarkup (resize_keyboard=True, is_persistent=True).
  Shuning uchun callback_data asosidagi barcha admin oqimlari (new:, exp:, bc:, t:,
  list:, nav:, rank:, res:) va ularga tegishli kod/matnlar O'CHIRILSIN.
- Admin matnli buyruq grammatikasi ("ban 123", "del 5", "required 1 0", JSON
  sozlamalar) O'CHIRILSIN. Hamma kiritish yo'naltirilgan: bitta savol, bitta javob.

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

## 6. Callback data konvensiyasi (eski kod holati)

R4 dan keyin faqat obuna tekshiruvi callbacki qoladi. Quyidagilar mavjud eski
kodning tavsifi; admin callbacklari R4/R8 da o‘chiriladi.
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

## 8. Eski 1–22 qadamlar: mavjud kod auditi

Quyidagi tavsiflar avvalgi talablar tarixidir. `[x]` asosiy funksional kod mavjudligini
bildiradi, yangi R talablar bajarilganini yoki barcha real Telegram stsenariylari
tekshirilganini bildirmaydi. Qisman bajarilgan bandlar sababi bilan `[ ]` qoldirilgan.
Ziddiyat bo'lsa, ushbu mavzuda R11 eng ustuvor; qolgan masalalarda 2-bo'limdagi
qarorlar va R1–R9 talablari saqlanadi.

### [ ] 1-qadam. Loyiha skeleti va muhit
**Qil:**
- Yuqoridagi tuzilmadagi papkalar va bo'sh `__init__.py` fayllar.
- `pyproject.toml` (bog'liqliklar, ruff, pytest sozlamalari).
- `.env.example`: `BOT_TOKEN, ADMIN_IDS, DATABASE_URL, REDIS_URL, WEBHOOK_URL, WEBHOOK_SECRET, MAIN_CHANNEL_ID, BOT_USERNAME, TZ=Asia/Tashkent`.
- `app/config.py` (pydantic-settings), `app/utils/logging.py`.
- `Dockerfile`, `docker-compose.yml` (bot, postgres, redis), `.gitignore`, `README.md` (ishga tushirish yo'riqnomasi).
**Qabul mezonlari:** `docker compose up -d postgres redis` ishlaydi, `python -c "from app.config import settings"` xatosiz o'tadi, `ruff check` toza.

**Kod auditi:** Qisman: skelet, sozlamalar, Docker va bog'liqliklar mavjud; README da amaliy ishga tushirish yo'riqnomasi yo'q. R9 da to'ldiriladi.

### [x] 2-qadam. DB modellari va migratsiya
**Qil:** 5-bo'limdagi barcha modellar (SQLAlchemy 2 async, `Mapped[...]`), `db/base.py`, Alembic sozlash (async), birinchi migratsiya.
**Qabul mezonlari:** `alembic upgrade head` toza bazada ishlaydi, `alembic downgrade base` ham. Barcha FK va unique cheklovlar bor.

**Kod auditi:** SQLAlchemy modellar, async Alembic va ikki migratsiya mavjud; upgrade/downgrade oldingi tekshiruvda o'tgan.

### [x] 3-qadam. Bot yadrosi, middleware va /start
**Qil:**
- `main.py`: Bot, Dispatcher, Redis storage (FSM), polling rejimi.
- Middleware: `db_session`, `user_upsert`, `ban_check`, `antiflood` (Redis, 1 soniyada ~3 so'rov).
- `/start` oddiy salomlashish, `/help`.
- Barcha handlerlar faqat private chatda ishlasin (`is_private`).
**Qabul mezonlari:** bot ishga tushadi, `/start` foydalanuvchini `users` ga yozadi, ban qilingan foydalanuvchiga javob bermaydi.

**Kod auditi:** Bot, Redis FSM, middleware, /start va ban tekshiruvi mavjud. Tranzaksiya/private/antiflood kamchiliklari R1, buyruqlar R4 da tuzatiladi.

### [x] 4-qadam. Obuna tekshiruvi
**Qil:**
- `subscription_service.check(user_id)`: barcha `is_required` kanallar bo'yicha `getChatMember`, natija Redisda 45 soniya keshlanadi. Statuslar: member, administrator, creator = obuna.
- `subscription.py` middleware/dekorator: obuna talab qilinadigan handlerlarga qo'llanadi.
- Obuna bo'lmasa: «📢 Kanalga obuna bo'ling» xabari (har bir kanal uchun URL tugma) + «✅ Tekshirish» callback. Tekshirishdan keyin to'xtagan amalni davom ettir (masalan, deep link dagi testni yubor).
- Bot kanalda admin emas bo'lsa, adminga ogohlantirish xabari yubor (xato tutish).
**Qabul mezonlari:** obuna bo'lmagan foydalanuvchi blok qilinadi, obuna bo'lgach «Tekshirish» orqali o'tadi, kesh ishlaydi, testlar bor.

**Kod auditi:** Ko'p kanal, 45 soniyali kesh, obuna to'sig'i va davom ettirish mavjud. API xatosidagi DB o'zgarishi R1 da tuzatiladi.

### [x] 5-qadam. Admin kirish va menyu
**Qil:** `is_admin` filtri (admins jadvali + `ADMIN_IDS` dan avtomatik seed, birinchisi owner), `/admin` menyu (reply tugmalar, 7-bo'limdagi tuzilma), rollar bo'yicha ruxsat dekoratori. Kanal qo'shish/o'chirish (`channels.py`): admin kanal ID yoki username yuboradi, bot adminligini tekshiradi.
**Qabul mezonlari:** oddiy foydalanuvchi `/admin` ni ocholmaydi, owner kanal qo'sha oladi, noto'g'ri kanal uchun tushunarli xato chiqadi.

**Yangi talab va qabul mezoni:** Admin va user bosh menyulari reply; /start rolni tekshiradi. Admin bo‘lmagan yuborgan admin tugmasi rad etiladi. Menyu holati va ruxsatlar test bilan tekshirilsin.

**Kod auditi:** ADMIN_IDS seed, DB rollari, admin panel va kanal boshqaruvi mavjud. Soddalashtirilgan ruxsat/menyu R4–R7 da.

### [x] 6-qadam. PDF servis
**Qil:** `pdf_service.py`
- `render_preview(pdf_path, pages=2, zoom=2.0) -> bytes|path`: PyMuPDF bilan boshidagi 1-2 sahifani rasmga aylantir.
- 2 sahifa bo'lsa, Pillow bilan yonma-yon yoki ketma-ket **bitta rasmga** birlashtir (kenglik ~1600px dan oshmasin, JPEG sifat 85, hajmi 10 MB dan oshmasin).
- Sahifalar soni 1 bo'lsa, bitta rasm. Shifrlangan/buzilgan PDF uchun aniq xato.
**Qabul mezonlari:** `tests/test_pdf_service.py` (namunaviy PDF yaratib sinash) o'tadi, natija Telegram `send_photo` talablariga mos (o'lchamlar yig'indisi <= 10000, hajm <= 10MB).

**Kod auditi:** PDF tekshiruv, birlashtirilgan preview va o'lcham/hajm cheklovlari hamda servis testlari mavjud.

### [x] 7-qadam. Admin: yangi test yaratish (FSM)
~~**Qil:** `add_test.py` + `states/add_test.py`. Oqim:~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~1. Admin PDF yuboradi (`document`, mime `application/pdf`). Faylni `storage/pdf/` ga yuklab ol (20 MB limit, undan kattasiga tushunarli xabar) va `file_id` ni saqla.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~2. Savollar: test nomi, **test kodi** (unikal, avtotaklif beradi), qisqa tavsif, savollar soni, **to'g'ri javoblar** (7-bo'limdagi parser bilan; soni savollar soniga teng bo'lishi shart), tugash muddati (sana-vaqt yoki "cheksiz"), sovrinlar soni, referral talab (yoq/o'chir va N), urinishlar soni (standart 1), kanal tanlash.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~3. Preview (6-qadamdagi rasm + caption) ko'rsatiladi: «✅ Tasdiqlash», «✏️ Tahrirlash», «❌ Bekor».~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~4. Tasdiqlansa, test `draft` holatida saqlanadi. Keyingi qadamda nashr qilinadi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~**Qabul mezonlari:** barcha validatsiyalar ishlaydi (dublikat kod, noto'g'ri kalit formati), bekor qilish FSM ni tozalaydi, DBda test to'g'ri saqlanadi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~**Yangi talab va qabul mezoni:** Kod 1000–9999, Avtomatik yoki qo'lda; draft/active bandlik tekshiruvi. Kalit a–d parseridan. FSM Orqaga/Bekor; Cheksiz va referral yoqish/o‘chirish tugmalari; preview nashr/reja/menga/tahrir. Menyu holati va ruxsatlar test bilan tekshirilsin.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~**Kod auditi:** PDFdan preview va qoralamagacha FSM, 4 xonali kod va kalit validatsiyasi mavjud. Yangi 10 bosqichli oqim R5 da.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

### [x] 8-qadam. Post generator va kanalga nashr
**Qil:** `post_service.py`
~~- Caption shabloni: sarlavha, qisqa tavsif, 🔑 Test kodi, muddat, sovrinlar, 📢 kanal havolasi, 🤖 bot havolasi. Limit 1024 belgi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~- Inline tugma: «📝 Testni ishlash» URL = `https://t.me/<BOT>?start=test_<id>`.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~- Rejimlar: «Hozir kanalga yuborish» (bot o'zi), «Menga yuborish» (admin o'zi nusxalab joylaydi), «Rejalashtirish» (vaqt tanlanadi, 16-qadamda job bog'lanadi).~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~- Nashrdan keyin: `status=active`, `channel_post_id` saqlanadi, `start_at` qo'yiladi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~**Qabul mezonlari:** kanalda rasm + caption + tugma to'g'ri chiqadi, tugma botni deep link bilan ochadi, `tests.status` yangilanadi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~**Yangi talab va qabul mezoni:** Caption «🔑 Test kodi: 4829». Nashr/reja/menga inline test kartasi amallari. Menyu holati va ruxsatlar test bilan tekshirilsin.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

**Kod auditi:** Caption, kanal/admin nashri, status va post ID saqlash mavjud. Umumiy deep link va diskdan mustaqillik R3 da.

### [x] 9-qadam. Foydalanuvchi: testni olish (deep link)
**Qil:** `start.py`, `get_test.py`
- `/start test_<id>`: obunani tekshir, so'ng PDFni `file_id` orqali yubor (sozlamaga qarab `protect_content`). `test_access_log` ga yoz (unikal).
- `/start` (parametrsiz) yoki «📝 Oxirgi test» tugmasi: **eng oxirgi e'lon qilingan faol** test yuboriladi.
- Test faol bo'lmasa/muddati o'tgan bo'lsa, tushunarli xabar.
- PDF yuborilgach: test kodi va javob formati ko'rsatmasi (`4829 1a,2b,3d`) yuboriladi.
- `/start ref_<user_id>` ni ham shu yerda ushla (10-qadamda mantiq to'ldiriladi).
**Qabul mezonlari:** obunasiz foydalanuvchi PDF olmaydi, obunadan keyin avtomatik oladi, access log takrorlanmaydi, oxirgi test to'g'ri tanlanadi.

**Yangi talab va qabul mezoni:** User reply: Oxirgi test, Javob yuborish (FSM), Natijalarim, Do'st taklif qilish, Yordam. Misol 4829 1a,2b. Admin /start panelga. Menyu holati va ruxsatlar test bilan tekshirilsin.

**Kod auditi:** Obunadan keyin PDF, access log, oxirgi test va deep linklar mavjud. Eski linklarni oxirgi faol testga yo'naltirish R3 da.

### [x] 10-qadam. Javoblarni qabul qilish va tekshirish
**Qil:** `answer_parser.py`, `grading_service.py`, `submit_answers.py`
- Parser 7-bo'limdagi barcha formatlarni qo'llab-quvvatlasin, xatolarni aniq qaytarsin. Birinchi `tests/test_answer_parser.py` ni yoz.
- Tekshiruv zanjiri: obuna, test kodi, test faolligi va muddati, urinishlar limiti, referral sharti (11-qadamgacha stub: har doim o'tadi), javoblar soni.
- Baholash: to'g'ri soni, xato soni, foiz. To'g'ri javoblar ochiq ko'rsatilmaydi (2-bo'limdagi qaror).
- Natija `submissions` ga yoziladi (unique cheklov himoyasi, poyga holatlariga tayyor).
- «📊 Mening natijalarim» (`my_results.py`).
**Qabul mezonlari:** parser va grading testlari o'tadi, takroriy yuborish rad etiladi, muddati o'tgan testga javob qabul qilinmaydi.

**Yangi talab va qabul mezoni:** Faqat a–d; kod alohida 4 xonali token. Kod boshida/oxirida, ko‘p qator, raqamli va ixcham format. Takror, bo'sh, chegara, yetishmagan savollar testlari. Yopilgan kod uchun aniq xabar. Menyu holati va ruxsatlar test bilan tekshirilsin.

**Kod auditi:** Parser, baholash, urinish/vaqt cheklovlari, natijalar va testlar mavjud. Kalit/user formatlarini birlashtirish R3 da.

### [x] 11-qadam. Referral tizimi (ixtiyoriy funksiya)
**Qil:** `referral_service.py`, `referral.py`, 10-qadamdagi stubni almashtir.
- Shaxsiy havola: `https://t.me/<BOT>?start=ref_<user_id>`.
- Taklif faqat shartlar bajarilganda `is_valid=True`: yangi foydalanuvchi, o'zi emas, bir marta, **kanalga obuna bo'lgan**. Obuna bo'lmasa, «pending», obuna bo'lgach avtomatik hisobga o'tadi.
- Test `referral_required=True` bo'lsa: foydalanuvchi `referral_count` ta valid taklif to'plamaguncha javob qabul qilinmaydi. «3/5 ta do'st qo'shildi» progress va havola tugmasi ko'rsatiladi.
- Taklif qilingan odam kanaldan chiqsa, taklif bekor bo'ladi (16-qadamdagi davriy job bilan).
- Taklif qilganga yangi odam qo'shilgani haqida xabar yuboriladi.
**Qabul mezonlari:** `test_referral_service.py` o'tadi (o'zini taklif qilish, ikki marta hisoblash, obunasiz taklif), funksiya o'chiq bo'lsa hech narsa o'zgarmaydi.

**Kod auditi:** Atributsiya, valid/pending referral, progress va obunadan chiqishni bekor qilish mavjud. Test kesimidagi hisob R1 da tuzatiladi.

### [x] 12-qadam. Admin: testlarni boshqarish
~~**Qil:** `tests_manage.py`: testlar ro'yxati (faol / qoralama / yopilgan, sahifalash), test kartasi, tugmalar: to'xtatish/davom ettirish, yopish, muddatni uzaytirish, kanalga qayta yuborish, javob kalitini tahrirlash (**natijalarni avtomatik qayta hisoblash**), tavsifni tahrirlash, o'chirish (tasdiq bilan).~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
**Qabul mezonlari:** kalit o'zgarganda barcha `submissions` qayta hisoblanadi va reyting yangilanadi, yopilgan testga javob qabul qilinmaydi.

**Yangi talab va qabul mezoni:** Reply holat filtrlari va kod qidiruvi; inline sahifalash/test kartasi. Yopilgan kod qayta ishlatiladi; kalit a–d. Menyu holati va ruxsatlar test bilan tekshirilsin.

~~**Kod auditi:** Testlar, kartalar, yopish, muddat/kalit tahriri va qayta hisoblash mavjud. Reply amallar va faqat qoralamani fayli bilan o'chirish R5 da.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

### [ ] 13-qadam. Admin: statistika va reyting
**Qil:** `stats.py`, `results.py`, `ranking_service.py`, `repositories/stats.py`
- Umumiy: foydalanuvchilar soni, bugun/hafta/oy o'sishi, kanaldan chiqqanlar.
- Test bo'yicha: **nechta kishi testni oldi**, nechta kishi **javob topshirdi**, o'rtacha ball, har bir savol bo'yicha to'g'ri javob foizi (qiyin savollar).
- Reyting: TOP-10/50 (ball bo'yicha kamayish, teng bo'lsa `submitted_at` bo'yicha oldin yuborgan yuqori), `rank` ni yozish.
- Referral statistikasi: eng ko'p taklif qilganlar TOP.
**Qabul mezonlari:** raqamlar DB bilan mos, reyting tartibi to'g'ri, katta ro'yxatlar sahifalanadi.

~~**Yangi talab va qabul mezoni:** Statistika va Natijalar reply bo‘limlari: Umumiy/Test/Kunlik/Referral TOP, TOP-10/50/g‘olib/natijalar posti. Menyu holati va ruxsatlar test bilan tekshirilsin.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

**Kod auditi:** Qisman: umumiy/test statistikasi, TOP-10/50 va referral agregati mavjud; katta reyting ro'yxatlari sahifalanmagan. Yangi qisqartirilgan UI va hisobotlar R6 da.

### [x] 14-qadam. Admin: Excel eksport
**Qil:** `export_service.py`, `export.py` (openpyxl, xotirada `BytesIO`, `send_document`).
Fayllar (.xlsx), har birida sarlavha qatori qotirilgan, ustun kengligi avtomoslangan:
- Test natijalari: №, F.I.O, username, tg_id, to'g'ri, xato, foiz, vaqt, o'rin.
- Testni olganlar ro'yxati.
- Barcha foydalanuvchilar (obuna holati, qo'shilgan sana, referrer).
- Referral hisoboti.
Katta ro'yxatlar uchun write-only rejim.
**Qabul mezonlari:** fayl Excelda ochiladi, ma'lumotlar to'g'ri, 10 000+ qator bilan ishlaydi.

**Yangi talab va qabul mezoni:** Excel reply: natijalar, olganlar, barcha userlar, referral; kerak bo'lsa inline test tanlash. Menyu holati va ruxsatlar test bilan tekshirilsin.

**Kod auditi:** To'rt xil Excel eksporti, write-only rejim, sarlavha qotirish, ustun kengligi va testlar mavjud; yangi kirish nuqtalari R6 da.

### [x] 15-qadam. G'oliblarni aniqlash va natijalar posti
~~**Qil:** Test yopilganda (qo'lda yoki avtomatik) `prizes_count` bo'yicha g'oliblar aniqlanadi. Admin ko'rib chiqib tasdiqlaydi. Natijalar posti kanalga yuboriladi (TOP ro'yxat, g'oliblar). G'oliblarga bot shaxsiy xabar yuboradi. Kalit ochish sozlamasi yoqilgan bo'lsa, to'g'ri javoblar ham yuboriladi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~**Qabul mezonlari:** teng ballarda tartib qoidasi ishlaydi, g'oliblarga xabar boradi, post kanalga chiqadi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~**Kod auditi:** Reytingdan g'oliblar, tasdiq, kanal posti, shaxsiy xabar va kalit e'loni mavjud. Reply tasdiqlash R5–R6 da.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

### [x] 16-qadam. Scheduler va avtomatik vazifalar
**Qil:** `scheduler/` (APScheduler, `Asia/Tashkent`, vazifalar bazada saqlansin yoki qayta ishga tushganda tiklansin).
- Rejalashtirilgan postni vaqtida nashr qilish.
- Muddati tugagan testlarni avtomatik yopish (+ adminga xabar).
- Tugashiga 1 soat/24 soat qolganda ishtirok etmaganlarga eslatma (sozlamada yoqiladi).
- Har kuni obunani qayta tekshirish: kanaldan chiqqanlarni `left_channel_at` bilan belgilash, referral larni bekor qilish.
**Qabul mezonlari:** bot qayta ishga tushsa vazifalar yo'qolmaydi, ikki marta ishlamaydi.

**Kod auditi:** DBdan tiklanuvchi scheduler, muddat, eslatma va kunlik obuna vazifalari mavjud. Ajratilgan joblar va cheklangan qayta urinishlar R1–R2 da.

### [x] 17-qadam. Broadcast (ommaviy xabar)
**Qil:** `broadcast_service.py`, `broadcast.py`. Auditoriya: hamma / test qatnashchilari / testni olib javob bermaganlar / kanaldan chiqqanlar. Matn, rasm, tugma bilan. Oldindan ko'rish va tasdiq. Tezlik ~20-25 xabar/s, `TelegramRetryAfter` va `TelegramForbiddenError` (bloklaganlar) ishlovi. Jarayon progressi va yakuniy hisobot (yuborildi/xato).
**Qabul mezonlari:** bloklagan foydalanuvchilar belgilanadi, jarayon bekor qilinadi, adminga yakuniy statistika keladi.

**Yangi talab va qabul mezoni:** Reply auditoriyalar: hamma/qatnashchilar/olib topshirmaganlar/chiqqanlar; FSM Bekor/Orqaga. Menyu holati va ruxsatlar test bilan tekshirilsin.

**Kod auditi:** Auditoriya, matn/rasm/tugma, preview/tasdiq, batch/progress, bekor qilish va xato ishlovi mavjud. Uch auditoriyali reply oqimi R7 da.

### [x] 18-qadam. Foydalanuvchilar, adminlar, ban va sozlamalar
**Qil:** `users.py` (qidirish tg_id/username bo'yicha, ban/unban, foydalanuvchi kartasi: natijalar, takliflar), `admins.py` (rol berish: owner/admin/moderator, ruxsatlar jadvali), `settings.py` (global sozlamalar: `protect_content`, referral standart qiymati, eslatmalar, kalitni ko'rsatish, til), `channels.py` ni yakunlash.
**Qabul mezonlari:** moderator faqat ruxsat etilgan bo'limlarni ko'radi, ban darhol ta'sir qiladi, sozlamalar Redis/DB orqali yangilanadi.

**Yangi talab va qabul mezoni:** Users, Kanallar, Sozlamalar, Adminlar reply ichki menyulari; owner-only sozlama/admin, sozlama holati tugmada. Orqaga ota menyuga; noma'lum matn joriy menyuni qaytaradi. Menyu holati va ruxsatlar test bilan tekshirilsin.

**Kod auditi:** User qidirish/ban, admin rollari, kanal va DB sozlamalari mavjud. Matn grammatikasisiz yo'naltirilgan kiritish va owner sozlamalari R7 da.

### [ ] 19-qadam. Ishonchlilik va xavfsizlik
**Qil:**
- Global error handler: xatolar logga va owner ga xabar sifatida.
- Barcha tashqi chaqiruvlarga retry/timeout.
- Poyga holatlari: javob yuborish va referral hisoblashda DB tranzaksiya + unique cheklov.
- Rate limit (antiflood) sinovdan o'tkaz.
- Foydalanuvchi kiritishlarini tozalash (HTML escape, uzunlik limiti).
- Sirlar logga tushmasin.
**Qabul mezonlari:** ataylab xato qilish stsenariylari (takroriy bosish, parallel yuborish) buzmaydi.

**Kod auditi:** Qisman: error handler, Telegram retry/timeout, lock/unique himoyasi va antiflood testlari mavjud; barcha tashqi chaqiruvlar va xato holatlari to'liq qoplanmagan. R1–R2 va R9 da tekshiriladi.

### [ ] 20-qadam. (Ixtiyoriy) Ko'p tillilik va sertifikat
**Qil:** `texts.py` ni `locales/uz.json`, `locales/ru.json` ga o'tkaz, foydalanuvchi tilini tanlash, kerak bo'lsa Pillow bilan ishtirokchi sertifikati rasmi.
**Qabul mezonlari:** til almashtirilsa barcha matnlar o'zgaradi, yo'q kalit uchun zaxira (uz) ishlaydi.

**Kod auditi:** Qisman: uz/ru locale va fallback bor, lekin barcha matnlar tilga to'liq mos emas; sertifikat yo'q (ixtiyoriy). Yangi qaror bo'yicha faqat o'zbek UI qoladi; R4/R8 da ru ishlatilishi olib tashlanadi.

### [ ] 21-qadam. Testlar va sifat
**Qil:** `tests/` dagi barcha fayllarni to'ldir (parser, grading, referral, subscription (mock), pdf, export). Kamida asosiy xizmatlar uchun qamrov 70%+. `ruff` va `pytest` CI skripti (`Makefile` yoki GitHub Actions).
**Qabul mezonlari:** `pytest` va `ruff check` toza.

**Kod auditi:** Qisman: servis testlari va 70% coverage talab qiluvchi CI bor; joriy kod uchun 70% qamrov natijasi tasdiqlanmagan, yangi oqimlar testlari hali yo'q. R9 da yakuniy tekshiruv.

### [ ] 22-qadam. Deploy
**Qil:** Docker Compose (bot, postgres, redis, nginx), webhook rejimi (`WEBHOOK_URL`, secret token), HTTPS yo'riqnomasi, kunlik `pg_dump` backup skripti (cron), `healthcheck`, `README.md` da to'liq deploy bosqichlari va birinchi sozlash (bot kanalga admin qilinadi, `.env`, `alembic upgrade head`, owner ni belgilash).
**Qabul mezonlari:** `docker compose up -d` bilan noldan ishga tushadi, qayta yuklashdan keyin ma'lumotlar saqlanadi, backup fayl hosil bo'ladi.

**Kod auditi:** Qisman: Compose, nginx, webhook, healthcheck va backup skripti mavjud; HTTPS/cron/birinchi admin yo'riqnomasi va to'liq prod smoke test dalili yetishmaydi. R9 da.

## 9. Yakuniy qabul tekshiruvi (smoke test)
1. Admin PDF yuboradi, test yaratadi, kanalga post chiqadi.
2. Yangi foydalanuvchi postdagi tugmani bosadi, obuna bo'lmagani uchun obunaga yo'naltiriladi.
3. Obuna bo'lgach, PDF oladi.
4. `4829 1a,2b,...` yuboradi, natija oladi. Takroran yuborsa rad etiladi.
5. Referral yoqilgan testda taklifsiz tekshirmaydi. Do'st qo'shilgach tekshiradi.
~~6. Admin statistika, reyting va Excel oladi, testni yopadi, g'oliblar postini chiqaradi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

## 10. Yangi admin va foydalanuvchi menyulari (R4–R7 uchun talab)

Menyularni deklarativ jadvalga o'tkaz: app/menus.py (menu_id -> sarlavha, tugmalar,
ruxsat, ota menyu). Orqaga/Bosh menyu umumiy mantiq bo'lsin, yangi tugma qo'shish
bitta qator bo'lsin. nav_service.py dagi uzun if zanjirini shu jadvalga almashtir.

Admin bosh menyusi (rolga qarab yashiriladi):
  [➕ Yangi test]          [📋 Testlar]
  [📊 Statistika]          [📥 Hisobotlar]
  [📢 Xabar yuborish]      [👥 Foydalanuvchilar]
  [⚙️ Sozlamalar]  (faqat owner)
  [🔙 Foydalanuvchi rejimi]

Rollar: owner = hammasi; admin = Sozlamalar'dan tashqari hammasi; moderator = faqat
Testlar (ko'rish), Statistika, Hisobotlar.

~~➕ Yangi test  (qadamlar ketma-ket, har savolda "3/10" ko'rsatkich, pastda~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~[⬅️ Orqaga] [❌ Bekor qilish]):~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~1 PDF yuborish~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~2 Nomi~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~3 Kod: [🎲 Avtomatik] yoki 4 xonali son (1000-9999)~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~4 Tavsif: [⏭ O'tkazib yuborish]~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~5 Savollar soni~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~6 To'g'ri javoblar kaliti (foydalanuvchi javobi bilan BIR XIL parser)~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~7 Muddat: [♾ Cheksiz] [24 soat] [3 kun] [7 kun] yoki "YYYY-MM-DD HH:MM"~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~8 Sovrinlar soni~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~9 Referral: [🚫 Talab qilinmasin] [3] [5] [10] yoki son kiritish~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~10 Kanal: faqat 1 ta kanal bo'lsa so'ralmaydi; 2+ bo'lsa kanallar tugma bo'ladi~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~Preview (rasm + caption) keyin reply tugmalar:~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~[📤 Kanalga yuborish] [📨 Menga yuborish]~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~[💾 Qoralama sifatida saqlash] [✏️ Qaytadan boshlash] [❌ Bekor qilish]~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~"Menga yuborish" = admin postni o'zi joylaydi, test faol bo'ladi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~📋 Testlar:~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~[🟢 Faol] [📝 Qoralamalar] [🔴 Yopilganlar] [🔎 Kod bo'yicha]~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~Testlar RO'YXATI ham reply tugmalarda: har bir tugma "#12 · 4829 · Nomi",~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~sahifalash [◀️] [▶️] (8 tadan), tugma matnidan #id ajratib ol.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~Test tanlangach TEST MENYUSI (holatga qarab tugmalar):~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
     ~~qoralama: [📤 Kanalga yuborish] [📨 Menga yuborish] [✏️ Tahrirlash] [🗑 O'chirish]~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
     ~~faol:     [📊 Statistika] [🏆 Reyting] [📥 Natijalar Excel] [📥 Testni olganlar Excel]~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
               ~~[⏳ Muddatni o'zgartirish] [🔑 Kalitni o'zgartirish] [🏁 Testni yopish]~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
     ~~yopiq:    [🏆 Reyting] [📥 Natijalar Excel] [📥 Testni olganlar Excel]~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
               ~~[🥇 G'oliblarni e'lon qilish] [🔑 Kalitni o'zgartirish]~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~Xavfli amallar (yopish, o'chirish, g'oliblarni e'lon qilish) oldin~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~[✅ Ha, tasdiqlayman] [❌ Yo'q] so'raydi. FAQAT qoralama o'chirilishi mumkin.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
   ~~O'chirilganda PDF fayl ham diskdan o'chsin.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

📊 Statistika: [📈 Umumiy (bugun/hafta/oy o'sishi, chiqib ketganlar)] [🔗 Referral TOP]
📥 Hisobotlar: [👥 Barcha foydalanuvchilar] [🔗 Referral hisoboti]
   (test hisobotlari Test menyusida; "growth" va "ref_top" dublikatlari olib tashlansin)
📢 Xabar yuborish: [👥 Hammaga] [✅ Test qatnashchilariga] [⏳ Olib topshirmaganlarga]
   (test kerak bo'lsa reply ro'yxatdan tanlanadi) -> matn/rasm -> ixtiyoriy tugma
   -> preview -> [✅ Yuborish] [❌ Bekor]. "Chiqib ketganlarga" olib tashlansin.
👥 Foydalanuvchilar: [🚫 Ban] [♻️ Unban] [📋 Banlanganlar] (tg_id yoki @username so'raladi)
⚙️ Sozlamalar (owner): [📺 Kanallar] [👮 Adminlar]
   [🔒 Kontentni himoya: ✅/❌] [🔔 Eslatmalar: ✅/❌] [🔑 Kalit e'londa: ✅/❌]
   Kanallar: [➕ Qo'shish] [📋 Ro'yxat] [🗑 O'chirish] (o'chirish reply ro'yxatdan).
     Barcha qo'shilgan kanallar majburiy. Birinchisi asosiy, o'chirilsa keyingisi asosiy.
   Adminlar: [➕ Qo'shish] [📋 Ro'yxat] [🗑 O'chirish]; qo'shishda tg_id so'raladi,
     keyin [Admin] [Moderator] tugmalari.
   "referral standarti" sozlamasi olib tashlansin.
Har bir menyuda pastki qator: [⬅️ Orqaga] [🏠 Bosh menyu].

Foydalanuvchi menyusi o'zgarmaydi: [📝 Oxirgi test] [✍️ Javob yuborish]
[📊 Natijalarim] [👥 Do'st taklif qilish] [ℹ️ Yordam].

## 11. Tuzatishlar va soddalashtirish

R1–R8 va R11 bajarildi. R11 foydalanuvchining barcha o'zgarishlarni hozir kiritish
ko'rsatmasi bilan bajarildi. R9 ham bajarildi; R10 berilmagan va qo'shilmagan.
Har safar faqat bitta belgilangan R qadam bajariladi.

### [x] R1. Xatolarni tuzatish (xizmat darajasi, UI ga tegmasdan)

**Qil:**
a) Referral test bo'yicha (1-bo'lim qarori). Test: boshqa test uchun to'plangan
     takliflar yangi testga o'tmaydi.
  b) subscription_service.check: Telegram API xatosida foydalanuvchi holati va
     referral O'ZGARMASIN (xato = "noma'lum"); interaktiv to'siqda esa obuna yo'q
     deb hisoblab to'sib turaversin, lekin DBga yozmasin.
  c) Kunlik obuna job: sekinlashtirilgan (<= 20 so'rov/s), xatoda to'xtamasin,
     xatolar sonini logga yozsin.
  d) users upsert: foydalanuvchi yozsa is_blocked=False bo'lsin.
  e) channel qo'shishda is_main mavjud kanal qayta qo'shilganda yo'qolmasin.
  f) DatabaseMiddleware: foydalanuvchi upsert alohida qisqa tranzaksiyada COMMIT
     bo'lsin (BusinessError bo'lsa ham user va referral yozuvi qolsin).
  g) Antiflood: callback uchun callback.answer() chaqirilsin; middlewarelar faqat
     private chatda ishlasin (guruh odamlari users ga yozilmasin).
  h) Barcha Asia/Tashkent o'rniga settings.tz.
  i) notify_admins(bot, session, text): bildirishnomalar DBdagi owner/admin larga
     borsin (hozir faqat .env dagilarga). Barcha chaqiruvlarni shunga o'tkaz.
  Testlar: har bir band uchun kamida 1 ta.

**Qabul mezonlari:** a–i bandlarining har biri uchun kamida bittadan test bor. Boshqa test takliflari yangi testga o'tmaydi; API xatosi DB/referralni o'zgartirmaydi; kunlik tekshiruv <=20 so'rov/s va xatoda davom etadi. User upsert BusinessError dan mustaqil saqlanadi; guruh userlari yozilmaydi, callback javobsiz qolmaydi; is_blocked va is_main tuzatiladi. Vaqt settings.tz dan, bildirishnoma DB owner/adminlariga boradi. UI o'zgarmaydi. Har o‘zgargan xatti-harakat uchun test; `ruff check .` va `pytest` toza. Hisobotda o‘zgargan fayllar ro‘yxati beriladi va shu qadamdan keyin to‘xtaladi.


**R1 bajarilish hisoboti:** Referral test boshlanishidan keyingi, hozir obuna takliflar bilan hisoblanadi; API xatosida obuna/referral o‘zgarmaydi. Kunlik tekshiruv cheklangan tezlikda xatolarni sanab davom etadi. Alohida user/referral commit, unblock, is_main, private middleware/callback, settings.tz va DB owner/admin bildirishnomalari tuzatildi. UI o‘zgarmadi. `ruff check .` toza; `TEST_INFRA=1 pytest -q`: **110 passed**.

**R1 o‘zgargan fayllar:**
- `PLAN.md`
- `app/main.py`
- `app/middlewares/antiflood.py`
- `app/middlewares/ban_check.py`
- `app/middlewares/db_session.py`
- `app/middlewares/user_upsert.py`
- `app/repositories/referrals.py`
- `app/repositories/stats.py`
- `app/repositories/users.py`
- `app/scheduler/jobs.py`
- `app/scheduler/setup.py`
- `app/services/admin_service.py`
- `app/services/broadcast_service.py`
- `app/services/grading_service.py`
- `app/services/post_service.py`
- `app/services/referral_service.py`
- `app/services/subscription_service.py`
- `app/services/test_creation_service.py`
- `app/services/user_service.py`
- `tests/test_postgres_integration.py`
- `tests/test_referral_service.py`
- `app/middlewares/private.py`
- `app/services/notification_service.py`
- `tests/test_r1.py`

### [x] R2. Scheduler soddalashtirish

**Qil:**
~~tick() dan scheduled publish olib tashlansin. Qoladi: muddati o'tgan testni yopish~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~(30 soniyada bir), broadcast batchlari (alohida job, tick ni bloklamasin),~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~heartbeat (alohida job), kunlik obuna tekshiruvi, eslatmalar. Muvaffaqiyatsiz~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~ishlar uchun urinishlar soni/kutish oralig'i bo'lsin (cheksiz qayta urinish yo'q),~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~3 marta xato bo'lsa adminlarga bir marta xabar.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~**Qabul mezonlari:** Yopish 30 soniyada, broadcast va heartbeat alohida joblarda; scheduled publish yo'q. Qayta ishga tushganda ishlar tiklanadi, parallel takror bajarish himoyalangan. Qayta urinishlar cheklangan va kutish oralig'i bor; uchinchi xatoda bir marta admin xabari. Joblar bir-birini bloklamasligi test qilinadi. Har o‘zgargan xatti-harakat uchun test; `ruff check .` va `pytest` toza. Hisobotda o‘zgargan fayllar ro‘yxati beriladi va shu qadamdan keyin to‘xtaladi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).


~~**R2 bajarilish hisoboti:** `tick` faqat muddati o'tgan testlarni 30 soniyada tekshiradi; rejalashtirilgan nashr olib tashlandi. Broadcast (1 soniya) va heartbeat (15 soniya) alohida joblar. Redis lock, saqlanadigan urinish hisoblagichi va 30/60 soniyalik backoff qo'shildi: uch xatodan so'ng shu ish qayta bajarilmaydi, DB owner/adminlariga bir marta xabar beriladi. Obuna va eslatma xatolari ham cheklangan; user/kun va eslatma/test bo'yicha alohida kalitlar. PostgreSQL testi qoralamani nashr qilmaslik, qayta ishga tushish va parallel yopishda takror xabar yo'qligini tekshiradi. `ruff check .` toza; `TEST_INFRA=1 pytest -q`: **114 passed**. Oxirgi concurrency/muddat himoyasidan keyin scheduler/R1 regression testlari: **15 passed**.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

**R2 o'zgargan fayllar:**
- `app/scheduler/jobs.py`
- `app/scheduler/setup.py`
- `app/locales/uz.json`
- `app/locales/ru.json`
- `tests/test_scheduler.py` (yangi)
- `tests/test_postgres_integration.py`
- `tests/test_r1.py`
- `PLAN.md`

### [x] R3. Test hayot sikli va post

**Qil:**
~~pause/resume/schedule olib tashlansin. Tugma havolasi ?start=test. Admin /start~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~deep link'ni (test, test_<id>, ref_<id>) ROL tekshiruvidan OLDIN qayta ishlasin~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~(admin ham testni ola oladi). Preview file_id yaratish bosqichida (preview~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~yuborilganda) saqlansin, nashr diskdagi PDFga bog'liq bo'lmasin.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~Javob kaliti parseri: parse_key va parse_answers bir xil formatlarni qabul qilsin~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~(1a,2b | 1a 2b | 1-a | abcd | yangi qator | oxirgi vergul).~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~**Qabul mezonlari:** Yangi va eski test linklari oxirgi faol testni beradi, admin deep linki ham rol yo'naltirishidan oldin ishlaydi. Pause/resume/schedule va urinish savoli yo'q; max_attempts=1. Preview file_id nashrdan oldin saqlanadi; disk PDFsiz nashr ishlaydi. Kalit va user javobi sanalgan barcha formatlarni bir xil qabul qiladi; a–d va savollar tekshiruvi saqlanadi. Har o‘zgargan xatti-harakat uchun test; `ruff check .` va `pytest` toza. Hisobotda o‘zgargan fayllar ro‘yxati beriladi va shu qadamdan keyin to‘xtaladi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).


~~**R3 bajarilish hisoboti:** Kanal tugmasi `?start=test`; eski `test_<id>` ham eng oxirgi e'lon qilingan, muddati o'tmagan faol testni beradi. Admin test/referral deep linklari rol menyusidan oldin ishlanadi. Pause/resume/schedule amallari, tugmalari va urinish savoli olib tashlandi; eski callback/FSM schedule amali rad etiladi. Preview yuborilganda `file_id` draftga, tasdiqda DBga saqlanadi; nashr faqat shu IDdan foydalanadi. Kalit va user javobi bir parserdan o'tadi, barcha sanalgan formatlar va oxirgi vergul qabul qilinadi. `max_attempts=1` ham service, ham DBda cheklangan.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~Migratsiya `c350_simple_lifecycle` eski paused testlarni yopiq holatga o'tkazadi (natijalar saqlanadi), scheduled_at ni tozalaydi va max_attempts=1 qiladi. Downgrade cheklovlarni olib tashlaydi, tarixiy qiymatlarni qaytarmaydi. Migratsiya hali ishlayotgan bot bazasiga qo'llanmagan; alohida vaqtinchalik PostgreSQL bazada upgrade/downgrade/upgrade o'tdi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

Tekshiruv: `ruff check .` toza; `TEST_INFRA=1 pytest -q`: **130 passed**. Oxirida qo'shilgan ikki DB-cheklov testi bilan R3 testlari alohida: **18 passed**. R4 boshlanmadi.

**R3 o'zgargan fayllar:**
- `app/db/models/__init__.py`
- `app/repositories/tests.py`
- `app/scheduler/jobs.py`
- `app/keyboards/inline.py`
- `app/locales/uz.json`
- `app/locales/ru.json`
- `app/services/admin_ui_service.py`
- `app/services/answer_parser.py`
- `app/services/application_service.py`
- `app/services/grading_service.py`
- `app/services/post_service.py`
- `app/services/test_creation_service.py`
- `app/services/user_service.py`
- `migrations/versions/c350_simple_lifecycle.py`
- `tests/conftest.py`
- `tests/helpers.py`
- `tests/test_admin_ui_service.py`
- `tests/test_answer_parser.py`
- `tests/test_grading_service.py`
- `tests/test_test_creation_service.py`
- `tests/test_r3.py`
- `PLAN.md`

### [x] R4. Reply menyu yadrosi

**Qil:**
Reply menyu yadrosi: app/menus.py, qayta yozilgan nav_service, role asosida
yashirish, Orqaga/Bosh menyu, FSM paytida [❌ Bekor qilish], noma'lum matnda joriy
  menyuni qayta ko'rsatish. Barcha tugma matnlari texts.py/locales dan. Eski
  callback'ka asoslangan admin kodi o'chirilsin. /start va /admin dan boshqa
  buyruqlar olib tashlansin.

**Qabul mezonlari:** Menyu qo'shish deklarativ app/menus.py orqali; role/parent/action jadvali bor. Har rolning ruxsati UI va servicedagi testlarda tekshirilgan; Orqaga/Bosh menyu/Bekor va noma'lum matn ishlaydi. Faqat /start va /admin, faqat o'zbek UI. Kanal/obunadan tashqari inline va eski admin callback marshrutlari yo'q; hali R5–R7 da bajariladigan amallar aniq ajratilgan. Har o‘zgargan xatti-harakat uchun test; `ruff check .` va `pytest` toza. Hisobotda o‘zgargan fayllar ro‘yxati beriladi va shu qadamdan keyin to‘xtaladi.


**R4 bajarilish hisoboti:** `app/menus.py` menu_id/title/parent/buttons/permission/action jadvali yagona manba bo'ldi. Yangi child qator ota menyuga avtomatik qo'shiladi, ota ruxsatlari meros olinadi; router yoki nav if-zanjirini o'zgartirish kerak emas. Owner/admin/moderator tugmalari va service ruxsatlari tekshiriladi. Kanallar/Adminlar Sozlamalar ichida; user sahifalari ota user menyuga qaytadi. FSM Bekor/Home ma'lumotni tozalaydi, noma'lum matn joriy menyuni qaytaradi. Faqat `/start`, `/admin`; Telegram buyruqlar menyusi ham shu ikki buyruqqa yangilanadi. UI faqat uz.json dan o'qiladi, ru.json fayli saqlandi va ishlatilmaydi.

Eski admin callback dispatcher, inline test kartasi/ro'yxatlar/preview/tasdiqlash va ularga tegishli o'nta admin callback adapteri olib tashlandi. Faqat kanal postidagi URL va obuna URL/`sub:check` inline qoldi. Broadcastdagi qo'shimcha havola inline tugma o'rniga matnda saqlanadi. Foydalanuvchining test/natija/referral/yordam/javob FSM amallari ishlaydi.

~~**R4 chegarasi — hali bajarilmagan amallar:** Deklaratsiyalarda `pending_step` bor. Yangi test, test ro'yxati va kod qidiruvi — R5; statistika/hisobot/user ban/unban va test amallari — R6; broadcast auditoriyalari, kanal/admin qo'shish/o'chirish va sozlama togglelari — R7. Hozir bu tugmalar aniq «Bu amal hozircha tayyorlanmoqda» xabarini va ota menyuni ko'rsatadi, eski oqimni bajarmaydi. Sozlama holati o'qib ko'rsatiladi, ammo o'zgartirish R7 da ulanadi. Yangi 10 bosqichli yaratish, reply test kartasi va yo'naltirilgan boshqaruv hali bajarilgan deb belgilanmagan. Mavjud domain servislar va ularning testlari saqlangan; eskirgan callback/UI testlari yangi ruxsat/navigation regressiyalari bilan almashtirilgan.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

Tekshiruv: `ruff check .` toza; `TEST_INFRA=1 pytest -q`: **161 passed**. Jadvalga bitta qator qo'shishdagi yakuniy o'zgarishdan so'ng navigation/application testlari: **42 passed**. Bot qayta ishga tushirilmadi, R5 boshlanmadi.

**R4 o'zgargan/yangi fayllar:**
- `app/menus.py`
- `app/keyboards/reply.py`
- `app/keyboards/inline.py`
- `app/keyboards/admin.py`
- `app/handlers/__init__.py`
- `app/handlers/user/subscription.py`
- `app/services/nav_service.py`
- `app/services/application_service.py`
- `app/services/admin_ui_service.py`
- `app/services/admin_service.py`
- `app/services/broadcast_ui_service.py`
- `app/services/broadcast_service.py`
- `app/services/test_creation_service.py`
- `app/services/grading_service.py`
- `app/texts.py`
- `app/constants.py`
- `app/locales/uz.json`
- `app/main.py`
- `app/middlewares/db_session.py`
- `app/middlewares/user_upsert.py`
- `tests/test_menu_core.py`
- `tests/test_nav_service.py`
- `tests/test_application_service.py`
- `tests/test_admin_ui_service.py`
- `tests/test_broadcast_service.py`
- `tests/test_settings_service.py`
- `PLAN.md`

**R4 o‘chirilgan eski callback adapterlari:**
- `app/handlers/admin/add_test.py`
- `app/handlers/admin/admins.py`
- `app/handlers/admin/broadcast.py`
- `app/handlers/admin/channels.py`
- `app/handlers/admin/export.py`
- `app/handlers/admin/results.py`
- `app/handlers/admin/settings.py`
- `app/handlers/admin/stats.py`
- `app/handlers/admin/tests_manage.py`
- `app/handlers/admin/users.py`

### [x] R5. Yangi test oqimi va Testlar bo‘limi

**Qil:**
~~Yangi test oqimi (2-bo'lim, "➕ Yangi test") va Testlar bo'limi (reply ro'yxat,~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
~~holatga qarab Test menyusi, tasdiqlash tugmalari, qoralamani o'chirish + fayl).~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~**Qabul mezonlari:** 10 bosqichli oqim, qadam ko'rsatkichi, muddat/referral shortcutlari va kanalni avtomatik tanlash ishlaydi. Previewdan kanalga/menga/qoralama amallari reply orqali; Menga yuborish testni faollashtiradi. 8 tadan ro'yxat, sahifalash va #id tanlash ishlaydi. Holatga mos test menyusi, yopish/o'chirish/e'lon tasdig'i bor; faqat qoralama o'chadi va PDF ham tozalanadi; moderator yozish amallarini bajarmaydi. Har o‘zgargan xatti-harakat uchun test; `ruff check .` va `pytest` toza. Hisobotda o‘zgargan fayllar ro‘yxati beriladi va shu qadamdan keyin to‘xtaladi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).


~~**R5 bajarilish hisoboti:** 10 bosqichli yaratish oqimi, qadam raqami, kod/tavsif/muddat/referral shortcutlari va bitta kanalni avtomatik tanlash ulandi. Ko'p kanal reply tanlovda, preview esa kanalga/menga/qoralama/qaytadan/bekor tugmalari bilan. Menga yuborish testni faollashtiradi; draft tahriri IDni saqlaydi. Testlar 8 tadan reply sahifalanadi, #id faqat server ko'rsatgan ro'yxatdan tanlanadi, kod qidiruvi faol testni ustun qo'yadi. Holat va rolga mos test menyusi bor; yopish/o'chirish/e'lon qilish oldin reply tasdiq so'raydi. Faqat qoralama o'chadi, uning storage/pdf ichidagi PDFi DB commitdan keyin o'chadi; rollback faylni saqlaydi. Moderator yozish amallarini bajarmaydi, tasdiqda rol/status qayta tekshiriladi. Bekor/restart yangi vaqtinchalik PDFni tozalaydi. Nashr xatosida preview FSM saqlanadi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~R6 chegarasi: test statistikasi, reyting, ikkala Excel, muddat/kalit tahriri va tasdiqlangan g'olib e'lonining bajarilishi hozircha pending; test menyusi va e'lon tasdiq chegarasi tayyor. Test yopish R5 da ishlaydi. R6 boshlanmadi. Bot qayta ishga tushirilmadi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

Tekshiruv: `ruff check .` toza; `TEST_INFRA=1 pytest -q`: **181 passed**. Integratsiya scheduler testlarining Redis lock/retry kalitlari ishlayotgan bot bilan to'qnashmasligi uchun alohida prefiksga o'tkazildi.

**R5 o'zgargan fayllar:**
- `app/services/test_creation_service.py`
- `app/services/test_manage_service.py (yangi)`
- `app/services/nav_service.py`
- `app/services/application_service.py`
- `app/menus.py`
- `app/locales/uz.json`
- `tests/test_r5.py (yangi)`
- `tests/test_test_creation_service.py`
- `tests/test_menu_core.py`
- `tests/test_postgres_integration.py`
- `PLAN.md`

### [x] R6. Statistika, hisobotlar va foydalanuvchilar

**Qil:**
Statistika, Hisobotlar, Foydalanuvchilar bo'limlari (2-bo'lim bo'yicha) va
~~test menyusidagi Reyting / Excel / Statistika / G'oliblarni e'lon qilish /~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).
  ~~Testni yopish. Raqamlar DB bilan mos bo'lsin.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

~~**Qabul mezonlari:** Umumiy/referral statistika va hisobotlar yangi xaritaga mos, dublikat bo'limlar yo'q. Ban/unban/banlanganlar yo'naltirilgan kiritish bilan ishlaydi. Test statistikasi, TOP/reytinq, ikkala Excel, yopish va g'olib e'loni DB bilan mos va ruxsat bilan himoyalangan; xavfli amallar tasdiqsiz bajarilmaydi. Har o‘zgargan xatti-harakat uchun test; `ruff check .` va `pytest` toza. Hisobotda o‘zgargan fayllar ro‘yxati beriladi va shu qadamdan keyin to‘xtaladi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).


**R6 bajarilish hisoboti:** Statistika → Umumiy va Referral TOP ulandi; umumiy hisobotdan takroriy referral bo'limi ajratildi. Referral TOP faqat valid va hozir obuna takliflarni sanaydi. Hisobotlar → barcha foydalanuvchilar/referral Excel ishlaydi. Foydalanuvchilar → Ban/Unban alohida TG ID yoki @username savoli bilan; adminlar himoyalangan, username case-insensitive va underscore literal, banlanganlar 20 tadan reply sahifalanadi.

~~Test kartasidagi statistika (olganlar/topshirganlar/o'rtacha/savol aniqligi), 20 tadan reply reyting, natijalar va olganlar Excel, muddat va kalit tahriri ulandi. Kalit o'zgarganda barcha natijalar va reyting qayta hisoblanadi. Kiritish/tasdiqda jonli rol va test holati qayta tekshiriladi. Yopish R5 dagi tasdiq bilan ishlaydi; g'oliblarni e'lon qilish endi tasdiqdan so'ng kanal va g'oliblarga yuboradi, takror e'lon rad etiladi. Uzun hisobotlar Telegram limitiga mos qismlarga bo'linadi. UI faqat reply; qolgan inline kanal/obuna joylari o'zgarmadi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

Tekshiruv: `ruff check .` toza; `TEST_INFRA=1 pytest -q`: **190 passed**. R6 regressiyalari: **9 passed**, ular DB raqamlari, Excel mazmuni, tie/page reytingi, ban/unban, roldan mahrum qilish, stale test, kalitdan qayta hisoblash, bir martalik tasdiqlangan e'lonni tekshiradi. Yangi jadval/maydon/kutubxona yo'q. Bot qayta ishga tushirilmadi; R7 boshlanmadi.

**R6 o'zgargan fayllar:**
- `app/services/reporting_service.py (yangi)`
- `app/services/test_manage_service.py`
- `app/services/nav_service.py`
- `app/repositories/stats.py`
- `app/menus.py`
- `app/locales/uz.json`
- `tests/test_r6.py (yangi)`
- `tests/test_r5.py`
- `PLAN.md`

### [x] R7. Xabar yuborish va Sozlamalar

**Qil:**
Xabar yuborish oqimi (reply, preview, tasdiq) va Sozlamalar (Kanallar, Adminlar,
uchta yoqish/o'chirish tugmasi, holat tugma matnida).

**Qabul mezonlari:** Broadcast uch auditoriya -> kerak bo'lsa reply test tanlash -> matn/rasm -> ixtiyoriy tugma -> preview -> reply tasdiq tartibida ishlaydi; Bekor tozalaydi. Owner sozlamalari uch toggle, Kanallar va Adminlar bilan; tugmalarda holat ko'rinadi. Kanal o'chirilsa asosiy qayta tanlanadi, hammasi majburiy. Admin qo'shish ID va alohida rol tanlash bilan; eski matn grammatikasi/referral standarti yo'q. Har o‘zgargan xatti-harakat uchun test; `ruff check .` va `pytest` toza. Hisobotda o‘zgargan fayllar ro‘yxati beriladi va shu qadamdan keyin to‘xtaladi.

**R7 bajarildi:** Uch auditoriyali reply oqimi, test tanlash (8 tadan), matn yoki rasm, havola nomi va URL uchun alohida savollar, aynan yuboriladigan preview va reply tasdiq ulandi. Inline chekloviga muvofiq havola matn ko‘rinishida yuboriladi. Yuborish holati/to‘xtatish tugmalari bor; Bekor, Orqaga va /start yoki /admin qoralamani bekor qiladi va FSMni tozalaydi. Telegram matn/izoh limitlari yakuniy havola bilan birga tekshiriladi.

Owner uch toggle holatini tugmada ko‘radi. Kanal qo‘shish botning admin huquqini tekshiradi; barcha kanallar majburiy, asosiy o‘chirilganda keyingisi tanlanadi. Startup eski ixtiyoriy kanallarni ham majburiy holatga keltiradi. Kanal/admin o‘chirish serverdagi reply tanlovdan; admin qo‘shish ID -> Admin/Moderator. Owner va .env adminlari o‘chirilmaydi yoki roli almashtirilmaydi. Har kiritishda jonli ruxsat tekshiriladi. Eski buyruq grammatikasi va referral/language sozlamalari olib tashlandi.

**R7 o‘zgargan fayllar:**
- `app/menus.py`
- `app/keyboards/reply.py`
- `app/locales/uz.json`
- `app/services/admin_service.py`
- `app/services/settings_service.py`
- `app/services/settings_ui_service.py` (yangi)
- `app/services/broadcast_ui_service.py`
- `app/services/nav_service.py`
- `app/services/application_service.py`
- `tests/test_admin_service.py`
- `tests/test_broadcast_service.py`
- `tests/test_nav_service.py`
- `tests/test_r7_flows.py` (yangi)
- `PLAN.md`

Tekshiruv: `ruff check .` toza; `TEST_INFRA=1 pytest -q`: **199 passed**. R7 regressiyalari: **9 passed** (owner sozlamalari, admin huquqlari, kanal almashishi, uch auditoriya, preview/bekor, URL va uzunlik tekshiruvlari). Yangi jadval/maydon/kutubxona yo‘q. Bot qayta ishga tushirilmadi; R8 boshlanmadi.

### [x] R8. Ishlatilmaydigan kodni tozalash

**Qil:**
Tozalash: ishlatilmaydigan locale kalitlari, state klasslari (AdminInput va
boshqalar), callback marshrutlari, __import__ hiylasi, funksiya ichidagi importlar,
  qisqartirilgan bir qatorli imzolar (ruff format). Handlerlarni ham ixchamlashtir.

**Qabul mezonlari:** Ishlatilmaydigan locale/state/callback kodi yo'q, dinamik __import__ va funksiya ichidagi importlar olib tashlangan. Handlerlar faqat delegatsiya qiladi; ruff format qo'llangan. Saqlangan ru.json UI da ishlatilmaydi; tozalash regressiya testlarini buzmaydi. Har o‘zgargan xatti-harakat uchun test; `ruff check .` va `pytest` toza. Hisobotda o‘zgargan fayllar ro‘yxati beriladi va shu qadamdan keyin to‘xtaladi.

**R8 bajarildi:** `AdminInput`, `BroadcastInput`, takroriy eski handler/keyboard/filter adapterlari va ishlatilmaydigan admin ko‘rinishlari olib tashlandi. Umumiy report eksporti ruxsat tekshiruvi bilan saqlandi. Handlerlar faqat service chaqiradi; /start, /admin va oddiy xabarlar bitta adapterga, callbacklar faqat sub:check ga ulangan.

Menyu renderi va tugma aniqlash `menu_service.py` ga ajratildi. App va testlardagi funksiya ichidagi importlar yuqoriga ko‘chirildi; dinamik `__import__` olib tashlandi. Eski pending deklaratsiya/amali va foydalanilmaydigan til ContextVar tozalandi. Uzbek katalogidan 33 ta ishlatilmaydigan kalit o‘chirildi; dinamik savol sarlavhalari va Excel headerlari saqlandi. `ru.json` saqlandi va UI ga yuklanmaydi. `ruff format .` qo‘llandi.

**R8 o‘zgargan/yangi fayllar:**
- `app/constants.py`
- `app/db/base.py`
- `app/handlers/__init__.py`
- `app/handlers/user/common.py`
- `app/handlers/user/subscription.py`
- `app/locales/uz.json`
- `app/main.py`
- `app/menus.py`
- `app/middlewares/user_upsert.py`
- `app/repositories/channels.py`
- `app/repositories/submissions.py`
- `app/services/admin_ui_service.py`
- `app/services/broadcast_service.py`
- `app/services/broadcast_ui_service.py`
- `app/services/menu_service.py`
- `app/services/nav_service.py`
- `app/services/reporting_service.py`
- `app/services/settings_ui_service.py`
- `app/services/user_service.py`
- `app/texts.py`
- `app/utils/files.py`
- `app/utils/formatting.py`
- `tests/conftest.py`
- `tests/test_admin_service.py`
- `tests/test_admin_ui_service.py`
- `tests/test_application_service.py`
- `tests/test_broadcast_service.py`
- `tests/test_nav_service.py`
- `tests/test_r1.py`
- `tests/test_r3.py`
- `tests/test_r5.py`
- `tests/test_r7_flows.py`
- `tests/test_r8_cleanup.py`
- `tests/test_settings_service.py`
- `tests/test_subscription_service.py`
- `tests/test_test_creation_service.py`
- `PLAN.md`

**R8 o‘chirilgan fayllar:**
- `app/states/admin_misc.py`
- `app/states/broadcast.py`
- `app/handlers/user/get_test.py`
- `app/handlers/user/my_results.py`
- `app/handlers/user/referral.py`
- `app/handlers/user/submit_answers.py`
- `app/handlers/user/start.py`
- `app/handlers/admin/menu.py`
- `app/handlers/admin/__init__.py`
- `app/keyboards/admin.py`
- `app/keyboards/user.py`
- `app/middlewares/subscription.py`
- `app/filters/is_admin.py`

Tekshiruv: `ruff check .` toza, `ruff format . --check`: **113 files already formatted**; `TEST_INFRA=1 pytest -q`: **201 passed**. Yangi R8 tekshiruvlari: import tuzilishi, dinamik locale/menyu/Excel kalitlari va yagona adapter marshrutlari — **3 passed**. Yangi kutubxona yoki DB o‘zgarishi yo‘q. Bot qayta ishga tushirilmadi; R9 boshlanmadi.

### [x] R9. Hujjat va sifat

**Qil:**
Hujjat va sifat: README to'ldirilsin (BotFather, .env, botni kanalga admin
qilish, docker compose, webhook+HTTPS, backup cron, birinchi admin), PLAN.md
  yangilansin, testlar: menyu navigatsiyasi (rolga qarab tugmalar, Orqaga/Bosh menyu),
  yangi test oqimi, test menyusi holatga qarab, scheduler ishlari, middleware.
  TEST_INFRA=1 bilan PostgreSQL integratsiya testlari ham o'tsin.
  Yakuniy smoke test: admin test yaratadi -> kanalga chiqadi -> yangi foydalanuvchi
  tugmani bosadi -> obunasiz to'siladi -> obuna bo'lgach PDF oladi -> javob yuboradi
  -> referral talabli testda taklifsiz rad etiladi -> admin Excel oladi, testni
  ~~yopadi, g'oliblarni e'lon qiladi.~~ — **R11 bilan almashtirilgan** (oldingi talab/hisobot, audit uchun saqlandi).

**Qabul mezonlari:** README da barcha sanalgan amaliy sozlash/deploy/backup bosqichlari bor; PLAN holati haqiqiy natijaga mos. Menyu, FSM, test holatlari, scheduler va middleware testlari mavjud. Ruff va pytest, jumladan TEST_INFRA=1 PostgreSQL integratsiyasi toza. Ko'rsatilgan yakuniy smoke test natijalari qayd etilgan; tekshirilmagan amallar bajarildi deb belgilanmaydi. Har o‘zgargan xatti-harakat uchun test; `ruff check .` va `pytest` toza. Hisobotda o‘zgargan fayllar ro‘yxati beriladi va shu qadamdan keyin to‘xtaladi.

**R9 bajarildi (2026-11-27):** README BotFather/token, `.env` kalitlari, birinchi owner seed va mavjud DB rollari, kanalga admin huquqi, Docker Compose, lokal Python, HTTPS/webhook, sertifikat yangilash, backup cron va tiklash bilan to'ldirildi. R11 dagi 5 qadamli oqim va ikki varaqli Excel hujjatlashtirildi.

**Yakuniy smoke test:** `tests/test_r9_smoke.py` bitta uzluksiz oqimni SQLite va alohida PostgreSQL schemada tekshiradi: admin /start -> PDF/kalit/boshlanish/tugash/referral -> kanal posti va ?start=test -> yangi user obunasiz to'siladi -> sub:check bilan obunadan so'ng PDF oladi -> referral yo'qligi sabab javob rad etiladi -> uchta yangi user haqiqiy ref deep link bilan kirib obuna bo'ladi -> javob 100% qabul qilinadi -> referral natijalari va ikki varaqli Excel -> tasdiqlangan yopish -> bitta TOP-10 kanal posti -> takror e'lon rad etiladi. **2 passed**. Telegram API mock, SQLite/PostgreSQL esa haqiqiy DB; bu jonli Telegram yetkazilish sinovi emas.

**Mavjud regressiyalar:** `test_menu_core.py` va `test_nav_service.py` rollar, Orqaga/Bosh menyu/Bekorni; `test_r11.py` yangi yaratish/sana/test holatlari/rejalashtirishni; `test_scheduler.py` va `test_postgres_integration.py` scheduler/retry/restartni; `test_r1.py`, `test_antiflood.py` middleware/private/transaction chegaralarini tekshiradi. Ularning hammasi to'liq suite bilan qayta o'tkazildi.

**Tekshiruv:** `ruff check .` toza; `ruff format . --check`: **115 files already formatted**; `TEST_INFRA=1 pytest -q`: **214 passed**. Mahalliy interpreter **Python 3.13.5**; Dockerfile Python 3.12 ni belgilaydi, ammo bu qadamda yangi 3.12 image build/test qilinmadi. Read-only `docker compose ps` da bot/PostgreSQL/Redis running healthy. Bot qayta ishga tushirilmadi; tashqi HTTPS, haqiqiy kanalga post va backup/tiklash buyruqlari bajarilmadi, faqat yo'riqnomasi yozildi. Yangi dependency, jadval yoki migratsiya yo'q.

**R9 o'zgargan fayllar:**
- `README.md` — amaliy sozlash/deploy/backup va tekshiruv yo'riqnomasi.
- `tests/test_r9_smoke.py` (yangi) — SQLite/PostgreSQL uzluksiz smoke testlari.
- `PLAN.md` — R9 belgilandi, dalillar va tekshirilmagan jonli amallar qayd etildi.

### [x] R11. Yangi test oqimi, boshlanish/tugash vaqti va sovrinlarni olib tashlash

**Holat:** R11 to'liq bajarildi; quyidagi talablar kod va testlarga kiritildi.
**Ish tartibi:** foydalanuvchining «barchasini hozir bajar» ko'rsatmasi bajarildi.
`ruff check .` va `pytest` toza o'tgach `[x]` qilinadi; o'zgargan fayllar ro'yxati
va nechta fayl/funksiya/tugma o'zgargani bilan qisqa hisobot beriladi va to'xtaladi.
R9 yoki boshqa qadam avtomatik boshlanmaydi. DB sxemasi o'zgarmaydi,
yangi migratsiya yaratilmaydi. Oldingi chizilgan bandlar R11 bilan almashtirilgan.

#### 1. YANGI TEST OQIMI (5 qadam, "n/5", pastda [⬅️ Orqaga] [❌ Bekor qilish])
1/5 PDF yuborish.
    - Nom: PDF izohi (caption) bo'lsa o'sha, bo'lmasa fayl nomi (".pdf" olinadi,
      "_" va "-" bo'shliqqa almashadi, 200 belgigacha).
    - Kod: avtomatik, 4 xonali (1000-9999), faol va rejalashtirilgan testlarda band emas.
2/5 To'g'ri javoblar kaliti (1a,2b,3d... mavjud parser bilan).
    - Savollar soni = kalitdagi javoblar soni. Raqamlar 1..N uzilishsiz bo'lishi
      shart, aks holda qaysi raqam tushib qolgani aytiladi.
3/5 BOSHLANISH: [▶️ Hozir] [🌅 Ertaga 09:00] yoki "YYYY-MM-DD HH:MM" kiritish.
4/5 TUGASH: [24 soat] [3 kun] [7 kun] [♾ Cheksiz] yoki "YYYY-MM-DD HH:MM"
    (tugmalar boshlanishdan hisoblanadi).
5/5 Referral: [🚫 Kerak emas] [3 ta] [5 ta] [10 ta].
Kanal faqat 2+ kanal bo'lsa 5/5 dan keyin tugmalar bilan so'raladi.
O'CHIRILSIN: nom, kod, tavsif, savollar soni, sovrinlar soni so'rash qadamlari;
qo'lda kod; qo'lda referral soni; tegishli FSM holatlari va locale kalitlari.

VALIDATSIYA (xatoda aniq xabar va namuna "2026-12-01 10:00"):
- Vaqt settings.tz bo'yicha kiritiladi va xabarlarda shu zonada ko'rsatiladi.
- Boshlanish o'tmishda bo'lmasin (1 daqiqa chegirma bilan).
- Tugash boshlanishdan keyin va kamida 10 daqiqa farq bilan bo'lsin.

#### 2. PREVIEW VA POST
Caption: nom, kod, "Muddat: 01.12 10:00 – 05.12 22:00" (cheksiz bo'lsa
"01.12 10:00 dan"), kanal havolasi, bot havolasi. "Sovrinlar" va tavsif qatori YO'Q.
Preview ostidagi matnda: "Savollar: N · Referral: M".
Tugmalar:
- Boshlanish = hozir:    [📤 Kanalga yuborish] [📨 Menga yuborish] [❌ Bekor qilish]
- Boshlanish kelajakda:  [⏰ Rejalashtirib qo'yish] [❌ Bekor qilish]
  ("Menga yuborish" bu holda chiqmaydi.)
Kanal postidagi tugma: [📝 Testni ishlash] -> https://t.me/BOT?start=test
(eng oxirgi faol test yuboriladi; eski test_<id> havolalari ham shunga tushadi).
Preview file_id yaratish bosqichida saqlansin (nashr diskdagi PDFga bog'liq emas).

#### 3. HAYOT SIKLI
- tests.start_at / end_at ishlatiladi. Kelajakdagi testda tests.scheduled_at =
  start_at, status "draft" (mavjud ustunlar, migratsiya yaratma).
- Scheduler (har 30 soniyada): start_at <= hozir bo'lgan rejalashtirilgan testni
  kanalga chiqaradi va "active" qiladi. Xatoda 3 martagacha qayta uriniladi
  (kutish oralig'i bilan), 3-xatoda adminlarga bir marta xabar, keyin to'xtaydi
  (cheksiz qayta urinish yo'q). Server o'chiq turgan bo'lsa, vaqti o'tgan test
  bot yurgach darhol chiqadi. Muddati tugagan faol testlar avtomatik yopiladi.
- Test faol: start_at <= hozir < end_at. "Oxirgi test" faqat boshlangan testlarni
  oladi. Rejalashtirilgan test havolasi/kodi bilan kelinsa:
  "Test hali boshlanmagan. Boshlanish: <vaqt>". Boshlanishdan oldin javob qabul
  qilinmaydi.
- Admin /start da deep link (test, test_<id>, ref_<id>) rol tekshiruvidan OLDIN
  qayta ishlansin.
- Referral hisobi: faqat test.start_at dan keyin yaratilgan va hozir obuna bo'lgan
  takliflar.

#### 4. ADMIN: TESTLAR MENYUSI
[🟢 Faol] [🔴 Yopilgan]. Ro'yxat reply tugmalarda, "#12 · 4829 · Nomi",
[◀️] [▶️] (8 tadan). "Faol" ro'yxatida rejalashtirilganlar ham chiqadi:
"⏰ #12 · 4829 · Nomi · 01.12 10:00".
- Rejalashtirilgan test menyusi: [❌ Rejalashtirishni bekor qilish]
  (testni va PDF faylini o'chiradi, oldin [✅ Ha] [❌ Yo'q] so'raydi).
- Faol test menyusi: [📊 Natijalar] [📥 Excel] [🔑 Kalitni tuzatish] [🏁 Yopish]
  (Yopish = end_at ni hozirga o'tkazadi, oldin tasdiq so'raydi).
- Yopiq test menyusi: [📊 Natijalar] [📥 Excel] [📣 Natijalarni e'lon qilish]
  Natijalarni e'lon qilish: [✅ Ha] [❌ Yo'q] tasdig'idan keyin kanalga bitta post:
  test nomi + TOP-10 (o'rin, ism, to'g'ri javoblar soni, foiz). G'olib belgilash
  yo'q, foydalanuvchilarga shaxsiy "g'olib" xabari yuborilmaydi. Faqat yopilgan
  testda va bir test uchun bir marta (results_published).
- "📊 Natijalar" xabari: testni olganlar soni, topshirganlar soni, o'rtacha ball,
  referral talab bo'lsa nechtasi to'ldirgan, TOP-10. Excel: bitta fayl, ikki varaq
  ("Natijalar", "Testni olganlar"). Sovrinlarga oid ustun/qator YO'Q.

#### 5. SOVRINLARNI OLIB TASHLASH
O'chirilsin: winner_dm, prompt_prizes_count va sovrinlarga tegishli barcha locale
kalitlari, FIELDS dagi prizes_count, validatsiya, "g'oliblar" logikasi, eskirgan
testlar. Ma'lumotlar bazasi O'ZGARMAYDI: tests.prizes_count ustuni (default 0)
qolsin, kod unga umuman murojaat qilmasin, migratsiya yaratilmasin.

#### QABUL MEZONLARI
- Admin PDF yuboradi, kalitni yozadi, boshlanish/tugash/referral tugmalarini
  bosadi, preview ko'radi. Sovrin haqida hech qayerda savol yoki so'z yo'q.
- "Hozir" + "24 soat": test darhol chiqadi, 24 soatdan keyin o'zi yopiladi.
- Kelajakdagi boshlanish: vaqti kelganda o'zi kanalga chiqadi, vaqtdan oldin
  kirgan foydalanuvchi "hali boshlanmagan" xabarini oladi, javob qabul qilinmaydi.
- Uzilgan/takroriy kalit (1a,3b), o'tmishdagi boshlanish, tugashi boshlanishdan
  oldingi vaqt: aniq xato bilan rad etiladi.
- Kanalga chiqarish xato bersa qayta urinish chegaralangan va admin ogohlantiriladi.
- "Natijalarni e'lon qilish" faqat yopilgan testda ishlaydi, kanalga TOP-10 chiqadi.
- grep -ri "prize\|sovrin\|winner" app/ natijasida faqat model ustuni qoladi.
- ruff va pytest toza. Testlar: izohli va izohsiz PDF, uzilgan kalit, har bir
  boshlanish/tugash/referral tugmasi, qo'lda sana, noto'g'ri sana, rejalashtirilgan
  nashr va uning xato holati, avtomatik yopilish, boshlanishdan oldingi javob,
  admin deep link, natijalarni e'lon qilish (bir marta).

#### R11 bajarilish hisoboti

PDF -> kalit -> boshlanish -> tugash -> referral ko'rinishidagi 5 qadam ulandi.
Nom PDF izohi/fayl nomidan, kod avtomatik, savollar soni uzilishsiz kalitdan olinadi.
2+ kanalda qo'shimcha reply tanlov bor. Hozirgi boshlanishda kanalga/menga,
kelajakda faqat rejalashtirish va bekor tugmalari bor. Preview file_id darhol FSMga
saqlanadi; nashr diskdagi PDFsiz ham ishlaydi. Vaqtlar DB uchun UTCga normallanadi,
foydalanuvchiga settings.tz da ko'rsatiladi. 1 daqiqa chegirma va 10 daqiqalik
minimal oraliq, sana namunalari bilan xatolar tekshirilgan.

Scheduler startupda darhol va so'ng har 30 soniyada DBni tekshiradi. Kelajakdagi
ish draft + scheduled_at=start_at; muddati kelganda nashr, muddati tugaganda yopish.
Redisda saqlanuvchi 3 urinish, kutish va uchinchi xatoda bir martalik admin xabari
bor. Boshlanmagan testning eski havolasi, kodi yoki kod+javoblari bilan kirish rad
etilib, boshlanish vaqti ko'rsatiladi. Oxirgi test va kodsiz javob faqat hozir faol
bo'lgan testni tanlaydi. Admin deep link va testga bog'liq referral hisobi saqlandi.

Testlar: Faol/Yopilgan; Faol ro'yxatida vaqtli rejalashtirilganlar ham, 8 tadan.
Rejalashtirishni bekor qilish tasdiqdan keyin DB qatori va commitdan keyin PDFni
o'chiradi. Yopish tasdiqdan keyin end_at ni hozirga qo'yadi. Natijalarda olganlar,
topshirganlar, o'rtacha ball, referralni to'ldirganlar va TOP-10 bor. Excel bitta
faylda «Natijalar» va «Testni olganlar» varaqlarini beradi. Yopilgan test natijalari
bir marta bitta kanal posti bilan e'lon qilinadi; shaxsiy tabrik xabarlari yo'q.
Eski yaratish qadamlari, tugmalar va testlar almashtirildi.

DB sxemasi va migratsiyalar o'zgarmadi. `prize|sovrin|winner` qidiruvi `app/` ichida
faqat mavjud model ustuni va uning mavjud constraintiga tushadi; servis/UI da yo'q.
Yangi kutubxona qo'shilmadi. Bot qayta ishga tushirilmadi; jonli Telegram kanaliga
sinov posti yuborilmadi (Telegram chaqiruvlari testlarda mock qilindi).

**Hajm:** 25 fayl (22 o'zgargan, 2 yangi, 1 o'chirilgan); app ichida 36 funksiya
(25 o'zgargan, 9 yangi, 2 olib tashlangan). Test funksiyalari bu 36 hisobiga kirmaydi.
Tugma hisobi — noyob UI kalitlari bo'yicha 26: 3 yangi, 13 matni almashtirilgan,
10 olib tashlangan; bitta tugmaning bir necha menyuda ishlatilishi qayta sanalmaydi.

**Funksiyalar ro'yxati:**
- `test_creation_service`: receive_pdf, prompt, field_value, show_preview, confirm, discard; yangi preview_keys; eski parse_date olib tashlandi.
- `test_time_service` (yangi): aware, display, explicit, beginning, ending.
- `post_service`: caption, publish, close, results.
- `grading_service`: active, submit.
- `user_service`: send_test, start.
- `test_manage_service`: list_page, card, action, confirm, handle; yangi allowed; eski ranking olib tashlandi.
- `export_service`: yangi test_report, _combine.
- `nav_service`: test_flow, handle.
- `answer_parser`: parse_key.
- `repositories/tests`: latest.
- `scheduler/jobs`: tick; `scheduler/setup`: create_scheduler.

**Tugmalar ro'yxati:**
- Yangi (3): start_now, start_tomorrow, schedule.
- Matni yangilangan (13): no_referral, ref3, ref5, ref10, delete, test_stats, excel_results, key, close, announce, yes, no, closed.
- Olib tashlangan (10): auto, skip, save_draft, restart, draft, search_code, edit, ranking, excel_access, deadline.
- publish va send_me previewda saqlandi; eski test kartasida chiqmaydi.

**O'zgargan/yangi fayllar:**
- `app/locales/ru.json`
- `app/locales/uz.json`
- `app/menus.py`
- `app/repositories/tests.py`
- `app/scheduler/jobs.py`
- `app/scheduler/setup.py`
- `app/services/answer_parser.py`
- `app/services/export_service.py`
- `app/services/grading_service.py`
- `app/services/nav_service.py`
- `app/services/post_service.py`
- `app/services/test_creation_service.py`
- `app/services/test_manage_service.py`
- `app/services/test_time_service.py`
- `app/services/user_service.py`
- `tests/test_nav_service.py`
- `tests/test_post_service.py`
- `tests/test_postgres_integration.py`
- `tests/test_r1.py`
- `tests/test_r11.py`
- `tests/test_r3.py`
- `tests/test_r5.py`
- `tests/test_r6.py`
- `PLAN.md`

**O'chirilgan:** `tests/test_test_creation_service.py` — eski oqim testlari yangi
`tests/test_r11.py` bilan almashtirildi. Fayl o'chirishdagi commit/rollback regressiyasi
`tests/test_r5.py` da saqlandi va yangi rejalashtirilgan holatga moslashtirildi.

**Tekshiruv:** `ruff check .` toza; `ruff format . --check`: **114 files already
formatted**; `TEST_INFRA=1 pytest -q`: **212 passed**. Shundan R11 regressiyalari
**34 ta**: izohli/izohsiz PDF, avtomatik metadata, barcha boshlanish/tugash/referral
tugmalari, qo'lda sana, noto'g'ri sana va kalit, kanal tanlash, preview/bekor,
rejalashtirilgan va qayta tiklangan nashr, uch xato/ogohlantirish, avtomatik yopish,
boshlanishdan oldingi javob/kod, admin deep link, menyu/paging/ruxsat, ikki varaqli
Excel va bir martalik natija posti. PostgreSQL scheduler integratsiyasi ham o'tdi.


## Qo‘shimcha talab: post matnini ixtiyoriy tahrirlash (2026-11-27)

Foydalanuvchining yangi ko‘rsatmasi R11 dagi o‘zgarmas caption talabini shu qismda
yangilaydi: 5 qadamli yaratish o‘zgarmaydi, preview va rejalashtirilgan test
kartasida «✏️ Postni tahrirlash» mavjud. Hozirgi to‘liq caption nusxalash uchun
ko‘rsatiladi; admin emoji/izoh qo‘shilgan matn yuboradi, yangi previewni ko‘radi,
«💾 O‘zgarishlarni saqlash» bilan tasdiqlaydi. Orqaga/Bekor saqlanmagan matnni
tashlaydi. Matn oddiy text, limit 1024 UTF-16 birlik; kod/vaqt/havola ham shu
tahrirlanadigan matnda, ammo testning DBdagi kodi/vaqti/kaliti o‘zgarmaydi.

`tests.custom_caption` nullable Text maydoni va `d460_custom_caption` Alembic
migratsiyasi qo‘shildi. Eski testlarda NULL: avtomatik caption saqlanadi. Yangi
matn saqlangan preview va scheduler nashrida aynan ishlatiladi. Faollashib ulgurgan
rejalashtirilgan testga tahrir saqlash rad etiladi. Har kiritish/saqlashda jonli
admin ruxsati tekshiriladi; moderatorga ruxsat yo‘q. /start yoki bosh menyuga
chiqishdagi vaqtinchalik PDF ham tozalanadi.

O‘zgargan fayllar: `app/db/models/__init__.py`,
`migrations/versions/d460_custom_caption.py` (yangi), `app/menus.py`,
`app/locales/uz.json`, `app/services/post_service.py`,
`app/services/test_creation_service.py`, `app/services/test_manage_service.py`,
`app/services/nav_service.py`, `app/services/application_service.py`,
`tests/test_post_edit.py` (yangi), `tests/test_r11.py`, `README.md`, `PLAN.md`.

Tekshiruv: `ruff check .` toza; `ruff format . --check`: 117 files already
formatted; `TEST_INFRA=1 pytest -q`: **221 passed**. Tahrirlash regressiyalari
**7 passed**: preview/saqlash/nashr, DBdan qayta o‘qish, rejalashtirilgan matn,
bekor va qayta tahrir, UTF-16 emoji limiti, rol/status o‘zgarishi, eski caption,
/start tozalashi hamda migratsiya upgrade/downgrade va eski satrning saqlanishi.
Yangi kutubxona qo‘shilmadi.

Deploy: `docker compose up -d --build bot` bajarildi. Ishlayotgan bazada
`alembic current`: **d460_custom_caption (head)**. Bot yangi image bilan qayta
ishga tushdi, `python -m app.healthcheck` muvaffaqiyatli, scheduler va polling
loglarda ishga tushgan. Tekshiruv uchun jonli post yoki xabar yuborilmadi.


## Qo‘shimcha talab: foydalanuvchi xabarlarini tushunarli qilish (2026-11-27)

Javob kiritish yo‘riqnomasida hardcoded 4829 o‘rniga oxirgi faol testning haqiqiy
kodi, nomi va savollar soni ko‘rsatiladi. Faol test bo‘lmasa javob FSMiga
kirilmaydi. Misoldagi kod va 1a nimani anglatishi, barcha javoblar bitta xabarda
va bir marta yuborilishi tushuntiriladi.

Do‘st taklif qilish bitta xabar: shaxsiy havola, test nomi, hisoblangan/talab
sonlari, qolgan takliflar yoki talab bajarilgani. Yangi user, havola orqali kirish,
kanal obunasi va test boshlanganidan keyingi takliflar sharti sodda tushuntiriladi.
Ixtiyoriy talab va faol test yo‘qligi alohida matnlar. Bir amal uchun tugma nomini
qaytaradigan ortiqcha xabarlar olib tashlandi. Natija, bo‘sh natijalar, obuna,
urinish cheklovi, salomlashish va yordam matnlari ham yangilandi.

O‘zgargan fayllar: `app/locales/uz.json`, `app/services/user_service.py`,
`app/services/nav_service.py`, `tests/test_user_messages.py` (yangi), `PLAN.md`.
Yangi jadval/migratsiya/kutubxona yo‘q. `ruff check .` toza, format check:
**118 files already formatted**; `TEST_INFRA=1 pytest -q`: **226 passed**.
Yangi 5 regressiya haqiqiy kod/savol soni, faol test yo‘qligi, takroriy xabarsiz
referral, qolgan/bajarilgan talab, ixtiyoriy referral va bo‘sh natijalarni tekshiradi.

Deploy: bot yangi image bilan qayta ishga tushirildi. Healthcheck muvaffaqiyatli;
bot/PostgreSQL/Redis healthy, polling va scheduler ishlayapti.


## Qo‘shimcha talab: nusxalanadigan bo‘sh javob namunasi (2026-11-27)

PDFdan keyingi yo‘riqnoma va «Javob yuborish» xabariga HTML pre blokdagi
nusxalanadigan namuna qo‘shildi: haqiqiy test kodi va 1?,2?,3? kabi bo‘sh joylar.
Adminning answer_key qiymati namuna yaratishda o‘qilmaydi; tayyor javoblar
chiqarilmaydi. «Namunani nusxalab, ? belgilarining o‘rniga o‘z javoblaringizni
kiriting» ko‘rsatmasi beriladi. 100 tagacha savol to‘liq; undan katta testda
Telegram xabar limitiga sig‘ishi uchun 100 raqam va davom belgisi ko‘rsatiladi,
barcha savollargacha davom ettirish so‘raladi. Nusxalash Telegram mijozining kod
bloki imkoniyati orqali, qo‘shimcha inline tugmasiz. Test nomi HTMLga xavfsiz
escape qilinadi. Parserdagi bo‘sh javob xabari ham eski tayyor misoldan tozalandi.

Fayllar: `app/locales/uz.json`, `app/services/user_service.py`,
`tests/test_user_messages.py`, `tests/test_settings_service.py`, `PLAN.md`.
`TEST_INFRA=1 pytest -q`: **228 passed**; ruff check toza, format check:
**118 files already formatted**. Namuna to‘g‘ri javoblarni oshkor qilmasligi,
HTML escape va katta testda namuna chegarasi tekshirilgan. Yangi DB o‘zgarishi
va kutubxona yo‘q.

Deploy yakunlandi: bot yangi image bilan qayta ishga tushdi, healthcheck o‘tdi;
bot/PostgreSQL/Redis healthy. Konteyner ichidagi answer_sample tekshiruvi:
`5833 1?,2?,3?`. Jonli Telegramga sinov xabari yuborilmadi.
