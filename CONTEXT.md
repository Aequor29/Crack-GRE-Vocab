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
A refresh-safe read model of one learner's current corpus coverage, actionable review load, today's activity, and recent Recall Outcomes.
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
