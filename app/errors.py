class NotFound(Exception):
    """The thing the caller asked for does not exist (becomes a 404)."""


class BadInput(Exception):
    """The caller sent something we cannot accept (becomes a 400)."""


class Conflict(Exception):
    """The request clashes with the current state, like a job already running (becomes a 409)."""


class BudgetExceeded(Exception):
    """The spending cap in .env is reached, so no more AI calls are made (becomes a 402)."""
