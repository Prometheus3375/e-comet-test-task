from datetime import date
from logging import getLogger
from math import inf

from psycopg import Connection
from psycopg.rows import TupleRow

from .requests import *

logger = getLogger(__name__)


def update_activity(
        conn: Connection[TupleRow],
        repo_id: int,
        /,
        *,
        owner: str,
        repo: str,
        last_activity_date: date | None = None,
        ) -> None:
    """
    Fetches activity information from GitHub API for the specified repository
    and updates the database with the new information.

    :param conn: An active connection to the database.
    :param repo_id: ID of the repository in the database.
    :param owner: Name of the owner of the repository.
    :param repo: Name of the repository.
    :param last_activity_date: A date from which start requesting activity information.
        If ``None``, fetches all available information.
    """
    if last_activity_date is None:
        last_activity_date = date(1970, 1, 1)

    for activity in request_repo_activity(owner, repo, last_activity_date):
        with conn.cursor() as cursor:
            cursor.execute(
                """
                insert into
                    activity (repo_id, date, commits, authors)
                    values (%(id)s, %(date)s, %(commits)s, %(authors)s)
                on conflict on constraint repo_id_date_tuple
                do update
                    set commits = %(commits)s, authors = %(authors)s
                    -- Avoid updates if data is unchanged
                    where activity.commits <> %(commits)s or activity.authors <> %(authors)s
                """,
                dict(
                    id=repo_id,
                    date=activity.date,
                    commits=activity.commits,
                    authors=sorted(activity.authors),
                    ),
                )


def update_database(
        database_uri: str,
        github_token: str | None,
        /,
        *,
        skip_rank_update: bool,
        skip_repo_update: bool,
        new_repo_limit: int | None,
        after_github_id: int,
        ) -> None:
    """
    Updates the database with the new information about repositories and their activity.

    :param database_uri: URI of the database.
    :param github_token: A GitHub authentication token for increasing API rate limits.
    :param skip_rank_update: If ``True``, skips the step of updating table for previous places.
    :param skip_repo_update: If ``True``, skips the step of updating already present repositories.
    :param new_repo_limit: The maximum number of new repositories to fetch from GitHub API.
        Can be ``None`` to fetch an unlimited number of repositories.
    :param after_github_id: Any new repository will have GitHub ID higher than this value.
    """
    # region Verify parameters
    if not isinstance(database_uri, str):
        raise TypeError(f'database_uri must be a string, got {database_uri!r}')

    if not (github_token is None or isinstance(github_token, str)):
        raise TypeError(f'github_token must be a string or None, got {github_token!r}')

    if github_token is not None:
        from parser import requests

        requests.headers['Authorization'] = f'Bearer {github_token}'
        logger.info(f'GitHub token is successfully added to headers of requests')

    if new_repo_limit is None:
        new_repo_limit = inf

    if not (new_repo_limit is None or isinstance(new_repo_limit, int)):
        raise TypeError(f'new_repo_limit must be an integer or None, got {new_repo_limit!r}')

    if new_repo_limit is None:
        new_repo_limit = inf
    else:
        new_repo_limit = max(0, new_repo_limit)

    if not isinstance(after_github_id, int):
        raise TypeError(f'after_github_id must be an integer, got {after_github_id!r}')

    # This value must be positive
    after_github_id = max(0, after_github_id)
    # endregion

    conn: Connection[TupleRow]
    # Specify autocommit, so all transactions are not nested transactions
    # https://www.psycopg.org/psycopg3/docs/basic/transactions.html#transaction-contexts
    with Connection.connect(database_uri, autocommit=True) as conn:
        # Step 1: evaluate current top and save to previous_places
        # The latest top always evaluated on demand;
        # while the database updating, the top at the beginning of update will become obsolete
        # and will represent previous top.
        if skip_rank_update:
            logger.info('Step 1 skipped')
        else:
            logger.info('Step 1: update table \'previous_places\'')
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    begin;
                    merge into previous_places
                    using (
                        select id, rank() over (order by stars desc) as p
                        from repositories
                        ) as current_places
                    on current_places.id = previous_places.repo_id
                    -- Avoid updates if data is unchanged
                    when matched and place <> p then
                        update set place = p
                    when not matched then  -- when not matched by target
                        insert (repo_id, place)
                        values (current_places.id, current_places.p);
                    commit;
                    """
                    )

            logger.info('Step 1: complete')

        # Step 2: update existing repos
        if skip_repo_update:
            with conn.cursor() as existing_repos:
                existing_repos.execute(
                    """
                    select (owner || '/' || repo) as repo
                    from repositories
                    """
                    )
                updated_repos = {row[0] for row in existing_repos}

            logger.info('Step 2 skipped')
        else:
            logger.info('Step 2: update existing repositories')
            with conn.cursor() as existing_repos:
                existing_repos.execute(
                    """
                    select id, owner, repo, last_activity_date
                    from repositories
                    left join
                    (
                        select repo_id, max(date) as last_activity_date
                        from activity
                        group by repo_id
                    ) as dates
                    on repositories.id = dates.repo_id
                    """
                    )

                updated_repos = set()
                for repo_id, owner, repo, last_activity_date in existing_repos:
                    # Add to updated_repos regardless of the request result
                    # as inserting an existing repo later will cause an error
                    full_name = f'{owner}/{repo}'
                    updated_repos.add(full_name)
                    repo_data = request_repo(owner, repo)
                    if not repo_data: continue

                    # Update repository and activity
                    with conn.transaction():
                        # Update repository
                        with conn.cursor() as crs:
                            crs.execute(
                                """
                                update repositories
                                set stars = %(stars)s
                                    , watchers = %(watchers)s
                                    , forks = %(forks)s
                                    , open_issues = %(open_issues)s
                                    , language = %(language)s
                                where 
                                    id = %(id)s
                                    -- Avoid updates if all values unchanged
                                    and (
                                        stars <> %(stars)s
                                        or watchers <> %(watchers)s
                                        or forks <> %(forks)s
                                        or open_issues <> %(open_issues)s
                                        or language <> %(language)s
                                    )
                                """,
                                dict(
                                    id=repo_id,
                                    stars=repo_data.stars,
                                    watchers=repo_data.watchers,
                                    forks=repo_data.forks,
                                    open_issues=repo_data.open_issues,
                                    language=repo_data.language,
                                    ),
                                )

                        # Update activity
                        update_activity(
                            conn,
                            repo_id,
                            owner=owner,
                            repo=repo,
                            last_activity_date=last_activity_date,
                            )
                        logger.info(
                            f'Updated repository {repo_id} '
                            f'https://github.com/{owner}/{repo}'
                            )

            logger.info('Step 2: complete')

        # Step 3: fetch new repositories
        logger.info(f'Step 3: fetch new repositories (up to {new_repo_limit})')
        it = request_public_repositories(
            new_repo_limit,
            skip_repos=updated_repos,
            after_github_id=after_github_id,
            )
        for repo_data in it:
            # Insert repository and activity
            with conn.transaction():
                # Insert repository
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        insert into
                        repositories (repo, owner, stars, watchers, forks, open_issues, language)
                        values (
                            %(repo)s
                            , %(owner)s
                            , %(stars)s
                            , %(watchers)s
                            , %(forks)s
                            , %(open_issues)s
                            , %(language)s
                            )
                        -- While it is guaranteed that no conflicts appear by set updated_repos,
                        -- still do nothing on conflict.
                        on conflict do nothing
                        returning id
                        """,
                        repo_data.model_dump(),
                        )
                    row = cursor.fetchone()
                    # row shouldn't be None, but just in case
                    if row is None: continue
                    repo_id = row[0]

                # Insert activity
                update_activity(conn, repo_id, owner=repo_data.owner, repo=repo_data.repo)
                logger.info(
                    f'Added repository {repo_id} '
                    f'https://github.com/{repo_data.owner}/{repo_data.repo}'
                    )

        logger.info('Step 3: complete')
        logger.info('Database updated successfully')


__all__ = 'update_database',
