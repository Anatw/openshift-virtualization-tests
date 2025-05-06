import pytest

from libs.net.traffic_generator import is_tcp_connection
from utilities.virt import migrate_vm_and_verify


@pytest.mark.ipv4
@pytest.mark.single_nic
@pytest.mark.usefixtures("nncp_localnet")
@pytest.mark.polarion("CNV-11775")
def test_connectivity_over_migration_between_localnet_vms(localnet_server, localnet_client):
    migrate_vm_and_verify(vm=localnet_client.vm)
    assert is_tcp_connection(server=localnet_server, client=localnet_client)
class TestLocalnetDefaultBridge:
    @pytest.mark.ipv4
    @pytest.mark.single_nic
    @pytest.mark.polarion("CNV-11775")
    def test_connectivity_over_migration_between_localnet_vms(self, nncp_localnet, localnet_server, localnet_client):
        migrate_vm_and_verify(vm=localnet_client.vm)
        assert is_tcp_connection(server=localnet_server, client=localnet_client)


class TestLocalnetAdditionalBridge:
    @pytest.mark.ipv4
    @pytest.mark.usefixtures("nncp_localnet_on_secondary_node_nic")
    @pytest.mark.polarion("CNV-11905")
    def test_connectivity_over_migration_between_localnet_vms(
        self, localnet_additional_ovs_bridge_server, localnet_additional_ovs_bridge_client
    ):
        migrate_vm_and_verify(vm=localnet_additional_ovs_bridge_client.vm)
        assert is_tcp_connection(
            server=localnet_additional_ovs_bridge_server, client=localnet_additional_ovs_bridge_client
        )
