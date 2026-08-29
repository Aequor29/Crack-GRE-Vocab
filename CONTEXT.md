# Crack GRE Vocab

Crack GRE Vocab helps a learner build durable recall of a versioned GRE vocabulary corpus through bounded study sessions and backend-owned scheduling.

## Vocabulary

**Vocabulary Corpus**:
The active, versioned collection of GRE words available to every learner.
_Avoid_: Word set, vocabulary list

**Word**:
A stable vocabulary identity that can appear in more than one Vocabulary Corpus release.
_Avoid_: Card, item

## Study

**Study Session**:
A bounded, resumable sequence of new and due Words planned for one learner.
_Avoid_: Lesson, sitting

**Recall Answer**:
A learner's accepted self-grade of remembered or forgot for one Word in a Study Session.
_Avoid_: Response, result

**Recall Outcome**:
The immutable scheduling transition produced by an accepted Recall Answer.
_Avoid_: Answer result, review result

## Progress

**Learning Progress**:
A refresh-safe read model of one learner's current corpus coverage, actionable review load, and today's activity.
_Avoid_: Study state, analytics

**Unseen Word**:
A Word in the active Vocabulary Corpus for which the learner has no scheduling state.
_Avoid_: New Word

**Learning Word**:
A Word whose current scheduling phase is learning or relearning.
_Avoid_: In-progress Word

**Review Word**:
A Word whose current scheduling phase is review.
_Avoid_: Learned Word, mastered Word

**Due Now**:
A scheduled Word whose next review time is at or before the Learning Progress snapshot time.
_Avoid_: Overdue

**Due Today**:
A scheduled Word whose next review time falls before the end of the learner's current local day, including Due Now Words.
_Avoid_: Today's reviews

**Review Recall Rate**:
The share of accepted Remembered answers among Recall Answers that began in the Review phase during a stated period. Initial learning and relearning answers are excluded.
_Avoid_: Accuracy, retention score

**Study Day**:
A date in the learner's timezone on which at least one Recall Answer was accepted.
_Avoid_: Login day, active day

**Current Study Streak**:
The uninterrupted count of Study Days through today, or through yesterday while the current local day is still available to study. A completed date without an accepted Recall Answer breaks the streak.
_Avoid_: Attendance streak

**Learning Curve**:
A week-by-week history of how the active Vocabulary Corpus is distributed across Unseen, Learning, and Review Words.
_Avoid_: Score history, mastery curve
