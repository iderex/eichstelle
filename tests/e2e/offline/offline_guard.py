"""Refusing an outbound connection, in whatever process loads this module.

Decision record 0010 makes "no network" a birth requirement of the default
suite rather than a later hardening step. This module is one of the two halves
that turn that sentence into a fact a run can produce: it replaces the socket
calls a Python program reaches the network through, so an attempt raises where
it is made instead of hanging, timing out, or succeeding on a machine that has
a route.

The other half is `sitecustomize.py` beside this file. Together they make the
denial reach a process this run started rather than only the process that
installed it, which matters because the end-to-end tests spend their time in
adapters running as subprocesses and an adapter is exactly the kind of program
that phones home.

## What is denied, and what is not

Denied: connecting an internet socket to anything that is not loopback,
resolving a name that is not loopback, and sending a datagram to an address
that is not loopback. Those are the routes a Python program takes outbound.

Not denied: binding, listening and accepting, because those are not outbound
and the constraint this module implements is the outbound one. A raw socket, a
connection made through `ctypes` against the platform's own sockets library,
and any subprocess that is not a Python interpreter are all outside what this
can see. So this is a floor on what the suite is permitted to reach, not a
sandbox: the workflow's own empty network namespace is the stronger statement
and this is the one that holds on a machine that has no namespaces.

A unix-domain socket is allowed. It reaches no network, and multiprocessing on
POSIX uses one.

An address shape this cannot read is denied rather than allowed. A guard that
passes what it does not understand is a guard that reports green about the
cases it was written for and nothing about the rest.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any, Final

# What a refusal says. The tests match on this string, and so does anybody
# reading a failure who has never heard of this file.
MARKER: Final = "eichstelle offline guard"

# The attribute this module sets on `socket` once it has patched it, so that a
# second install is a no-op rather than a second layer of wrappers around the
# first. Two layers would still deny, and the saved originals would be the
# already-patched functions, which is how an uninstall stops working.
_INSTALLED: Final = "_eichstelle_offline_guard_installed"

# Names that mean this machine and reach no network. Everything else is
# resolved by asking a resolver, which is itself the outbound step this denies.
_LOOPBACK_NAMES: Final = frozenset({"localhost", "ip6-localhost", "ip6-loopback"})

_REAL_CONNECT: Final = socket.socket.connect
_REAL_CONNECT_EX: Final = socket.socket.connect_ex
_REAL_SENDTO: Final = socket.socket.sendto
_REAL_GETADDRINFO: Final = socket.getaddrinfo


class OutboundDenied(OSError):
    """An outbound attempt was refused by this guard rather than by a network.

    An `OSError` rather than a new base, because `socket.create_connection`,
    `http.client` and `urllib` all catch `OSError` and a guard that raised
    outside that family would be reported by them as an internal error instead
    of as a connection that did not happen.
    """


def _is_loopback(host: object) -> bool:
    """Whether this host names this machine without a resolver being asked."""
    if host is None:
        return True
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    if host == "" or host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _denied_address(sock: socket.socket, address: object) -> bool:
    """Whether this address, on this socket, is an outbound one."""
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return False
    if isinstance(address, tuple) and address:
        return not _is_loopback(address[0])
    return True


def _refuse(what: str, where: object) -> OutboundDenied:
    """The one refusal, so every route says the same thing about itself."""
    return OutboundDenied(
        f"{MARKER}: {what} to {where!r} was refused. Decision record 0010 keeps "
        f"the default suite off the network, and this run is being checked "
        f"against that. If this test needs a remote host it does not belong in "
        f"the default suite."
    )


def _connect(self: socket.socket, address: Any) -> None:
    """`socket.connect`, refusing anything that leaves this machine."""
    if _denied_address(self, address):
        raise _refuse("a connection", address)
    _REAL_CONNECT(self, address)


def _connect_ex(self: socket.socket, address: Any) -> int:
    """`socket.connect_ex`, refusing by raising rather than by returning an errno.

    The real call reports failure in its return value, and a caller that
    ignores the return would take a denial for a connection. A guard that can
    be ignored is not one, so this raises where the real call would report.
    """
    if _denied_address(self, address):
        raise _refuse("a connection", address)
    return _REAL_CONNECT_EX(self, address)


def _sendto(self: socket.socket, *arguments: Any) -> int:
    """`socket.sendto`, which reaches an address without connecting to it."""
    if arguments:
        address = arguments[-1]
        if _denied_address(self, address):
            raise _refuse("a datagram", address)
    return int(_REAL_SENDTO(self, *arguments))


def _getaddrinfo(host: Any, port: Any, *arguments: Any, **keywords: Any) -> Any:
    """`socket.getaddrinfo`, which is the outbound step of a name lookup."""
    if not _is_loopback(host):
        raise _refuse("a name lookup", host)
    return _REAL_GETADDRINFO(host, port, *arguments, **keywords)


def install() -> None:
    """Patch the socket module in this interpreter. Idempotent."""
    if getattr(socket, _INSTALLED, False):
        return
    socket.socket.connect = _connect  # type: ignore[assignment]
    socket.socket.connect_ex = _connect_ex  # type: ignore[assignment]
    socket.socket.sendto = _sendto  # type: ignore[assignment]
    socket.getaddrinfo = _getaddrinfo
    socket._eichstelle_offline_guard_installed = True  # type: ignore[attr-defined]


def is_installed() -> bool:
    """Whether this interpreter's socket module is the patched one."""
    return bool(getattr(socket, _INSTALLED, False))
