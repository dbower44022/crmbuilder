"""Operate segment package (PI-513 / REQ-591, DEC-1077, DEC-1090).

Owns the records created by provisioning, connecting and running the
servers: the instance (one connection to a live CRM system), its deployment
configuration, the provider credential (an opaque reference to a secret in
the Shared Core secret store) and the deploy run. Build and Solution Design
read the instance; the instance membership table belongs to Build and stays
in the shared module. The deploy worker under ``crmbuilder_v2.deploy`` stays
shared: Build's audit worker uses its worker identity.

This module stays empty on purpose: the segment registry imports one
submodule at a time (``models``, ``routers``, ``tools``, ``client``, ``ui``)
so no import cycle forms with the shared files.
"""
