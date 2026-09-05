# Study

The `study` app owns daily Study Sessions, accepted Recall Answers, and their
scheduling outcomes. Initialize its schema by applying the current migrations
to a fresh PostgreSQL database.

## Daily sessions

Starting a session assigns every overdue or same-day scheduled Word from the
active corpus plus the requested new words. The new-word target is 0 through
20, limited by the available unseen words. Each session stores the learner's
IANA timezone and the next local midnight as its completion boundary.

New words have a stable, learner-specific order for a given corpus and planning
policy. Due reviews start ahead of new words, ordered by their scheduled time.
The persisted session preserves its membership and order when resumed.

The working window holds up to 30 unfinished words and refills from the
session's assigned set. Each answer advances to the least recently presented
unfinished word. A word scheduled at or beyond the session's day boundary is
cleared; a word still due today rotates back into practice immediately.

Progress counts unique cleared words. The session completes when every assigned
word is cleared. A learner can pause and resume with the same current card and
saved progress. Abandoning a session retains its accepted answers; unanswered
new words remain eligible for future sessions.

## Scheduling

The current scheduling policy is `m1-fsrs-6.3.1-binary-v1`. The FSRS adapter maps
Remembered to Good and Forgot to Again, with 90% desired retention, one- and
ten-minute learning steps, a ten-minute relearning step, and a maximum interval
of 36,500 days. Fuzzing is disabled. Each answer uses its actual server timestamp
and stores the resulting FSRS state and next review date.

A fresh word answered Remembered normally advances to a ten-minute learning
review, then to the Review phase after its next Remembered answer. The session
can present that repeat during the current sitting. Completion is determined
by the saved daily boundary. Only a Forgot answer beginning in the Review phase
increments the lapse count.

## API and recovery

- `POST /api/study/sessions/` accepts
  `{"new_word_target": number, "timezone": "Area/City"}`. It creates a session
  (`201`) or resumes the active session (`200`).
- `GET /api/study/sessions/active/` returns the active session and its current
  card, or `404` when none exists.
- `POST /api/study/sessions/{session_id}/items/{item_id}/answer/` accepts a stable
  `client_request_id` and a `remembered` or `forgot` rating. It records the answer
  and outcome (`201`) or returns the previously accepted answer on replay (`200`).

All endpoints require the learner's Django session. Mutations require the CSRF
cookie and masked `X-CSRFToken` issued by `GET /api/auth/csrf/`. Responses include
the current card, session status, and unique-word progress.

Concurrent session starts converge on one active session for the learner.
Concurrent submissions for an issued card produce one accepted answer.
An identical retry returns the accepted result; a conflicting rating or reused
request identity is rejected. Answer, scheduling-state, and progress writes
commit together.

The frontend keeps a pending answer's identity through retries and refreshes.
It restores authoritative progress after a conflict, offers retry for temporary
unavailability, and redirects expired authentication to sign-in.

## Modules

- `services.py`: session planning, answer acceptance, and transaction boundaries.
- `selectors.py`: session, corpus, and scheduling-state reads.
- `persistence.py`: row locking and writes.
- `new_words.py`: stable learner-specific new-word selection.
- `scheduling.py`: FSRS transitions.
- `policy.py`: planning limits and policy version.
- `models.py`: durable relationships and constraints.

## Verification

With the repository-root virtual environment active, run the complete backend
gate from the repository root:

```sh
python scripts/verify_backend.py
```

It includes the clean-schema check, PostgreSQL concurrency and answer-retry
tests, scheduling tests, and API-contract verification. Follow the
[root README](../../README.md) for local setup and the frontend gate.
