"""Helper functions."""


# ---------------------------
#   format_attribute
# ---------------------------
def format_attribute(attr: str) -> str:
    """Format attribute."""
    attr = attr.replace("_", " ")
    attr = attr.replace("-", " ")
    attr = attr.capitalize()
    attr = attr.replace("zfs", "ZFS")
    attr = attr.replace(" gib", " GiB")
    attr = attr.replace("Cpu ", "CPU ")
    attr = attr.replace("Vcpu ", "vCPU ")
    attr = attr.replace("Vmware ", "VMware ")
    attr = attr.replace("Ip4 ", "IP4 ")
    attr = attr.replace("Ip6 ", "IP6 ")
    return attr
