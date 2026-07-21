"""
Rate Limiter & Anti-Flood Protection Module

Protects the bot from:
- Spam (rapid /start pressing)
- Flood attacks (mass button clicks)
- Resource exhaustion on free-tier hosting (Render/Vercel)

Uses in-memory tracking with automatic cleanup to prevent memory leaks.
"""

import time
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# --- Configuration ---
# Minimum seconds between /start commands per user
START_COOLDOWN_SECONDS = 5

# Minimum seconds between callback button presses per user
CALLBACK_COOLDOWN_SECONDS = 2

# Minimum seconds between any message per user
MESSAGE_COOLDOWN_SECONDS = 1

# If a user exceeds this many violations in VIOLATION_WINDOW, they get temp-banned
MAX_VIOLATIONS = 10
VIOLATION_WINDOW_SECONDS = 60

# Temporary ban duration (seconds) — user won't get any response
TEMP_BAN_SECONDS = 300  # 5 minutes

# Auto-cleanup: remove tracking data for users inactive longer than this
CLEANUP_INTERVAL_SECONDS = 600  # 10 minutes


class RateLimiter:
    """In-memory rate limiter with per-user cooldowns and auto-temp-ban."""

    def __init__(self):
        # user_id -> last action timestamp for each action type
        self._last_action: dict[int, dict[str, float]] = defaultdict(dict)
        # user_id -> list of violation timestamps
        self._violations: dict[int, list[float]] = defaultdict(list)
        # user_id -> temp-ban expiry timestamp
        self._temp_bans: dict[int, float] = {}
        # Last cleanup timestamp
        self._last_cleanup: float = time.time()

    def _cleanup_old_data(self):
        """Remove stale tracking data to prevent memory leaks."""
        now = time.time()
        if now - self._last_cleanup < CLEANUP_INTERVAL_SECONDS:
            return

        self._last_cleanup = now
        stale_threshold = now - CLEANUP_INTERVAL_SECONDS

        # Clean up last_action
        stale_users = []
        for user_id, actions in self._last_action.items():
            if all(ts < stale_threshold for ts in actions.values()):
                stale_users.append(user_id)
        for uid in stale_users:
            del self._last_action[uid]

        # Clean up violations
        stale_violations = []
        for user_id, viol_list in self._violations.items():
            # Remove old violation timestamps
            self._violations[user_id] = [
                t for t in viol_list if now - t < VIOLATION_WINDOW_SECONDS
            ]
            if not self._violations[user_id]:
                stale_violations.append(user_id)
        for uid in stale_violations:
            del self._violations[uid]

        # Clean up expired temp bans
        expired_bans = [
            uid for uid, expiry in self._temp_bans.items() if now >= expiry
        ]
        for uid in expired_bans:
            del self._temp_bans[uid]
            logger.info(f"Temp ban expired for user {uid}")

    def is_temp_banned(self, user_id: int) -> bool:
        """Check if a user is currently temp-banned."""
        if user_id in self._temp_bans:
            if time.time() < self._temp_bans[user_id]:
                return True
            else:
                # Ban expired, remove it
                del self._temp_bans[user_id]
                logger.info(f"Temp ban expired for user {user_id}")
        return False

    def _record_violation(self, user_id: int) -> bool:
        """
        Record a rate-limit violation. Returns True if user was temp-banned as a result.
        """
        now = time.time()

        # Clean old violations
        self._violations[user_id] = [
            t for t in self._violations[user_id]
            if now - t < VIOLATION_WINDOW_SECONDS
        ]

        self._violations[user_id].append(now)

        if len(self._violations[user_id]) >= MAX_VIOLATIONS:
            # Temp ban the user
            self._temp_bans[user_id] = now + TEMP_BAN_SECONDS
            self._violations[user_id].clear()
            logger.warning(
                f"User {user_id} temp-banned for {TEMP_BAN_SECONDS}s "
                f"(exceeded {MAX_VIOLATIONS} violations in {VIOLATION_WINDOW_SECONDS}s)"
            )
            return True

        return False

    def check_rate_limit(
        self,
        user_id: int,
        action: str = "message",
        cooldown: Optional[float] = None
    ) -> dict:
        """
        Check if a user's action should be allowed.

        Args:
            user_id: Telegram user ID
            action: Action type ("start", "callback", "message")
            cooldown: Override cooldown in seconds. If None, uses default for action type.

        Returns:
            {
                "allowed": bool,
                "retry_after": float (seconds until allowed, 0 if allowed),
                "temp_banned": bool,
                "reason": str
            }
        """
        self._cleanup_old_data()

        now = time.time()

        # 1. Check temp ban first
        if self.is_temp_banned(user_id):
            remaining = self._temp_bans[user_id] - now
            return {
                "allowed": False,
                "retry_after": remaining,
                "temp_banned": True,
                "reason": f"Vaqtincha bloklangansiz. {int(remaining)} soniyadan keyin qayta urinib ko'ring."
            }

        # 2. Determine cooldown
        if cooldown is None:
            cooldown_map = {
                "start": START_COOLDOWN_SECONDS,
                "callback": CALLBACK_COOLDOWN_SECONDS,
                "message": MESSAGE_COOLDOWN_SECONDS,
            }
            cooldown = cooldown_map.get(action, MESSAGE_COOLDOWN_SECONDS)

        # 3. Check cooldown
        last_ts = self._last_action[user_id].get(action, 0)
        elapsed = now - last_ts

        if elapsed < cooldown:
            retry_after = cooldown - elapsed
            was_banned = self._record_violation(user_id)

            if was_banned:
                remaining = self._temp_bans[user_id] - now
                return {
                    "allowed": False,
                    "retry_after": remaining,
                    "temp_banned": True,
                    "reason": f"⛔ Juda ko'p so'rov! {int(remaining)} soniya vaqtincha bloklangansiz."
                }

            return {
                "allowed": False,
                "retry_after": retry_after,
                "temp_banned": False,
                "reason": f"⏳ Iltimos, {int(retry_after) + 1} soniya kuting."
            }

        # 4. Allowed — update timestamp
        self._last_action[user_id][action] = now
        return {
            "allowed": True,
            "retry_after": 0,
            "temp_banned": False,
            "reason": ""
        }

    def get_stats(self) -> dict:
        """Get rate limiter statistics for admin panel."""
        now = time.time()
        active_bans = {
            uid: int(expiry - now)
            for uid, expiry in self._temp_bans.items()
            if expiry > now
        }
        return {
            "tracked_users": len(self._last_action),
            "active_violations": sum(
                len(v) for v in self._violations.values()
            ),
            "temp_banned_users": len(active_bans),
            "temp_bans": active_bans,
        }


# Global singleton instance
rate_limiter = RateLimiter()
