from datetime import date
from typing import TypeAlias

from pydantic import BaseModel, NonNegativeInt, PositiveInt, constr

RepoNameType: TypeAlias = constr(min_length=1, max_length=100)
UserNameType: TypeAlias = constr(min_length=1, max_length=39)
RepoFullNameType: TypeAlias = constr(min_length=1, max_length=140)
MAX_AUTHOR_NAME_LENGTH = 100


class RepoData(BaseModel, frozen=True):
    """
    Model for basic repository data.
    """
    repo: RepoNameType
    owner: UserNameType
    stars: NonNegativeInt
    watchers: NonNegativeInt
    forks: NonNegativeInt
    open_issues: NonNegativeInt
    language: constr(min_length=1, max_length=100) | None


class RepoActivity(BaseModel, frozen=True):
    """
    Model for repository activity.
    """
    date: date
    commits: PositiveInt
    # Authors are names specified in commits, not GitHub usernames
    # Can be empty if all commits at the date have no names or the name exceeds length limit
    authors: frozenset[constr(min_length=1, max_length=MAX_AUTHOR_NAME_LENGTH)]


__all__ = (
    'RepoNameType',
    'UserNameType',
    'RepoFullNameType',
    'RepoData',
    'RepoActivity',
    'MAX_AUTHOR_NAME_LENGTH',
    )
