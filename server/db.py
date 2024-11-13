from datetime import date
from logging import getLogger
from types import TracebackType
from typing import LiteralString, Self, TypeVar, final

from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import class_row

from common.models import RepoActivity
from .models import *

ExcT = TypeVar('ExcT', bound=BaseException)
logger = getLogger(__name__)


@final
class PostgreSQLManager:
    """
    A class for managing connections to PostgreSQL database.
    """
    def __init__(self, connection: AsyncConnection, /) -> None:
        self._conn = connection

    @classmethod
    async def __make_connection(cls, uri: str, /) -> AsyncConnection:
        """
        Establishes a connection to the database with the given URI.
        """
        # Specify autocommit to avoid starting a transaction with the first select
        # https://www.psycopg.org/psycopg3/docs/basic/transactions.html#autocommit-transactions
        conn = await AsyncConnection.connect(uri, autocommit=True)
        await conn.set_read_only(True)
        return conn

    @classmethod
    async def verify_connectivity(cls, uri: str | None, /) -> bool:
        """
        Verifies whether a connection to the database with the given URI can be established
        and logs errors if it is not possible.
        """
        if not uri:
            logger.error('URI of PostgreSQL cannot be None or empty')
            return False

        try:
            parsed = conninfo_to_dict(uri)
        except Exception:
            logger.exception('Failed to parse the provided PostgreSQL URI')
            return False

        logger.info(
            f"Verifying connectivity to the database "
            f"postgresql://{parsed['user']}:REDACTED@"
            f"{parsed['host']}:{parsed['port']}/{parsed['dbname']}"
            )

        try:
            connection = await cls.__make_connection(uri)
            logger.info('Connection to the database can be established successfully')
            await connection.close()
        except Exception:
            logger.exception('Connection to the database cannot be established')
            return False

        return True

    @classmethod
    async def connect(cls, uri: str, /) -> Self:
        """
        Creates a manager for the database with the given URI.
        """
        return cls(await cls.__make_connection(uri))

    async def close(self, /) -> None:
        """
        Closes this database manager.
        """
        await self._conn.close()

    async def __aenter__(self, /) -> Self:
        return self

    async def __aexit__(
            self,
            exc_type: type[ExcT] | None,
            exc_val: ExcT | None,
            exc_tb: TracebackType | None,
            /,
            ) -> bool:
        await self.close()
        return False

    async def fetch_top_n(self, n: int, /) -> list[RepoDataWithRank]:
        """
        Fetches the top ``n`` repositories.
        The place is determined by the number of stargazers.
        """
        async with self._conn.cursor(row_factory=class_row(RepoDataWithRank)) as cursor:
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

    async def fetch_activity(
            self,
            /,
            owner: str,
            repo: str,
            since: date | None,
            until: date | None,
            ) -> list[RepoActivity]:
        """
        Fetches the activity for the repository with the given owner for the specified period.
        """
        query: LiteralString
        if since is None and until is None:
            query = self._query_fetch_activity_all
            params = dict(repo=repo, owner=owner)
        elif since is None:
            query = self._query_fetch_activity_until
            params = dict(repo=repo, owner=owner, until=until)
        elif until is None:
            query = self._query_fetch_activity_since
            params = dict(repo=repo, owner=owner, since=since)
        else:
            query = self._query_fetch_activity_since_until
            params = dict(repo=repo, owner=owner, since=since, until=until)

        async with self._conn.cursor(row_factory=class_row(RepoActivity)) as cursor:
            result = await cursor.execute(query, params)
            return await result.fetchall()


__all__ = 'PostgreSQLManager',
