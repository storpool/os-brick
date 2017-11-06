# Copyright 2013 OpenStack Foundation.
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
"""Brick Connector objects for each supported transport protocol.

.. module: connector

The connectors here are responsible for discovering and removing volumes for
each of the supported transport protocols.
"""

import platform
import re
import socket
import sys

from oslo_concurrency import lockutils
from oslo_log import log as logging
from oslo_utils import importutils

from os_brick import exception
from os_brick.i18n import _
from os_brick import initiator
from os_brick import utils

LOG = logging.getLogger(__name__)

synchronized = lockutils.synchronized_with_prefix('os-brick-')

# These constants are being deprecated and moving to the init file.
# Please use the constants there instead.

DEVICE_SCAN_ATTEMPTS_DEFAULT = 3
MULTIPATH_ERROR_REGEX = re.compile("\w{3} \d+ \d\d:\d\d:\d\d \|.*$")
MULTIPATH_DEV_CHECK_REGEX = re.compile("\s+dm-\d+\s+")
MULTIPATH_PATH_CHECK_REGEX = re.compile("\s+\d+:\d+:\d+:\d+\s+")

PLATFORM_ALL = 'ALL'
PLATFORM_x86 = 'X86'
PLATFORM_S390 = 'S390'
OS_TYPE_ALL = 'ALL'
OS_TYPE_LINUX = 'LINUX'
OS_TYPE_WINDOWS = 'WIN'

S390X = "s390x"
S390 = "s390"

ISCSI = "ISCSI"
ISER = "ISER"
FIBRE_CHANNEL = "FIBRE_CHANNEL"
AOE = "AOE"
DRBD = "DRBD"
NFS = "NFS"
GLUSTERFS = "GLUSTERFS"
LOCAL = "LOCAL"
GPFS = "GPFS"
HUAWEISDSHYPERVISOR = "HUAWEISDSHYPERVISOR"
HGST = "HGST"
RBD = "RBD"
SCALEIO = "SCALEIO"
SCALITY = "SCALITY"
QUOBYTE = "QUOBYTE"
DISCO = "DISCO"
VZSTORAGE = "VZSTORAGE"
SHEEPDOG = "SHEEPDOG"

# List of connectors to call when getting
# the connector properties for a host
connector_list = [
    'os_brick.initiator.connectors.base.BaseLinuxConnector',
    'os_brick.initiator.connectors.iscsi.ISCSIConnector',
    'os_brick.initiator.connectors.fibre_channel.FibreChannelConnector',
    ('os_brick.initiator.connectors.fibre_channel_s390x.'
     'FibreChannelConnectorS390X'),
    'os_brick.initiator.connectors.aoe.AoEConnector',
    'os_brick.initiator.connectors.remotefs.RemoteFsConnector',
    'os_brick.initiator.connectors.rbd.RBDConnector',
    'os_brick.initiator.connectors.local.LocalConnector',
    'os_brick.initiator.connectors.gpfs.GPFSConnector',
    'os_brick.initiator.connectors.drbd.DRBDConnector',
    'os_brick.initiator.connectors.huawei.HuaweiStorHyperConnector',
    'os_brick.initiator.connectors.hgst.HGSTConnector',
    'os_brick.initiator.connectors.scaleio.ScaleIOConnector',
    'os_brick.initiator.connectors.disco.DISCOConnector',
    'os_brick.initiator.connectors.vmware.VmdkConnector',
    'os_brick.initiator.windows.base.BaseWindowsConnector',
    'os_brick.initiator.windows.iscsi.WindowsISCSIConnector',
    'os_brick.initiator.windows.fibre_channel.WindowsFCConnector',
    'os_brick.initiator.windows.smbfs.WindowsSMBFSConnector',
]

# Mappings used to determine who to contruct in the factory
_connector_mapping_linux = {
    initiator.AOE:
        'os_brick.initiator.connectors.aoe.AoEConnector',
    initiator.DRBD:
        'os_brick.initiator.connectors.drbd.DRBDConnector',

    initiator.GLUSTERFS:
        'os_brick.initiator.connectors.remotefs.RemoteFsConnector',
    initiator.NFS:
        'os_brick.initiator.connectors.remotefs.RemoteFsConnector',
    initiator.SCALITY:
        'os_brick.initiator.connectors.remotefs.RemoteFsConnector',
    initiator.QUOBYTE:
        'os_brick.initiator.connectors.remotefs.RemoteFsConnector',
    initiator.VZSTORAGE:
        'os_brick.initiator.connectors.remotefs.RemoteFsConnector',

    initiator.ISCSI:
        'os_brick.initiator.connectors.iscsi.ISCSIConnector',
    initiator.ISER:
        'os_brick.initiator.connectors.iscsi.ISCSIConnector',
    initiator.FIBRE_CHANNEL:
        'os_brick.initiator.connectors.fibre_channel.FibreChannelConnector',

    initiator.LOCAL:
        'os_brick.initiator.connectors.local.LocalConnector',
    initiator.HUAWEISDSHYPERVISOR:
        'os_brick.initiator.connectors.huawei.HuaweiStorHyperConnector',
    initiator.HGST:
        'os_brick.initiator.connectors.hgst.HGSTConnector',
    initiator.RBD:
        'os_brick.initiator.connectors.rbd.RBDConnector',
    initiator.SCALEIO:
        'os_brick.initiator.connectors.scaleio.ScaleIOConnector',
    initiator.DISCO:
        'os_brick.initiator.connectors.disco.DISCOConnector',
    initiator.SHEEPDOG:
        'os_brick.initiator.connectors.sheepdog.SheepdogConnector',
    initiator.VMDK:
        'os_brick.initiator.connectors.vmware.VmdkConnector',
    initiator.GPFS:
        'os_brick.initiator.connectors.gpfs.GPFSConnector',
    initiator.STORPOOL:
        'os_brick.initiator.connectors.storpool.StorPoolConnector',

}

# Mapping for the S390X platform
_connector_mapping_linux_s390x = {
    initiator.FIBRE_CHANNEL:
        'os_brick.initiator.connectors.fibre_channel_s390x.'
        'FibreChannelConnectorS390X',
    initiator.DRBD:
        'os_brick.initiator.connectors.drbd.DRBDConnector',
    initiator.NFS:
        'os_brick.initiator.connectors.remotefs.RemoteFsConnector',
    initiator.ISCSI:
        'os_brick.initiator.connectors.iscsi.ISCSIConnector',
    initiator.LOCAL:
        'os_brick.initiator.connectors.local.LocalConnector',
    initiator.RBD:
        'os_brick.initiator.connectors.rbd.RBDConnector',
    initiator.GPFS:
        'os_brick.initiator.connectors.gpfs.GPFSConnector',
}

# Mapping for the windows connectors
_connector_mapping_windows = {
    initiator.ISCSI:
        'os_brick.initiator.windows.iscsi.WindowsISCSIConnector',
    initiator.FIBRE_CHANNEL:
        'os_brick.initiator.windows.fibre_channel.WindowsFCConnector',
    initiator.SMBFS:
        'os_brick.initiator.windows.smbfs.WindowsSMBFSConnector',
}


# Create aliases to the old names until 2.0.0
# TODO(smcginnis) Remove this lookup once unit test code is updated to
# point to the correct location
for item in connector_list:
    _name = item.split('.')[-1]
    globals()[_name] = importutils.import_class(item)


@utils.trace
def get_connector_properties(root_helper, my_ip, multipath, enforce_multipath,
                             host=None, execute=None):
    """Get the connection properties for all protocols.

    When the connector wants to use multipath, multipath=True should be
    specified. If enforce_multipath=True is specified too, an exception is
    thrown when multipathd is not running. Otherwise, it falls back to
    multipath=False and only the first path shown up is used.
    For the compatibility reason, even if multipath=False is specified,
    some cinder storage drivers may export the target for multipath, which
    can be found via sendtargets discovery.

    :param root_helper: The command prefix for executing as root.
    :type root_helper: str
    :param my_ip: The IP address of the local host.
    :type my_ip: str
    :param multipath: Enable multipath?
    :type multipath: bool
    :param enforce_multipath: Should we enforce that the multipath daemon is
                              running?  If the daemon isn't running then the
                              return dict will have multipath as False.
    :type enforce_multipath: bool
    :param host: hostname.
    :param execute: execute helper.
    :returns: dict containing all of the collected initiator values.
    """
    props = {}
    props['platform'] = platform.machine()
    props['os_type'] = sys.platform
    props['ip'] = my_ip
    props['host'] = host if host else socket.gethostname()

    for item in connector_list:
        connector = importutils.import_class(item)

        if (utils.platform_matches(props['platform'], connector.platform) and
           utils.os_matches(props['os_type'], connector.os_type)):
            props = utils.merge_dict(props,
                                     connector.get_connector_properties(
                                         root_helper,
                                         host=host,
                                         multipath=multipath,
                                         enforce_multipath=enforce_multipath,
                                         execute=execute))

    return props


# TODO(walter-boring) We have to keep this class defined here
# so we don't break backwards compatibility
class InitiatorConnector(object):

    @staticmethod
    def factory(protocol, root_helper, driver=None,
                use_multipath=False,
                device_scan_attempts=initiator.DEVICE_SCAN_ATTEMPTS_DEFAULT,
                arch=None,
                *args, **kwargs):
        """Build a Connector object based upon protocol and architecture."""

        # We do this instead of assigning it in the definition
        # to help mocking for unit tests
        if arch is None:
            arch = platform.machine()

        # Set the correct mapping for imports
        if sys.platform == 'win32':
            _mapping = _connector_mapping_windows
        elif arch in (initiator.S390, initiator.S390X):
            _mapping = _connector_mapping_linux_s390x
        else:
            _mapping = _connector_mapping_linux

        LOG.debug("Factory for %(protocol)s on %(arch)s",
                  {'protocol': protocol, 'arch': arch})
        protocol = protocol.upper()

        # set any special kwargs needed by connectors
        if protocol in (initiator.NFS, initiator.GLUSTERFS,
                        initiator.SCALITY, initiator.QUOBYTE,
                        initiator.VZSTORAGE):
            kwargs.update({'mount_type': protocol.lower()})
        elif protocol == initiator.ISER:
            kwargs.update({'transport': 'iser'})

        # now set all the default kwargs
        kwargs.update(
            {'root_helper': root_helper,
             'driver': driver,
             'use_multipath': use_multipath,
             'device_scan_attempts': device_scan_attempts,
             })

        connector = _mapping.get(protocol)
        if not connector:
            msg = (_("Invalid InitiatorConnector protocol "
                     "specified %(protocol)s") %
                   dict(protocol=protocol))
            raise exception.InvalidConnectorProtocol(msg)

        conn_cls = importutils.import_class(connector)
        return conn_cls(*args, **kwargs)
