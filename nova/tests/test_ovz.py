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
from nova import flags
from nova import test
from nova.compute import power_state
from nova.virt.openvz import connection as openvz_conn
from nova.openstack.common import cfg
from nova.virt.openvz.file import *
from nova.virt.openvz.network_drivers.network_bridge import \
    OVZNetworkBridgeDriver
from nova.virt.openvz.mount import *
from nova.virt.openvz.network import *
from nova.virt.openvz import utils as ovz_utils
from StringIO import StringIO

FLAGS = flags.FLAGS

ROOTPASS = '2s3cUr3'

USER = {'user': 'admin', 'role': 'admin', 'id': 1}

PROJECT = {'name': 'test', 'id': 2}

ADMINCONTEXT = {'context': 'admin'}

INSTANCE = {
    "image_ref": 1,
    "name": "instance-00001002",
    "instance_type_id": 1,
    "id": 1002,
    "hostname": "test.foo.com",
    "power_state": power_state.RUNNING,
    "admin_pass": ROOTPASS,
    "user_id": USER['id'],
    "project_id": PROJECT['id'],
    "memory_mb": 1024,
    "volumes": [
        {
            "uuid": "776E384C-47FF-433D-953B-61272EFDABE1",
            "mountpoint": "/var/lib/mysql"
        },
        {
            "uuid": False,
            "dev": "/dev/sda1",
            "mountpoint": "/var/tmp"
        }
    ]
}

IMAGEPATH = '%s/%s.tar.gz' % \
            (FLAGS.ovz_image_template_dir, INSTANCE['image_ref'])

INSTANCETYPE = {
    'vcpus': 1,
    'name': 'm1.small',
    'memory_mb': 2048,
    'swap': 0,
    'root_gb': 20
}

INSTANCES = [INSTANCE, INSTANCE]

RES_PERCENT = .50

RES_OVER_PERCENT = 1.50

VZLIST = "\t1001\n\t%d\n\t1003\n\t1004\n" % (INSTANCE['id'],)

VZLISTDETAIL = "        %d         10 running   -               %s" \
    % (INSTANCE['id'], INSTANCE['hostname'])

FINDBYNAME = VZLISTDETAIL.split()
FINDBYNAME = {'name': FINDBYNAME[4], 'id': int(FINDBYNAME[0]),
              'state': FINDBYNAME[2]}

VZNAME = """\tinstance-00001001\n"""

VZNAMES = """\tinstance-00001001\n\t%s
              \tinstance-00001003\n\tinstance-00001004\n""" % (
    INSTANCE['name'],)

GOODSTATUS = {
    'state': power_state.RUNNING,
    'max_mem': 0,
    'mem': 0,
    'num_cpu': 0,
    'cpu_time': 0
}

NOSTATUS = {
    'state': power_state.NOSTATE,
    'max_mem': 0,
    'mem': 0,
    'num_cpu': 0,
    'cpu_time': 0
}

ERRORMSG = "vz command ran but output something to stderr"

MEMINFO = """MemTotal:         506128 kB
MemFree:          291992 kB
Buffers:           44512 kB
Cached:            64708 kB
SwapCached:            0 kB
Active:           106496 kB
Inactive:          62948 kB
Active(anon):      62108 kB
Inactive(anon):      496 kB
Active(file):      44388 kB
Inactive(file):    62452 kB
Unevictable:        2648 kB
Mlocked:            2648 kB
SwapTotal:       1477624 kB
SwapFree:        1477624 kB
Dirty:                 0 kB
Writeback:             0 kB
AnonPages:         62908 kB
Mapped:            14832 kB
Shmem:               552 kB
Slab:              27988 kB
SReclaimable:      17280 kB
SUnreclaim:        10708 kB
KernelStack:        1448 kB
PageTables:         3092 kB
NFS_Unstable:          0 kB
Bounce:                0 kB
WritebackTmp:          0 kB
CommitLimit:     1730688 kB
Committed_AS:     654760 kB
VmallocTotal:   34359738367 kB
VmallocUsed:       24124 kB
VmallocChunk:   34359711220 kB
HardwareCorrupted:     0 kB
HugePages_Total:       0
HugePages_Free:        0
HugePages_Rsvd:        0
HugePages_Surp:        0
Hugepagesize:       2048 kB
DirectMap4k:        8128 kB
DirectMap2M:      516096 kB
"""

PROCINFO = """
processor	: 0
vendor_id	: AuthenticAMD
cpu family	: 16
model		: 4
model name	: Dual-Core AMD Opteron(tm) Processor 2374 HE

processor	: 1
vendor_id	: AuthenticAMD
cpu family	: 16
model		: 4
model name	: Dual-Core AMD Opteron(tm) Processor 2374 HE
"""

UTILITY = {
    'CTIDS': {
        1: {

        }
    },
    'UTILITY': 10000,
    'TOTAL': 1000,
    'UNITS': 100000,
    'MEMORY_MB': 512000,
    'CPULIMIT': 2400
}

CPUUNITSCAPA = {
    'total': 500000,
    'subscribed': 1000
}

CPUCHECKCONT = """VEID      CPUUNITS
-------------------------
0       1000
26      25000
27      25000
Current CPU utilization: 51000
Power of the node: 758432
"""

CPUCHECKNOCONT = """Current CPU utilization: 51000
Power of the node: 758432
"""

FILECONTENTS = """mount UUID=FEE52433-F693-448E-B6F6-AA6D0124118B /mnt/foo
        mount --bind /mnt/foo /vz/private/1/mnt/foo
        """

NETWORKINFO = [
    [
        {
            u'bridge': u'br100',
            u'multi_host': False,
            u'bridge_interface': u'eth0',
            u'vlan': None,
            u'id': 1,
            u'injected': True,
            u'cidr': u'10.0.2.0/24',
            u'cidr_v6': None
        },
        {
            u'should_create_bridge': True,
            u'dns': [
                    u'192.168.2.1'
                ],
            u'label': u'usernet',
            u'broadcast': u'10.0.2.255',
            u'ips': [
                    {
                        u'ip': u'10.0.2.16',
                        u'netmask': u'255.255.255.0',
                        u'enabled':
                        u'1'
                    }
                ],
            u'mac': u'02:16:3e:0c:2c:08',
            u'rxtx_cap': 0,
            u'should_create_vlan': True,
            u'dhcp_server': u'10.0.2.2',
            u'gateway': u'10.0.2.2'
        }
    ],
    [
        {
            u'bridge': u'br200',
            u'multi_host': False,
            u'bridge_interface': u'eth1',
            u'vlan': None,
            u'id': 2,
            u'injected': True,
            u'cidr': u'10.0.4.0/24',
            u'cidr_v6': None
        },
        {
            u'should_create_bridge': False,
            u'dns': [
                    u'192.168.2.1'
                ],
            u'label': u'infranet',
            u'broadcast': u'10.0.4.255',
            u'ips': [
                    {
                        u'ip': u'10.0.4.16',
                        u'netmask':
                        u'255.255.255.0',
                        u'enabled': u'1'
                    }
                ],
            u'mac': u'02:16:3e:40:5e:1b',
            u'rxtx_cap': 0,
            u'should_create_vlan': False,
            u'dhcp_server': u'10.0.2.2',
            u'gateway': u'10.0.2.2'
        }
    ]
]

INTERFACEINFO = [
    {
        'id': 1,
        'interface_number': 0,
        'bridge': 'br100',
        'name': 'eth0',
        'mac': '02:16:3e:0c:2c:08',
        'address': '10.0.2.16',
        'netmask': '255.255.255.0',
        'gateway': '10.0.2.2',
        'broadcast': '10.0.2.255',
        'dns': '192.168.2.1',
        'address_v6': None,
        'gateway_v6': None,
        'netmask_v6': None
    },
    {
        'id': 1,
        'interface_number': 1,
        'bridge': 'br200',
        'name': 'eth1',
        'mac': '02:16:3e:40:5e:1b',
        'address': '10.0.4.16',
        'netmask': '255.255.255.0',
        'gateway': '10.0.2.2',
        'broadcast': '10.0.4.255',
        'dns': '192.168.2.1',
        'address_v6': None,
        'gateway_v6': None,
        'netmask_v6': None
    }
]

TEMPFILE = '/tmp/foo/file'

NETTEMPLATE = """
    # This file describes the network interfaces available on your system
    # and how to activate them. For more information, see interfaces(5).

    # The loopback network interface
    auto lo
    iface lo inet loopback

    #for $ifc in $interfaces
    auto ${ifc.name}
    iface ${ifc.name} inet static
            address ${ifc.address}
            netmask ${ifc.netmask}
            broadcast ${ifc.broadcast}
            gateway ${ifc.gateway}
            dns-nameservers ${ifc.dns}

    #if $use_ipv6
    iface ${ifc.name} inet6 static
        address ${ifc.address_v6}
        netmask ${ifc.netmask_v6}
        gateway ${ifc.gateway_v6}
    #end if

    #end for
    """


class OpenVzConnTestCase(test.TestCase):
    def setUp(self):
        super(OpenVzConnTestCase, self).setUp()
        try:
            FLAGS.injected_network_template
        except AttributeError as err:
            FLAGS.register_opt(cfg.StrOpt('injected_network_template',
                                default='nova/virt/interfaces.template',
                                help='Stub for network template for testing purposes')
            )
        FLAGS.use_ipv6 = False
        self.fake_file = mox.MockAnything()
        self.fake_file.readlines().AndReturn(FILECONTENTS.split())
        self.fake_file.writelines(mox.IgnoreArg())
        self.fake_file.read().AndReturn(FILECONTENTS)

    def test_list_instances_detail_success(self):
        # Testing happy path of OpenVzConnection.list_instances_detail()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '-o', 'name', '-H',
                                  run_as_root=True).AndReturn(
            (VZNAMES, ERRORMSG))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'get_info')
        conn.get_info(mox.IgnoreArg()).MultipleTimes().AndReturn(GOODSTATUS)

        # Start test
        self.mox.ReplayAll()

        vzs = conn.list_instances_detail()
        self.assertEqual(vzs.__class__, list)

    def test_list_instances_detail_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '-o', 'name', '-H',
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable,
                          conn.list_instances_detail)

    def test_start_success(self):
        # Testing happy path :-D
        # Mock the objects needed for this test to succeed.
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', INSTANCE['id'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.RUNNING})
        # Start the tests
        self.mox.ReplayAll()
        # Create our connection object.  For all intents and purposes this is
        # a real OpenVzConnection object.
        conn = openvz_conn.OpenVzConnection(True)
        conn._start(INSTANCE)

    def test_start_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', INSTANCE['id'],
                            run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._start, INSTANCE)

    def test_list_instances_success(self):
        # Testing happy path of OpenVzConnection.list_instances()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '--no-header', '--output',
                                  'ctid', run_as_root=True).AndReturn(
            (VZLIST, ERRORMSG))
        # Start test
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        vzs = conn.list_instances()
        self.assertEqual(vzs.__class__, list)

    def test_list_instances_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '--no-header', '--output',
                                  'ctid', run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        # Start test
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable, conn.list_instances)

    def test_create_vz_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'create', INSTANCE['id'],
                                  '--ostemplate', INSTANCE['image_ref'],
                                  run_as_root=True).AndReturn(
            ('', ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._create_vz(INSTANCE)

    def test_create_vz_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'create', INSTANCE['id'],
                                  '--ostemplate', INSTANCE['image_ref'],
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._create_vz, INSTANCE)

    def test_set_vz_os_hint_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--ostemplate', 'ubuntu', run_as_root=True)\
            .AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_vz_os_hint(INSTANCE)

    def test_set_vz_os_hint_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--ostemplate', 'ubuntu', run_as_root=True)\
            .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._set_vz_os_hint, INSTANCE)

    def test_configure_vz_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--applyconfig', 'basic', run_as_root=True)\
            .AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._configure_vz(INSTANCE)

    def test_configure_vz_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--applyconfig', 'basic', run_as_root=True)\
            .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._configure_vz, INSTANCE)

    def test_stop_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.SHUTDOWN})
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._stop(INSTANCE)

    def test_stop_failure_on_exec(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._stop, INSTANCE)

    def test_stop_failure_on_db_access(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.SHUTDOWN})\
                                       .AndRaise(exception.DBError('FAIL'))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.DBError,
                          conn._stop, INSTANCE)

    def test_set_vmguarpages_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--vmguarpages', mox.IgnoreArg(),
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_vmguarpages(INSTANCE,
                              conn._calc_pages(INSTANCE['memory_mb']))

    def test_set_vmguarpages_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--vmguarpages', mox.IgnoreArg(),
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._set_vmguarpages, INSTANCE,
                          conn._calc_pages(INSTANCE['memory_mb']))

    def test_set_privvmpages_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--privvmpages', mox.IgnoreArg(),
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_privvmpages(INSTANCE,
                              conn._calc_pages(INSTANCE['memory_mb']))

    def test_set_privvmpages_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--privvmpages', mox.IgnoreArg(),
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._set_privvmpages, INSTANCE,
                          conn._calc_pages(INSTANCE['memory_mb']))

    def test_set_kmemsize_success(self):
        kmemsize = ((INSTANCE['memory_mb'] * 1024) * 1024)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--kmemsize', mox.IgnoreArg(),
                                  run_as_root=True).AndReturn(('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_kmemsize(INSTANCE, kmemsize)

    def test_set_kmemsize_failure(self):
        kmemsize = ((INSTANCE['memory_mb'] * 1024) * 1024)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--kmemsize', mox.IgnoreArg(),
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._set_kmemsize, INSTANCE, kmemsize)

    def test_set_onboot_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--onboot',
                                  'no', '--save', run_as_root=True).AndReturn(
            ('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_onboot(INSTANCE)

    def test_set_onboot_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--onboot',
                                  'no', '--save', run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._set_onboot, INSTANCE)

    def test_set_cpuunits_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpuunits', mox.IgnoreArg(),
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(RES_PERCENT)
        self.mox.StubOutWithMock(ovz_utils, 'get_cpuunits_capability')
        ovz_utils.get_cpuunits_capability().AndReturn(CPUUNITSCAPA)
        self.mox.StubOutWithMock(openvz_conn, 'ovz_utils')
        openvz_conn.ovz_utils = ovz_utils
        self.mox.ReplayAll()
        conn._set_cpuunits(INSTANCE,
                           conn._percent_of_resource(INSTANCETYPE['memory_mb'])
        )

    def test_set_cpuunits_over_subscribe(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpuunits', mox.IgnoreArg(),
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_utils, 'get_cpuunits_capability')
        ovz_utils.get_cpuunits_capability().AndReturn(CPUUNITSCAPA)
        self.mox.StubOutWithMock(openvz_conn, 'ovz_utils')
        openvz_conn.ovz_utils = ovz_utils
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(RES_OVER_PERCENT)
        self.mox.ReplayAll()
        conn._set_cpuunits(INSTANCE,
                           conn._percent_of_resource(INSTANCETYPE['memory_mb'])
        )

    def test_set_cpuunits_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpuunits', mox.IgnoreArg(),
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(RES_PERCENT)
        self.mox.StubOutWithMock(ovz_utils, 'get_cpuunits_capability')
        ovz_utils.get_cpuunits_capability().AndReturn(CPUUNITSCAPA)
        self.mox.StubOutWithMock(openvz_conn, 'ovz_utils')
        openvz_conn.ovz_utils = ovz_utils
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable, conn._set_cpuunits,
                          INSTANCE,
                          conn._percent_of_resource(INSTANCETYPE['memory_mb']))

    def test_set_cpulimit_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpulimit',
                                  UTILITY['CPULIMIT'] * RES_PERCENT,
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(
            RES_PERCENT
        )
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        conn._set_cpulimit(INSTANCE,
                           conn._percent_of_resource(INSTANCETYPE['memory_mb'])
        )

    def test_set_cpulimit_over_subscribe(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpulimit', UTILITY['CPULIMIT'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(
            RES_OVER_PERCENT
        )
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        conn._set_cpulimit(INSTANCE,
                           conn._percent_of_resource(INSTANCETYPE['memory_mb'])
        )

    def test_set_cpulimit_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpulimit',
                                  UTILITY['CPULIMIT'] * RES_PERCENT,
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(RES_PERCENT)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._set_cpulimit, INSTANCE,
                          conn._percent_of_resource(INSTANCETYPE['memory_mb']))

    def test_set_cpus_success(self):
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'],
                                  '--save', '--cpus',
                                  mox.IgnoreArg(), run_as_root=True
                                  ).AndReturn(('', ERRORMSG))
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        conn._set_cpus(INSTANCE, INSTANCETYPE['vcpus'])

    def test_set_cpus_failure(self):
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpus', mox.IgnoreArg(),
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.assertRaises(exception.InstanceUnacceptable, conn._set_cpus,
                          INSTANCE, INSTANCETYPE['vcpus'])

    def test_calc_pages_success(self):
        # this test is a little sketchy because it is testing the default
        # values of memory for instance type id 1.  if this value changes then
        # we will have a mismatch.

        # TODO(imsplitbit): make this work better.  This test is very brittle
        # because it relies on the default memory size for flavor 1 never
        # changing.  Need to fix this.
        conn = openvz_conn.OpenVzConnection(False)
        self.assertEqual(conn._calc_pages(INSTANCE['memory_mb']),
            262144)

    def test_get_cpuunits_capability_success(self):
        self.mox.StubOutWithMock(ovz_utils.utils, 'execute')
        ovz_utils.utils.execute('vzcpucheck', run_as_root=True).AndReturn(
            (CPUCHECKNOCONT, ERRORMSG))
        self.mox.ReplayAll()
        ovz_utils.get_cpuunits_capability()

    def test_get_cpuunits_capability_failure(self):
        self.mox.StubOutWithMock(ovz_utils.utils, 'execute')
        ovz_utils.utils.execute('vzcpucheck', run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable,
                          ovz_utils.get_cpuunits_capability())

    def test_get_cpuunits_usage_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzcpucheck', '-v',
                                  run_as_root=True).AndReturn(
            (CPUCHECKCONT, ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._get_cpuunits_usage()

    def test_get_cpuunits_usage_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzcpucheck', '-v',
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertFalse(conn._get_cpuunits_usage())

    def test_percent_of_resource(self):
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        self.assertEqual(float,
                         type(conn._percent_of_resource(INSTANCE['memory_mb']))
        )

    def test_set_ioprio_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--ioprio', 3, run_as_root=True).AndReturn(
            ('', ERRORMSG))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(INSTANCE['memory_mb']).AndReturn(.50)
        self.mox.ReplayAll()
        conn._set_ioprio(INSTANCE,
                         conn._percent_of_resource(INSTANCE['memory_mb']))

    def test_set_ioprio_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--ioprio', 3, run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(INSTANCE['memory_mb']).AndReturn(.50)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable,
                          conn._set_ioprio, INSTANCE,
                          conn._percent_of_resource(INSTANCE['memory_mb']))

    def test_set_diskspace_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--diskspace', mox.IgnoreArg(),
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_diskspace(INSTANCE, INSTANCETYPE)

    def test_set_diskspace_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                            '--diskspace', mox.IgnoreArg(), run_as_root=True)\
                            .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable, conn._set_diskspace,
                          INSTANCE, INSTANCETYPE)

    def test_attach_volumes_success(self):
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'attach_volume')
        conn.attach_volume(INSTANCE['name'], None,
                                      mox.IgnoreArg())
        self.mox.ReplayAll()
        conn._attach_volumes(INSTANCE)

    def test_attach_volume_failure(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context()
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(mox.IgnoreArg(),
                                    INSTANCE['id']).AndReturn(
            INSTANCE)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_find_by_name')
        conn._find_by_name(INSTANCE['name']).AndReturn(INSTANCE)
        mock_volumes = self.mox.CreateMock(openvz_conn.OVZVolumes)
        mock_volumes.setup()
        mock_volumes.attach()
        mock_volumes.write_and_close()
        self.mox.StubOutWithMock(openvz_conn, 'OVZVolumes')
        openvz_conn.OVZVolumes(INSTANCE['id'], mox.IgnoreArg(),
                               mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(
            mock_volumes)
        self.mox.ReplayAll()
        conn.attach_volume(INSTANCE['name'], '/dev/sdb1', '/var/tmp')

    def test_detach_volume_success(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context()
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(mox.IgnoreArg(), INSTANCE['id']).AndReturn(
            INSTANCE)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_find_by_name')
        conn._find_by_name(INSTANCE['name']).AndReturn(INSTANCE)
        mock_volumes = self.mox.CreateMock(openvz_conn.OVZVolumes)
        mock_volumes.setup()
        mock_volumes.detach()
        mock_volumes.write_and_close()
        self.mox.StubOutWithMock(openvz_conn, 'OVZVolumes')
        openvz_conn.OVZVolumes(INSTANCE['id'],
                               mox.IgnoreArg()).AndReturn(mock_volumes)
        self.mox.ReplayAll()
        conn.detach_volume(None, INSTANCE['name'], '/var/tmp')

    def test_make_directory_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', TEMPFILE, run_as_root=True)\
            .AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        fh.make_dir(TEMPFILE)

    def test_make_directory_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', TEMPFILE, run_as_root=True)\
                            .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        self.assertRaises(exception.InstanceUnacceptable,
                          fh.make_dir, TEMPFILE)

    def test_touch_file_success(self):
        fh = OVZFile(TEMPFILE)
        self.mox.StubOutWithMock(fh, 'make_path')
        fh.make_path()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('touch', TEMPFILE, run_as_root=True)\
                                  .AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        fh.touch()

    def test_touch_file_failure(self):
        fh = OVZFile(TEMPFILE)
        self.mox.StubOutWithMock(fh, 'make_path')
        fh.make_path()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('touch', TEMPFILE, run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable, fh.touch)

    def test_read_file_success(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'r').AndReturn(self.fake_file)
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        fh.read()

    def test_read_file_failure(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'r').AndRaise(exception.FileNotFound)
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        self.assertRaises(exception.FileNotFound, fh.read)

    def test_write_to_file_success(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'w').AndReturn(self.fake_file)
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        fh.write()

    def test_write_to_file_failure(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'w').AndRaise(exception.FileNotFound)
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        self.assertRaises(exception.FileNotFound, fh.write)

    def test_set_perms_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('chmod', 755, TEMPFILE, run_as_root=True)\
            .AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        fh.set_permissions(755)

    def test_set_perms_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('chmod', 755, TEMPFILE, run_as_root=True)\
                            .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        self.assertRaises(exception.InstanceUnacceptable,
                          fh.set_permissions, 755)

    def test_gratuitous_arp_all_addresses(self):
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_send_garp')
        conn._send_garp(INSTANCE['id'],
                        mox.IgnoreArg(),
                        mox.IgnoreArg()).MultipleTimes()
        self.mox.ReplayAll()
        conn._gratuitous_arp_all_addresses(INSTANCE, NETWORKINFO)

    def test_send_garp_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', INSTANCE['id'], 'arping',
                                  '-q', '-c', '5', '-A', '-I',
                                  NETWORKINFO[0][0]['bridge_interface'],
                                  NETWORKINFO[0][1]['ips'][0]['ip'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._send_garp(INSTANCE['id'], NETWORKINFO[0][1]['ips'][0]['ip'],
                        NETWORKINFO[0][0]['bridge_interface'])

    def test_send_garp_faiure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', INSTANCE['id'], 'arping',
                                  '-q', '-c', '5', '-A', '-I',
                                  NETWORKINFO[0][0]['bridge_interface'],
                                  NETWORKINFO[0][1]['ips'][0]['ip'],
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._send_garp(INSTANCE['id'], NETWORKINFO[0][1]['ips'][0]['ip'],
                        NETWORKINFO[0][0]['bridge_interface'])

    def test_ovz_network_bridge_driver_plug(self):
        self.mox.StubOutWithMock(
            openvz_conn.linux_net.LinuxBridgeInterfaceDriver,
            'ensure_vlan_bridge'
        )
        openvz_conn.linux_net.LinuxBridgeInterfaceDriver.ensure_vlan_bridge(
            mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()
        )
        self.mox.ReplayAll()
        driver = OVZNetworkBridgeDriver()
        for network, mapping in NETWORKINFO:
            driver.plug(INSTANCE, network, mapping)

    def test_ovz_network_interfaces_add_success(self):
        self.mox.StubOutWithMock(OVZNetworkFile, 'append')
        OVZNetworkFile.append(mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(OVZNetworkFile, 'write')
        OVZNetworkFile.write().MultipleTimes()
        self.mox.StubOutWithMock(OVZNetworkFile, 'set_permissions')
        OVZNetworkFile.set_permissions(
                                    mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg()).AndReturn(StringIO(NETTEMPLATE))
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        self.mox.StubOutWithMock(ifaces, '_add_netif')
        ifaces._add_netif(INTERFACEINFO[0]['id'],
                          mox.IgnoreArg(),
                          mox.IgnoreArg(),
                          mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(ifaces, '_set_nameserver')
        ifaces._set_nameserver(INTERFACEINFO[0]['id'], INTERFACEINFO[0]['dns'])
        self.mox.ReplayAll()
        ifaces.add()

    def test_ovz_network_interfaces_add_ip_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save', '--ipadd',
                                  INTERFACEINFO[0]['address'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        ifaces._add_ip(INTERFACEINFO[0]['id'], INTERFACEINFO[0]['address'])

    def test_ovz_network_interfaces_add_ip_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save',
                                  '--ipadd', INTERFACEINFO[0]['address'],
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        self.assertRaises(exception.InstanceUnacceptable, ifaces._add_ip,
                          INTERFACEINFO[0]['id'], INTERFACEINFO[0]['address'])

    def test_ovz_network_interfaces_add_netif(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save', '--netif_add',
                                  '%s,,veth%s.%s,%s,%s' % (
                                      INTERFACEINFO[0]['name'],
                                      INTERFACEINFO[0]['id'],
                                      INTERFACEINFO[0]['name'],
                                      INTERFACEINFO[0]['mac'],
                                      INTERFACEINFO[0]['bridge']),
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        ifaces._add_netif(
            INTERFACEINFO[0]['id'],
            INTERFACEINFO[0]['name'],
            INTERFACEINFO[0]['bridge'],
            INTERFACEINFO[0]['mac']
        )

    def test_filename_factory_debian_variant(self):
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        for filename in ifaces._filename_factory():
            self.assertFalse('//' in filename)

    def test_set_nameserver_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save', '--nameserver',
                                  INTERFACEINFO[0]['dns'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        ifaces._set_nameserver(INTERFACEINFO[0]['id'], INTERFACEINFO[0]['dns'])

    def test_set_nameserver_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save', '--nameserver',
                                  INTERFACEINFO[0]['dns'], run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        self.assertRaises(exception.InstanceUnacceptable,
                          ifaces._set_nameserver,
                          INTERFACEINFO[0]['id'], INTERFACEINFO[0]['dns'])

    # TODO (imsplitbit): make sure the order of these tests follows the driver.
    # this is solely for readability purposes.  The tests are written in no
    # particular order and I would prefer to make them follow the code a
    # little better.
    def test_get_connection(self):
        ovz_conn = openvz_conn.get_connection(False)
        self.assertTrue(isinstance(ovz_conn, openvz_conn.OpenVzConnection))

    def test_init_host_success(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().AndReturn(ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get_all_by_host')
        openvz_conn.db.instance_get_all_by_host(mox.IgnoreArg(),
                                                socket.gethostname())\
                            .MultipleTimes().AndReturn(INSTANCES)
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(INSTANCE['name']).MultipleTimes()\
                            .AndReturn(GOODSTATUS)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                {'power_state': power_state.RUNNING}).MultipleTimes()
        self.mox.StubOutWithMock(ovz_conn, '_get_cpulimit')
        ovz_conn._get_cpulimit()
        self.mox.ReplayAll()
        ovz_conn.init_host()

    def test_init_host_not_found(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().AndReturn(ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get_all_by_host')
        openvz_conn.db.instance_get_all_by_host(mox.IgnoreArg(),
                                                socket.gethostname())\
                            .MultipleTimes().AndReturn(INSTANCES)
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(INSTANCE['name']).MultipleTimes()\
                            .AndRaise(exception.NotFound)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                {'power_state': power_state.SHUTDOWN}).MultipleTimes()
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_destroy')
        openvz_conn.db.instance_destroy(ADMINCONTEXT, INSTANCE['id'])\
                            .MultipleTimes()
        self.mox.StubOutWithMock(ovz_conn, '_get_cpulimit')
        ovz_conn._get_cpulimit()
        self.mox.ReplayAll()
        ovz_conn.init_host()

    def test_set_hostname_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--hostname', INSTANCE['hostname'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        ovz_conn._set_hostname(INSTANCE)

    def test_set_hostname_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                            '--hostname', INSTANCE['hostname'],
                            run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          ovz_conn._set_hostname, INSTANCE)

    def test_set_name_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--name', INSTANCE['name'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        ovz_conn._set_name(INSTANCE)

    def test_set_name_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                            '--name', INSTANCE['name'],
                            run_as_root=True)\
                            .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          ovz_conn._set_name, INSTANCE)

    def test_find_by_name_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '-H', '--all', '--name_filter',
                                  INSTANCE['name'], run_as_root=True)\
            .AndReturn((VZLISTDETAIL, ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        meta = ovz_conn._find_by_name(INSTANCE['name'])
        self.assertEqual(INSTANCE['hostname'], meta['name'])
        self.assertEqual(str(INSTANCE['id']), meta['id'])
        self.assertEqual('running', meta['state'])

    def test_find_by_name_not_found(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '-H', '--all', '--name_filter',
                                  INSTANCE['name'], run_as_root=True)\
                                  .AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.NotFound, ovz_conn._find_by_name,
                          INSTANCE['name'])

    def test_find_by_name_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '-H', '--all', '--name_filter',
                            INSTANCE['name'], run_as_root=True)\
                            .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          ovz_conn._find_by_name, INSTANCE['name'])

    def test_plug_vifs(self):
        ovz_conn = openvz_conn.OpenVzConnection(False)
        ovz_conn.vif_driver = mox.MockAnything()
        ovz_conn.vif_driver.plug(INSTANCE, mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.StubOutWithMock(openvz_conn.OVZNetworkInterfaces, 'add')
        openvz_conn.OVZNetworkInterfaces.add()
        self.mox.ReplayAll()
        ovz_conn.plug_vifs(INSTANCE, NETWORKINFO)

    def test_reboot_success(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
            .AndReturn(ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                                       mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'restart', INSTANCE['id'],
                            run_as_root=True).AndReturn(('', ERRORMSG))
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(INSTANCE['name']).MultipleTimes()\
            .AndReturn(GOODSTATUS)
        self.mox.ReplayAll()
        timer = ovz_conn.reboot(INSTANCE, NETWORKINFO, 'hard')
        timer.wait()

    def test_reboot_fail_in_get_info(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
            .AndReturn(ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                                       mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'restart', INSTANCE['id'],
                            run_as_root=True).AndReturn(('', ERRORMSG))
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(INSTANCE['name']).AndRaise(exception.NotFound)
        self.mox.ReplayAll()
        timer = ovz_conn.reboot(INSTANCE, NETWORKINFO, 'hard')
        timer.wait()

    def test_reboot_fail_because_not_found(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
            .AndReturn(ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                                       mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'restart', INSTANCE['id'],
                            run_as_root=True).AndReturn(('', ERRORMSG))
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(INSTANCE['name']).AndReturn(NOSTATUS)
        self.mox.ReplayAll()
        timer = ovz_conn.reboot(INSTANCE, NETWORKINFO, 'hard')
        timer.wait()

    def test_reboot_failure(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().AndReturn(ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                                       {'power_state': power_state.PAUSED})
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'restart', INSTANCE['id'],
                            run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable, ovz_conn.reboot,
                          INSTANCE, NETWORKINFO, 'hard')

    def test_set_admin_password_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', INSTANCE['id'], 'echo',
                                  'root:%s' % ROOTPASS, '|', 'chpasswd',
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        ovz_conn.set_admin_password(ADMINCONTEXT, INSTANCE['id'], ROOTPASS)

    def test_set_admin_password_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', INSTANCE['id'], 'echo',
                            'root:%s' % ROOTPASS, '|', 'chpasswd',
                            run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          ovz_conn.set_admin_password,
                          ADMINCONTEXT, INSTANCE['id'], ROOTPASS)

    def test_pause_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.SHUTDOWN})
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn.pause(INSTANCE)

    def test_pause_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                            run_as_root=True)\
                            .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn.pause, INSTANCE)

    def test_suspend_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.SHUTDOWN})
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn.suspend(INSTANCE)

    def test_suspend_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                                  run_as_root=True)\
            .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn.suspend, INSTANCE)

    def test_unpause_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', INSTANCE['id'],
                            run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.RUNNING})

        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(True)
        conn.unpause(INSTANCE)

    def test_unpause_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', INSTANCE['id'],
                            run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn.unpause, INSTANCE)

    def test_resume_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', INSTANCE['id'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.RUNNING})

        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(True)
        conn.resume(INSTANCE)

    def test_resume_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', INSTANCE['id'],
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.InstanceUnacceptable,
                          conn.resume, INSTANCE)

    def test_destroy_fail_on_exec(self):
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, '_stop')
        ovz_conn._stop(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(INSTANCE['name']).AndReturn(GOODSTATUS)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'destroy', INSTANCE['id'],
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable, ovz_conn.destroy,
                          INSTANCE, NETWORKINFO)

    def test_destroy_success(self):
        ovz_conn = openvz_conn.OpenVzConnection(False)
        ovz_conn.vif_driver = mox.MockAnything()
        ovz_conn.vif_driver.unplug(INSTANCE, mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.StubOutWithMock(ovz_conn, '_stop')
        ovz_conn._stop(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(INSTANCE['name']).AndReturn(GOODSTATUS)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'destroy', INSTANCE['id'],
                                  run_as_root=True).AndRaise(
            exception.NotFound)
        self.mox.StubOutWithMock(ovz_conn, '_clean_orphaned_directories')
        ovz_conn._clean_orphaned_directories(INSTANCE['id'])
        self.mox.StubOutWithMock(ovz_conn, '_clean_orphaned_files')
        ovz_conn._clean_orphaned_files(INSTANCE['id'])
        self.mox.ReplayAll()
        ovz_conn.destroy(INSTANCE, NETWORKINFO)

    def test_get_info_running_state(self):
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(ADMINCONTEXT, INSTANCE['id'])\
            .AndReturn(INSTANCE)
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
            .AndReturn(ADMINCONTEXT)
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(INSTANCE['name']).AndReturn(FINDBYNAME)
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(INSTANCE['name'])
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.RUNNING)

    def test_get_info_shutdown_state(self):
        # Create a copy of instance to overwrite it's state
        NEWINSTANCE = INSTANCE.copy()
        NEWINSTANCE['power_state'] = power_state.SHUTDOWN
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(ADMINCONTEXT, INSTANCE['id'])\
            .AndReturn(NEWINSTANCE)
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
            .AndReturn(ADMINCONTEXT)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                                       mox.IgnoreArg())
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(INSTANCE['name']).AndReturn(FINDBYNAME)
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(INSTANCE['name'])
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.RUNNING)

    def test_get_info_no_state(self):
        # Create a copy of instance to overwrite it's state
        NEWINSTANCE = INSTANCE.copy()
        NEWINSTANCE['power_state'] = power_state.NOSTATE
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(ADMINCONTEXT, INSTANCE['id'])\
            .AndReturn(NEWINSTANCE)
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
            .AndReturn(ADMINCONTEXT)
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(INSTANCE['name']).AndReturn(FINDBYNAME)
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(INSTANCE['name'])
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.NOSTATE)

    def test_get_info_state_is_None(self):
        BADFINDBYNAME = FINDBYNAME.copy()
        BADFINDBYNAME['state'] = None
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(ADMINCONTEXT, INSTANCE['id'])\
            .AndReturn(INSTANCE)
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
            .AndReturn(ADMINCONTEXT)
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(INSTANCE['name']).AndReturn(BADFINDBYNAME)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                                       mox.IgnoreArg())
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(INSTANCE['name'])
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.NOSTATE)

    def test_get_info_state_is_shutdown(self):
        BADFINDBYNAME = FINDBYNAME.copy()
        BADFINDBYNAME['state'] = 'shutdown'
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(ADMINCONTEXT, INSTANCE['id'])\
            .AndReturn(INSTANCE)
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context().MultipleTimes()\
            .AndReturn(ADMINCONTEXT)
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(INSTANCE['name']).AndReturn(BADFINDBYNAME)
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                                       mox.IgnoreArg())
        self.mox.ReplayAll()
        meta = ovz_conn.get_info(INSTANCE['name'])
        self.assertTrue(isinstance(meta, dict))
        self.assertEqual(meta['state'], power_state.SHUTDOWN)

    def test_get_info_notfound(self):
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, '_find_by_name')
        ovz_conn._find_by_name(INSTANCE['name']).AndRaise(exception.NotFound)
        self.mox.ReplayAll()
        self.assertRaises(exception.NotFound, ovz_conn.get_info,
                          INSTANCE['name'])

    def test_percent_of_memory_over_subscribe(self):
        # Force the utility storage to have really low memory so as to test the
        # code that doesn't allow more than a 1.x multiplier.
        ovz_conn = openvz_conn.OpenVzConnection(False)
        ovz_conn.utility['MEMORY_MB'] = 16
        self.mox.StubOutWithMock(ovz_utils, 'get_memory_mb_total')
        ovz_utils.get_memory_mb_total().AndReturn(1024)
        self.mox.ReplayAll()
        self.assertEqual(1,
                         ovz_conn._percent_of_resource(INSTANCE['memory_mb']))

    def test_percent_of_memory_normal_subscribe(self):
        ovz_conn = openvz_conn.OpenVzConnection(False)
        ovz_conn.utility['MEMORY_MB'] = 16384
        self.mox.ReplayAll()
        self.assertTrue(
            ovz_conn._percent_of_resource(INSTANCE['memory_mb']) < 1)

    def test_get_cpulimit_success(self):
        self.mox.StubOutWithMock(ovz_utils.multiprocessing, 'cpu_count')
        ovz_utils.multiprocessing.cpu_count().AndReturn(2)
        self.mox.ReplayAll()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        ovz_conn._get_cpulimit()
        self.assertEqual(ovz_conn.utility['CPULIMIT'], 200)

    def test_append_file(self):
        fh = OVZFile(TEMPFILE)
        fh.append('foo')
        fh.append(['bar', 'baz'])
        self.assertEqual(['foo', 'bar', 'baz'], fh.contents)

    def test_prepend_file(self):
        fh = OVZFile(TEMPFILE)
        fh.prepend('foo')
        fh.prepend(['bar', 'baz'])
        self.assertEqual(['bar', 'baz', 'foo'], fh.contents)

    def test_delete_from_file(self):
        fh = OVZFile(TEMPFILE)
        fh.append(['foo', 'bar', 'baz'])
        fh.delete('bar')
        fh.delete(['baz'])
        self.assertEqual(['foo'], fh.contents)

    def test_make_path_and_dir_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', mox.IgnoreArg(),
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.os.path, 'exists')
        openvz_conn.os.path.exists(mox.IgnoreArg()).AndReturn(False)
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        fh.make_path()

    def test_make_path_and_dir_exists(self):
        self.mox.StubOutWithMock(openvz_conn.os.path, 'exists')
        openvz_conn.os.path.exists(mox.IgnoreArg()).AndReturn(True)
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        fh.make_path()

    def test_make_path_and_dir_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', mox.IgnoreArg(),
                                  run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.StubOutWithMock(openvz_conn.os.path, 'exists')
        openvz_conn.os.path.exists(mox.IgnoreArg()).AndReturn(False)
        self.mox.ReplayAll()
        fh = OVZFile(TEMPFILE)
        self.assertRaises(exception.InstanceUnacceptable, fh.make_path)

    def test_ovzmounts_format(self):
        mf = OVZMounts(TEMPFILE, '/var/lib/mysql', INSTANCE['id'],
                                   INSTANCE['volumes'][0]['uuid'])
        mf.contents = ['this is a test']
        mf.format()
        self.assertTrue(mf.contents[0] == '#!/bin/sh')
        mf.contents = []
        mf.format()
        self.assertTrue('#!/bin/sh' in mf.contents)

    def test_ovzmountfile_mount_lines_uuid(self):
        mf = OVZMountFile(TEMPFILE,
                                   INSTANCE['volumes'][0]['mountpoint'],
                                   INSTANCE['id'],
                                   uuid=INSTANCE['volumes'][0]['uuid'])
        host_mount_line = mf.host_mount_line()
        ex_host_mount_line = 'mount -o defaults UUID=%s %s' % \
                             (INSTANCE['volumes'][0]['uuid'], mf.host_mount)
        self.assertEqual(host_mount_line, ex_host_mount_line)

    def test_ovzmountfile_mount_lines_device(self):
        mf = OVZMountFile(TEMPFILE,
                                   INSTANCE['volumes'][1]['mountpoint'],
                                   INSTANCE['id'],
                                   device=INSTANCE['volumes'][1]['dev'])
        host_mount_line = mf.host_mount_line()
        ex_host_mount_line = 'mount -o defaults %s %s' % \
                             (INSTANCE['volumes'][1]['dev'], mf.host_mount)
        self.assertEqual(host_mount_line, ex_host_mount_line)

    def test_ovzmountfile_mount_lines_error(self):
        mf = OVZMountFile(TEMPFILE,
                                   INSTANCE['volumes'][1]['mountpoint'],
                                   INSTANCE['id'])
        self.assertRaises(exception.InvalidDevicePath, mf.host_mount_line)

    def test_container_mount_line(self):
        mf = OVZMountFile(TEMPFILE,
                                   INSTANCE['volumes'][1]['mountpoint'],
                                   INSTANCE['id'])
        ex_container_mount_line = 'mount -n -t simfs %s %s -o %s' % \
                                  (mf.host_mount, mf.container_root_mount,
                                   mf.host_mount)
        self.assertEqual(mf.container_mount_line(), ex_container_mount_line)

    def test_delete_mounts(self):
        mf = OVZMountFile(TEMPFILE,
                                   INSTANCE['volumes'][1]['mountpoint'],
                                   INSTANCE['id'],
                                   device=INSTANCE['volumes'][1]['dev'])
        mf.add_host_mount_line()
        mf.add_container_mount_line()
        mf.delete_mounts()

    def test_make_host_mount_point(self):
        mf = OVZMountFile(TEMPFILE,
                                   INSTANCE['volumes'][1]['mountpoint'],
                                   INSTANCE['id'],
                                   device=INSTANCE['volumes'][1]['dev'])
        self.mox.StubOutWithMock(openvz_conn.os.path, 'exists')
        openvz_conn.os.path.exists(mf.host_mount).AndReturn(False)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', mf.host_mount,
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        mf.make_host_mount_point()

    def test_make_container_mount_point(self):
        mf = OVZMountFile(TEMPFILE,
                                   INSTANCE['volumes'][1]['mountpoint'],
                                   INSTANCE['id'],
                                   device=INSTANCE['volumes'][1]['dev'])
        self.mox.StubOutWithMock(openvz_conn.os.path, 'exists')
        openvz_conn.os.path.exists(mf.container_mount).AndReturn(False)
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', mf.container_mount,
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        mf.make_container_mount_point()

    def test_spawn_success(self):
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                                  mox.IgnoreArg()).MultipleTimes()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, '_get_cpuunits_usage')
        ovz_conn._get_cpuunits_usage()
        self.mox.StubOutWithMock(ovz_conn, '_cache_image')
        ovz_conn._cache_image(ADMINCONTEXT, INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_create_vz')
        ovz_conn._create_vz(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_vz_os_hint')
        ovz_conn._set_vz_os_hint(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_configure_vz')
        ovz_conn._configure_vz(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_name')
        ovz_conn._set_name(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, 'plug_vifs')
        ovz_conn.plug_vifs(INSTANCE, NETWORKINFO)
        self.mox.StubOutWithMock(ovz_conn, '_set_hostname')
        ovz_conn._set_hostname(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_instance_size')
        ovz_conn._set_instance_size(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_attach_volumes')
        ovz_conn._attach_volumes(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_start')
        ovz_conn._start(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_initial_secure_host')
        ovz_conn._initial_secure_host(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_gratuitous_arp_all_addresses')
        ovz_conn._gratuitous_arp_all_addresses(INSTANCE, NETWORKINFO)
        self.mox.StubOutWithMock(ovz_conn, 'set_admin_password')
        ovz_conn.set_admin_password(ADMINCONTEXT, INSTANCE['id'],
                                    INSTANCE['admin_pass'])
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(INSTANCE['name']).AndReturn(GOODSTATUS)
        self.mox.ReplayAll()
        timer = ovz_conn.spawn(ADMINCONTEXT, INSTANCE, None, NETWORKINFO)
        timer.wait()

    def test_spawn_failure(self):
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(ADMINCONTEXT, INSTANCE['id'],
                                  mox.IgnoreArg()).MultipleTimes()
        ovz_conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(ovz_conn, '_get_cpuunits_usage')
        ovz_conn._get_cpuunits_usage()
        self.mox.StubOutWithMock(ovz_conn, '_cache_image')
        ovz_conn._cache_image(ADMINCONTEXT, INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_create_vz')
        ovz_conn._create_vz(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_vz_os_hint')
        ovz_conn._set_vz_os_hint(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_configure_vz')
        ovz_conn._configure_vz(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_name')
        ovz_conn._set_name(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, 'plug_vifs')
        ovz_conn.plug_vifs(INSTANCE, NETWORKINFO)
        self.mox.StubOutWithMock(ovz_conn, '_set_hostname')
        ovz_conn._set_hostname(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_set_instance_size')
        ovz_conn._set_instance_size(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_attach_volumes')
        ovz_conn._attach_volumes(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_start')
        ovz_conn._start(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_initial_secure_host')
        ovz_conn._initial_secure_host(INSTANCE)
        self.mox.StubOutWithMock(ovz_conn, '_gratuitous_arp_all_addresses')
        ovz_conn._gratuitous_arp_all_addresses(INSTANCE, NETWORKINFO)
        self.mox.StubOutWithMock(ovz_conn, 'set_admin_password')
        ovz_conn.set_admin_password(ADMINCONTEXT, INSTANCE['id'],
                                    INSTANCE['admin_pass'])
        self.mox.StubOutWithMock(ovz_conn, 'get_info')
        ovz_conn.get_info(INSTANCE['name']).AndRaise(exception.NotFound)
        self.mox.ReplayAll()
        timer = ovz_conn.spawn(ADMINCONTEXT, INSTANCE, None, NETWORKINFO)
        timer.wait()
