# -*- coding: utf-8 -*-

"""Sphinx plugin to create Jira tickets based on traceable items."""

from .jira_traceability import setup

try:
    from ._version import __version__
except ImportError:
    __version__ = "unknown"

__all__ = ['setup', '__version__']
