# Радиоцех

Интернет-магазин проектов модернизации советских радиоприёмников и библиотека: модели, заводы, статьи, книги и файлы печатных плат в формате **LAY** (оригинал и современная элементная база).

## Почему Django, а не Flask

Для этого проекта нужен каталог с админкой, пользователи, загрузка файлов и заказы. Django даёт это из коробки: ORM, admin, auth, сессии корзины. Flask пришлось бы собирать из расширений. **PostgreSQL** — основная база.

## Данные

`seed_catalog` наполняет каталог из JSON в `data/`: заводы (`factories.json`, `rw6ase_factories.json`), категории, 102 модели из справочника (`receivers.json`) и индекс карточек источника (`all_catalog.json`, ~1460 ссылок на rw6ase.narod.ru).

Сырые исходники в репозиторий не входят: PDF-справочники («Радиозаводы из каталога», «Советские портативные радиоприёмники», `zd_v9.6.pdf`) и сохранённые HTML-страницы источника. Они нужны только скриптам пересборки JSON (`scripts/build_catalog_index.py`, `scripts/import_factories.py`) — положите их в корень и `data/`, если понадобится пересобрать данные. Описания и фото подтягивает `scripts/enrich_receivers.py` прямо с сайта источника.

## Запуск

```bash
source .venv/bin/activate   # или: uv venv && uv pip install -r requirements.txt
cp .env.example .env
./scripts/postgres.sh start   # или: docker compose up -d
python manage.py migrate
python manage.py seed_catalog
python manage.py createsuperuser
python manage.py runserver
```

Админка: https://192.168.100.43/admin/ (локально без nginx — http://127.0.0.1:8000/admin/)

База: `postgres://radiotsekh:radiotsekh@127.0.0.1:5432/radiotsekh`. Локальный сервер без Docker — `./scripts/postgres.sh start`. Если есть Docker — `docker compose up -d`.

## Что загрузить дальше

Платы загружаются через сайт («Платы LAY» → «Добавить проект», для группы «продавец» и персонала) или в админке.

Файлы плат лежат в `private/pcb/`, а не в `media/`: прямой ссылки на них нет, они отдаются только через сайт. Бесплатные доступны всем, платные — персоналу и тому, кто плату загрузил или разработал. Делайте резервную копию `private/` вместе с `media/`. К приёмнику можно привязать сколько угодно оригинальных и современных плат, статей и книг.

## Работа на сервере

- **nginx** (`/etc/nginx/sites-available/radiotsekh.conf`) принимает 80/443: HTTP перенаправляет на HTTPS, завершает TLS и проксирует на Gunicorn `127.0.0.1:8000`. Статику и публичную `media/` отдаёт Django (WhiteNoise и `serve`), `private/` наружу не попадает.
- **Перебор паролей**: nginx пропускает не больше 6 POST-запросов в минуту с одного IP (запас 5) на `/vhod/`, `/admin/login/`, `/registraciya/`, дальше отвечает 429. Общий лимит — 20 запросов в секунду с IP.
- **Сертификат** выпущен локальным CA (`/etc/nginx/ssl/radiotsekh/`, ключи доступны только root), действует до 17.11.2027. Чтобы браузеры не предупреждали, установите корневой сертификат `http://192.168.100.43/radiotsekh-ca.crt` на устройства как доверенный. Когда появится домен, замените на Let's Encrypt (`certbot --nginx`).
- **Django**: `HTTPS=True` в `.env` включает secure-cookie, редирект на HTTPS и HSTS (`SECURE_HSTS_SECONDS`). Для разработки по HTTP — `HTTPS=False`.
- **Сервисы** (systemd --user): `radiotsekh` (Gunicorn), `radiotsekh-postgres`, таймер `radiotsekh-clearsessions`. Логи: `journalctl --user -u radiotsekh`, `sudo tail /var/log/nginx/error.log`.
