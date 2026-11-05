"""
AURA OS — Memory Vault (Layer 2)
A plain-markdown, Obsidian-compatible knowledge base in three areas:
  raw/      incoming, unprocessed captures (voice notes, clippings, dumps)
  wiki/     organised, readable knowledge articles compiled from raw/
  outputs/  final deliverables (reports, briefs, decks)
Open the folder in Obsidian to browse it; Aura reads/writes the same files. No database, no lock-in.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

AREAS = ("raw", "wiki", "outputs")
_FM = re.compile(r"^---\n(.*?)\n---\n?", re.S)
_WORD = re.compile(r"[a-z0-9']+")


def slugify(title: str, maxlen: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return (s or "untitled")[:maxlen].strip("-") or "untitled"


def split_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    m = _FM.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), text[m.end():]


def render(meta: Dict[str, Any], body: str) -> str:
    return f"---\n{yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()}\n---\n\n{body.strip()}\n"


class Vault:
    def __init__(self, root: str | Path = "~/AuraVault") -> None:
        self.root = Path(root).expanduser().resolve()
        for a in AREAS:
            (self.root / a).mkdir(parents=True, exist_ok=True)
        readme = self.root / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Aura Vault\n\n- `raw/` incoming captures\n- `wiki/` organised knowledge\n- `outputs/` deliverables\n\n"
                "Aura keeps these in sync. Open this folder in Obsidian to browse.\n")

    # ------------------------------------------------------------------ paths
    def _resolve(self, rel: str) -> Path:
        """Resolve a vault-relative path; refuse anything outside the vault or outside the 3 areas."""
        p = (self.root / rel).resolve()
        if self.root not in p.parents or p.relative_to(self.root).parts[0] not in AREAS:
            raise ValueError("Path must be inside raw/, wiki/ or outputs/ of the vault.")
        return p

    def _unique(self, area: str, stem: str) -> Path:
        p = self.root / area / f"{stem}.md"
        n = 2
        while p.exists():
            p = self.root / area / f"{stem}-{n}.md"
            n += 1
        return p

    # ------------------------------------------------------------------ write
    def add_raw(self, title: str, text: str, source: str = "voice") -> str:
        stamp = time.strftime("%Y-%m-%d-%H%M")
        p = self._unique("raw", f"{stamp}-{slugify(title)}")
        meta = {"title": title, "source": source, "created": time.strftime("%Y-%m-%d %H:%M"), "status": "new"}
        p.write_text(render(meta, text))
        return str(p.relative_to(self.root))

    def write(self, area: str, title: str, body: str, meta: Optional[Dict[str, Any]] = None) -> str:
        if area not in ("wiki", "outputs"):
            raise ValueError("write() targets wiki or outputs; use add_raw() for raw captures.")
        stem = slugify(title) if area == "wiki" else f"{time.strftime('%Y-%m-%d')}-{slugify(title)}"
        p = self.root / area / f"{slugify(title)}.md" if area == "wiki" else self._unique(area, stem)
        m = {"title": title, "created": time.strftime("%Y-%m-%d %H:%M"), **(meta or {})}
        p.write_text(render(m, body))
        return str(p.relative_to(self.root))

    # ------------------------------------------------------------------ read
    def read(self, rel: str, max_chars: int = 20000) -> Dict[str, Any]:
        p = self._resolve(rel)
        if not p.is_file():
            raise FileNotFoundError(rel)
        meta, body = split_frontmatter(p.read_text(encoding="utf-8", errors="replace")[:max_chars])
        return {"path": rel, "title": meta.get("title") or p.stem, "meta": meta, "body": body.strip()}

    def list(self, area: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for a in ([area] if area else AREAS):
            if a not in AREAS:
                raise ValueError(f"Unknown area '{a}'")
            for p in (self.root / a).rglob("*.md"):
                meta, _ = split_frontmatter(p.read_text(encoding="utf-8", errors="replace")[:600])
                out.append({"path": str(p.relative_to(self.root)), "area": a,
                            "title": meta.get("title") or p.stem, "status": meta.get("status"),
                            "mtime": p.stat().st_mtime})
        return sorted(out, key=lambda x: -x["mtime"])[:limit]

    def latest(self, area: str = "outputs") -> Optional[Dict[str, Any]]:
        items = self.list(area, limit=1)
        return self.read(items[0]["path"]) if items else None

    def search(self, query: str, limit: int = 5, areas: tuple[str, ...] = AREAS) -> List[Dict[str, Any]]:
        """Keyword search (title hits weigh 3x). Dependency-free and fast enough for thousands of notes."""
        terms = [t for t in _WORD.findall(query.lower()) if len(t) > 2 and t not in _STOP]
        if not terms:
            return []
        hits = []
        for a in areas:
            for p in (self.root / a).rglob("*.md"):
                meta, body = split_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
                title = str(meta.get("title") or p.stem).lower()
                low = body.lower()
                score = sum(3 * title.count(t) + low.count(t) for t in terms)
                if score:
                    i = min((low.find(t) for t in terms if t in low), default=0)
                    snippet = re.sub(r"\s+", " ", body[max(0, i - 60): i + 180]).strip()
                    hits.append({"path": str(p.relative_to(self.root)), "title": meta.get("title") or p.stem,
                                 "area": a, "score": score, "snippet": snippet})
        return sorted(hits, key=lambda h: -h["score"])[:limit]

    # ------------------------------------------------------------------ raw -> wiki
    def pending_raw(self) -> List[Dict[str, Any]]:
        return [i for i in self.list("raw") if i["status"] == "new"]

    def compile_raw(self, llm: Optional[Callable[[str, str], str]], limit: int = 10) -> Dict[str, Any]:
        """Turn new raw captures into wiki articles. `llm(system, prompt)` returns JSON text.
        Without an LLM, raw notes are left untouched (never silently copied into the wiki)."""
        pending = self.pending_raw()[:limit]
        if not pending:
            return {"compiled": 0, "pending": 0, "note": "Nothing new in raw/."}
        if llm is None:
            return {"compiled": 0, "pending": len(pending), "note": "Compiling needs a Gemini key."}
        import json

        existing = [w["title"] for w in self.list("wiki", 100)]
        done = []
        for item in pending:
            note = self.read(item["path"])
            system = ("You maintain a personal wiki. Turn the raw capture into one clear, well-structured "
                      "markdown article. Link related existing articles with [[Title]]. "
                      'Return ONLY JSON: {"title": str, "article": markdown str, "tags": [str]}.')
            prompt = f"Existing wiki titles: {existing}\n\nRaw capture:\n{note['body'][:6000]}"
            try:
                data = json.loads(re.sub(r"^```(?:json)?|```$", "", llm(system, prompt).strip(), flags=re.M).strip())
                title, article = str(data["title"]), str(data["article"])
            except Exception:
                continue
            wiki_path = self.write("wiki", title, article,
                                   {"tags": data.get("tags", []), "sources": [item["path"]]})
            p = self._resolve(item["path"])
            meta, body = split_frontmatter(p.read_text())
            meta.update(status="compiled", wiki=wiki_path)
            p.write_text(render(meta, body))
            existing.append(title)
            done.append(wiki_path)
        return {"compiled": len(done), "pending": len(pending) - len(done), "articles": done}


_STOP = {"the", "and", "for", "that", "this", "with", "what", "about", "from", "have", "are", "was", "any",
         "does", "say", "tell", "notes", "note", "search", "find", "know", "you", "my", "your"}
