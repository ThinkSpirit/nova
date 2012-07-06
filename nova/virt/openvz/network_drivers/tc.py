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
import random
import os
from nova import exception
from nova.utils import synchronized
from nova.virt.openvz import utils as ovz_utils
from nova import db
from nova import context
from nova import flags
from nova.openstack.common import log as logging
from Cheetah.Template import Template

FLAGS = flags.FLAGS
LOG = logging.getLogger('nova.virt.openvz.network_drivers.tc')


class OVZTcRules():
    # Set our class variables if they don't exist
    # TODO(imsplitbit): figure out if there is a more pythonic way to do this
    try:
        available_ids
    except NameError:
        available_ids = list()

    try:
        inflight_ids
    except NameError:
        inflight_ids = list()

    def __init__(self):
        """
        This class is used to return TC rulesets for both a host and guest for
        use with host and guest startup and shutdown.
        """
        if not len(OVZTcRules.available_ids):
            LOG.debug(_('Available_ids is empty, filling it with numbers'))
            OVZTcRules.available_ids = [
                i for i in range(1, FLAGS.ovz_tc_id_max)
            ]

        # do an initial clean of the available ids
        self._remove_used_ids()
        LOG.debug(
            _('OVZTcRules thinks ovz_tc_host_slave_device is set to %s')
            % FLAGS.ovz_tc_host_slave_device)

    def instance_info(self, instance_id, address, vz_iface):
        """
        Use this method when creating or resizing an instance.  It will
        generate a new tc ruleset

        :param instance_id: Instance to generate the rules for
        :param address: IP address for the instance
        :param vz_iface: interface on the hosts bridge that is associated with
        the instance
        """
        if not instance_id:
            self.instance_type = dict()
            self.instance_type['memory_mb'] = 2048
        else:
            admin_context = context.get_admin_context()
            self.instance = db.instance_get(admin_context, instance_id)
            self.instance_type = db.instance_type_get(admin_context,
                                            self.instance['instance_type_id'])
        LOG.debug(_('CT TC address: %s') % address)

        self.address = address
        self.vz_iface = vz_iface

        # Calculate the bandwidth total by figuring out how many units we have
        self.bandwidth = int(round(self.instance_type['memory_mb'] /
                                   FLAGS.ovz_memory_unit_size)) *\
                         FLAGS.ovz_tc_mbit_per_unit
        LOG.debug(_('Allotted bandwidth: %s') % self.bandwidth)
        self.tc_id = self._get_instance_tc_id()
        if not self.tc_id:
            LOG.debug(_('No preassigned tc_id for %s, getting a new one') %
                      instance_id)
            self.tc_id = self.get_id()

        self._save_instance_tc_id()
        LOG.debug(_('Saved the tc_id in the database for the instance'))

    @synchronized('get_id_lock')
    def get_id(self):
        """
        Uses nova utils decorator @synchronized to make sure that we do not
        return duplicate available ids.  This will return a random id number
        between 1 and 9999 which are the limits of TC.
        """
        self._remove_used_ids()
        LOG.debug(_('Pulling new TC id'))
        id = self._pull_id()
        LOG.debug(_('TC id %s pulled, testing for dupe') % id)
        while id in OVZTcRules.inflight_ids:
            LOG.debug(_('TC id %s inflight already, pulling another') % id)
            id = self._pull_id()
            LOG.debug(_('TC id %s pulled, testing for dupe') % id)
        LOG.debug(_('TC id %s pulled, verified unique'))
        self._reserve_id(id)
        return id

    def container_start(self):
        template = self._load_template('tc_container_start.template')
        search_list = {
            'prio': self.tc_id,
            'host_iface': FLAGS.ovz_tc_host_slave_device,
            'vz_iface': self.vz_iface,
            'bandwidth': self.bandwidth,
            'vz_address': self.address,
            'line_speed': FLAGS.ovz_tc_max_line_speed
        }
        ovz_utils.save_instance_metadata(self.instance['id'],
                                         'tc_id', self.tc_id)
        return self._fill_template(template, search_list).splitlines()

    def container_stop(self):
        template = self._load_template('tc_container_stop.template')
        search_list = {
            'prio': self.tc_id,
            'host_iface': FLAGS.ovz_tc_host_slave_device,
            'vz_iface': self.vz_iface,
            'bandwidth': self.bandwidth,
            'vz_address': self.address
        }
        ovz_utils.save_instance_metadata(self.instance['id'],
                                         'tc_id', self.tc_id)
        return self._fill_template(template, search_list).splitlines()

    def host_start(self):
        template = self._load_template('tc_host_start.template')
        search_list = {
            'host_iface': FLAGS.ovz_tc_host_slave_device,
            'line_speed': FLAGS.ovz_tc_max_line_speed
        }
        return self._fill_template(template, search_list).splitlines()

    def host_stop(self):
        template = self._load_template('tc_host_stop.template')
        search_list = {
            'host_iface': FLAGS.ovz_tc_host_slave_device
        }
        return self._fill_template(template, search_list).splitlines()

    def _load_template(self, template_name):
        """
        read and return the template file
        """
        full_template_path = '%s/%s' % (
            FLAGS.ovz_tc_template_dir, template_name)
        full_template_path = os.path.abspath(full_template_path)
        try:
            LOG.debug(_('Opening template file: %s') % full_template_path)
            template_file = open(full_template_path).read()
            LOG.debug(_('Template file opened successfully'))
            return template_file
        except Exception as err:
            LOG.error(_('Unable to open template: %s') % full_template_path)
            raise exception.FileNotFound(err)

    def _fill_template(self, template, search_list):
        """
        Take the vars in search_list and fill out template
        """
        return str(Template(template, searchList=[search_list]))

    def _pull_id(self):
        """
        Pop a random id from the list of available ids for tc rules
        """
        return OVZTcRules.available_ids[random.randint(
            0, len(OVZTcRules.available_ids) - 1)]

    def _list_existing_ids(self):
        LOG.debug(_('Attempting to list existing IDs'))
        out = ovz_utils.execute('tc', 'filter', 'show', 'dev',
                                FLAGS.ovz_tc_host_slave_device,
                                run_as_root=True)
        ids = list()
        for line in out.splitlines():
            line = line.split()
            if line[0] == 'filter':
                id = int(line[6])
                if not id in ids:
                    ids.append(int(id))

        # get the metadata for instances from the database
        # this will provide us with any ids of instances that aren't
        # currently running so that we can remove active and provisioned
        # but inactive ids from the available list
        instances_metadata = ovz_utils.read_all_instance_metadata()
        LOG.debug(_('Instances metadata: %s') % instances_metadata)
        if instances_metadata:
            for instance_id, meta in instances_metadata.iteritems():
                tc_id = meta.get('tc_id')
                if tc_id:
                    if not tc_id in ids:
                        LOG.debug(
                            _('TC id "%(tc_id)s" for instance '
                              '"%(instance_id)s" found') % locals())
                        ids.append(int(tc_id))
        return ids

    def _reserve_id(self, id):
        """
        This removes the id from the available_ids and adds it to the
        inflight_ids
        """
        LOG.debug(_('Beginning reservation process'))
        OVZTcRules.inflight_ids.append(id)
        LOG.debug(_('Added id "%s" to inflight_ids') % id)
        OVZTcRules.available_ids.remove(id)
        LOG.debug(_('Removed id "%s" from available_ids') % id)

    def _remove_used_ids(self):
        """
        Clean ids that are currently provisioned on the host from the
        list of available_ids
        """
        LOG.debug(_('Beginning cleanup of used ids'))
        used_ids = self._list_existing_ids()
        LOG.debug(_('Used ids found, removing from available_ids'))
        for id in used_ids:
            if id in OVZTcRules.available_ids:
                OVZTcRules.available_ids.remove(id)
        LOG.debug(_('Removed all ids in use'))

    def _save_instance_tc_id(self):
        """
        Save the tc id in the instance metadata in the database
        """
        ovz_utils.save_instance_metadata(self.instance['id'], 'tc_id',
                                         self.tc_id)

    def _get_instance_tc_id(self):
        """
        Look up instance metadata in the db and see if there is already
        a tc_id for the instance
        """
        instance_metadata = ovz_utils.read_instance_metadata(
            self.instance['id'])
        LOG.debug(_('Instances metadata: %s') % instance_metadata)
        if instance_metadata:
            tc_id = instance_metadata.get('tc_id')
            LOG.debug(
                _('TC id for instance %(instance_id)s is %(tc_id)s') %
                {'instance_id': self.instance['id'], 'tc_id': tc_id})
            return tc_id
