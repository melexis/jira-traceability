from collections import namedtuple
from logging import WARNING, warning
from unittest import TestCase, mock

from jira import JIRAError

from mlx.traceable_attribute import TraceableAttribute
from mlx.traceable_collection import TraceableCollection
from mlx.traceable_item import TraceableItem
import mlx.jira_interaction as dut


@mock.patch('mlx.jira_interaction.JIRA')
class TestJiraInteraction(TestCase):
    def setUp(self):
        self.general_fields = {
            'components': [
                {'name': '[SW]'},
                {'name': '[HW]'},
            ],
            'issuetype': {'name': 'Task'},
            'project': 'MLX12345',
        }
        self.settings = {
            'api_endpoint': 'https://jira.atlassian.com/rest/api/latest/',
            'username': 'my_username',
            'password': 'my_password',
            'jira_field_id': 'summary',
            'issue_type': 'Task',
            'item_to_ticket_regex': r'ACTION-12345_ACTION_\d+',
            'project_key_regex': r'ACTION-(?P<project>\d{5})_',
            'project_key_prefix': 'MLX',
            'default_project': 'SWCC',
            'warn_if_exists': True,
            'relationship_to_parent': 'depends_on',
            'components': '[SW],[HW]',
            'catch_errors': False,
            'notify_watchers': False,
        }
        self.coll = TraceableCollection()
        parent = TraceableItem('MEETING-12345_2')
        action1 = TraceableItem('ACTION-12345_ACTION_1')
        action1.caption = 'Action 1\'s caption?'
        action1.set_content('Description for action 1')
        action2 = TraceableItem('ACTION-12345_ACTION_2')
        action2.caption = 'Caption for action 2'
        action2.set_content('')
        action3 = TraceableItem('ACTION-98765_ACTION_55')
        item1 = TraceableItem('ITEM-12345_1')

        effort_attr = TraceableAttribute('effort', r'^([\d\.]+(mo|[wdhm]) ?)+$')
        assignee_attr = TraceableAttribute('assignee', '^.*$')
        attendees_attr = TraceableAttribute('attendees', '^([A-Z]{3}[, ]*)+$')
        TraceableItem.define_attribute(effort_attr)
        TraceableItem.define_attribute(assignee_attr)
        TraceableItem.define_attribute(attendees_attr)

        parent.add_attribute('attendees', 'ABC, ZZZ')
        action1.add_attribute('effort', '2w 3d 4h 55m')
        action1.add_attribute('assignee', 'ABC')
        action2.add_attribute('assignee', 'ZZZ')
        action3.add_attribute('assignee', 'ABC')

        for item in (parent, action1, action2, action3, item1):
            self.coll.add_item(item)

        self.coll.add_relation_pair('depends_on', 'impacts_on')
        self.coll.add_relation(action1.id, 'impacts_on', item1.id)  # to be ignored
        self.coll.add_relation(action1.id, 'depends_on', parent.id)  # to be taken into account
        self.coll.add_relation(action2.id, 'impacts_on', parent.id)  # to be ignored

    def test_missing_endpoint(self, *_):
        self.settings.pop('api_endpoint')
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, None)
        self.assertEqual(
            cm.output,
            ["WARNING:sphinx.mlx.jira_interaction:Jira interaction failed: configuration is "
             "missing mandatory values for keys ['api_endpoint']"]
        )

    def test_missing_username(self, *_):
        self.settings.pop('username')
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, None)
        self.assertEqual(
            cm.output,
            ["WARNING:sphinx.mlx.jira_interaction:Jira interaction failed: configuration is "
             "missing mandatory values for keys ['username']"]
        )

    def test_missing_all_mandatory(self, *_):
        mandatory_keys = ['api_endpoint', 'username', 'password', 'item_to_ticket_regex', 'issue_type']
        for key in mandatory_keys:
            self.settings.pop(key)
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, None)
        self.assertEqual(
            cm.output,
            ["WARNING:sphinx.mlx.jira_interaction:Jira interaction failed: configuration is "
             "missing mandatory values for keys {}".format(mandatory_keys)]
        )

    def test_missing_all_optional_one_mandatory(self, *_):
        keys_to_remove = ['components', 'project_key_prefix', 'project_key_regex', 'default_project',
                          'relationship_to_parent', 'warn_if_exists', 'catch_errors', 'password']
        for key in keys_to_remove:
            self.settings.pop(key)
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, None)
        self.assertEqual(
            cm.output,
            ["WARNING:sphinx.mlx.jira_interaction:Jira interaction failed: configuration is "
             "missing mandatory values for keys ['password']"]
        )

    def test_create_jira_issues_unique(self, jira):
        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        with self.assertLogs(level=WARNING) as cm:
            warning('Dummy log')
            dut.create_jira_issues(self.settings, self.coll)

        self.assertEqual(
            cm.output,
            ['WARNING:root:Dummy log']
        )
        self.assertEqual(jira.call_args,
                         mock.call({'server': 'https://jira.atlassian.com/rest/api/latest/'},
                                   basic_auth=('my_username', 'my_password')))
        self.assertEqual(jira_mock.search_issues.call_args_list,
                         [
                             mock.call(
                                 'project=MLX12345 and summary ~ "MEETING\\\\-12345_2\\\\: Action 1\'s caption\\\\?"'),
                             mock.call("project=MLX12345 and summary ~ 'Caption for action 2'"),
                         ])

        issue = jira_mock.create_issue.return_value
        self.assertEqual(
            jira_mock.create_issue.call_args_list,
            [
                mock.call(
                    summary='MEETING-12345_2: Action 1\'s caption?',
                    description='Description for action 1',
                    assignee={'name': 'ABC'},
                    **self.general_fields
                ),
                mock.call(
                    summary='Caption for action 2',
                    description='Caption for action 2',
                    assignee={'name': 'ZZZ'},
                    **self.general_fields
                ),
            ])

        self.assertEqual(
            issue.update.call_args_list,
            [mock.call(update={'timetracking': [{"edit": {"originalEstimate": '2w 3d 4h 55m'}}]})]
        )

        # attendees added for action1 since it is linked with depends_on to parent item with ``attendees`` attribute
        self.assertEqual(jira_mock.add_watcher.call_args_list,
                         [
                             mock.call(issue, 'ABC'),
                             mock.call(issue, 'ZZZ'),
                         ])

        self.assertEqual(jira_mock.assign_issue.call_args_list, [])

    def test_notify_watchers(self, jira):
        """ Test effect of setting `notify_watchers` to True

        By default, watchers are added as the last step. When setting `notify_watchers` is set to a truthy value,
        the assignee should be set in an additional call to Jira after the watchers have been added.
        """
        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        self.settings['notify_watchers'] = True

        with self.assertLogs(level=WARNING):
            warning('Dummy log')
            dut.create_jira_issues(self.settings, self.coll)

        # No kwarg 'assignee' should be passed
        self.assertEqual(
            jira_mock.create_issue.call_args_list,
            [
                mock.call(
                    description='Description for action 1',
                    summary='MEETING-12345_2: Action 1\'s caption?',
                    **self.general_fields
                ),
                mock.call(
                    description='Caption for action 2',
                    summary='Caption for action 2',
                    **self.general_fields
                ),
            ])
        # Additional call to set assignee should be made after the issue has been created
        issue = jira_mock.create_issue.return_value
        self.assertEqual(jira_mock.assign_issue.call_args_list,
                         [
                             mock.call(issue, 'ABC'),
                             mock.call(issue, 'ZZZ'),
                         ])

    def test_create_issue_timetracking_unavailable(self, jira):
        """ Value of effort attribute should be appended to description when setting timetracking field raises error """
        def jira_update_mock(update={}, **_):
            if 'timetracking' in update:
                raise JIRAError

        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        issue = jira_mock.create_issue.return_value
        issue.update.side_effect = jira_update_mock
        dut.create_jira_issues(self.settings, self.coll)

        self.assertEqual(
            issue.update.call_args_list,
            [
                mock.call(update={'timetracking': [{"edit": {"originalEstimate": '2w 3d 4h 55m'}}]}),
                mock.call(description="Description for action 1\n\nEffort estimate: 2w 3d 4h 55m"),
            ]
        )

    def test_prevent_duplication(self, jira):
        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = ['Jira already contains this ticket']
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, self.coll)

        self.assertEqual(
            cm.output,
            ["WARNING:sphinx.mlx.jira_interaction:Won't create a Task for item "
             "'ACTION-12345_ACTION_1' because the Jira API query to check to prevent "
             "duplication returned ['Jira already contains this ticket']",
             "WARNING:sphinx.mlx.jira_interaction:Won't create a Task for item "
             "'ACTION-12345_ACTION_2' because the Jira API query to check to prevent "
             "duplication returned ['Jira already contains this ticket']"]
        )

    def test_no_warning_about_duplication(self, jira):
        """ Default behavior should be no warning when a Jira ticket doesn't get created to prevent duplication """
        self.settings.pop('warn_if_exists')
        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = ['Jira already contains this ticket']
        with self.assertLogs(level=WARNING) as cm:
            warning('Dummy log')
            dut.create_jira_issues(self.settings, self.coll)

        self.assertEqual(
            cm.output,
            ['WARNING:root:Dummy log']
        )

    def test_default_project(self, jira):
        """ The default_project should get used when project_key_regex doesn't match """
        self.settings['project_key_regex'] = 'regex_that_does_not_match_any_id'
        self.general_fields['project'] = self.settings['default_project']

        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        dut.create_jira_issues(self.settings, self.coll)

        self.assertEqual(
            jira_mock.create_issue.call_args_list,
            [
                mock.call(
                    summary='MEETING-12345_2: Action 1\'s caption?',
                    description='Description for action 1',
                    assignee={'name': 'ABC'},
                    **self.general_fields
                ),
                mock.call(
                    summary='Caption for action 2',
                    description='Caption for action 2',
                    assignee={'name': 'ZZZ'},
                    **self.general_fields
                ),
            ])

    def test_add_watcher_jira_error(self, jira):
        Response = namedtuple('Response', 'text')

        def jira_add_watcher_mock(*_):
            raise JIRAError(status_code=401, response=Response('dummy msg'))

        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        jira_mock.add_watcher.side_effect = jira_add_watcher_mock
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, self.coll)

        error_msg = ("WARNING:sphinx.mlx.jira_interaction:Jira interaction failed: item ACTION-12345_ACTION_1: "
                     "error code 401: dummy msg")
        self.assertEqual(
            cm.output,
            [error_msg, error_msg]
        )

    def test_tuple_for_relationship_to_parent(self, jira):
        """
        Tests that the linked item, added in this test case, is selected by configured tuple for
        ``relationship_to_parent``
        """
        self.settings['relationship_to_parent'] = ('depends_on', r'ZZZ-[\w_]+')
        alternative_parent = TraceableItem('ZZZ-TO_BE_PRIORITIZED')
        # to be prioritized over MEETING-12345_2
        self.coll.add_relation('ACTION-12345_ACTION_1', 'depends_on', alternative_parent.id)

        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        with self.assertLogs(level=WARNING) as cm:
            warning('Dummy log')
            dut.create_jira_issues(self.settings, self.coll)

        self.assertEqual(
            cm.output,
            ['WARNING:root:Dummy log']
        )

        self.assertEqual(jira_mock.search_issues.call_args_list,
                         [
                             mock.call("project=MLX12345 and summary ~ "
                                       '"ZZZ\\\\-TO_BE_PRIORITIZED\\\\: Action 1\'s caption\\\\?"'),
                             mock.call("project=MLX12345 and summary ~ 'Caption for action 2'"),
                         ])

        self.assertEqual(
            jira_mock.create_issue.call_args_list,
            [
                mock.call(
                    summary='ZZZ-TO_BE_PRIORITIZED: Action 1\'s caption?',
                    description='Description for action 1',
                    assignee={'name': 'ABC'},
                    **self.general_fields
                ),
                mock.call(
                    summary='Caption for action 2',
                    description='Caption for action 2',
                    assignee={'name': 'ZZZ'},
                    **self.general_fields
                ),
            ])

    def test_get_info_from_relationship_tuple(self, _):
        """ Tests dut.get_info_from_relationship with a config_for_parent parameter as tuple """
        relationship_to_parent = ('depends_on', r'ZZZ-[\w_]+')
        alternative_parent = TraceableItem('ZZZ-TO_BE_PRIORITIZED')
        # to be prioritized over MEETING-12345_2
        self.coll.add_relation('ACTION-12345_ACTION_1', 'depends_on', alternative_parent.id)
        action1 = self.coll.get_item('ACTION-12345_ACTION_1')

        attendees, jira_field = dut.get_info_from_relationship(action1, relationship_to_parent, self.coll)

        self.assertEqual(attendees, [])
        self.assertEqual(jira_field, 'ZZZ-TO_BE_PRIORITIZED: Action 1\'s caption?')

    def test_get_info_from_relationship_str(self, _):
        """ Tests dut.get_info_from_relationship with a config_for_parent parameter as str """
        relationship_to_parent = 'depends_on'
        alternative_parent = TraceableItem('ZZZ-TO_BE_IGNORED')
        # not to be prioritized over MEETING-12345_2 (natural sorting)
        self.coll.add_relation('ACTION-12345_ACTION_1', 'depends_on', alternative_parent.id)
        action1 = self.coll.get_item('ACTION-12345_ACTION_1')

        attendees, jira_field = dut.get_info_from_relationship(action1, relationship_to_parent, self.coll)

        self.assertEqual(attendees, ['ABC', ' ZZZ'])
        self.assertEqual(jira_field, 'MEETING-12345_2: Action 1\'s caption?')
