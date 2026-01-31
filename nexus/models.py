"""Pydantic models for Nexus data structures."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Source of the data item."""
    BOOKMARK = "bookmark"
    RSS = "rss"
    MEMORY = "memory"


class NexusItem(BaseModel):
    """Unified item from any source."""
    id: str
    source: SourceType
    title: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[list[float]] = None
    
    # Source-specific fields
    favicon_url: Optional[str] = None  # karakeep
    feed_title: Optional[str] = None   # miniflux
    author: Optional[str] = None       # either


class SearchQuery(BaseModel):
    """Semantic search request."""
    query: str
    sources: list[SourceType] = Field(default_factory=lambda: list(SourceType))
    limit: int = 10
    include_content: bool = False


class SearchResult(BaseModel):
    """Search result with relevance scores."""
    item: NexusItem
    similarity_score: float
    matched_on: str  # "title", "content", "tags", "embedding"


class MemoryEntry(BaseModel):
    """Store something in memory."""
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
