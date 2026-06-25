import engine
from engine.config import APP_NAME


def test_engine_version() -> None:
    assert engine.__version__ == "0.0.0"


def test_app_name_default() -> None:
    assert APP_NAME == "BackTester"
