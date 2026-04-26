class MemoryPolicy:
    def filterLongTermCandidates(self, in_candidates: list[str]) -> list[str]:
        ret: list[str]
        accepted: list[str] = []
        stableKeywords = [
            "предпочита",
            "ограничени",
            "договор",
            "всегда",
            "никогда",
            "постоян",
            "формат",
            "timezone",
        ]
        rejectKeywords = [
            "сегодня",
            "временно",
            "случайн",
            "промежуточ",
            "черновик",
        ]
        for candidateText in in_candidates:
            loweredText = candidateText.lower()
            isStable = any(item in loweredText for item in stableKeywords)
            isRejected = any(item in loweredText for item in rejectKeywords)
            if isStable and not isRejected:
                accepted.append(candidateText.strip())
        ret = accepted
        return ret
