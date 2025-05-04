from collections.abc import Generator

import pytest
from ocp_resources.namespace import Namespace
from ocp_resources.node import Node

import tests.network.libs.nodenetworkconfigurationpolicy as libnncp
from libs.net import netattachdef
from libs.net.traffic_generator import Client, Server
from libs.vm.vm import BaseVirtualMachine
from tests.network.localnet.liblocalnet import (
    NETWORK_NAME,
    additional_ovs_bridge_interface,
    localnet_nad,
    localnet_vm,
    start_client_vm,
    start_server_vm,
)
from utilities.constants import (
    WORKER_NODE_LABEL_KEY,
)
from utilities.infra import create_ns

IP_NETWORK_PREFIX = "10.0.0"


@pytest.fixture(scope="module")
def vlan_id(vlan_index_number: Generator[int]) -> int:
    return next(vlan_index_number)


@pytest.fixture(scope="class")
def nncp_localnet() -> Generator[libnncp.NodeNetworkConfigurationPolicy]:
    desired_state = libnncp.DesiredState(
        ovn=libnncp.OVN([
            libnncp.BridgeMappings(
                localnet=NETWORK_NAME,
                bridge=libnncp.DEFAULT_OVN_EXTERNAL_BRIDGE,
                state=libnncp.BridgeMappings.State.PRESENT.value,
            )
        ])
    )

    with libnncp.NodeNetworkConfigurationPolicy(
        name="test-localnet-nncp",
        desired_state=desired_state,
        node_selector={WORKER_NODE_LABEL_KEY: ""},
    ) as nncp:
        nncp.wait_for_status_success()
        yield nncp


@pytest.fixture(scope="class")
def namespace_localnet_1() -> Generator[Namespace]:
    yield from create_ns(name="test-localnet-ns1")  # type: ignore


@pytest.fixture(scope="class")
def namespace_localnet_2() -> Generator[Namespace]:
    yield from create_ns(name="test-localnet-ns2")  # type: ignore


@pytest.fixture(scope="class")
def nad_localnet_1(
    nncp_localnet: Generator[libnncp.NodeNetworkConfigurationPolicy], namespace_localnet_1: Namespace, vlan_id: int
) -> Generator[netattachdef.NetworkAttachmentDefinition]:
    with localnet_nad(namespace=namespace_localnet_1.name, name="test-localnet-nad1", vlan_id=vlan_id) as nad:
        yield nad


@pytest.fixture(scope="class")
def nad_localnet_2(
    nncp_localnet: Generator[libnncp.NodeNetworkConfigurationPolicy], namespace_localnet_2: Namespace, vlan_id: int
) -> Generator[netattachdef.NetworkAttachmentDefinition]:
    with localnet_nad(namespace=namespace_localnet_2.name, name="test-localnet-nad2", vlan_id=vlan_id) as nad:
        yield nad


@pytest.fixture(scope="class")
def vm_localnet_1(nad_localnet_1: netattachdef.NetworkAttachmentDefinition) -> Generator[BaseVirtualMachine]:
    with localnet_vm(
        namespace=nad_localnet_1.namespace,
        name="test-vm1",
        network=nad_localnet_1.name,
        cidr=f"{IP_NETWORK_PREFIX}.1/24",
    ) as vm:
        yield vm


@pytest.fixture(scope="class")
def vm_localnet_2(nad_localnet_2: netattachdef.NetworkAttachmentDefinition) -> Generator[BaseVirtualMachine]:
    with localnet_vm(
        namespace=nad_localnet_2.namespace,
        name="test-vm2",
        network=nad_localnet_2.name,
        cidr=f"{IP_NETWORK_PREFIX}.2/24",
    ) as vm:
        yield vm


@pytest.fixture(scope="class")
def vms_localnet(
    vm_localnet_1: BaseVirtualMachine, vm_localnet_2: BaseVirtualMachine
) -> Generator[tuple[BaseVirtualMachine, BaseVirtualMachine]]:
    vms = (vm_localnet_1, vm_localnet_2)
    for vm in vms:
        vm.start()
    for vm in vms:
        vm.wait_for_ready_status(status=True)
        vm.vmi.wait_for_condition(condition=vm.Condition.Type.AGENT_CONNECTED, status=vm.Condition.Status.TRUE)
    yield vms


@pytest.fixture()
def localnet_server(vms_localnet: tuple[BaseVirtualMachine, BaseVirtualMachine]) -> Generator[Server]:
    vm1, _ = vms_localnet
    with start_server_vm(vm=vm1) as server:
        yield server


@pytest.fixture()
def localnet_client(vms_localnet: tuple[BaseVirtualMachine, BaseVirtualMachine]) -> Generator[Client]:
    with start_client_vm(vms=vms_localnet) as client:
        yield client


@pytest.fixture(scope="class")
def nncp_localnet_additional_ovs_bridge(
    worker_node1: Node, nodes_available_nics: dict[str, list[str]]
) -> Generator[libnncp.NodeNetworkConfigurationPolicy]:
    bridge_name = "localnet-additional-ovs-bridge"
    desired_state = libnncp.DesiredState(
        interfaces=[
            additional_ovs_bridge_interface(
                bridge_name=bridge_name, worker_port_name=nodes_available_nics[worker_node1.name][-1]
            )
        ],
        ovn=libnncp.OVN([
            libnncp.BridgeMappings(
                localnet=NETWORK_NAME,
                bridge=bridge_name,
                state=libnncp.BridgeMappings.State.PRESENT.value,
            )
        ]),
    )
    with libnncp.NodeNetworkConfigurationPolicy(
        name=bridge_name,
        desired_state=desired_state,
        node_selector={WORKER_NODE_LABEL_KEY: ""},
    ) as nncp:
        nncp.wait_for_status_success()
        yield nncp


@pytest.fixture(scope="class")
def nad_localnet_additional_ovs_bridge(
    namespace: Namespace,
    nncp_localnet_additional_ovs_bridge: Generator[libnncp.NodeNetworkConfigurationPolicy],
    vlan_id: int,
) -> Generator[netattachdef.NetworkAttachmentDefinition]:
    with localnet_nad(namespace=namespace.name, name=f"{NETWORK_NAME}-nad", vlan_id=vlan_id) as nad:
        yield nad


@pytest.fixture(scope="class")
def additional_ovs_bridge_localnet_vma(
    nad_localnet_additional_ovs_bridge: netattachdef.NetworkAttachmentDefinition,
) -> Generator[BaseVirtualMachine]:
    with localnet_vm(
        namespace=nad_localnet_additional_ovs_bridge.namespace,
        name="localnet-vma",
        network=nad_localnet_additional_ovs_bridge.name,
        cidr=f"{IP_NETWORK_PREFIX}.1/24",
    ) as vma:
        yield vma


@pytest.fixture(scope="class")
def additional_ovs_bridge_localnet_vmb(
    nad_localnet_additional_ovs_bridge: netattachdef.NetworkAttachmentDefinition,
) -> Generator[BaseVirtualMachine]:
    with localnet_vm(
        namespace=nad_localnet_additional_ovs_bridge.namespace,
        name="localnet-vmb",
        network=nad_localnet_additional_ovs_bridge.name,
        cidr=f"{IP_NETWORK_PREFIX}.2/24",
    ) as vmb:
        yield vmb


@pytest.fixture(scope="class")
def additional_ovs_bridge_localnet_vms(
    additional_ovs_bridge_localnet_vma: BaseVirtualMachine, additional_ovs_bridge_localnet_vmb: BaseVirtualMachine
) -> Generator[tuple[BaseVirtualMachine, BaseVirtualMachine]]:
    vms = (additional_ovs_bridge_localnet_vma, additional_ovs_bridge_localnet_vmb)
    for vm in vms:
        vm.start()
    for vm in vms:
        vm.wait_for_ready_status(status=True)
        vm.vmi.wait_for_condition(condition=vm.Condition.Type.AGENT_CONNECTED, status=vm.Condition.Status.TRUE)
    yield vms


@pytest.fixture()
def localnet_additional_ovs_bridge_server(
    additional_ovs_bridge_localnet_vms: tuple[BaseVirtualMachine, BaseVirtualMachine],
) -> Generator[Server]:
    vma, _ = additional_ovs_bridge_localnet_vms
    with start_server_vm(vm=vma) as server:
        yield server


@pytest.fixture()
def localnet_additional_ovs_bridge_client(
    additional_ovs_bridge_localnet_vms: tuple[BaseVirtualMachine, BaseVirtualMachine],
) -> Generator[Client]:
    with start_client_vm(vms=additional_ovs_bridge_localnet_vms) as client:
        yield client
