from typing import Protocol

from app.domain.entities.routingResolution import RoutingResolutionEntity


class RoutingPlanResolverProtocol(Protocol):
    def resolve(self, in_userMessage: str, *, in_runId: str = "") -> RoutingResolutionEntity:
        ...
