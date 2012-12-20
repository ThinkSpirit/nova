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
This class will be used to tie volume operations together and wrap other
volume related classes like Mounts, Umounts and Volume to simplify their
use.
"""
import json
from nova import context
from nova import db
from nova.openstack.common import log as logging
from nova.openstack.common import cfg

CONF = cfg.CONF
LOG = logging.getLogger('nova.virt.openvz.volume_ops')


class OVZInstanceVolumeOps(object):
    def __init__(self, instance):
        self.instance = instance

    def attach_all_volumes(self):
        """
        iterate through all volumes and do any tasks necessary to attach them
        to the host in preparation for the guest to use them.
        """
        volumes, connection_infos = self.block_device_mappings()
        if volumes:
            for volume in volumes:
                connection_info = None
                for info in connection_infos:
                    if info['volume_id'] == volume['id']:
                        LOG.debug(
                            _('Found matching connection info for volume %s')
                            % volume['id'])
                        connection_info = info['connection_info']
                if connection_info:
                    LOG.debug(_('connection_info: %s') %
                              connection_info)
                    # Right now the connection info stuff is a json marshaled
                    # string so if it is a string, lets load it proper
                    if isinstance(connection_info, basestring):
                        connection_info = json.loads(connection_info)
                        # leave room for us to use other storage drivers in the
                    # future, i.e. cifs, nfs, etc...
                    if connection_info['driver_volume_type'] == 'iscsi':
                        LOG.debug(_('Volume type is iSCSI'))
                        from nova.virt.openvz.volume_drivers.iscsi\
                        import OVZISCSIStorageDriver
                        LOG.debug(_('iSCSI volume driver loaded'))
                        vol = OVZISCSIStorageDriver(connection_info,
                                                    self.instance['id'],
                                                    volume['mountpoint'])
                        vol.discover_volume()
                        LOG.debug(_('Attached volume: %s') % volume['id'])
                    else:
                        LOG.warn(_('Cannot attach volume: %s') %
                                 volume['id'])

    def detach_all_volumes(self):
        """
        Iterate through all known volumes and take care of all the things
        that need to be done to detach them.
        """
        volumes, connection_infos = self.block_device_mappings()
        if volumes:
            for volume in volumes:
                connection_info = None
                for info in connection_infos:
                    if info['volume_id'] == volume['id']:
                        LOG.debug(
                            _('Found matching connection info for volume %s')
                            % volume['id'])
                        connection_info = info['connection_info']
                if connection_info:
                    LOG.debug(_('connection_info: %s') %
                              connection_info)
                    # Right now the connection info stuff is a json marshaled
                    # string so if it is a string, lets load it proper
                    if isinstance(connection_info, basestring):
                        connection_info = json.loads(connection_info)
                        # leave room for us to use other storage drivers in the
                    # future, i.e. cifs, nfs, etc...
                    if connection_info['driver_volume_type'] == 'iscsi':
                        LOG.debug(_('Volume type is iSCSI'))
                        from nova.virt.openvz.volume_drivers.iscsi\
                        import OVZISCSIStorageDriver
                        LOG.debug(_('iSCSI volume driver loaded'))
                        vol = OVZISCSIStorageDriver(connection_info,
                                                    self.instance['id'],
                                                    volume['mountpoint'])
                        vol.disconnect_iscsi_volume()
                        LOG.debug(_('Detached volume: %s') % volume['id'])
                    else:
                        LOG.warn(_('Cannot detach volume: %s') %
                                 volume['id'])

    def mountpoints(self):
        """
        returns a list of mountpoints that are associated with this instance
        """
        volumes = self.volume_list()
        mountpoints = []
        if volumes:
            for volume in volumes:
                mountpoints.append(volume['mountpoint'])
        return mountpoints

    def find_connection_info_by_volume(self, volume_id):
        """
        :param volume_id: The id used to get connection data for
        """
        connection_infos = self._connection_infos()
        if connection_infos:
            for info in connection_infos:
                if info['volume_id'] == volume_id:
                    LOG.debug(_('Found connection info for volume: %s') %
                              volume_id)
                    # A related connection info is found so lets spit it back
                    # out.
                    return info['connection_info']
        # if we can find no connection info for the volume then return None
        # so it can be handled properly
        return None

    def volume_list(self):
        """
        Returns the volumes for an instance
        """
        return db.volume_get_all_by_instance_uuid(context.get_admin_context(),
                                                  self.instance['uuid'])

    def _connection_infos(self):
        """
        Returns the connection info for volumes on an instance
        """
        return db.block_device_mapping_get_all_by_instance(
            context.get_admin_context(), self.instance['uuid'])

    def block_device_mappings(self):
        """
        Returns a block device mapping that we can use for volume operations
        """
        return self.volume_list(), self._connection_infos()
