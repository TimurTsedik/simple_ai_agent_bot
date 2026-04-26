from app.tools.registry.toolRegistry import ToolRegistry


class ToolMetadataRenderer:
    def renderForPrompt(self, in_toolRegistry: ToolRegistry) -> str:
        ret: str
        renderedBlocks: list[str] = []
        for toolDefinition in in_toolRegistry.listTools():
            schema = toolDefinition.argsModel.model_json_schema()
            renderedBlocks.append(
                "\n".join(
                    [
                        f"Tool: {toolDefinition.name}",
                        f"Description: {toolDefinition.description}",
                        f"Args JSON schema: {schema}",
                    ]
                )
            )
        ret = "\n\n".join(renderedBlocks)
        return ret
