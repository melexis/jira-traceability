"""Utility functions for JIRA error handling and formatting"""

from jira import JIRAError
from sphinx.util.logging import getLogger

LOGGER = getLogger('mlx.jira_traceability')


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


def validate_components(jira, project_id_or_key, components):
    """Validate a list of components against a Jira project's available components.

    Attempts to use original component names first, falling back to stripped versions (removing '[' and ']').

    Args:
        jira: Jira interface object
        project_id_or_key (str): Project key or ID to validate components against
        components (list): List of component dictionaries with 'name' key

    Returns:
        list: List of valid component dictionaries, using stripped names where applicable
    """
    try:
        valid_components = jira.project_components(project_id_or_key)
        valid_component_names = [c.name for c in valid_components]
        invalid_components = []
        final_components = []
        for comp in components:
            comp_name = comp['name']
            if comp_name in valid_component_names:
                final_components.append({'name': comp_name})
            else:
                stripped_name = comp_name.strip('[]')
                if stripped_name != comp_name and stripped_name in valid_component_names:
                    final_components.append({'name': stripped_name})
                    LOGGER.info(f"Using stripped component name '{stripped_name}' instead of "
                                f"'{comp_name}' for project {project_id_or_key}")
                else:
                    invalid_components.append(comp_name)
        if invalid_components:
            LOGGER.warning(f"Invalid components found for project {project_id_or_key}: {', '.join(invalid_components)}")
        return final_components
    except JIRAError as err:
        LOGGER.warning(f"Failed to validate components: {err.text}")
        return components  # Return original components if validation fails
