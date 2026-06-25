from enum import StrEnum


class TOPICS(StrEnum):
    RAW_DOCUMENTS = "raw.documents"
    RAW_LOGS = "raw.logs"
    STREAM_IOT = "stream.iot"
    DERIVED_ENTITIES = "derived.entities"
    MEMORY_OBSERVATIONS = "memory.observations"
    AUDIT_ACTIONS = "audit.actions"
