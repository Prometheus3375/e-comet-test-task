if __name__ == '__main__':
    from argparse import ArgumentParser, RawTextHelpFormatter
    from parser.defaults import *
    import parser

    argparser = ArgumentParser(
        prog=f'python -m {parser.__name__}',
        formatter_class=RawTextHelpFormatter,
        description='A script for updating the database with new repository information',
        add_help=False,
        )

    argparser.add_argument(
        '-h',
        '--help',
        action='help',
        help='If specified, the script shows this help message and exits.',
        )
    argparser.add_argument(
        'database_uri',
        help='The URI of PostgreSQL database to update.',
        )
    argparser.add_argument(
        '--github-token',
        help='A GitHub authentication token for increasing API rate limits.\n'
             'Defaults to None.\n\n'
             'More on GitHub API rate limits: '
             'https://docs.github.com/en/rest/using-the-rest-api'
             '/rate-limits-for-the-rest-api?apiVersion=2022-11-28',
        )
    argparser.add_argument(
        '--skip-rank-update',
        action='store_true',
        help='If specified, the script does not update previous places of repositories.',
        )
    argparser.add_argument(
        '--skip-repo-update',
        action='store_true',
        help='If specified, the script does not update '
             'general and activity information of repositories.',
        )
    argparser.add_argument(
        '--update-repo-since',
        type=int,
        default=DEFAULT_UPDATE_REPO_SINCE,
        help='The value of database ID since which the repositories are updated. '
             'This bound is inclusive.\n'
             f'Defaults to {DEFAULT_UPDATE_REPO_SINCE}.',
        )
    argparser.add_argument(
        '--update-repo-until',
        type=int,
        default=DEFAULT_UPDATE_REPO_UNTIL,
        help='The value of database ID until which the repositories are updated. '
             'This bound is inclusive.\n'
             f'If not specified, this bound is disabled.',
        )
    argparser.add_argument(
        '--new-repo-limit',
        type=int,
        default=DEFAULT_NEW_REPO_LIMIT,
        help='The maximum number of new repositories added to the database.\n'
             'Defaults to None which means no limit.',
        )
    argparser.add_argument(
        '--new-repo-since',
        type=int,
        default=DEFAULT_AFTER_GITHUB_ID,
        help=f'GitHub repository ID after which new repositories are fetched.\n'
             f'Defaults to {DEFAULT_AFTER_GITHUB_ID} '
             f'which is just before ID for Prometheus3375/dim-wishlist.',
        )

    params = argparser.parse_args()
    from logging import Formatter
    from parser.logging import init_logging
    from parser.update import update_database

    init_logging(
        Formatter(
            fmt='{asctime} [{name}] {levelname:<8} {message}',
            datefmt='%Y-%m-%d %H:%M:%S',
            style='{',
            )
        )
    update_database(
        params.database_uri,
        params.github_token,
        skip_rank_update=params.skip_rank_update,
        skip_repo_update=params.skip_repo_update,
        update_repo_since=params.update_repo_since,
        update_repo_until=params.update_repo_until,
        new_repo_limit=params.new_repo_limit,
        after_github_id=params.new_repo_since,
        )
