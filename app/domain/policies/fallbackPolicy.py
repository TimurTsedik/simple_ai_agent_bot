from dataclasses import dataclass

from app.config.settingsModels import ModelSettings


@dataclass(frozen=True)
class FallbackDecisionModel:
    modelOrder: list[str]


class FallbackPolicy:
    def __init__(self, in_modelSettings: ModelSettings) -> None:
        self._modelSettings = in_modelSettings

    def buildModelOrder(
        self,
        in_preferredModel: str,
        in_isPrimarySuppressed: bool,
    ) -> FallbackDecisionModel:
        ret: FallbackDecisionModel
        orderedModels: list[str]
        if in_isPrimarySuppressed is True:
            orderedModels = [
                self._modelSettings.secondaryModel,
                self._modelSettings.tertiaryModel,
                self._modelSettings.primaryModel,
            ]
        else:
            orderedModels = [
                in_preferredModel,
                self._modelSettings.secondaryModel,
                self._modelSettings.tertiaryModel,
            ]
        uniqueModels: list[str] = []
        for itemModel in orderedModels:
            if itemModel and itemModel not in uniqueModels:
                uniqueModels.append(itemModel)
        ret = FallbackDecisionModel(modelOrder=uniqueModels)
        return ret
