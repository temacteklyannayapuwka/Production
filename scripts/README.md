# Служебные скрипты

Скрипты из этой папки не импортируются Django и не запускаются автоматически.

## Подготовка production `.env`

`prepare_production_env.py` читает только секцию `DATABASES` из доверенной
резервной копии `settings.py`, создаёт новый secret key и никогда не выводит
пароль базы данных.

```bash
.venv/bin/python scripts/prepare_production_env.py \
  --source-settings /absolute/path/to/backup/stavplus/settings.py
```

Существующий `.env` не перезаписывается. Другой путь назначения можно указать
через `--output`.
