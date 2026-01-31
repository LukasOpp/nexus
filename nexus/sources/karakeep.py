"""Karakeep bookmark client."""

from datetime import datetime
from typing import Optional

import httpx

from nexus.models import NexusItem, SourceType


class KarakeepClient:
    """Client for Karakeep bookmark API."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.karakeep.app"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0
        )
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{self.base_url}/api/v1{endpoint}"
        resp = await self.client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()
    
    def _to_nexus(self, bm: dict) -> NexusItem:
        """Convert Karakeep bookmark to NexusItem."""
        # Handle tags
        tags = bm.get("tags", [])
        if tags and isinstance(tags[0], dict):
            tags = [t["name"] for t in tags]
        
        return NexusItem(
            id=f"bk_{bm['id']}",
            source=SourceType.BOOKMARK,
            title=bm.get("title"),
            url=bm.get("url"),
            content=bm.get("content") or bm.get("description"),
            summary=bm.get("description"),
            tags=tags,
            created_at=datetime.fromisoformat(bm["createdAt"].replace("Z", "+00:00")),
            metadata={
                "archive_url": bm.get("archiveUrl"),
                "archived": bm.get("archived", False),
                "favourited": bm.get("favourited", False)
            },
            favicon_url=bm.get("faviconUrl")
        )
    
    async def get_recent(self, limit: int = 20) -> list[NexusItem]:
        """Get recent bookmarks."""
        data = await self._request("GET", "/bookmarks", params={"limit": limit})
        bookmarks = data.get("bookmarks", [])
        return [self._to_nexus(bm) for bm in bookmarks]
    
    async def get_by_tag(self, tag: str, limit: int = 20) -> list[NexusItem]:
        """Get bookmarks by tag."""
        # Search with tag filter
        data = await self._request(
            "GET", "/bookmarks",
            params={"limit": limit, "tag": tag}
        )
        bookmarks = data.get("bookmarks", [])
        return [self._to_nexus(bm) for bm in bookmarks]
    
    async def search(self, query: str, limit: int = 10) -> list[tuple[NexusItem, float]]:
        """Search bookmarks. Returns items with similarity scores."""
        # Karakeep has text search via the API
        data = await self._request(
            "GET", "/bookmarks",
            params={"limit": limit, "q": query}
        )
        bookmarks = data.get("bookmarks", [])
        return [
            (self._to_nexus(bm), 1.0 - (i * 0.1))  # Simple ranking
            for i, bm in enumerate(bookmarks)
        ]
    
    async def close(self):
        await self.client.aclose()
