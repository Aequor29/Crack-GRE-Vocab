# Vocabulary corpus pipeline

This app owns the Milestone 1 vocabulary data model and the reproducible path
from the retained `data/GRE_word.csv` list to an immutable, importable corpus.
It does not expose runtime API endpoints and has no dependency on authentication,
the legacy backend, or a live dictionary provider.

## Data contract

`GRE_word.csv` remains the vocabulary membership source. The pipeline applies
Unicode NFKC normalization, collapses whitespace, and case-folds only for stable
identity. Accents are not removed. Duplicate normalized terms are rejected unless
their exact source rows appear in `data/vocabulary/duplicate-decisions.json`.

Definitions and examples come from a pinned provider snapshot or an explicitly
reviewed editorial override:

- Open English WordNet 2025 is the primary bulk source. Its canonical URL and
  SHA-256 are pinned in `data/vocabulary/providers.json`.
- FreeDictionaryAPI.com is the first HTTP fallback. It is limited to 1,000
  requests per hour and paced at no less than 3.6 seconds between every network
  attempt, including retries.
- DictionaryAPI.dev is the tertiary HTTP fallback.

A definition and example are always retained from the same provider sense.
FreeDictionary examples are preferred within a sense; attributed quotes from
that same sense may follow as a fallback. Provider sense IDs, snapshot digests,
parser versions, request URLs, and quote attribution are retained as provenance.
Every learner-facing example must contain the exact headword. Matching uses
Unicode-aware token boundaries and preserves spaces or hyphens in phrases; it
does not guess inflections, stems, or fuzzy relatives.

Automatic selection intentionally fails closed. It requires either one unique,
content-equivalent exact match or a strong lexical score with a clear runner-up
margin. Any ambiguity becomes review work; provider sense ordering is never used
as evidence. A checked decision is bound to the exact candidate SHA-256 so a
provider-content change invalidates the approval.

## Checked inputs and generated state

- `data/vocabulary/source-audit.json`: deterministic audit of the retained CSV.
- `data/vocabulary/duplicate-decisions.json`: reviewed duplicate collapses tied to
  the exact CSV digest.
- `data/vocabulary/providers.json`: provider versions, URLs, checksums, parser
  versions, priority, and rate policy.
- `data/vocabulary/review-queue.json`: deterministic unresolved candidates and
  current alignment-policy metadata.
- `data/vocabulary/sense-decisions.json`: checked provider-sense approvals and
  explicit dispositions for rejected legacy source hints.
- `data/vocabulary/editorial-overrides.json`: checked local definitions/examples
  for terms that cannot be resolved from a provider, with the same explicit
  source-hint disposition contract.
- `data/vocabulary/enrichment/fallback.jsonl`: resumable raw HTTP response cache
  once fallbacks have been fetched. Its payloads carry their own SHA-256.
- `data/vocabulary/versions/<version>/`: final immutable `corpus.jsonl` and
  `manifest.json` release artifacts.

The downloaded OEWN ZIP and rate-limit sidecar are local rebuild caches under
`.cache/vocabulary/`; `.cache/` is ignored by Git. Final fallback snapshots and
review decisions are build inputs and should be reviewed before they are checked
in.

## Rebuild workflow

Run commands from `crackGreVocab` with the branch-local virtual environment.

1. Audit the retained source and reproduce the checked audit:

   ```sh
   .venv/bin/python manage.py audit_vocabulary_source \
     --source data/GRE_word.csv \
     --duplicate-decisions data/vocabulary/duplicate-decisions.json \
     --output data/vocabulary/source-audit.json
   ```

2. Download and checksum-verify the pinned OEWN archive. This is the only bulk
   network step:

   ```sh
   .venv/bin/python manage.py refresh_vocabulary_snapshot \
     --providers data/vocabulary/providers.json \
     --provider oewn-2025 \
     --destination .cache/vocabulary/english-wordnet-2025-json.zip
   ```

3. Generate the deterministic review/fallback queue strictly from local files:

   ```sh
   .venv/bin/python manage.py prepare_vocabulary_review \
     --source data/GRE_word.csv \
     --duplicate-decisions data/vocabulary/duplicate-decisions.json \
     --providers data/vocabulary/providers.json \
     --oewn-archive .cache/vocabulary/english-wordnet-2025-json.zip \
     --sense-decisions data/vocabulary/sense-decisions.json \
     --editorial-overrides data/vocabulary/editorial-overrides.json \
     --fallback-cache data/vocabulary/enrichment/fallback.jsonl \
     --output data/vocabulary/review-queue.json
   ```

   The checked Milestone 1 queue is empty. All 3,034 canonical words are
   resolved: 22 by the deliberately narrow automatic policy, 2,399 by reviewed
   provider-sense decisions, and 613 by reviewed editorial overrides. Rebuilding
   this queue from the pinned local inputs must continue to produce zero items.

4. Fetch a deliberately bounded fallback batch. The JSONL cache is checkpointed,
   atomic, and resumable. Re-running the command skips cached terms. Keep each
   FreeDictionary batch at or below its 1,000-request hourly limit:

   ```sh
   .venv/bin/python manage.py fetch_vocabulary_fallbacks \
     --providers data/vocabulary/providers.json \
     --provider freedictionaryapi-v1 \
     --review-queue data/vocabulary/review-queue.json \
     --cache data/vocabulary/enrichment/fallback.jsonl \
     --rate-state .cache/vocabulary/freedictionaryapi-v1.rate-limit \
     --limit 100 \
     --checkpoint-every 25
   ```

5. Review candidates and record the accepted exact sense/example index in
   `sense-decisions.json`, including `candidate_sha256` and the exact
   `source_hints` covered by each selection. Every decision word also has an
   explicit `rejected_source_hints` list. A rejected entry copies an exact CSV
   hint and gives a non-empty canonical rationale for excluding that hint; an
   empty list is required when nothing is rejected. Selected and rejected hints
   must together dispose every CSV hint exactly once. Use
   `editorial-overrides.json` only when no provider candidate is suitable. Then
   regenerate the queue. The build remains blocked while any term is unresolved.

   A schema-v3 provider decision copies every identifier and digest from one
   candidate in the queue. This example retains one `abandon` hint and explicitly
   rejects the other as too vague to identify a sense:

   ```json
   {
     "schema_version": 3,
     "source_sha256": "8c929941d992eee05a3014a7f08b0a130a4104b142800cd987b8500a17998efb",
     "selections": {
       "abandon": {
         "rejected_source_hints": [{
           "rationale": "The legacy hint is too vague to identify a reviewable sense.",
           "source_hint": "withdraw"
         }],
         "senses": [{
           "candidate_sha256": "8767a6e1a88f1306f94ec6fd5a54968dc2215d846ede0dd1b7840d30dff28077",
           "definition_index": 0,
           "example_index": 0,
           "provider": "oewn-2025",
           "provider_sense_id": "abandon%1:07:00::",
           "provider_synset_id": "04892593-n",
           "source_hints": ["freedom from constraint"]
         }]
       }
     }
   }
   ```

   A schema-v3 editorial override has the same exact disposition contract and
   must provide an example containing the exact headword:

   ```json
   {
     "schema_version": 3,
     "source_sha256": "8c929941d992eee05a3014a7f08b0a130a4104b142800cd987b8500a17998efb",
     "words": {
       "abandon": {
         "pronunciation": "",
         "replacement_mode": "none",
         "rejected_source_hints": [{
           "rationale": "The legacy hint is too vague to identify a reviewable sense.",
           "source_hint": "withdraw"
         }],
         "senses": [{
           "definition": "freedom from constraint or inhibition",
           "editorial_id": "m1-abandon-1",
           "example": "She danced with abandon after the final exam.",
           "part_of_speech": "noun",
           "source_hints": ["freedom from constraint"]
         }]
       }
     }
   }
   ```

   If every hint for a word is demonstrably contaminated, the override may
   reject them all and provide exactly one replacement sense with
   `"source_hints": []` and `"replacement_mode": "source-contamination"`.
   The mode is an explicit, source-digest-bound review approval. This exception
   keeps the corrected sense unanchored; it cannot be mixed with hint-anchored
   senses or used without rejecting every original hint. Ordinary overrides
   must set `"replacement_mode": "none"`. Editorial parts of speech must be
   canonical supported values such as `noun`, `verb`, `adjective`, or `adverb`.

6. Build the immutable release offline. This command contains no HTTP path and
   validates every input and decision before writing:

   ```sh
   .venv/bin/python manage.py build_vocabulary_corpus \
     --source data/GRE_word.csv \
     --duplicate-decisions data/vocabulary/duplicate-decisions.json \
     --providers data/vocabulary/providers.json \
     --oewn-archive .cache/vocabulary/english-wordnet-2025-json.zip \
     --sense-decisions data/vocabulary/sense-decisions.json \
     --editorial-overrides data/vocabulary/editorial-overrides.json \
     --fallback-cache data/vocabulary/enrichment/fallback.jsonl \
     --corpus-version m1-v1 \
     --output-directory data/vocabulary/versions/m1-v1
   ```

   An identical rerun is a no-op. Reusing a version directory with different
   bytes fails instead of overwriting a release.

7. Validate and atomically import the release into PostgreSQL:

   ```sh
   .venv/bin/python manage.py import_vocabulary_corpus \
     data/vocabulary/versions/m1-v1/manifest.json \
     --report .cache/vocabulary/m1-v1-import-report.json
   ```

   Import validates all bytes before database writes, rolls back as a unit,
   preserves stable word identities across corpus versions, stores display terms
   per release, and makes at most one corpus active. Re-importing identical data
   is a verified no-op; database tampering or version-content drift fails.

## Verification

With the isolated PostgreSQL test database configured in `.env`:

```sh
.venv/bin/ruff check .
.venv/bin/mypy .
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py check
.venv/bin/python manage.py test
```

The test suite uses synthetic provider responses and never makes live HTTP calls.
The checked review queue is also pinned to the current source digest, alignment
policy, summary counts, and known ambiguity regressions so code/data drift is
visible.

## Current Milestone 1 release

`data/vocabulary/versions/m1-v1/` is the reviewed canonical release. It contains
3,034 words and 3,389 paired definition/example senses. Its corpus SHA-256 is
`15c3ea744e2c728a89c2ee1c20dec9713fdfa2d7f38ce8f313b3b819e973f1ad`;
the manifest binds that content to the exact CSV, duplicate decisions, provider
registry, OEWN archive, HTTP cache, sense decisions, and editorial overrides.
An identical rebuild is a byte-for-byte no-op. Unknown, duplicate, overlapping,
missing, and orphan hint dispositions fail closed, as does any changed input
that attempts to reuse the `m1-v1` directory.
