"""
In-memory SSE queue registry for session supersession notifications.

Stores asyncio Queues per provider_id. On login, the login endpoint:
  1. Calls notify_event(id, "flush")   -- Device A saves its draft (token still valid)
  2. Waits 1.5 s                       -- grace period for the save round-trip
  3. Increments session_version + commits
  4. Calls notify_event(id, "superseded") -- Device A shows the overlay / redirects

Single-process only. If this app ever runs multi-process, replace with Redis pub/sub.
"""
import asyncio
from collections import defaultdict
from typing import Dict, List

_session_queues: Dict[int, List[asyncio.Queue]] = defaultdict(list)


def has_connections(provider_id: int) -> bool:
    """Return True if there are open SSE connections for this provider."""
    return bool(_session_queues.get(provider_id))


async def notify_event(provider_id: int, event: str) -> None:
    """Push an event string to every open SSE connection for this provider."""
    for q in list(_session_queues.get(provider_id, [])):
        await q.put(event)


def register_queue(provider_id: int) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _session_queues[provider_id].append(q)
    return q


def unregister_queue(provider_id: int, q: asyncio.Queue) -> None:
    try:
        _session_queues[provider_id].remove(q)
    except ValueError:
        pass
