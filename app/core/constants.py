class Pagination:
    DEFAULT_BATCH_SIZE = 10


class Calendar:
    # Month (inclusive) at which the current year is used as anchor; before it, prior year is used.
    ACADEMIC_YEAR_CUTOFF_MONTH = 6
    # How many of the most recent academic years are always shown regardless of data.
    MANDATORY_YEARS_WINDOW = 5
    # Oldest year that can appear in the discipline timeline.
    MIN_YEAR = 2000


class Consensus:
    # Minimum number of votes a report must have before its status can move beyond "neutral".
    MIN_VOTES_FOR_VERIFICATION = 2
    # Fraction of total event votes a single report must hold to be considered "verified".
    VERIFICATION_THRESHOLD = 0.75


class RateLimit:
    # slowapi limit strings, keyed by remote address (per-IP).
    MAGIC_LINK_REQUEST = "5/minute"
    REPORT_CREATION = "10/hour"
    VOTE_CAST = "20/hour"


class Cache:
    # Region/Discipline rows are effectively static reference data (seeded once,
    # never edited by users), so a TTL just bounds how long a manual DB edit
    # takes to show up rather than guarding against real staleness.
    REFERENCE_DATA_TTL_SECONDS = 3600
    REFERENCE_DATA_MAX_ENTRIES = 64
