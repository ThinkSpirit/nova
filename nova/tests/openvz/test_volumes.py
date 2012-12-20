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

    def test_attach_volume_failure(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context()
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(mox.IgnoreArg(),
            fakes.INSTANCE['id']).AndReturn(
            fakes.INSTANCE)
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_find_by_name')
        conn._find_by_name(fakes.INSTANCE['name']).AndReturn(fakes.INSTANCE)
        mock_volumes = self.mox.CreateMock(openvz_conn.OVZVolumes)
        mock_volumes.setup()
        mock_volumes.attach()
        mock_volumes.write_and_close()
        self.mox.StubOutWithMock(openvz_conn, 'OVZVolumes')
        openvz_conn.OVZVolumes(fakes.INSTANCE['id'], mox.IgnoreArg(),
            mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(
            mock_volumes)
        self.mox.ReplayAll()
        conn.attach_volume(fakes.INSTANCE['name'], '/dev/sdb1', '/var/tmp')

    def test_detach_volume_success(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context()
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(mox.IgnoreArg(), fakes.INSTANCE['id']).AndReturn(
            fakes.INSTANCE)
        conn = openvz_conn.OpenVzDriver(False)
        self.mox.StubOutWithMock(conn, '_find_by_name')
        conn._find_by_name(fakes.INSTANCE['name']).AndReturn(fakes.INSTANCE)
        mock_volumes = self.mox.CreateMock(openvz_conn.OVZVolumes)
        mock_volumes.setup()
        mock_volumes.detach()
        mock_volumes.write_and_close()
        self.mox.StubOutWithMock(openvz_conn, 'OVZVolumes')
        openvz_conn.OVZVolumes(fakes.INSTANCE['id'],
            mox.IgnoreArg()).AndReturn(mock_volumes)
        self.mox.ReplayAll()
        conn.detach_volume(None, fakes.INSTANCE['name'], '/var/tmp')