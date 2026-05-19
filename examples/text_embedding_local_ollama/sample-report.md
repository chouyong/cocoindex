# Local Ollama Query Report

- Generated At: `2026-05-17T19:37:04`
- Query: `vector search`
- Top K: `2`
- Indexed chunks searched: `4`
- Matching chunks after filter: `1`
- File filter: `vector`
- Ollama API Base: `http://127.0.0.1:11434`
- Embed Model: `ollama/nomic-embed-text`
- Embedding JSON Directory: `output_embeddings`

## Results

### 1. data\vector_search_demo.md

- Score: `0.7222`
- Chunk: `0..367`
- Embedding dim: `768`

#### Highlighted Preview

# **Vector** **Search** Demo  **Vector** **search** compares a query embedding with stored document embeddings and ranks the nearest matches.  This local demo stores **vector**s as JSON files and uses cosine similarity for retrieval without Postgres, Qdrant...

```text
# Vector Search Demo

Vector search compares a query embedding with stored document embeddings and ranks the nearest matches.

This local demo stores vectors as JSON files and uses cosine similarity for retrieval without Postgres, Qdrant, or any external vector service.

This file should rank for searches about vector search, cosine similarity, and local retrieval.
```
