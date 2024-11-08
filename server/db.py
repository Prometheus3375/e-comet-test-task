import os
from datetime import date
from typing import final

from psycopg import AsyncConnection
from psycopg.rows import DictRow, class_row

from server.models import *


@final
class PostgreSQLManager:
    """
    A class for managing connections to PostgreSQL databases.
    """
    def __init__(self, /) -> None:
        raise TypeError(f'cannot instantiate {self.__class__.__name__}')

    __connection: AsyncConnection[DictRow] | None = None

    @classmethod
    async def __connect(cls, /) -> AsyncConnection[DictRow]:
        """
        Establishes connection to a database or returns an existing one.
        """
        if cls.__connection is None:
            url = os.environ.get('DATABASE_URL')
            cls.__connection = await AsyncConnection.connect(url)
            cls.__connection.read_only = True

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
    async def fetch_top_n(cls, n: int, /) -> list[RepoData]:
        """
        Fetches the top ``n`` repositories.
        """
        conn = await cls.__connect()
        async with conn.cursor(row_factory=class_row(RepoData)) as cursor:
            result = await cursor.execute('')  # todo
            return await result.fetchall()

    @classmethod
    async def fetch_activity(
            cls,
            /,
            repo: str,
            owner: str,
            since: date,
            until: date,
            ) -> list[RepoActivity]:
        """
        Fetches the activity for a repository with the given owner for the specified period.
        """
        conn = await cls.__connect()
        async with conn.cursor(row_factory=class_row(RepoActivity)) as cursor:
            result = await cursor.execute('')  # todo
            return await result.fetchall()


__all__ = 'PostgreSQLManager',
