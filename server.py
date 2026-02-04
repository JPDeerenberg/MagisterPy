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

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout
)
logger = logging.getLogger("MagisterNinja")

# --- ENVIRONMENT VARIABLES ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass 

# --- IMPORT MAGISTERPY ---
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
        
        # Parse Sleep Schedule
        try:
            self.sleep_start = int(os.getenv("SLEEP_START", 1)) 
            self.sleep_end = int(os.getenv("SLEEP_END", 6))     
        except ValueError:
            self.sleep_start = 1
            self.sleep_end = 6

        # Tracking State
        self.seen_grade_ids: Set[int] = set()
        self.seen_message_ids: Set[int] = set()
        self.seen_assignment_ids: Set[int] = set() 
        
        self.schedule_cache: Dict[int, dict] = {} 
        self.schedule_date = None
        
        self.initialized = False
        self.last_heartbeat = 0
        
        # --- CONFIGURATION GUARDS ---
        self.MAX_CHANGES_THRESHOLD = 5  # If >5 changes happen at once, assume glitch and ignore.

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
        # We include ID, Start, End, Location, Description, InfoType, Content
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
                # Double check the date to ensure API didn't return next day's items by mistake
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
                
                # --- GRADES, MAIL, ASSIGNMENTS (Standard Logic) ---
                # (Keeping this concise as the focus is the schedule)
                try:
                    grades = await m.get_grades(limit=10)
                    new_grades = [g for g in grades if g.id not in self.seen_grade_ids]
                    if new_grades and self.initialized:
                        for g in new_grades:
                            await self._send_discord(f"📊 **New Grade**: {g.subject.description} - **{g.value}**")
                    self.seen_grade_ids.update(g.id for g in grades)
                except Exception as e: logger.error(f"Error checking grades: {e}")

                # --- SCHEDULE LOGIC (THE STARK PROTOCOL) ---
                today = date.today()
                
                # Check 1: Is this a new day?
                # If yes, we mark it, but we wait until we successfully fetch data to "commit" the new day.
                is_new_day = (self.schedule_date != today)
                if is_new_day:
                    logger.info(f"📅 Date changed: {self.schedule_date} -> {today}. Resetting cache silently.")

                # FETCH 1: Primary Fetch
                current_map = await self._fetch_schedule_safe(m, today)
                if current_map is None: return # Network error, skip

                # FALLBACK: Double-Tap Verification
                # If we detect changes, we wait 5 seconds and fetch AGAIN to ensure it wasn't a glitch.
                # We skip this check on the very first run or if it's a new day (since everything is 'new' then).
                if self.initialized and not is_new_day:
                    current_ids = set(current_map.keys())
                    previous_ids = set(self.schedule_cache.keys())
                    
                    # Calculate potential changes
                    added = len(current_ids - previous_ids)
                    removed = len(previous_ids - current_ids)
                    
                    if added > 0 or removed > 0:
                        logger.info(f"Changes detected (+{added}/-{removed}). Verifying stability...")
                        await asyncio.sleep(5) # Wait for API to settle
                        
                        # FETCH 2: Verification Fetch
                        verify_map = await self._fetch_schedule_safe(m, today)
                        if verify_map is None: 
                            logger.warning("Verification fetch failed. Aborting update.")
                            return
                        
                        # Compare Hash of Maps to ensure they are identical
                        # (Simplest way: are the keys the same?)
                        if set(verify_map.keys()) != set(current_map.keys()):
                            logger.warning("🛡️ STARK PROTOCOL: Data is unstable (flapping). Ignoring update.")
                            return
                        
                        current_map = verify_map # Data is confirmed stable

                # --- SANITY CHECKS ---
                
                # 1. The "Empty Response" Glitch
                # If cache has data, but API returns EMPTY, it's 99% a bug.
                if self.initialized and not is_new_day and self.schedule_cache and not current_map:
                    logger.warning("🛡️ STARK PROTOCOL: API returned 0 items. Keeping old cache.")
                    return

                # 2. The "Nuke" Guard (Max Changes)
                # If too many items change at once, suppress notifications.
                if self.initialized and not is_new_day:
                    previous_ids = set(self.schedule_cache.keys())
                    current_ids = set(current_map.keys())
                    
                    added_count = len(current_ids - previous_ids)
                    removed_count = len(previous_ids - current_ids)
                    total_changes = added_count + removed_count

                    if total_changes > self.MAX_CHANGES_THRESHOLD:
                        logger.warning(f"🛡️ STARK PROTOCOL: Massive change detected ({total_changes} items). Spam protection active.")
                        # We update the cache so the NEXT check is accurate, but we send NO Discord alerts.
                        self.schedule_cache = current_map
                        return

                # --- NOTIFICATIONS ---
                # Only notify if initialized AND it is NOT a new day rollover.
                if self.initialized and not is_new_day:
                    previous_map = self.schedule_cache
                    current_ids = set(current_map.keys())
                    previous_ids = set(previous_map.keys())

                    # Added
                    for aid in (current_ids - previous_ids):
                        data = current_map[aid]
                        logger.info(f"Lesson Added: {data['desc']}")
                        await self._send_discord(f"📅 **New Lesson**: {data['desc']}\nTime: {data['start']} ({data['loc']})")

                    # Removed
                    for rid in (previous_ids - current_ids):
                        old_data = previous_map[rid]
                        logger.info(f"Lesson Removed: {old_data['desc']}")
                        await self._send_discord(f"🗑️ **Lesson Cancelled/Removed**: {old_data['desc']}\nWas at: {old_data['start']}")

                    # Changed
                    for cid in (current_ids & previous_ids):
                        if current_map[cid]["hash"] != previous_map[cid]["hash"]:
                            data = current_map[cid]
                            logger.info(f"Lesson Changed: {data['desc']}")
                            await self._send_discord(f"✏️ **Lesson Updated**: {data['desc']}\nTime: {data['start']} ({data['loc']})")

                # --- COMMIT STATE ---
                self.schedule_cache = current_map
                
                # Handle Initialization / Rollover
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