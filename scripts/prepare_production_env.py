#!/usr/bin/env python3
"""Create an untracked production .env from the trusted local backup.

The script intentionally never prints connection values. Run it locally before
uploading .env to the server; .env is ignored by Git.
"""

from __future__ import annotations

import ast
import argparse
import secrets
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_SETTINGS = (
    PROJECT_ROOT.parent / 'production-backup' / 'stavplus.ru' / 'stavplus' / 'settings.py'
)
DEFAULT_ENV_FILE = PROJECT_ROOT / '.env'
REQUIRED_DATABASE_KEYS = ('ENGINE', 'NAME', 'USER', 'PASSWORD', 'HOST', 'PORT')


def read_backup_database_settings(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == 'DATABASES' for target in node.targets):
            continue
        database = ast.literal_eval(node.value)['default']
        values = {key: str(database.get(key, '')) for key in REQUIRED_DATABASE_KEYS}
        if all(values.values()):
            return values
    raise RuntimeError('PostgreSQL settings were not found in the trusted backup.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Create a protected .env from a trusted Django settings backup.',
    )
    parser.add_argument(
        '--source-settings',
        type=Path,
        default=DEFAULT_BACKUP_SETTINGS,
        help='Path to the trusted production settings.py backup.',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_ENV_FILE,
        help='Destination .env path. Existing files are never overwritten.',
    )
    args = parser.parse_args()
    backup_settings = args.source_settings.expanduser().resolve()
    env_file = args.output.expanduser().resolve()

    if env_file.exists():
        raise SystemExit(f'{env_file} already exists; it was left untouched.')
    if not backup_settings.is_file():
        raise SystemExit(
            f'Trusted backup was not found: {backup_settings}. '
            'Pass its path with --source-settings.'
        )

    database = read_backup_database_settings(backup_settings)
    content = '\n'.join((
        '# Generated locally from the trusted production backup. Never commit this file.',
        f'DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}',
        'DJANGO_DEBUG=false',
        'DJANGO_ALLOWED_HOSTS=stavplus.ru,www.stavplus.ru,localhost,127.0.0.1',
        f"DB_ENGINE={database['ENGINE']}",
        f"DB_NAME={database['NAME']}",
        f"DB_USER={database['USER']}",
        f"DB_PASSWORD={database['PASSWORD']}",
        f"DB_HOST={database['HOST']}",
        f"DB_PORT={database['PORT']}",
        '',
    ))
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(content, encoding='utf-8')
    env_file.chmod(0o600)
    print(f'Created protected environment file: {env_file}')


if __name__ == '__main__':
    main()
