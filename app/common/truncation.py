def truncateText(in_text: str, in_maxChars: int) -> tuple[str, bool]:
    ret: tuple[str, bool]
    if len(in_text) <= in_maxChars:
        ret = (in_text, False)
    else:
        ret = (in_text[:in_maxChars], True)
    return ret
