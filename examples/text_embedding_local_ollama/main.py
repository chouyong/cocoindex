r"""
Local Ollama embedding and query demo for CocoIndex.

Build/update embeddings:
    cocoindex update .\main.py

Live mode:
    cocoindex update .\main.py --live

Single query:
    python .\main.py "your search query"
    python .\main.py --query "your search query" --top-k 3
    python .\main.py --query "your search query" --file-contains ollama
    python .\main.py --query "your search query" --html-report .\report.html

Interactive query:
    python .\main.py
    python .\main.py --top-k 3
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import html
import json
import os
import pathlib
import re
import threading
import sys
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import AsyncIterator
from urllib.parse import parse_qs, urlencode, urlparse

from dotenv import load_dotenv
import numpy as np

import cocoindex as coco
from cocoindex.connectors import localfs

# Force LiteLLM to use the bundled local cost map and avoid the remote fetch timeout.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")

from cocoindex.ops.litellm import LiteLLMEmbedder
from cocoindex.ops.text import RecursiveSplitter
from cocoindex.resources.chunk import Chunk
from cocoindex.resources.file import FileLike, PatternFilePathMatcher


load_dotenv()

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "ollama/nomic-embed-text")
DEFAULT_TOP_K = int(os.getenv("TOP_K", "5"))
EMBEDDER = LiteLLMEmbedder(OLLAMA_EMBED_MODEL, api_base=OLLAMA_API_BASE)
_splitter = RecursiveSplitter()


@dataclass
class SearchResult:
    score: float
    source_file: str
    chunk_start: int
    chunk_end: int
    embedding_dim: int
    text: str


@dataclass
class SearchRun:
    query_text: str
    top_k: int
    file_contains: str | None
    total_chunks: int
    matched_chunks: int
    results: list[SearchResult]
    outdir: pathlib.Path


@coco.lifespan
async def coco_lifespan(builder: coco.EnvironmentBuilder) -> AsyncIterator[None]:
    builder.settings.db_path = pathlib.Path("./cocoindex.db")
    yield


def _output_name(filename: pathlib.PurePath, chunk: Chunk) -> str:
    safe_name = "__".join(filename.parts)
    return f"{safe_name}__{chunk.start.char_offset}_{chunk.end.char_offset}.json"


@coco.fn(memo=True)
async def process_chunk(
    chunk: Chunk, filename: pathlib.PurePath, outdir: pathlib.Path
) -> None:
    embedding = await EMBEDDER.embed(chunk.text)
    payload = {
        "source_file": str(filename),
        "chunk_start": chunk.start.char_offset,
        "chunk_end": chunk.end.char_offset,
        "text": chunk.text,
        "embedding_model": OLLAMA_EMBED_MODEL,
        "ollama_api_base": OLLAMA_API_BASE,
        "embedding_dim": int(embedding.shape[0]),
        "embedding": embedding.tolist(),
    }
    localfs.declare_file(
        outdir / _output_name(filename, chunk),
        json.dumps(payload, ensure_ascii=False, indent=2),
        create_parent_dirs=True,
    )


@coco.fn(memo=True)
async def process_file(file: FileLike, outdir: pathlib.Path) -> None:
    text = await file.read_text()
    chunks = _splitter.split(
        text,
        chunk_size=1000,
        chunk_overlap=100,
        language="markdown",
    )
    await coco.map(process_chunk, chunks, file.file_path.path, outdir)


@coco.fn
async def app_main(sourcedir: pathlib.Path, outdir: pathlib.Path) -> None:
    files = localfs.walk_dir(
        sourcedir,
        recursive=True,
        path_matcher=PatternFilePathMatcher(included_patterns=["**/*.md"]),
        live=True,
    )
    await coco.mount_each(process_file, files.items(), outdir)


app = coco.App(
    coco.AppConfig(name="TextEmbeddingLocalOllama"),
    app_main,
    sourcedir=pathlib.Path("./data"),
    outdir=pathlib.Path("./output_embeddings"),
)


def _iter_embedding_files(outdir: pathlib.Path) -> list[pathlib.Path]:
    return sorted(outdir.glob("*.json"))


def _list_source_files(outdir: pathlib.Path) -> list[str]:
    source_files: set[str] = set()
    for path in _iter_embedding_files(outdir):
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_files.add(str(payload["source_file"]))
    return sorted(source_files)


def _cosine_similarity(query_vec: np.ndarray, doc_vec: np.ndarray) -> float:
    denom = float(np.linalg.norm(query_vec) * np.linalg.norm(doc_vec))
    if denom == 0.0:
        return 0.0
    return float(np.dot(query_vec, doc_vec) / denom)


def _load_results(
    outdir: pathlib.Path,
    *,
    file_contains: str | None,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for path in _iter_embedding_files(outdir):
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_file = str(payload["source_file"])
        if file_contains and file_contains.lower() not in source_file.lower():
            continue
        payloads.append(payload)
    return payloads


def _query_terms(query_text: str) -> list[str]:
    terms = re.findall(r"\w+", query_text, flags=re.UNICODE)
    unique_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = term.lower()
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        unique_terms.append(term)
    return unique_terms


def _highlight_text(text: str, query_text: str, *, marker: str = "[[{text}]]") -> str:
    highlighted = text
    for term in sorted(_query_terms(query_text), key=len, reverse=True):
        pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
        highlighted = pattern.sub(lambda m: marker.format(text=m.group(0)), highlighted)
    return highlighted


def _make_preview(
    text: str,
    query_text: str,
    *,
    limit: int = 200,
    marker: str = "[[{text}]]",
) -> str:
    compact = text.replace("\n", " ").strip()
    highlighted = _highlight_text(compact, query_text, marker=marker)
    if len(highlighted) > limit:
        highlighted = highlighted[: limit - 3] + "..."
    return highlighted


def _make_html_preview(text: str, query_text: str, *, limit: int = 320) -> str:
    escaped = html.escape(text.replace("\n", " ").strip())
    highlighted = _highlight_text(escaped, query_text, marker="<mark>{text}</mark>")
    if len(highlighted) > limit:
        highlighted = highlighted[: limit - 3] + "..."
    return highlighted


def _safe_download_stem(query_text: str) -> str:
    normalized = re.sub(r"\W+", "-", query_text.strip().lower(), flags=re.UNICODE)
    normalized = normalized.strip("-")
    return normalized[:48] or "query"


def _render_result(result: SearchResult, rank: int, query_text: str) -> None:
    text_preview = _make_preview(result.text, query_text, marker="[[{text}]]")
    print(f"{rank}. score={result.score:.4f} file={result.source_file}")
    print(
        f"   chunk={result.chunk_start}..{result.chunk_end} dim={result.embedding_dim}"
    )
    print(f"   highlight={text_preview}")


async def _run_search(
    query_text: str,
    outdir: pathlib.Path,
    *,
    top_k: int = DEFAULT_TOP_K,
    file_contains: str | None = None,
) -> SearchRun:
    all_payloads = _load_results(outdir, file_contains=None)
    filtered_payloads = _load_results(outdir, file_contains=file_contains)
    if not filtered_payloads:
        if all_payloads and file_contains:
            raise SystemExit(
                f"No embedding JSON files matched filter '{file_contains}' in {outdir}."
            )
        raise SystemExit(
            f"No embedding JSON files found in {outdir}. Run `cocoindex update .\\main.py` first."
        )

    query_vec = await EMBEDDER.embed(query_text)
    scored: list[SearchResult] = []
    for payload in filtered_payloads:
        doc_vec = np.array(payload["embedding"], dtype=np.float32)
        score = _cosine_similarity(query_vec, doc_vec)
        scored.append(
            SearchResult(
                score=score,
                source_file=str(payload["source_file"]),
                chunk_start=int(payload["chunk_start"]),
                chunk_end=int(payload["chunk_end"]),
                embedding_dim=int(payload["embedding_dim"]),
                text=str(payload["text"]),
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return SearchRun(
        query_text=query_text,
        top_k=top_k,
        file_contains=file_contains,
        total_chunks=len(all_payloads),
        matched_chunks=len(filtered_payloads),
        results=scored[:top_k],
        outdir=outdir,
    )


def _render_markdown_report(run: SearchRun) -> str:
    def markdown_preview(text: str) -> str:
        return _make_preview(text, run.query_text, limit=260, marker="**{text}**").replace(
            "[[", ""
        ).replace("]]", "")

    lines = [
        "# Local Ollama Query Report",
        "",
        f"- Generated At: `{dt.datetime.now().isoformat(timespec='seconds')}`",
        f"- Query: `{run.query_text}`",
        f"- Top K: `{run.top_k}`",
        f"- Indexed chunks searched: `{run.total_chunks}`",
        f"- Matching chunks after filter: `{run.matched_chunks}`",
        f"- File filter: `{run.file_contains or '(none)'}`",
        f"- Ollama API Base: `{OLLAMA_API_BASE}`",
        f"- Embed Model: `{OLLAMA_EMBED_MODEL}`",
        f"- Embedding JSON Directory: `{run.outdir}`",
        "",
        "## Results",
        "",
    ]
    if not run.results:
        lines.append("No matching indexed chunks.")
    for idx, result in enumerate(run.results, start=1):
        lines.extend(
            [
                f"### {idx}. {result.source_file}",
                "",
                f"- Score: `{result.score:.4f}`",
                f"- Chunk: `{result.chunk_start}..{result.chunk_end}`",
                f"- Embedding dim: `{result.embedding_dim}`",
                "",
                "#### Highlighted Preview",
                "",
                markdown_preview(result.text),
                "",
                "```text",
                result.text.strip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _write_markdown_report(
    report_path: pathlib.Path,
    *,
    run: SearchRun,
) -> None:
    report_path.write_text(_render_markdown_report(run), encoding="utf-8")


def _render_html_report(run: SearchRun) -> str:
    cards: list[str] = []
    for idx, result in enumerate(run.results, start=1):
        cards.append(
            f"""
            <article class="result-card">
              <div class="result-rank">{idx}</div>
              <div class="result-body">
                <h2>{html.escape(result.source_file)}</h2>
                <p class="meta">
                  <span>rank={idx}</span>
                  <span>score={result.score:.4f}</span>
                  <span>chunk={result.chunk_start}..{result.chunk_end}</span>
                  <span>dim={result.embedding_dim}</span>
                </p>
                <div class="preview">{_make_html_preview(result.text, run.query_text)}</div>
                <details>
                  <summary>Full Text</summary>
                  <pre>{html.escape(result.text.strip())}</pre>
                </details>
              </div>
            </article>
            """
        )

    summary_items = [
        ("Generated At", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("Query", run.query_text),
        ("Top K", str(run.top_k)),
        ("Indexed Chunks Searched", str(run.total_chunks)),
        ("Matching Chunks After Filter", str(run.matched_chunks)),
        ("File Filter", run.file_contains or "(none)"),
        ("Ollama API Base", OLLAMA_API_BASE),
        ("Embed Model", OLLAMA_EMBED_MODEL),
        ("Embedding JSON Directory", str(run.outdir)),
    ]
    summary_cards = "".join(
        f'<div class="meta-card"><span class="label">{html.escape(label)}</span><span class="value">{html.escape(value)}</span></div>'
        for label, value in summary_items
    )
    query_terms = _query_terms(run.query_text)
    query_tags = "".join(
        f"<span>{html.escape(term)}</span>" for term in query_terms
    ) or "<span>(no query terms extracted)</span>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local Ollama Query Report</title>
  <style>
    :root {{
      --bg: #f2efe8;
      --panel: #fffdf8;
      --ink: #1d1a15;
      --muted: #6f6558;
      --accent: #0f766e;
      --accent-soft: #d9f3ef;
      --border: #ded6c9;
      --mark: #ffe08a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #f7d9b8 0, transparent 28%),
        radial-gradient(circle at top right, #d5efe7 0, transparent 24%),
        var(--bg);
    }}
    .page {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 40px 24px 60px;
    }}
    .hero {{
      background: linear-gradient(135deg, #fffdf8, #f7f1e5);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 18px 40px rgba(29, 26, 21, 0.08);
      margin-bottom: 24px;
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-size: 32px;
      line-height: 1.1;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      font-size: 16px;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 20px;
    }}
    .meta-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px 16px;
    }}
    .meta-card .label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
    }}
    .meta-card .value {{
      font-size: 16px;
      font-weight: 600;
      word-break: break-word;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: 1.3fr 0.7fr;
      gap: 16px;
      margin-top: 18px;
    }}
    .summary-panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
    }}
    .summary-panel h3 {{
      margin: 0 0 12px;
      font-size: 16px;
    }}
    .summary-panel p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }}
    .tag-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .tag-list span {{
      background: #eef8f6;
      color: var(--accent);
      border: 1px solid #c6e8e2;
      border-radius: 999px;
      padding: 7px 11px;
      font-size: 13px;
      font-weight: 600;
    }}
    .results {{
      display: grid;
      gap: 16px;
    }}
    .result-card {{
      display: grid;
      grid-template-columns: 72px 1fr;
      gap: 16px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 18px;
      box-shadow: 0 16px 36px rgba(29, 26, 21, 0.06);
    }}
    .result-rank {{
      align-self: start;
      width: 54px;
      height: 54px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      font-size: 20px;
      font-weight: 700;
    }}
    .result-body h2 {{
      margin: 0 0 10px;
      font-size: 22px;
      line-height: 1.2;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 14px;
    }}
    .meta span {{
      background: #f4eee3;
      border-radius: 999px;
      padding: 6px 10px;
    }}
    .preview {{
      background: var(--accent-soft);
      border-left: 4px solid var(--accent);
      border-radius: 14px;
      padding: 14px 16px;
      line-height: 1.7;
      font-size: 15px;
    }}
    mark {{
      background: var(--mark);
      padding: 0 0.12em;
      border-radius: 0.2em;
    }}
    details {{
      margin-top: 14px;
    }}
    summary {{
      cursor: pointer;
      color: var(--accent);
      font-weight: 600;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #f7f1e5;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      margin-top: 10px;
      font-size: 13px;
      line-height: 1.6;
      overflow: auto;
    }}
    .empty {{
      background: var(--panel);
      border: 1px dashed var(--border);
      border-radius: 20px;
      padding: 24px;
      color: var(--muted);
    }}
    @media (max-width: 700px) {{
      .summary-grid {{
        grid-template-columns: 1fr;
      }}
      .result-card {{
        grid-template-columns: 1fr;
      }}
      .result-rank {{
        width: 44px;
        height: 44px;
        font-size: 18px;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <h1>Local Ollama Query Report</h1>
      <p>Static HTML report generated from local CocoIndex JSON embeddings.</p>
      <div class="meta-grid">
        {summary_cards}
      </div>
      <div class="summary-grid">
        <section class="summary-panel">
          <h3>Query Summary</h3>
          <p>This report was generated from local JSON embeddings using local Ollama query embedding plus cosine similarity ranking. The file filter narrows the candidate set before scoring.</p>
        </section>
        <section class="summary-panel">
          <h3>Query Terms Highlighted</h3>
          <div class="tag-list">{query_tags}</div>
        </section>
      </div>
    </section>
    <section class="results">
      {''.join(cards) if cards else '<div class="empty">No matching indexed chunks.</div>'}
    </section>
  </main>
</body>
</html>
"""


def _write_html_report(
    report_path: pathlib.Path,
    *,
    run: SearchRun,
) -> None:
    report_path.write_text(_render_html_report(run), encoding="utf-8")


async def query_index(
    query_text: str,
    outdir: pathlib.Path,
    *,
    top_k: int = DEFAULT_TOP_K,
    file_contains: str | None = None,
    report_path: pathlib.Path | None = None,
    html_report_path: pathlib.Path | None = None,
) -> list[SearchResult]:
    run = await _run_search(
        query_text,
        outdir,
        top_k=top_k,
        file_contains=file_contains,
    )
    shown = run.results
    print(f"Showing top {len(shown)} of {run.matched_chunks} indexed chunks.")
    if file_contains:
        print(f"File filter: {file_contains}")
    for idx, result in enumerate(shown, start=1):
        _render_result(result, idx, query_text)
    if report_path is not None:
        _write_markdown_report(report_path, run=run)
        print(f"Markdown report written to {report_path}")
    if html_report_path is not None:
        _write_html_report(html_report_path, run=run)
        print(f"HTML report written to {html_report_path}")
    return shown


async def interactive_query_loop(
    outdir: pathlib.Path, *, top_k: int = DEFAULT_TOP_K
) -> None:
    current_top_k = top_k
    current_file_filter: str | None = None
    current_report_path: pathlib.Path | None = None
    current_html_report_path: pathlib.Path | None = None
    print("Interactive local query mode. Press Enter on an empty line to exit.")
    print(
        "Use `/top N`, `/file SUBSTR`, `/clearfile`, `/report PATH`, `/clearreport`, "
        "`/htmlreport PATH`, `/clearhtmlreport`."
    )
    while True:
        query_text = input("query> ").strip().lstrip("\ufeff")
        if not query_text:
            break
        normalized_query = query_text.replace("／", "/")
        if normalized_query.startswith("/top "):
            _, _, value = normalized_query.partition(" ")
            try:
                parsed_top_k = int(value.strip())
            except ValueError:
                print("Top K must be an integer.")
                print()
                continue
            if parsed_top_k <= 0:
                print("Top K must be greater than zero.")
                print()
                continue
            current_top_k = parsed_top_k
            print(f"Top K updated to {current_top_k}.")
            print()
            continue
        if normalized_query.startswith("/file "):
            _, _, value = normalized_query.partition(" ")
            current_file_filter = value.strip() or None
            print(f"File filter updated to {current_file_filter!r}.")
            print()
            continue
        if normalized_query == "/clearfile":
            current_file_filter = None
            print("File filter cleared.")
            print()
            continue
        if normalized_query.startswith("/report "):
            _, _, value = normalized_query.partition(" ")
            current_report_path = pathlib.Path(value.strip())
            print(f"Report path updated to {current_report_path}.")
            print()
            continue
        if normalized_query == "/clearreport":
            current_report_path = None
            print("Report path cleared.")
            print()
            continue
        if normalized_query.startswith("/htmlreport "):
            _, _, value = normalized_query.partition(" ")
            current_html_report_path = pathlib.Path(value.strip())
            print(f"HTML report path updated to {current_html_report_path}.")
            print()
            continue
        if normalized_query == "/clearhtmlreport":
            current_html_report_path = None
            print("HTML report path cleared.")
            print()
            continue
        await query_index(
            query_text,
            outdir,
            top_k=current_top_k,
            file_contains=current_file_filter,
            report_path=current_report_path,
            html_report_path=current_html_report_path,
        )
        print()


def _render_web_ui(
    *,
    run: SearchRun | None,
    baseline_run: SearchRun | None,
    query_text: str,
    top_k: int,
    file_contains: str | None,
    error: str | None,
    source_files: list[str],
    compare_all: bool,
) -> str:
    result_cards = ""
    if run is not None:
        cards: list[str] = []
        for idx, result in enumerate(run.results, start=1):
            is_active_filter = run.file_contains == result.source_file
            filter_params = urlencode(
                {
                    "query": run.query_text,
                    "top_k": str(run.top_k),
                    "file_contains": result.source_file,
                }
            )
            cards.append(
                f"""
                <article class="ui-card">
                  <div class="ui-rank">{idx}</div>
                  <div>
                    <h3>{html.escape(result.source_file)}</h3>
                    <p class="ui-meta">
                      <a class="ui-file-tag{' is-active' if is_active_filter else ''}" href="/?{filter_params}">filter:{html.escape(result.source_file)}</a>
                      <span>score={result.score:.4f}</span>
                      <span>chunk={result.chunk_start}..{result.chunk_end}</span>
                      <span>dim={result.embedding_dim}</span>
                    </p>
                    <div class="ui-preview">{_make_html_preview(result.text, run.query_text, limit=280)}</div>
                    <details>
                      <summary>Full Text</summary>
                      <pre>{html.escape(result.text.strip())}</pre>
                    </details>
                  </div>
                </article>
                """
            )
        result_cards = "".join(cards) or '<div class="ui-empty">No matching indexed chunks.</div>'

    summary = ""
    if run is not None:
        summary = f"""
        <section class="ui-summary">
          <div class="ui-stat"><span>Query</span><strong>{html.escape(run.query_text)}</strong></div>
          <div class="ui-stat"><span>Top K</span><strong>{run.top_k}</strong></div>
          <div class="ui-stat"><span>File Filter</span><strong>{html.escape(run.file_contains or '(none)')}</strong></div>
          <div class="ui-stat"><span>Indexed Chunks</span><strong>{run.total_chunks}</strong></div>
          <div class="ui-stat"><span>Matching Chunks</span><strong>{run.matched_chunks}</strong></div>
          <div class="ui-stat"><span>Embed Model</span><strong>{html.escape(OLLAMA_EMBED_MODEL)}</strong></div>
        </section>
        """

    error_block = (
        f'<div class="ui-error">{html.escape(error)}</div>' if error is not None else ""
    )
    file_value = html.escape(file_contains or "")
    query_value = html.escape(query_text)
    top_value = html.escape(str(top_k))
    file_hint = (
        f"Current filter: <code>{html.escape(file_contains)}</code>"
        if file_contains
        else "Current filter: <code>(none)</code>"
    )
    clear_filter_link = ""
    if query_text and file_contains:
        clear_params = urlencode({"query": query_text, "top_k": str(top_k)})
        clear_filter_link = (
            f'<a class="ui-clear-filter" href="/?{clear_params}">Clear Current Filter</a>'
        )
    filter_badge = ""
    if run is not None and run.file_contains:
        noun = "chunk" if run.matched_chunks == 1 else "chunks"
        compare_params = urlencode(
            {
                "query": run.query_text,
                "top_k": str(run.top_k),
                "file_contains": run.file_contains,
                "compare": "all",
            }
        )
        filter_badge = (
            f'<a class="ui-filter-badge" href="/?{compare_params}">Filtered Results: '
            f'<strong>{run.matched_chunks}</strong> {noun} · Compare With All Results</a>'
        )
    datalist_options = "".join(
        f'<option value="{html.escape(source_file)}"></option>'
        for source_file in source_files
    )
    export_links = ""
    if run is not None:
        base_params = {
            "query": run.query_text,
            "top_k": str(run.top_k),
        }
        if run.file_contains:
            base_params["file_contains"] = run.file_contains
        markdown_export = urlencode(base_params | {"download": "md"})
        html_export = urlencode(base_params | {"download": "html"})
        export_links = f"""
        <div class="ui-export-row">
          <a class="ui-export" href="/?{markdown_export}">Download Markdown</a>
          <a class="ui-export" href="/?{html_export}">Download HTML</a>
        </div>
        """
    comparison_section = ""
    if compare_all and run is not None and baseline_run is not None:
        baseline_cards: list[str] = []
        for idx, result in enumerate(baseline_run.results, start=1):
            baseline_cards.append(
                f"""
                <article class="ui-card ui-card-baseline">
                  <div class="ui-rank">{idx}</div>
                  <div>
                    <h3>{html.escape(result.source_file)}</h3>
                    <p class="ui-meta">
                      <span>score={result.score:.4f}</span>
                      <span>chunk={result.chunk_start}..{result.chunk_end}</span>
                      <span>dim={result.embedding_dim}</span>
                    </p>
                    <div class="ui-preview">{_make_html_preview(result.text, baseline_run.query_text, limit=220)}</div>
                  </div>
                </article>
                """
            )
        comparison_section = f"""
        <section class="ui-compare">
          <div class="ui-compare-head">
            <h2>All Results Baseline</h2>
            <p>Showing the same query without the current file filter so you can compare filtered and unfiltered ranking side by side.</p>
          </div>
          <div class="ui-compare-grid">
            {''.join(baseline_cards) if baseline_cards else '<div class="ui-empty">No baseline results.</div>'}
          </div>
        </section>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local Ollama Web UI</title>
  <style>
    :root {{
      --bg: #f3efe7;
      --panel: #fffdf9;
      --ink: #1c1a16;
      --muted: #6a655a;
      --accent: #165d52;
      --accent-soft: #dff2ec;
      --line: #d8d0c5;
      --mark: #ffe08a;
      --danger: #7f1d1d;
      --danger-soft: #fee2e2;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top left, #f4d7b6 0, transparent 24%),
        radial-gradient(circle at top right, #d5ebe2 0, transparent 20%),
        var(--bg);
    }}
    .ui-page {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}
    .ui-hero {{
      background: linear-gradient(135deg, #fffdf9, #f8f1e5);
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 28px;
      box-shadow: 0 22px 48px rgba(28, 26, 22, 0.08);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 34px;
      line-height: 1.1;
    }}
    .ui-lead {{
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }}
    .ui-form {{
      display: grid;
      grid-template-columns: 2fr 0.9fr 1.1fr auto;
      gap: 12px;
      margin-top: 22px;
      align-items: end;
    }}
    .ui-field label {{
      display: block;
      margin-bottom: 8px;
      font-size: 13px;
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .ui-field input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      font-size: 15px;
      background: white;
    }}
    .ui-actions button {{
      border: 0;
      border-radius: 14px;
      background: var(--accent);
      color: white;
      padding: 13px 18px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
    }}
    .ui-actions {{
      display: flex;
      align-items: end;
    }}
    .ui-hints {{
      margin-top: 12px;
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      font-size: 13px;
    }}
    .ui-error {{
      margin-top: 16px;
      background: var(--danger-soft);
      color: var(--danger);
      border: 1px solid #fecaca;
      border-radius: 16px;
      padding: 14px 16px;
      line-height: 1.6;
    }}
    .ui-summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin: 22px 0 18px;
    }}
    .ui-export-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 0 0 18px;
    }}
    .ui-export {{
      display: inline-block;
      text-decoration: none;
      background: #f4eee3;
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 14px;
      font-weight: 700;
    }}
    .ui-clear-filter {{
      display: inline-block;
      text-decoration: none;
      background: #fff4e8;
      color: #8a4b12;
      border: 1px solid #f2c48e;
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 14px;
      font-weight: 700;
    }}
    .ui-filter-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: #e8f4f0;
      color: var(--accent);
      border: 1px solid #c7e3db;
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 14px;
      font-weight: 700;
      margin: 0 0 18px;
      text-decoration: none;
    }}
    .ui-filter-badge strong {{
      font-size: 16px;
      color: var(--ink);
    }}
    .ui-file-tag {{
      display: inline-block;
      text-decoration: none;
      background: #e8f4f0;
      color: var(--accent);
      border: 1px solid #c7e3db;
      border-radius: 999px;
      padding: 6px 10px;
      font-weight: 700;
    }}
    .ui-file-tag.is-active {{
      background: var(--accent);
      color: white;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(22, 93, 82, 0.14);
    }}
    .ui-stat {{
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px 16px;
    }}
    .ui-stat span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
    }}
    .ui-stat strong {{
      display: block;
      font-size: 15px;
      word-break: break-word;
    }}
    .ui-results {{
      margin-top: 24px;
      display: grid;
      gap: 16px;
    }}
    .ui-compare {{
      margin-top: 8px;
      display: grid;
      gap: 16px;
    }}
    .ui-compare-head {{
      background: #f6efe2;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
    }}
    .ui-compare-head h2 {{
      margin: 0 0 8px;
      font-size: 22px;
      line-height: 1.2;
    }}
    .ui-compare-head p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }}
    .ui-compare-grid {{
      display: grid;
      gap: 16px;
    }}
    .ui-card {{
      display: grid;
      grid-template-columns: 64px 1fr;
      gap: 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 18px;
      box-shadow: 0 18px 40px rgba(28, 26, 22, 0.06);
    }}
    .ui-card-baseline {{
      background: #fcfaf5;
    }}
    .ui-rank {{
      width: 48px;
      height: 48px;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      display: grid;
      place-items: center;
      font-weight: 700;
      font-size: 18px;
    }}
    .ui-card h3 {{
      margin: 0 0 10px;
      font-size: 22px;
      line-height: 1.25;
    }}
    .ui-meta {{
      margin: 0 0 12px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 14px;
    }}
    .ui-meta span {{
      background: #f4eee3;
      border-radius: 999px;
      padding: 6px 10px;
    }}
    .ui-preview {{
      background: var(--accent-soft);
      border-left: 4px solid var(--accent);
      border-radius: 14px;
      padding: 14px 16px;
      line-height: 1.7;
    }}
    .ui-empty {{
      background: var(--panel);
      border: 1px dashed var(--line);
      border-radius: 18px;
      padding: 24px;
      color: var(--muted);
    }}
    details {{
      margin-top: 14px;
    }}
    summary {{
      cursor: pointer;
      color: var(--accent);
      font-weight: 700;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #f7f1e5;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      line-height: 1.6;
      overflow: auto;
    }}
    mark {{
      background: var(--mark);
      padding: 0 0.12em;
      border-radius: 0.2em;
    }}
    code {{
      background: #f2ece1;
      padding: 0.12em 0.34em;
      border-radius: 6px;
    }}
    @media (max-width: 820px) {{
      .ui-form {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 720px) {{
      .ui-card {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="ui-page">
    <section class="ui-hero">
      <h1>Local Ollama Search UI</h1>
      <p class="ui-lead">This browser page runs against local JSON embeddings generated by CocoIndex. Queries are embedded through local Ollama and ranked with local cosine similarity. No remote vector database or cloud search service is involved.</p>
      <form class="ui-form" method="get" action="/">
        <div class="ui-field">
          <label for="query">Query</label>
          <input id="query" name="query" value="{query_value}" placeholder="vector search">
        </div>
        <div class="ui-field">
          <label for="top_k">Top K</label>
          <input id="top_k" name="top_k" value="{top_value}" inputmode="numeric">
        </div>
        <div class="ui-field">
          <label for="file_contains">File Filter</label>
          <input id="file_contains" name="file_contains" value="{file_value}" placeholder="ollama" list="file-filter-options">
        </div>
        <div class="ui-actions">
          <button type="submit">Search</button>
        </div>
      </form>
      <datalist id="file-filter-options">
        {datalist_options}
      </datalist>
      <div class="ui-hints">
        <span>{file_hint}</span>
        <span>Embedding dir: <code>{html.escape(str(pathlib.Path('./output_embeddings')))}</code></span>
        <span>Model: <code>{html.escape(OLLAMA_EMBED_MODEL)}</code></span>
        <span>Indexed source files: <code>{len(source_files)}</code></span>
      </div>
      {error_block}
      {summary}
    </section>
    <section class="ui-results">
      {export_links}
      {filter_badge}
      {clear_filter_link}
      {result_cards if run is not None else '<div class="ui-empty">Enter a query to search local embeddings.</div>'}
      {comparison_section}
    </section>
  </main>
</body>
</html>
"""


def launch_web_ui(
    outdir: pathlib.Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8008,
    top_k: int = DEFAULT_TOP_K,
) -> None:
    loop = asyncio.new_event_loop()

    def run_loop() -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    loop_worker = threading.Thread(target=run_loop, daemon=True)
    loop_worker.start()

    def execute_search(
        query_text: str,
        current_top_k: int,
        file_contains: str | None,
    ) -> SearchRun:
        future = asyncio.run_coroutine_threadsafe(
            _run_search(
                query_text,
                outdir,
                top_k=current_top_k,
                file_contains=file_contains,
            ),
            loop,
        )
        return future.result()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/":
                self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
                return

            params = parse_qs(parsed.query)
            download_kind = params.get("download", [""])[0].strip().lower()
            compare_all = params.get("compare", [""])[0].strip().lower() == "all"
            query_text = params.get("query", [""])[0].strip()
            file_contains = params.get("file_contains", [""])[0].strip() or None
            raw_top_k = params.get("top_k", [str(top_k)])[0].strip() or str(top_k)
            error: str | None = None
            run: SearchRun | None = None
            baseline_run: SearchRun | None = None
            source_files = _list_source_files(outdir)
            try:
                current_top_k = int(raw_top_k)
                if current_top_k <= 0:
                    raise ValueError
            except ValueError:
                current_top_k = top_k
                error = "Top K must be a positive integer."
            else:
                if query_text:
                    try:
                        run = execute_search(
                            query_text,
                            current_top_k,
                            file_contains,
                        )
                        if compare_all and file_contains:
                            baseline_run = execute_search(
                                query_text,
                                current_top_k,
                                None,
                            )
                    except SystemExit as exc:
                        error = str(exc)

            if download_kind and run is not None:
                timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
                base_name = (
                    f"local-ollama-query-{_safe_download_stem(run.query_text)}-{timestamp}"
                )
                if download_kind == "md":
                    body = _render_markdown_report(run).encode("utf-8")
                    filename = f"{base_name}.md"
                    content_type = "text/markdown; charset=utf-8"
                elif download_kind == "html":
                    body = _render_html_report(run).encode("utf-8")
                    filename = f"{base_name}.html"
                    content_type = "text/html; charset=utf-8"
                else:
                    body = b"Unsupported download type."
                    filename = "error.txt"
                    content_type = "text/plain; charset=utf-8"
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            body = _render_web_ui(
                run=run,
                baseline_run=baseline_run,
                query_text=query_text,
                top_k=current_top_k,
                file_contains=file_contains,
                error=error,
                source_files=source_files,
                compare_all=compare_all,
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Local web UI running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web UI...")
    finally:
        server.server_close()
        loop.call_soon_threadsafe(loop.stop)
        loop_worker.join(timeout=2)
        loop.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local Ollama embedding demo over JSON output files."
    )
    parser.add_argument("query", nargs="*", help="Optional single-shot query text.")
    parser.add_argument(
        "--query",
        dest="query_flag",
        help="Optional single-shot query text. If omitted, interactive mode starts.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Number of top results to display. Default comes from TOP_K or 5.",
    )
    parser.add_argument(
        "--file-contains",
        help="Only search indexed chunks whose source file path contains this substring.",
    )
    parser.add_argument(
        "--report",
        help="Optional Markdown report output path for single-shot query mode.",
    )
    parser.add_argument(
        "--html-report",
        help="Optional static HTML report output path for single-shot query mode.",
    )
    parser.add_argument(
        "--web-ui",
        action="store_true",
        help="Launch a small local web UI for querying local embeddings.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the local web UI to. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8008,
        help="Port for the local web UI. Default: 8008",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    query_text = args.query_flag or " ".join(args.query).strip()
    if args.top_k <= 0:
        raise SystemExit("--top-k must be greater than zero")
    outdir = pathlib.Path("./output_embeddings")
    if args.web_ui:
        launch_web_ui(outdir, host=args.host, port=args.port, top_k=args.top_k)
    elif query_text:
        report_path = pathlib.Path(args.report) if args.report else None
        html_report_path = pathlib.Path(args.html_report) if args.html_report else None
        asyncio.run(
            query_index(
                query_text,
                outdir,
                top_k=args.top_k,
                file_contains=args.file_contains,
                report_path=report_path,
                html_report_path=html_report_path,
            )
        )
    else:
        asyncio.run(interactive_query_loop(outdir, top_k=args.top_k))
