import asyncio
import os
import hashlib
import httpx
import random
import time
import logging
import sys
from datetime import date, timedelta, datetime
from typing import Optional, Dict, Set

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout
)
logger = logging.getLogger("MagisterNinja")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass 

try:
    from MagisterPy import MagisterClient, MagisterAuth
except ImportError:
    logger.critical("MagisterPy not found. Run 'pip install .' first.")
    exit(1)

class MagisterMonitor:
    def __init__(self):
        self.school = os.getenv("SCHOOL")
        self.username = os.getenv("USERNAME")
        self.password = os.getenv("PASSWORD")
        self.webhook = os.getenv("DISCORD_WEBHOOK")
        self.token_file = os.getenv("TOKEN_FILE", "access_token.txt")
        self.state_file = os.path.join(os.path.dirname(self.token_file), "browser_state.json")

        self.base_interval = int(os.getenv("CHECK_INTERVAL", 300))
        self.jitter_range = (-30, 60)
        
        try:
            self.sleep_start = int(os.getenv("SLEEP_START", 1)) 
            self.sleep_end = int(os.getenv("SLEEP_END", 6))     
        except ValueError:
            self.sleep_start = 1
            self.sleep_end = 6

        self.seen_grade_ids: Set[int] = set()
        self.seen_message_ids: Set[int] = set()
        self.seen_assignment_ids: Set[int] = set() 
        
        self.schedule_cache: Dict[int, dict] = {} 
        self.schedule_date = None
        
        self.initialized = False
        self.last_heartbeat = 0

        if not all([self.school, self.username, self.password]):
            logger.critical("CONFIG ERROR: Missing credentials in .env file.")
            exit(1)
            
        if os.path.dirname(self.token_file):
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)

    async def _send_discord(self, text: str):
        if not self.webhook or "YOUR_WEBHOOK" in self.webhook:
            logger.info(f"[Mock Discord] {text}")
            return

        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "username": "Magister Ninja",
                    "avatar_url": "https://i.imgur.com/bM8k8s6.png",
                    "content": text
                }
                await client.post(self.webhook, json=payload)
            except Exception as e:
                logger.error(f"Failed to notify Discord: {e}")

    async def _refresh_session(self) -> Optional[str]:
        logger.info(f"Refreshing token for {self.username}...")
        try:
            auth = MagisterAuth(self.school, self.username, self.password, state_file=self.state_file)
            token = await auth.get_token()
            
            with open(self.token_file, "w") as f:
                f.write(token)
            logger.info("Session refreshed successfully.")
            return token
        except Exception as e:
            logger.critical(f"Login Failed: {e}")
            await self._send_discord(f"⚠️ **Bot Error**: Login failed. Check logs.")
            return None

    def _compute_hash(self, appt) -> str:
        info = getattr(appt, "info_type", 0)
        raw = f"{appt.id}|{appt.start}|{appt.end}|{appt.location}|{appt.description}|{info}|{appt.content}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _is_sleeping(self) -> bool:
        """Checks if current time is within the configured sleep window."""
        now = datetime.now().hour
        if self.sleep_start < self.sleep_end:
            return self.sleep_start <= now < self.sleep_end
        else:
            return now >= self.sleep_start or now < self.sleep_end

    async def _smart_sleep(self, duration: float):
        """
        Sleeps for `duration` seconds, but checks the sleep window every second.
        If the sleep window starts, it returns early so the main loop can handle it.
        """
        end_time = time.time() + duration
        while time.time() < end_time:
            if self._is_sleeping():
                return 
            await asyncio.sleep(1)

    async def check_updates(self):
        token = None
        if os.path.exists(self.token_file):
            with open(self.token_file, "r") as f:
                token = f.read().strip()
        
        if not token:
            token = await self._refresh_session()
            if not token: return

        try:
            async with MagisterClient(self.school, token) as m:
                
                grades = await m.get_grades(limit=10)
                new_grades = [g for g in grades if g.id not in self.seen_grade_ids]
                
                if new_grades and self.initialized:
                    for g in new_grades:
                        logger.info(f"New Grade: {g.subject.description} -> {g.value}")
                        await self._send_discord(f"📊 **New Grade**: {g.subject.description} - **{g.value}**")
                self.seen_grade_ids.update(g.id for g in grades)

                folders = await m.get_folders()
                inbox = next((f for f in folders if "Postvak IN" in f.name), None)
                if inbox:
                    msgs = await m.get_messages(inbox.id, limit=5)
                    new_msgs = [msg for msg in msgs if msg.id not in self.seen_message_ids]
                    if new_msgs and self.initialized:
                        for msg in new_msgs:
                            logger.info(f"New Mail: {msg.sender_name}")
                            await self._send_discord(f"📧 **Mail**: From {msg.sender_name}\nSubject: {msg.subject}")
                    self.seen_message_ids.update(msg.id for msg in msgs)

                assignments = await m.get_assignments(open_only=True)
                new_assignments = [a for a in assignments if a.id not in self.seen_assignment_ids]
                
                if new_assignments and self.initialized:
                    for a in new_assignments:
                        logger.info(f"New Assignment: {a.title}")
                        deadline_str = a.deadline.strftime('%d-%m %H:%M') if a.deadline else "No deadline"
                        await self._send_discord(f"📚 **New Assignment**: {a.title}\nDue: {deadline_str}")
                self.seen_assignment_ids.update(a.id for a in assignments)

                today = date.today()
                
                if self.schedule_date != today:
                    logger.info(f"Date changed to {today}. Resetting schedule cache.")
                    self.schedule_cache = {}
                    self.schedule_date = today
                    
                appts = await m.get_schedule(today, today + timedelta(days=1))
                
                current_map = {}
                for appt in appts:
                    current_map[appt.id] = {
                        "hash": self._compute_hash(appt),
                        "desc": appt.description,
                        "start": appt.start.strftime("%H:%M"),
                        "loc": appt.location or "?"
                    }

                if self.initialized:
                    previous_map = self.schedule_cache
                    current_ids = set(current_map.keys())
                    previous_ids = set(previous_map.keys())

                    for aid in (current_ids - previous_ids):
                        data = current_map[aid]
                        logger.info(f"Lesson Added: {data['desc']}")
                        await self._send_discord(f"📅 **New Lesson**: {data['desc']}\nTime: {data['start']} ({data['loc']})")

                    for rid in (previous_ids - current_ids):
                        old_data = previous_map[rid]
                        logger.info(f"Lesson Removed: {old_data['desc']}")
                        await self._send_discord(f"🗑️ **Lesson Cancelled/Removed**: {old_data['desc']}\nWas at: {old_data['start']}")

                    for cid in (current_ids & previous_ids):
                        if current_map[cid]["hash"] != previous_map[cid]["hash"]:
                            data = current_map[cid]
                            logger.info(f"Lesson Changed: {data['desc']}")
                            await self._send_discord(f"✏️ **Lesson Updated**: {data['desc']}\nTime: {data['start']} ({data['loc']})")

                self.schedule_cache = current_map

                if not self.initialized:
                    logger.info(f"Monitoring initialized. Tracking {len(current_map)} schedule items.")
                    self.initialized = True

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                logger.warning("Token expired (401/403). Triggering refresh...")
                await self._refresh_session()
            else:
                logger.error(f"HTTP Error {e.response.status_code}: {e}")
                
        except Exception as e:
            logger.exception(f"Unexpected error during check: {e}")

    async def run(self):
        logger.info("Magister Ninja started.")
        logger.info(f"Sleep schedule: {self.sleep_start}:00 - {self.sleep_end}:00")
        
        while True:
            if self._is_sleeping():
                if time.time() - self.last_heartbeat > 3600:
                    logger.info("Sleeping... zzz")
                    self.last_heartbeat = time.time()
                
                await asyncio.sleep(30)
                continue

            await self.check_updates()
            
            if time.time() - self.last_heartbeat > 3600:
                logger.info("Still running. No new changes.")
                self.last_heartbeat = time.time()

            jitter = random.uniform(*self.jitter_range)
            sleep_time = self.base_interval + jitter
            
            await self._smart_sleep(sleep_time)

if __name__ == "__main__":
    try:
        bot = MagisterMonitor()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Exiting via KeyboardInterrupt.")