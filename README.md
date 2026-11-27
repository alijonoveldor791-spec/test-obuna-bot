# Test-Obuna Telegram boti

PDF testlar, majburiy obuna, testga bog‘liq referral va Excel hisobotlari. Yaratish: PDF → kalit → boshlanish → tugash → referral. Interfeys o‘zbekcha; buyruqlar `/start`, `/admin`. Qarorlar: [PLAN.md](PLAN.md), agent qoidalari: [AGENTS.md](AGENTS.md).

## BotFather va birinchi admin

Rasmiy **@BotFather** da `/newbot` orqali bot yarating. Tokenni faqat `.env` ga yozing, Git yoki logga chiqarmang. `BOT_USERNAME` — `@` siz username; startup uni Telegramdan ham aniqlaydi.

`ADMIN_IDS` — vergul bilan ajratilgan raqamli Telegram ID lar (telefon yoki username emas). Birinchi ID bazada yo‘q bo‘lsa owner, qolganlari admin bo‘ladi. Mavjud DB rollari startupda o‘zgarmaydi: ro‘yxat tartibini almashtirish mavjud ownerni almashtirmaydi. `/start` adminni panelga yo‘naltiradi, `/admin` ham panelni ochadi. Owner Sozlamalar → Adminlar orqali ID, keyin Admin/Moderator rolini tanlaydi. Owner va `.env` adminlari paneldan o‘chirilmaydi.

## `.env`

PowerShell: `Copy-Item .env.example .env`. Linux: `cp .env.example .env`.

| Kalit | Qiymat |
|---|---|
| BOT_TOKEN | BotFather tokeni |
| BOT_USERNAME | Username, `@` siz |
| ADMIN_IDS | Telegram ID lar, avval owner |
| MAIN_CHANNEL_ID | Ixtiyoriy `-100…` kanal ID; bo‘sh bo‘lishi mumkin |
| POSTGRES_PASSWORD | Tasodifiy, URLga xavfsiz parol, masalan hex |
| DATABASE_URL | Mahalliy Python: `postgresql+asyncpg://bot:PAROL@localhost:55432/bot` |
| REDIS_URL | Mahalliy Python: `redis://localhost:6379/0` |
| POSTGRES_PORT | Odatda 55432; o‘zgarsa mahalliy DB URLni ham moslang |
| WEBHOOK_URL | Pollingda bo‘sh; webhookda `https://bot.example.uz`, `/webhook` siz |
| WEBHOOK_SECRET | Webhook uchun alohida kamida 24 belgili sir |
| TZ | `Asia/Tashkent` |

Sir yaratish: `python -c "import secrets; print(secrets.token_hex(32))"`. Docker bot konteynerida DB/Redis URLlarini ichki `postgres`/`redis` servislariga almashtiradi. Mahalliy testlar `.env` dagi localhost URLlarini ishlatadi. Mavjud PostgreSQL volume paroli `.env` almashtirilganda avtomatik o‘zgarmaydi.

## Kanalga admin qilish

Kanal → boshqaruv → Administratorlar orqali botni qo‘shib, post yozish huquqini bering. Xususiy kanal uchun taklif havolasini yaratish huquqi ham kerak bo‘lishi mumkin. Owner Sozlamalar → Kanallar → Qo‘shish orqali `@username` yoki `-100…` ID yuboradi. Bot kanal va admin huquqlarini tekshiradi. Barcha kanallar majburiy, birinchisi asosiy; u o‘chirilsa keyingisi asosiy. Bir kanal avtomatik, 2+ kanal test yaratishda tanlanadi.

## Docker Compose

Docker Engine/Desktop va Compose v2 kerak. Loyiha ildizida:

```sh
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 bot
```

Startup `alembic upgrade head`, keyin botni ishga tushiradi. Bir token uchun bitta polling nusxasi ishlasin. PostgreSQL/Redis portlari localhostga bog‘langan. `postgres_data`, `redis_data`, `bot_storage` volume lari ma’lumotni saqlaydi. `docker compose down` ularni saqlaydi; `down -v` o‘chiradi. Yangilashdan oldin backup oling, keyin `docker compose up -d --build bot`. R11 yangi migratsiya qo‘shmaydi; oldingi mavjud migratsiyalar startupda qo‘llanadi.

## Mahalliy Python va testlar

Python 3.12 tavsiya etiladi. Mahalliy botni Docker bot bilan parallel pollingda ishlatmang.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
docker compose up -d postgres redis
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.main
```

Linuxda `.venv/bin/python` ishlating. Tekshiruv:

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format . --check
$env:TEST_INFRA='1'
.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_INFRA
```

Linux: `TEST_INFRA=1 .venv/bin/python -m pytest -q`. Oddiy testlar vaqtinchalik SQLite bazada. PostgreSQL testlari tasodifiy alohida schema yaratib o‘chiradi; foydalanuvchiga CREATE SCHEMA huquqi kerak. Redis test kalitlari alohida prefiksda. Telegram API mock qilinadi, jonli post yuborilmaydi.

## Webhook va HTTPS

1. Domen DNS yozuvlarini serverga yo‘naltiring, 80/443 portlarini oching.
2. Ishonchli TLS sertifikatini masalan ACME/Certbot bilan oling: `deploy/certs/fullchain.pem`, `deploy/certs/privkey.pem`. Private keyni Gitga qo‘shmang. `deploy/nginx.conf` dagi ikkala `server_name _;` ni domeningizga almashtiring.
3. `.env`: `WEBHOOK_URL=https://bot.example.uz`, `WEBHOOK_SECRET` kamida 24 belgi. Ilova `/webhook` ni o‘zi qo‘shadi, Telegram secret headerini tekshiradi.
4. `docker compose --profile production up -d --build`.
5. `curl --fail https://bot.example.uz/health` javobi `{"status":"ok"}` bo‘lsin; Telegramda `/start` va loglarni tekshiring.
6. ACME vositasida sertifikat yangilanishini avtomatlashtiring. Yangilangach `docker compose --profile production exec nginx nginx -s reload`.

Pollingga qaytish: WEBHOOK_URL ni bo‘shatib `docker compose up -d --force-recreate bot`. Polling startup webhookni o‘chiradi. Ichki 8080 portni tashqariga ochish shart emas, HTTPSni Nginx beradi.

## Backup cron va tiklash

Linux/WSLda loyiha ildizidan `sh scripts/backup.sh`: DB custom-format dump `backups/bot-VAQT.dump` ga yoziladi, bo‘sh fayl qabul qilinmaydi, 14 kundan eskilari o‘chiriladi. Cron misoli (yo‘lni moslang):

```cron
0 2 * * * cd /srv/test-obuna-bot && /bin/sh scripts/backup.sh >> /var/log/test-obuna-backup.log 2>&1
```

Cron foydalanuvchisi Dockerga kira olsin. Backuplarni boshqa disk/serverga nusxalang, alohida bazada tiklashni sinang. DB dump PDF/Redisni saqlamaydi: `bot_storage` va `redis_data` volume larini ham arxivlang. Mos nusxa uchun botni to‘xtating, DB dump oling, `docker compose exec -T redis redis-cli SAVE` bajaring va Redisni to‘xtatib volume ni nusxalang. Haqiqiy nomlar `docker volume ls` da (odatda loyiha prefiksi bor). `.env` nusxasini alohida shifrlang.

Tiklashni avval alohida test loyihasida bajaring. Maqsad DB jadvallari almashtiriladi; botni to‘xtatib, Linux/WSL terminalida:

```sh
docker compose stop bot
docker compose exec -T postgres pg_restore -U bot -d bot --clean --if-exists --no-owner < backups/bot-VAQT.dump
```

PDF arxivini mos `bot_storage` volume iga `/bot/storage` tuzilmasi bilan tiklang, egasini bot foydalanuvchisiga moslang. Redis arxivini servis to‘xtatilganda tegishli volume ga tiklang. Servislarni yoqing, migratsiya va healthni tekshiring. Windows PowerShell matn redirectionini binar dump uchun ishlatmang; `backup.sh` Linux/WSLda bajariladi.

## Ishlash va sifat chegaralari

Kalit `1a,2b,3c`: 1..N uzilishsiz. Kod avtomatik 1000–9999. Boshlanish hozir/ertaga 09:00/sana; tugash boshlanishdan 24 soat/3 kun/7 kun/cheksiz/sana, minimal oraliq 10 daqiqa. Referral 0/3/5/10: test boshlanganidan keyingi va hozir obuna takliflar.

Rejalashtirilgan test `draft` + `scheduled_at=start_at`. Startup va har 30 soniyada nashr tekshiriladi; uch xatodan keyin admin bir marta ogohlantiriladi, urinish to‘xtaydi. Sababni tuzatib, rejalashtirishni bekor qilib qayta yaratish mumkin. Yopilgan test TOP-10 natijalari tasdiqdan keyin bir marta kanalga chiqadi. Excel: «Natijalar», «Testni olganlar».

`tests/test_r9_smoke.py` bitta oqimda admin yaratishi → post → obunasiz blok → obunadan keyin PDF → referral sabab rad → takliflar → javob → Excel → yopish → bir martalik natija postini tekshiradi. Haqiqiy DB, mock Telegram ishlatiladi. Menyu/ruxsat, FSM, scheduler va middleware regressiyalari ham mavjud. Jonli BotFather/kanal, tashqi HTTPS va backup/tiklashni bu testlar tasdiqlamaydi; serverda alohida tekshiring.


## Post matnini ixtiyoriy tahrirlash

5 qadamli yaratish oqimi o‘zgarmaydi. Preview yoki rejalashtirilgan test kartasida
«✏️ Postni tahrirlash»ni bosing. Bot hozirgi captionni yuboradi: nusxalab, emoji va
izohlar qo‘shib, to‘liq matnni qayta yuboring. Yangi previewdan keyin
«💾 O‘zgarishlarni saqlash»ni bosing. Orqaga/Bekor saqlanmagan matnni tashlaydi.
Rasm ostidagi matn oddiy matn sifatida, formatlashsiz saqlanadi; limit 1024 UTF-16
birlik (ayrim emojilar ikki birlik). Kod, vaqt va havolalar ham tahrirlanadigan
matn ichida — keraklilarini saqlang. Kod/jadval ma’lumotlari bu matn bilan
almashmaydi. Rejalashtirilgan test allaqachon nashr qilingan bo‘lsa saqlash rad
etiladi. Eski testlar oldingi avtomatik caption bilan ishlaydi. Startupdagi
`d460_custom_caption` migratsiyasi nullable `tests.custom_caption` qo‘shadi.
