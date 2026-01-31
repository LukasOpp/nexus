"""Local memory store with semantic search via embeddings."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb
import numpy as np
from sentence_transformers import SentenceTransformer

from nexus.models import NexusItem, SourceType


class MemoryStore:
    """Local memory with semantic search."""
    
    def __init__(self, db_path: str = "./nexus_memory.db", model_name: str = "all-MiniLM-L6-v2"):
        self.db_path = db_path
        self.con = duckdb.connect(db_path)
        
        # Lazy load model
        self._model: Optional[SentenceTransformer] = None
        self._model_name = model_name
        
        self._init_db()
    
    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model
    
    def _init_db(self):
        """Initialize database schema."""
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id VARCHAR PRIMARY KEY,
                source VARCHAR DEFAULT 'memory',
                title VARCHAR,
                url VARCHAR,
                content TEXT,
                summary VARCHAR,
                tags JSON,
                created_at TIMESTAMP,
                metadata JSON,
                embedding FLOAT8[384]
            )
        """)
    
    def _embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        vec = self.model.encode(text, convert_to_numpy=True)
        return vec.tolist()
    
    def store(self, item: NexusItem) -> NexusItem:
        """Store an item with its embedding."""
        # Generate embedding from content/title
        text_to_embed = item.content or item.title or item.summary or ""
        if not text_to_embed:
            return item
        
        embedding = self._embed(text_to_embed[:1000])  # Limit length
        
        self.con.execute("""
            INSERT OR REPLACE INTO memories
            (id, source, title, url, content, summary, tags, created_at, metadata, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            item.id or str(uuid.uuid4()),
            item.source.value,
            item.title,
            item.url,
            item.content,
            item.summary,
            json.dumps(item.tags),
            item.created_at or datetime.now(),
            json.dumps(item.metadata),
            embedding
        ])
        
        item.embedding = embedding
        return item
    
    def search(self, query: str, limit: int = 10) -> list[tuple[NexusItem, float]]:
        """Semantic search using cosine similarity."""
        query_vec = np.array(self._embed(query))
        
        # Get all memories with embeddings
        rows = self.con.execute("""
            SELECT id, source, title, url, content, summary, tags, created_at, metadata, embedding
            FROM memories
            WHERE embedding IS NOT NULL
        """).fetchall()
        
        results = []
        for row in rows:
            mem_vec = np.array(row[9])
            # Cosine similarity
            similarity = np.dot(query_vec, mem_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(mem_vec))
            
            item = NexusItem(
                id=row[0],
                source=SourceType(row[1]),
                title=row[2],
                url=row[3],
                content=row[4],
                summary=row[5],
                tags=json.loads(row[6]) if row[6] else [],
                created_at=row[7],
                metadata=json.loads(row[8]) if row[8] else {},
                embedding=row[9]
            )
            results.append((item, float(similarity)))
        
        # Sort by similarity and return top results
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def get_recent(self, limit: int = 20) -> list[NexusItem]:
        """Get recent memories."""
        rows = self.con.execute("""
            SELECT id, source, title, url, content, summary, tags, created_at, metadata
            FROM memories
            ORDER BY created_at DESC
            LIMIT ?
        """, [limit]).fetchall()
        
        return [
            NexusItem(
                id=row[0],
                source=SourceType(row[1]),
                title=row[2],
                url=row[3],
                content=row[4],
                summary=row[5],
                tags=json.loads(row[6]) if row[6] else [],
                created_at=row[7],
                metadata=json.loads(row[8]) if row[8] else {}
            )
            for row in rows
        ]
    
    def close(self):
        self.con.close()
