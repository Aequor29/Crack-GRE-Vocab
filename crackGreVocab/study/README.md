# Study domain contract

The `study` app owns learner scheduling state and backend-planned Study Sessions.
It starts from the clean Milestone 1 schema and has no prototype compatibility or
data-migration path.

## Milestone 1 planning policy

`m1-due-first-v1` produces one bounded session with at most 30 items:

1. Return the learner's existing active session, if one exists.
2. Select states due at or before the server planning instant from the active
   corpus, ordered by due instant and then stable Word identity.
3. Fill remaining capacity with unseen Words in active-corpus order, up to the
   requested New-Word Target. The accepted target range is 0 through 20.
4. Persist the session, ordered items, and due-state snapshots in one database
   transaction before returning any content.

Due work consumes capacity before new material. A high due count can therefore
reduce the planned new count below the learner's target. A Word is unseen when
the learner has no scheduling state for its stable Word identity; an abandoned,
unanswered new item remains eligible because session planning does not create
scheduling state.

The planner returns an explicit conflict when there is no active corpus or no
eligible work. The partial unique constraint on active sessions and the locked
learner row enforce one active session in the current synchronous path. AEQ-16
will add the dedicated concurrent-request and retry contract.

## Scheduling boundary

The models can retain versioned FSRS inputs and transitions, but AEQ-13 and
AEQ-14 do not score answers. AEQ-15 owns accepted self-grades, FSRS adapter
behavior, Recall Outcomes, and current-state updates. Browser code never
reconstructs planning or scheduling rules.

## API

- `POST /api/study/sessions/` with `{"new_word_target": number}` creates a
  session (`201`) or resumes the active session (`200`).
- `GET /api/study/sessions/active/` returns the current active session or `404`.

Both endpoints require the Django session. Creation also requires the CSRF
cookie and masked `X-CSRFToken` issued by `GET /api/auth/csrf/`.

## Code boundaries

- `selectors.py` owns read-only ORM query shapes and ordering.
- `persistence.py` owns row locking and Study Session writes; callers provide
  the transaction boundary.
- `services.py` owns product policy, business exceptions, and transactional
  orchestration.
- `models.py` owns durable relationships and database constraints.
