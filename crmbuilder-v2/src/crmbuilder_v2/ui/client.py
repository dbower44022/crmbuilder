"""Typed HTTP client over the v2 storage REST API.

Wired in slice C. Wraps the storage system REST endpoints, parses the
envelope response shape, and surfaces validation/conflict/not-found
errors as typed exceptions. Pure Python, no Qt dependencies. Per
DEC-019 the UI consumes the API exclusively through this client.
"""
