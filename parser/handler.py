import json
import os
from logging import Formatter, LogRecord, getLogger
from typing import Any, overload

from parser.defaults import *

logger = getLogger(__name__)


@overload
def int_or_none(value: Any, /) -> int: ...


@overload
def int_or_none(value: None, /) -> None: ...


def int_or_none(value: Any | None, /) -> int | None:
    """
    Coverts a value to an integer.
    If the passed value is ``None``, returns ``None``.
    """
    return None if value is None else int(value)


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


def handler(_, __, /) -> dict[str, Any]:
    """
    Handler for Yandex Cloud function.
    """
    from common.logging import init_logging

    init_logging(formatter=YCFormatter(), use_new_handler=False)

    from parser.update import update_database

    database_uri = os.environ.get('DATABASE_URI')
    github_token = os.environ.get('GITHUB_TOKEN')
    skip_rank_update = os.environ.get('SKIP_RANK_UPDATE')
    skip_repo_update = os.environ.get('SKIP_REPO_UPDATE')
    new_repo_limit = os.environ.get('NEW_REPO_LIMIT', DEFAULT_NEW_REPO_LIMIT)
    after_github_id = os.environ.get('NEW_REPO_SINCE', DEFAULT_AFTER_GITHUB_ID)

    try:
        update_database(
            database_uri,
            github_token,
            skip_rank_update=bool(skip_rank_update),
            skip_repo_update=bool(skip_repo_update),
            new_repo_limit=int_or_none(new_repo_limit),
            after_github_id=int_or_none(after_github_id),
            )

        code = 200
        body = 'Success'
    except Exception:
        body = 'An error occurred during database update'
        logger.exception(body)
        code = 500

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
                    ]
                f.write(b'\n'.join(reqs))
                f.write(b'\n')

            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            os.chdir(parent_dir)
            # zf.write(os.path.basename(__file__))
            for parent_path, dirnames, filenames in os.walk('common'):
                for filename in filenames:
                    if filename.endswith('.py'):
                        zf.write(os.path.join(parent_path, filename))

            for parent_path, dirnames, filenames in os.walk('parser'):
                for filename in filenames:
                    if filename.endswith('.py') and filename != '__main__.py':
                        zf.write(os.path.join(parent_path, filename))


    main()
