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
