"""Miniflux RSS client."""

from datetime import datetime
from typing import Optional

import httpx

from nexus.models import NexusItem, SourceType


class MinifluxClient:
    """Client for Miniflux RSS API."""
    
    def __init__(self, api_key: str, base_url: str = "https://miniflux.app"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            headers={"X-Auth-Token": api_key},
            timeout=30.0
        )
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}/v1{endpoint}"
        resp = await self.client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()
    
    def _to_nexus(self, entry: dict) -> NexusItem:
        """Convert Miniflux entry to NexusItem."""
        return NexusItem(
            id=f"rss_{entry['id']}",
            source=SourceType.RSS,
            title=entry.get("title"),
            url=entry.get("url"),
            content=entry.get("content"),
            summary=entry.get("author") or entry.get("feed", {}).get("title"),
            tags=[entry.get("feed", {}).get("category", {}).get("title")] if entry.get("feed", {}).get("category") else [],
            created_at=datetime.fromisoformat(entry["published_at"].replace("Z", "+00:00")),
            metadata={
                "entry_id": entry["id"],
                "status": entry.get("status"),
                "starred": entry.get("starred", False)
            },
            feed_title=entry.get("feed", {}).get("title"),
            author=entry.get("author")
        )
    
    async def get_recent(self, limit: int = 20) -> list[NexusItem]:
        """Get recent entries."""
        entries = await self._request("GET", "/entries", params={"limit": limit})
        return [self._to_nexus(e) for e in entries.get("entries", [])]
    
    async def get_unread(self, limit: int = 20) -> list[NexusItem]:
        """Get unread entries."""
        entries = await self._request(
            "GET", "/entries",
            params={"limit": limit, "status": "unread"}
        )
        return [self._to_nexus(e) for e in entries.get("entries", [])]
    
    async def search(self, query: str, limit: int = 10) -> list[tuple[NexusItem, float]]:
        """Search entries."""
        entries = await self._request(
            "GET", "/entries",
            params={"limit": limit, "search": query}
        )
        return [
            (self._to_nexus(e), 1.0 - (i * 0.1))
            for i, e in enumerate(entries.get("entries", []))
        ]
    
    async def mark_read(self, entry_ids: list[int]):
        """Mark entries as read."""
        await self._request(
            "PUT", "/entries",
            json={"entry_ids": entry_ids, "status": "read"}
        )
    
    async def close(self):
        await self.client.aclose()
