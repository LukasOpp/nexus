# Nexus

Unified personal data API for your digital life. Aggregates:
- **Karakeep** (bookmarks)
- **Miniflux** (RSS feeds)
- **Memory** (semantic embeddings)

## API Endpoints

- `POST /search` - Semantic search across all sources
- `GET /unread` - Unread RSS entries
- `GET /bookmarks` - Bookmarks with tag filters
- `GET /recent` - Recent activity across sources
- `POST /remember` - Store something to memory

## Setup

```bash
pip install -r requirements.txt
python -m nexus
```

## Configuration

Set via environment:
- `KARAKEEP_API_KEY`
- `KARAKEEP_BASE_URL`  
- `MINIFLUX_API_KEY`
- `MINIFLUX_BASE_URL`
- `MEMORY_DB_PATH`
