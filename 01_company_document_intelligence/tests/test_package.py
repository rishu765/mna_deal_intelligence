"""Foundation checks for the installable package."""

import ma_company_intelligence


def test_package_exposes_version() -> None:
    assert ma_company_intelligence.__version__ == "0.1.0"

