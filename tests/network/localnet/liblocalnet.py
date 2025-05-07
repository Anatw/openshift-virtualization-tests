import tests.network.libs.nodenetworkconfigurationpolicy as libnncp
from libs.net import netattachdef
from libs.net.traffic_generator import Client, Server
from libs.net.vmspec import IP_ADDRESS, add_network_interface, add_volume_disk, lookup_iface_status
from libs.vm.affinity import new_pod_anti_affinity
from libs.vm.factory import base_vmspec, fedora_vm
from libs.vm.spec import CloudInitNoCloud, Interface, Metadata, Multus, Network
from libs.vm.vm import BaseVirtualMachine, cloudinitdisk_storage
from tests.network.libs import cloudinit

_IPERF_SERVER_PORT = 5201
NNCP_INTERFACE_TYPE_OVS_BRIDGE = "ovs-bridge"


def run_vms(
    vms: tuple[BaseVirtualMachine, BaseVirtualMachine],
) -> tuple[BaseVirtualMachine, BaseVirtualMachine]:
    for vm in vms:
        vm.start()
    for vm in vms:
        vm.wait_for_ready_status(status=True)
        vm.wait_for_agent_connected()
    return vms


def create_traffic_server(vm: BaseVirtualMachine) -> Server:
    return Server(vm=vm, port=_IPERF_SERVER_PORT)


def create_traffic_client(vms: tuple[BaseVirtualMachine, BaseVirtualMachine], network_name: str) -> Client:
    vm_server, vm_client = vms
    return Client(
        vm=vm_client,
        server_ip=lookup_iface_status(vm=vm_server, iface_name=network_name)[IP_ADDRESS],
        server_port=_IPERF_SERVER_PORT,
    )


def additional_ovs_bridge_interface(bridge_name: str, worker_port_name: str) -> libnncp.Interface:
    return libnncp.Interface(
        name=bridge_name,
        type=NNCP_INTERFACE_TYPE_OVS_BRIDGE,
        ipv4=libnncp.IPv4(enabled=False),
        ipv6=libnncp.IPv6(enabled=False),
        state=libnncp.Resource.Interface.State.UP,
        bridge=libnncp.Bridge(
            options=libnncp.BridgeOptions(libnncp.STP(enabled=False)),
            port=[
                libnncp.Port(
                    name=worker_port_name,
                )
            ],
        ),
    )


def localnet_vm(namespace: str, name: str, network: str, cidr: str, network_name: str) -> BaseVirtualMachine:
    """
    Create a Fedora-based Virtual Machine connected to a given localnet network with a static IP configuration.

    The VM will:
    - Attach to a Multus network using a bridge interface.
    - Apply a specific label for anti-affinity scheduling.
    - Use cloud-init to configure a static IP address.
    - Based on a standard Fedora VM template.

    Args:
        namespace (str): The namespace where the VM should be created.
        name (str): The name of the VM.
        network (str): The name of the Multus network to attach.
        cidr (str): The CIDR address to assign to the VM's interface.

    Returns:
        BaseVirtualMachine: The configured VM object ready for creation.
    """
    spec = base_vmspec()
    spec.template.metadata = spec.template.metadata or Metadata()
    spec.template.metadata.labels = spec.template.metadata.labels or {}
    localnet_test_label = {"test": "localnet"}
    spec.template.metadata.labels.update(localnet_test_label)
    vmi_spec = spec.template.spec

    vmi_spec = add_network_interface(
        vmi_spec=vmi_spec,
        network=Network(name=network_name, multus=Multus(networkName=network)),
        interface=Interface(name=network_name, bridge={}),
    )

    netdata = cloudinit.NetworkData(ethernets={"eth0": cloudinit.EthernetDevice(addresses=[cidr])})
    # Prevents cloud-init from overriding the default OS user credentials
    userdata = cloudinit.UserData(users=[])
    disk, volume = cloudinitdisk_storage(
        data=CloudInitNoCloud(
            networkData=cloudinit.asyaml(no_cloud=netdata), userData=cloudinit.format_cloud_config(userdata=userdata)
        )
    )
    vmi_spec = add_volume_disk(vmi_spec=vmi_spec, volume=volume, disk=disk)

    vmi_spec.affinity = new_pod_anti_affinity(label=next(iter(localnet_test_label.items())))
    vmi_spec.affinity.podAntiAffinity.requiredDuringSchedulingIgnoredDuringExecution[0].namespaceSelector = {}

    return fedora_vm(namespace=namespace, name=name, spec=spec)


def localnet_nad(
    namespace: str, name: str, vlan_id: int, network_name: str
) -> netattachdef.NetworkAttachmentDefinition:
    return netattachdef.NetworkAttachmentDefinition(
        namespace=namespace,
        name=name,
        config=netattachdef.NetConfig(
            network_name,
            [
                netattachdef.CNIPluginOvnK8sConfig(
                    topology=netattachdef.CNIPluginOvnK8sConfig.Topology.LOCALNET.value,
                    netAttachDefName=f"{namespace}/{name}",
                    vlanID=vlan_id,
                )
            ],
        ),
    )
