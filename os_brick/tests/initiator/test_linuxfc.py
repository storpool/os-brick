# (c) Copyright 2013 Hewlett-Packard Development Company, L.P.
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

import os.path

import mock

from os_brick.initiator import linuxfc
from os_brick.tests import base


class LinuxFCTestCase(base.TestCase):

    def setUp(self):
        super(LinuxFCTestCase, self).setUp()
        self.cmds = []

        self.mock_object(os.path, 'exists', return_value=True)
        self.mock_object(os.path, 'isdir', return_value=True)
        self.lfc = linuxfc.LinuxFibreChannel(None, execute=self.fake_execute)

    def fake_execute(self, *cmd, **kwargs):
        self.cmds.append(" ".join(cmd))
        return "", None

    def test_has_fc_support(self):

        self.mock_object(os.path, 'isdir', return_value=False)
        has_fc = self.lfc.has_fc_support()
        self.assertFalse(has_fc)

        self.mock_object(os.path, 'isdir', return_value=True)
        has_fc = self.lfc.has_fc_support()
        self.assertTrue(has_fc)

    def test_rescan_hosts(self):
        # We check that we try to get the HBA channel and SCSI target
        execute_results = (
            ('/sys/class/fc_transport/target10:2:3/node_name:'
             '0x5006016090203181\n/sys/class/fc_transport/target10:4:5/'
             'node_name:0x5006016090203181', ''),
            None,
            None,
            ('/sys/class/fc_transport/target11:6:7/node_name:'
             '0x5006016090203181\n/sys/class/fc_transport/target11:8:9/'
             'node_name:0x5006016090203181', ''),
            None,
            None)
        hbas = [{'host_device': 'host10', 'node_name': '5006016090203181'},
                {'host_device': 'host11', 'node_name': '5006016090203181'}]
        with mock.patch.object(self.lfc, '_execute',
                               side_effect=execute_results) as execute_mock:
            self.lfc.rescan_hosts(hbas, 1)
            expected_commands = [
                mock.call('grep 5006016090203181 /sys/class/fc_transport/'
                          'target10:*/node_name'),
                mock.call('tee', '-a', '/sys/class/scsi_host/host10/scan',
                          process_input='2 3 1',
                          root_helper=None, run_as_root=True),
                mock.call('tee', '-a', '/sys/class/scsi_host/host10/scan',
                          process_input='4 5 1',
                          root_helper=None, run_as_root=True),
                mock.call('grep 5006016090203181 /sys/class/fc_transport/'
                          'target11:*/node_name'),
                mock.call('tee', '-a', '/sys/class/scsi_host/host11/scan',
                          process_input='6 7 1',
                          root_helper=None, run_as_root=True),
                mock.call('tee', '-a', '/sys/class/scsi_host/host11/scan',
                          process_input='8 9 1',
                          root_helper=None, run_as_root=True)]

            execute_mock.assert_has_calls(expected_commands)
            self.assertEqual(len(expected_commands), execute_mock.call_count)

    def test_rescan_hosts_wildcard(self):
        hbas = [{'host_device': 'host10', 'node_name': '5006016090203181'},
                {'host_device': 'host11', 'node_name': '5006016090203181'}]
        with mock.patch.object(self.lfc, '_get_hba_channel_scsi_target',
                               return_value=None), \
            mock.patch.object(self.lfc, '_execute',
                              return_value=None) as execute_mock:

            self.lfc.rescan_hosts(hbas, 1)

            expected_commands = [
                mock.call('tee', '-a', '/sys/class/scsi_host/host10/scan',
                          process_input='- - 1',
                          root_helper=None, run_as_root=True),
                mock.call('tee', '-a', '/sys/class/scsi_host/host11/scan',
                          process_input='- - 1',
                          root_helper=None, run_as_root=True)]

            execute_mock.assert_has_calls(expected_commands)
            self.assertEqual(len(expected_commands), execute_mock.call_count)

    def test_rescan_hosts_wildcard_exception(self):
        def _execute(cmd, *args, **kwargs):
            if cmd.startswith('grep'):
                raise Exception

        hbas = [{'host_device': 'host10', 'node_name': '5006016090203181'},
                {'host_device': 'host11', 'node_name': '5006016090203181'}]
        with mock.patch.object(self.lfc, '_execute',
                               side_effect=_execute) as execute_mock:

            self.lfc.rescan_hosts(hbas, 1)

            expected_commands = [
                mock.call('grep 5006016090203181 /sys/class/fc_transport/'
                          'target10:*/node_name'),
                mock.call('tee', '-a', '/sys/class/scsi_host/host10/scan',
                          process_input='- - 1',
                          root_helper=None, run_as_root=True),
                mock.call('grep 5006016090203181 /sys/class/fc_transport/'
                          'target11:*/node_name'),
                mock.call('tee', '-a', '/sys/class/scsi_host/host11/scan',
                          process_input='- - 1',
                          root_helper=None, run_as_root=True)]

            execute_mock.assert_has_calls(expected_commands)
            self.assertEqual(len(expected_commands), execute_mock.call_count)

    def test_get_fc_hbas_fail(self):
        def fake_exec1(a, b, c, d, run_as_root=True, root_helper='sudo'):
            raise OSError

        def fake_exec2(a, b, c, d, run_as_root=True, root_helper='sudo'):
            return None, 'None found'

        self.lfc._execute = fake_exec1
        hbas = self.lfc.get_fc_hbas()
        self.assertEqual(0, len(hbas))
        self.lfc._execute = fake_exec2
        hbas = self.lfc.get_fc_hbas()
        self.assertEqual(0, len(hbas))

    def test_get_fc_hbas(self):
        def fake_exec(a, b, c, d, run_as_root=True, root_helper='sudo'):
            return SYSTOOL_FC, None
        self.lfc._execute = fake_exec
        hbas = self.lfc.get_fc_hbas()
        self.assertEqual(2, len(hbas))
        hba1 = hbas[0]
        self.assertEqual("host0", hba1["ClassDevice"])
        hba2 = hbas[1]
        self.assertEqual("host2", hba2["ClassDevice"])

    def test_get_fc_hbas_info(self):
        def fake_exec(a, b, c, d, run_as_root=True, root_helper='sudo'):
            return SYSTOOL_FC, None
        self.lfc._execute = fake_exec
        hbas_info = self.lfc.get_fc_hbas_info()
        expected_info = [{'device_path': '/sys/devices/pci0000:20/'
                                         '0000:20:03.0/0000:21:00.0/'
                                         'host0/fc_host/host0',
                          'host_device': 'host0',
                          'node_name': '50014380242b9751',
                          'port_name': '50014380242b9750'},
                         {'device_path': '/sys/devices/pci0000:20/'
                                         '0000:20:03.0/0000:21:00.1/'
                                         'host2/fc_host/host2',
                          'host_device': 'host2',
                          'node_name': '50014380242b9753',
                          'port_name': '50014380242b9752'}, ]
        self.assertEqual(expected_info, hbas_info)

    def test_get_fc_wwpns(self):
        def fake_exec(a, b, c, d, run_as_root=True, root_helper='sudo'):
            return SYSTOOL_FC, None

        self.lfc._execute = fake_exec
        wwpns = self.lfc.get_fc_wwpns()
        expected_wwpns = ['50014380242b9750', '50014380242b9752']
        self.assertEqual(expected_wwpns, wwpns)

    def test_get_fc_wwnns(self):
        def fake_exec(a, b, c, d, run_as_root=True, root_helper='sudo'):
            return SYSTOOL_FC, None
        self.lfc._execute = fake_exec
        wwnns = self.lfc.get_fc_wwpns()
        expected_wwnns = ['50014380242b9750', '50014380242b9752']
        self.assertEqual(expected_wwnns, wwnns)

SYSTOOL_FC = """
Class = "fc_host"

  Class Device = "host0"
  Class Device path = "/sys/devices/pci0000:20/0000:20:03.0/\
0000:21:00.0/host0/fc_host/host0"
    dev_loss_tmo        = "16"
    fabric_name         = "0x100000051ea338b9"
    issue_lip           = <store method only>
    max_npiv_vports     = "0"
    node_name           = "0x50014380242b9751"
    npiv_vports_inuse   = "0"
    port_id             = "0x960d0d"
    port_name           = "0x50014380242b9750"
    port_state          = "Online"
    port_type           = "NPort (fabric via point-to-point)"
    speed               = "8 Gbit"
    supported_classes   = "Class 3"
    supported_speeds    = "1 Gbit, 2 Gbit, 4 Gbit, 8 Gbit"
    symbolic_name       = "QMH2572 FW:v4.04.04 DVR:v8.03.07.12-k"
    system_hostname     = ""
    tgtid_bind_type     = "wwpn (World Wide Port Name)"
    uevent              =
    vport_create        = <store method only>
    vport_delete        = <store method only>

    Device = "host0"
    Device path = "/sys/devices/pci0000:20/0000:20:03.0/0000:21:00.0/host0"
      edc                 = <store method only>
      optrom_ctl          = <store method only>
      reset               = <store method only>
      uevent              = "DEVTYPE=scsi_host"


  Class Device = "host2"
  Class Device path = "/sys/devices/pci0000:20/0000:20:03.0/\
0000:21:00.1/host2/fc_host/host2"
    dev_loss_tmo        = "16"
    fabric_name         = "0x100000051ea33b79"
    issue_lip           = <store method only>
    max_npiv_vports     = "0"
    node_name           = "0x50014380242b9753"
    npiv_vports_inuse   = "0"
    port_id             = "0x970e09"
    port_name           = "0x50014380242b9752"
    port_state          = "Online"
    port_type           = "NPort (fabric via point-to-point)"
    speed               = "8 Gbit"
    supported_classes   = "Class 3"
    supported_speeds    = "1 Gbit, 2 Gbit, 4 Gbit, 8 Gbit"
    symbolic_name       = "QMH2572 FW:v4.04.04 DVR:v8.03.07.12-k"
    system_hostname     = ""
    tgtid_bind_type     = "wwpn (World Wide Port Name)"
    uevent              =
    vport_create        = <store method only>
    vport_delete        = <store method only>

    Device = "host2"
    Device path = "/sys/devices/pci0000:20/0000:20:03.0/0000:21:00.1/host2"
      edc                 = <store method only>
      optrom_ctl          = <store method only>
      reset               = <store method only>
      uevent              = "DEVTYPE=scsi_host"


"""


class LinuxFCS390XTestCase(LinuxFCTestCase):

    def setUp(self):
        super(LinuxFCS390XTestCase, self).setUp()
        self.cmds = []
        self.lfc = linuxfc.LinuxFibreChannelS390X(None,
                                                  execute=self.fake_execute)

    def test_get_fc_hbas_info(self):
        def fake_exec(a, b, c, d, run_as_root=True, root_helper='sudo'):
            return SYSTOOL_FC_S390X, None
        self.lfc._execute = fake_exec
        hbas_info = self.lfc.get_fc_hbas_info()
        expected = [{'device_path': '/sys/devices/css0/0.0.02ea/'
                                    '0.0.3080/host0/fc_host/host0',
                     'host_device': 'host0',
                     'node_name': '1234567898765432',
                     'port_name': 'c05076ffe680a960'}]
        self.assertEqual(expected, hbas_info)

    @mock.patch.object(os.path, 'exists', return_value=False)
    def test_configure_scsi_device(self, mock_execute):
        device_number = "0.0.2319"
        target_wwn = "0x50014380242b9751"
        lun = 1
        self.lfc.configure_scsi_device(device_number, target_wwn, lun)
        expected_commands = [('tee -a /sys/bus/ccw/drivers/zfcp/0.0.2319/'
                             'port_rescan'),
                             ('tee -a /sys/bus/ccw/drivers/zfcp/0.0.2319/'
                                 '0x50014380242b9751/unit_add')]
        self.assertEqual(expected_commands, self.cmds)

    def test_deconfigure_scsi_device(self):
        device_number = "0.0.2319"
        target_wwn = "0x50014380242b9751"
        lun = 1
        self.lfc.deconfigure_scsi_device(device_number, target_wwn, lun)
        expected_commands = [('tee -a /sys/bus/ccw/drivers/zfcp/'
                              '0.0.2319/0x50014380242b9751/unit_remove')]
        self.assertEqual(expected_commands, self.cmds)

SYSTOOL_FC_S390X = """
Class = "fc_host"

  Class Device = "host0"
  Class Device path = "/sys/devices/css0/0.0.02ea/0.0.3080/host0/fc_host/host0"
    active_fc4s         = "0x00 0x00 0x01 0x00 0x00 0x00 0x00 0x00 0x00 0x00 \
    0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 \
    0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 "
    dev_loss_tmo        = "60"
    maxframe_size       = "2112 bytes"
    node_name           = "0x1234567898765432"
    permanent_port_name = "0xc05076ffe6803081"
    port_id             = "0x010014"
    port_name           = "0xc05076ffe680a960"
    port_state          = "Online"
    port_type           = "NPIV VPORT"
    serial_number       = "IBM00000000000P30"
    speed               = "8 Gbit"
    supported_classes   = "Class 2, Class 3"
    supported_fc4s      = "0x00 0x00 0x01 0x00 0x00 0x00 0x00 0x00 0x00 0x00 \
    0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 \
    0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 "
    supported_speeds    = "2 Gbit, 4 Gbit"
    symbolic_name       = "IBM     2827            00000000000P30  \
    PCHID: 0308 NPIV UlpId: 01EA0A00   DEVNO: 0.0.1234 NAME: dummy"
    tgtid_bind_type     = "wwpn (World Wide Port Name)"
    uevent              =

    Device = "host0"
    Device path = "/sys/devices/css0/0.0.02ea/0.0.3080/host0"
      uevent              = "DEVTYPE=scsi_host"

"""
