from collections import namedtuple
from logging import WARNING, warning
from unittest import TestCase, mock

from jira import JIRAError

from mlx.traceability import TraceableAttribute, TraceableCollection, TraceableItem
import mlx.jira_traceability.jira_interaction as dut


def produce_fake_users(**kwargs):
    users = []
    if kwargs.get('user') is not None:
        User = namedtuple('User', 'name')
        users.append(User(kwargs['user']))
    if kwargs.get('query') is not None:
        User = namedtuple('User', 'accountId')
        users.append(User('bf3157418d89e30046118185'))
    return users


def produce_fake_components():
    """Produce fake components for project_components mock"""
    Component = namedtuple('Component', 'name')
    return [
        Component('[SW]'),
        Component('[HW]'),
    ]


@mock.patch('mlx.jira_traceability.jira_interaction.JIRA')
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
            'api_endpoint': 'https://jira.example.com/jira',
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
        action1.content = 'Description for action 1'
        action2 = TraceableItem('ACTION-12345_ACTION_2')
        action2.caption = 'Caption for action 2'
        action2.content = ''
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
        self.coll.add_relation(action1.identifier, 'impacts_on', item1.identifier)  # to be ignored
        self.coll.add_relation(action1.identifier, 'depends_on', parent.identifier)  # to be taken into account
        self.coll.add_relation(action2.identifier, 'impacts_on', parent.identifier)  # to be ignored

    def test_missing_endpoint(self, *_):
        self.settings.pop('api_endpoint')
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, None)
        self.assertEqual(
            cm.output,
            ["WARNING:sphinx.mlx.jira_traceability:Jira interaction failed: configuration is "
             "missing mandatory values for keys ['api_endpoint']"]
        )

    def test_missing_username(self, *_):
        self.settings.pop('username')
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, None)
        self.assertEqual(
            cm.output,
            ["WARNING:sphinx.mlx.jira_traceability:Jira interaction failed: configuration is "
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
            ["WARNING:sphinx.mlx.jira_traceability:Jira interaction failed: configuration is "
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
            ["WARNING:sphinx.mlx.jira_traceability:Jira interaction failed: configuration is "
             "missing mandatory values for keys ['password']"]
        )

    def test_create_jira_issues_unique(self, jira):
        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        jira_mock.search_users.side_effect = produce_fake_users
        jira_mock.project_components.return_value = produce_fake_components()
        with self.assertLogs(level=WARNING) as cm:
            warning('Dummy log')
            dut.create_jira_issues(self.settings, self.coll)

        self.assertEqual(
            cm.output,
            ['WARNING:root:Dummy log']
        )
        self.assertEqual(jira.call_args,
                         mock.call({'server': 'https://jira.example.com/jira'},
                                   basic_auth=('my_username', 'my_password')))
        self.assertEqual(jira_mock.search_issues.call_args_list,
                         [
                             mock.call(
                                 'project=MLX12345 and summary ~ "MEETING\\\\-12345_2\\\\: Action 1\'s caption\\\\?"'),
                             mock.call("project=MLX12345 and summary ~ 'Caption for action 2'"),
                         ])

        issue = jira_mock.create_issue.return_value
        out = jira_mock.create_issue.call_args_list
        ref = [
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
            ]
        self.assertEqual(out, ref)

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
        jira_mock.project_components.return_value = produce_fake_components()
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
        jira_mock.project_components.return_value = produce_fake_components()
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
        jira_mock.project_components.return_value = produce_fake_components()
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, self.coll)

        self.assertEqual(
            cm.output,
            ["WARNING:sphinx.mlx.jira_traceability:Won't create a Task for item "
             "'ACTION-12345_ACTION_1' because the Jira API query to check to prevent "
             "duplication returned ['Jira already contains this ticket']",
             "WARNING:sphinx.mlx.jira_traceability:Won't create a Task for item "
             "'ACTION-12345_ACTION_2' because the Jira API query to check to prevent "
             "duplication returned ['Jira already contains this ticket']"]
        )

    def test_no_warning_about_duplication(self, jira):
        """ Default behavior should be no warning when a Jira ticket doesn't get created to prevent duplication """
        self.settings.pop('warn_if_exists')
        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = ['Jira already contains this ticket']
        jira_mock.project_components.return_value = produce_fake_components()
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
        jira_mock.search_users.side_effect = produce_fake_users
        jira_mock.project_components.return_value = produce_fake_components()
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
        self.maxDiff = None

        def jira_add_watcher_mock(*_):
            raise JIRAError(status_code=401, text='dummy msg')

        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        jira_mock.add_watcher.side_effect = jira_add_watcher_mock
        jira_mock.search_users.side_effect = produce_fake_users
        jira_mock.project_components.return_value = produce_fake_components()
        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, self.coll)

        issue = jira_mock.create_issue.return_value
        error_msg_abc = (f"WARNING:sphinx.mlx.jira_traceability:Could not add watcher ABC to issue "
                         f"{issue.key}: dummy msg")
        error_msg_zzz = (f"WARNING:sphinx.mlx.jira_traceability:Could not add watcher ZZZ to issue "
                         f"{issue.key}: dummy msg")
        self.assertEqual(
            cm.output,
            [error_msg_abc, error_msg_zzz]
        )

    def test_tuple_for_relationship_to_parent(self, jira):
        """
        Tests that the linked item, added in this test case, is selected by configured tuple for
        ``relationship_to_parent``
        """
        self.settings['relationship_to_parent'] = ('depends_on', r'ZZZ-[\w_]+')
        alternative_parent = TraceableItem('ZZZ-TO_BE_PRIORITIZED')
        # to be prioritized over MEETING-12345_2
        self.coll.add_relation('ACTION-12345_ACTION_1', 'depends_on', alternative_parent.identifier)

        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        jira_mock.search_users.side_effect = produce_fake_users
        jira_mock.project_components.return_value = produce_fake_components()
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
        self.coll.add_relation('ACTION-12345_ACTION_1', 'depends_on', alternative_parent.identifier)
        action1 = self.coll.get_item('ACTION-12345_ACTION_1')

        attendees, jira_field = dut.get_info_from_relationship(action1, relationship_to_parent, self.coll)

        self.assertEqual(attendees, [])
        self.assertEqual(jira_field, 'ZZZ-TO_BE_PRIORITIZED: Action 1\'s caption?')

    def test_get_info_from_relationship_str(self, _):
        """ Tests dut.get_info_from_relationship with a config_for_parent parameter as str """
        relationship_to_parent = 'depends_on'
        alternative_parent = TraceableItem('ZZZ-TO_BE_IGNORED')
        # not to be prioritized over MEETING-12345_2 (natural sorting)
        self.coll.add_relation('ACTION-12345_ACTION_1', 'depends_on', alternative_parent.identifier)
        action1 = self.coll.get_item('ACTION-12345_ACTION_1')

        attendees, jira_field = dut.get_info_from_relationship(action1, relationship_to_parent, self.coll)

        self.assertEqual(attendees, ['ABC', 'ZZZ'])
        self.assertEqual(jira_field, 'MEETING-12345_2: Action 1\'s caption?')

    def test_component_stripping(self, jira):
        """ Test that component names get stripped of square brackets when the original doesn't exist """
        def produce_stripped_components():
            Component = namedtuple('Component', 'name')
            return [
                Component('SW'),  # Note: no brackets
                Component('HW'),  # Note: no brackets
            ]

        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        jira_mock.search_users.side_effect = produce_fake_users
        jira_mock.project_components.return_value = produce_stripped_components()

        # Use INFO level to capture the stripped component messages
        with self.assertLogs(level='INFO') as cm:
            dut.create_jira_issues(self.settings, self.coll)

        # Check that info messages about component stripping are logged
        stripped_logs = [log for log in cm.output if 'Using stripped component name' in log]
        self.assertEqual(len(stripped_logs), 2)  # Should have 2 stripped components

        # Check that the create_issue calls use the stripped component names
        out = jira_mock.create_issue.call_args_list

        # Expected components should be stripped
        expected_general_fields = self.general_fields.copy()
        expected_general_fields['components'] = [{'name': 'SW'}, {'name': 'HW'}]

        ref = [
            mock.call(
                summary='MEETING-12345_2: Action 1\'s caption?',
                description='Description for action 1',
                assignee={'name': 'ABC'},
                **expected_general_fields
            ),
            mock.call(
                summary='Caption for action 2',
                description='Caption for action 2',
                assignee={'name': 'ZZZ'},
                **expected_general_fields
            ),
        ]
        self.assertEqual(out, ref)

    def test_invalid_components_warning(self, jira):
        """ Test that invalid components generate warnings """
        def produce_different_components():
            Component = namedtuple('Component', 'name')
            return [
                Component('DOCS'),  # Different component names
                Component('QA'),
            ]

        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        jira_mock.search_users.side_effect = produce_fake_users
        jira_mock.project_components.return_value = produce_different_components()

        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, self.coll)

        # Check that warning about invalid components is logged
        # With caching optimization, validation happens once per project
        invalid_component_logs = [log for log in cm.output if 'Invalid components found' in log]
        self.assertEqual(len(invalid_component_logs), 1)  # Should warn once per project

        # Verify the warning message contains the invalid component names
        self.assertIn('[SW], [HW]', invalid_component_logs[0])

    def test_component_validation_failure(self, jira):
        """ Test that component validation failure falls back to original components """
        def jira_project_components_error(*_):
            raise JIRAError(status_code=404, text='Project not found')

        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        jira_mock.search_users.side_effect = produce_fake_users
        jira_mock.project_components.side_effect = jira_project_components_error

        with self.assertLogs(level=WARNING) as cm:
            dut.create_jira_issues(self.settings, self.coll)

        # Check that warning about validation failure is logged
        # With caching optimization, validation happens once per project
        validation_failure_logs = [log for log in cm.output if 'Failed to validate components' in log]
        self.assertEqual(len(validation_failure_logs), 1)  # Should warn once per project

        # Check that the create_issue calls use the original component names (fallback behavior)
        out = jira_mock.create_issue.call_args_list
        ref = [
            mock.call(
                summary='MEETING-12345_2: Action 1\'s caption?',
                description='Description for action 1',
                assignee={'name': 'ABC'},
                **self.general_fields  # Original components should be used
            ),
            mock.call(
                summary='Caption for action 2',
                description='Caption for action 2',
                assignee={'name': 'ZZZ'},
                **self.general_fields  # Original components should be used
            ),
        ]
        self.assertEqual(out, ref)

    def test_component_validation_caching(self, jira):
        """ Test that component validation is cached per project """
        jira_mock = jira.return_value
        jira_mock.search_issues.return_value = []
        jira_mock.search_users.side_effect = produce_fake_users
        jira_mock.project_components.return_value = produce_fake_components()

        dut.create_jira_issues(self.settings, self.coll)

        # Verify that project_components was called only once (cached for subsequent items)
        self.assertEqual(jira_mock.project_components.call_count, 1)

        # Verify it was called with the correct project
        jira_mock.project_components.assert_called_with('MLX12345')
