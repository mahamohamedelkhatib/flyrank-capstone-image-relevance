class NotFound(Exception):
    """The thing the caller asked for does not exist (becomes a 404)."""


class BadInput(Exception):
    """The caller sent something we cannot accept (becomes a 400)."""
