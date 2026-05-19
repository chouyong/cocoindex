# Text Embedding with Local Ollama

This example is the local-first demo entry for `cocoindex`.

It shows one complete path:

1. read local Markdown files
2. embed chunks through local `Ollama`
3. write embeddings as local JSON files
4. run local cosine-similarity search over those JSON files
5. inspect results from terminal, Markdown report, static HTML report, or a small local Web UI

This example stays intentionally smaller than the Postgres, Qdrant, or cloud-provider demos:

- no Postgres
- no Qdrant
- no external API key
- no remote vector service

## Current Capabilities

This example currently supports:

- multiple Markdown files under `data\`
- local `Ollama` embeddings through `LiteLLMEmbedder`
- local JSON embedding output under `output_embeddings\`
- local cosine-similarity query
- configurable `Top K`
- filename substring filter
- interactive multi-turn terminal query loop
- Markdown report export
- static HTML report export
- lexical highlight previews
- small local Web UI
- Web UI file-filter suggestions from indexed files
- Web UI direct download buttons for Markdown and HTML
- Web UI clickable file tags
- Web UI active filter highlight state
- Web UI one-click clear filter
- Web UI filtered-result-count badge
- Web UI "compare with all results" baseline view

## Recommended Sample Outputs

If you just want to inspect the final demo artifacts directly, start here:

- Markdown sample report: `sample-report.md`
- HTML sample report: `sample-report.html`

These two files are the cleaned, canonical sample outputs kept in this directory after the final demo pass.

## Local Assumptions

This repository has already been verified on this machine with:

- `ollama --version`
- `ollama list`
- `http://127.0.0.1:11434/api/tags`
- local model `nomic-embed-text:latest`

Default runtime config in `main.py`:

- `OLLAMA_API_BASE=http://127.0.0.1:11434`
- `OLLAMA_EMBED_MODEL=ollama/nomic-embed-text`
- `TOP_K=5`
- `LITELLM_LOCAL_MODEL_COST_MAP=true`

## Install

At repo root:

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo
pip install -e .
```

If the current Python environment does not already contain the local Ollama example dependencies:

```powershell
pip install litellm botocore
```

If editable extras installation is unstable because `core.pyd` is occupied, prefer:

```powershell
pip install litellm
```

instead of:

```powershell
pip install -e ".[litellm]"
```

## Step 1: Build Local Embeddings

Go to the example directory:

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo\examples\text_embedding_local_ollama
```

Build or refresh embeddings:

```powershell
cocoindex update .\main.py
```

Live mode:

```powershell
cocoindex update .\main.py --live
```

What this produces:

- one JSON embedding file per chunk under `output_embeddings\`
- local CocoIndex state under `cocoindex.db\`

Current sample corpus in `data\` contains multiple Markdown files, so query results already demonstrate cross-file ranking.

## Step 2: Run a Single Terminal Query

Examples:

```powershell
python .\main.py "vector search"
python .\main.py --query "vector search" --top-k 2
python .\main.py --query "Ollama API" --top-k 2
python .\main.py --query "local model embeddings" --top-k 3 --file-contains ollama
```

What happens:

- the query text is embedded through local `Ollama`
- all candidate JSON vectors are loaded from `output_embeddings\*.json`
- cosine similarity is computed locally
- top matches are printed to the terminal

Terminal preview behavior:

- query-term hits are marked as `[[term]]`
- this is readability-only highlighting
- it does not change retrieval ranking

## Step 3: Export Reports

### Markdown Report

```powershell
python .\main.py --query "vector search" --top-k 2 --file-contains vector --report .\sample-report.md
```

Recommended sample file in this directory:

- `sample-report.md`

### Static HTML Report

```powershell
python .\main.py --query "vector search" --top-k 2 --file-contains vector --html-report .\sample-report.html
```

Recommended sample file in this directory:

- `sample-report.html`

The static HTML report includes:

- query text
- `Top K`
- indexed chunk count
- matching chunks after filter
- file filter
- Ollama API base
- embedding model
- embedding JSON directory
- highlighted preview snippets
- expandable full text per result

HTML reports are static files, not a local app.

## Step 4: Run Interactive Terminal Mode

Start:

```powershell
python .\main.py
python .\main.py --top-k 3
```

Interactive commands:

- `/top 3`
- `/file ollama`
- `/clearfile`
- `/report .\report.md`
- `/clearreport`
- `/htmlreport .\report.html`
- `/clearhtmlreport`

Behavior:

- each non-empty line is a new query
- empty line exits
- current `Top K` and file filter stay active until changed

## Step 5: Run the Local Web UI

Start:

```powershell
python .\main.py --web-ui
python .\main.py --web-ui --port 8008
```

Default address:

- `http://127.0.0.1:8008`

The Web UI uses:

- local `Ollama` for query embedding
- local JSON embedding files for retrieval
- local cosine similarity for ranking

No Postgres, Qdrant, or remote vector service is involved.

## Web UI Walkthrough

### Basic Search

Use the page inputs for:

- `Query`
- `Top K`
- `File Filter`

The file filter input also shows datalist suggestions from currently indexed source files.

### Drill Down by File

Each result card includes a clickable file tag such as:

- `filter:data\vector_search_demo.md`

Clicking that tag:

- keeps the current query
- keeps the current `Top K`
- applies that file as the active filter

### Filter State

When a file filter is active:

- the matching file tag becomes highlighted
- a `Clear Current Filter` button appears
- a filtered-result-count badge appears

Example verified filter page:

- `http://127.0.0.1:8021/?query=vector+search&top_k=2&file_contains=data%5Cvector_search_demo.md`

### Compare Filtered vs All Results

When a filter is active, the filtered-result badge is clickable.

Clicking it switches to a compare view that:

- keeps the current filtered results visible
- appends an `All Results Baseline` section below
- shows the same query and same `Top K` without the current file filter

Example verified compare URL:

- `http://127.0.0.1:8023/?query=vector+search&top_k=2&file_contains=data%5Cvector_search_demo.md&compare=all`

This is useful when you want to see how the current file-scoped ranking differs from the full corpus ranking.

### Download from Web UI

After a query is shown, the page can directly download:

- `Download Markdown`
- `Download HTML`

Downloads are generated from the current query parameters.

Current behavior:

- no extra output path is required
- filenames include a normalized query stem plus timestamp

Example verified response headers:

- `attachment; filename="local-ollama-query-vector-search-20260517-191126.md"`
- `attachment; filename="local-ollama-query-vector-search-20260517-191126.html"`

## Verified Demo Script

If you want a repeatable local demo flow, use this order:

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo\examples\text_embedding_local_ollama
cocoindex update .\main.py
python .\main.py --query "vector search" --top-k 2
python .\main.py --query "vector search" --top-k 2 --file-contains vector --report .\sample-report.md --html-report .\sample-report.html
python .\main.py --web-ui --port 8008
```

Then in the browser:

1. search `vector search`
2. click `filter:data\vector_search_demo.md`
3. click the filtered-result badge to open the compare view
4. try `Download Markdown` or `Download HTML`

## Highlighting Notes

This example adds a lightweight lexical highlight layer on top of semantic retrieval:

- terminal previews use `[[term]]`
- Markdown reports use `**term**`
- HTML and Web UI previews use `<mark>`

This highlighting is:

- based on local query-word matching
- intended to improve readability
- not a token-level model explanation

## Warning Handling

This example now avoids the two common local warnings seen earlier:

- `LiteLLM` remote model-cost-map timeout
  - handled by `LITELLM_LOCAL_MODEL_COST_MAP=true`
- missing `botocore` for Bedrock/SageMaker preload
  - handled by installing `botocore`

The Web UI also keeps a long-lived asyncio loop for repeated query embedding calls, which avoids the `Event loop is closed` failure pattern that can happen with per-request loop creation.

## Output Layout

Important paths in this directory:

- `data\`
- `output_embeddings\`
- `cocoindex.db\`
- `sample-report.md`
- `sample-report.html`

## When to Use This Example

Use this example first when the task is:

- prove local `Ollama` is actually wired up
- test local embedding generation
- test local similarity search without a vector database
- demo local retrieval UX before introducing Postgres or Qdrant
- validate file filtering, report export, or lightweight browser search interactions
