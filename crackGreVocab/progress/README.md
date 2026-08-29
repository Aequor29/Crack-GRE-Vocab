# Learning Progress metrics

The `progress` app owns read-only, backend-authoritative views of current Learning Progress and historical learning insights. It does not change scheduling state.

## Review Recall Rate

Review Recall Rate is `Remembered / accepted Review-phase Recall Answers` for a learner-local date range.

- The current period contains today and the preceding 29 local dates.
- The comparison period is the immediately preceding 30 local dates.
- An answer counts only when its Recall Outcome began in the `review` phase. Initial learning, learning, and relearning answers are excluded.
- A period with no qualifying answers has no percentage.
- A percentage based on fewer than 10 qualifying answers is returned as an early trend. The period-to-period change is shown only when both periods contain at least 10 qualifying answers.
- Change is expressed as percentage points, not percent growth.

## Study Days and Current Study Streak

A Study Day is a learner-local date with at least one accepted Recall Outcome. Calendar intensity uses the number of distinct Words practiced that day; the API also returns the accepted-answer count.

The Current Study Streak counts consecutive Study Days ending today. When the learner has not studied today, the streak may end yesterday because the current day is still available. A completed local date without an accepted outcome breaks the streak. Local midnights are converted through the requested IANA timezone, including daylight-saving transitions.

## Weekly Learning Curve

The Learning Curve contains 12 learner-local weeks beginning on Monday. Completed points end on Sunday; the current point ends on the current local date.

Each point is a snapshot of the active Vocabulary Corpus:

- `unseen`: Words without an accepted Recall Outcome by the end of the week;
- `learning`: Words whose latest outcome ends in learning or relearning;
- `review`: Words whose latest outcome ends in review.

History follows stable Word identity across Vocabulary Corpus releases. The backend reconstructs the first point from at most one pre-window outcome per active-corpus Word, then applies only phase transitions inside the 12-week window. Calendar activity and Review Recall Rate use bounded date-range aggregations; the Current Study Streak reads distinct Study Days rather than individual answers.
