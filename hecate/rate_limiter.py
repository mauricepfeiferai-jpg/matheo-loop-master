#!/usr/bin/env python3
"""Rate Limiter — Token Bucket für Agent-Team + Telegram.

Schließt Lücke #11: Kein Rate-Limiting.
"""
import time
from dataclasses import dataclass, field

@dataclass
class TokenBucket:
    capacity: int
    tokens: float = field(init=False)
    last_update: float = field(init=False)
    refill_rate: float = 1.0  # tokens pro Sekunde

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_update = time.time()

    def _refill(self):
        now = time.time()
        delta = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + delta * self.refill_rate)
        self.last_update = now

    def consume(self, tokens: int = 1) -> bool:
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_time(self, tokens: int = 1) -> float:
        self._refill()
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.refill_rate

# Globale Buckets
AGENT_BUCKET = TokenBucket(capacity=3, refill_rate=0.05)   # 3 Jobs / 60s
TELEGRAM_BUCKET = TokenBucket(capacity=5, refill_rate=0.1) # 5 Msg / 50s

def can_run_agent() -> bool:
    return AGENT_BUCKET.consume(1)

def can_send_telegram() -> bool:
    return TELEGRAM_BUCKET.consume(1)

def agent_wait() -> float:
    return AGENT_BUCKET.wait_time(1)

def telegram_wait() -> float:
    return TELEGRAM_BUCKET.wait_time(1)
