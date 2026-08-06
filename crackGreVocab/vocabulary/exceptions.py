"""Actionable vocabulary pipeline failures."""


class VocabularyPipelineError(ValueError):
    """Base class for deterministic vocabulary pipeline errors."""


class SourceAuditError(VocabularyPipelineError):
    """The retained source list or its duplicate decisions are invalid."""


class SnapshotError(VocabularyPipelineError):
    """A pinned provider snapshot or cached response is invalid."""


class CorpusBuildError(VocabularyPipelineError):
    """A canonical corpus cannot be built from reviewed local inputs."""


class CorpusImportError(VocabularyPipelineError):
    """A corpus artifact cannot be safely imported."""


class EnrichmentFetchError(VocabularyPipelineError):
    """A network-only enrichment refresh could not complete safely."""
