# StavPlus

Django-проект новостного сайта «Ставрополь+». Главная страница выводит опубликованные новости и категории, которые заполняются через админ-панель Django.

## Локальный запуск

Целевой runtime совпадает с production: Python 3.12 и Django 6.0.6.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# Replace DJANGO_SECRET_KEY in .env before continuing.
python manage.py migrate
python manage.py runserver
```

Откройте `http://127.0.0.1:8000/`. Админ-панель находится по адресу `/admin/`.

## Демо-наполнение

Чтобы локальная главная сразу выглядела заполненной, выполните:

```bash
python manage.py seed_demo_news
```

Команда создаёт только локальные демонстрационные категории и новости с фотографиями. Она не запускается при деплое и не заменяет реальные материалы из админ-панели.

## Переменные окружения

Перед публикацией на хостинге задайте значения из `.env.example` в настройках окружения ISPmanager или в конфигурации процесса:

- `DJANGO_SECRET_KEY` — уникальный секретный ключ;
- `DJANGO_DEBUG=0` — отключает отладочный режим;
- `DJANGO_ALLOWED_HOSTS=stavplus.ru,www.stavplus.ru` — домены сайта.

`.env`, база `db.sqlite3`, пользовательские загрузки `media/`, собранная статика и виртуальное окружение намеренно исключены из Git.

Для опционального PostgreSQL установите системные клиентские библиотеки и
используйте `pip install -r requirements-postgres.txt` вместо базового списка.

Транзитивные версии, проверенные для Python 3.12, закреплены в
`constraints.txt`. Все три requirements-файла используют один базовый runtime,
поэтому локальное, development- и PostgreSQL-окружения не расходятся.

## Известный долг CKEditor

`django-ckeditor` 6.7.3 включает неподдерживаемый CKEditor 4.22.1 с известными
неисправленными уязвимостями и поэтому выдаёт предупреждение `ckeditor.W001`
при системных проверках Django. Предупреждение намеренно не отключено. Переход
на CKEditor 5 либо поддерживаемый CKEditor 4 LTS нужно выполнить отдельной
задачей после проверки совместимости редакционных данных и условий лицензии.

## Публикация

На сервере после получения коммита выполните:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

Затем перезапустите процесс приложения через ISPmanager или используемый процесс-менеджер.

## Проверки качества

Инструменты разработки устанавливаются отдельно от production-зависимостей:

```bash
pip install -r requirements-dev.txt
python -m pip check
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
ruff check .
git diff --check
```

## Структура проекта

- `news/` — модели, admin, views, URL, migrations, команды и тесты приложения;
- `stavplus/` — project-level Django settings, WSGI/ASGI и root URL config;
- `templates/` и `static/` — рабочий интерфейс сайта;
- `news/fixtures/` — демонстрационные данные и bundled media;
- `scripts/` — служебные операции, не запускаемые приложением автоматически;
- `docs/` — презентации, отчёты, архив и статический прототип;
- `server.py` и `ecosystem.config.js` — существующие файлы совместимости хостинга.

Локальные `.venv`, `db.sqlite3`, `media/`, `staticfiles/`, кэши Python и Ruff
не входят в репозиторий. VS Code скрывает их из Explorer, но Django продолжает
использовать их в обычном режиме.
