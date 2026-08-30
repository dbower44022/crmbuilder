"""Typed failures for the provisioning path — PI-419."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """An infrastructure-provider API call failed.

    Carries enough to be shown to an administrator and logged on a deploy run
    without the caller re-parsing the provider's response.

    :ivar provider: ``digitalocean`` or ``cloudflare``.
    :ivar status: The HTTP status, or ``None`` for a transport failure.
    :ivar message: The provider's own message when it gave one.
    """

    def __init__(self, provider: str, message: str, *, status: int | None = None):
        self.provider = provider
        self.status = status
        self.message = message
        where = f" (HTTP {status})" if status is not None else ""
        super().__init__(f"{provider}{where}: {message}")


class DeployPhaseError(RuntimeError):
    """A deploy phase could not complete; the run fails at this phase."""

    def __init__(self, phase: str, message: str):
        self.phase = phase
        self.message = message
        super().__init__(f"{phase}: {message}")
