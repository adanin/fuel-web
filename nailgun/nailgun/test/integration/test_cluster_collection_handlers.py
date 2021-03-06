# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import json

from mock import patch
from sqlalchemy.sql import not_

from nailgun.api.models import Cluster
from nailgun.api.models import Network
from nailgun.api.models import NetworkConfiguration
from nailgun.api.models import NetworkGroup
from nailgun.api.models import Release
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):

    def _get_cluster_networks(self, cluster_id):
        nets = json.loads(self.app.get(
            reverse('NovaNetworkConfigurationHandler',
                    {"cluster_id": cluster_id}),
            headers=self.default_headers,
        ).body)["networks"]
        return nets

    def test_cluster_list_empty(self):
        resp = self.app.get(
            reverse('ClusterCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status)
        response = json.loads(resp.body)
        self.assertEquals([], response)

    def test_cluster_create(self):
        release_id = self.env.create_release(api=False).id
        resp = self.app.post(
            reverse('ClusterCollectionHandler'),
            json.dumps({
                'name': 'cluster-name',
                'release': release_id,
            }),
            headers=self.default_headers
        )
        self.assertEquals(201, resp.status)

    def test_cluster_create_no_ip_addresses(self):
        """In this test we check that no error is occured
        if two clusters will have same networks updated to use
        full CIDR
        """
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.db.query(Cluster).get(cluster["id"])
        cluster2 = self.env.create_cluster(api=True,
                                           release=cluster_db.release.id)
        cluster2_db = self.db.query(Cluster).get(cluster2["id"])

        for clstr in (cluster_db, cluster2_db):
            management_net = self.db.query(NetworkGroup).filter_by(
                name="management",
                cluster_id=clstr.id
            ).first()
            NetworkConfiguration.update(
                clstr,
                {
                    "networks": [
                        {
                            "network_size": 65536,
                            "name": "management",
                            "ip_ranges": [
                                ["192.168.0.2", "192.168.255.254"]
                            ],
                            "amount": 1,
                            "id": management_net.id,
                            "netmask": "255.255.255.0",
                            "cluster_id": clstr.id,
                            "vlan_start": 101,
                            "cidr": "192.168.0.0/16",
                            "gateway": "192.168.0.1"
                        }
                    ]
                }
            )

        cluster1_nets = self._get_cluster_networks(cluster["id"])
        cluster2_nets = self._get_cluster_networks(cluster2["id"])

        for net1, net2 in zip(cluster1_nets, cluster2_nets):
            for f in ('cluster_id', 'id'):
                del net1[f]
                del net2[f]

        self.assertEquals(cluster1_nets, cluster2_nets)

    def test_cluster_creation_same_networks(self):
        cluster1_id = self.env.create_cluster(api=True)["id"]
        cluster2_id = self.env.create_cluster(api=True)["id"]
        cluster1_nets = self._get_cluster_networks(cluster1_id)
        cluster2_nets = self._get_cluster_networks(cluster2_id)

        for net1, net2 in zip(cluster1_nets, cluster2_nets):
            for f in ('cluster_id', 'id'):
                del net1[f]
                del net2[f]

        cluster1_nets = sorted(cluster1_nets, key=lambda n: n['vlan_start'])
        cluster2_nets = sorted(cluster2_nets, key=lambda n: n['vlan_start'])

        self.assertEquals(cluster1_nets, cluster2_nets)

    def test_if_cluster_creates_correct_networks(self):
        release = Release()
        release.version = "1.1.1"
        release.name = u"release_name_" + str(release.version)
        release.description = u"release_desc" + str(release.version)
        release.operating_system = "CentOS"
        release.networks_metadata = self.env.get_default_networks_metadata()
        release.attributes_metadata = {
            "editable": {
                "keystone": {
                    "admin_tenant": "admin"
                }
            },
            "generated": {
                "mysql": {
                    "root_password": ""
                }
            }
        }
        self.db.add(release)
        self.db.commit()
        resp = self.app.post(
            reverse('ClusterCollectionHandler'),
            json.dumps({
                'name': 'cluster-name',
                'release': release.id,
            }),
            headers=self.default_headers
        )
        self.assertEquals(201, resp.status)
        nets = self.db.query(Network).filter(
            not_(Network.name == "fuelweb_admin")
        ).all()
        obtained = []
        for net in nets:
            obtained.append({
                'release': net.release,
                'name': net.name,
                'vlan_id': net.vlan_id,
                'cidr': net.cidr,
                'gateway': net.gateway
            })
        expected = [
            {
                'release': release.id,
                'name': u'floating',
                'vlan_id': None,
                'cidr': '172.16.0.0/24',
                'gateway': None
            },
            {
                'release': release.id,
                'name': u'public',
                'vlan_id': None,
                'cidr': '172.16.0.0/24',
                'gateway': '172.16.0.1'
            },
            {
                'release': release.id,
                'name': u'fixed',
                'vlan_id': 103,
                'cidr': '10.0.0.0/24',
                'gateway': '10.0.0.1'
            },
            {
                'release': release.id,
                'name': u'storage',
                'vlan_id': 102,
                'cidr': '192.168.1.0/24',
                'gateway': None
            },
            {
                'release': release.id,
                'name': u'management',
                'vlan_id': 101,
                'cidr': '192.168.0.0/24',
                'gateway': None
            }
        ]
        self.assertItemsEqual(expected, obtained)

    @patch('nailgun.rpc.cast')
    def test_verify_networks(self, mocked_rpc):
        cluster = self.env.create_cluster(api=True)
        nets = json.loads(self.env.nova_networks_get(cluster['id']).body)

        resp = self.env.nova_networks_put(cluster['id'], nets)
        self.assertEquals(202, resp.status)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')
