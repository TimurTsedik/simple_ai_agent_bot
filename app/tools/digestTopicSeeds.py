"""Seed keywords for digest topics (substring match on post text, lower-cased)."""

from typing import Final


_DIGEST_TOPIC_SEED_KEYWORDS: Final[dict[str, list[str]]] = {
    "ai": [
        "llm",
        "gpt",
        "claude",
        "openai",
        "neural",
        "инференс",
        "модель",
        "агент",
        "генератив",
        "embedding",
        "трансформер",
        "fine-tun",
        "rag",
        "машинное обучение",
    ],
    "economy": [
        "инфляц",
        "цб",
        "фрс",
        "fed",
        "gdp",
        "ввп",
        "ставк",
        "офз",
        "минфин",
        "бюджет",
        "дефицит",
        "pmi",
        "рынок облигаций",
    ],
    "crypto": [
        "bitcoin",
        "btc",
        "ethereum",
        "eth",
        "крипт",
        "defi",
        "stablecoin",
        "блокчейн",
        "etf на биткоин",
    ],
    "markets": [
        "индекс",
        "s&p",
        "nasdaq",
        "moex",
        "imoex",
        "фьючерс",
        "опцион",
        "волатильность",
        "ликвидность",
    ],
    "tech": [
        "chip",
        "semiconductor",
        "nvidia",
        "datacenter",
        "cloud",
        "saas",
        "кибер",
        "security",
    ],
    "custom": [],
}


def collectSeedKeywordsForTopics(in_topics: list[str]) -> list[str]:
    ret: list[str]
    merged: list[str] = []
    seen: set[str] = set()
    for rawTopic in in_topics:
        if not isinstance(rawTopic, str):
            continue
        topicKey = rawTopic.strip().lower()
        if not topicKey:
            continue
        seedList = _DIGEST_TOPIC_SEED_KEYWORDS.get(topicKey, [])
        for seed in seedList:
            normalized = seed.strip()
            if not normalized:
                continue
            keyLower = normalized.lower()
            if keyLower in seen:
                continue
            seen.add(keyLower)
            merged.append(normalized)
    ret = merged
    return ret
