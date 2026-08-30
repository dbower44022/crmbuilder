"""Infrastructure-provider REST clients — PI-419.

Thin ``requests``-based wrappers (no SDK: the production venv cannot install
packages) exposing only the calls the deploy runner needs. Every failure is a
:class:`~crmbuilder_v2.deploy.errors.ProviderError` so the runner and the API
can report it as a run error rather than a 500.
"""
