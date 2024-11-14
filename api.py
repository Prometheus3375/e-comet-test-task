import os
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date
from logging import getLogger
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from psycopg_pool import AsyncConnectionPool

from common.models import RepoActivity
from server.db import *
from server.models import *


def get_int_env(env_name: str, default: int | None, /) -> int | None:
    """
    Converts the value of an environmental variable into an integer
    if it is set (i.e., it is not ``None`` and not an empty string),
    or returns the default value otherwise.
    """
    value = os.getenv(env_name)
    return int(value) if value else default


DATABASE_URI = os.getenv('DATABASE_URI')
MIN_POOL_SIZE = get_int_env('CONNECTION_POOL_MIN_SIZE', 1)
MAX_POOL_SIZE = get_int_env('CONNECTION_POOL_MAX_SIZE', None)

connection_pool = AsyncConnectionPool(
    DATABASE_URI,
    kwargs=None,
    min_size=MIN_POOL_SIZE,
    max_size=MAX_POOL_SIZE,
    open=False,
    configure=configure_connection,
    check=AsyncConnectionPool.check_connection,
    name='Global PostgreSQL connection pool',
    )


@asynccontextmanager
async def lifespan(_: FastAPI, /) -> Iterator[None]:
    # Actions on startup
    if not (await verify_connectivity(DATABASE_URI)):
        raise ValueError('environmental variable DATABASE_URI is not properly set')

    await connection_pool.open()
    await connection_pool.wait()
    logger.info(
        f'Connection pool is ready. '
        f'Min size is {connection_pool.min_size}, '
        f'max size is {connection_pool.max_size}'
        )
    yield
    # Actions on shutdown
    await connection_pool.close()


async def make_db_requester() -> Iterator[PostgreSQLRequester]:
    """
    Dependency function for creating an instance of :class:`PostgreSQLRequester`.
    """
    async with connection_pool.connection() as conn:
        yield PostgreSQLRequester(conn)


DBRequesterType = Annotated[PostgreSQLRequester, Depends(make_db_requester)]
app = FastAPI(
    title='Entity Resolution API',
    version='1.0.0',
    # PyCharm still thinks / is an argument in a function signature,
    # 5 years has passed since introduction of positional-only specifier,
    # what a shame.
    lifespan=lifespan,
    )
logger = getLogger(__name__)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError, /):
    """
    Request validation handler which logs errors caused by request validation in detail.
    """
    errors = []
    for d in exc.errors():
        msg = d['msg']
        loc = '.'.join(str(part) for part in d['loc'])  # some parts can be integers
        errors.append(f'At location {loc!r} {msg[0].lower()}{msg[1:]}')

    err_noun = 'error' if len(errors) == 1 else 'errors'
    err_msgs = '\n  '.join(errors)
    logger.error(f'{len(errors)} validation {err_noun} in the recent request:\n  {err_msgs}')
    return await request_validation_exception_handler(request, exc)


@app.get('/api/repos/top100')
async def api_get_top_100(
        *,
        db_requester: DBRequesterType,
        sort_by: SortByOptions = SortByOptions.stars,
        descending: bool = False,
        ) -> list[RepoDataWithRank]:
    """
    Returns the current top 100 repositories
    sorted by the specified option in the specified order.

    The place is determined by the number of stargazers.
    """
    result = await db_requester.fetch_top_n(100)
    result.sort(key=sort_by.sort_key, reverse=descending)
    return result


@app.get('/api/repos/{owner}/{repo}/activity')
async def api_get_activity(
        *,
        db_requester: DBRequesterType,
        owner: str,
        repo: str,
        since: date | None = None,
        until: date | None = None,
        ) -> list[RepoActivity]:
    """
    Returns the activity inside the given repository in the specified range of dates.
    Bounds are inclusive; parameters ``since`` and ``until`` must be the same
    for fetching the activity for a single day.
    """
    return await db_requester.fetch_activity(
        owner=owner,
        repo=repo,
        since=since,
        until=until,
        )
