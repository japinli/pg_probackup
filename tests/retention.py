import os
import unittest
from datetime import datetime, timedelta
from .helpers.ptrack_helpers import ProbackupTest, ProbackupException
from time import sleep
from distutils.dir_util import copy_tree


module_name = 'retention'


class RetentionTest(ProbackupTest, unittest.TestCase):

    # @unittest.skip("skip")
    # @unittest.expectedFailure
    def test_retention_redundancy_1(self):
        """purge backups using redundancy-based retention policy"""
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        self.set_config(
            backup_dir, 'node', options=['--retention-redundancy=1'])

        # Make backups to be purged
        self.backup_node(backup_dir, 'node', node)
        self.backup_node(backup_dir, 'node', node, backup_type="page")
        # Make backups to be keeped
        self.backup_node(backup_dir, 'node', node)
        self.backup_node(backup_dir, 'node', node, backup_type="page")

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 4)

        output_before = self.show_archive(backup_dir, 'node', tli=1)

        # Purge backups
        log = self.delete_expired(
            backup_dir, 'node', options=['--expired', '--wal'])
        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 2)

        output_after = self.show_archive(backup_dir, 'node', tli=1)

        self.assertEqual(
            output_before['max-segno'],
            output_after['max-segno'])

        self.assertNotEqual(
            output_before['min-segno'],
            output_after['min-segno'])

        # Check that WAL segments were deleted
        min_wal = output_after['min-segno']
        max_wal = output_after['max-segno']

        for wal_name in os.listdir(os.path.join(backup_dir, 'wal', 'node')):
            if not wal_name.endswith(".backup"):

                if self.archive_compress:
                    wal_name = wal_name[-19:]
                    wal_name = wal_name[:-3]
                else:
                    wal_name = wal_name[-16:]

                self.assertTrue(wal_name >= min_wal)
                self.assertTrue(wal_name <= max_wal)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_retention_window_2(self):
        """purge backups using window-based retention policy"""
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        with open(
            os.path.join(
                backup_dir,
                'backups',
                'node',
                "pg_probackup.conf"), "a") as conf:
            conf.write("retention-redundancy = 1\n")
            conf.write("retention-window = 1\n")

        # Make backups to be purged
        self.backup_node(backup_dir, 'node', node)
        self.backup_node(backup_dir, 'node', node, backup_type="page")
        # Make backup to be keeped
        self.backup_node(backup_dir, 'node', node)

        backups = os.path.join(backup_dir, 'backups', 'node')
        days_delta = 5
        for backup in os.listdir(backups):
            if backup == 'pg_probackup.conf':
                continue
            with open(
                    os.path.join(
                        backups, backup, "backup.control"), "a") as conf:
                conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                    datetime.now() - timedelta(days=days_delta)))
                days_delta -= 1

        # Make backup to be keeped
        self.backup_node(backup_dir, 'node', node, backup_type="page")

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 4)

        # Purge backups
        self.delete_expired(backup_dir, 'node', options=['--expired'])
        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 2)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_retention_window_3(self):
        """purge all backups using window-based retention policy"""
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # take FULL BACKUP
        backup_id_1 = self.backup_node(backup_dir, 'node', node)

        # Take second FULL BACKUP
        backup_id_2 = self.backup_node(backup_dir, 'node', node)

        # Take third FULL BACKUP
        backup_id_3 = self.backup_node(backup_dir, 'node', node)

        backups = os.path.join(backup_dir, 'backups', 'node')
        for backup in os.listdir(backups):
            if backup == 'pg_probackup.conf':
                continue
            with open(
                    os.path.join(
                        backups, backup, "backup.control"), "a") as conf:
                conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                    datetime.now() - timedelta(days=3)))

        # Purge backups
        self.delete_expired(
            backup_dir, 'node', options=['--retention-window=1', '--expired'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 0)

        print(self.show_pb(
            backup_dir, 'node', as_json=False, as_text=True))

        # count wal files in ARCHIVE

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_retention_window_4(self):
        """purge all backups using window-based retention policy"""
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # take FULL BACKUPs
        backup_id_1 = self.backup_node(backup_dir, 'node', node)

        backup_id_2 = self.backup_node(backup_dir, 'node', node)

        backup_id_3 = self.backup_node(backup_dir, 'node', node)

        backups = os.path.join(backup_dir, 'backups', 'node')
        for backup in os.listdir(backups):
            if backup == 'pg_probackup.conf':
                continue
            with open(
                    os.path.join(
                        backups, backup, "backup.control"), "a") as conf:
                conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                    datetime.now() - timedelta(days=3)))

        self.delete_pb(backup_dir, 'node', backup_id_2)
        self.delete_pb(backup_dir, 'node', backup_id_3)

        # Purge backups
        self.delete_expired(
            backup_dir, 'node',
            options=['--retention-window=1', '--expired', '--wal'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 0)

        print(self.show_pb(
            backup_dir, 'node', as_json=False, as_text=True))

        # count wal files in ARCHIVE
        wals_dir = os.path.join(backup_dir, 'wal', 'node')
        # n_wals = len(os.listdir(wals_dir))

        # self.assertTrue(n_wals > 0)

        # self.delete_expired(
        #     backup_dir, 'node',
        #     options=['--retention-window=1', '--expired', '--wal'])

        # count again
        n_wals = len(os.listdir(wals_dir))
        self.assertTrue(n_wals == 0)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_window_expire_interleaved_incremental_chains(self):
        """complicated case of interleaved backup chains"""
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # take FULL BACKUPs
        backup_id_a = self.backup_node(backup_dir, 'node', node)
        backup_id_b = self.backup_node(backup_dir, 'node', node)

        # Change FULLb backup status to ERROR
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        # FULLb  ERROR
        # FULLa  OK

        # Take PAGEa1 backup
        page_id_a1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        # Change FULLb backup status to OK
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        # Change PAGEa1 and FULLa to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'ERROR')

        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  ERROR

        page_id_b1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEb1 OK
        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  ERROR

        # Now we start to play with first generation of PAGE backups
        # Change PAGEb1 and FULLb to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        # Change PAGEa1 and FULLa to OK
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'OK')

        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        page_id_a2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEa2 OK
        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        # Change PAGEa2 and FULLa to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a2, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'ERROR')

        # Change PAGEb1 and FULLb to OK
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        # PAGEa2 ERROR
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  ERROR

        page_id_b2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # Change PAGEa2 and FULla to OK
        self.change_backup_status(backup_dir, 'node', page_id_a2, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'OK')

        # PAGEb2 OK
        # PAGEa2 OK
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  OK

        # Purge backups
        backups = os.path.join(backup_dir, 'backups', 'node')
        for backup in os.listdir(backups):
            if backup not in [page_id_a2, page_id_b2, 'pg_probackup.conf']:
                with open(
                        os.path.join(
                            backups, backup, "backup.control"), "a") as conf:
                    conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                        datetime.now() - timedelta(days=3)))

        self.delete_expired(
            backup_dir, 'node',
            options=['--retention-window=1', '--expired'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 6)

        print(self.show_pb(
            backup_dir, 'node', as_json=False, as_text=True))

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_redundancy_expire_interleaved_incremental_chains(self):
        """complicated case of interleaved backup chains"""
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # take FULL BACKUPs
        backup_id_a = self.backup_node(backup_dir, 'node', node)
        backup_id_b = self.backup_node(backup_dir, 'node', node)

        # Change FULL B backup status to ERROR
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        # FULLb  ERROR
        # FULLa  OK
        # Take PAGEa1 backup
        page_id_a1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        # Change FULLb backup status to OK
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        # Change PAGEa1 and FULLa backup status to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'ERROR')

        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  ERROR

        page_id_b1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEb1 OK
        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  ERROR

        # Now we start to play with first generation of PAGE backups
        # Change PAGEb1 status to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        # Change PAGEa1 status to OK
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'OK')

        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK
        page_id_a2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEa2 OK
        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        # Change PAGEa2 and FULLa status to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a2, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'ERROR')

        # Change PAGEb1 and FULLb status to OK
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        # PAGEa2 ERROR
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  ERROR
        page_id_b2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # Change PAGEa2 and FULLa status to OK
        self.change_backup_status(backup_dir, 'node', page_id_a2, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'OK')

        # PAGEb2 OK
        # PAGEa2 OK
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  OK

        self.delete_expired(
            backup_dir, 'node',
            options=['--retention-redundancy=1', '--expired'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 3)

        print(self.show_pb(
            backup_dir, 'node', as_json=False, as_text=True))

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_window_merge_interleaved_incremental_chains(self):
        """complicated case of interleaved backup chains"""
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # Take FULL BACKUPs
        backup_id_a = self.backup_node(backup_dir, 'node', node)
        backup_id_b = self.backup_node(backup_dir, 'node', node)

        # Change FULLb backup status to ERROR
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        # FULLb  ERROR
        # FULLa  OK

        # Take PAGEa1 backup
        page_id_a1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        # Change FULLb to OK
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        # Change PAGEa1 backup status to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'ERROR')

        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  OK

        page_id_b1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEb1 OK
        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  OK

        # Now we start to play with first generation of PAGE backups
        # Change PAGEb1 and FULLb to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        # Change PAGEa1 to OK
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'OK')

        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        page_id_a2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEa2 OK
        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        # Change PAGEa2 and FULLa to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a2, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'ERROR')

        # Change PAGEb1 and FULLb to OK
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        # PAGEa2 ERROR
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  ERROR

        page_id_b2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # Change PAGEa2 and FULLa to OK
        self.change_backup_status(backup_dir, 'node', page_id_a2, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'OK')

        # PAGEb2 OK
        # PAGEa2 OK
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  OK

        # Purge backups
        backups = os.path.join(backup_dir, 'backups', 'node')
        for backup in os.listdir(backups):
            if backup not in [page_id_a2, page_id_b2, 'pg_probackup.conf']:
                with open(
                        os.path.join(
                            backups, backup, "backup.control"), "a") as conf:
                    conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                        datetime.now() - timedelta(days=3)))

        output = self.delete_expired(
            backup_dir, 'node',
            options=['--retention-window=1', '--expired', '--merge-expired'])

        self.assertIn(
            "Merge incremental chain between FULL backup {0} and backup {1}".format(
                backup_id_a, page_id_a2),
            output)

        self.assertIn(
            "Merging backup {0} with backup {1}".format(
                page_id_a1, backup_id_a), output)

        self.assertIn(
            "Rename {0} to {1}".format(
                backup_id_a, page_id_a1), output)

        self.assertIn(
            "Merging backup {0} with backup {1}".format(
                page_id_a2, page_id_a1), output)

        self.assertIn(
            "Rename {0} to {1}".format(
                page_id_a1, page_id_a2), output)

        self.assertIn(
            "Merge incremental chain between FULL backup {0} and backup {1}".format(
                backup_id_b, page_id_b2),
            output)

        self.assertIn(
            "Merging backup {0} with backup {1}".format(
                page_id_b1, backup_id_b), output)

        self.assertIn(
            "Rename {0} to {1}".format(
                backup_id_b, page_id_b1), output)

        self.assertIn(
            "Merging backup {0} with backup {1}".format(
                page_id_b2, page_id_b1), output)

        self.assertIn(
            "Rename {0} to {1}".format(
                page_id_b1, page_id_b2), output)

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 2)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_window_merge_interleaved_incremental_chains_1(self):
        """
            PAGEb3
            PAGEb2
            PAGEb1
            PAGEa1
            FULLb
            FULLa
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'],
            pg_options={'autovacuum':'off'})

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        node.pgbench_init(scale=3)

        # Take FULL BACKUPs
        backup_id_a = self.backup_node(backup_dir, 'node', node)
        pgbench = node.pgbench(options=['-t', '10', '-c', '2'])
        pgbench.wait()

        backup_id_b = self.backup_node(backup_dir, 'node', node)
        pgbench = node.pgbench(options=['-t', '10', '-c', '2'])
        pgbench.wait()

        # Change FULL B backup status to ERROR
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        page_id_a1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        pgdata_a1 = self.pgdata_content(node.data_dir)

        pgbench = node.pgbench(options=['-t', '10', '-c', '2'])
        pgbench.wait()

        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK
        # Change FULL B backup status to OK
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        # Change PAGEa1 backup status to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'ERROR')

        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  OK
        page_id_b1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        pgbench = node.pgbench(options=['-t', '10', '-c', '2'])
        pgbench.wait()

        page_id_b2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        pgbench = node.pgbench(options=['-t', '10', '-c', '2'])
        pgbench.wait()

        page_id_b3 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')
        pgdata_b3 = self.pgdata_content(node.data_dir)

        pgbench = node.pgbench(options=['-t', '10', '-c', '2'])
        pgbench.wait()

        # PAGEb3 OK
        # PAGEb2 OK
        # PAGEb1 OK
        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  OK

        # Change PAGEa1 backup status to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'OK')

        # PAGEb3 OK
        # PAGEb2 OK
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  OK

        # Purge backups
        backups = os.path.join(backup_dir, 'backups', 'node')
        for backup in os.listdir(backups):
            if backup in [page_id_a1, page_id_b3, 'pg_probackup.conf']:
                continue

            with open(
                    os.path.join(
                        backups, backup, "backup.control"), "a") as conf:
                conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                    datetime.now() - timedelta(days=3)))

        output = self.delete_expired(
            backup_dir, 'node',
            options=['--retention-window=1', '--expired', '--merge-expired'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 2)

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[1]['id'],
            page_id_b3)

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[0]['id'],
            page_id_a1)

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[1]['backup-mode'],
            'FULL')

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[0]['backup-mode'],
            'FULL')

        node.cleanup()

        # Data correctness of PAGEa3
        self.restore_node(backup_dir, 'node', node, backup_id=page_id_a1)
        pgdata_restored_a1 = self.pgdata_content(node.data_dir)
        self.compare_pgdata(pgdata_a1, pgdata_restored_a1)

        node.cleanup()

        # Data correctness of PAGEb3
        self.restore_node(backup_dir, 'node', node, backup_id=page_id_b3)
        pgdata_restored_b3 = self.pgdata_content(node.data_dir)
        self.compare_pgdata(pgdata_b3, pgdata_restored_b3)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_basic_window_merge_multiple_descendants(self):
        """
        PAGEb3
          |                 PAGEa3
        -----------------------------retention window
        PAGEb2               /
          |       PAGEa2    /        should be deleted
        PAGEb1       \     /
          |           PAGEa1
        FULLb           |
                      FULLa
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'],
            pg_options={'autovacuum': 'off'})

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        node.pgbench_init(scale=3)

        # Take FULL BACKUPs
        backup_id_a = self.backup_node(backup_dir, 'node', node)
        # pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        # pgbench.wait()

        backup_id_b = self.backup_node(backup_dir, 'node', node)
        # pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        # pgbench.wait()

        # Change FULLb backup status to ERROR
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        page_id_a1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        # pgbench.wait()

        # Change FULLb  to OK
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        # Change PAGEa1 to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'ERROR')

        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  OK

        page_id_b1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEb1 OK
        # PAGEa1 ERROR
        # FULLb  OK
        # FULLa  OK

        # pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        # pgbench.wait()

        # Change PAGEa1 to OK
        self.change_backup_status(backup_dir, 'node', page_id_a1, 'OK')

        # Change PAGEb1 and FULLb to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        page_id_a2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        # pgbench.wait()

        # PAGEa2 OK
        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        # Change PAGEb1 and FULLb to OK
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        # Change PAGEa2 and FULLa to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a2, 'ERROR')
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'ERROR')

        # PAGEa2 ERROR
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  ERROR

        page_id_b2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        # pgbench.wait()

        # PAGEb2 OK
        # PAGEa2 ERROR
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  ERROR

        # Change PAGEb2 and PAGEb1 to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_b2, 'ERROR')
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'ERROR')

        # and FULL stuff
        self.change_backup_status(backup_dir, 'node', backup_id_a, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        # PAGEb2 ERROR
        # PAGEa2 ERROR
        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        page_id_a3 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')
        # pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        # pgbench.wait()

        # PAGEa3 OK
        # PAGEb2 ERROR
        # PAGEa2 ERROR
        # PAGEb1 ERROR
        # PAGEa1 OK
        # FULLb  ERROR
        # FULLa  OK

        # Change PAGEa3 to ERROR
        self.change_backup_status(backup_dir, 'node', page_id_a3, 'ERROR')

        # Change PAGEb2, PAGEb1 and FULLb to OK
        self.change_backup_status(backup_dir, 'node', page_id_b2, 'OK')
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'OK')
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'OK')

        page_id_b3 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # PAGEb3 OK
        # PAGEa3 ERROR
        # PAGEb2 OK
        # PAGEa2 ERROR
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  OK

        # Change PAGEa3, PAGEa2 and PAGEb1 status to OK
        self.change_backup_status(backup_dir, 'node', page_id_a3, 'OK')
        self.change_backup_status(backup_dir, 'node', page_id_a2, 'OK')
        self.change_backup_status(backup_dir, 'node', page_id_b1, 'OK')

        # PAGEb3 OK
        # PAGEa3 OK
        # PAGEb2 OK
        # PAGEa2 OK
        # PAGEb1 OK
        # PAGEa1 OK
        # FULLb  OK
        # FULLa  OK

        # Check that page_id_a3 and page_id_a2 are both direct descendants of page_id_a1
        self.assertEqual(
            self.show_pb(
                backup_dir, 'node', backup_id=page_id_a3)['parent-backup-id'],
            page_id_a1)

        self.assertEqual(
            self.show_pb(
                backup_dir, 'node', backup_id=page_id_a2)['parent-backup-id'],
            page_id_a1)

        # Purge backups
        backups = os.path.join(backup_dir, 'backups', 'node')
        for backup in os.listdir(backups):
            if backup in [page_id_a3, page_id_b3, 'pg_probackup.conf']:
                continue

            with open(
                    os.path.join(
                        backups, backup, "backup.control"), "a") as conf:
                conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                    datetime.now() - timedelta(days=3)))

        output = self.delete_expired(
            backup_dir, 'node',
            options=[
                '--retention-window=1', '--expired',
                '--merge-expired', '--log-level-console=log'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 3)

        # Merging chain A
        self.assertIn(
            "Merge incremental chain between FULL backup {0} and backup {1}".format(
                backup_id_a, page_id_a3),
            output)

        self.assertIn(
            "Merging backup {0} with backup {1}".format(
                page_id_a1, backup_id_a), output)

        self.assertIn(
            "INFO: Rename {0} to {1}".format(
                backup_id_a, page_id_a1), output)

        self.assertIn(
            "WARNING: Backup {0} has multiple valid descendants. "
            "Automatic merge is not possible.".format(
                page_id_a1), output)

        # Merge chain B
        self.assertIn(
            "Merge incremental chain between FULL backup {0} and backup {1}".format(
                backup_id_b, page_id_b3),
            output)

        self.assertIn(
            "Merging backup {0} with backup {1}".format(
                page_id_b1, backup_id_b), output)

        self.assertIn(
            "INFO: Rename {0} to {1}".format(
                backup_id_b, page_id_b1), output)

        self.assertIn(
            "Merging backup {0} with backup {1}".format(
                page_id_b2, page_id_b1), output)

        self.assertIn(
            "INFO: Rename {0} to {1}".format(
                page_id_b1, page_id_b2), output)

        self.assertIn(
            "Merging backup {0} with backup {1}".format(
                page_id_b3, page_id_b2), output)

        self.assertIn(
            "INFO: Rename {0} to {1}".format(
                page_id_b2, page_id_b3), output)

        # this backup deleted because it is not guarded by retention
        self.assertIn(
            "INFO: Delete: {0}".format(
                page_id_a1), output)

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[2]['id'],
            page_id_b3)

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[1]['id'],
            page_id_a3)

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[0]['id'],
            page_id_a1)

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[2]['backup-mode'],
            'FULL')

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[1]['backup-mode'],
            'PAGE')

        self.assertEqual(
            self.show_pb(backup_dir, 'node')[0]['backup-mode'],
            'FULL')

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_window_chains(self):
        """
        PAGE
        -------window
        PAGE
        PAGE
        FULL
        PAGE
        PAGE
        FULL
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'],
            pg_options={'autovacuum': 'off'})

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        node.pgbench_init(scale=3)

        # Chain A
        backup_id_a = self.backup_node(backup_dir, 'node', node)
        page_id_a1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        page_id_a2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # Chain B
        backup_id_b = self.backup_node(backup_dir, 'node', node)

        pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        pgbench.wait()

        page_id_b1 = self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        pgbench.wait()

        page_id_b2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        pgbench = node.pgbench(options=['-T', '10', '-c', '2'])
        pgbench.wait()

        page_id_b3 = self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        pgdata = self.pgdata_content(node.data_dir)

        # Purge backups
        backups = os.path.join(backup_dir, 'backups', 'node')
        for backup in os.listdir(backups):
            if backup in [page_id_b3, 'pg_probackup.conf']:
                continue

            with open(
                    os.path.join(
                        backups, backup, "backup.control"), "a") as conf:
                conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                    datetime.now() - timedelta(days=3)))

        output = self.delete_expired(
            backup_dir, 'node',
            options=[
                '--retention-window=1', '--expired',
                '--merge-expired', '--log-level-console=log'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 1)

        node.cleanup()

        self.restore_node(backup_dir, 'node', node)

        pgdata_restored = self.pgdata_content(node.data_dir)
        self.compare_pgdata(pgdata, pgdata_restored)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_window_chains_1(self):
        """
        PAGE
        -------window
        PAGE
        PAGE
        FULL
        PAGE
        PAGE
        FULL
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        node.pgbench_init(scale=3)

        # Chain A
        backup_id_a = self.backup_node(backup_dir, 'node', node)
        page_id_a1 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        page_id_a2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # Chain B
        backup_id_b = self.backup_node(backup_dir, 'node', node)

        page_id_b1 = self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        page_id_b2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        page_id_b3 = self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        pgdata = self.pgdata_content(node.data_dir)

        # Purge backups
        backups = os.path.join(backup_dir, 'backups', 'node')
        for backup in os.listdir(backups):
            if backup in [page_id_b3, 'pg_probackup.conf']:
                continue

            with open(
                    os.path.join(
                        backups, backup, "backup.control"), "a") as conf:
                conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                    datetime.now() - timedelta(days=3)))

        output = self.delete_expired(
            backup_dir, 'node',
            options=[
                '--retention-window=1',
                '--merge-expired', '--log-level-console=log'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 4)

        self.assertIn(
            "There are no backups to delete by retention policy",
            output)

        self.assertIn(
            "Retention merging finished",
            output)

        output = self.delete_expired(
            backup_dir, 'node',
            options=[
                '--retention-window=1',
                '--expired', '--log-level-console=log'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 1)

        self.assertIn(
            "There are no backups to merge by retention policy",
            output)

        self.assertIn(
            "Purging finished",
            output)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    @unittest.skip("skip")
    def test_window_error_backups(self):
        """
        PAGE ERROR
        -------window
        PAGE ERROR
        PAGE ERROR
        PAGE ERROR
        FULL ERROR
        FULL
        -------redundancy
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # Take FULL BACKUPs
        backup_id_a1 = self.backup_node(backup_dir, 'node', node)
        gdb = self.backup_node(
            backup_dir, 'node', node, backup_type='page', gdb=True)

        page_id_a3 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # Change FULLb backup status to ERROR
        self.change_backup_status(backup_dir, 'node', backup_id_b, 'ERROR')

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_window_error_backups_1(self):
        """
        DELTA
        PAGE ERROR
        FULL
        -------window
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # Take FULL BACKUP
        full_id = self.backup_node(backup_dir, 'node', node)

        # Take PAGE BACKUP
        gdb = self.backup_node(
            backup_dir, 'node', node, backup_type='page', gdb=True)

        gdb.set_breakpoint('pg_stop_backup')
        gdb.run_until_break()
        gdb.remove_all_breakpoints()
        gdb._execute('signal SIGINT')
        gdb.continue_execution_until_error()

        page_id = self.show_pb(backup_dir, 'node')[1]['id']

        # Take DELTA backup
        delta_id = self.backup_node(
            backup_dir, 'node', node, backup_type='delta',
            options=['--retention-window=2', '--delete-expired'])

        # Take FULL BACKUP
        full2_id = self.backup_node(backup_dir, 'node', node)

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 4)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_window_error_backups_2(self):
        """
        DELTA
        PAGE ERROR
        FULL
        -------window
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # Take FULL BACKUP
        full_id = self.backup_node(backup_dir, 'node', node)

        # Take PAGE BACKUP
        gdb = self.backup_node(
            backup_dir, 'node', node, backup_type='page', gdb=True)

        gdb.set_breakpoint('pg_stop_backup')
        gdb.run_until_break()
        gdb._execute('signal SIGKILL')
        gdb.continue_execution_until_error()

        page_id = self.show_pb(backup_dir, 'node')[1]['id']

        # Take DELTA backup
        delta_id = self.backup_node(
            backup_dir, 'node', node, backup_type='delta',
            options=['--retention-window=2', '--delete-expired'])

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 3)

        # Clean after yourself
        # self.del_test_dir(module_name, fname)

    def test_retention_redundancy_overlapping_chains(self):
        """"""
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        if self.get_version(node) < 90600:
            self.del_test_dir(module_name, fname)
            return unittest.skip('Skipped because ptrack support is disabled')

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        self.set_config(
            backup_dir, 'node', options=['--retention-redundancy=1'])

        # Make backups to be purged
        self.backup_node(backup_dir, 'node', node)
        self.backup_node(backup_dir, 'node', node, backup_type="page")

        # Make backups to be keeped
        gdb = self.backup_node(backup_dir, 'node', node, gdb=True)
        gdb.set_breakpoint('backup_files')
        gdb.run_until_break()

        sleep(1)

        self.backup_node(backup_dir, 'node', node, backup_type="page")

        gdb.remove_all_breakpoints()
        gdb.continue_execution_until_exit()

        self.backup_node(backup_dir, 'node', node, backup_type="page")

        # Purge backups
        log = self.delete_expired(
            backup_dir, 'node', options=['--expired', '--wal'])
        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 2)

        self.validate_pb(backup_dir, 'node')

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    def test_retention_redundancy_overlapping_chains(self):
        """"""
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        if self.get_version(node) < 90600:
            self.del_test_dir(module_name, fname)
            return unittest.skip('Skipped because ptrack support is disabled')

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        self.set_config(
            backup_dir, 'node', options=['--retention-redundancy=1'])

        # Make backups to be purged
        self.backup_node(backup_dir, 'node', node)
        self.backup_node(backup_dir, 'node', node, backup_type="page")

        # Make backups to be keeped
        gdb = self.backup_node(backup_dir, 'node', node, gdb=True)
        gdb.set_breakpoint('backup_files')
        gdb.run_until_break()

        sleep(1)

        self.backup_node(backup_dir, 'node', node, backup_type="page")

        gdb.remove_all_breakpoints()
        gdb.continue_execution_until_exit()

        self.backup_node(backup_dir, 'node', node, backup_type="page")

        # Purge backups
        log = self.delete_expired(
            backup_dir, 'node', options=['--expired', '--wal'])
        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 2)

        self.validate_pb(backup_dir, 'node')

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    def test_wal_purge_victim(self):
        """
        https://github.com/postgrespro/pg_probackup/issues/103
        """
        fname = self.id().split('.')[3]
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            initdb_params=['--data-checksums'])

        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # Make ERROR incremental backup
        try:
            self.backup_node(backup_dir, 'node', node, backup_type='page')
            # we should die here because exception is what we expect to happen
            self.assertEqual(
                1, 0,
                "Expecting Error because page backup should not be possible "
                "without valid full backup.\n Output: {0} \n CMD: {1}".format(
                    repr(self.output), self.cmd))
        except ProbackupException as e:
            self.assertIn(
                "ERROR: Valid backup on current timeline 1 is not found. "
                "Create new FULL backup before an incremental one.",
                e.message,
                "\n Unexpected Error Message: {0}\n CMD: {1}".format(
                    repr(e.message), self.cmd))

        page_id = self.show_pb(backup_dir, 'node')[0]['id']

        sleep(1)

        # Make FULL backup
        full_id = self.backup_node(backup_dir, 'node', node, options=['--delete-wal'])

        try:
            self.validate_pb(backup_dir, 'node')
            # we should die here because exception is what we expect to happen
            self.assertEqual(
                1, 0,
                "Expecting Error because page backup should not be possible "
                "without valid full backup.\n Output: {0} \n CMD: {1}".format(
                    repr(self.output), self.cmd))
        except ProbackupException as e:
            self.assertIn(
                "INFO: Backup {0} WAL segments are valid".format(full_id),
                e.message)
            self.assertIn(
                "WARNING: Backup {0} has missing parent 0".format(page_id),
                e.message)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.skip("skip")
    def test_failed_merge_redundancy_retention(self):
        """
        Check that retention purge works correctly with MERGING backups
        """
        fname = self.id().split('.')[3]
        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        node = self.make_simple_node(
            base_dir=os.path.join(
                module_name, fname, 'node'),
            set_replication=True,
            initdb_params=['--data-checksums'])

        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # FULL1 backup
        full_id = self.backup_node(backup_dir, 'node', node)

        # DELTA BACKUP
        delta_id = self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        # DELTA BACKUP
        self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        # DELTA BACKUP
        self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        # FULL2 backup
        self.backup_node(backup_dir, 'node', node)

        # DELTA BACKUP
        self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        # DELTA BACKUP
        self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        # FULL3 backup
        self.backup_node(backup_dir, 'node', node)

        # DELTA BACKUP
        self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        # DELTA BACKUP
        self.backup_node(
            backup_dir, 'node', node, backup_type='delta')

        self.set_config(
            backup_dir, 'node', options=['--retention-redundancy=2'])

        self.set_config(
            backup_dir, 'node', options=['--retention-window=2'])

        # create pair of MERGING backup as a result of failed merge 
        gdb = self.merge_backup(
            backup_dir, 'node', delta_id, gdb=True)
        gdb.set_breakpoint('copy_file')
        gdb.run_until_break()
        gdb.continue_execution_until_break(2)
        gdb._execute('signal SIGKILL')

        # "expire" first full backup
        backups = os.path.join(backup_dir, 'backups', 'node')
        with open(
                os.path.join(
                    backups, full_id, "backup.control"), "a") as conf:
            conf.write("recovery_time='{:%Y-%m-%d %H:%M:%S}'\n".format(
                datetime.now() - timedelta(days=3)))

        # run retention merge
        self.delete_expired(
            backup_dir, 'node', options=['--delete-expired'])

        self.assertEqual(
            'MERGING',
            self.show_pb(backup_dir, 'node', full_id)['status'],
            'Backup STATUS should be "MERGING"')

        self.assertEqual(
            'MERGING',
            self.show_pb(backup_dir, 'node', delta_id)['status'],
            'Backup STATUS should be "MERGING"')

        self.assertEqual(len(self.show_pb(backup_dir, 'node')), 10)

        # Clean after yourself
        self.del_test_dir(module_name, fname)

    # @unittest.expectedFailure
    @unittest.skip("skip")
    def test_wal_depth(self):
        """
        ARCHIVE replica:

        t6                     |---------------------->
        t5                     |                           |------>
                               |                           |
        t4                     |                      |----|------>
                               |                      |
        t3                     |      |--B1--|/|--B2-|/|-B3-->
                               |      |
        t2                  |--A1-----|--A2--->
        t1  ---------Y1--Y2-|

        ARCHIVE master:
        t1  -Z1--Z2-->
        """
        fname = self.id().split('.')[3]
        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        master = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'master'),
            set_replication=True,
            initdb_params=['--data-checksums'],
            pg_options={
                'archive_timeout': '30s',
                'checkpoint_timeout': '30s',
                'autovacuum': 'off'})

        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'master', master)
        self.set_archiving(backup_dir, 'master', master)

        master.slow_start()

        # FULL
        master.safe_psql(
            "postgres",
            "create table t_heap as select i as id, md5(i::text) as text, "
            "md5(repeat(i::text,10))::tsvector as tsvector "
            "from generate_series(0,10000) i")

        self.backup_node(backup_dir, 'master', master)

        # PAGE
        master.safe_psql(
            "postgres",
            "insert into t_heap select i as id, md5(i::text) as text, "
            "md5(repeat(i::text,10))::tsvector as tsvector "
            "from generate_series(10000,20000) i")

        self.backup_node(
            backup_dir, 'master', master, backup_type='page')

        replica = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'replica'))
        replica.cleanup()
        self.restore_node(backup_dir, 'master', replica)
        self.set_replica(master, replica)

        self.add_instance(backup_dir, 'replica', replica)
        self.set_archiving(backup_dir, 'replica', replica, replica=True)

        copy_tree(
            os.path.join(backup_dir, 'wal', 'master'),
            os.path.join(backup_dir, 'wal', 'replica'))

        # Check data correctness on replica
        replica.slow_start(replica=True)

        # FULL backup replica
        Y1 = self.backup_node(
            backup_dir, 'replica', replica,
            options=['--stream', '--archive-timeout=60s'])

        master.pgbench_init(scale=5)

        # PAGE backup replica
        Y2 = self.backup_node(
            backup_dir, 'replica', replica,
            backup_type='page', options=['--stream', '--archive-timeout=60s'])

        # create timeline t2
        replica.promote()

        # do checkpoint to increment timeline ID in pg_control
        replica.safe_psql(
            'postgres',
            'CHECKPOINT')

        # FULL backup replica
        A1 = self.backup_node(
            backup_dir, 'replica', replica)

        replica.pgbench_init(scale=5)

        replica.safe_psql(
            'postgres',
            "CREATE TABLE t1 (a text)")

        target_xid = None
        with replica.connect("postgres") as con:
            res = con.execute(
                "INSERT INTO t1 VALUES ('inserted') RETURNING (xmin)")
            con.commit()
            target_xid = res[0][0]

        # DELTA backup replica
        A2 = self.backup_node(
            backup_dir, 'replica', replica, backup_type='delta')

        # create timeline t3
        replica.cleanup()
        self.restore_node(
            backup_dir, 'replica', replica,
            options=[
                '--recovery-target-xid={0}'.format(target_xid),
                '--recovery-target-timeline=2',
                '--recovery-target-action=promote'])

        replica.slow_start()

        B1 = self.backup_node(
            backup_dir, 'replica', replica)

        replica.pgbench_init(scale=2)

        B2 = self.backup_node(
            backup_dir, 'replica', replica, backup_type='page')

        replica.pgbench_init(scale=2)

        target_xid = None
        with replica.connect("postgres") as con:
            res = con.execute(
                "INSERT INTO t1 VALUES ('inserted') RETURNING (xmin)")
            con.commit()
            target_xid = res[0][0]

        B3 = self.backup_node(
            backup_dir, 'replica', replica, backup_type='page')

        replica.pgbench_init(scale=2)

        # create timeline t4
        replica.cleanup()
        self.restore_node(
            backup_dir, 'replica', replica,
            options=[
                '--recovery-target-xid={0}'.format(target_xid),
                '--recovery-target-timeline=3',
                '--recovery-target-action=promote'])

        replica.slow_start()

        replica.safe_psql(
            'postgres',
            'CREATE TABLE '
            't2 as select i, '
            'repeat(md5(i::text),5006056) as fat_attr '
            'from generate_series(0,6) i')

        target_xid = None
        with replica.connect("postgres") as con:
            res = con.execute(
                "INSERT INTO t1 VALUES ('inserted') RETURNING (xmin)")
            con.commit()
            target_xid = res[0][0]

        replica.safe_psql(
            'postgres',
            'CREATE TABLE '
            't3 as select i, '
            'repeat(md5(i::text),5006056) as fat_attr '
            'from generate_series(0,10) i')

        # create timeline t5
        replica.cleanup()
        self.restore_node(
            backup_dir, 'replica', replica,
            options=[
                '--recovery-target-xid={0}'.format(target_xid),
                '--recovery-target-timeline=4',
                '--recovery-target-action=promote'])

        replica.slow_start()

        replica.safe_psql(
            'postgres',
            'CREATE TABLE '
            't4 as select i, '
            'repeat(md5(i::text),5006056) as fat_attr '
            'from generate_series(0,6) i')

        # create timeline t6
        replica.cleanup()

        self.restore_node(
            backup_dir, 'replica', replica, backup_id=A1,
            options=[
                '--recovery-target=immediate',
                '--recovery-target-action=promote'])
        replica.slow_start()

        replica.pgbench_init(scale=2)

        show = self.show_archive(backup_dir, as_text=True)
        show = self.show_archive(backup_dir)

        for instance in show:
            if instance['instance'] == 'replica':
                replica_timelines = instance['timelines']

            if instance['instance'] == 'master':
                master_timelines = instance['timelines']

        # check that all timelines are ok
        for timeline in replica_timelines:
            self.assertTrue(timeline['status'], 'OK')

        # check that all timelines are ok
        for timeline in master_timelines:
            self.assertTrue(timeline['status'], 'OK')

        # create holes in t3
        wals_dir = os.path.join(backup_dir, 'wal', 'replica')
        wals = [
                f for f in os.listdir(wals_dir) if os.path.isfile(os.path.join(wals_dir, f))
                and not f.endswith('.backup') and not f.endswith('.history') and f.startswith('00000003')
            ]
        wals.sort()

        # check that t3 is ok
        self.show_archive(backup_dir)

        file = os.path.join(backup_dir, 'wal', 'replica', '000000030000000000000017')
        if self.archive_compress:
            file = file + '.gz'
        os.remove(file)

        file = os.path.join(backup_dir, 'wal', 'replica', '000000030000000000000012')
        if self.archive_compress:
            file = file + '.gz'
        os.remove(file)

        file = os.path.join(backup_dir, 'wal', 'replica', '000000030000000000000013')
        if self.archive_compress:
            file = file + '.gz'
        os.remove(file)

        # check that t3 is not OK
        show = self.show_archive(backup_dir)

        show = self.show_archive(backup_dir)

        for instance in show:
            if instance['instance'] == 'replica':
                replica_timelines = instance['timelines']

        # sanity
        for timeline in replica_timelines:
            if timeline['tli'] == 1:
                timeline_1 = timeline
                continue

            if timeline['tli'] == 2:
                timeline_2 = timeline
                continue

            if timeline['tli'] == 3:
                timeline_3 = timeline
                continue

            if timeline['tli'] == 4:
                timeline_4 = timeline
                continue

            if timeline['tli'] == 5:
                timeline_5 = timeline
                continue

            if timeline['tli'] == 6:
                timeline_6 = timeline
                continue

        self.assertEqual(timeline_6['status'], "OK")
        self.assertEqual(timeline_5['status'], "OK")
        self.assertEqual(timeline_4['status'], "OK")
        self.assertEqual(timeline_3['status'], "DEGRADED")
        self.assertEqual(timeline_2['status'], "OK")
        self.assertEqual(timeline_1['status'], "OK")

        self.assertEqual(len(timeline_3['lost-segments']), 2)
        self.assertEqual(timeline_3['lost-segments'][0]['begin-segno'], '0000000000000012')
        self.assertEqual(timeline_3['lost-segments'][0]['end-segno'], '0000000000000013')
        self.assertEqual(timeline_3['lost-segments'][1]['begin-segno'], '0000000000000017')
        self.assertEqual(timeline_3['lost-segments'][1]['end-segno'], '0000000000000017')

        self.assertEqual(len(timeline_6['backups']), 0)
        self.assertEqual(len(timeline_5['backups']), 0)
        self.assertEqual(len(timeline_4['backups']), 0)
        self.assertEqual(len(timeline_3['backups']), 3)
        self.assertEqual(len(timeline_2['backups']), 2)
        self.assertEqual(len(timeline_1['backups']), 2)

        # check closest backup correctness
        self.assertEqual(timeline_6['closest-backup-id'], A1)
        self.assertEqual(timeline_5['closest-backup-id'], B2)
        self.assertEqual(timeline_4['closest-backup-id'], B2)
        self.assertEqual(timeline_3['closest-backup-id'], A1)
        self.assertEqual(timeline_2['closest-backup-id'], Y2)

        # check parent tli correctness
        self.assertEqual(timeline_6['parent-tli'], 2)
        self.assertEqual(timeline_5['parent-tli'], 4)
        self.assertEqual(timeline_4['parent-tli'], 3)
        self.assertEqual(timeline_3['parent-tli'], 2)
        self.assertEqual(timeline_2['parent-tli'], 1)
        self.assertEqual(timeline_1['parent-tli'], 0)

        output = self.delete_pb(
            backup_dir, 'replica',
            options=['--delete-wal', '--log-level-console=verbose'])

        self.validate_pb(backup_dir, 'node')

        self.del_test_dir(module_name, fname)

    def test_wal_depth_1(self):
        """
                        |-------------B5----------> WAL timeline3
                  |-----|-------------------------> WAL timeline2
        B1   B2---|        B3     B4-------B6-----> WAL timeline1

        wal-depth=2
        """
        fname = self.id().split('.')[3]
        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            set_replication=True,
            initdb_params=['--data-checksums'],
            pg_options={
                'archive_timeout': '30s',
                'checkpoint_timeout': '30s',
                'autovacuum': 'off'})

        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_archiving(backup_dir, 'node', node)

        self.set_config(backup_dir, 'node', options=['--archive-timeout=60s'])

        node.slow_start()

        # FULL
        node.pgbench_init(scale=1)
        B1 = self.backup_node(backup_dir, 'node', node)

        # PAGE
        node.pgbench_init(scale=1)
        B2 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # generate_some more data
        node.pgbench_init(scale=1)

        target_xid = node.safe_psql(
            "postgres",
            "select txid_current()").rstrip()

        node.pgbench_init(scale=1)

        B3 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        node.pgbench_init(scale=1)

        B4 = self.backup_node(
            backup_dir, 'node', node, backup_type='page')

        # Timeline 2
        node_restored = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node_restored'))

        node_restored.cleanup()

        output = self.restore_node(
            backup_dir, 'node', node_restored,
            options=[
                '--recovery-target-xid={0}'.format(target_xid),
                '--recovery-target-action=promote'])

        self.assertIn(
            'Restore of backup {0} completed'.format(B2),
            output)

        self.set_auto_conf(node_restored, options={'port': node_restored.port})

        node_restored.slow_start()

        node_restored.pgbench_init(scale=1)

        target_xid = node_restored.safe_psql(
            "postgres",
            "select txid_current()").rstrip()

        node_restored.pgbench_init(scale=2)

        # Timeline 3
        node_restored.cleanup()

        output = self.restore_node(
            backup_dir, 'node', node_restored,
            options=[
                '--recovery-target-xid={0}'.format(target_xid),
                '--recovery-target-timeline=2',
                '--recovery-target-action=promote'])

        self.assertIn(
            'Restore of backup {0} completed'.format(B2),
            output)

        self.set_auto_conf(node_restored, options={'port': node_restored.port})

        node_restored.slow_start()

        node_restored.pgbench_init(scale=1)
        B5 = self.backup_node(
            backup_dir, 'node', node_restored, data_dir=node_restored.data_dir)

        node.pgbench_init(scale=1)
        B6 = self.backup_node(backup_dir, 'node', node)

        lsn = self.show_archive(backup_dir, 'node', tli=2)['switchpoint']

        self.validate_pb(
            backup_dir, 'node', backup_id=B2,
            options=['--recovery-target-lsn={0}'.format(lsn)])

        self.validate_pb(backup_dir, 'node')

        self.del_test_dir(module_name, fname)

    def test_wal_purge(self):
        """
         -------------------------------------> tli5
         ---------------------------B6--------> tli4
                            S2`---------------> tli3
             S1`------------S2---B4-------B5--> tli2
        B1---S1-------------B2--------B3------> tli1

        B* - backups
        S* - switchpoints

        Expected result:
                    TLI5 will be purged entirely
                                    B6--------> tli4
                            S2`---------------> tli3
             S1`------------S2---B4-------B5--> tli2
        B1---S1-------------B2--------B3------> tli1

        wal-depth=2
        """
        fname = self.id().split('.')[3]
        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            set_replication=True,
            initdb_params=['--data-checksums'])

        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_config(backup_dir, 'node', options=['--archive-timeout=60s'])

        node.slow_start()

        # STREAM FULL
        stream_id = self.backup_node(
            backup_dir, 'node', node, options=['--stream'])

        node.stop()
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # FULL
        B1 = self.backup_node(backup_dir, 'node', node)
        node.pgbench_init(scale=1)

        target_xid = node.safe_psql(
            "postgres",
            "select txid_current()").rstrip()
        node.pgbench_init(scale=5)

        # B2 FULL on TLI1
        B2 = self.backup_node(backup_dir, 'node', node)
        node.pgbench_init(scale=4)
        B3 = self.backup_node(backup_dir, 'node', node)
        node.pgbench_init(scale=4)

        # TLI 2
        node_tli2 = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node_tli2'))
        node_tli2.cleanup()

        output = self.restore_node(
            backup_dir, 'node', node_tli2,
            options=[
                '--recovery-target-xid={0}'.format(target_xid),
                '--recovery-target-timeline=1'.format(target_xid),
                '--recovery-target-action=promote'])

        self.assertIn(
            'INFO: Restore of backup {0} completed'.format(B1),
            output)

        self.set_auto_conf(node_tli2, options={'port': node_tli2.port})
        node_tli2.slow_start()
        node_tli2.pgbench_init(scale=4)

        target_xid = node_tli2.safe_psql(
            "postgres",
            "select txid_current()").rstrip()
        node_tli2.pgbench_init(scale=1)

        B4 = self.backup_node(
            backup_dir, 'node', node_tli2, data_dir=node_tli2.data_dir)
        node_tli2.pgbench_init(scale=3)

        B5 = self.backup_node(
            backup_dir, 'node', node_tli2, data_dir=node_tli2.data_dir)
        node_tli2.pgbench_init(scale=1)
        node_tli2.cleanup()

        # TLI3
        node_tli3 = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node_tli3'))
        node_tli3.cleanup()

        # Note, that successful validation here is a happy coincidence 
        output = self.restore_node(
            backup_dir, 'node', node_tli3,
            options=[
                '--recovery-target-xid={0}'.format(target_xid),
                '--recovery-target-timeline=2',
                '--recovery-target-action=promote'])

        self.assertIn(
            'INFO: Restore of backup {0} completed'.format(B1),
            output)
        self.set_auto_conf(node_tli3, options={'port': node_tli3.port})
        node_tli3.slow_start()
        node_tli3.pgbench_init(scale=5)
        node_tli3.cleanup()

        # TLI4
        node_tli4 = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node_tli4'))
        node_tli4.cleanup()

        self.restore_node(
            backup_dir, 'node', node_tli4, backup_id=stream_id,
            options=[
                '--recovery-target=immediate',
                '--recovery-target-action=promote'])

        self.set_auto_conf(node_tli4, options={'port': node_tli4.port})
        self.set_archiving(backup_dir, 'node', node_tli4)
        node_tli4.slow_start()

        node_tli4.pgbench_init(scale=5)

        B6 = self.backup_node(
            backup_dir, 'node', node_tli4, data_dir=node_tli4.data_dir)
        node_tli4.pgbench_init(scale=5)
        node_tli4.cleanup()

        # TLI5
        node_tli5 = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node_tli5'))
        node_tli5.cleanup()

        self.restore_node(
            backup_dir, 'node', node_tli5, backup_id=stream_id,
            options=[
                '--recovery-target=immediate',
                '--recovery-target-action=promote'])

        self.set_auto_conf(node_tli5, options={'port': node_tli5.port})
        self.set_archiving(backup_dir, 'node', node_tli5)
        node_tli5.slow_start()
        node_tli5.pgbench_init(scale=10)

        # delete '.history' file of TLI4
        os.remove(os.path.join(backup_dir, 'wal', 'node', '00000004.history'))
        # delete '.history' file of TLI5
        os.remove(os.path.join(backup_dir, 'wal', 'node', '00000005.history'))

        output = self.delete_pb(
            backup_dir, 'node',
            options=[
                '--delete-wal', '--dry-run',
                '--log-level-console=verbose'])

        self.assertIn(
            'INFO: On timeline 4 WAL segments between 0000000000000002 '
            'and 0000000000000005 can be removed',
            output)

        self.assertIn(
            'INFO: On timeline 5 all files can be removed',
            output)

        show_tli1_before = self.show_archive(backup_dir, 'node', tli=1)
        show_tli2_before = self.show_archive(backup_dir, 'node', tli=2)
        show_tli3_before = self.show_archive(backup_dir, 'node', tli=3)
        show_tli4_before = self.show_archive(backup_dir, 'node', tli=4)
        show_tli5_before = self.show_archive(backup_dir, 'node', tli=5)

        self.assertTrue(show_tli1_before)
        self.assertTrue(show_tli2_before)
        self.assertTrue(show_tli3_before)
        self.assertTrue(show_tli4_before)
        self.assertTrue(show_tli5_before)

        output = self.delete_pb(
            backup_dir, 'node',
            options=['--delete-wal', '--log-level-console=verbose'])

        self.assertIn(
            'INFO: On timeline 4 WAL segments between 0000000000000002 '
            'and 0000000000000005 will be removed',
            output)

        self.assertIn(
            'INFO: On timeline 5 all files will be removed',
            output)

        show_tli1_after = self.show_archive(backup_dir, 'node', tli=1)
        show_tli2_after = self.show_archive(backup_dir, 'node', tli=2)
        show_tli3_after = self.show_archive(backup_dir, 'node', tli=3)
        show_tli4_after = self.show_archive(backup_dir, 'node', tli=4)
        show_tli5_after = self.show_archive(backup_dir, 'node', tli=5)

        self.assertEqual(show_tli1_before, show_tli1_after)
        self.assertEqual(show_tli2_before, show_tli2_after)
        self.assertEqual(show_tli3_before, show_tli3_after)
        self.assertNotEqual(show_tli4_before, show_tli4_after)
        self.assertNotEqual(show_tli5_before, show_tli5_after)

        self.assertEqual(
            show_tli4_before['min-segno'],
            '0000000000000002')

        self.assertEqual(
            show_tli4_after['min-segno'],
            '0000000000000006')

        self.assertFalse(show_tli5_after)

        self.validate_pb(backup_dir, 'node')

        self.del_test_dir(module_name, fname)

    def test_wal_depth_2(self):
        """
         -------------------------------------> tli5
         ---------------------------B6--------> tli4
                            S2`---------------> tli3
             S1`------------S2---B4-------B5--> tli2
        B1---S1-------------B2--------B3------> tli1

        B* - backups
        S* - switchpoints
        wal-depth=2

        Expected result:
                    TLI5 will be purged entirely
                                    B6--------> tli4
                            S2`---------------> tli3
             S1`------------S2   B4-------B5--> tli2
        B1---S1             B2--------B3------> tli1

        wal-depth=2
        """
        fname = self.id().split('.')[3]
        backup_dir = os.path.join(self.tmp_path, module_name, fname, 'backup')
        node = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node'),
            set_replication=True,
            initdb_params=['--data-checksums'])

        self.init_pb(backup_dir)
        self.add_instance(backup_dir, 'node', node)
        self.set_config(backup_dir, 'node', options=['--archive-timeout=60s'])

        node.slow_start()

        # STREAM FULL
        stream_id = self.backup_node(
            backup_dir, 'node', node, options=['--stream'])

        node.stop()
        self.set_archiving(backup_dir, 'node', node)
        node.slow_start()

        # FULL
        B1 = self.backup_node(backup_dir, 'node', node)
        node.pgbench_init(scale=1)

        target_xid = node.safe_psql(
            "postgres",
            "select txid_current()").rstrip()
        node.pgbench_init(scale=5)

        # B2 FULL on TLI1
        B2 = self.backup_node(backup_dir, 'node', node)
        node.pgbench_init(scale=4)
        B3 = self.backup_node(backup_dir, 'node', node)
        node.pgbench_init(scale=4)

        # TLI 2
        node_tli2 = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node_tli2'))
        node_tli2.cleanup()

        output = self.restore_node(
            backup_dir, 'node', node_tli2,
            options=[
                '--recovery-target-xid={0}'.format(target_xid),
                '--recovery-target-timeline=1'.format(target_xid),
                '--recovery-target-action=promote'])

        self.assertIn(
            'INFO: Restore of backup {0} completed'.format(B1),
            output)

        self.set_auto_conf(node_tli2, options={'port': node_tli2.port})
        node_tli2.slow_start()
        node_tli2.pgbench_init(scale=4)

        target_xid = node_tli2.safe_psql(
            "postgres",
            "select txid_current()").rstrip()
        node_tli2.pgbench_init(scale=1)

        B4 = self.backup_node(
            backup_dir, 'node', node_tli2, data_dir=node_tli2.data_dir)
        node_tli2.pgbench_init(scale=3)

        B5 = self.backup_node(
            backup_dir, 'node', node_tli2, data_dir=node_tli2.data_dir)
        node_tli2.pgbench_init(scale=1)
        node_tli2.cleanup()

        # TLI3
        node_tli3 = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node_tli3'))
        node_tli3.cleanup()

        # Note, that successful validation here is a happy coincidence 
        output = self.restore_node(
            backup_dir, 'node', node_tli3,
            options=[
                '--recovery-target-xid={0}'.format(target_xid),
                '--recovery-target-timeline=2',
                '--recovery-target-action=promote'])

        self.assertIn(
            'INFO: Restore of backup {0} completed'.format(B1),
            output)
        self.set_auto_conf(node_tli3, options={'port': node_tli3.port})
        node_tli3.slow_start()
        node_tli3.pgbench_init(scale=5)
        node_tli3.cleanup()

        # TLI4
        node_tli4 = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node_tli4'))
        node_tli4.cleanup()

        self.restore_node(
            backup_dir, 'node', node_tli4, backup_id=stream_id,
            options=[
                '--recovery-target=immediate',
                '--recovery-target-action=promote'])

        self.set_auto_conf(node_tli4, options={'port': node_tli4.port})
        self.set_archiving(backup_dir, 'node', node_tli4)
        node_tli4.slow_start()

        node_tli4.pgbench_init(scale=5)

        B6 = self.backup_node(
            backup_dir, 'node', node_tli4, data_dir=node_tli4.data_dir)
        node_tli4.pgbench_init(scale=5)
        node_tli4.cleanup()

        # TLI5
        node_tli5 = self.make_simple_node(
            base_dir=os.path.join(module_name, fname, 'node_tli5'))
        node_tli5.cleanup()

        self.restore_node(
            backup_dir, 'node', node_tli5, backup_id=stream_id,
            options=[
                '--recovery-target=immediate',
                '--recovery-target-action=promote'])

        self.set_auto_conf(node_tli5, options={'port': node_tli5.port})
        self.set_archiving(backup_dir, 'node', node_tli5)
        node_tli5.slow_start()
        node_tli5.pgbench_init(scale=10)

        # delete '.history' file of TLI4
        os.remove(os.path.join(backup_dir, 'wal', 'node', '00000004.history'))
        # delete '.history' file of TLI5
        os.remove(os.path.join(backup_dir, 'wal', 'node', '00000005.history'))

        output = self.delete_pb(
            backup_dir, 'node',
            options=[
                '--delete-wal', '--dry-run',
                '--wal-depth=2', '--log-level-console=verbose'])

        start_lsn_B2 = self.show_pb(backup_dir, 'node', B2)['start-lsn']
        self.assertIn(
            'On timeline 1 WAL is protected from purge at {0}'.format(start_lsn_B2),
            output)

        self.assertIn(
            'VERBOSE: Archive backup {0} to stay consistent protect from '
            'purge WAL interval between 0000000000000004 and 0000000000000004 '
            'on timeline 1'.format(B1), output)

        start_lsn_B4 = self.show_pb(backup_dir, 'node', B4)['start-lsn']
        self.assertIn(
            'On timeline 2 WAL is protected from purge at {0}'.format(start_lsn_B4),
            output)

        self.assertIn(
            'VERBOSE: Timeline 3 to stay reachable from timeline 1 protect '
            'from purge WAL interval between 0000000000000005 and '
            '0000000000000008 on timeline 2', output)

        self.assertIn(
            'VERBOSE: Timeline 3 to stay reachable from timeline 1 protect '
            'from purge WAL interval between 0000000000000004 and '
            '0000000000000005 on timeline 1', output)

        show_tli1_before = self.show_archive(backup_dir, 'node', tli=1)
        show_tli2_before = self.show_archive(backup_dir, 'node', tli=2)
        show_tli3_before = self.show_archive(backup_dir, 'node', tli=3)
        show_tli4_before = self.show_archive(backup_dir, 'node', tli=4)
        show_tli5_before = self.show_archive(backup_dir, 'node', tli=5)

        self.assertTrue(show_tli1_before)
        self.assertTrue(show_tli2_before)
        self.assertTrue(show_tli3_before)
        self.assertTrue(show_tli4_before)
        self.assertTrue(show_tli5_before)

        output = self.delete_pb(
            backup_dir, 'node',
            options=['--delete-wal', '--wal-depth=2', '--log-level-console=verbose'])

        show_tli1_after = self.show_archive(backup_dir, 'node', tli=1)
        show_tli2_after = self.show_archive(backup_dir, 'node', tli=2)
        show_tli3_after = self.show_archive(backup_dir, 'node', tli=3)
        show_tli4_after = self.show_archive(backup_dir, 'node', tli=4)
        show_tli5_after = self.show_archive(backup_dir, 'node', tli=5)

        self.assertNotEqual(show_tli1_before, show_tli1_after)
        self.assertNotEqual(show_tli2_before, show_tli2_after)
        self.assertEqual(show_tli3_before, show_tli3_after)
        self.assertNotEqual(show_tli4_before, show_tli4_after)
        self.assertNotEqual(show_tli5_before, show_tli5_after)

        self.assertEqual(
            show_tli4_before['min-segno'],
            '0000000000000002')

        self.assertEqual(
            show_tli4_after['min-segno'],
            '0000000000000006')

        self.assertFalse(show_tli5_after)

        self.assertTrue(show_tli1_after['lost-segments'])
        self.assertTrue(show_tli2_after['lost-segments'])
        self.assertFalse(show_tli3_after['lost-segments'])
        self.assertFalse(show_tli4_after['lost-segments'])
        self.assertFalse(show_tli5_after)

        self.assertEqual(len(show_tli1_after['lost-segments']), 1)
        self.assertEqual(len(show_tli2_after['lost-segments']), 1)

        self.assertEqual(
            show_tli1_after['lost-segments'][0]['begin-segno'],
            '0000000000000006')

        self.assertEqual(
            show_tli1_after['lost-segments'][0]['end-segno'],
            '0000000000000009')

        self.assertEqual(
            show_tli2_after['lost-segments'][0]['begin-segno'],
            '0000000000000009')

        self.assertEqual(
            show_tli2_after['lost-segments'][0]['end-segno'],
            '0000000000000009')

        self.validate_pb(backup_dir, 'node')

        self.del_test_dir(module_name, fname)
