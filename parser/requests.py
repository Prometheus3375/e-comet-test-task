import json
import os
from collections.abc import Iterator
from datetime import date, datetime
from http.client import HTTPResponse
from logging import getLogger
from math import ceil
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from common.models import MAX_AUTHOR_NAME_LENGTH, RepoActivity, RepoData

logger = getLogger(__name__)
_headers = {
    'Accept':               'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    }

_github_token = os.environ.get('GITHUB_TOKEN')
if _github_token:
    _headers['Authorization'] = f'Bearer {_github_token}'
    from common.logging import init_logging

    init_logging()
    logger.info(f'GitHub token is successfully added to headers')

del _github_token


def make_request(url: str, /) -> Request:
    """
    Creates a request with default headers for GitHub API.
    """
    return Request(url, headers=_headers)


def request_data(url: str, /) -> Any:
    """
    Creates a request with default headers for GitHub API
    and returns JSON data from the response.
    """
    response: HTTPResponse
    with urlopen(make_request(url)) as response:
        return json.loads(response.read())


def request_repo(owner: str, repo: str, /) -> RepoData | None:
    """
    Requests repository info via GitHub API
    and returns respective :class:`RepoData` instance.
    Returns ``None`` if request fails or returns invalid data.
    """
    # Response schema:
    # https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#get-a-repository
    try:
        data = request_data(f'https://api.github.com/repos/{owner}/{repo}')
        return RepoData(
            id=data['id'],
            repo=repo,
            owner=owner,
            stars=data['stargazers_count'],
            watchers=data['watchers_count'],
            forks=data['forks_count'],
            open_issues=data['open_issues_count'],
            language=data['language'],
            )
    except HTTPError as e:
        logger.error(f'{e.__class__.__name__} {e.code} ({e.reason}) for {e.url!r}')
        return None
    except ValidationError as e:
        logger.error(str(e))
        return None


def request_public_repositories(
        limit: float,
        /,
        skip_repos: set[str],
        after_github_id: int,
        ) -> Iterator[RepoData]:
    """
    Requests public repositories from GitHub API and yields :class:`RepoData` instances.

    :param limit: The maximum number of repositories to yield.
        Can be ``inf`` to yield an unlimited number of repositories.
    :param skip_repos: A set of strings of format ``repo_owner/repo_name``.
        If any requested repo is inside this set, it is not yielded.
    :param after_github_id: Any requested repository will have GitHub ID higher than this value.
        Can be zero to request from the very first repository.
    """
    last_id = after_github_id
    curr = 0
    while curr < limit:
        # Response schema:
        # https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#list-public-repositories
        try:
            # Parameter since excludes the repository with such id from the result
            data = request_data(f'https://api.github.com/repositories?since={last_id}')
        except HTTPError as e:
            logger.error(f'{e.__class__.__name__} {e.code} ({e.reason}) for {e.url!r}')
            # Exit immediately
            return

        for repo in data:
            if curr >= limit: break

            last_id = repo['id']
            owner = repo['owner']['login']
            name = repo['name']
            if f'{owner}/{name}' in skip_repos: continue

            repo_data = request_repo(owner, name)
            if repo_data:
                yield repo_data
                curr += 1


def parse_commit(commit: dict[str, Any]) -> tuple[date, str | None] | None:
    """
    Parses a commit object from GitHub API into commit date and author name.
    Returns ``None``, if commit date is not present.
    """
    # Use committer instead of author as the former is actually the one who contributed.
    # Also, GitHub sorts commits by the date committed, not authored.
    # For example
    # https://api.github.com/repos/RSamokhin/tslint/commits?since=2014-04-13&until=2014-04-14
    # 4th commit has author '=', commit was also authored a month earlier.
    commit_author = commit['commit']['committer']
    if commit_author:
        commit_dt = commit_author.get('date')
        if commit_dt:
            commit_dt = datetime.fromisoformat(commit_dt)
            commit_date = date(commit_dt.year, commit_dt.month, commit_dt.day)
            author_name = commit_author.get('name')
            return commit_date, author_name

    return None


def request_repo_activity(owner: str, repo: str, /, since: date) -> Iterator[RepoActivity]:
    """
    Requests activity since the given date for the specified repository from GitHub API
    and yields :class:`RepoActivity` instances.
    """
    # Retrieve total commit count
    # Ref: https://stackoverflow.com/a/70610670/14369408
    # Parameter since is inclusive here up to seconds.
    url = (
        f'https://api.github.com/repos/{owner}/{repo}/commits'
        f'?since={since}&per_page=1'
    )
    try:
        response: HTTPResponse
        with urlopen(make_request(url)) as response:
            link = response.getheader('Link')
            # If there is no link for the very first page,
            # then the number of (new) commits is zero.
            # Here is the project with 1 commit in main (yet):
            # https://github.com/Prometheus3375/wc3-generation
            # The first page has the commit and link header,
            # the next is empty and no header.
            if link is None: return

            _, _, number_rel = link.rpartition('page=')
            number, _, _ = number_rel.partition('>')
            commits_total = int(number)

    except HTTPError as e:
        logger.error(f'{e.__class__.__name__} {e.code} ({e.reason}) for {e.url!r}')
        return

    # Request 100 (max) commits per page
    pages_count = ceil(commits_total / 100)
    # Commits are returned sorted by committed date in descending order
    last_date: date | None = None
    commit_count = 0
    authors = set()
    for page in range(1, pages_count + 1):
        url = (
            f'https://api.github.com/repos/{owner}/{repo}/commits'
            f'?since={since}&per_page=100&page={page}'
        )
        # Response schema:
        # https://docs.github.com/en/rest/commits/commits?apiVersion=2022-11-28#list-commits
        try:
            data = request_data(url)
        except HTTPError as e:
            logger.error(f'{e.__class__.__name__} {e.code} ({e.reason}) for {e.url!r}')
            return

        for commit in data:
            date_author = parse_commit(commit)
            if not date_author: continue

            commit_date, author_name = date_author
            if last_date != commit_date:
                if last_date is None:
                    # This is the very first date
                    last_date = commit_date
                else:
                    # This date is different from the last date, yield activity
                    yield RepoActivity(
                        date=last_date,
                        commits=commit_count,
                        authors=authors,
                        )
                    # Set last date to the new date, reset commit count and authors
                    last_date = commit_date
                    commit_count = 0
                    authors = set()

            commit_count += 1
            if author_name and len(author_name) <= MAX_AUTHOR_NAME_LENGTH:
                authors.add(author_name)

    # Yield activity for the remaining date
    if commit_count > 0:
        yield RepoActivity(
            date=last_date,
            commits=commit_count,
            authors=authors,
            )


__all__ = (
    'request_public_repositories',
    'request_repo',
    'request_repo_activity',
    )
