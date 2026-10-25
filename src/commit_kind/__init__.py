"""commit-kind: a transparent, rule-based classifier for git commit message types."""

__version__ = "0.1.0"

from commit_kind.classifier import Classification, EmptyMessageError, classify

__all__ = ["Classification", "EmptyMessageError", "__version__", "classify"]
