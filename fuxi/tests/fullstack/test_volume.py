# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from fuxi.tests.fullstack import fuxi_base
from fuxi import utils


class VolumeTest(fuxi_base.FuxiBaseTest):
    """Test Volumes operation

    Test volumes creation/deletion from docker to Cinder
    """
    def test_create_delete_volume_with_fuxi_driver(self):
        """Create and Delete docker volume with Fuxi

           This method creates a docker volume with Fuxi driver
           and tests it was created in Cinder.
           It then deletes the docker volume and tests that it was
           deleted from Cinder.
        """
        driver_opts = {
            'size': '1',
            'fstype': 'ext4',
            'multiattach': 'true',
        }
        vol_name = utils.get_random_string(8)
        self.docker_client.create_volume(name=vol_name, driver='fuxi',
                                         driver_opts=driver_opts)
        # Assure volume was created in Docker
        self._assert_docker_volume_found(vol_name)
        docker_volume = self.docker_client.inspect_volume(vol_name)
        self.assertEqual('fuxi', docker_volume['Driver'])
        self.assertEqual(vol_name, docker_volume['Name'])
        # Assure volume was created in Cinder
        try:
            volumes = self.cinder_client.volumes.list(
                search_opts={'all_tenants': 1, 'name': vol_name})
        except Exception as e:
            self.docker_client.remove_volume(vol_name)
            message = ("Failed to list cinder volumes: %s")
            self.fail(message % str(e))
        self.assertEqual(1, len(volumes))
        self.docker_client.remove_volume(vol_name)
        volumes = self.cinder_client.volumes.list(
            search_opts={'all_tenants': 1, 'name': vol_name})
        self.assertEqual(0, len(volumes))

    def test_create_delete_volume_without_fuxi_driver(self):
        """Create and Delete docker volume without Fuxi

           This method create a docker network with the default
           docker driver, It tests that it was created correctly, but
           not added to Cinder
        """
        vol_name = utils.get_random_string(8)
        self.docker_client.create_volume(name=vol_name)
        # Assure volume was created in Docker
        self._assert_docker_volume_found(vol_name)
        docker_volume = self.docker_client.inspect_volume(vol_name)
        self.assertEqual('local', docker_volume['Driver'])
        self.assertEqual(vol_name, docker_volume['Name'])
        # Assure volume was NOT created in Cinder
        volumes = self.cinder_client.volumes.list(
            search_opts={'all_tenants': 1, 'name': vol_name})
        self.assertEqual(0, len(volumes))
        self.docker_client.remove_volume(vol_name)

    def test_create_from_existing_volume(self):
        """Create docker volume with existing Cinder volume"""
        vol_name = utils.get_random_string(8)
        vol = self._create_cinder_volume(vol_name)
        driver_opts = {
            'volume_id': vol.id,
            'fstype': 'ext4',
            'multiattach': 'true',
        }
        self.docker_client.create_volume(name=vol_name, driver='fuxi',
                                         driver_opts=driver_opts)
        # Assure volume was created in Docker
        self._assert_docker_volume_found(vol_name)
        docker_volume = self.docker_client.inspect_volume(vol_name)
        self.assertEqual('fuxi', docker_volume['Driver'])
        self.assertEqual(vol_name, docker_volume['Name'])
        self.docker_client.remove_volume(vol_name)

    def _create_cinder_volume(self, vol_name):
        # Start to create docker volume from Cinder
        volume = self.cinder_client.volumes.create(name=vol_name, size=1)
        # Waiting volume to be available
        from fuxi.common import state_monitor
        volume_monitor = state_monitor.StateMonitor(
            self.cinder_client,
            volume,
            'available',
            ('creating',),
            time_delay=0.3)
        volume = volume_monitor.monitor_cinder_volume()
        return volume

    def _assert_docker_volume_found(self, vol_name):
        docker_volumes = self.docker_client.volumes()['Volumes']
        volume_found = False
        for docker_vol in docker_volumes or {}:
            if docker_vol['Name'] == vol_name:
                volume_found = True
        self.assertTrue(volume_found)
