from app.domain.policies.memoryPolicy import MemoryPolicy


def testMemoryPolicyKeepsOnlyStableCandidates() -> None:
    policy = MemoryPolicy()
    candidates = [
        "Пользователь предпочитает короткий формат ответа",
        "Сегодня нужно проверить черновик вручную",
        "Постоянное ограничение: отвечать только на русском",
    ]

    result = policy.filterLongTermCandidates(in_candidates=candidates)

    assert len(result) == 2
    assert "короткий формат" in result[0]
    assert "Постоянное ограничение" in result[1]
