# Copyright 2014 Intel Corporation
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

import datetime

from oslo_log import log as logging
from tempest.common import waiters
from tempest import config
from tempest.lib import decorators

from blazar_tempest_plugin.tests.scenario import (
    resource_reservation_scenario as rrs)

CONF = config.CONF

LOG = logging.getLogger(__name__)

# same as the one at blazar/manager/service
LEASE_DATE_FORMAT = "%Y-%m-%d %H:%M"


class TestInstanceReservationScenario(rrs.ResourceReservationScenarioTest):
    """A scenario test class that checks the instance reservation feature."""

    def setUp(self):
        super(TestInstanceReservationScenario, self).setUp()
        # Setup image and flavor the test instance
        # Support both configured and injected values
        if not hasattr(self, 'image_ref'):
            self.image_ref = CONF.compute.image_ref
        if not hasattr(self, 'flavor_ref'):
            self.flavor_ref = CONF.compute.flavor_ref
        if not self.is_flavor_enough(self.flavor_ref, self.image_ref):
            raise self.skipException(
                '{image} does not fit in {flavor}'.format(
                    image=self.image_ref, flavor=self.flavor_ref
                )
            )
        self.host = self._add_host_once()

    def tearDown(self):
        super(TestInstanceReservationScenario, self).tearDown()

    def get_lease_body(self, lease_name):
        current_time = datetime.datetime.utcnow()
        end_time = current_time + datetime.timedelta(hours=1)
        body = {
            "start_date": "now",
            "end_date": end_time.strftime(LEASE_DATE_FORMAT),
            "name": lease_name,
            "events": [],
            }
        body["reservations"] = [
            {
                "resource_type": 'virtual:instance',
                'vcpus': 1,
                'memory_mb': 1024,
                'disk_gb': 10,
                'amount': 1,
                'affinity': False,
                'resource_properties': '',
                }
            ]
        return body

    def get_lease_expiration_body(self, lease_name):
        current_time = datetime.datetime.utcnow()
        end_time = current_time + datetime.timedelta(seconds=90)
        body = {
            "start_date": "now",
            "end_date": end_time.strftime(LEASE_DATE_FORMAT),
            "name": lease_name,
            "events": [],
            }
        body["reservations"] = [
            {
                "resource_type": 'virtual:instance',
                'vcpus': 1,
                'memory_mb': 1024,
                'disk_gb': 10,
                'amount': 1,
                'affinity': False,
                'resource_properties': '',
                }
            ]
        return body

    @decorators.attr(type='smoke')
    def test_instance_reservation(self):
        body = self.get_lease_body('instance-scenario')
        lease = self.reservation_client.create_lease(body)['lease']
        reservation = next(iter(lease['reservations']))

        self.wait_for_lease_status(lease['id'], 'ACTIVE')

        # create an instance within the reservation
        create_kwargs = {
            'image_id': CONF.compute.image_ref,
            'flavor': reservation['id'],
            'scheduler_hints': {
                'group': reservation['server_group_id']
                },
            }
        server1 = self.create_server(clients=self.os_admin,
                                     **create_kwargs)

        # create another instance within the reservation, which is expected to
        # fail because we are over the reserved capacity
        create_kwargs = {
            'image_id': CONF.compute.image_ref,
            'flavor': reservation['id'],
            'scheduler_hints': {
                'group': reservation['server_group_id']
                },
            }
        server2 = self.create_server(clients=self.os_admin,
                                     wait_until=None,
                                     **create_kwargs)
        waiters.wait_for_server_status(self.os_admin.servers_client,
                                       server2['id'], 'ERROR',
                                       raise_on_error=False)

        # create an instance without specifying a reservation, which is
        # expected to fail
        create_kwargs = {
            'image_id': CONF.compute.image_ref,
            'flavor': CONF.compute.flavor_ref,
            }
        server3 = self.create_server(clients=self.os_admin,
                                     wait_until=None,
                                     **create_kwargs)
        waiters.wait_for_server_status(self.os_admin.servers_client,
                                       server3['id'], 'ERROR',
                                       raise_on_error=False)

        # delete the lease, which should trigger termination of the instance
        self.reservation_client.delete_lease(lease['id'])
        waiters.wait_for_server_termination(self.os_admin.servers_client,
                                            server1['id'])

    @decorators.attr(type='smoke')
    def test_lease_expiration(self):
        body = self.get_lease_expiration_body('instance-scenario-expiration')
        lease = self.reservation_client.create_lease(body)['lease']
        reservation = next(iter(lease['reservations']))

        self.wait_for_lease_status(lease['id'], 'ACTIVE')

        create_kwargs = {
            'image_id': CONF.compute.image_ref,
            'flavor': reservation['id'],
            'scheduler_hints': {
                'group': reservation['server_group_id']
                },
            }
        server1 = self.create_server(clients=self.os_admin,
                                     **create_kwargs)

        # wait for lease end
        self.wait_for_lease_end(lease['id'])

        waiters.wait_for_server_termination(self.os_admin.servers_client,
                                            server1['id'])

        # check the lease status and reservation status
        lease = self.reservation_client.get_lease(lease['id'])['lease']
        self.assertTrue(lease['status'] == 'TERMINATED')
        self.assertTrue('deleted' in
                        next(iter(lease['reservations']))['status'])

    @decorators.attr(type='smoke')
    def test_update_instance_reservation(self):
        body = self.get_lease_body('instance-scenario-update')
        lease = self.reservation_client.create_lease(body)['lease']
        reservation = next(iter(lease['reservations']))

        self.wait_for_lease_status(lease['id'], 'ACTIVE')

        create_kwargs = {
            'image_id': CONF.compute.image_ref,
            'flavor': reservation['id'],
            'scheduler_hints': {
                'group': reservation['server_group_id']
                },
            }
        server = self.create_server(clients=self.os_admin,
                                    **create_kwargs)

        # Updating the lease end_date to 1 minute from now to avoid a failure
        # of the lease update request
        now = datetime.datetime.utcnow()
        end_time = now + datetime.timedelta(minutes=1)
        body = {
            'end_date': end_time.strftime(LEASE_DATE_FORMAT)
            }
        self.reservation_client.update_lease(lease['id'], body)

        waiters.wait_for_server_termination(self.os_admin.servers_client,
                                            server['id'])

        # There is a lag between the server termination and the lease status
        # transition. Let's wait a bit here.
        self.wait_for_lease_end(lease['id'])

        # check the lease status and reservation status
        lease = self.reservation_client.get_lease(lease['id'])['lease']
        self.assertTrue(lease['status'] == 'TERMINATED')
        self.assertTrue('deleted' in
                        next(iter(lease['reservations']))['status'])
