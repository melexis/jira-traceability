"""Utility functions for JIRA error handling and formatting"""

import json
from jira.resilientsession import parse_errors


def format_jira_error(err):
    """Format a JIRAError for better error reporting.

    Args:
        err (JIRAError): The JIRA error to format

    Returns:
        str: Formatted error message
    """
    try:
        # Use parse_errors to get a proper error message from the response
        if hasattr(err, 'response') and err.response is not None:
            error_messages = parse_errors(err.response)
            if error_messages:
                status_code = getattr(err, 'status_code', 'unknown')
                return f"JIRA API error (HTTP {status_code}): {'; '.join(error_messages)}"

        # Try to extract detailed error information from response text
        status_code = getattr(err, 'status_code', 'unknown')
        url = getattr(err, 'url', 'unknown URL')

        if hasattr(err, 'response') and err.response is not None:
            try:
                # Try to parse JSON error response
                response_text = getattr(err.response, 'text', '')
                if response_text:
                    error_data = json.loads(response_text)
                    error_parts = []

                    # Extract error messages
                    if 'errorMessages' in error_data and error_data['errorMessages']:
                        error_parts.extend(error_data['errorMessages'])

                    # Extract field-specific errors
                    if 'errors' in error_data and error_data['errors']:
                        for field, message in error_data['errors'].items():
                            error_parts.append(f"{field}: {message}")

                    if error_parts:
                        return f"JIRA API error (HTTP {status_code}): {'; '.join(error_parts)}"
                    else:
                        return f"JIRA API error (HTTP {status_code}) at {url}: {response_text}"
                else:
                    return f"JIRA API error (HTTP {status_code}) at {url}: no error description"
            except (json.JSONDecodeError, AttributeError):
                # Fallback to basic error text
                error_text = getattr(err.response, 'text', 'no error description')
                return f"JIRA API error (HTTP {status_code}) at {url}: {error_text}"
        else:
            return f"JIRA API error (HTTP {status_code}) at {url}: no response available"

    except Exception:
        # If anything goes wrong with error formatting, fall back to string representation
        return str(err)
