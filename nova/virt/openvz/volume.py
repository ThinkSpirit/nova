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

import os
import pexpect
import uuid as uuid4
from nova.openstack.common import log as logging
from nova import db
from nova import context
from nova import exception
from nova.virt.openvz import utils as ovz_utils
from nova.virt.openvz.file_ext.mount import OVZMountFile
from nova.virt.openvz.file_ext.umount import OVZUmountFile
from nova import flags

FLAGS = flags.FLAGS
LOG = logging.getLogger('nova.virt.openvz.volume')


class OVZVolume(object):
    """
    This Class is a helper class to manage the mount and umount files
    for a given container.
    """
    def __init__(self, instance_id, mountpoint, dev, fs_uuid=None):
        self.instance_id = instance_id
        self.mountpoint = mountpoint
        self.device = dev

        if not fs_uuid:
            self.fs_uuid = str(uuid4.uuid4())
        else:
            self.fs_uuid = fs_uuid

        self.context = context
        self.mountfile = '%s/%s.mount' % (FLAGS.ovz_config_dir,
                                          self.instance_id)
        self.umountfile = '%s/%s.umount' % (FLAGS.ovz_config_dir,
                                            self.instance_id)
        self.mountfile = os.path.abspath(self.mountfile)
        self.umountfile = os.path.abspath(self.umountfile)

    def prepare_filesystem(self):
        """
        Generate a uuid for the filesystem and create it
        """
        ovz_utils.mkfs(self.device, FLAGS.ovz_volume_default_fs, self.fs_uuid)

    def setup(self):
        """
        Prep the paths and files for manipulation.
        """
        # Create the file objects
        self.mountfh = OVZMountFile(self.mountfile, self.mountpoint,
                                    self.instance_id, self.device,
                                    self.fs_uuid)
        self.umountfh = OVZUmountFile(self.umountfile, self.mountpoint,
                                      self.instance_id, self.device,
                                      self.fs_uuid)

        with self.mountfh:
            self.mountfh.read()
            self.mountfh.make_proper_script()

        with self.umountfh:
            self.umountfh.read()
            self.umountfh.make_proper_script()

    def attach(self):
        # Create the mount point on the host node
        self.mountfh.make_host_mount_point()
        # Create a mount point for the device inside the root of the container
        self.mountfh.make_container_mount_point()

        # Add the host and container mount lines to the mount script
        self.mountfh.add_host_mount_line()
        self.mountfh.add_container_mount_line()

        # Add umount lines to the umount script
        #self.umountfh.add_container_umount_line()
        self.umountfh.add_host_umount_line()

    def detach(self):
        # Unmount the storage if possible
        self.umountfh.unmount_all()

        # If the lines of the mount and unmount statements are in the
        # container mount and umount files, remove them.
        self.mountfh.delete_mounts(self.fs_uuid)
        self.umountfh.delete_umounts()

    def write_and_close(self):
        with self.mountfh:
            self.mountfh.write()

        with self.umountfh:
            self.umountfh.write()

    def find_volume_by_id(self, volume_id):
        try:
            return db.volume_get(context.get_admin_context(), volume_id)
        except exception.DBError:
            LOG.error(_('Volume %s not found') % volume_id)
            raise exception.VolumeNotFound(_('Volume %s not found') %
                                           volume_id)

    def get_volume_uuid(self, device_path):
        """Returns the UUID of a device given that device path.

        The returned UUID is expected to be hex in five groups with the lengths
        8,4,4,4 and 12.
        Example:
        fd575a25-f9d9-4e7f-aafd-9c2b92e9ec4c

        If the device_path doesn't match anything, DevicePathInvalidForUuid
        is raised.

        """
        try:
            out = ovz_utils.execute('blkid', device_path)
            out = out.split()
            out = out[1].split('=')
            return out[1]
        except exception.InstanceUnacceptable as err:
            LOG.error(_('Unable to get UUID for %s') % device_path)
            LOG.error(err)
            raise exception.InvalidDevicePath(device_path=device_path)

    def _check_device_exists(self, device_path):
        """Check that the device path exists.

        Verify that the device path has actually been created and can report
        it's size, only then can it be available for formatting, retry
        num_tries to account for the time lag.
        """
        try:
            ovz_utils.execute('blockdev', '--getsize64', device_path,
                              attempts=FLAGS.ovz_system_num_tries,
                              run_as_root=True)
        except exception.ProcessExecutionError:
            raise exception.InvalidDevicePath(path=device_path)

    def _check_format(self, device_path):
        """Checks that an unmounted volume is formatted."""
        child = pexpect.spawn("sudo dumpe2fs %s" % device_path)
        try:
            i = child.expect(['has_journal', 'Wrong magic number'])
            if i == 0:
                return
            raise IOError('Device path at %s did not seem to be %s.' %
                          (device_path, FLAGS.volume_fstype))
        except pexpect.EOF:
            raise IOError("Volume was not formatted.")
        child.expect(pexpect.EOF)

    def format(self, device_path):
        """Formats the device at device_path and checks the filesystem."""
        self._check_device_exists(device_path)
        ovz_utils.mkfs(device_path, FLAGS.ovz_volume_default_fs)
        self._check_format(device_path)
