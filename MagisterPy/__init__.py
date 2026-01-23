from .client import MagisterClient
from .models import (
    Person, AccountInfo, Grade, Appointment, 
    Message, MessageFolder, Assignment, StudyGuide
)

__version__ = "2.0.0"
__all__ = [
    "MagisterClient",
    "Person", "AccountInfo", 
    "Grade", "Appointment", 
    "Message", "MessageFolder", 
    "Assignment", "StudyGuide"
]