"""Helper functions."""


# ---------------------------
#   format_attribute
# ---------------------------
def format_attribute(attr):
    res = attr.replace("_", " ")
    res = res.capitalize()
    res = res.replace(" gib", " GiB")
    res = res.replace("Cpu ", "CPU ")
    res = res.replace("Vmware ", "VMware ")
    return res
