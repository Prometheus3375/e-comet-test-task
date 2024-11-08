import json
import os
from collections.abc import Iterator
from datetime import date, datetime
from http.client import HTTPResponse
from logging import getLogger
from math import ceil, inf
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
    logger.info(f'GitHub token successfully added to request headers')


def make_request(url: str, /) -> Request:
    """
    Creates request with default headers for GitHub API.
    """
    return Request(url, headers=_headers)


def request_data(url: str, /) -> Any:
    """
    Creates request with default headers for GitHub API and returns JSON data from response.
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
    except (HTTPError, ValidationError):
        logger.exception(f'Cannot request information for repository {owner}/{repo}')
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
        except HTTPError:
            logger.exception(f'Cannot request information for public repositories since {last_id}')
            # Exit immediately
            break

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


def request_repo_activity(owner: str, repo: str, /, since: date) -> Iterator[RepoActivity]:
    """
    Requests activity since the given date for the specified repository from GitHub API
    and yields :class:`RepoActivity` instances.
    """
    # Retrieve total commit count
    # https://stackoverflow.com/a/70610670/14369408
    url = (
        f'https://api.github.com/repos/{owner}/{repo}/commits'
        f'?since={since}&per_page=1'
    )
    try:
        response: HTTPResponse
        with urlopen(make_request(url)) as response:
            link = response.getheader('Link')
            _, _, number_rel = link.rpartition('page=')
            number, _, _ = number_rel.partition('>')
            commits_total = int(number)
    except HTTPError:
        logger.exception(f'Cannot request activity for repository {owner}/{repo}')
        return

    # Request commits per 100 (max) per page
    pages_count = ceil(commits_total / 100)
    # Commits are returned sorted in descending order
    last_date: date | None = None
    commit_count = 0
    authors = set()
    # date2count = Counter()
    # date2authors = defaultdict(set)
    for page in range(1, pages_count + 1):
        url = (
            f'https://api.github.com/repos/{owner}/{repo}/commits'
            f'?since={since}&per_page=100&page={page}'
        )
        # Response schema:
        # https://docs.github.com/en/rest/commits/commits?apiVersion=2022-11-28#list-commits
        try:
            data = request_data(url)
        except HTTPError:
            logger.exception(f'Cannot request activity for repository {owner}/{repo}')
            return

        for commit in data:
            commit_author = commit['commit']['author']
            if commit_author:
                commit_dt = commit_author.get('date')
                if commit_dt:
                    commit_dt = datetime.fromisoformat(commit_dt)
                    commit_date = date(commit_dt.year, commit_dt.month, commit_dt.day)
                    if last_date != commit_date:
                        if last_date is None:
                            # This is the very first date
                            last_date = commit_date
                        else:
                            # This date is different from the last date,
                            # yield activity, then reset counter and set
                            yield RepoActivity(
                                date=last_date,
                                commits=commit_count,
                                authors=authors,
                                )
                            commit_count = 0
                            authors = set()

                    commit_count += 1
                    author_name = commit_author.get('name')
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
