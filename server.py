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
        self.assignment_24h_notified: Set[int] = set()  
        self.assignment_1h_notified: Set[int] = set()   
        
        self.schedule_cache: Dict[int, dict] = {} 
        self.schedule_date = None
        
        self.initialized = False
        self.last_heartbeat = 0
        self.last_check_time = 0  
        
        
        self.MAX_CHANGES_THRESHOLD = 5  
        self.SLEEP_GAP_THRESHOLD = 3600  

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
        """Create a unique fingerprint for an appointment."""
        info = getattr(appt, "info_type", 0)
        
        start_str = appt.start.strftime("%Y-%m-%d %H:%M")
        raw = f"{appt.id}|{start_str}|{appt.end}|{appt.location}|{appt.description}|{info}|{appt.content}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _is_sleeping(self) -> bool:
        now = datetime.now().hour
        if self.sleep_start < self.sleep_end:
            return self.sleep_start <= now < self.sleep_end
        else:
            return now >= self.sleep_start or now < self.sleep_end

    async def _smart_sleep(self, duration: float):
        end_time = time.time() + duration
        while time.time() < end_time:
            if self._is_sleeping():
                return 
            await asyncio.sleep(1)

    async def _fetch_schedule_safe(self, client: MagisterClient, day: date) -> Optional[Dict[int, dict]]:
        """
        Fetches schedule and formats it into a dictionary. 
        Returns None if the fetch fails (so we don't crash the main loop).
        """
        try:
            appts = await client.get_schedule(day, day + timedelta(days=1))
            current_map = {}
            for appt in appts:
                
                if appt.start.date() == day:
                    current_map[appt.id] = {
                        "hash": self._compute_hash(appt),
                        "desc": appt.description,
                        "start": appt.start.strftime("%H:%M"),
                        "loc": appt.location or "?"
                    }
            return current_map
        except Exception as e:
            logger.error(f"Failed to fetch schedule: {e}")
            return None

    def _extract_assignment_info(self, assignment) -> tuple:
        """
    def _extract_assignment_info(self, assignment) -> tuple:
        """
        Extract title and subject from assignment object.
        Returns (title, subject_str).
        """
        title = getattr(assignment, 'title', 'Unknown')
        subject = getattr(assignment, 'subject', None)
        subject_str = f"{subject.description}" if subject and hasattr(subject, 'description') else "Unknown Subject"
        return title, subject_str

    async def _check_assignment_deadlines(self, client: MagisterClient):
        """
        Check for upcoming assignment deadlines and send notifications.
        Sends at 24 hours and 1 hour before deadline.
        """
        try:
            assignments = await client.get_assignments()
            now = datetime.now()

            for assignment in assignments:
                
                if not hasattr(assignment, 'deadline'):
                    continue
                    
                deadline = assignment.deadline
                if isinstance(deadline, date) and not isinstance(deadline, datetime):
                    
                    deadline = datetime.combine(deadline, datetime.max.time())
                elif not isinstance(deadline, datetime):
                    continue  

                time_until_deadline = deadline - now
                hours_remaining = time_until_deadline.total_seconds() / 3600
                
                title, subject_str = self._extract_assignment_info(assignment)
                deadline_str = deadline.strftime('%Y-%m-%d %H:%M')

                
                if 23 < hours_remaining <= 24 and assignment.id not in self.assignment_24h_notified:
                    self.assignment_24h_notified.add(assignment.id)
                    logger.info(f"Assignment 24h Warning: {title}")
                    await self._send_discord(
                        f"⏰ **Assignment Due in 24 Hours**\n"
                        f"Title: {title}\n"
                        f"Subject: {subject_str}\n"
                        f"Deadline: {deadline_str}"
                    )

                
                elif 0.5 < hours_remaining <= 1 and assignment.id not in self.assignment_1h_notified:
                    self.assignment_1h_notified.add(assignment.id)
                    logger.info(f"Assignment 1h Warning: {title}")
                    await self._send_discord(
                        f"🚨 **Assignment Due in 1 Hour**\n"
                        f"Title: {title}\n"
                        f"Subject: {subject_str}\n"
                        f"Deadline: {deadline_str}"
                    )

                
                elif hours_remaining < 0:
                    self.assignment_24h_notified.discard(assignment.id)
                    self.assignment_1h_notified.discard(assignment.id)

        except Exception as e:
            logger.error(f"Failed to check assignment deadlines: {e}")

    async def check_updates(self):
        
        current_time = time.time()
        time_since_last_check = current_time - self.last_check_time
        is_post_sleep = (self.initialized and time_since_last_check > self.SLEEP_GAP_THRESHOLD)
        
        if is_post_sleep:
            logger.warning(f"⏰ FALLBACK 1: Large time gap detected ({time_since_last_check:.0f}s). Treating as potential day rollover.")
        
        token = None
        if os.path.exists(self.token_file):
            with open(self.token_file, "r") as f:
                token = f.read().strip()
        
        if not token:
            token = await self._refresh_session()
            if not token: return

        try:
            async with MagisterClient(self.school, token) as m:
                
                
                
                try:
                    grades = await m.get_grades(limit=10)
                    new_grades = [g for g in grades if g.id not in self.seen_grade_ids]
                    if new_grades and self.initialized:
                        for g in new_grades:
                            await self._send_discord(f"📊 **New Grade**: {g.subject.description} - **{g.value}**")
                    self.seen_grade_ids.update(g.id for g in grades)
                except Exception as e: logger.error(f"Error checking grades: {e}")

                
                await self._check_assignment_deadlines(m)

                
                today = date.today()
                
                
                
                is_new_day = (self.schedule_date != today)
                if is_new_day:
                    logger.info(f"📅 Date changed: {self.schedule_date} -> {today}. Resetting cache silently.")
                    
                    self.schedule_cache = {}

                
                current_map = await self._fetch_schedule_safe(m, today)
                if current_map is None: return 

                
                
                
                if self.initialized and not is_new_day:
                    current_ids = set(current_map.keys())
                    previous_ids = set(self.schedule_cache.keys())
                    
                    
                    added = len(current_ids - previous_ids)
                    removed = len(previous_ids - current_ids)
                    
                    if added > 0 or removed > 0:
                        logger.info(f"Changes detected (+{added}/-{removed}). Verifying stability...")
                        await asyncio.sleep(5) 
                        
                        
                        verify_map = await self._fetch_schedule_safe(m, today)
                        if verify_map is None: 
                            logger.warning("Verification fetch failed. Aborting update.")
                            return
                        
                        
                        
                        if set(verify_map.keys()) != set(current_map.keys()):
                            logger.warning("🛡️ STARK PROTOCOL: Data is unstable (flapping). Ignoring update.")
                            return
                        
                        current_map = verify_map 

                
                
                
                
                if self.initialized and not is_new_day and self.schedule_cache and not current_map:
                    logger.warning("🛡️ STARK PROTOCOL: API returned 0 items. Keeping old cache.")
                    return

                
                
                if self.initialized and not is_new_day:
                    current_ids = set(current_map.keys())
                    previous_ids = set(self.schedule_cache.keys())
                    
                    total_changes = len(current_ids - previous_ids) + len(previous_ids - current_ids)

                    if total_changes > self.MAX_CHANGES_THRESHOLD:
                        logger.warning(f"🛡️ STARK PROTOCOL: Massive change detected ({total_changes} items). Spam protection active.")
                        
                        self.schedule_cache = current_map
                        return

                
                
                
                if self.initialized and not is_new_day and not is_post_sleep:
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
                    logger.info(f"Initialized. Tracking {len(current_map)} items.")
                    self.initialized = True
                    self.schedule_date = today
                elif is_new_day:
                    logger.info("Daily rollover complete. Cache reset.")
                    self.schedule_date = today

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                logger.warning("Token expired. Refreshing...")
                await self._refresh_session()
            else:
                logger.error(f"HTTP Error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
        finally:
            
            self.last_check_time = current_time

    async def run(self):
        logger.info("Magister Ninja started.")
        
        while True:
            if self._is_sleeping():
                if time.time() - self.last_heartbeat > 3600:
                    logger.info("Sleeping... zzz")
                    self.last_heartbeat = time.time()
                await asyncio.sleep(30)
                continue

            await self.check_updates()
            self.last_heartbeat = time.time()

            jitter = random.uniform(*self.jitter_range)
            await self._smart_sleep(self.base_interval + jitter)

if __name__ == "__main__":
    try:
        bot = MagisterMonitor()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Exiting...")