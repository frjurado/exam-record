from unittest.mock import patch

from app.core import monitoring
from app.core.config import settings


def test_init_sentry_noop_in_development():
    with (
        patch.object(settings, "ENVIRONMENT", "development"),
        patch.object(settings, "SENTRY_DSN", "https://example@sentry.io/1"),
        patch("app.core.monitoring.sentry_sdk.init") as mock_init,
    ):
        monitoring.init_sentry()

    mock_init.assert_not_called()


def test_init_sentry_noop_without_dsn():
    with (
        patch.object(settings, "ENVIRONMENT", "production"),
        patch.object(settings, "SENTRY_DSN", None),
        patch("app.core.monitoring.sentry_sdk.init") as mock_init,
    ):
        monitoring.init_sentry()

    mock_init.assert_not_called()


def test_init_sentry_initializes_in_production_with_dsn():
    dsn = "https://example@sentry.io/1"
    with (
        patch.object(settings, "ENVIRONMENT", "production"),
        patch.object(settings, "SENTRY_DSN", dsn),
        patch("app.core.monitoring.sentry_sdk.init") as mock_init,
    ):
        monitoring.init_sentry()

    mock_init.assert_called_once_with(dsn=dsn, send_default_pii=False)
