"""
Utilities
"""
import re
from collections.abc import Iterable

__all__ = ['split']


def re_choice(items: Iterable[str]) -> str:
    """Turn items into a list of alternatives suitable for a regex pattern."""
    return r'|'.join(re.escape(i) for i in sorted(items, key=lambda ii: (-len(ii), ii)))


def split(s: str, sep: str = ';') -> list[str]:
    """Split into non-empty parts."""
    return [ss.strip() for ss in (s or '').split(sep) if ss.strip()]
