from enum import StrEnum

from pydantic import PositiveInt

from common.models import *


class RepoDataWithRank(RepoData, frozen=True):
    """
    Model for repository data with rank information.
    """
    repo: RepoFullNameType
    position_cur: PositiveInt
    position_prev: PositiveInt | None


class SortByOptions(StrEnum):
    """
    Options for sorting sequences of :class:`RepoDataWithRank`.
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


__all__ = 'RepoDataWithRank', 'SortByOptions'
