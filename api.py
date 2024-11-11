from contextlib import asynccontextmanager
from datetime import date
from logging import getLogger
from operator import attrgetter

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError

from common.models import RepoActivity
from server.db import PostgreSQLManager
from server.models import *


@asynccontextmanager
async def lifespan(_: FastAPI, /):
    # Actions on startup
    yield
    # Actions on shutdown
    await PostgreSQLManager.close()


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
        sort_by: SortByOptions = SortByOptions.stars,
        descending: bool = False,
        ) -> list[RepoDataWithRank]:
    """
    Returns the current top 100 repositories
    sorted by the specified option in the specified order.

    The place is determined by the number of stargazers.
    """
    result = await PostgreSQLManager.fetch_top_n(100)
    result.sort(key=attrgetter(sort_by.name), reverse=descending)
    return result


@app.get('/api/repos/{owner}/{repo}/activity')
async def api_get_activity(
        *,
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
    return await PostgreSQLManager.fetch_activity(
        owner=owner,
        repo=repo,
        since=since,
        until=until,
        )
