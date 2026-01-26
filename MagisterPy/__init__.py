from .client import MagisterClient
from .auth import MagisterAuth
from .models import (
    Person, AccountInfo, Grade, Appointment, 
    Message, MessageFolder, Assignment, StudyGuide
)

__version__ = "0.1.0" 
__all__ = [
    "MagisterClient",
    "Person", "AccountInfo", 
    "Grade", "Appointment", 
    "Message", "MessageFolder", 
    "Assignment", "StudyGuide"
]