"""Test Specs endpoints — PI-004 cohort closer methodology entity (v0.5+).

The eight standard endpoints from ``test_spec.md`` §3.5.1 plus the
``POST /test-specs/{identifier}/record-run`` convenience endpoint per
§3.8.1 (resolved affirmatively for v0.5+). Each delegates to the
:mod:`crmbuilder_v2.access.repositories.test_spec` repository; request/
response bodies use the parent-prefixed ``test_spec_*`` field names.
Error responses use the v2 ``{data, meta, errors}`` envelope. Status
transitions render via the shared ``status_transition_handler``
(``{"error": ..., "from": ..., "to": ...}`` shape from
``domain.md`` §3.5.3). Outcome transitions are unrestricted per §3.4.2
so no equivalent handler exists for them — the only outcome-side
server-enforced rule is the §3.4.4 cross-field invariant, which
surfaces via the standard envelope as a 422 field error
(``required_when_outcome_is_run_state``).

Per ``test_spec.md`` §3.5.4 reference handling is decomposed: no
``/test-specs/{id}/scopes`` shortcut endpoints; no inline-affiliation
fields in create/update bodies. All three outbound reference kinds
(``test_spec_touches_entity``, ``test_spec_touches_field``,
``test_spec_exercises_process``) attach via the existing
``POST /references`` route. The inbound
``requirement_verified_by_test_spec`` kind is registered by the
``requirement`` side.

URL plural is hyphenated per §3.5.1; storage entity-type name keeps
the underscore.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import test_spec
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    TestSpecCreateIn,
    TestSpecPatchIn,
    TestSpecRecordRunIn,
    TestSpecReplaceIn,
)

router = APIRouter(prefix="/test-specs", tags=["test-specs"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "test_spec_"


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(
            test_spec.list_test_specs(s, include_deleted=include_deleted)
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``TST-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": test_spec.next_test_spec_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = test_spec.get_test_spec(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("test_spec", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: TestSpecCreateIn):
    # ``exclude_unset`` keeps an explicit ``test_spec_last_run_at: null``
    # distinct from an omitted ``test_spec_last_run_at`` so the §3.4.4
    # invariant can reject the former in a run state.
    provided = body.model_dump(exclude_unset=True)
    last_run_at_supplied = "test_spec_last_run_at" in provided
    with writable_session() as s:
        return ok(
            test_spec.create_test_spec(
                s,
                name=body.test_spec_name,
                description=body.test_spec_description,
                steps=body.test_spec_steps,
                expected=body.test_spec_expected,
                setup=body.test_spec_setup,
                notes=body.test_spec_notes,
                status=body.test_spec_status,
                last_run_outcome=body.test_spec_last_run_outcome,
                last_run_at=body.test_spec_last_run_at,
                last_run_notes=body.test_spec_last_run_notes,
                identifier=body.test_spec_identifier,
                last_run_at_supplied=last_run_at_supplied,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: TestSpecReplaceIn):
    provided = body.model_dump(exclude_unset=True)
    last_run_at_supplied = "test_spec_last_run_at" in provided
    with writable_session() as s:
        return ok(
            test_spec.update_test_spec(
                s,
                identifier,
                test_spec_identifier=body.test_spec_identifier,
                name=body.test_spec_name,
                description=body.test_spec_description,
                steps=body.test_spec_steps,
                expected=body.test_spec_expected,
                setup=body.test_spec_setup,
                notes=body.test_spec_notes,
                status=body.test_spec_status,
                last_run_outcome=body.test_spec_last_run_outcome,
                last_run_at=body.test_spec_last_run_at,
                last_run_notes=body.test_spec_last_run_notes,
                last_run_at_supplied=last_run_at_supplied,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: TestSpecPatchIn):
    # ``exclude_unset`` is load-bearing for the §3.4.4 invariant — see
    # the schema docstring.
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(test_spec.patch_test_spec(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(test_spec.delete_test_spec(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(test_spec.restore_test_spec(s, identifier))


@router.post("/{identifier}/record-run")
def record_run(identifier: str, body: TestSpecRecordRunIn):
    """Atomic outcome + last_run_at + last_run_notes update (§3.8.1).

    Thinner shape than PATCH for automation callers — body is just
    ``{outcome, notes?, at?}``. The §3.4.4 cross-field invariant
    applies: outcome=not_run clears last_run_at and last_run_notes;
    outcome in {passing, failing, skipped} server-defaults last_run_at
    to ``now()`` when ``at`` is omitted.
    """
    with writable_session() as s:
        return ok(
            test_spec.record_run(
                s,
                identifier,
                outcome=body.outcome,
                notes=body.notes,
                at=body.at,
            )
        )
