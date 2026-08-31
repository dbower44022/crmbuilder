"""SSH key material for a deploy run — PI-419.

Each run gets its own ed25519 keypair: the public half is registered on the
DigitalOcean account and baked into the droplet, the private half is stored as
a secret ref and used for the run's SSH phases. The v1 ``connect_ssh`` takes a
key *path*, so :func:`private_key_file` materializes the stored key into a
0600 temporary file for the duration of an SSH session only.
"""

from __future__ import annotations

import base64
import hashlib
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def generate_keypair(comment: str = "crmbuilder") -> tuple[str, str]:
    """Return ``(private_openssh_pem, public_authorized_line)`` for a new key."""
    private = ed25519.Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_line = private.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode()
    return private_pem, f"{public_line} {comment}"


def public_key_fingerprint(public_line: str) -> str:
    """OpenSSH-style ``SHA256:`` fingerprint of an ``authorized_keys`` line.

    PI-442 (REQ-544): recorded on the instance's deploy config so an admin or
    agent can match the stored key against the provider console or a server's
    ``authorized_keys`` without touching the private half.
    """
    blob = base64.b64decode(public_line.split()[1])
    return "SHA256:" + base64.b64encode(
        hashlib.sha256(blob).digest()
    ).decode().rstrip("=")


@contextmanager
def private_key_file(private_pem: str) -> Iterator[str]:
    """Write ``private_pem`` to a 0600 temp file and yield its path; then remove it."""
    fd, path = tempfile.mkstemp(prefix="crmbuilder-deploy-", suffix=".key")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(private_pem)
        os.chmod(path, 0o600)
        yield path
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
