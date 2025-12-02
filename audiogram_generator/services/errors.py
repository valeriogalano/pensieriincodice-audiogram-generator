"""Custom exceptions for service layer operations."""


class RssError(Exception):
    """Raised when fetching/parsing RSS feed fails."""


class SrtFetchError(Exception):
    """Raised when fetching transcript SRT fails."""


class AssetDownloadError(Exception):
    """Raised when downloading an external asset (e.g., image) fails."""


class RenderError(Exception):
    """Raised when rendering fails in the rendering pipeline."""
