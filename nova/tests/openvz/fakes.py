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

import os
from nova.compute import power_state
from nova.openstack.common import cfg
from Cheetah.Template import Template
from nova import exception
import random
from nova.virt import openvz

CONF = cfg.CONF


class FakeOVZTcRules(object):
    try:
        available_ids
    except NameError:
        available_ids = list()

    try:
        inflight_ids
    except NameError:
        inflight_ids = list()

    def __init__(self):
        if not len(FakeOVZTcRules.available_ids):
            FakeOVZTcRules.available_ids = [
            i for i in range(1, CONF.ovz_tc_id_max)
            ]

        self._remove_used_ids()

    def instance_info(self, instance_id, address, vz_iface):
        if not instance_id:
            self.instance_type = dict()
            self.instance_type['memory_mb'] = 2048

        self.address = address
        self.vz_iface = vz_iface
        self.bandwidth = int(round(self.instance_type['memory_mb'] /
                                   CONF.ovz_memory_unit_size)) *\
                         CONF.ovz_tc_mbit_per_unit
        self.tc_id = self._get_instance_tc_id()
        if not self.tc_id:
            self.tc_id = self.get_id()

        self._save_instance_tc_id()

    def get_id(self):
        self._remove_used_ids()
        id = self._pull_id()
        while id in FakeOVZTcRules.inflight_ids:
            id = self._pull_id()
        self._reserve_id(id)
        return id

    def container_start(self):
        template = self._load_template('tc_container_start.template')
        search_list = {
            'prio': self.tc_id,
            'host_iface': CONF.ovz_tc_host_slave_device,
            'vz_iface': self.vz_iface,
            'bandwidth': self.bandwidth,
            'vz_address': self.address,
            'line_speed': CONF.ovz_tc_max_line_speed
        }
        return self._fill_template(template, search_list).splitlines()

    def container_stop(self):
        template = self._load_template('tc_container_stop.template')
        search_list = {
            'prio': self.tc_id,
            'host_iface': CONF.ovz_tc_host_slave_device,
            'vz_iface': self.vz_iface,
            'bandwidth': self.bandwidth,
            'vz_address': self.address
        }
        return self._fill_template(template, search_list).splitlines()

    def host_start(self):
        template = self._load_template('tc_host_start.template')
        search_list = {
            'host_iface': CONF.ovz_tc_host_slave_device,
            'line_speed': CONF.ovz_tc_max_line_speed
        }
        return self._fill_template(template, search_list).splitlines()

    def host_stop(self):
        template = self._load_template('tc_host_stop.template')
        search_list = {
            'host_iface': CONF.ovz_tc_host_slave_device
        }
        return self._fill_template(template, search_list).splitlines()

    def _load_template(self, template_name):
        full_template_path = '%s/%s' % (
            CONF.ovz_tc_template_dir, template_name)
        full_template_path = os.path.abspath(full_template_path)
        try:
            template_file = open(full_template_path).read()
            return template_file
        except Exception as err:
            raise exception.FileNotFound(err)

    def _fill_template(self, template, search_list):
        return str(Template(template, searchList=[search_list]))

    def _pull_id(self):
        return FakeOVZTcRules.available_ids[random.randint(
            0, len(FakeOVZTcRules.available_ids) - 1)]

    def _list_existing_ids(self):
        return [1,3,6]

    def _reserve_id(self, id):
        FakeOVZTcRules.inflight_ids.append(id)
        FakeOVZTcRules.available_ids.remove(id)

    def _remove_used_ids(self):
        used_ids = self._list_existing_ids()
        for id in used_ids:
            if id in FakeOVZTcRules.available_ids:
                FakeOVZTcRules.available_ids.remove(id)

    def _save_instance_tc_id(self):
        return

    def _get_instance_tc_id(self):
        return 1


class Context(object):
    def __init__(self):
        self.is_admin = False
        self.read_deleted = "yes"


class AdminContext(Context):
    def __init__(self):
        super(AdminContext, self).__init__()
        self.is_admin = True


# Stubs for faked file operations to allow unittests to test code paths
# without actually leaving file turds around the test box.
class FakeOvzFile(object):
    def __init__(self, filename, perms):
        self.filename = filename
        self.perms = perms
        self.contents = []

    def __enter__(self):
        """
        This may feel dirty but we need to be able to read and write files
        as a non priviledged user so we need to change the permissions to
        be more open for our file operations and then secure them once we
        are done.
        """
        if not self.exists():
            self.make_path()
            self.touch()

        self.set_permissions(666)

    def __exit__(self, _type, value, tb):
        if self.exists():
            self.set_permissions(self.permissions)

    def exists(self):
        return

    def make_path(self, path=None):
        return

    def touch(self):
        return

    def set_permissions(self, perms):
        return

    def read(self):
        return

    def run_contents(self):
        return

    def set_contents(self, contents):
        self.contents = contents

    def make_proper_script(self):
        return

    def append(self, contents):
        self.contents = self.contents + contents

    def prepend(self, contents):
        self.contents = contents + self.contents

    def write(self):
        return


class FakeOVZShutdownFile(FakeOvzFile):
    def __init__(self, instance_id, permissions):
        filename = "%s/%s.shutdown" % (CONF.ovz_config_dir, instance_id)
        filename = os.path.abspath(filename)
        super(FakeOVZShutdownFile, self).__init__(filename, permissions)


class FakeOVZBootFile(FakeOvzFile):
    def __init__(self, instance_id, permissions):
        filename = "%s/%s.shutdown" % (CONF.ovz_config_dir, instance_id)
        filename = os.path.abspath(filename)
        super(FakeOVZBootFile, self).__init__(filename, permissions)


ROOTPASS = '2s3cUr3'

USER = {'user': 'admin', 'role': 'admin', 'id': 1}

PROJECT = {'name': 'test', 'id': 2}

ADMINCONTEXT = AdminContext()

CONTEXT = Context()

BDM = {
    'block_device_mapping': [
        {
            'connection_info': {},
            'mount_device': '/dev/sdgg'
        }
    ]
}

INSTANCE = {
    "image_ref": 1,
    "name": "instance-00001002",
    "instance_type_id": 1,
    "id": 1002,
    "uuid": "07fd1fc9-eb75-4375-88d5-6247ce2fb7e4",
    "hostname": "test.foo.com",
    "power_state": power_state.RUNNING,
    "admin_pass": ROOTPASS,
    "user_id": USER['id'],
    "project_id": PROJECT['id'],
    "memory_mb": 1024,
    "block_device_mapping": BDM
}

IMAGEPATH = '%s/%s.tar.gz' %\
            (CONF.ovz_image_template_dir, INSTANCE['image_ref'])

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

VZLISTDETAIL = "        %d         running   %s"\
               % (INSTANCE['id'], INSTANCE['hostname'])

FINDBYNAME = VZLISTDETAIL.split()
FINDBYNAME = {'name': FINDBYNAME[2], 'id': int(FINDBYNAME[0]),
              'state': FINDBYNAME[1]}
FINDBYNAMENOSTATE = VZLISTDETAIL.split()
FINDBYNAMENOSTATE = {'name': FINDBYNAMENOSTATE[2], 'id': int(FINDBYNAMENOSTATE[0]),
                     'state': '-'}
FINDBYNAMESHUTDOWN = VZLISTDETAIL.split()
FINDBYNAMESHUTDOWN = {'name': FINDBYNAMESHUTDOWN[2], 'id': int(FINDBYNAMESHUTDOWN[0]),
                      'state': 'stopped'}

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
