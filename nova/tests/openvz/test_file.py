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

    def test_make_directory_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', fakes.TEMPFILE, run_as_root=True)\
        .AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        fh.make_dir(fakes.TEMPFILE)

    def test_make_directory_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', fakes.TEMPFILE, run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        self.assertRaises(exception.InstanceUnacceptable,
            fh.make_dir, fakes.TEMPFILE)

    def test_touch_file_success(self):
        fh = OVZFile(fakes.TEMPFILE)
        self.mox.StubOutWithMock(fh, 'make_path')
        fh.make_path()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('touch', fakes.TEMPFILE, run_as_root=True)\
        .AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        fh.touch()

    def test_touch_file_failure(self):
        fh = OVZFile(fakes.TEMPFILE)
        self.mox.StubOutWithMock(fh, 'make_path')
        fh.make_path()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('touch', fakes.TEMPFILE, run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        self.assertRaises(exception.InstanceUnacceptable, fh.touch)

    def test_read_file_success(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'r').AndReturn(self.fake_file)
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        fh.read()

    def test_read_file_failure(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'r').AndRaise(exception.FileNotFound)
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        self.assertRaises(exception.FileNotFound, fh.read)

    def test_write_to_file_success(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'w').AndReturn(self.fake_file)
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        fh.write()

    def test_write_to_file_failure(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'w').AndRaise(exception.FileNotFound)
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        self.assertRaises(exception.FileNotFound, fh.write)

    def test_set_perms_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('chmod', 755, fakes.TEMPFILE, run_as_root=True)\
        .AndReturn(('', fakes.ERRORMSG))
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        fh.set_permissions(755)

    def test_set_perms_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('chmod', 755, fakes.TEMPFILE, run_as_root=True)\
        .AndRaise(exception.InstanceUnacceptable)
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        self.assertRaises(exception.InstanceUnacceptable,
            fh.set_permissions, 755)

    def test_make_path_and_dir_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', mox.IgnoreArg(),
            run_as_root=True).AndReturn(('', fakes.ERRORMSG))
        self.mox.StubOutWithMock(openvz_conn.os.path, 'exists')
        openvz_conn.os.path.exists(mox.IgnoreArg()).AndReturn(False)
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        fh.make_path()

    def test_make_path_and_dir_exists(self):
        self.mox.StubOutWithMock(openvz_conn.os.path, 'exists')
        openvz_conn.os.path.exists(mox.IgnoreArg()).AndReturn(True)
        self.mox.ReplayAll()
        fh = OVZFile(fakes.TEMPFILE)
        fh.make_path()
