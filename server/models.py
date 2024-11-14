from collections.abc import Callable
from enum import Enum
from operator import attrgetter
from typing import Any

from pydantic import PositiveInt

from common.models import *


class RepoDataWithRank(RepoData, frozen=True):
    """
    Model for repository data with rank information.
    """
    repo: RepoFullNameType
    position_cur: PositiveInt
    position_prev: PositiveInt | None


class SortByOptions(Enum):
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

    @property
    def sort_key(self, /) -> Callable[[Any], Any]:
        """
        The key function for sorting by this option.
        """
        return _sort_options_to_key[self]


_sort_options_to_key: dict[SortByOptions, Callable[[Any], Any]] = {
    option: attrgetter(option.name)
    for option in SortByOptions
    }
# Define special cases for nullable fields
_sort_options_to_key[SortByOptions.position_prev] = \
    lambda x: -1 if x.position_prev is None else x.position_prev

_sort_options_to_key[SortByOptions.language] = lambda x: x.language or ''

__all__ = 'RepoDataWithRank', 'SortByOptions'
