import urllib3.util

common_subdomains = {"www", "blog", "library", "note", "notes"}


def cross_domain(url1: urllib3.util.Url, url2: urllib3.util.Url):
    if url1 is None or url2 is None:
        return False
    if url1.host is None or url2.host is None:
        return False
    strip1 = strip_host(url1.host)
    strip2 = strip_host(url2.host)
    return strip1 != strip2


def strip_host(host: str | None) -> str:
    if host is None:
        return ""
    if (index := host.find("://")) != -1:
        host = host[index + 3 :]
    if (index := host.find("/")) != -1:
        host = host[:index]
    host = host.strip()
    for subdomain in common_subdomains:
        host = host.removeprefix(subdomain + ".").strip()
    return host


def host_or_sub_in_list(host: str, hosts: set[str]) -> bool:
    if host in hosts:
        return True
    dot_index = host.find(".")
    while dot_index != -1:
        host = host[dot_index + 1 :]
        if host in hosts:
            return True
        dot_index = host.find(".")
    return False
