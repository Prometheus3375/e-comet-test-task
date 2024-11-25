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

settings: Settings
connection_pool: AsyncConnectionPool


@asynccontextmanager
async def lifespan(_: FastAPI, /) -> Iterator[None]:
    global settings, connection_pool
    # Actions on startup
    settings = Settings()

    if not (await verify_connectivity(settings.database_uri)):
        raise ValueError('environmental variable DATABASE_URI is not properly set')

    connection_pool = AsyncConnectionPool(
        settings.database_uri,
        kwargs=None,
        min_size=settings.connection_pool_min_size,
        max_size=settings.connection_pool_max_size,
        open=False,
        configure=configure_connection,
        check=AsyncConnectionPool.check_connection,
        name='Global PostgreSQL connection pool',
        )

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
    title='Public Repository API',
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
