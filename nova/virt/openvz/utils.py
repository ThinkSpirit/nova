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

import multiprocessing
import os
import platform
import uuid
import sys
import re
from nova import exception
from nova import utils
from nova.openstack.common import log as logging
from nova import flags
from nova import context
from nova import db

FLAGS = flags.FLAGS
LOG = logging.getLogger('nova.virt.openvz.utils')


def execute(*cmd, **kwargs):
    """
    This is a wrapper for utils.execute so as to reduce the amount of
    duplicated code in the driver.
    """
    if 'raise_on_error' in kwargs:
        raise_on_error = kwargs.pop('raise_on_error')
    else:
        raise_on_error = True

    try:
        out, err = utils.execute(*cmd, **kwargs)
        if out:
            LOG.debug(_('Stdout from %(command)s: %(out)s') %
                      {'command': cmd[0], 'out': out})
        if err:
            LOG.debug(_('Stderr from %(command)s: %(out)s') %
                      {'command': cmd[0], 'out': err})
        return out
    except exception.ProcessExecutionError as err:
        LOG.error(_('Stderr from %(command)s: %(out)s') %
                  {'command': cmd[0], 'out': err})
        if raise_on_error:
            raise exception.InstanceUnacceptable(
                _('Error running %(command)s: %(out)s') %
                {'command': cmd[0], 'out': err})
        else:
            return None


def mkfs(path, fs, fs_uuid=None, fs_label=None):
    """Format a file or block device

    :param fs: Filesystem type (examples include 'ext3', 'ext4'
           'btrfs', etc.)
    :param path: Path to file or block device to format
    :param fs_uuid: Volume uuid to use
    :param fs_label: Volume label to use
    """
    if not fs_uuid:
        fs_uuid = str(uuid.uuid4())

    args = ['mkfs', '-F', '-t', fs]
    if fs_uuid:
        args.extend(['-U', fs_uuid])
    if fs_label:
        args.extend(['-L', fs_label])
    args.append(path)
    LOG.debug(_('Mkfs command: %s') % args)
    execute(*args, run_as_root=True)


def get_fs_uuid(device):
    """
    Because we may need to operate on a volume by it's uuid
    we need a way to see if a filesystem has a uuid on it
    """
    LOG.debug(_('Getting FS UUID for: %s') % device)
    out = execute('blkid', '-o', 'value', '-s', 'UUID', device,
                  run_as_root=True)
    if out:
        LOG.debug(_('Found something in get_fs_uuid'))
        for line in out.split('\n'):
            line = line.strip()
            LOG.debug(_('Examining line: %s') % line)
            result = re.search(
                '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',
                line)
            if result:
                LOG.debug(
                    _('Found the FS UUID for: %(device)s It is: %(uuid)s') %
                    {'device': device, 'uuid': result.group(0)})
                return result.group(0)
    return None


def get_vcpu_total():
    """Get vcpu number of physical computer.

    :returns: the number of cpu core.

    """

    # On certain platforms, this will raise a NotImplementedError.
    try:
        return multiprocessing.cpu_count()
    except NotImplementedError:
        LOG.warn(_("Cannot get the number of cpu, because this "
                   "function is not implemented for this platform. "
                   "This error can be safely ignored for now."))
        return 0


def get_cpuinfo():
    """
    Gather detailed statistics on the host's cpus
    """

    if sys.platform.upper() not in ['LINUX2', 'LINUX3']:
        return 0

    cpuinfo = dict()
    cpuinfo['features'] = list()

    # Gather the per core/hyperthread info for accumulation
    for line in open('/proc/cpuinfo').readlines():
        # Do some cleaning up to make searching for keys easier
        line = line.split(':')
        line[0] = line[0].strip().replace(' ', '_')
        if len(line) > 1:
            line[1] = line[1].strip()

        if line[0] == 'vendor_id':
            cpuinfo['vendor'] = line[1]

        if line[0] == 'model_name':
            cpuinfo['model'] = line[1]

        if line[0] == 'flags':
            cpuinfo['features'] += line[1].split()

    cpuinfo['arch'] = platform.uname()[4]

    # dedupe the features
    cpuinfo['features'] = list(set(cpuinfo['features']))

    return cpuinfo


def get_iscsi_initiator():
    """
    This is a basic implementation of the iscsi stuff needed for external
    volumes.  This should live in a utility module when the openvz driver is
    broken up.
    """
    # code borrowed from libvirt utils
    contents = utils.read_file_as_root('/etc/iscsi/initiatorname.iscsi')
    for l in contents.split('\n'):
        if l.startswith('InitiatorName='):
            return l[l.index('=') + 1:].strip()


def get_cpuunits_capability():
    """
    Use openvz tools to discover the total processing capability of the
    host node.  This is done using the vzcpucheck utility.

    Run the command:

    vzcpucheck

    If this fails to run an exception is raised because the output of this
    method is required to calculate the overall bean count available on the
    host to be carved up for guests to use.
    """
    result = {}
    out = execute('vzcpucheck', run_as_root=True)
    for line in out.splitlines():
        line = line.split()
        if len(line) > 0:
            if line[0] == 'Power':
                LOG.debug(_('Power of host: %s') % line[4])
                result['total'] = int(line[4])
            elif line[0] == 'Current':
                LOG.debug(_('Current cpuunits subscribed: %s') % line[3])
                result['subscribed'] = int(line[3])

    if len(result.keys()) == 2:
        return result
    else:
        raise exception.InvalidCPUInfo(
            _("Cannot determine the CPUUNITS for host"))


def get_vcpu_used():
    """
    OpenVz doesn't have the concept of VCPUs but we can approximate
    what they would be by looking at the percentage of subscribed
    cpuunits.

    :returns: The total number of vcpu that currently used.

    """

    cpuunits = get_cpuunits_capability()
    cpus = get_vcpu_total()
    pct_cpuunits_used = float(cpuunits['subscribed']) / cpuunits['total']
    return int(cpus * pct_cpuunits_used)


def get_memory_mb_total():
    """Get the total memory size(MB) of physical computer.

    :returns: the total amount of memory(MB).

    """

    if sys.platform.upper() not in ['LINUX2', 'LINUX3']:
        return 0

    meminfo = open('/proc/meminfo').read().split()
    idx = meminfo.index(u'MemTotal:')
    # transforming kb to mb.
    return int(meminfo[idx + 1]) / 1024


def get_memory_mb_used(instance_id=None, block_size=4096):
    """
    Get the free memory size(MB) of physical computer.

    :returns: the total committed of memory(MB).

    """

    if instance_id:
        cmd = "vzlist -H -o ctid,privvmpages.l %s" % instance_id
    else:
        cmd = "vzlist --all -H -o ctid,privvmpages.l"

    cmd = cmd.split()
    total_used_mb = 0
    out = execute(*cmd, run_as_root=True)
    for line in out.splitlines():
        line = line.split()
        total_used_mb += ((int(line[1]) * block_size) / 1024 ** 2)
    return total_used_mb


def get_local_gb(path):
    """
    Get the total hard drive space at <path>
    """

    hddinfo = os.statvfs(path)
    total = hddinfo.f_frsize * hddinfo.f_blocks
    free = hddinfo.f_frsize * hddinfo.f_bavail
    used = hddinfo.f_frsize * (hddinfo.f_blocks - hddinfo.f_bfree)
    return {'total': total, 'free': free, 'used': used}


def get_local_gb_total():
    """
    Get the total hdd size(GB) of physical computer.

    :returns:
        The total amount of HDD(GB).
        Note that this value shows a partition where
        OVZ_VE_PRIVATE_DIR is.

    """

    return get_local_gb(FLAGS.ovz_ve_private_dir)['total'] / (1024 ** 3)


def get_local_gb_used():
    """
    Get the total used disk space on the host computer.

    :returns:
        The total amount of HDD(GB)
        Note that this value show  a partition where
        OVZ_VE_PRIVATE_DIR is.
    """

    return get_local_gb(FLAGS.ovz_ve_private_dir)['used'] / (1024 ** 3)


def get_hypervisor_type():
    """
    Just return the type of hypervisor we are using.  This will always
    be 'openvz'
    """

    return 'openvz'


def get_hypervisor_version():
    """
    Since the version of the hypervisor is really determined by the kernel
    it is running lets just return that for version.  I don't think it
    matters at this point and this is the most accurate representation of
    what *version* we are running.
    """

    return platform.uname()[2]


def make_dir(path):
    """
    This is the method that actually creates directories. This is used by
    make_path and can be called directly as a utility to create
    directories.

    Run the command:

    mkdir -p <path>

    If this doesn't run an exception is raised as this path creation is
    required to ensure that other file operations are successful. Such
    as creating the path for a file yet to be created.
    """
    if not os.path.exists(path):
        execute('mkdir', '-p', path, run_as_root=True)


def delete_path(path):
    """
    After a volume has been detached and the mount statements have been
    removed from the mount configuration for a container we want to remove
    the paths created on the host system so as not to leave orphaned files
    and directories on the system.

    This runs a command like:
    sudo rmdir /mnt/100/var/lib/mysql
    """
    try:
        execute('rmdir', path, run_as_root=True)
        return True
    except exception.InstanceUnacceptable:
        return False


def set_permissions(filename, permissions):
    """
    Because nova runs as an unprivileged user we need a way to mangle
    permissions on files that may be owned by root for manipulation

    Run the command:

    chmod <permissions> <filename>

    If this doesn't run an exception is raised because the permissions not
    being set to what the application believes they are set to can cause
    a failure of epic proportions.
    """
    execute('chmod', permissions, filename, run_as_root=True)


def save_instance_metadata(instance_id, key, value):
    """
    Simple wrapper for saving data to the db as metadata for an instance

    :param instance_id: Instance id to add metadata to
    :param key: Key to save to db
    :param value: Value of key to save to db
    """
    LOG.debug(
        _('Beginning saving instance metadata for '
          '%(instance_id)s: {%(key)s: %(value)s}') % locals())
    admin_context = context.get_admin_context()
    LOG.debug(_('Got admin context'))
    try:
        instance = db.instance_get(admin_context, instance_id)
        LOG.debug(_('Fetched instance'))
        db.instance_metadata_update(admin_context,
                                    instance['uuid'],
                {key: value},
                                    False)
        LOG.debug(_('Updated instance metadata'))
    except exception.InstanceNotFound as err:
        LOG.error(_('Instance not in the database: %s') % instance_id)
        LOG.error(_('Consistency check is needed, orphaned instance: %s') %
                  instance_id)
    except exception.DBError as err:
        LOG.error(
            _('Error saving metadata {%(key)s: %(value)s} '
              'for %(instance_id)s') % locals())
        LOG.err(err)


def read_instance_metadata(instance_id):
    """
    Read the metadata in the database for a given instance

    :param instance_id: Instance to read all metadata for from the db
    :returns: dict()
    """
    LOG.debug(_('Beginning read_instance_metadata: %s') % instance_id)
    admin_context = context.get_admin_context()
    LOG.debug(_('Got admin context for db access'))
    try:
        instance = db.instance_get(admin_context, instance_id)
        LOG.debug(_('Fetched instance'))
        result = db.instance_metadata_get(admin_context, instance['uuid'])
        instance_meta = dict()
        LOG.debug(_('Results from read_instance_metadata: %s') % result)
        for key, value in result.iteritems():
            LOG.debug(_('Metadata %(key)s: %(value)s') %
                      {'key': key, 'value': result[key]})
            instance_meta[key] = result[key]
        return instance_meta
    except exception.InstanceNotFound as err:
        LOG.error(_('Instance not in the database: %s') % instance_id)
        LOG.error(_('Consistency check is needed, orphaned instance: %s') %
                  instance_id)
        return dict()
    except exception.DBError as err:
        LOG.error(_('Error reading metadata from db for %s') % instance_id)
        LOG.error(err)
        return dict()


def read_all_instance_metadata():
    """
    Fetch a list of all instance ids on the local host and for each get
    the associated metadata and return it in a dictionary

    :returns dict():
    """
    instances_metadata = {}
    out = execute('vzlist', '-H', '-o', 'ctid', '--all', run_as_root=True)
    for line in out.splitlines():
        instance_id = line.strip()
        instances_metadata[instance_id] = read_instance_metadata(instance_id)
    return instances_metadata


def remove_instance_metadata_key(instance_id, key):
    """
    Remove a specific key from an instance's metadata
    """
    LOG.debug(_('Getting an admin context for remove_instance_metadata_key'))
    admin_context = context.get_admin_context()
    LOG.debug(_('Got admin context, fetching instance ref'))
    instance = db.instance_get(admin_context, instance_id)
    LOG.debug(_('Got instance ref, beginning deletion of metadata'))
    try:
        db.instance_metadata_delete(admin_context, instance['uuid'], key)
        return True
    except exception.DBError as err:
        LOG.error(_('Error deleting metadata for instance %s') % instance_id)
        LOG.error(err)
        return False


def remove_instance_metadata(instance_id):
    """
    Clean up instance metadata for an instance
    """
    LOG.debug(_('Getting an admin context for remove_instance_metadata'))
    admin_context = context.get_admin_context()
    LOG.debug(_('Got admin context, fetching instance ref'))
    try:
        instance = db.instance_get(admin_context, instance_id)
        LOG.debug(_('Fetched instance'))
        LOG.debug(_('Fetching metadata for %s') % instance_id)
        meta = read_instance_metadata(instance_id)
        LOG.debug(_('Metadata for instance %(instance_id)s is %(meta)s') %
                  locals())
        for key, value in meta.iteritems():
            LOG.debug(_('Attempting to delete key:%(key)s, value:%(value)s') %
                      locals())
            db.instance_metadata_delete(admin_context, instance['uuid'], key)
            LOG.debug(
                _('Deleted key:%(key)s, value:%(value)s for %(instance_id)s')
                % locals())
        return True
    except exception.InstanceNotFound as err:
        LOG.error(_('Instance not in the database: %s') % instance_id)
        LOG.error(_('Consistency check is needed, orphaned instance: %s') %
                  instance_id)
        return False
    except exception.DBError as err:
        LOG.error(_('Error deleting metadata for instance %s') % instance_id)
        LOG.error(err)
        return False


def generate_network_dict(instance_id, network_info):
    interfaces = list()
    interface_num = -1
    for (network, mapping) in network_info:
        if mapping['ips']:
            interface_num += 1

            #TODO(imsplitbit): make this work for ipv6
            address_v6 = None
            gateway_v6 = None
            netmask_v6 = None
            if FLAGS.use_ipv6:
                address_v6 = mapping['ip6s'][0]['ip']
                netmask_v6 = mapping['ip6s'][0]['netmask']
                gateway_v6 = mapping['gateway6']

            interface_info = {
                'id': instance_id,
                'interface_number': interface_num,
                'bridge': network['bridge'],
                'name': 'eth%d' % interface_num,
                'mac': mapping['mac'],
                'address': mapping['ips'][0]['ip'],
                'netmask': mapping['ips'][0]['netmask'],
                'gateway': mapping['gateway'],
                'broadcast': mapping['broadcast'],
                'dns': ' '.join(mapping['dns']),
                'address_v6': address_v6,
                'gateway_v6': gateway_v6,
                'netmask_v6': netmask_v6
            }
            interface_info['vz_host_if'] = ('veth%s.%s' %
                                            (interface_info['id'],
                                             interface_info['name']))
            interfaces.append(interface_info)
    return interfaces
