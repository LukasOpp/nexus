"""Nexus API server - unified personal data interface."""

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from nexus.models import MemoryEntry, NexusItem, SearchQuery, SearchResult
from nexus.sources.karakeep import KarakeepClient
from nexus.sources.miniflux import MinifluxClient
from nexus.memory_store import MemoryStore


class Nexus:
    """Unified interface to all data sources."""
    
    def __init__(
        self,
        karakeep_key: Optional[str] = None,
        karakeep_url: Optional[str] = None,
        miniflux_key: Optional[str] = None,
        miniflux_url: Optional[str] = None,
        memory_path: str = "./nexus_memory.db"
    ):
        self.karakeep = KarakeepClient(
            api_key=karakeep_key or os.getenv("KARAKEEP_API_KEY"),
            base_url=karakeep_url or os.getenv("KARAKEEP_BASE_URL", "https://api.karakeep.app")
        ) if karakeep_key or os.getenv("KARAKEEP_API_KEY") else None
        
        self.miniflux = MinifluxClient(
            api_key=miniflux_key or os.getenv("MINIFLUX_API_KEY"),
            base_url=miniflux_url or os.getenv("MINIFLUX_BASE_URL", "https://miniflux.app")
        ) if miniflux_key or os.getenv("MINIFLUX_API_KEY") else None
        
        self.memory = MemoryStore(db_path=memory_path)
    
    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Semantic search across all sources."""
        results = []
        
        if self.karakeep and "bookmark" in [s.value for s in query.sources]:
            bk_results = await self.karakeep.search(query.query, query.limit)
            for item, score in bk_results:
                results.append(SearchResult(
                    item=item,
                    similarity_score=score,
                    matched_on="embedding"
                ))
        
        if self.miniflux and "rss" in [s.value for s in query.sources]:
            rss_results = await self.miniflux.search(query.query, query.limit)
            for item, score in rss_results:
                results.append(SearchResult(
                    item=item,
                    similarity_score=score,
                    matched_on="content"
                ))
        
        # Local memory search
        if "memory" in [s.value for s in query.sources]:
            mem_results = self.memory.search(query.query, query.limit)
            for item, score in mem_results:
                results.append(SearchResult(
                    item=item,
                    similarity_score=score,
                    matched_on="embedding"
                ))
        
        # Sort by similarity
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        return results[:query.limit]
    
    async def get_recent(self, limit: int = 20) -> list[NexusItem]:
        """Recent items from all sources, merged."""
        items = []
        
        if self.karakeep:
            items.extend(await self.karakeep.get_recent(limit // 3))
        
        if self.miniflux:
            items.extend(await self.miniflux.get_recent(limit // 3))
        
        items.extend(self.memory.get_recent(limit // 3))
        
        # Sort by created_at descending
        items.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
        return items[:limit]
    
    def remember(self, entry: MemoryEntry) -> NexusItem:
        """Store something in memory."""
        item = NexusItem(
            id=str(uuid.uuid4()),
            source="memory",
            content=entry.content,
            tags=entry.tags,
            metadata=entry.metadata,
            created_at=datetime.now()
        )
        self.memory.store(item)
        return item


# Global nexus instance
nexus: Optional[Nexus] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage nexus lifecycle."""
    global nexus
    nexus = Nexus()
    yield
    nexus = None


app = FastAPI(title="Nexus", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
async def root():
    return {"name": "Nexus", "version": "0.1.0"}


@app.post("/search", response_model=list[SearchResult])
async def search(query: SearchQuery):
    if not nexus:
        raise HTTPException(500, "Nexus not initialized")
    return await nexus.search(query)


@app.get("/bookmarks", response_model=list[NexusItem])
async def bookmarks(
    tag: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    if not nexus or not nexus.karakeep:
        raise HTTPException(404, "Karakeep not configured")
    return await nexus.karakeep.get_by_tag(tag, limit) if tag else await nexus.karakeep.get_recent(limit)


@app.get("/unread", response_model=list[NexusItem])
async def unread(limit: int = Query(20, ge=1, le=100)):
    if not nexus or not nexus.miniflux:
        raise HTTPException(404, "Miniflux not configured")
    return await nexus.miniflux.get_unread(limit)


@app.get("/recent", response_model=list[NexusItem])
async def recent(limit: int = Query(20, ge=1, le=100)):
    if not nexus:
        raise HTTPException(500, "Nexus not initialized")
    return await nexus.get_recent(limit)


@app.post("/remember", response_model=NexusItem)
async def remember(entry: MemoryEntry):
    if not nexus:
        raise HTTPException(500, "Nexus not initialized")
    return nexus.remember(entry)
