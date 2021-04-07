"""Functionality to interact with Jira"""
from re import match, search

from jira import JIRA, JIRAError
from sphinx.util.logging import getLogger

LOGGER = getLogger(__name__)


def create_jira_issues(settings, traceability_collection):
    """ Creates Jira issues using configuration variable ``traceability_jira_automation``.

    Args:
        settings (dict): Settings relevant to this feature
        traceability_collection (TraceableCollection): Collection of all traceability items
    """
    mandatory_keys = ('api_endpoint', 'username', 'password', 'jira_field_id', 'item_to_ticket_regex', 'issue_type')
    missing_keys = []
    for key in mandatory_keys:
        if not settings.get(key, None):
            missing_keys.append(key)
    if missing_keys:
        return LOGGER.warning("Jira interaction failed: configuration is missing mandatory values for keys {}"
                              .format(missing_keys))

    issue_type = settings['issue_type']
    general_fields = {}
    general_fields['issuetype'] = {'name': issue_type}
    components = []
    for comp in settings.get('components', '').split(','):
        if comp:
            components.append({'name': comp.strip()})
    if components:
        general_fields['components'] = components

    relevant_item_ids = traceability_collection.get_items(settings['item_to_ticket_regex'])
    if relevant_item_ids:
        jira = JIRA({"server": settings['api_endpoint']}, basic_auth=(settings['username'], settings['password']))
        create_unique_issues(relevant_item_ids, jira, general_fields, settings, traceability_collection)


def create_unique_issues(item_ids, jira, general_fields, settings, traceability_collection):
    """ Creates a Jira ticket for each item matching the configured regex.

    Duplication is avoided by first querying Jira issues filtering on project and summary.

    Args:
        item_ids (list): List of item IDs
        jira (jira.JIRA): Jira interface object
        general_fields (dict): Dictionary containing fields that are not item-specific
        settings (dict): Configuration for this feature
        traceability_collection (TraceableCollection): Collection of all traceability items
    """
    for item_id in item_ids:
        fields = {}
        item = traceability_collection.get_item(item_id)
        project_id_or_key = determine_jira_project(settings.get('project_key_regex', ''),
                                                   settings.get('project_key_prefix', ''),
                                                   settings.get('default_project', ''),
                                                   item_id)
        if not project_id_or_key:
            LOGGER.warning("Could not determine a JIRA project key or id for item {!r}".format(item_id))
            continue

        assignee = item.get_attribute('assignee')
        attendees, jira_field = get_info_from_relationship(item, settings['relationship_to_parent'],
                                                           traceability_collection)

        jira_field_id = settings['jira_field_id']
        jira_field_query_value = escape_special_characters(jira_field)
        matches = jira.search_issues("project={} and {} ~ '{}'".format(project_id_or_key,
                                                                       jira_field_id,
                                                                       jira_field_query_value))
        if matches:
            if settings.get('warn_if_exists', False):
                LOGGER.warning("Won't create a {} for item {!r} because the Jira API query to check to prevent "
                               "duplication returned {}".format(general_fields['issuetype']['name'], item_id, matches))
            continue

        fields['project'] = project_id_or_key
        fields[jira_field_id] = jira_field
        body = item.get_content()
        if not body:
            body = item.caption

        description = settings.get('description_head', '') + body
        for str_to_replace, attr_name in settings.get('description_str_to_attr', {}).items():
            attribute = getattr(item, attr_name)
            description = description.replace(str(str_to_replace), str(attribute))
        fields['description'] = description

        if assignee and not settings.get('notify_watchers', False):
            fields['assignee'] = {'name': item.get_attribute('assignee')}
            assignee = ''

        issue = push_item_to_jira(jira, {**fields, **general_fields}, item, attendees, assignee)
        print("mlx.jira-traceability: created Jira ticket for item {} here: {}".format(item_id, issue.permalink()))


def push_item_to_jira(jira, fields, item, attendees, assignee):
    """ Pushes the request to create a ticket on Jira for the given item.

    The value of the effort option gets added to the Estimated field of the time tracking section. On failure, it gets
    appended to the description instead.
    The attendees are added to the watchers field. A warning is raised for each error returned by Jira.
    The assignee can be set as the last step. When this results in a change in the ticket, the watchers get notified.

    Args:
        jira (jira.JIRA): Jira interface object
        general_fields (dict): Dictionary containing all fields to include in the initial creation of the Jira ticket
        item (TraceableItem): Traceable item to create the Jira ticket for
        attendees (list): List of attendees that should get added to the watchers field
        assignee (str): User to assign to the issue as a last and separate call to Jira; empty to skip this step

    Returns:
        jira.resources.Issue: newly created Jira issue
    """
    issue = jira.create_issue(**fields)

    effort = item.get_attribute('effort')
    if effort:
        try:
            issue.update(update={"timetracking": [{"edit": {"originalEstimate": effort}}]})
        except JIRAError:
            issue.update(description="{}\n\nEffort estimate: {}".format(item.get_content(), effort))

    for attendee in attendees:
        try:
            jira.add_watcher(issue, attendee.strip())
        except JIRAError as err:
            LOGGER.warning("Jira interaction failed: item {}: error code {}: {}"
                           .format(item.id, err.status_code, err.response.text))

    if assignee:
        jira.assign_issue(issue, assignee)
    return issue


def determine_jira_project(key_regex, key_prefix, default_project, item_id):
    """ Determines the JIRA project key or id to use for give item ID.

    Args:
        key_regex (str): Regular expression used to scan through the <<item_id>>. In case of a hit, the capture group
            with name 'project' will be used to build the project key.
        key_prefix (str): Prefix to use if <<key_regex>> gets used to build the project key.
        default_project (str): Project key or id to use if a match for <<key_regex>> doesn't get used.

    Returns:
        str: JIRA project key or id.
    """
    key_match = search(key_regex, item_id)
    try:
        return key_prefix + key_match.group('project')
    except (AttributeError, IndexError):
        return default_project


def get_info_from_relationship(item, config_for_parent, traceability_collection):
    """ Gets info from the first item with the given relationship.

    Its id is added to the jira field and if it has the 'attendees' attribute, its value is returned as a list.

    Args:
        item (TraceableItem): Traceable item to create the Jira ticket for
        config_for_parent (str/tuple/list): Relationship to the item to extract info from / tuple or list with
            relationship as the first element and regex to match ID of parent item as the second element
        traceability_collection (TraceableCollection): Collection of all traceability items

    Returns:
        list: List of attendees (str)
        str: Contents for field with id jira_field_id
    """
    attendees = []
    jira_field = item.caption
    if config_for_parent:
        if isinstance(config_for_parent, (tuple, list)):
            relationship = config_for_parent[0]
            parent_regex = config_for_parent[1]
        else:
            relationship = config_for_parent
            parent_regex = '.+'
        parent_ids = item.iter_targets(relationship)
        parent_id = None
        for id_ in parent_ids:
            if match(parent_regex, id_):
                parent_id = id_
                break
        if parent_id:
            parent = traceability_collection.get_item(parent_id)
            jira_field = "{id}: {field}".format(id=parent_id, field=jira_field)  # prepend item ID of parent
            attr_value = parent.get_attribute('attendees')
            if attr_value:
                attendees = attr_value.split(',')
    return attendees, jira_field


def escape_special_characters(input_string):
    """ Escape special characters to avoid unwanted behavior.

    Note that they are not stored in the index so you cannot search for them.

    Args:
        input_string (str): String to escape special characters of

    Returns:
        str: Input string that has its special characters escaped
    """
    prepared_string = input_string
    for special_char in ("\\", "+", "-", "&", "|", "!", "(", ")", "{", "}", "[", "]", "^", "~", "*", "?", ":"):
        if special_char in prepared_string:
            prepared_string = prepared_string.replace(special_char, "\\" + special_char)
    return prepared_string
