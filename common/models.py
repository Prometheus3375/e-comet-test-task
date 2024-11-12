from datetime import date
from typing import Annotated

from pydantic import BaseModel, NonNegativeInt, PositiveInt, StringConstraints

NonEmptyStringUpTo100 = Annotated[str, StringConstraints(min_length=1, max_length=100)]
RepoNameType = NonEmptyStringUpTo100
UserNameType = Annotated[str, StringConstraints(min_length=1, max_length=39)]
RepoFullNameType = Annotated[str, StringConstraints(min_length=1, max_length=140)]
CommitAuthorNameType = NonEmptyStringUpTo100


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
    language: NonEmptyStringUpTo100 | None


class RepoActivity(BaseModel, frozen=True):
    """
    Model for repository activity.
    """
    date: date
    commits: PositiveInt
    # Authors are names specified in commits, not GitHub usernames
    # Can be empty if all commits at the date have no names or the name exceeds length limit
    authors: frozenset[CommitAuthorNameType]


__all__ = (
    'RepoNameType',
    'UserNameType',
    'RepoFullNameType',
    'CommitAuthorNameType',
    'RepoData',
    'RepoActivity',
    )
