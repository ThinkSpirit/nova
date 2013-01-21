# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mox
import __builtin__
from StringIO import StringIO
from nova import exception
from nova import test
from nova.compute import power_state
from nova.tests.openvz import fakes
from nova.openstack.common import cfg
from uuid import uuid4
from nova.virt.openvz import utils as ovz_utils

CONF = cfg.CONF


class OpenVzUtilsTestCase(test.TestCase):
    def setUp(self):
        super(OpenVzUtilsTestCase, self).setUp()

    def test_execute_process_execution_error(self):
        self.mox.StubOutWithMock(ovz_utils.utils, 'execute')
        ovz_utils.utils.execute(
            'cat', '/proc/cpuinfo', run_as_root=False).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable, ovz_utils.execute,
            'cat', '/proc/cpuinfo', run_as_root=False)

    def test_execute_process_execution_error_no_raise_on_error(self):
        self.mox.StubOutWithMock(ovz_utils.utils, 'execute')
        ovz_utils.utils.execute(
            'cat', '/proc/cpuinfo', run_as_root=False).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ovz_utils.execute(
            'cat', '/proc/cpuinfo', run_as_root=False, raise_on_error=False)

    def test_mkfs_uuid(self):
        fs_uuid = uuid4()
        path = '/dev/sdgg'
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute(
            'mkfs', '-F', '-t', 'ext3', '-U', fs_uuid, path, run_as_root=True)
        self.mox.ReplayAll()
        ovz_utils.mkfs(path, 'ext3', fs_uuid)

    def test_mkfs_label(self):
        path = '/dev/sdgg'
        fs_label = 'STORAGE'
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute(
            'mkfs', '-F', '-t', 'ext3', '-U', mox.IgnoreArg(), '-L', fs_label,
            path, run_as_root=True)
        self.mox.ReplayAll()
        ovz_utils.mkfs(path, 'ext3', None, fs_label)

    def test_get_fs_uuid_success(self):
        dev = '/dev/sdgg'
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute(
            'blkid', '-o', 'value', '-s', 'UUID', dev,
            run_as_root=True).AndReturn(fakes.BLKID)
        self.mox.ReplayAll()
        fs_uuid = ovz_utils.get_fs_uuid(dev)
        self.assertEqual(fs_uuid, fakes.BLKID.strip())

    def test_get_fs_uuid_failure(self):
        dev = '/dev/sdgg'
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute(
            'blkid', '-o', 'value', '-s', 'UUID', dev,
            run_as_root=True).AndReturn('\n')
        self.mox.ReplayAll()
        fs_uuid = ovz_utils.get_fs_uuid(dev)
        self.assertFalse(fs_uuid)

    def test_get_vcpu_total_success(self):
        self.mox.StubOutWithMock(
            ovz_utils.multiprocessing, 'cpu_count')
        ovz_utils.multiprocessing.cpu_count().AndReturn(
            fakes.HOSTSTATS['vcpus'])
        self.mox.ReplayAll()
        result = ovz_utils.get_vcpu_total()
        self.assertEqual(result, fakes.HOSTSTATS['vcpus'])

    def test_get_vcpu_total_success(self):
        self.mox.StubOutWithMock(
            ovz_utils.multiprocessing, 'cpu_count')
        ovz_utils.multiprocessing.cpu_count().AndRaise(NotImplementedError)
        self.mox.ReplayAll()
        result = ovz_utils.get_vcpu_total()
        self.assertEqual(result, 0)

    def test_get_cpuinfo_not_running_on_linux(self):
        self.mox.StubOutWithMock(ovz_utils, 'sys')
        self.mox.StubOutWithMock(ovz_utils.sys, 'platform')
        self.mox.StubOutWithMock(ovz_utils.sys.platform, 'upper')
        ovz_utils.sys.platform.upper().AndReturn('DARWIN')
        self.mox.ReplayAll()
        result = ovz_utils.get_cpuinfo()
        self.assertEqual(result, 0)

#    def test_get_cpuinfo(self):
#        self.mox.StubOutWithMock(ovz_utils, 'sys')
#        self.mox.StubOutWithMock(ovz_utils.sys, 'platform')
#        self.mox.StubOutWithMock(ovz_utils.sys.platform, 'upper')
#        ovz_utils.sys.platform.upper().AndReturn('LINUX2')
#        self.mox.StubOutWithMock(__builtin__, 'open')
#        __builtin__.open('/proc/cpuinfo').AndReturn(StringIO(fakes.PROCINFO))
#        self.mox.ReplayAll()
#        result = ovz_utils.get_cpuinfo()
#        self.assertEqual(result, 0)

    def test_iscsi_initiator(self):
        self.mox.StubOutWithMock(ovz_utils.utils, 'read_file_as_root')
        ovz_utils.utils.read_file_as_root(
            '/etc/iscsi/initiatorname.iscsi').AndReturn(fakes.ISCSIINITIATOR)
        self.mox.ReplayAll()
        iscsi_initiator = ovz_utils.get_iscsi_initiator()
        self.assertEqual(fakes.INITIATORNAME, iscsi_initiator)

    def test_get_cpuunits_capability(self):
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute(
            'vzcpucheck', run_as_root=True).AndReturn('')
        self.mox.ReplayAll()
        self.assertRaises(
            exception.InvalidCPUInfo, ovz_utils.get_cpuunits_capability)

    def test_get_vcpu_used(self):
        self.mox.StubOutWithMock(ovz_utils, 'get_cpuunits_capability')
        ovz_utils.get_cpuunits_capability().AndReturn(fakes.CPUUNITSCAPA)
        self.mox.StubOutWithMock(ovz_utils, 'get_vcpu_total')
        ovz_utils.get_vcpu_total().AndReturn(fakes.HOSTSTATS['vcpus'])
        self.mox.ReplayAll()
        used = int(fakes.HOSTSTATS['vcpus'] *
                   (float(fakes.CPUUNITSCAPA['subscribed']) /
                    fakes.CPUUNITSCAPA['total']))
        result = ovz_utils.get_vcpu_used()
        self.assertEqual(result, used)

    def test_get_memory_mb_total_not_running_on_linux(self):
        self.mox.StubOutWithMock(ovz_utils, 'sys')
        self.mox.StubOutWithMock(ovz_utils.sys, 'platform')
        self.mox.StubOutWithMock(ovz_utils.sys.platform, 'upper')
        ovz_utils.sys.platform.upper().AndReturn('DARWIN')
        self.mox.ReplayAll()
        result = ovz_utils.get_memory_mb_total()
        self.assertEqual(result, 0)

    def test_get_memory_mb_used(self):
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute(
            'vzlist', '--all', '-H', '-o', 'ctid,privvmpages.l',
            run_as_root=True).AndReturn(fakes.PRIVVMPAGES)
        self.mox.ReplayAll()
        memory_used = (((int(
            fakes.PRIVVMPAGES_1024.strip().split()[1]) * 4096) / 1024 ** 2) +
            ((int(
                fakes.PRIVVMPAGES_2048.strip().split()[1]) *
              4096) / 1024 ** 2))
        result = ovz_utils.get_memory_mb_used()
        self.assertEqual(memory_used, result)

    def test_get_memory_mb_used_instance(self):
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute(
            'vzlist', '-H', '-o', 'ctid,privvmpages.l',
            str(fakes.INSTANCE['id']),
            run_as_root=True).AndReturn(fakes.PRIVVMPAGES_2048)
        self.mox.ReplayAll()
        memory_used = ((int(
            fakes.PRIVVMPAGES_2048.strip().split()[1]) * 4096) / 1024 ** 2)
        result = ovz_utils.get_memory_mb_used(fakes.INSTANCE['id'])
        self.assertEqual(memory_used, result)

    def test_get_local_gb_total(self):
        self.mox.StubOutWithMock(ovz_utils.os, 'statvfs')
        ovz_utils.os.statvfs(
            CONF.ovz_ve_private_dir).AndReturn(fakes.STATVFSRESULT)
        self.mox.ReplayAll()
        total = ((fakes.STATVFSRESULT.f_frsize * fakes.STATVFSRESULT.f_blocks)
                 / 1024 ** 3)
        result = ovz_utils.get_local_gb_total()
        self.assertEqual(total, result)

    def test_get_local_gb_used(self):
        self.mox.StubOutWithMock(ovz_utils.os, 'statvfs')
        ovz_utils.os.statvfs(
            CONF.ovz_ve_private_dir).AndReturn(fakes.STATVFSRESULT)
        self.mox.ReplayAll()
        used = ((fakes.STATVFSRESULT.f_frsize *
                 (fakes.STATVFSRESULT.f_blocks - fakes.STATVFSRESULT.f_bfree)
                     ) / (1024 ** 3))
        result = ovz_utils.get_local_gb_used()
        self.assertEqual(used, result)

    def test_get_hypervisor_version(self):
        self.mox.StubOutWithMock(ovz_utils.platform, 'uname')
        ovz_utils.platform.uname().AndReturn(fakes.UNAME)
        self.mox.ReplayAll()
        result = ovz_utils.get_hypervisor_version()
        self.assertEqual(result, fakes.UNAME[2])

    def test_delete_path_good(self):
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute(
            'rmdir', CONF.ovz_ve_private_dir,
            run_as_root=True).AndReturn(('', ''))
        self.mox.ReplayAll()
        self.assertTrue(ovz_utils.delete_path(CONF.ovz_ve_private_dir))

    def test_delete_path_bad(self):
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute(
            'rmdir', CONF.ovz_ve_private_dir,
            run_as_root=True).AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        self.assertFalse(ovz_utils.delete_path(CONF.ovz_ve_private_dir))

    def test_set_permissions(self):
        perms = 755
        filename = '/tmp/testfile'
        self.mox.StubOutWithMock(ovz_utils, 'execute')
        ovz_utils.execute('chmod', perms, filename, run_as_root=True)
        self.mox.ReplayAll()
        ovz_utils.set_permissions(filename, perms)

    def test_save_instance_metadata_success(self):
        self.mox.StubOutWithMock(ovz_utils.context, 'get_admin_context')
        ovz_utils.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_get')
        ovz_utils.db.instance_get(
            fakes.ADMINCONTEXT, fakes.INSTANCE['id']).AndReturn(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_metadata_update')
        ovz_utils.db.instance_metadata_update(
            fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'], fakes.METADATA, False)
        self.mox.ReplayAll()
        ovz_utils.save_instance_metadata(
            fakes.INSTANCE['id'], fakes.METAKEY, fakes.METAVALUE)

    def test_save_instance_metadata_not_found(self):
        self.mox.StubOutWithMock(ovz_utils.context, 'get_admin_context')
        ovz_utils.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_get')
        ovz_utils.db.instance_get(
            fakes.ADMINCONTEXT, fakes.INSTANCE['id']).AndReturn(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_metadata_update')
        ovz_utils.db.instance_metadata_update(
            fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'], fakes.METADATA,
            False).AndRaise(exception.InstanceNotFound)
        self.mox.ReplayAll()
        ovz_utils.save_instance_metadata(
            fakes.INSTANCE['id'], fakes.METAKEY, fakes.METAVALUE)

    def test_save_instance_metadata_not_found(self):
        self.mox.StubOutWithMock(ovz_utils.context, 'get_admin_context')
        ovz_utils.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_get')
        ovz_utils.db.instance_get(
            fakes.ADMINCONTEXT, fakes.INSTANCE['id']).AndReturn(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_metadata_update')
        ovz_utils.db.instance_metadata_update(
            fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'], fakes.METADATA,
            False).AndRaise(exception.DBError)
        self.mox.ReplayAll()
        ovz_utils.save_instance_metadata(
            fakes.INSTANCE['id'], fakes.METAKEY, fakes.METAVALUE)

    def test_read_instance_metadata_success(self):
        self.mox.StubOutWithMock(ovz_utils.context, 'get_admin_context')
        ovz_utils.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_get')
        ovz_utils.db.instance_get(
            fakes.ADMINCONTEXT, fakes.INSTANCE['id']).AndReturn(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_metadata_get')
        ovz_utils.db.instance_metadata_get(
            fakes.ADMINCONTEXT, fakes.INSTANCE['uuid']).AndReturn(
                fakes.METADATA)
        self.mox.ReplayAll()
        meta = ovz_utils.read_instance_metadata(fakes.INSTANCE['id'])
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta[fakes.METAKEY], fakes.METAVALUE)

    def test_read_instance_metadata_not_found(self):
        self.mox.StubOutWithMock(ovz_utils.context, 'get_admin_context')
        ovz_utils.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_get')
        ovz_utils.db.instance_get(
            fakes.ADMINCONTEXT, fakes.INSTANCE['id']).AndReturn(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_metadata_get')
        ovz_utils.db.instance_metadata_get(
            fakes.ADMINCONTEXT, fakes.INSTANCE['uuid']).AndRaise(
                exception.InstanceNotFound)
        self.mox.ReplayAll()
        meta = ovz_utils.read_instance_metadata(fakes.INSTANCE['id'])
        self.assertTrue(isinstance(meta, dict))
        self.assertTrue(len(meta) == 0)

    def test_read_instance_metadata_dberror(self):
        self.mox.StubOutWithMock(ovz_utils.context, 'get_admin_context')
        ovz_utils.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_get')
        ovz_utils.db.instance_get(
            fakes.ADMINCONTEXT, fakes.INSTANCE['id']).AndReturn(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_utils.db, 'instance_metadata_get')
        ovz_utils.db.instance_metadata_get(
            fakes.ADMINCONTEXT, fakes.INSTANCE['uuid']).AndRaise(
            exception.DBError)
        self.mox.ReplayAll()
        meta = ovz_utils.read_instance_metadata(fakes.INSTANCE['id'])
        self.assertTrue(isinstance(meta, dict))
        self.assertTrue(len(meta) == 0)
