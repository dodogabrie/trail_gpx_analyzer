"""Custom exceptions for hybrid prediction system."""


class HybridPredictionError(Exception):
    """Base exception for hybrid prediction errors."""
    pass


class InsufficientDataError(HybridPredictionError):
    """Raised when user has insufficient activities for requested tier."""
    pass


class TrainingFailedError(HybridPredictionError):
    """Raised when model training fails."""
    pass


class ModelNotFoundError(HybridPredictionError):
    """Raised when expected model is not found."""
    pass


class InvalidParametersError(HybridPredictionError):
    """Raised when parameters are invalid or out of bounds."""
    pass


class OptimizationError(HybridPredictionError):
    """Raised when optimization fails to converge."""
    pass


class ResidualCollectionError(HybridPredictionError):
    """Raised when residual collection from activity fails."""
    pass
