from enum import StrEnum

class TriggerType(StrEnum):
    MENTION = "mention"
    DM = "dm"
    API = "api"

class PersonaType(StrEnum):
    GENERAL = "general"
    AUTOMATION = "automation" # For API triggers
    REVIEWER = "reviewer"     # Implicitly handled by tools, but good to have
