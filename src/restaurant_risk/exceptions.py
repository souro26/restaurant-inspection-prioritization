class PipelineError(Exception):
    """Base exception for pipeline failures."""


class DataQualityError(PipelineError):
    """Raised when a hard data-quality contract is violated."""


class SourceDataError(PipelineError):
    """Raised when the source cannot be downloaded or loaded."""


class TransformationError(PipelineError):
    """Raised when a SQL transformation fails."""


class ValidationError(PipelineError):
    """Raised when validation SQL detects an invalid state."""