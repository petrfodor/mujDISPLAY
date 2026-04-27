# media_provider.py
"""Informace o přehrávaných médiích."""

import asyncio
import datetime
import logging
import threading
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
import pyautogui
import i18n                       # <-- import modulu
from app_state import AppState

logger = logging.getLogger(__name__)

class MediaProvider:
    def __init__(self, state: AppState):
        self.state = state
        self._info = {"text": i18n._("media_nothing"), "progress": 0,
                      "time_str": "--:-- / --:--", "remaining": "--:--", "status_pic": 19}
        self._lock = threading.Lock()

    @property
    def current_info(self):
        with self._lock:
            return self._info.copy()

    async def _update_loop(self):
        while self.state.running:
            try:
                sessions = await MediaManager.request_async()
                current = sessions.get_current_session()
                if current is None:
                    self._update_fallback()
                    await asyncio.sleep(1)
                    continue

                playback = current.get_playback_info()
                status = playback.playback_status
                status_pic = 19
                if status == 4: status_pic = 17
                elif status == 5: status_pic = 18

                props = await current.try_get_media_properties_async()
                raw = f"{props.artist} - {props.title}" if props.artist else props.title
                import unicodedata
                title = "".join(c for c in unicodedata.normalize('NFD', raw)
                                if unicodedata.category(c) != 'Mn')[:49]

                timeline = current.get_timeline_properties()
                if not timeline or timeline.end_time.total_seconds() <= 0:
                    self._update_simple(title, status_pic)
                else:
                    pos = timeline.position.total_seconds()
                    end = timeline.end_time.total_seconds()
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    delta = (now_utc - timeline.last_updated_time).total_seconds() if timeline.last_updated_time else 0
                    if status == 4 and delta > 0:
                        pos += delta
                    if pos > end: pos = end
                    rem = end - pos
                    progress = int((pos / end) * 100)
                    def fmt(s): m, s = divmod(int(s), 60); return f"{m:02d}:{s:02d}"
                    with self._lock:
                        self._info = {
                            "text": title, "progress": progress,
                            "time_str": f"{fmt(pos)} / {fmt(end)}",
                            "remaining": f"-{fmt(rem)}", "status_pic": status_pic
                        }
            except Exception as e:
                logger.error(f"Media error: {e}")
                self._update_fallback()
            await asyncio.sleep(1)

    def _update_fallback(self):
        with self._lock:
            self._info = {"text": i18n._("media_nothing"), "progress": 0,
                          "time_str": "--:-- / --:--", "remaining": "--:--", "status_pic": 19}

    def _update_simple(self, title, pic):
        with self._lock:
            self._info = {"text": title, "progress": 0,
                          "time_str": "00:00 / 00:00", "remaining": "00:00", "status_pic": pic}

    def send_action(self, action: str):
        mapping = {
            "play": "playpause", "stop": "stop", "prev": "prevtrack",
            "next": "nexttrack", "vup": "volumeup", "vdown": "volumedown"
        }
        key = mapping.get(action)
        if key:
            pyautogui.press(key)

    def start(self):
        async def runner(): await self._update_loop()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner())
