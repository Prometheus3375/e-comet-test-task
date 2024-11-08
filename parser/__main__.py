def main() -> None:
    from argparse import ArgumentParser, RawTextHelpFormatter
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
        'database_url',
        help='The URL to PostreSQL database to update.',
        )
    argparser.add_argument(
        '--github-token',
        help='An authentication token for GitHub for increasing API rate limits.\n'
             'Defaults to None.\n'
             'More on GitHub API rate limits: '
             'https://docs.github.com/en/rest/using-the-rest-api'
             '/rate-limits-for-the-rest-api?apiVersion=2022-11-28',
        )
    argparser.add_argument(
        '--new-limit',
        type=int,
        default=None,
        help='The maximum number of new repositories added to the database.\n'
             'Defaults to None which means no limit.',
        )
    argparser.add_argument(
        '--new-since',
        type=int,
        default=815_368_990,
        help='GitHub repository ID after which new repositories will be fetched.\n'
             'Defaults to 815368990 which is just before ID for Prometheus3375/dim-wishlist.',
        )

    argparser = argparser.parse_args()
    import os

    # Set GITHUB_TOKEN before any other import
    os.environ['GITHUB_TOKEN'] = argparser.github_token

    from common.logging import init_logging
    from parser.update import update_database

    init_logging()
    update_database(
        argparser.database_url,
        new_repo_limit=argparser.new_limit,
        after_github_id=argparser.new_since,
        )


if __name__ == '__main__':
    main()
