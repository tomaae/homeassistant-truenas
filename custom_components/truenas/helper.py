"""Helper functions."""


# ---------------------------
#   format_attribute
# ---------------------------
def format_attribute(attr: str) -> str:
    """Format attribute."""
    res = attr.replace("_", " ")
    res = res.replace("-", " ")
    res = res.capitalize()
    res = res.replace("zfs", "ZFS")
    res = res.replace(" gib", " GiB")
    res = res.replace("Cpu ", "CPU ")
    res = res.replace("Vcpu ", "vCPU ")
    res = res.replace("Vmware ", "VMware ")
    res = res.replace("Ip4 ", "IP4 ")
    res = res.replace("Ip6 ", "IP6 ")
    return res
