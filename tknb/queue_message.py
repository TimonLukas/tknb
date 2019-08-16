from enum import Enum
from typing import Tuple, Any


class MessageType(Enum):
    METHOD_CALL = 0
    CUSTOM_EVENT = 1


QueueMessage = Tuple[MessageType, str, Any]
