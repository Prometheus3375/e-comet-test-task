from argparse import ArgumentParser
from typing import LiteralString, cast

from psycopg import Connection


def main() -> None:
    parser = ArgumentParser(
        description='Helper script to create tables in PostreSQL required for this project'
        )
    parser.add_argument(
        'database_url',
        help='the URL to PostreSQL database where tables will be created',
        )

    database_url = parser.parse_args().database_url
    with Connection.connect(database_url) as conn, open('create-tables.sql') as query_file:
        query = cast(LiteralString, query_file.read())
        conn.execute(query)

    print('Tables created successfully!')


if __name__ == '__main__':
    main()
