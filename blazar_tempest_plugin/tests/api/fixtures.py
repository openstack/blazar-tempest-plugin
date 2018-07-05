#
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

import os

from gabbi import fixture
from tempest import clients as tempestclients
from tempest import test


class AuthenticationFixture(fixture.GabbiFixture, test.BaseTestCase):
    def start_fixture(self):
        cred_provider = self._get_credentials_provider()
        creds = cred_provider.get_credentials('admin')
        auth_prov = tempestclients.get_auth_provider(creds._credentials)

        os.environ['OS_TOKEN'] = auth_prov.get_token()

    def stop_fixture(self):
        pass
