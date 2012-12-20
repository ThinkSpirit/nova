# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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

"""
A driver specific to OpenVz as the support for Ovz in libvirt
is sketchy at best.
"""
from nova.virt.openvz.volume import OVZVolume
from nova.virt.openvz import utils as ovz_utils
from nova import exception
from nova.openstack.common import cfg
from nova.openstack.common import log as logging
from nova.openstack.common import lockutils


CONF = cfg.CONF
CONF.register_opt(
    cfg.IntOpt('ovz_iscsiadm_num_tries',
               default=1,
               help='Number of attempts to make an iscsi connection'))

LOG = logging.getLogger('nova.virt.openvz.volume_drivers.iscsi')


class OVZISCSIStorageDriver(OVZVolume):
    def __init__(self, connection_data, instance_id, mountpoint):
        """
        Driver for openvz to connect iscsi volumes to instances

        :param connection_data: Data from the connection_info given to the
        ovz driver
        :param instance_id: Instance ID for the volume to be attached to
        :param mountpoint: place to mount the volume within the container
        """
        self.iscsi_properties = connection_data['data']
        self.instance_id = instance_id
        self.mountpoint = mountpoint

    def device_name(self):
        """
        Generates an device name based on the iSCSI parameters in the
        block device mapping
        """
        return "/dev/disk/by-path/ip-%s-iscsi-%s-lun-%s" % \
            (self.iscsi_properties['target_portal'],
             self.iscsi_properties['target_iqn'],
             self.iscsi_properties['target_lun'])

    def init_volume(self, fs_uuid=None):
        super(OVZISCSIStorageDriver, self).__init__(self.instance_id,
                                                    self.mountpoint,
                                                    self.device_name(),
                                                    fs_uuid)

    def init_iscsi_device(self):
        """
        Log into the device and setup files
        """
        self.discover_volume()
        self.init_volume()

    def _run_iscsiadm(self, iscsi_command, raise_on_error=True):
        out = ovz_utils.execute('iscsiadm', '-m', 'node', '-T',
                                self.iscsi_properties['target_iqn'],
                                '-p', self.iscsi_properties['target_portal'],
                                *iscsi_command, run_as_root=True,
                                attempts=CONF.ovz_iscsiadm_num_tries,
                                raise_on_error=raise_on_error)
        LOG.debug("iscsiadm %s: stdout=%s" %
                  (iscsi_command, out))
        return out

    def _iscsiadm_update(self, property_key, property_value,
                         raise_on_error=True):
        iscsi_command = ('--op', 'update', '-n', property_key,
                         '-v', property_value)
        return self._run_iscsiadm(iscsi_command, raise_on_error=raise_on_error)

    def get_iscsi_properties_for_volume(self):
        if not self.iscsi_properties['target_discovered']:
            self._run_iscsiadm(('--op', 'new'))

    def session_currently_connected(self):
        out = ovz_utils.execute('iscsiadm', '-m', 'session', run_as_root=True)
        if out:
            for line in out.splitlines():
                if self.iscsi_properties['target_iqn'] in line:
                    return True
        return False

    def set_iscsi_auth(self):
        if self.iscsi_properties.get('auth_method', None):
            self._iscsiadm_update("node.session.auth.authmethod",
                                  self.iscsi_properties['auth_method'])
            self._iscsiadm_update("node.session.auth.username",
                                  self.iscsi_properties['auth_username'])
            self._iscsiadm_update("node.session.auth.password",
                                  self.iscsi_properties['auth_password'])

    @lockutils.synchronized('iscsiadm_lock')
    def discover_volume(self):
        """Discover volume on a remote host."""
        self.get_iscsi_properties_for_volume()
        self.set_iscsi_auth()

        try:
            if not self.session_currently_connected():
                LOG.debug(_('iSCSI session for %s not connected, '
                            'connecting now') %
                          self.iscsi_properties['target_iqn'])
                self._run_iscsiadm(("--login",))
                LOG.debug(_('iSCSI session for %s connected') %
                          self.iscsi_properties['target_iqn'])
        except exception.ProcessExecutionError as err:
            if "15 - already exists" in err.message:
                raise exception.VolumeUnattached()
            LOG.error(err)
            raise exception.VolumeNotFound(_("iSCSI device %s not found") %
                                           self.iscsi_properties['target_iqn'])

    @lockutils.synchronized('iscsiadm_lock')
    def disconnect_iscsi_volume(self):
        """Detach the volume from instance_name"""
        self.init_volume()
        self._iscsiadm_update("node.startup", "manual")
        self._run_iscsiadm(("--logout",), raise_on_error=False)
        self._run_iscsiadm(('--op', 'delete'), raise_on_error=False)

    @lockutils.synchronized('iscsiadm_lock')
    def rescan(self):
        """Rescan the client storage connection"""

        self.get_iscsi_properties_for_volume()
        try:
            LOG.debug("ISCSI Properties: %s" % self.iscsi_properties)
            self._run_iscsiadm(("--rescan",))
            return ("/dev/disk/by-path/ip-%s-iscsi-%s-lun-%s" %
                    (self.iscsi_properties['target_portal'],
                     self.iscsi_properties['target_iqn'],
                     self.iscsi_properties['target_lun']))
        except exception.ProcessExecutionError as err:
            LOG.error(err)
            raise exception.VolumeIsBusy(
                _("Error rescanning iscsi device: %s") %
                self.iscsi_properties['target_iqn'])
