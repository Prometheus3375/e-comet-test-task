from datetime import date
from logging import getLogger
from typing import LiteralString, final

from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import class_row

from common.models import RepoActivity
from .models import *

logger = getLogger(__name__)


async def configure_connection(conn: AsyncConnection, /) -> None:
    """
    A function for configuring a database connection.
    """
    await conn.set_autocommit(True)
    await conn.set_read_only(True)


async def verify_connectivity(uri: str, /) -> bool:
    """
    Verifies whether a connection to the database with the given URI can be established
    and logs errors if it is not possible.
    """
    try:
        parsed = conninfo_to_dict(uri)
        logger.info(
            f"Verifying connectivity to the database "
            f"postgresql://{parsed['user']}:REDACTED@"
            f"{parsed['host']}:{parsed['port']}/{parsed['dbname']}"
            )
    except Exception:
        logger.exception('Failed to parse the provided PostgreSQL URI')
        return False

    try:
        async with await AsyncConnection.connect(uri) as conn:
            await configure_connection(conn)
            logger.info('Connection to the database can be established successfully')
    except Exception:
        logger.exception('Connection to the database cannot be established')
        return False

    return True


@final
class PostgreSQLRequester:
    """
    A class for querying PostgreSQL database.
    """
    def __init__(self, connection: AsyncConnection, /) -> None:
        self._conn = connection

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


__all__ = 'configure_connection', 'verify_connectivity', 'PostgreSQLRequester'
