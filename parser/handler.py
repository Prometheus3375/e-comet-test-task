import json
from logging import Formatter, LogRecord, getLogger
from typing import Any

from pydantic import NonNegativeInt
from pydantic_settings import BaseSettings

from common.models import NonEmptyString
from parser.defaults import *
from parser.logging import init_logging
from parser.update import update_database

logger = getLogger(__name__)


def truncate(value: str, limit: int, /) -> str:
    """
    If the length of the given string is higher than the limit,
    cuts it to ``limit - 3`` characters and appends ellipsis.
    """
    return f'{value[:limit - 3]}...' if len(value) > limit else value


class YCFormatter(Formatter):
    """
    Log formatter for Yandex Cloud.
    """
    __slots__ = ()

    def format(self, record: LogRecord, /) -> str:
        message = record.getMessage().rstrip()

        if record.exc_info:
            exc_text = record.exc_text or self.formatException(record.exc_info)
            message = f'{message}\n{exc_text.rstrip()}'

        if record.stack_info:
            stack_text = self.formatStack(record.stack_info)
            message = f'{message}\n{stack_text.rstrip()}'

        match record.levelname:
            case 'WARNING': level = 'WARN'
            case 'CRITICAL': level = 'FATAL'
            case lvl: level = lvl

        msg = dict(
            message=message,
            level=level,
            logger=record.name,
            stream_name=truncate(record.name, 63),
            )
        return json.dumps(msg)


class Settings(BaseSettings, env_ignore_empty=True):
    """
    Model for holding handler settings.
    """
    database_uri: NonEmptyString
    github_token: NonEmptyString | None = None
    skip_rank_update: bool = False
    skip_repo_update: bool = False
    new_repo_limit: NonNegativeInt | None = DEFAULT_NEW_REPO_LIMIT
    new_repo_since: NonNegativeInt = DEFAULT_AFTER_GITHUB_ID


def handler(_, __, /) -> dict[str, Any]:
    """
    Handler for Yandex Cloud function.
    """
    init_logging(YCFormatter(), use_new_handler=False)

    try:
        settings = Settings()
        update_database(
            settings.database_uri,
            settings.github_token,
            skip_rank_update=settings.skip_rank_update,
            skip_repo_update=settings.skip_repo_update,
            new_repo_limit=settings.new_repo_limit,
            after_github_id=settings.new_repo_since,
            )

        code = 200
        body = 'Success'
    except Exception:
        code = 500
        body = 'An error occurred during database update'
        logger.exception(body)

    return {
        'statusCode':      code,
        'headers':         {
            'Content-Type': 'text/plain'
            },
        'isBase64Encoded': False,
        'body':            body,
        }


if __name__ == '__main__':
    def main() -> None:
        import os
        from zipfile import ZipFile

        with ZipFile('cloud-function.zip', 'w') as zf:
            with zf.open('requirements.txt', 'w') as f:
                reqs = [
                    b'psycopg[binary]~=3.2.3',
                    b'pydantic~=2.9.2',
                    b'pydantic-settings~=2.6.1',
                    ]
                f.write(b'\n'.join(reqs))
                f.write(b'\n')

            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            os.chdir(parent_dir)
            for parent_path, dirnames, filenames in os.walk('common'):
                for filename in filenames:
                    if filename.endswith('.py'):
                        zf.write(os.path.join(parent_path, filename))

            for parent_path, dirnames, filenames in os.walk('parser'):
                for filename in filenames:
                    if filename.endswith('.py') and filename != '__main__.py':
                        zf.write(os.path.join(parent_path, filename))


    main()
