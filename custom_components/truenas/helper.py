"""Helper functions"""
from pytz import utc
from datetime import datetime

DEFAULT_TIME_ZONE = None


# ---------------------------
#   format_attribute
# ---------------------------
def format_attribute(attr):
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


# ---------------------------
#   as_local
# ---------------------------
def as_local(dattim: datetime) -> datetime:
    """Convert a UTC datetime object to local time zone"""
    if dattim.tzinfo == DEFAULT_TIME_ZONE:
        return dattim
    if dattim.tzinfo is None:
        dattim = utc.localize(dattim)

    return dattim.astimezone(DEFAULT_TIME_ZONE)


# ---------------------------
#   b2gib
# ---------------------------
def b2gib(b: int) -> float:
    return round(b / 1073741824, 2)
