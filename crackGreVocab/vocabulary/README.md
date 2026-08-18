# Vocabulary corpus pipeline

This app owns the reproducible path from the retained `data/GRE_word.csv` list
to an immutable, importable Milestone 1 corpus. Provider APIs are offline build
inputs only; the running product never depends on them.

## Durable contract

`GRE_word.csv` defines corpus membership. The source audit applies Unicode NFKC
normalization, collapses whitespace, and case-folds only for stable identity.
Duplicate normalized terms are rejected unless their exact rows are approved in
`data/vocabulary/duplicate-decisions.json`.

Every accepted sense contains one definition and one example from the same
provider sense, or one reviewed local definition/example pair. Examples must
contain the exact headword; the pipeline does not guess stems, inflections, or
fuzzy relatives. Provider candidates retain source provenance, and reviewed
provider choices are bound to the exact candidate SHA-256 so changed provider
content invalidates an approval.

The supported providers and parser behavior live in code. The checked
`providers.json` file contains only mutable URLs, checksums, and rate limits:

- Open English WordNet 2025 is the checksum-pinned bulk source.
- FreeDictionaryAPI.com is the first HTTP fallback and is paced to its published
  request limit.
- DictionaryAPI.dev is the tertiary HTTP fallback.

## Checked inputs and generated state

- `data/vocabulary/source-audit.json`: deterministic source audit.
- `data/vocabulary/duplicate-decisions.json`: reviewed duplicate collapses.
- `data/vocabulary/providers.json`: mutable provider pins.
- `data/vocabulary/sense-decisions.json`: exact provider candidate/example
  selections, plus an optional word-level review note for an exceptional choice.
- `data/vocabulary/editorial-overrides.json`: checked local learning content,
  plus an optional word-level review note.
- `data/vocabulary/review-queue.json`: deterministic unresolved candidates and
  alignment-policy metadata.
- `data/vocabulary/enrichment/fallback.jsonl`: resumable raw HTTP cache.
- `data/vocabulary/versions/<version>/`: immutable corpus and manifest releases.

Legacy CSV hints remain useful evidence during candidate alignment and review,
but they are not a second persisted domain model. An editor approves learning
content; they do not need to classify every old hint as retained or rejected.

## Rebuild workflow

Run commands from `crackGreVocab` with the branch-local virtual environment.

1. Audit the retained source:

   ```sh
   .venv/bin/python manage.py audit_vocabulary_source \
     --source data/GRE_word.csv \
     --duplicate-decisions data/vocabulary/duplicate-decisions.json \
     --output data/vocabulary/source-audit.json
   ```

2. Download and checksum-verify the pinned OEWN archive:

   ```sh
   .venv/bin/python manage.py refresh_vocabulary_snapshot \
     --providers data/vocabulary/providers.json \
     --provider oewn-2025 \
     --destination .cache/vocabulary/english-wordnet-2025-json.zip
   ```

3. Generate the deterministic review queue from local inputs:

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

   The checked Milestone 1 queue is empty. Tests assert the queue policy, source
   digest, and absence of actionable items rather than historical accounting
   totals for how each word happened to resolve.

4. Fetch a bounded fallback batch when the queue requires it:

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

   One command owns a fallback cache at a time. Checkpoints are atomic and
   resumable; a second writer fails clearly instead of merging competing data.
   Provider pacing persists across command restarts.

5. Review candidate material. A schema-v4 provider decision names the exact
   candidate and example; an exceptional choice may include one concise note:

   ```json
   {
     "schema_version": 4,
     "source_sha256": "8c929941d992eee05a3014a7f08b0a130a4104b142800cd987b8500a17998efb",
     "selections": {
       "abandon": {
         "senses": [{
           "candidate_sha256": "8767a6e1a88f1306f94ec6fd5a54968dc2215d846ede0dd1b7840d30dff28077",
           "definition_index": 0,
           "example_index": 0,
           "provider": "oewn-2025",
           "provider_sense_id": "abandon%1:07:00::",
           "provider_synset_id": "04892593-n"
         }]
       }
     }
   }
   ```

   A schema-v4 editorial override contains only learning content and an optional
   word-level note:

   ```json
   {
     "schema_version": 4,
     "source_sha256": "8c929941d992eee05a3014a7f08b0a130a4104b142800cd987b8500a17998efb",
     "words": {
       "abase": {
         "pronunciation": "",
         "senses": [{
           "definition": "to lower someone in rank, dignity, or self-respect",
           "editorial_id": "m1-editorial-abase-1",
           "example": "The despot tried to abase every official who challenged him.",
           "part_of_speech": "verb"
         }]
       }
     }
   }
   ```

6. Build the current immutable release offline:

   ```sh
   .venv/bin/python manage.py build_vocabulary_corpus \
     --source data/GRE_word.csv \
     --duplicate-decisions data/vocabulary/duplicate-decisions.json \
     --providers data/vocabulary/providers.json \
     --oewn-archive .cache/vocabulary/english-wordnet-2025-json.zip \
     --sense-decisions data/vocabulary/sense-decisions.json \
     --editorial-overrides data/vocabulary/editorial-overrides.json \
     --fallback-cache data/vocabulary/enrichment/fallback.jsonl \
     --corpus-version m1-v2 \
     --output-directory data/vocabulary/versions/m1-v2
   ```

   Identical inputs produce identical bytes and an identical rerun is a no-op.
   Reusing a release directory with different bytes fails. Each build input is
   read once into an immutable byte snapshot; parsing and manifest SHA-256 values
   use that same snapshot, so a release cannot describe bytes it did not consume.

7. Validate and atomically import the release into PostgreSQL:

   ```sh
   .venv/bin/python manage.py import_vocabulary_corpus \
     data/vocabulary/versions/m1-v2/manifest.json \
     --report .cache/vocabulary/m1-v2-import-report.json
   ```

   Import validates every artifact byte before database writes, preserves stable
   Word identities across corpus versions, and activates at most one release.
   Matching version/digest/count metadata makes an identical re-import a no-op.

## Verification

```sh
.venv/bin/ruff check .
.venv/bin/mypy .
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py check
.venv/bin/python manage.py test
```

Tests use synthetic provider responses and never require live HTTP. The checked
release membership is compared directly with the audited `GRE_word.csv` list.

## Current Milestone 1 release

`data/vocabulary/versions/m1-v2/` contains 3,034 words and 3,389 paired senses.
Its corpus SHA-256 is
`b7ab61e2771b9097ea715861c448c6da2bd6ef3cda1eeb4b6a57327b6eac47bb`.
The learner-facing terms, definitions, and examples are unchanged from m1-v1;
m1-v2 simplifies review metadata and records the new checked-input digests.
