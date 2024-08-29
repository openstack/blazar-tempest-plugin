# Copyright 2024 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime

import testtools

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


class TestFlavorReservationScenario(rrs.ResourceReservationScenarioTest):
    """A scenario that checks the flavor-based instance reservation feature."""

    def setUp(self):
        super(TestFlavorReservationScenario, self).setUp()
        # Setup image and flavor for the test instance
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
        super(TestFlavorReservationScenario, self).tearDown()

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
                "resource_type": 'flavor:instance',
                'flavor_id': self.flavor_ref,
                'amount': 1,
                'affinity': None,
                'resource_properties': '',
                }
            ]
        return body

    @decorators.attr(type='smoke')
    @testtools.skipUnless(
        CONF.resource_reservation.flavor_instance_plugin,
        'Flavor-based instance reservation tests are disabled.')
    def test_flavor_instance_reservation(self):
        body = self.get_lease_body('flavor-instance-scenario')
        lease = self.reservation_client.create_lease(body)['lease']
        reservation = next(iter(lease['reservations']))

        self.wait_for_lease_status(lease['id'], 'ACTIVE')

        # create an instance within the reservation
        create_kwargs = {
            'image_id': CONF.compute.image_ref,
            'flavor': reservation['id'],
            }
        server1 = self.create_server(clients=self.os_admin,
                                     **create_kwargs)

        # create another instance within the reservation, which is expected to
        # fail because we are over the reserved capacity
        create_kwargs = {
            'image_id': CONF.compute.image_ref,
            'flavor': reservation['id'],
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
