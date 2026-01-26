import httpx
from datetime import date
from typing import List
from .models import (
    Appointment, Grade, AccountInfo, 
    MessageFolder, Message, 
    StudyGuide, StudyGuideItem, Assignment
)

class MagisterClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token if token.startswith("Bearer ") else f"Bearer {token}"
        self.person_id = None
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url, 
            headers={
                "Authorization": self.token,
                "User-Agent": "MagisterPy/2.0",
                "Accept": "application/json"
            }
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def _get_me(self) -> int:
        if self.person_id: return self.person_id
        resp = await self.client.get("/api/account")
        resp.raise_for_status()
        self.person_id = AccountInfo(**resp.json()).person.id
        return self.person_id

    async def get_grades(self, limit: int = 25) -> List[Grade]:
        pid = await self._get_me()
        resp = await self.client.get(f"/api/personen/{pid}/cijfers/laatste", params={"top": limit, "skip": 0})
        resp.raise_for_status()
        return [Grade(**i) for i in resp.json().get("items", [])]

    async def get_schedule(self, start: date, end: date) -> List[Appointment]:
        pid = await self._get_me()
        params = {"van": start.isoformat(), "tot": end.isoformat()}
        resp = await self.client.get(f"/api/personen/{pid}/afspraken", params=params)
        resp.raise_for_status()
        return [Appointment(**i) for i in resp.json().get("Items", [])]

    async def get_folders(self) -> List[MessageFolder]:
        resp = await self.client.get("/api/berichten/mappen")
        resp.raise_for_status()
        return [MessageFolder(**i) for i in resp.json()["items"]]

    async def get_messages(self, folder_id: int, limit: int = 10) -> List[Message]:
        resp = await self.client.get(f"/api/berichten/mappen/{folder_id}/berichten", params={"top": limit, "skip": 0})
        resp.raise_for_status()
        return [Message(**i) for i in resp.json()["items"]]

    async def send_mail(self, recipient_id: int, subject: str, body: str) -> bool:
        payload = {
            "onderwerp": subject,
            "inhoud": body,
            "ontvangers": [
                {"id": recipient_id, "type": "persoon"} 
            ],
            "prioriteit": 0,
            "bevestigingGevraagd": False
        }
        
        resp = await self.client.post("/api/berichten", json=payload)
        
        if resp.status_code in [200, 201, 204]:
            return True
        return False

    async def get_study_guides(self) -> List[StudyGuide]:
        pid = await self._get_me()
        resp = await self.client.get(f"/api/leerlingen/{pid}/studiewijzers")
        resp.raise_for_status()
        return [StudyGuide(**i) for i in resp.json()["Items"]]

    async def get_study_guide_items(self, guide_id: int) -> List[StudyGuideItem]:
        pid = await self._get_me()
        resp = await self.client.get(f"/api/leerlingen/{pid}/studiewijzers/{guide_id}/onderdelen")
        
        if resp.status_code in [204, 404]:
            return []
            
        resp.raise_for_status()
        
        try:
            data = resp.json()
        except:
            return []

        return [StudyGuideItem(**i) for i in data.get("Items", [])]

    async def get_assignments(self, open_only: bool = False) -> List[Assignment]:
        pid = await self._get_me()
        resp = await self.client.get(f"/api/personen/{pid}/opdrachten", params={"top": 50, "skip": 0})
        resp.raise_for_status()
        
        all_assignments = [Assignment(**i) for i in resp.json()["Items"]]
        
        if open_only:
            return [a for a in all_assignments if a.is_open]
            
        return all_assignments