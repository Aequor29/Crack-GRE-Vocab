# Study domain contract

The `study` app owns learner scheduling state and backend-planned Study Sessions.
It starts from the clean Milestone 1 schema and has no prototype compatibility or
data-migration path.

## Milestone 1 daily queue policy

`m1-daily-queue-stable-deck-v2` produces one fixed daily set and a bounded working window:

1. Return the learner's existing active session, if one exists.
2. Store the next local midnight as a stable UTC completion cutoff using the
   learner's validated IANA timezone.
3. Assign every overdue or same-day scheduled Word from the active corpus plus
   the available requested New-Word Target. The accepted target range is 0
   through 20.
4. Activate at most 30 session Words at once. Ready work takes priority and the
   window refills without creating another learner-visible session.
5. Persist unique Word membership separately from presentation attempts so a
   Learning or Relearning Word can return after its timer elapses.

Review-phase work due later in the local day is ready immediately. Learning and
Relearning timers retain their actual minute-based readiness. Among ready Words,
the queue chooses the least recently presented Word and uses stable initial
position to break ties.

Progress is the number of unique session Words whose authoritative next review
is at or beyond the stored cutoff. Repeated attempts do not increase that count,
and the session completes only when every assigned Word is cleared for the day.
The API derives counts with database aggregates and returns only the issued card,
progress, waiting state, and next-ready time; it never resends attempt history.

A Word is unseen when the learner has no scheduling state for its stable Word
identity. An abandoned, unanswered new membership remains eligible because
session planning does not create scheduling state.

New Words have a stable, individualized deck order. Selection ranks each eligible
Word by SHA-256 of the ASCII JSON array `[planner_version, str(learner_id),
corpus.version]` (compact separators), followed by the Word UUID's 16 bytes.
The Word UUID breaks digest ties. The corpus release name and Word identity are
used instead of corpus-entry IDs or canonical positions. Given the same learner,
corpus, and policy, removing seen Words preserves the relative order of every
remaining Word. Changing corpus or policy can change the new-Word order.

The selector streams unseen Word IDs and keeps only the requested top K with a
bounded heap: O(U log K) time and O(K) ranking memory for U eligible Words, or
O(U) time for K=1. The database cursor reads fixed-size chunks; only the winning
entries are loaded with their content relationships. K=0 returns immediately.
Due reviews retain their oldest-due-first initial positions ahead of new Words.
Selected new Words receive stable positions in the daily queue. Active sessions
retain their saved order and planner version when resumed after a policy update.
No corpus artifacts or additional learner-deck tables are needed.

The planner returns a coded conflict when there is no active corpus or no
eligible work. The partial unique constraint on active sessions and the locked
learner row enforce one active session under concurrent requests. The write
path also rejects any corpus entry that does not belong to the session corpus
before it creates the session row.

## Scheduling boundary

`m1-fsrs-6.3.1-binary-v1` is the first accepted Recall Outcome policy. It pins
py-fsrs 6.3.1 behind `scheduling.py`, maps Remembered to Good and Forgot to
Again, uses 90% desired retention, one- and ten-minute learning steps, one
ten-minute relearning step, a 36,500-day maximum interval, and disables
fuzzing. Every transition receives one explicit server UTC instant and stores
the complete serialized card state. Browser code never reconstructs planning
or scheduling rules.

The complete FSRS card is canonical. Difficulty and stability are not copied
into separate columns because Milestone 1 has no read model that queries them.

Only a Review-phase Forgot increments the lapse count. A new or learning Word
still receives the appropriate failed-recall transition without being counted
as a review lapse.

## API

- `POST /api/study/sessions/` with
  `{"new_word_target": number, "timezone": "Area/City"}` creates a session
  (`201`) or resumes the active session (`200`).
- `GET /api/study/sessions/active/` returns the current active session or `404`.
- `POST /api/study/sessions/{session_id}/items/{item_id}/answer/` with a stable
  `client_request_id` and `remembered` or `forgot` rating records one Recall
  Outcome (`201`) or returns the exact accepted replay (`200`).

All endpoints require the Django session. Mutations also require the CSRF cookie
and masked `X-CSRFToken` issued by `GET /api/auth/csrf/`.

Study failures include stable machine-readable codes. Authentication and CSRF
rejection do not require clients to parse framework messages. Only connection
and operational database failures are returned as retryable `503` responses;
integrity, schema, and programming defects surface as server errors.

## Code boundaries

- `selectors.py` owns read-only ORM query shapes and ordering.
- `new_words.py` owns pure deterministic top-K selection of unseen Word IDs.
- `persistence.py` owns row locking and Study Session writes; callers provide
  the transaction boundary.
- `policy.py` owns shared planning limits and version identifiers.
- `services.py` owns business exceptions and transactional orchestration.
- `scheduling.py` owns the pure, versioned FSRS adapter and contains no ORM
  access.
- `models.py` owns durable relationships and database constraints.
