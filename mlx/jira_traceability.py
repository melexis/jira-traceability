from sphinx.util.logging import getLogger

from .jira_interaction import create_jira_issues

LOGGER = getLogger(__name__)


def jira_interaction(app):
    """ Execute the functionality that creates Jira tickets based on traceable items.

    Args:
        app: Sphinx application object to use.
    """
    try:
        create_jira_issues(app.config.traceability_jira_automation, app.builder.env.traceability_collection)
    except Exception as err:  # pylint: disable=broad-except
        if app.config.traceability_jira_automation.get('errors_to_warnings', True):
            LOGGER.warning("Jira interaction failed: {}".format(err))
        else:
            raise err


def perform_consistency_check(app, doctree):
    """Consistency checker callback"""
    if app.config.traceability_jira_automation:
        jira_interaction(app)


# -----------------------------------------------------------------------------
# Extension setup
def setup(app):
    # Configuration for automated issue creation in JIRA
    app.add_config_value('traceability_jira_automation', {}, 'env')

    app.connect('env-check-consistency', perform_consistency_check)
