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
from nova.openstack.common import cfg
from nova.virt.openvz.file import *
from nova.virt.openvz.network_drivers.network_bridge import\
    OVZNetworkBridgeDriver
from nova.virt.openvz.network import *
from nova.virt.openvz import utils as ovz_utils
from StringIO import StringIO

CONF = cfg.CONF


class OpenVzVolumeTestCase(test.TestCase):
    def setUp(self):
        super(OpenVzVolumeTestCase, self).setUp()
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

    def test_ovz_network_interfaces_add_success(self):
        self.mox.StubOutWithMock(OVZNetworkFile, 'append')
        OVZNetworkFile.append(mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(OVZNetworkFile, 'write')
        OVZNetworkFile.write().MultipleTimes()
        self.mox.StubOutWithMock(OVZNetworkFile, 'set_permissions')
        OVZNetworkFile.set_permissions(
            mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg()).AndReturn(StringIO(fakes.NETTEMPLATE))
        ifaces = openvz_conn.OVZNetworkInterfaces(fakes.INTERFACEINFO)
        self.mox.StubOutWithMock(ifaces, '_add_netif')
        ifaces._add_netif(fakes.INTERFACEINFO[0]['id'],
            mox.IgnoreArg(),
            mox.IgnoreArg(),
            mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(ifaces, '_set_nameserver')
        ifaces._set_nameserver(fakes.INTERFACEINFO[0]['id'], fakes.INTERFACEINFO[0]['dns'])
        self.mox.ReplayAll()
        ifaces.add()

    def test_ovz_network_interfaces_add_ip_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INTERFACEINFO[0]['id'],
            '--save', '--ipadd',
            fakes.INTERFACEINFO[0]['address'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(fakes.INTERFACEINFO)
        ifaces._add_ip(fakes.INTERFACEINFO[0]['id'], fakes.INTERFACEINFO[0]['address'])

    def test_ovz_network_interfaces_add_ip_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INTERFACEINFO[0]['id'],
            '--save',
            '--ipadd', fakes.INTERFACEINFO[0]['address'],
            run_as_root=True).AndRaise(
            exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(fakes.INTERFACEINFO)
        self.assertRaises(exception.InstanceUnacceptable, ifaces._add_ip,
            fakes.INTERFACEINFO[0]['id'], fakes.INTERFACEINFO[0]['address'])

    def test_ovz_network_interfaces_add_netif(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INTERFACEINFO[0]['id'],
            '--save', '--netif_add',
            '%s,,veth%s.%s,%s,%s' % (
                fakes.INTERFACEINFO[0]['name'],
                fakes.INTERFACEINFO[0]['id'],
                fakes.INTERFACEINFO[0]['name'],
                fakes.INTERFACEINFO[0]['mac'],
                fakes.INTERFACEINFO[0]['bridge']),
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(fakes.INTERFACEINFO)
        ifaces._add_netif(
            fakes.INTERFACEINFO[0]['id'],
            fakes.INTERFACEINFO[0]['name'],
            fakes.INTERFACEINFO[0]['bridge'],
            fakes.INTERFACEINFO[0]['mac']
        )

    def test_filename_factory_debian_variant(self):
        ifaces = openvz_conn.OVZNetworkInterfaces(fakes.INTERFACEINFO)
        for filename in ifaces._filename_factory():
            self.assertFalse('//' in filename)

    def test_set_nameserver_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INTERFACEINFO[0]['id'],
            '--save', '--nameserver',
            fakes.INTERFACEINFO[0]['dns'],
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(fakes.INTERFACEINFO)
        ifaces._set_nameserver(fakes.INTERFACEINFO[0]['id'], fakes.INTERFACEINFO[0]['dns'])

    def test_set_nameserver_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', fakes.INTERFACEINFO[0]['id'],
            '--save', '--nameserver',
            fakes.INTERFACEINFO[0]['dns'], run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(fakes.INTERFACEINFO)
        self.assertRaises(exception.InstanceUnacceptable,
            ifaces._set_nameserver,
            fakes.INTERFACEINFO[0]['id'], fakes.INTERFACEINFO[0]['dns'])

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
        for network, mapping in fakes.NETWORKINFO:
            driver.plug(fakes.INSTANCE, network, mapping)
