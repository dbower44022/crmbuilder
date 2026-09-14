"""Client Management segment package (PI-508 / REQ-591, DEC-1077, DEC-1090).

Owns the client organisation's scope records: the engagement registry row,
the principal, the access token, the role assignment, and the participant.
The engagement row is the scope root every scoped table's foreign key points
at; the principal, token and role-assignment rows are system-wide and are
never filtered by engagement. The engagement-scope filter and the principal
middleware are Shared Core plumbing and read these tables from outside.

This module stays empty on purpose: the segment registry imports one
submodule at a time (``models``, ``routers``, ``tools``, ``client``, ``ui``)
so no import cycle forms with the shared files.
"""
