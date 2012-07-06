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
from nova.openstack.common import log as logging
from nova.virt.openvz.file import OVZFile
from nova.virt.openvz import utils as ovz_utils
from nova import flags

FLAGS = flags.FLAGS

LOG = logging.getLogger('nova.virt.openvz.mounts')


class OVZMounts(OVZFile):
    """
    OVZMounts is a sub-class of OVZFile that applies mount/umount file specific
    operations to the object.
    """
    def __init__(self, filename, mount, instance_id, device=None, uuid=None):
        super(OVZMounts, self).__init__(filename, 755)
        self.device = device
        self.uuid = uuid

        # Generate the mountpoint paths
        self.host_mount_container_root = '%s/%s' %\
                                         (FLAGS.ovz_ve_host_mount_dir,
                                          instance_id)
        self.host_mount_container_root = os.path.abspath(
            self.host_mount_container_root)
        self.container_mount = '%s/%s/%s' %\
                               (FLAGS.ovz_ve_private_dir, instance_id, mount)
        self.container_root_mount = '%s/%s/%s' %\
                                    (FLAGS.ovz_ve_root_dir, instance_id, mount)
        self.host_mount = '%s/%s' %\
                          (self.host_mount_container_root, mount)
        # Fix mounts to remove duplicate slashes
        self.container_mount = os.path.abspath(self.container_mount)
        self.container_root_mount = os.path.abspath(self.container_root_mount)
        self.host_mount = os.path.abspath(self.host_mount)

    def delete_full_mount_path(self):
        """
        Issuing an rm -rf is a little careless because it is
        possible for 2 filesystems to be mounted within each other.  For
        example, one filesystem could be mounted as /var/lib in the container
        and another be mounted as /var/lib/mysql.  An rmdir will return an
        error if we try to remove a directory not empty so it seems to me the
        best way to recursively delete a mount path is to actually start at the
        uppermost mount and work backwards.

        We will still need to put some safeguards in place to protect users
        from killing their machine but rmdir does a pretty good job of this
        already.
        """
        mount_path = self.host_mount
        while mount_path != self.host_mount_container_root:
            # Just a safeguard for root
            if mount_path == '/':
                # while rmdir would fail in this case, lets just break out
                # anyway to be safe.
                break

            if not ovz_utils.delete_path(mount_path):
                # there was an error returned from rmdir.  It is assumed that
                # if this happened it is because the directory isn't empty
                # so we want to stop where we are.
                break

            # set the path to the directory sub of the current directory we are
            # working on.
            mount_path = os.path.dirname(mount_path)

    def delete_line_that_contains(self, pattern):
        """
        This method facilitates removing the mount line from the container's
        mount line from the CTID.mount file.  The reason this is difficult is
        that the uuid for the filesystem is created when the volume is attached
        and we don't want to have to call filesystem utils to get the uuid when
        we know the mountpoint of the volume.  So instead we'll look through
        each line in the mount file and remove the line or lines that have to
        do with the mount point of the volume being operated on.
        """
        lines_to_remove = list()
        for line in self.contents:
            if pattern in line:
                lines_to_remove.append(line)
        self.delete(lines_to_remove)
