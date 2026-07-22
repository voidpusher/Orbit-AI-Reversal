import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, status


def normalize_public_url(raw_url: str, allowed_hosts: tuple[str, ...] = ()) -> str:
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Only absolute HTTP(S) URLs are supported")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".local"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Local network targets are not allowed")
    if allowed_hosts and hostname not in allowed_hosts:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This target is outside the configured allowlist")
    try:
        candidate = ipaddress.ip_address(hostname)
        if not candidate.is_global:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Non-public targets are not allowed")
    except ValueError:
        pass
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path or "/", parsed.query, ""))


async def assert_public_resolution(url: str) -> None:
    hostname = urlsplit(url).hostname
    if hostname is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid target hostname")
    try:
        results = await asyncio.get_running_loop().run_in_executor(
            None, lambda: socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        )
    except socket.gaierror as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Target hostname cannot be resolved") from error
    for result in results:
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Target resolves to a non-public address")
