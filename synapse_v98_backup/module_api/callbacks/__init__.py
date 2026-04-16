from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.server import HomeServer

from synapse.module_api.callbacks.account_validity_callbacks import (
    AccountValidityModuleApiCallbacks,
)
from synapse.module_api.callbacks.spamchecker_callbacks import (
    SpamCheckerModuleApiCallbacks,
)
from synapse.module_api.callbacks.third_party_event_rules_callbacks import (
    ThirdPartyEventRulesModuleApiCallbacks,
)


class ModuleApiCallbacks:
    def __init__(self, hs: "HomeServer") -> None:
        self.account_validity = AccountValidityModuleApiCallbacks()
        self.spam_checker = SpamCheckerModuleApiCallbacks(hs)
        self.third_party_event_rules = ThirdPartyEventRulesModuleApiCallbacks(hs)
