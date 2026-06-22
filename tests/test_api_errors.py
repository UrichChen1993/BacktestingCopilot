from backtesting_copilot.app.api.errors import classify_exception, APIValidationError
from backtesting_copilot.data.provider import DataUnavailableError


def test_data_unavailable_is_422():
    code, detail = classify_exception(DataUnavailableError("no data"))
    assert code == 422
    assert detail["error_code"] == "DATA_UNAVAILABLE"


def test_validation_error_is_400():
    code, detail = classify_exception(APIValidationError("bad param"))
    assert code == 400
    assert detail["error_code"] == "VALIDATION_ERROR"


def test_unknown_exception_is_500():
    code, detail = classify_exception(RuntimeError("boom"))
    assert code == 500
    assert detail["error_code"] == "INTERNAL_ERROR"
