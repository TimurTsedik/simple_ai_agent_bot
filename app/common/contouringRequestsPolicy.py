import random
import time
from threading import BoundedSemaphore
from typing import Any, Callable

import requests


class ContouringRequestsPolicy:
    """Единая политика timeout / retry и ограничение параллелизма для блокирующих HTTP-вызовов."""

    def __init__(
        self,
        in_maxConcurrentRequests: int,
        in_timeoutSeconds: float,
        in_maxRetries: int,
    ) -> None:
        self._semaphore = BoundedSemaphore(value=max(1, int(in_maxConcurrentRequests)))
        self._defaultTimeoutSeconds = max(1.0, float(in_timeoutSeconds))
        self._maxRetries = max(0, int(in_maxRetries))

    def get(
        self,
        in_url: str,
        *,
        in_params: dict[str, Any] | None = None,
        in_timeoutSeconds: float | None = None,
    ) -> requests.Response:
        timeoutValue = self._resolveTimeoutSeconds(in_timeoutSeconds=in_timeoutSeconds)

        def requestCallable() -> requests.Response:
            retInner = requests.get(in_url, params=in_params, timeout=timeoutValue)
            return retInner

        ret = self._executeWithSemaphoreAndRetries(in_requestCallable=requestCallable)
        return ret

    def post(
        self,
        in_url: str,
        *,
        in_json: dict[str, Any] | None = None,
        in_timeoutSeconds: float | None = None,
    ) -> requests.Response:
        timeoutValue = self._resolveTimeoutSeconds(in_timeoutSeconds=in_timeoutSeconds)

        def requestCallable() -> requests.Response:
            retInner = requests.post(in_url, json=in_json, timeout=timeoutValue)
            return retInner

        ret = self._executeWithSemaphoreAndRetries(in_requestCallable=requestCallable)
        return ret

    def _resolveTimeoutSeconds(self, in_timeoutSeconds: float | None) -> float:
        ret: float
        if in_timeoutSeconds is None:
            ret = self._defaultTimeoutSeconds
        else:
            ret = max(1.0, float(in_timeoutSeconds))
        return ret

    def _executeWithSemaphoreAndRetries(
        self,
        in_requestCallable: Callable[[], requests.Response],
    ) -> requests.Response:
        lastExc: requests.RequestException | None = None
        ret: requests.Response | None = None
        self._semaphore.acquire()
        try:
            attemptIndex = 0
            while True:
                try:
                    ret = in_requestCallable()
                    break
                except requests.RequestException as in_exc:
                    lastExc = in_exc
                    if attemptIndex >= self._maxRetries:
                        break
                    sleepSeconds = (0.35 * (2**attemptIndex)) + (random.random() * 0.15)
                    time.sleep(sleepSeconds)
                    attemptIndex += 1
        finally:
            self._semaphore.release()
        if ret is not None:
            return ret
        if lastExc is not None:
            raise lastExc
        raise RuntimeError("contouring_http_unexpected_state")
