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
OpenVZ doesn't allow for a script to be run after a container has started up
using the host node's context so we are implementing one here
"""

import os
from nova.openstack.common import log as logging
from nova import flags
from nova.virt.openvz.file import OVZFile

FLAGS = flags.FLAGS
LOG = logging.getLogger('nova.virt.openvz.boot')


class OVZBootFile(OVZFile):
    def __init__(self, instance_id, permissions):
        """
        Child class of OVZFile used to manage the CTID.boot file.  This file
        will be executed line by line after the container has started but
        using the host's context.

        :param instance_id: Instance used for the file
        """
        filename = "%s/%s.boot" % (FLAGS.ovz_config_dir, instance_id)
        filename = os.path.abspath(filename)
        super(OVZBootFile, self).__init__(filename, permissions)
