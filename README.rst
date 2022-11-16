.. image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
    :target: https://opensource.org/licenses/Apache-2.0
    :alt: Apache 2.0 License

.. image:: https://badge.fury.io/py/mlx.jira-traceability.svg
    :target: https://badge.fury.io/py/mlx.jira-traceability
    :alt: PyPI packaged release

.. image:: https://github.com/melexis/jira-traceability/actions/workflows/python-package.yml/badge.svg?branch=main
    :target: https://github.com/melexis/jira-traceability/actions/workflows/python-package.yml
    :alt: Build status

.. image:: https://img.shields.io/badge/contributions-welcome-brightgreen.svg
    :target: https://github.com/melexis/jira-traceability/issues
    :alt: Contributions welcome

============
Introduction
============

Sphinx plugin for creating Jira tickets based on traceable items that have been added by
`mlx.traceability <https://pypi.org/project/mlx.traceability/>`_. You can look at this module as an extension for
mlx.traceability.

=====
Usage
=====

--------------------
Jira Ticket Creation
--------------------

Jira tickets that are based on traceable items can be automatically created by the plugin. A ticket gets created only
for each item of which its ID **matches** the configured regular expression ``item_to_ticket_regex``.
Duplication of tickets is avoided by querying Jira first for existing tickets based on the Jira project and the
value of the ticket field configured by ``jira_field_id``. Below is an example configuration:

Configuration
=============

.. code-block:: python

    extensions = [
        'mlx.traceability',
        'mlx.jira_traceability',
    ]

    traceability_jira_automation = {
        'api_endpoint': 'https://example.atlassian.com',
        'username': 'abc@example.com',
        'password': 'my_api_token',
        'item_to_ticket_regex': r'ACTION-12345_ACTION_\d+',
        'jira_field_id': 'summary',
        'issue_type': 'Task',
        'project_key_regex': r'ACTION-(?P<project>\d{5})_',
        'project_key_prefix': 'MLX',  # MLX12345 for example
        'default_project': 'SWCC',
        'relationship_to_parent': ('depends_on', r'MEETING-[\w_]+'),
        'components': '[SW],[HW]',
        'description_head': 'Action raised in [this meeting|https://docserver.com/<<file_name>>.html].\n\n',
        'description_str_to_attr': {'<<file_name>>': 'docname'},
        'warn_if_exists': False,
        'errors_to_warnings': True,
        'notify_watchers': False,
    }

Jira Configuration
------------------

Jira Server
^^^^^^^^^^^

:api_endpoint: ``https://jira.example.com/jira``
:username: ``abc``
:password: ``my_password``


Jira Cloud
^^^^^^^^^^

:api_endpoint: ``https://example.atlassian.com``
:username: ``abc@example.com``
:password: ``my_api_token``

Plugin Configuration
--------------------

``project_key_regex`` can optionally be defined. This regular expression with a named group *project* is used to
extract a certain part of the item ID to determine the Jira project key. ``project_key_prefix`` can optionally be
defined to add a prefix to the match for ``project_key_regex``. Additionally, ``default_project`` defines the Jira
project key or id in case the regular expression doesn't come up with a match or hasn't been configured.

``item_to_ticket_regex`` defines the regular expression used to filter item IDs to be exported as Jira tickets.
A warning gets reported when a Jira ticket already exists. These warnings can be disabled by setting
``warn_if_exists`` to ``True``. Errors raised by Jira are converted to warnings by default. If you want these errors to
crash your build, you can set ``errors_to_warnings`` to a falsy value.

The item ID of a linked item can be added to the summary of the Jira ticket to create by specifying the relationship
to this item in the value for setting ``relationship_to_parent``. The value can be a list or tuple with the relationship
as the first element and the regular expression to match the linked item's ID as the second element.
This feature makes it possible to create a query link in advance to list all Jira tickets that are related to this
linked item.

A string can be added to the start of a ticket's description by configuring ``description_head``. If the item to create
a ticket for does not have a body, its caption will be used to build the ticket's description.

Watchers of a ticket can be notified about the creation of the ticket by setting ``notify_watchers`` to ``True``.
Note that this notification is only sent when the user to assign to the ticket is different from the default assignee
configured in Jira.

Attributes
==========

All attributes are optional and are defined in `the default configuration of mlx.traceability
<https://melexis.github.io/sphinx-traceability-extension/configuration.html#default-config>`_.

- *assignee* is used to assign a username to the Jira ticket.
- *effort* is used to set the original effort estimation field. On failure, it gets appended to the description field.

If the item for which to create a ticket has an item linked to it by a ``relationship_to_parent`` relationship,
the *attendees* attribute of this linked item should be a comma-separated list of usernames that get added as watchers
to the ticket.

Mapping of Strings to Item Attributes (advanced)
================================================

If you want to use the value of an attribute of a TraceableItem in the string value for the
``description_head`` setting, you can set the ``description_str_to_attr`` setting to a dictionary mapping the string you
want to have replaced to the attribute of the ``TraceableItem`` that should take its place. In the following example,
some placeholder text will get replaced by the document name the item is located in:

.. code-block:: python

    'description_head': 'Action raised in [this meeting|https://docserver.com/<<file_name>>.html].\n\n',
    'description_str_to_attr': {'<<file_name>>': 'docname'}
