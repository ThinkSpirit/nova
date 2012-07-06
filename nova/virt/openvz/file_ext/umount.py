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

from nova.openstack.common import log as logging
from nova.virt.openvz.file_ext.mounts import OVZMounts
from nova.virt.openvz import utils as ovz_utils
from nova import flags

FLAGS = flags.FLAGS

LOG = logging.getLogger('nova.virt.openvz.umount')


class OVZUmountFile(OVZMounts):
    """
    methods to be used for manipulating the CTID.umount files
    """
    def host_umount_line(self):
        """
        Generate a umount line to compliment the host mount line added for the
        filesystem in OVZMountFile
        """
        return self._umount_line(self.host_mount)

    def container_umount_line(self):
        """
        Generate a umount line to compliment the container mount line added for
        the filesystem in OVZMountFile
        """
        return self._umount_line(self.container_root_mount, False)

    @staticmethod
    def _umount_line(mount, lazy=True):
        """
        Helper method to assemble a umount line for CTID.umount.  This uses
        lazy and force to unmount the filesystem because in the condition that
        you are detaching a volume it is assumed that a potentially dirty
        filesystem isn't a concern and in the case that the container is just
        stopped the filesystem will already have all descriptors closed so the
        lazy forced unmount has no adverse affect.
        """
        if lazy:
            return 'umount -l -f %s' % mount
        else:
            return 'umount %s' % mount

    def add_host_umount_line(self):
        """
        Add the host umount line to the CTID.umount file
        """
        LOG.debug(_('Host umount line: %s') % self.host_umount_line())
        self.append(self.host_umount_line())

    def add_container_umount_line(self):
        """
        Add the container umount line to the CTID.umount file
        """
        LOG.debug(_('Container umount line: %s') %
                  self.container_umount_line())
        self.append(self.container_umount_line())

    def delete_umounts(self):
        """
        In the case that we need to detach a volume from a container we need to
        remove the umount lines from the file object's contents.
        """
        LOG.debug(_('Deleting umount line: %s') % self.container_umount_line())
        self.delete(self.container_umount_line())
        LOG.debug(_('Deleting umount line: %s') % self.host_umount_line())
        self.delete(self.host_umount_line())

    def unmount_all(self):
        """
        Wrapper for unmounting both the container mounted filesystem and the
        original host mounted filesystem
        """
        # Unmount the container mount
        LOG.debug(_('Unmounting: %s') % self.container_umount_line())
        self.unmount(self.container_umount_line())

        # Now unmount the host mount
        LOG.debug(_('Unmounting: %s') % self.host_umount_line())
        self.unmount(self.host_umount_line())

    @staticmethod
    def unmount(mount_line):
        """
        Helper method to use nova commandline utilities to unmount the
        filesystem given as an argument.
        """
        mount_line = mount_line.split()
        ovz_utils.execute(*mount_line, run_as_root=True)
