"""Exception types which are exposed as part of the stable module API"""

from synapse.api.errors import (
    Codes,
    InvalidClientCredentialsError,
    RedirectException,
    SynapseError,
)
from synapse.config._base import ConfigError
from synapse.handlers.push_rules import InvalidRuleException
from synapse.storage.push_rule import RuleNotFoundException

__all__ = [
    "Codes",
    "InvalidClientCredentialsError",
    "RedirectException",
    "SynapseError",
    "ConfigError",
    "InvalidRuleException",
    "RuleNotFoundException",
]
