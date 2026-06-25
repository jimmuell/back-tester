import backtester
from backtester.config import APP_NAME


def test_backtester_version() -> None:
    assert backtester.__version__ == "0.2.0"


def test_app_name_default() -> None:
    assert APP_NAME == "BackTester"
