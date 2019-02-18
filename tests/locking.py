import unittest
import os
from time import sleep
from .helpers.ptrack_helpers import ProbackupTest, ProbackupException


module_name = 'locking'


class LockingTest(ProbackupTest, unittest.TestCase):

    # @unittest.skip("skip")
    # @unittest.expectedFailure
    def test_locking_running_validate_1(self):
        """
        make node, take full backup, stop it in the middle
        run validate, expect it to successfully executed,
        concurrect RUNNING backup with pid file and active process is legal
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'],
            pg_options={'wal_level': 'replica'})

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        self.backup_node(backup_dir, 'node', node)

        gdb = self.backup_node(
            backup_dir, 'node', node, gdb=True)

        gdb.set_breakpoint('copy_file')
        gdb.run_until_break()

        if gdb.continue_execution_until_break(20) != 'breakpoint-hit':
            self.AssertTrue(False, 'Failed to hit breakpoint')

        self.assertEqual(
            'OK', self.show_pb(backup_dir, 'node')[0]['status'])

        self.assertEqual(
            'RUNNING', self.show_pb(backup_dir, 'node')[1]['status'])

        validate_output = self.validate_pb(
            backup_dir, options=['--log-level-console=LOG'])

        backup_id = self.show_pb(backup_dir, 'node')[1]['id']

        self.assertIn(
            "is using backup {0} and still is running".format(backup_id),
            validate_output,
            '\n Unexpected Validate Output: {0}\n'.format(repr(validate_output)))

        self.assertEqual(
            'OK', self.show_pb(backup_dir, 'node')[0]['status'])

        self.assertEqual(
            'RUNNING', self.show_pb(backup_dir, 'node')[1]['status'])

        # Clean after yourself
        # self.del_test_dir(module_name, fname)

    def test_locking_running_validate_2(self):
        """
        make node, take full backup, stop it in the middle,
        kill process so no cleanup is done - pid file is in place,
        run validate, expect it to not successfully executed,
        RUNNING backup with pid file AND without active pid is legal,
        but his status must be changed to ERROR and pid file is deleted
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'],
            pg_options={'wal_level': 'replica'})

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        self.backup_node(backup_dir, 'node', node)

        gdb = self.backup_node(
            backup_dir, 'node', node, gdb=True)

        gdb.set_breakpoint('copy_file')
        gdb.run_until_break()

        if gdb.continue_execution_until_break(20) != 'breakpoint-hit':
            self.AssertTrue(False, 'Failed to hit breakpoint')

        gdb._execute('signal SIGKILL')
        gdb.continue_execution_until_error()

        self.assertEqual(
            'OK', self.show_pb(backup_dir, 'node')[0]['status'])

        self.assertEqual(
            'RUNNING', self.show_pb(backup_dir, 'node')[1]['status'])

        backup_id = self.show_pb(backup_dir, 'node')[1]['id']

        try:
            self.validate_pb(backup_dir)
            self.assertEqual(
                1, 0,
                "Expecting Error because RUNNING backup is no longer active.\n "
                "Output: {0} \n CMD: {1}".format(
                    repr(self.output), self.cmd))
        except ProbackupException as e:
            self.assertTrue(
                "which used backup {0} no longer exists".format(
                    backup_id) in e.message and
                "Backup {0} has status RUNNING, change it "
                "to ERROR and skip validation".format(
                    backup_id) in e.message and
                "WARNING: Some backups are not valid" in
                e.message,
                '\n Unexpected Error Message: {0}\n CMD: {1}'.format(
                    repr(e.message), self.cmd))

        self.assertEqual(
            'OK', self.show_pb(backup_dir, 'node')[0]['status'])

        self.assertEqual(
            'ERROR', self.show_pb(backup_dir, 'node')[1]['status'])

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    def test_locking_running_validate_2_specific_id(self):
        """
        make node, take full backup, stop it in the middle,
        kill process so no cleanup is done - pid file is in place,
        run validate on this specific backup,
        expect it to not successfully executed,
        RUNNING backup with pid file AND without active pid is legal,
        but his status must be changed to ERROR and pid file is deleted
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'],
            pg_options={'wal_level': 'replica'})

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        self.backup_node(backup_dir, 'node', node)

        gdb = self.backup_node(
            backup_dir, 'node', node, gdb=True)

        gdb.set_breakpoint('copy_file')
        gdb.run_until_break()

        if gdb.continue_execution_until_break(20) != 'breakpoint-hit':
            self.AssertTrue(False, 'Failed to hit breakpoint')

        gdb._execute('signal SIGKILL')
        gdb.continue_execution_until_error()

        self.assertEqual(
            'OK', self.show_pb(backup_dir, 'node')[0]['status'])

        self.assertEqual(
            'RUNNING', self.show_pb(backup_dir, 'node')[1]['status'])

        backup_id = self.show_pb(backup_dir, 'node')[1]['id']

        try:
            self.validate_pb(backup_dir, 'node', backup_id)
            self.assertEqual(
                1, 0,
                "Expecting Error because RUNNING backup is no longer active.\n "
                "Output: {0} \n CMD: {1}".format(
                    repr(self.output), self.cmd))
        except ProbackupException as e:
            self.assertTrue(
                "which used backup {0} no longer exists".format(
                    backup_id) in e.message and
                "Backup {0} has status RUNNING, change it "
                "to ERROR and skip validation".format(
                    backup_id) in e.message and
                "WARNING: Some backups are not valid" in
                e.message,
                '\n Unexpected Error Message: {0}\n CMD: {1}'.format(
                    repr(e.message), self.cmd))

        self.assertEqual(
            'OK', self.show_pb(backup_dir, 'node')[0]['status'])

        self.assertEqual(
            'ERROR', self.show_pb(backup_dir, 'node')[1]['status'])

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    def test_locking_running_3(self):
        """
        make node, take full backup, stop it in the middle,
        terminate process, delete pid file,
        run validate, expect it to not successfully executed,
        RUNNING backup without pid file AND without active pid is legal,
        his status must be changed to ERROR
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'],
            pg_options={'wal_level': 'replica'})

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        self.backup_node(backup_dir, 'node', node)

        gdb = self.backup_node(
            backup_dir, 'node', node, gdb=True)

        gdb.set_breakpoint('copy_file')
        gdb.run_until_break()

        if gdb.continue_execution_until_break(20) != 'breakpoint-hit':
            self.AssertTrue(False, 'Failed to hit breakpoint')

        gdb._execute('signal SIGKILL')
        gdb.continue_execution_until_error()

        self.assertEqual(
            'OK', self.show_pb(backup_dir, 'node')[0]['status'])

        self.assertEqual(
            'RUNNING', self.show_pb(backup_dir, 'node')[1]['status'])

        backup_id = self.show_pb(backup_dir, 'node')[1]['id']

        os.remove(
            os.path.join(backup_dir, 'backups', 'node', backup_id, 'backup.pid'))

        try:
            self.validate_pb(backup_dir)
            self.assertEqual(
                1, 0,
                "Expecting Error because RUNNING backup is no longer active.\n "
                "Output: {0} \n CMD: {1}".format(
                    repr(self.output), self.cmd))
        except ProbackupException as e:
            self.assertTrue(
                "Backup {0} has status RUNNING, change it "
                "to ERROR and skip validation".format(
                    backup_id) in e.message and
                "WARNING: Some backups are not valid" in
                e.message,
                '\n Unexpected Error Message: {0}\n CMD: {1}'.format(
                    repr(e.message), self.cmd))

        self.assertEqual(
            'OK', self.show_pb(backup_dir, 'node')[0]['status'])

        self.assertEqual(
            'ERROR', self.show_pb(backup_dir, 'node')[1]['status'])

        # Clean after yourself
        self.del_test_dir(module_name, fname)
