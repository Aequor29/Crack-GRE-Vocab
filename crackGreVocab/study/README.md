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

`m1-fsrs-6.3.1-binary-v1` is the first accepted Recall Outcome policy. It pins
py-fsrs 6.3.1 behind `scheduling.py`, maps Remembered to Good and Forgot to
Again, uses 90% desired retention, one- and ten-minute learning steps, one
ten-minute relearning step, a 36,500-day maximum interval, and disables
fuzzing. Every transition receives one explicit server UTC instant and stores
the complete serialized card state. Browser code never reconstructs planning
or scheduling rules.

Only a Review-phase Forgot increments the lapse count. A new or learning Word
still receives the appropriate failed-recall transition without being counted
as a review lapse.

## API

- `POST /api/study/sessions/` with `{"new_word_target": number}` creates a
  session (`201`) or resumes the active session (`200`).
- `GET /api/study/sessions/active/` returns the current active session or `404`.
- `POST /api/study/sessions/{session_id}/items/{item_id}/answer/` with a stable
  `client_request_id` and `remembered` or `forgot` rating records one Recall
  Outcome (`201`) or returns the exact accepted replay (`200`).

All endpoints require the Django session. Mutations also require the CSRF cookie
and masked `X-CSRFToken` issued by `GET /api/auth/csrf/`.

## Code boundaries

- `selectors.py` owns read-only ORM query shapes and ordering.
- `persistence.py` owns row locking and Study Session writes; callers provide
  the transaction boundary.
- `services.py` owns product policy, business exceptions, and transactional
  orchestration.
- `scheduling.py` owns the pure, versioned FSRS adapter and contains no ORM
  access.
- `models.py` owns durable relationships and database constraints.
