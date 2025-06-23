"""Utility functions for JIRA error handling and formatting"""

from jira.exceptions import JIRAError


def format_jira_error(err):
    """Format a JIRAError into a readable error message using its attributes."""
    if isinstance(err, JIRAError):
        # Use the documented JIRAError attributes
        parts = []

        if hasattr(err, 'text') and err.text:
            parts.append(err.text)

        if hasattr(err, 'status_code') and err.status_code:
            parts.append(f"HTTP {err.status_code}")

        if hasattr(err, 'url') and err.url:
            parts.append(f"at {err.url}")

        if parts:
            return f"JIRA error: {' - '.join(parts)}"
        else:
            # Fallback to string representation if attributes are missing
            return f"JIRA error: {str(err)}"
    else:
        return f"Error: {str(err)}"
