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
import socket
from nova import exception
from nova import test
from nova.compute import power_state
from nova.tests.openvz import fakes
from nova.virt.openvz import driver as openvz_conn
from nova.virt.openvz import network as openvz_net
from nova.virt.openvz import volume_ops as openvz_volume_ops
from nova.openstack.common import cfg
from nova.virt.openvz.file_ext.shutdown import OVZShutdownFile
from nova.virt.openvz.file_ext.boot import OVZBootFile
from nova.virt.openvz.network_drivers.network_bridge import\
    OVZNetworkBridgeDriver
from nova.virt.openvz.network import *
from nova.virt.openvz import utils as ovz_utils
from StringIO import StringIO

CONF = cfg.CONF


class OpenVzDriverTestCase(test.TestCase):
    def setUp(self):
        super(OpenVzDriverTestCase, self).setUp()
        try:
            CONF.injected_network_template
        except AttributeError as err:
            CONF.register_opt(cfg.StrOpt('injected_network_template',
                default='nova/virt/interfaces.template',
                help='Stub for network template for testing purposes')
            )
        CONF.use_ipv6 = False
        self.fake_file = mox.MockAnything()
        self.fake_file.readlines().AndReturn(fakes.FILECONTENTS.split())
        self.fake_file.writelines(mox.IgnoreArg())
        self.fake_file.read().AndReturn(fakes.FILECONTENTS)

    def test_start_success(self):
        # Testing happy path :-D
        # Mock the objects needed for this test to succeed.
        self.mox.StubOutWithMock(openvz_conn, 'OVZBootFile')
        openvz_conn.OVZBootFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZBootFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', fakes.INSTANCE['id'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
            fakes.INSTANCE['uuid'],
            {'power_state': power_state.RUNNING})
        # Start the tests
        self.mox.ReplayAll()
        # Create our connection object.  For all intents and purposes this is
        # a real OpenVzDriver object.
        conn = openvz_conn.OpenVzDriver(True)
        conn._start(fakes.INSTANCE)

    def test_start_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', fakes.INSTANCE['id'],
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn._start, fakes.INSTANCE)

    def test_list_instances_success(self):
        # Testing happy path of OpenVzDriver.list_instances()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '--no-header', '--output',
            'ctid', run_as_root=True).AndReturn(
            (fakes.VZLIST, fakes.ERRORMSG))
        # Start test
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        vzs = conn.list_instances()
        self.assertEqual(vzs.__class__, list)

    def test_list_instances_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '--no-header', '--output',
            'ctid', run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        # Start test
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable, conn.list_instances)

    def test_create_vz_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'create', fakes.INSTANCE['id'],
            '--ostemplate', fakes.INSTANCE['image_ref'],
            run_as_root=True).AndReturn(
            ('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._create_vz(fakes.INSTANCE)

    def test_create_vz_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'create', fakes.INSTANCE['id'],
            '--ostemplate', fakes.INSTANCE['image_ref'],
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn._create_vz, fakes.INSTANCE)

    def test_set_vz_os_hint_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--ostemplate', 'ubuntu', run_as_root=True)\
        .AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._set_vz_os_hint(fakes.INSTANCE)

    def test_set_vz_os_hint_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--ostemplate', 'ubuntu', run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn._set_vz_os_hint, fakes.INSTANCE)

    def test_configure_vz_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--applyconfig', 'basic', run_as_root=True)\
        .AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._configure_vz(fakes.INSTANCE)

    def test_configure_vz_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--applyconfig', 'basic', run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn._configure_vz, fakes.INSTANCE)

    def test_stop_success(self):
        self.mox.StubOutWithMock(openvz_conn, 'OVZShutdownFile')
        openvz_conn.OVZShutdownFile(fakes.INSTANCE['id'],
            mox.IgnoreArg()).AndReturn(
            fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', fakes.INSTANCE['id'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
            fakes.INSTANCE['uuid'],
            {'power_state': power_state.SHUTDOWN})
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._stop(fakes.INSTANCE)

    def test_stop_failure_on_exec(self):
        self.mox.StubOutWithMock(openvz_conn, 'OVZShutdownFile')
        openvz_conn.OVZShutdownFile(fakes.INSTANCE['id'],
            mox.IgnoreArg()).AndReturn(
            fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', fakes.INSTANCE['id'],
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn._stop, fakes.INSTANCE)

    def test_stop_failure_on_db_access(self):
        self.mox.StubOutWithMock(openvz_conn, 'OVZShutdownFile')
        openvz_conn.OVZShutdownFile(fakes.INSTANCE['id'],
            mox.IgnoreArg()).AndReturn(
            fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', fakes.INSTANCE['id'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
            fakes.INSTANCE['uuid'],
            {'power_state': power_state.SHUTDOWN})\
        .AndRaise(exception.DBError('FAIL'))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.DBError,
            conn._stop, fakes.INSTANCE)

    def test_set_vmguarpages_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--vmguarpages', mox.IgnoreArg(),
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._set_vmguarpages(fakes.INSTANCE,
            conn._calc_pages(fakes.INSTANCE['memory_mb']))

    def test_set_vmguarpages_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--vmguarpages', mox.IgnoreArg(),
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn._set_vmguarpages, fakes.INSTANCE,
            conn._calc_pages(fakes.INSTANCE['memory_mb']))

    def test_set_privvmpages_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--privvmpages', mox.IgnoreArg(),
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._set_privvmpages(fakes.INSTANCE,
            conn._calc_pages(fakes.INSTANCE['memory_mb']))

    def test_set_privvmpages_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--privvmpages', mox.IgnoreArg(),
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn._set_privvmpages, fakes.INSTANCE,
            conn._calc_pages(fakes.INSTANCE['memory_mb']))

    def test_set_kmemsize_success(self):
        kmemsize = ((fakes.INSTANCE['memory_mb'] * 1024) * 1024)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--kmemsize', mox.IgnoreArg(),
            run_as_root=True).AndReturn(('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._set_kmemsize(fakes.INSTANCE, kmemsize)

    def test_set_kmemsize_failure(self):
        kmemsize = ((fakes.INSTANCE['memory_mb'] * 1024) * 1024)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--kmemsize', mox.IgnoreArg(),
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn._set_kmemsize, fakes.INSTANCE, kmemsize)

    def test_set_onboot_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--onboot',
            'no', '--save', run_as_root=True).AndReturn(
            ('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._set_onboot(fakes.INSTANCE)

    def test_set_onboot_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--onboot',
            'no', '--save', run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn._set_onboot, fakes.INSTANCE)

    def test_set_cpuunits_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--cpuunits', mox.IgnoreArg(),
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(fakes.RES_PERCENT)
        self.mox.StubOutWithMock(openvz_conn, 'ovz_utils')
        openvz_conn.ovz_utils = ovz_utils
        self.mox.ReplayAll()
        conn._set_cpuunits(fakes.INSTANCE,
            conn._percent_of_resource(fakes.INSTANCETYPE['memory_mb'])
        )

    def test_set_cpuunits_over_subscribe(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--cpuunits', mox.IgnoreArg(),
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(openvz_conn, 'ovz_utils')
        openvz_conn.ovz_utils = ovz_utils
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(fakes.RES_OVER_PERCENT)
        self.mox.ReplayAll()
        conn._set_cpuunits(fakes.INSTANCE,
            conn._percent_of_resource(fakes.INSTANCETYPE['memory_mb'])
        )

    def test_set_cpuunits_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--cpuunits', mox.IgnoreArg(),
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(fakes.RES_PERCENT)
        self.mox.StubOutWithMock(openvz_conn, 'ovz_utils')
        openvz_conn.ovz_utils = ovz_utils
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable, conn._set_cpuunits,
            fakes.INSTANCE,
            conn._percent_of_resource(fakes.INSTANCETYPE['memory_mb']))

    def test_set_cpulimit_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--cpulimit',
            fakes.UTILITY['CPULIMIT'] * fakes.RES_PERCENT,
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(
            fakes.RES_PERCENT
        )
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = fakes.UTILITY
        self.mox.ReplayAll()
        conn._set_cpulimit(fakes.INSTANCE,
            conn._percent_of_resource(fakes.INSTANCETYPE['memory_mb'])
        )

    def test_set_cpulimit_over_subscribe(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--cpulimit', fakes.UTILITY['CPULIMIT'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(
            fakes.RES_OVER_PERCENT
        )
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = fakes.UTILITY
        self.mox.ReplayAll()
        conn._set_cpulimit(fakes.INSTANCE,
            conn._percent_of_resource(fakes.INSTANCETYPE['memory_mb'])
        )

    def test_set_cpulimit_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--cpulimit',
            fakes.UTILITY['CPULIMIT'] * fakes.RES_PERCENT,
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(fakes.RES_PERCENT)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = fakes.UTILITY
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable,
            conn._set_cpulimit, fakes.INSTANCE,
            conn._percent_of_resource(fakes.INSTANCETYPE['memory_mb']))

    def test_set_cpus_success(self):
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'],
            '--save', '--cpus',
            mox.IgnoreArg(), run_as_root=True
        ).AndReturn(('', fakes.ERRORMSG))
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = fakes.UTILITY
        self.mox.ReplayAll()
        conn._set_cpus(fakes.INSTANCE, fakes.INSTANCETYPE['vcpus'])

    def test_set_cpus_failure(self):
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--cpus', mox.IgnoreArg(),
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = fakes.UTILITY
        self.assertRaises(exception.InstanceUnacceptable, conn._set_cpus,
            fakes.INSTANCE, fakes.INSTANCETYPE['vcpus'])

    def test_calc_pages_success(self):
        # this test is a little sketchy because it is testing the default
        # values of memory for instance type id 1.  if this value changes then
        # we will have a mismatch.

        # TODO(imsplitbit): make this work better.  This test is very brittle
        # because it relies on the default memory size for flavor 1 never
        # changing.  Need to fix this.
        conn = openvz_conn.OpenVzDriver(False)
        self.assertEqual(conn._calc_pages(fakes.INSTANCE['memory_mb']),
            262144)

    def test_get_cpuunits_capability_success(self):
        self.mox.StubOutWithMock(ovz_utils.utils, 'execute')
        ovz_utils.utils.execute('vzcpucheck', run_as_root=True).AndReturn(
            (fakes.CPUCHECKNOCONT, fakes.ERRORMSG))
        self.mox.ReplayAll()
        ovz_utils.get_cpuunits_capability()

    def test_get_cpuunits_capability_failure(self):
        self.mox.StubOutWithMock(ovz_utils.utils, 'execute')
        ovz_utils.utils.execute('vzcpucheck', run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable,
            ovz_utils.get_cpuunits_capability)

    def test_get_cpuunits_usage_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzcpucheck', '-v',
            run_as_root=True).AndReturn(
            (fakes.CPUCHECKCONT, fakes.ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._get_cpuunits_usage()

    def test_get_cpuunits_usage_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzcpucheck', '-v',
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable, conn._get_cpuunits_usage)

    def test_percent_of_resource(self):
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = fakes.UTILITY
        self.mox.ReplayAll()
        self.assertEqual(float,
            type(conn._percent_of_resource(fakes.INSTANCE['memory_mb']))
        )

    def test_set_ioprio_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--ioprio', mox.IgnoreArg(), run_as_root=True).AndReturn(
            ('', fakes.ERRORMSG))
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(fakes.INSTANCE['memory_mb']).AndReturn(.50)
        self.mox.ReplayAll()
        conn._set_ioprio(fakes.INSTANCE,
            conn._percent_of_resource(fakes.INSTANCE['memory_mb']))

    def test_set_ioprio_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--ioprio', mox.IgnoreArg(), run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(fakes.INSTANCE['memory_mb']).AndReturn(.50)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable,
            conn._set_ioprio, fakes.INSTANCE,
            conn._percent_of_resource(fakes.INSTANCE['memory_mb']))

    def test_set_diskspace_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--diskspace', mox.IgnoreArg(),
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._set_diskspace(fakes.INSTANCE, fakes.INSTANCETYPE)

    def test_set_diskspace_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--diskspace', mox.IgnoreArg(), run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable, conn._set_diskspace,
            fakes.INSTANCE, fakes.INSTANCETYPE)

    def test_attach_volumes_success(self):
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, 'attach_volume')
        conn.attach_volume(fakes.BDM['block_device_mapping'][0]['connection_info'], fakes.INSTANCE['name'], fakes.BDM['block_device_mapping'][0]['mount_device'])
        self.mox.ReplayAll()
        conn._attach_volumes(fakes.INSTANCE['name'], fakes.BDM)

    def test_gratuitous_arp_all_addresses(self):
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_send_garp')
        conn._send_garp(fakes.INSTANCE['id'],
            mox.IgnoreArg(),
            mox.IgnoreArg()).MultipleTimes()
        self.mox.ReplayAll()
        conn._gratuitous_arp_all_addresses(fakes.INSTANCE, fakes.NETWORKINFO)

    def test_send_garp_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', fakes.INSTANCE['id'], 'arping',
            '-q', '-c', '5', '-A', '-I',
            fakes.NETWORKINFO[0][0]['bridge_interface'],
            fakes.NETWORKINFO[0][1]['ips'][0]['ip'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn._send_garp(fakes.INSTANCE['id'], fakes.NETWORKINFO[0][1]['ips'][0]['ip'],
            fakes.NETWORKINFO[0][0]['bridge_interface'])

    def test_send_garp_faiure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', fakes.INSTANCE['id'], 'arping',
            '-q', '-c', '5', '-A', '-I',
            fakes.NETWORKINFO[0][0]['bridge_interface'],
            fakes.NETWORKINFO[0][1]['ips'][0]['ip'],
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable, conn._send_garp, fakes.INSTANCE['id'], fakes.NETWORKINFO[0][1]['ips'][0]['ip'],
            fakes.NETWORKINFO[0][0]['bridge_interface'])

    def test_init_host_success(self):
        self.mox.StubOutWithMock(openvz_conn, 'OVZTcRules')
        openvz_conn.OVZTcRules().AndReturn(fakes.FakeOVZTcRules)
        self.mox.StubOutWithMock(ovz_utils.utils, 'execute')
        ovz_utils.utils.execute('vzcpucheck', run_as_root=True).AndReturn(
            (fakes.CPUCHECKNOCONT, fakes.ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get_all_by_host')
        openvz_conn.db.instance_get_all_by_host(mox.IgnoreArg(),
            socket.gethostname())\
        .MultipleTimes().AndReturn(fakes.INSTANCES)
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, '_refresh_host_stats')
        ovz_conn._refresh_host_stats()
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(fakes.INSTANCE).MultipleTimes()\
        .AndReturn(fakes.GOODSTATUS)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            {'power_state': power_state.RUNNING}).MultipleTimes()
        self.mox.StubOutWithMock(ovz_conn, '_get_cpulimit')
        ovz_conn._get_cpulimit()
        self.mox.ReplayAll()
        ovz_conn.init_host()

    def test_init_host_not_found(self):
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get_all_by_host')
        openvz_conn.db.instance_get_all_by_host(mox.IgnoreArg(),
            socket.gethostname())\
        .AndReturn(fakes.INSTANCES)
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(fakes.INSTANCE).AndRaise(exception.NotFound)
        #self.mox.StubOutWithMock(openvz_conn.db, 'instance_destroy')
        #openvz_conn.db.instance_destroy(fakes.ADMINCONTEXT, fakes.INSTANCE['id'])
        self.mox.ReplayAll()
        self.assertRaises(exception.NotFound, ovz_conn.init_host)

    def test_set_hostname_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--hostname', fakes.INSTANCE['hostname'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        ovz_conn._set_hostname(fakes.INSTANCE)

    def test_set_hostname_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--hostname', fakes.INSTANCE['hostname'],
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            ovz_conn._set_hostname, fakes.INSTANCE)

    def test_set_name_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--name', fakes.INSTANCE['name'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        ovz_conn._set_name(fakes.INSTANCE)

    def test_set_name_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INSTANCE['id'], '--save',
            '--name', fakes.INSTANCE['name'],
            run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            ovz_conn._set_name, fakes.INSTANCE)

    def test_find_by_name_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '-H', '-o', 'ctid,status,name',
            '--all', '--name_filter', fakes.INSTANCE['name'],
            run_as_root=True).AndReturn((fakes.VZLISTDETAIL, fakes.ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        meta = ovz_conn._find_by_name(fakes.INSTANCE['name'])
        self.assertEqual(fakes.INSTANCE['hostname'], meta['name'])
        self.assertEqual(str(fakes.INSTANCE['id']), meta['id'])
        self.assertEqual('running', meta['state'])

    def test_find_by_name_not_found(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '-H', '-o', 'ctid,status,name',
            '--all', '--name_filter', fakes.INSTANCE['name'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.NotFound, ovz_conn._find_by_name,
            fakes.INSTANCE['name'])

    def test_find_by_name_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '-H', '-o', 'ctid,status,name',
            '--all', '--name_filter', fakes.INSTANCE['name'],
            run_as_root=True).AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            ovz_conn._find_by_name, fakes.INSTANCE['name'])

    def test_plug_vifs(self):
        self.mox.StubOutWithMock(openvz_net, 'OVZShutdownFile')
        openvz_net.OVZShutdownFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_net, 'OVZBootFile')
        openvz_net.OVZBootFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZBootFile(fakes.INSTANCE['id'], 700))
        ovz_conn = openvz_conn.OpenVzDriver(False)
        ovz_conn.vif_driver = mox.MockAnything()
        ovz_conn.vif_driver.plug(fakes.INSTANCE, mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.StubOutWithMock(openvz_conn.OVZNetworkInterfaces, 'add')
        openvz_conn.OVZNetworkInterfaces.add()
        self.mox.ReplayAll()
        ovz_conn.plug_vifs(fakes.INSTANCE, fakes.NETWORKINFO)

    def test_reboot_success(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
        .AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn, 'OVZShutdownFile')
        openvz_conn.OVZShutdownFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn, 'OVZBootFile')
        openvz_conn.OVZBootFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZBootFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'restart', fakes.INSTANCE['id'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(fakes.INSTANCE).MultipleTimes()\
        .AndReturn(fakes.GOODSTATUS)
        self.mox.ReplayAll()
        timer = ovz_conn.reboot(fakes.INSTANCE, fakes.NETWORKINFO, 'hard')
        timer.wait()

    def test_reboot_fail_in_get_info(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
        .AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn, 'OVZShutdownFile')
        openvz_conn.OVZShutdownFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        #self.mox.StubOutWithMock(openvz_conn, 'OVZBootFile')
        #openvz_conn.OVZBootFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZBootFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'restart', fakes.INSTANCE['id'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(fakes.INSTANCE).AndRaise(exception.NotFound)
        self.mox.ReplayAll()
        #timer = self.assertRaises(exception.NotFound, ovz_conn.reboot, fakes.INSTANCE, fakes.NETWORKINFO, 'hard')
        timer = ovz_conn.reboot(fakes.INSTANCE, fakes.NETWORKINFO, 'hard')
        self.assertRaises(exception.NotFound, timer.wait)

    def test_reboot_fail_because_not_found(self):
        self.mox.StubOutWithMock(openvz_conn, 'OVZShutdownFile')
        openvz_conn.OVZShutdownFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        #self.mox.StubOutWithMock(openvz_conn, 'OVZBootFile')
        #openvz_conn.OVZBootFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZBootFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
        .AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'restart', fakes.INSTANCE['id'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(fakes.INSTANCE).AndReturn(fakes.NOSTATUS)
        self.mox.ReplayAll()
        timer = ovz_conn.reboot(fakes.INSTANCE, fakes.NETWORKINFO, 'hard')
        timer.wait()

    def test_reboot_failure(self):
        self.mox.StubOutWithMock(openvz_conn, 'OVZShutdownFile')
        openvz_conn.OVZShutdownFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            {'power_state': power_state.PAUSED})
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'restart', fakes.INSTANCE['id'],
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable, ovz_conn.reboot,
            fakes.INSTANCE, fakes.NETWORKINFO, 'hard')

    def test_set_admin_password_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', fakes.INSTANCE['id'], 'echo',
            'root:%s' % fakes.ROOTPASS, '|', 'chpasswd',
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        ovz_conn.set_admin_password(fakes.ADMINCONTEXT, fakes.INSTANCE['id'], fakes.ROOTPASS)

    def test_set_admin_password_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', fakes.INSTANCE['id'], 'echo',
            'root:%s' % fakes.ROOTPASS, '|', 'chpasswd',
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            ovz_conn.set_admin_password,
            fakes.ADMINCONTEXT, fakes.INSTANCE['id'], fakes.ROOTPASS)

    def test_pause_success(self):
        self.mox.StubOutWithMock(openvz_conn, 'OVZShutdownFile')
        openvz_conn.OVZShutdownFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', fakes.INSTANCE['id'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
            fakes.INSTANCE['uuid'],
            {'power_state': power_state.SHUTDOWN})
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn.pause(fakes.INSTANCE)

    def test_pause_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', fakes.INSTANCE['id'],
            run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.StubOutWithMock(openvz_conn, 'OVZShutdownFile')
        openvz_conn.OVZShutdownFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZShutdownFile(fakes.INSTANCE['id'], 700))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn.pause, fakes.INSTANCE)

    def test_suspend_success(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'chkpnt', fakes.INSTANCE['id'],
            '--suspend', run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT,
            fakes.INSTANCE['uuid'],
            {'power_state': power_state.SUSPENDED})
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        conn.suspend(fakes.INSTANCE)

    def test_suspend_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'chkpnt', fakes.INSTANCE['id'],
            '--suspend', run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn.suspend, fakes.INSTANCE)

    def test_unpause_success(self):
        self.mox.StubOutWithMock(openvz_conn, 'OVZBootFile')
        openvz_conn.OVZBootFile(fakes.INSTANCE['id'], mox.IgnoreArg()).AndReturn(fakes.FakeOVZBootFile(fakes.INSTANCE['id'], 700))
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', fakes.INSTANCE['id'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
            fakes.INSTANCE['uuid'],
            {'power_state': power_state.RUNNING})

        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(True)
        conn.unpause(fakes.INSTANCE)

    def test_unpause_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', fakes.INSTANCE['id'],
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn.unpause, fakes.INSTANCE)

    def test_resume_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'chkpnt', fakes.INSTANCE['id'],
            '--resume', run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
            fakes.INSTANCE['uuid'],
            {'power_state': power_state.RUNNING})

        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(True)
        conn.resume(fakes.INSTANCE, fakes.NETWORKINFO)

    def test_resume_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'chkpnt', fakes.INSTANCE['id'],
            '--resume', run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzDriver(False)
        self.assertRaises(exception.InstanceUnacceptable,
            conn.resume, fakes.INSTANCE, None, None)

    def test_destroy_fail_on_exec(self):
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, '_stop')
        ovz_conn._stop(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(fakes.INSTANCE).AndReturn(fakes.GOODSTATUS)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'destroy', fakes.INSTANCE['id'],
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable, ovz_conn.destroy,
            fakes.INSTANCE, fakes.NETWORKINFO)

    def test_destroy_success(self):
        ovz_conn = openvz_conn.OpenVzDriver(False)
        ovz_conn.vif_driver = mox.MockAnything()
        ovz_conn.vif_driver.unplug(fakes.INSTANCE, mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.StubOutWithMock(ovz_conn, '_stop')
        ovz_conn._stop(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(fakes.INSTANCE).AndReturn(fakes.GOODSTATUS)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'destroy', fakes.INSTANCE['id'],
            run_as_root=True).AndRaise(exception.InstanceNotFound)
        self.mox.StubOutWithMock(ovz_conn, '_clean_orphaned_directories')
        ovz_conn._clean_orphaned_directories(fakes.INSTANCE['id'])
        self.mox.StubOutWithMock(ovz_conn, '_clean_orphaned_files')
        ovz_conn._clean_orphaned_files(fakes.INSTANCE['id'])
        self.mox.StubOutWithMock(openvz_volume_ops.OVZInstanceVolumeOps, 'detach_all_volumes')
        openvz_volume_ops.OVZInstanceVolumeOps(fakes.INSTANCE).detach_all_volumes()
        self.mox.ReplayAll()
        ovz_conn.destroy(fakes.INSTANCE, fakes.NETWORKINFO, fakes.BDM)

    def test_get_info_running_state(self):
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(fakes.INSTANCE['name']).AndReturn(fakes.FINDBYNAME)
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(fakes.INSTANCE)
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.RUNNING)

    def test_get_info_shutdown_state(self):
        # Create a copy of instance to overwrite it's state
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().AndReturn(fakes.ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            {'power_state': power_state.SHUTDOWN})
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(fakes.INSTANCE['name']).AndReturn(fakes.FINDBYNAMESHUTDOWN)
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(fakes.INSTANCE)
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.SHUTDOWN)

    def test_get_info_no_state(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
        .AndReturn(fakes.ADMINCONTEXT)
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT,
            fakes.INSTANCE['uuid'], {'power_state': power_state.NOSTATE})
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(fakes.INSTANCE['name']).AndReturn(fakes.FINDBYNAMENOSTATE)
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(fakes.INSTANCE)
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.NOSTATE)

    def test_get_info_state_is_None(self):
        BADFINDBYNAME = fakes.FINDBYNAME.copy()
        BADFINDBYNAME['state'] = None
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
        .AndReturn(fakes.ADMINCONTEXT)
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(fakes.INSTANCE['name']).AndReturn(BADFINDBYNAME)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            mox.IgnoreArg())
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(fakes.INSTANCE)
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.NOSTATE)

    def test_get_info_state_is_shutdown(self):
        BADFINDBYNAME = fakes.FINDBYNAME.copy()
        BADFINDBYNAME['state'] = 'shutdown'
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
        .AndReturn(fakes.ADMINCONTEXT)
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(fakes.INSTANCE['name']).AndReturn(BADFINDBYNAME)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            mox.IgnoreArg())
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(fakes.INSTANCE)
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.SHUTDOWN)

    def test_get_info_notfound(self):
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(fakes.INSTANCE['name']).AndRaise(exception.NotFound)
        self.mox.ReplayAll()
        self.assertRaises(exception.NotFound, ovz_conn.get_info,
            fakes.INSTANCE)

    def test_percent_of_memory_over_subscribe(self):
        # Force the utility storage to have really low memory so as to test the
        # code that doesn't allow more than a 1.x multiplier.
        ovz_conn = openvz_conn.OpenVzDriver(False)
        ovz_conn.utility['MEMORY_MB'] = 16
        self.mox.StubOutWithMock(ovz_utils, 'get_memory_mb_total')
        ovz_utils.get_memory_mb_total().AndReturn(1024)
        self.mox.ReplayAll()
        self.assertEqual(1,
            ovz_conn._percent_of_resource(fakes.INSTANCE['memory_mb']))

    def test_percent_of_memory_normal_subscribe(self):
        ovz_conn = openvz_conn.OpenVzDriver(False)
        ovz_conn.utility['MEMORY_MB'] = 16384
        self.mox.ReplayAll()
        self.assertTrue(
            ovz_conn._percent_of_resource(fakes.INSTANCE['memory_mb']) < 1)

    def test_get_cpulimit_success(self):
        self.mox.StubOutWithMock(ovz_utils.multiprocessing, 'cpu_count')
        ovz_utils.multiprocessing.cpu_count().AndReturn(2)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        ovz_conn._get_cpulimit()
        self.assertEqual(ovz_conn.utility['CPULIMIT'], 200)

    def test_spawn_success(self):
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            mox.IgnoreArg())
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, '_get_cpuunits_usage')
        ovz_conn._get_cpuunits_usage()
        self.mox.StubOutWithMock(ovz_conn, '_cache_image')
        ovz_conn._cache_image(fakes.ADMINCONTEXT, fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_create_vz')
        ovz_conn._create_vz(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_vz_os_hint')
        ovz_conn._set_vz_os_hint(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_configure_vz')
        ovz_conn._configure_vz(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_onboot')
        ovz_conn._set_onboot(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_name')
        ovz_conn._set_name(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, 'plug_vifs')
        ovz_conn.plug_vifs(fakes.INSTANCE, fakes.NETWORKINFO)
        self.mox.StubOutWithMock(ovz_conn, '_set_hostname')
        ovz_conn._set_hostname(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_instance_size')
        ovz_conn._set_instance_size(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_attach_volumes')
        ovz_conn._attach_volumes(fakes.INSTANCE['name'], fakes.BDM)
        self.mox.StubOutWithMock(ovz_conn, '_start')
        ovz_conn._start(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_initial_secure_host')
        ovz_conn._initial_secure_host(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_gratuitous_arp_all_addresses')
        ovz_conn._gratuitous_arp_all_addresses(fakes.INSTANCE, fakes.NETWORKINFO)
        self.mox.StubOutWithMock(ovz_conn, 'set_admin_password')
        ovz_conn.set_admin_password(fakes.ADMINCONTEXT, fakes.INSTANCE['id'],
            fakes.INSTANCE['admin_pass'])
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(fakes.INSTANCE).AndReturn(fakes.GOODSTATUS)
        self.mox.ReplayAll()
        timer = ovz_conn.spawn(fakes.ADMINCONTEXT, fakes.INSTANCE, None, None, fakes.ROOTPASS, fakes.NETWORKINFO, fakes.BDM)
        timer.wait()

    def test_spawn_failure(self):
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(fakes.ADMINCONTEXT, fakes.INSTANCE['uuid'],
            mox.IgnoreArg()).MultipleTimes()
        ovz_conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(ovz_conn, '_get_cpuunits_usage')
        ovz_conn._get_cpuunits_usage()
        self.mox.StubOutWithMock(ovz_conn, '_cache_image')
        ovz_conn._cache_image(fakes.ADMINCONTEXT, fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_create_vz')
        ovz_conn._create_vz(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_vz_os_hint')
        ovz_conn._set_vz_os_hint(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_configure_vz')
        ovz_conn._configure_vz(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_onboot')
        ovz_conn._set_onboot(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_name')
        ovz_conn._set_name(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, 'plug_vifs')
        ovz_conn.plug_vifs(fakes.INSTANCE, fakes.NETWORKINFO)
        self.mox.StubOutWithMock(ovz_conn, '_set_hostname')
        ovz_conn._set_hostname(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_instance_size')
        ovz_conn._set_instance_size(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_attach_volumes')
        ovz_conn._attach_volumes(fakes.INSTANCE['name'], fakes.BDM)
        self.mox.StubOutWithMock(ovz_conn, '_start')
        ovz_conn._start(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_initial_secure_host')
        ovz_conn._initial_secure_host(fakes.INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_gratuitous_arp_all_addresses')
        ovz_conn._gratuitous_arp_all_addresses(fakes.INSTANCE, fakes.NETWORKINFO)
        self.mox.StubOutWithMock(ovz_conn, 'set_admin_password')
        ovz_conn.set_admin_password(fakes.ADMINCONTEXT, fakes.INSTANCE['id'],
            fakes.INSTANCE['admin_pass'])
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(fakes.INSTANCE).AndRaise(exception.NotFound)
        self.mox.ReplayAll()
        timer = ovz_conn.spawn(fakes.ADMINCONTEXT, fakes.INSTANCE, None, None, fakes.ROOTPASS, fakes.NETWORKINFO, fakes.BDM)
        timer.wait()
