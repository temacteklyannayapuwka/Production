# Безопасная выкладка редизайна на new.stavplus.ru

Этот сценарий предназначен только для тестового поддомена new.stavplus.ru.
Конфигурацию, процесс и рабочую директорию основного stavplus.ru менять нельзя.

## Зафиксированные точки

- исходный HEAD: 4993d992d278d6a08c3f708a754a3356eea74876;
- точка отката: тег pre-figma-redesign-20260910;
- ветка редизайна: redesign/figma-hero.

## Изоляция тестового окружения

Для поддомена нужны отдельные:

- checkout/рабочая директория;
- virtualenv;
- process-manager entry и порт;
- Nginx vhost;
- база данных либо безопасная копия production-базы;
- каталог собранной статики.

В окружении тестового процесса задайте:

    DJANGO_DEBUG=0
    DJANGO_ALLOWED_HOSTS=new.stavplus.ru
    DJANGO_SECRET_KEY=<отдельный тестовый секрет>

Если используется PostgreSQL, DB_NAME должен указывать на тестовую базу. Не
запускайте миграции редизайна против production-базы без отдельного плана.

## Проверка перед переключением vhost

Из checkout ветки редизайна:

    python -m pip install -r requirements.txt -c constraints.txt
    python -m pip check
    python manage.py check --deploy
    python manage.py makemigrations --check --dry-run
    python manage.py test
    python manage.py collectstatic --noinput

Затем запустите отдельный WSGI-процесс на тестовом порту и проверьте его
напрямую с заголовком Host: new.stavplus.ru. Только после успешной проверки
подключайте к этому порту vhost new.stavplus.ru и выпускайте TLS-сертификат
для поддомена.

## Smoke-check после выкладки

Проверьте:

1. главную на desktop и mobile;
2. открытие меню и поиск;
3. страницу раздела, тега и результата поиска;
4. статью с главным фото и галереей;
5. отображение всех рекламных слотов;
6. отсутствие 404 у /static/stavplus-redesign.css и /static/hero/*;
7. отсутствие новых ошибок в журнале тестового процесса.

## Откат тестового поддомена

Остановите только тестовый процесс, переключите его checkout на
pre-figma-redesign-20260910, повторно соберите статику в тестовый каталог и
запустите процесс снова. Основной домен в этом сценарии не участвует.
