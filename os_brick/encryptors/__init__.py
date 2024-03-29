# Copyright (c) 2013 The Johns Hopkins University/Applied Physics Laboratory
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


from oslo_log import log as logging
from oslo_utils import importutils
from oslo_utils import strutils

from os_brick.encryptors import nop

LOG = logging.getLogger(__name__)

LUKS = "luks"
LUKS2 = "luks2"
PLAIN = "plain"

FORMAT_TO_FRONTEND_ENCRYPTOR_MAP = {
    LUKS: 'os_brick.encryptors.luks.LuksEncryptor',
    LUKS2: 'os_brick.encryptors.luks.Luks2Encryptor',
    PLAIN: 'os_brick.encryptors.cryptsetup.CryptsetupEncryptor'
}

LEGACY_PROVIDER_CLASS_TO_FORMAT_MAP = {
    "nova.volume.encryptors.luks.LuksEncryptor": LUKS,
    "nova.volume.encryptors.cryptsetup.CryptsetupEncryptor": PLAIN,
    "nova.volume.encryptors.nop.NoopEncryptor": None,
    "os_brick.encryptors.luks.LuksEncryptor": LUKS,
    "os_brick.encryptors.cryptsetup.CryptsetupEncryptor": PLAIN,
    "os_brick.encryptors.nop.NoopEncryptor": None,
    "LuksEncryptor": LUKS,
    "CryptsetupEncryptor": PLAIN,
    "NoOpEncryptor": None,
}


def get_volume_encryptor(root_helper,
                         connection_info,
                         keymgr,
                         execute=None,
                         *args, **kwargs):
    """Creates a VolumeEncryptor used to encrypt the specified volume.

    :param: the connection information used to attach the volume
    :returns VolumeEncryptor: the VolumeEncryptor for the volume
    """
    encryptor = nop.NoOpEncryptor(root_helper=root_helper,
                                  connection_info=connection_info,
                                  keymgr=keymgr,
                                  execute=execute,
                                  *args, **kwargs)

    location = kwargs.get('control_location', None)
    if location and location.lower() == 'front-end':  # case insensitive
        provider = kwargs.get('provider')

        # TODO(lyarwood): Remove the following in Queens and raise an
        # ERROR if provider is not a key in SUPPORTED_ENCRYPTION_PROVIDERS.
        # Until then continue to allow both the class name and path to be used.
        if provider in LEGACY_PROVIDER_CLASS_TO_FORMAT_MAP:
            LOG.warning("Use of the in tree encryptor class %(provider)s"
                        " by directly referencing the implementation class"
                        " will be blocked in the Queens release of"
                        " os-brick.", {'provider': provider})
            provider = LEGACY_PROVIDER_CLASS_TO_FORMAT_MAP[provider]

        if provider in FORMAT_TO_FRONTEND_ENCRYPTOR_MAP:
            provider = FORMAT_TO_FRONTEND_ENCRYPTOR_MAP[provider]
        elif provider is None:
            provider = "os_brick.encryptors.nop.NoOpEncryptor"
        else:
            LOG.warning("Use of the out of tree encryptor class "
                        "%(provider)s will be blocked with the Queens "
                        "release of os-brick.", {'provider': provider})

        try:
            encryptor = importutils.import_object(
                provider,
                root_helper,
                connection_info,
                keymgr,
                execute,
                **kwargs)
        except Exception as e:
            LOG.error("Error instantiating %(provider)s: %(exception)s",
                      {'provider': provider, 'exception': e})
            raise

    msg = ("Using volume encryptor '%(encryptor)s' for connection: "
           "%(connection_info)s" %
           {'encryptor': encryptor, 'connection_info': connection_info})
    LOG.debug(strutils.mask_password(msg))

    return encryptor


def get_encryption_metadata(context, volume_api, volume_id, connection_info):
    metadata = {}
    if ('data' in connection_info and
            connection_info['data'].get('encrypted', False)):
        try:
            metadata = volume_api.get_volume_encryption_metadata(context,
                                                                 volume_id)
            if not metadata:
                LOG.warning('Volume %s should be encrypted but there is no '
                            'encryption metadata.', volume_id)
        except Exception as e:
            LOG.error("Failed to retrieve encryption metadata for "
                      "volume %(volume_id)s: %(exception)s",
                      {'volume_id': volume_id, 'exception': e})
            raise

    if metadata:
        msg = ("Using volume encryption metadata '%(metadata)s' for "
               "connection: %(connection_info)s" %
               {'metadata': metadata, 'connection_info': connection_info})
        LOG.debug(strutils.mask_password(msg))

    return metadata
