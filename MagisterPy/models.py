from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Person(BaseModel):
    id: int = Field(alias="Id")
    first_name: str = Field(alias="Roepnaam")
    last_name: str = Field(alias="Achternaam")
    class Config:
        populate_by_name = True

class AccountInfo(BaseModel):
    person: Person = Field(alias="Persoon")

class Subject(BaseModel):
    code: str = Field(alias="code")
    description: str = Field(alias="omschrijving")

class Grade(BaseModel):
    id: int = Field(alias="kolomId")
    description: str = Field(alias="omschrijving")
    date_input: datetime = Field(alias="ingevoerdOp")
    subject: Subject = Field(alias="vak")
    value: str = Field(alias="waarde") 
    is_sufficient: bool = Field(alias="isVoldoende")

    @property
    def is_pass(self) -> bool:
        return self.is_sufficient

class Appointment(BaseModel):
    id: int = Field(alias="Id")
    start: datetime = Field(alias="Start")
    end: datetime = Field(alias="Einde")
    description: Optional[str] = Field(default=None, alias="Omschrijving")
    location: Optional[str] = Field(default=None, alias="Lokatie")
    content: Optional[str] = Field(default=None, alias="Inhoud")
    completed: bool = Field(alias="Afgerond")

    @property
    def has_homework(self) -> bool:
        return bool(self.content)

class MessageFolder(BaseModel):
    id: int = Field(alias="id")
    name: str = Field(alias="naam")
    unread_count: int = Field(default=0, alias="aantalOngelezen")

class Message(BaseModel):
    id: int = Field(alias="id")
    subject: str = Field(alias="onderwerp")
    sent_at: datetime = Field(alias="verzondenOp")
    is_read: bool = Field(alias="isGelezen")
    sender: dict = Field(alias="afzender") 

    @property
    def sender_name(self) -> str:
        return self.sender.get("naam", "Unknown")

class StudyGuide(BaseModel):
    id: int = Field(alias="Id")
    title: str = Field(alias="Titel")

class StudyGuideItem(BaseModel):
    id: int = Field(alias="Id")
    title: str = Field(alias="Titel")
    resource_type: Optional[str] = Field(default="Unknown", alias="OnderdeelType") 
    links: List[dict] = Field(default_factory=list, alias="Links")

    @property
    def url(self) -> Optional[str]:
        for link in self.links:
            if link.get("Rel") == "Content":
                return link.get("Href")
        return None

class Assignment(BaseModel):
    id: int = Field(alias="Id")
    title: str = Field(alias="Titel")
    deadline: datetime = Field(alias="InleverenVoor")
    closed: bool = Field(alias="Afgesloten")
    graded: bool = Field(default=False, alias="Beoordeeld")
    status: Optional[int] = Field(default=None, alias="Status")

    @property
    def is_open(self) -> bool:
        if self.status is not None:
            return self.status < 3
        return not self.closed