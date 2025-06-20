# -*- coding: utf-8 -*-

"""Sphinx plugin to create Jira tickets based on traceable items."""

from .jira_traceability import setup, jira_interaction, perform_consistency_check
from .jira_interaction import create_jira_issues, fetch_user

try:
    from ._version import __version__
except ImportError:
    __version__ = "unknown"

__all__ = ['setup', 'jira_interaction', 'perform_consistency_check', 'create_jira_issues', 'fetch_user', '__version__']
