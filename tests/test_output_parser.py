from app.runtime.outputParser import OutputParser


def testParseValidFinalOutput() -> None:
    parser = OutputParser()
    rawText = '{"type":"final","reason":"done","final_answer":"Готово"}'

    result = parser.parse(in_rawText=rawText)

    assert result.isValid is True
    assert result.parsedOutput is not None
    assert result.parsedOutput.outputType == "final"
    assert result.parsedOutput.finalAnswer == "Готово"


def testParseValidToolCallOutput() -> None:
    parser = OutputParser()
    rawText = (
        '{"type":"tool_call","reason":"need_data","action":"digest_news",'
        '"args":{"topic":"ai"}}'
    )

    result = parser.parse(in_rawText=rawText)

    assert result.isValid is True
    assert result.parsedOutput is not None
    assert result.parsedOutput.outputType == "tool_call"
    assert result.parsedOutput.action == "digest_news"


def testParseInvalidJsonOutput() -> None:
    parser = OutputParser()
    rawText = '{"type":"final","reason":"x","final_answer":"y"'

    result = parser.parse(in_rawText=rawText)

    assert result.isValid is False
    assert result.errorCode == "INVALID_JSON"


def testParseSchemaViolationOutput() -> None:
    parser = OutputParser()
    rawText = '{"type":"final","reason":"x"}'

    result = parser.parse(in_rawText=rawText)

    assert result.isValid is False
    assert result.errorCode == "INVALID_SCHEMA"
