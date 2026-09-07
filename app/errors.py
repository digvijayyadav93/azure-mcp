"""Domain errors shared by the database, API adapter, and MCP tools."""


class NotFoundError(LookupError):
    """Raised when the requested customer or related record does not exist."""


class BackendError(RuntimeError):
    """Raised when a configured backend cannot satisfy a request."""

