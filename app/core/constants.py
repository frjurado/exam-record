class Roles:
    # users.role values. Only ADMIN is checked anywhere; it is granted with scripts/set_role.py.
    VISITOR = "Visitor"
    ADMIN = "Admin"


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
    # slowapi limit strings. Counters live in each worker's memory, so with N workers
    # the effective limit is up to N times the figure.
    # Link requests are anonymous: per IP (generous, a classroom shares one address)...
    MAGIC_LINK_REQUEST = "30/hour"
    # ...and per target address, so nobody can flood someone else's inbox.
    MAGIC_LINK_PER_EMAIL = "5/hour"
    # Per signed-in user (per IP for the anonymous click that opens the email form).
    REPORT_CREATION = "10/hour"
    VOTE_CAST = "20/hour"
    # Type-ahead searches that may reach OpenOpus/Wikidata. High enough for fast typing,
    # low enough that the endpoints cannot be used as an open proxy to those services.
    CATALOG_SEARCH = "120/minute"


class Cache:
    # Region/Discipline rows are effectively static reference data (seeded once,
    # never edited by users), so a TTL just bounds how long a manual DB edit
    # takes to show up rather than guarding against real staleness.
    REFERENCE_DATA_TTL_SECONDS = 3600
    REFERENCE_DATA_MAX_ENTRIES = 64
    # A composer's OpenOpus catalogue is static for our purposes; a day bounds memory
    # use on a long-lived worker rather than guarding against staleness.
    OPENOPUS_TTL_SECONDS = 86400
    OPENOPUS_MAX_COMPOSERS = 128


class Statistics:
    # A work appears in the "works that repeat" list from this many appearances.
    MIN_WORK_APPEARANCES = 2
    # Longest ranking shown.
    MAX_ROWS = 30


class Coverage:
    # How many recent years the region table shows by default. Recent exams are the
    # ones people can still report (fresh memory, candidates still reachable); the full
    # range back to Calendar.MIN_YEAR is one click away.
    YEARS = 6


class Suggestions:
    # How many frequently reported composers the contribute form offers before typing.
    MAX_COMPOSERS = 8
    # How many of a composer's works are offered before typing.
    MAX_WORKS = 40
