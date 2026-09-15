from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class CapabilitySupport(str, Enum):
    """Gateway knowledge level for a provider capability."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Conservative capabilities known by the gateway for one provider."""

    text: CapabilitySupport = CapabilitySupport.SUPPORTED
    html: CapabilitySupport = CapabilitySupport.UNKNOWN
    auto_source: CapabilitySupport = CapabilitySupport.UNKNOWN

    def as_dict(self) -> dict[str, str]:
        return {
            "text": self.text.value,
            "html": self.html.value,
            "auto_source": self.auto_source.value,
        }


# The upstream pool itself is the source of truth for provider discovery. We only
# record capabilities that the gateway can establish without probing a live service.
_DEFAULT_CAPABILITIES = ProviderCapabilities()


def capabilities_for(translators: Iterable[str]) -> dict[str, dict[str, str]]:
    return {name: _DEFAULT_CAPABILITIES.as_dict() for name in sorted(set(translators))}


def supports(capabilities: ProviderCapabilities, capability: str) -> bool:
    return getattr(capabilities, capability) is CapabilitySupport.SUPPORTED
