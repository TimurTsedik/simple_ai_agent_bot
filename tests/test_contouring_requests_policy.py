from unittest.mock import MagicMock, patch

import pytest
import requests

from app.common.contouringRequestsPolicy import ContouringRequestsPolicy


def testContouringRequestsPolicyRetriesThenSucceeds() -> None:
    callCount = {"value": 0}

    def fakeGet(*args, **kwargs) -> MagicMock:  # noqa: ANN002, ANN003
        callCount["value"] += 1
        if callCount["value"] < 2:
            raise requests.ConnectionError("transient")
        ret = MagicMock()
        ret.status_code = 200
        return ret

    policy = ContouringRequestsPolicy(
        in_maxConcurrentRequests=2,
        in_timeoutSeconds=10.0,
        in_maxRetries=2,
    )
    with patch("app.common.contouringRequestsPolicy.requests.get", side_effect=fakeGet):
        response = policy.get("https://example.test/", in_params=None)

    assert response.status_code == 200
    assert callCount["value"] == 2


def testContouringRequestsPolicyRaisesAfterRetries() -> None:
    policy = ContouringRequestsPolicy(
        in_maxConcurrentRequests=2,
        in_timeoutSeconds=10.0,
        in_maxRetries=1,
    )
    with patch(
        "app.common.contouringRequestsPolicy.requests.get",
        side_effect=requests.ConnectionError("always"),
    ):
        with pytest.raises(requests.ConnectionError):
            policy.get("https://example.test/", in_params=None)
