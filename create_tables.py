from argparse import ArgumentParser
from typing import LiteralString, cast

from psycopg import Connection


def main() -> None:
    parser = ArgumentParser(
        description='Helper script to create tables in PostreSQL required for this project'
        )
    parser.add_argument(
        'database_uri',
        help='the URI of PostreSQL database where tables will be created',
        )

    database_uri = parser.parse_args().database_uri
    with Connection.connect(database_uri) as conn, open('create-tables.sql') as query_file:
        query = cast(LiteralString, query_file.read())
        conn.execute(query)

    print('Tables created successfully!')


if __name__ == '__main__':
    main()
