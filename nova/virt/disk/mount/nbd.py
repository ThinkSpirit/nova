# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Support for mounting images with qemu-nbd"""

import os
import random
import re
import time

from nova.openstack.common import cfg
from nova.openstack.common import log as logging
from nova import utils
from nova.virt.disk.mount import api

LOG = logging.getLogger(__name__)

nbd_opts = [
    cfg.IntOpt('timeout_nbd',
               default=10,
               help='time to wait for a NBD device coming up'),
    ]

CONF = cfg.CONF
CONF.register_opts(nbd_opts)

NBD_DEVICE_RE = re.compile('nbd[0-9]+')
MAX_NBD_WAIT = 30


class NbdMount(api.Mount):
    """qemu-nbd support disk images."""
    mode = 'nbd'

    def _detect_nbd_devices(self):
        """Detect nbd device files."""
        return filter(NBD_DEVICE_RE.match, os.listdir('/sys/block/'))

    def _find_unused(self, devices):
        for device in devices:
            if not os.path.exists(os.path.join('/sys/block/', device, 'pid')):
                return device
        LOG.warn(_('No free nbd devices'))
        return None

    def _allocate_nbd(self):
        if not os.path.exists('/sys/block/nbd0'):
            LOG.error(_('ndb module not loaded'))
            self.error = _('nbd unavailable: module not loaded')
            return None

        devices = self._detect_nbd_devices()
        random.shuffle(devices)
        device = self._find_unused(devices)
        if not device:
            # really want to log this info, not raise
            self.error = _('No free nbd devices')
            return None
        return os.path.join('/dev', device)

    def _read_pid_file(self, pidfile):
        # This is for unit test convenience
        with open(pidfile) as f:
            pid = int(f.readline())
        return pid

    def _inner_get_dev(self):
        device = self._allocate_nbd()
        if not device:
            return False

        # NOTE(mikal): qemu-nbd will return an error if the device file is
        # already in use.
        LOG.debug(_('Get nbd device %(dev)s for %(imgfile)s'),
                  {'dev': device, 'imgfile': self.image})
        _out, err = utils.trycmd('qemu-nbd', '-c', device, self.image,
                                 run_as_root=True)
        if err:
            self.error = _('qemu-nbd error: %s') % err
            return False

        # NOTE(vish): this forks into another process, so give it a chance
        # to set up before continuing
        pidfile = "/sys/block/%s/pid" % os.path.basename(device)
        for _i in range(CONF.timeout_nbd):
            if os.path.exists(pidfile):
                self.device = device
                break
            time.sleep(1)
        else:
            _out, err = utils.trycmd('qemu-nbd', '-d', device,
                                     run_as_root=True)
            if err:
                LOG.warn(_('Detaching from erroneous nbd device returned '
                           'error: %s'), err)
            self.error = _('nbd device %s did not show up') % device
            return False

        self.error = ''
        self.linked = True
        return True

    def get_dev(self):
        """Retry requests for NBD devices."""
        start_time = time.time()
        device = self._inner_get_dev()
        while not device:
            LOG.info(_('nbd device allocation failed. Will retry in 2 '
                       'seconds.'))
            time.sleep(2)
            if time.time() - start_time > MAX_NBD_WAIT:
                LOG.warn(_('nbd device allocation failed after repeated '
                           'retries.'))
                return False
            device = self._inner_get_dev()
        return True

    def unget_dev(self):
        if not self.linked:
            return
        LOG.debug(_('Release nbd device %s'), self.device)
        utils.execute('qemu-nbd', '-d', self.device, run_as_root=True)
        self.linked = False
        self.device = None
