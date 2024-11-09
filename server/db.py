from datetime import date
from logging import getLogger
from typing import LiteralString, final

from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import class_row

from common.models import RepoActivity
from .models import *

logger = getLogger(__name__)


@final
class PostgreSQLManager:
    """
    A class for managing connections to PostgreSQL databases.
    """
    def __init__(self, /) -> None:
        raise TypeError(f'cannot instantiate {self.__class__.__name__}')

    __connection: AsyncConnection | None = None

    @classmethod
    async def __connect(cls, /) -> AsyncConnection:
        """
        Establishes connection to a database or returns an existing one.
        """
        if cls.__connection is None:
            import os

            url = os.environ.get('DATABASE_URL')
            if not url:
                raise ValueError('environmental variable DATABASE_URL must be set')

            parsed = conninfo_to_dict(url)
            logger.info(
                f"Connecting to the database "
                f"postgresql://{parsed['user']}:REDACTED@"
                f"{parsed['host']}:{parsed['port']}/{parsed['database']}"
                )
            cls.__connection = await AsyncConnection.connect(url)
            await cls.__connection.set_read_only(True)

        return cls.__connection

    @classmethod
    async def close(cls, /) -> None:
        """
        Closes the connection to the database.
        """
        if cls.__connection is not None:
            await cls.__connection.close()
            cls.__connection = None

    @classmethod
    async def fetch_top_n(cls, n: int, /) -> list[RepoDataWithRank]:
        """
        Fetches the top ``n`` repositories.
        """
        conn = await cls.__connect()
        async with conn.cursor(row_factory=class_row(RepoDataWithRank)) as cursor:
            result = await cursor.execute(
                """
                with current_places as (
                    select *, rank() over (order by stars desc) as position_cur
                    from repositories
                    limit %(top_n)s
                    )
                select (owner || '/' || repo) as repo
                     , owner
                     , position_cur
                     , place as position_prev
                     , stars
                     , watchers
                     , forks
                     , open_issues
                     , language
                
                from current_places
                    left join previous_places
                    on current_places.id = previous_places.repo_id
                """,
                dict(top_n=n),
                )
            return await result.fetchall()

    _query_fetch_activity_all: LiteralString = """
        with this_repo as (
            select id, owner, repo
            from repositories
            where owner = %(owner)s and repo = %(repo)s
            )
        select date, commits, authors
        from this_repo
            left join activity
            on this_repo.id = activity.repo_id
        """
    _query_fetch_activity_since: LiteralString = f"""
        {_query_fetch_activity_all.lstrip()}
        where %(since)s <= date
        """
    _query_fetch_activity_until: LiteralString = f"""
        {_query_fetch_activity_all.lstrip()}
        where date <= %(until)s
        """
    _query_fetch_activity_since_until: LiteralString = f"""
        {_query_fetch_activity_all.lstrip()}
        where %(since)s <= date and date <= %(until)s
        """

    @classmethod
    async def fetch_activity(
            cls,
            /,
            owner: str,
            repo: str,
            since: date | None,
            until: date | None,
            ) -> list[RepoActivity]:
        """
        Fetches the activity for a repository with the given owner for the specified period.
        """
        query: LiteralString
        if since is None and until is None:
            query = cls._query_fetch_activity_all
            params = dict(repo=repo, owner=owner)
        elif since is None:
            query = cls._query_fetch_activity_until
            params = dict(repo=repo, owner=owner, until=until)
        elif until is None:
            query = cls._query_fetch_activity_since
            params = dict(repo=repo, owner=owner, since=since)
        else:
            query = cls._query_fetch_activity_since_until
            params = dict(repo=repo, owner=owner, since=since, until=until)

        conn = await cls.__connect()
        async with conn.cursor(row_factory=class_row(RepoActivity)) as cursor:
            result = await cursor.execute(query, params)
            return await result.fetchall()


__all__ = 'PostgreSQLManager',
