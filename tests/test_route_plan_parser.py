from app.runtime.routePlanParser import RoutePlanParser


def testRoutePlanParserAcceptsMinimalValidPlan() -> None:
    yamlTextValue = """type: route_plan
selected_skill_ids:
  - default_assistant
allow_tool_calls: true
required_first_successful_tool_name: ""
memory_mode: full
"""
    parserInstance = RoutePlanParser()
    parseOutcomeModel = parserInstance.parseAndValidateCatalog(
        in_rawText=yamlTextValue,
        in_knownSkillIds={"default_assistant"},
        in_registeredToolNames=set(),
    )
    assert parseOutcomeModel.isValid is True
    assert parseOutcomeModel.validatedPlan is not None


def testRoutePlanParserRejectsUnknownToolName() -> None:
    yamlTextValue = """type: route_plan
selected_skill_ids:
  - default_assistant
allow_tool_calls: true
required_first_successful_tool_name: read_email
memory_mode: full
"""
    parserInstance = RoutePlanParser()
    parseOutcomeModel = parserInstance.parseAndValidateCatalog(
        in_rawText=yamlTextValue,
        in_knownSkillIds={"default_assistant"},
        in_registeredToolNames=set(),
    )
    assert parseOutcomeModel.isValid is False


def testRoutePlanParserStripsFenceWrapping() -> None:
    yamlTextValue = """```yaml
type: route_plan
selected_skill_ids: [default_assistant]
allow_tool_calls: false
required_first_successful_tool_name: ''
memory_mode: full
```
"""
    parserInstance = RoutePlanParser()
    parseOutcomeModel = parserInstance.parseAndValidateCatalog(
        in_rawText=yamlTextValue,
        in_knownSkillIds={"default_assistant"},
        in_registeredToolNames=set(),
    )
    assert parseOutcomeModel.isValid is True
    assert parseOutcomeModel.validatedPlan is not None
    assert parseOutcomeModel.validatedPlan.allow_tool_calls is False
