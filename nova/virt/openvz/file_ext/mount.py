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
from nova import flags

FLAGS = flags.FLAGS

LOG = logging.getLogger('nova.virt.openvz.mount')


class OVZMountFile(OVZMounts):
    """
    methods used to specifically interact with the /etc/vz/conf/CTID.mount file
    that handles all mounted filesystems for containers.
    """
    def host_mount_line(self):
        """
        OpenVz is unlike most hypervisors in that it cannot actually do
        anything with raw devices. When migrating containers from host to host
        you are not guaranteed to have the same device name on each host so we
        need a conditional that generates a mount line that can use a UUID
        attribute that can be added to a filesystem which allows us to be
        device name agnostic.
        """
        #TODO(imsplitbit): Add LABEL= to allow for disk labels as well
        mount_line = 'mount -o %s UUID=%s %s' % (
            FLAGS.ovz_mount_options, self.uuid, self.host_mount)
        return mount_line

    def container_mount_line(self):
        """
        Generate a mount line that will allow OpenVz to mount a filesystem
        within the container's root filesystem.  This is done with the bind
        mount feature and is the prescribed method for OpenVz
        """
        if FLAGS.ovz_use_bind_mount:
            return 'mount --bind %s %s' %\
                   (self.host_mount, self.container_root_mount)
        else:
            return 'mount -n -t simfs %s %s -o %s' % (
                self.host_mount, self.container_root_mount, self.host_mount)

    def delete_mounts(self, fs_uuid):
        """
        When detaching a volume from a container we need to also remove the
        mount statements from the CTID.mount file.
        """
        # delete the host mount line from the CTID.mount file
        LOG.debug(_('Deleting mount line: %s') % self.host_mount_line())
        self.delete(self.host_mount_line())

        # remove the
        LOG.debug(_('Deleting mount line: %s') % self.container_mount_line())
        self.delete(self.container_mount_line())

    def add_container_mount_line(self):
        """
        Add the generated container mount line to the CTID.mount script
        """
        LOG.debug(_('Container mount line: %s') % self.container_mount_line())
        self.append(self.container_mount_line())

    def add_host_mount_line(self):
        """
        Add the generated host mount line to the CTID.mount script
        """
        LOG.debug(_('Host mount line: %s') % self.host_mount_line())
        self.append(self.host_mount_line())

    def make_host_mount_point(self):
        """
        Create the host mount point if it doesn't exist.  This is required
        to allow for container startup.
        """
        self.make_dir(self.host_mount)

    def make_container_mount_point(self):
        """
        Create the container private mount point if it doesn't exist.  This is
        required to happen before the container starts so that when it chroots
        in /vz/root/CTID the path will exist to match container_root_mount
        """
        self.make_dir(self.container_mount)

    def make_container_root_mount_point(self):
        """
        Unused at the moment but exists in case we reach a condition that the
        container starts and somehow make_container_mount_point didn't get run.
        """
        # TODO(imsplitbit): Look for areas this can be used.  Right now the
        # process is very prescibed so it doesn't appear necessary just yet.
        # We will need this in the future when we do more dynamic operations.
        self.make_dir(self.container_root_mount)
