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

from nailgun.api.models import Cluster
from nailgun.api.models import IPAddrRange
from nailgun.api.models import NetworkGroup
from nailgun.db import db
from nailgun.network.manager import NetworkManager


class NovaNetworkManager(NetworkManager):

    @classmethod
    def create_network_groups(cls, cluster_id):
        """Method for creation of network groups for cluster.

        :param cluster_id: Cluster database ID.
        :type  cluster_id: int
        :returns: None
        :raises: errors.OutOfVLANs, errors.OutOfIPs,
        errors.NoSuitableCIDR
        """
        cluster_db = db().query(Cluster).get(cluster_id)
        networks_metadata = \
            cluster_db.release.networks_metadata["nova_network"]

        for network in networks_metadata["networks"]:
            new_ip_range = IPAddrRange(
                first=network["ip_range"][0],
                last=network["ip_range"][1]
            )
            gw = network['gateway'] if network.get('use_gateway') else None

            nw_group = NetworkGroup(
                release=cluster_db.release.id,
                name=network['name'],
                cidr=network['cidr'],
                netmask=network['netmask'],
                gateway=gw,
                cluster_id=cluster_id,
                vlan_start=network['vlan_start'],
                amount=1,
                network_size=network['network_size']
                if 'network_size' in network else 256
            )
            db().add(nw_group)
            db().commit()
            nw_group.ip_ranges.append(new_ip_range)
            db().commit()
            cls.create_networks(nw_group)

    @classmethod
    def assign_networks_by_default(cls, node):
        cls.clear_assigned_networks(node)

        for nic in node.interfaces:
            map(nic.assigned_networks.append,
                cls.get_default_nic_networkgroups(node, nic))

        db().commit()

    @classmethod
    def get_default_networks_assignment(cls, node):
        nics = []
        for nic in node.interfaces:
            nic_dict = {
                "id": nic.id,
                "name": nic.name,
                "mac": nic.mac,
                "max_speed": nic.max_speed,
                "current_speed": nic.current_speed
            }

            assigned_ngs = cls.get_default_nic_networkgroups(
                node, nic)

            for ng in assigned_ngs:
                nic_dict.setdefault('assigned_networks', []).append(
                    {'id': ng.id, 'name': ng.name})

            allowed_ngs = cls.get_allowed_nic_networkgroups(
                node,
                nic
            )

            for ng in allowed_ngs:
                nic_dict.setdefault('allowed_networks', []).append(
                    {'id': ng.id, 'name': ng.name})

            nics.append(nic_dict)
        return nics

    @classmethod
    def get_default_nic_networkgroups(cls, node, nic):
        """Assign all network groups except admin to one NIC,
        admin network group has its own NIC by default
        """
        if len(node.interfaces) < 2:
            return (
                [cls.get_admin_network_group()] +
                cls.get_all_cluster_networkgroups(node)
            ) if nic == node.admin_interface else []

        if nic == node.admin_interface:
            return [cls.get_admin_network_group()]
        # return get_all_cluster_networkgroups() for the first non-admin NIC
        # and [] for other NICs
        for n in node.interfaces:
            if n == nic:
                return cls.get_all_cluster_networkgroups(node)
            if n != node.admin_interface:
                return []

    @classmethod
    def allow_network_assignment_to_all_interfaces(cls, node):
        """Method adds all network groups from cluster
        to allowed_networks list for all interfaces
        of specified node.

        :param node: Node object.
        :type  node: Node
        """
        for nic in node.interfaces:

            if nic == node.admin_interface:
                nic.allowed_networks.append(
                    cls.get_admin_network_group()
                )

            for ng in cls.get_cluster_networkgroups_by_node(node):
                nic.allowed_networks.append(ng)

        db().commit()

    @classmethod
    def get_allowed_nic_networkgroups(cls, node, nic):
        """Get all allowed network groups
        """
        ngs = cls.get_all_cluster_networkgroups(node)
        if nic == node.admin_interface:
            ngs.append(cls.get_admin_network_group())
        return ngs
