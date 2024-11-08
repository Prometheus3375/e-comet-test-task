from datetime import date
from enum import StrEnum

from pydantic import BaseModel, NonNegativeInt, PositiveInt, constr


class RepoData(BaseModel):
    """
    Model for basic repository data.
    """
    repo: constr(min_length=1)
    owner: constr(min_length=1)
    position_cur: PositiveInt
    position_prev: PositiveInt | None
    stars: NonNegativeInt
    watchers: NonNegativeInt
    forks: NonNegativeInt
    open_issues: NonNegativeInt
    language: constr(min_length=1) | None


class SortByOptions(StrEnum):
    """
    Options for sorting sequences of :class:`RepoData`.
    """
    repo = 'repository-name'
    owner = 'owner-name'
    position_cur = 'current-position'
    position_prev = 'previous-position'
    stars = 'stars-count'
    watchers = 'watchers-count'
    forks = 'forks-count'
    open_issues = 'open-issues-count'
    language = 'language'


class RepoActivity(BaseModel):
    """
    Model for repository activity.
    """
    date: date
    commits: NonNegativeInt
    authors: frozenset[constr(min_length=1)]


__all__ = 'RepoData', 'RepoActivity', 'SortByOptions'
