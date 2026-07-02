"""Knowledge-class endpoints (REL-039 / PI-357 — REQ-416, DEC-891).

Three system|engagement-scoped knowledge entities migrated out of the
instruction files: preference (PRF-), lesson (LSN-), reference_pointer (RFP-).
Each gets the standard list / next-identifier / get / create (POST) / update
(PATCH) / delete set under the ``{data, meta, errors}`` envelope, with the
identifier optional on POST (server-assigned when omitted).
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import (
    lessons,
    preferences,
    reference_pointers,
)
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    LessonCreateIn,
    LessonUpdateIn,
    PreferenceCreateIn,
    PreferenceUpdateIn,
    ReferencePointerCreateIn,
    ReferencePointerUpdateIn,
)

# --------------------------------------------------------------------------
# preferences
# --------------------------------------------------------------------------
preferences_router = APIRouter(prefix="/preferences", tags=["preferences"])


@preferences_router.get("")
def list_preferences(
    category: str | None = None,
    applies_to: str | None = None,
    status: str | None = None,
    scope: str | None = None,
):
    with readonly_session() as s:
        return ok(preferences.list_all(
            s, category=category, applies_to=applies_to, status=status, scope=scope
        ))


@preferences_router.get("/next-identifier")
def preference_next_identifier():
    with readonly_session() as s:
        return ok({"next": preferences.compute_next_identifier(s)})


@preferences_router.get("/{identifier}")
def get_preference(identifier: str):
    with readonly_session() as s:
        return ok(preferences.get(s, identifier))


@preferences_router.post("", status_code=201)
def create_preference(body: PreferenceCreateIn):
    with writable_session() as s:
        return ok(preferences.create(s, **body.model_dump()))


@preferences_router.patch("/{identifier}")
def update_preference(identifier: str, body: PreferenceUpdateIn):
    provided = body.model_dump(exclude_unset=True)
    scope = provided.pop("scope", None)
    with writable_session() as s:
        return ok(preferences.update(s, identifier, scope=scope, **provided))


@preferences_router.delete("/{identifier}")
def delete_preference(identifier: str):
    with writable_session() as s:
        return ok(preferences.delete(s, identifier))


# --------------------------------------------------------------------------
# lessons
# --------------------------------------------------------------------------
lessons_router = APIRouter(prefix="/lessons", tags=["lessons"])


@lessons_router.get("")
def list_lessons(
    category: str | None = None,
    signal: str | None = None,
    status: str | None = None,
    scope: str | None = None,
):
    with readonly_session() as s:
        return ok(lessons.list_all(
            s, category=category, signal=signal, status=status, scope=scope
        ))


@lessons_router.get("/next-identifier")
def lesson_next_identifier():
    with readonly_session() as s:
        return ok({"next": lessons.compute_next_identifier(s)})


@lessons_router.get("/{identifier}")
def get_lesson(identifier: str):
    with readonly_session() as s:
        return ok(lessons.get(s, identifier))


@lessons_router.post("", status_code=201)
def create_lesson(body: LessonCreateIn):
    with writable_session() as s:
        return ok(lessons.create(s, **body.model_dump()))


@lessons_router.patch("/{identifier}")
def update_lesson(identifier: str, body: LessonUpdateIn):
    provided = body.model_dump(exclude_unset=True)
    scope = provided.pop("scope", None)
    with writable_session() as s:
        return ok(lessons.update(s, identifier, scope=scope, **provided))


@lessons_router.delete("/{identifier}")
def delete_lesson(identifier: str):
    with writable_session() as s:
        return ok(lessons.delete(s, identifier))


# --------------------------------------------------------------------------
# reference_pointers
# --------------------------------------------------------------------------
reference_pointers_router = APIRouter(
    prefix="/reference-pointers", tags=["reference_pointers"]
)


@reference_pointers_router.get("")
def list_reference_pointers(
    kind: str | None = None,
    status: str | None = None,
    scope: str | None = None,
):
    with readonly_session() as s:
        return ok(reference_pointers.list_all(s, kind=kind, status=status, scope=scope))


@reference_pointers_router.get("/next-identifier")
def reference_pointer_next_identifier():
    with readonly_session() as s:
        return ok({"next": reference_pointers.compute_next_identifier(s)})


@reference_pointers_router.get("/{identifier}")
def get_reference_pointer(identifier: str):
    with readonly_session() as s:
        return ok(reference_pointers.get(s, identifier))


@reference_pointers_router.post("", status_code=201)
def create_reference_pointer(body: ReferencePointerCreateIn):
    with writable_session() as s:
        return ok(reference_pointers.create(s, **body.model_dump()))


@reference_pointers_router.patch("/{identifier}")
def update_reference_pointer(identifier: str, body: ReferencePointerUpdateIn):
    provided = body.model_dump(exclude_unset=True)
    scope = provided.pop("scope", None)
    with writable_session() as s:
        return ok(reference_pointers.update(s, identifier, scope=scope, **provided))


@reference_pointers_router.delete("/{identifier}")
def delete_reference_pointer(identifier: str):
    with writable_session() as s:
        return ok(reference_pointers.delete(s, identifier))
