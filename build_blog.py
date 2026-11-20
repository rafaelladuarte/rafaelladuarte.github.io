#!/usr/bin/env python3
"""Gera o blog estático a partir de arquivos Markdown em _posts/.

Uso:
    pip install -r requirements-blog.txt
    python build_blog.py

Saída (commitada no repositório, o GitHub Pages só serve os arquivos):
    blog.html          -> listagem de posts
    blog/<slug>.html   -> uma página por post

Formato de cada post (_posts/<slug>.md):
    ---
    title: Título do post
    date: 2026-11-19
    summary: Resumo de uma ou duas frases (aparece na listagem).
    tags: Kafka, CDC, Data Lake
    draft: true        # opcional: posts com draft: true não são publicados
    ---
    Corpo em Markdown...
"""
from __future__ import annotations

import html
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "_posts"
OUT_DIR = ROOT / "blog"
LISTING = ROOT / "blog.html"

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

HEAD = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Rafaella Duarte</title>
<meta name="description" content="{description}">
<link rel="icon" type="image/png" href="{root}images/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}css/style.css">
</head>
<body>
<nav>
  <div class="wrap">
    <a href="{root}index.html" class="nav-logo">rafaella<span>.duarte</span></a>
    <ul class="nav-links">
      <li><a href="{root}index.html#projetos">Projetos</a></li>
      <li><a href="{root}blog.html">Blog</a></li>
    </ul>
  </div>
</nav>
"""

FOOT = """<footer>
  <div class="wrap" style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px;">
    <span>© {year} Rafaella Duarte</span>
    <a href="{root}index.html">Voltar à home ↑</a>
  </div>
</footer>
</body>
</html>
"""


class Post:
    def __init__(self, path: Path):
        self.slug = path.stem
        meta, self.body_md = parse_front_matter(path.read_text(encoding="utf-8"), path)
        self.title = meta.get("title") or fail(path, "falta 'title'")
        raw_date = meta.get("date") or fail(path, "falta 'date' (AAAA-MM-DD)")
        try:
            self.date = date.fromisoformat(raw_date)
        except ValueError:
            fail(path, f"data inválida: {raw_date!r} (use AAAA-MM-DD)")
        self.summary = meta.get("summary", "")
        self.tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
        self.draft = meta.get("draft", "").lower() in ("true", "yes", "sim", "1")
        self.minutes = max(1, round(len(self.body_md.split()) / 200))

    @property
    def date_pt(self) -> str:
        return f"{self.date.day} de {MESES[self.date.month - 1]} de {self.date.year}"


def fail(path: Path, msg: str):
    sys.exit(f"Erro em {path.name}: {msg}")


def parse_front_matter(text: str, path: Path) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        fail(path, "front matter ausente (bloco --- no início do arquivo)")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            # remove comentário no fim da linha e aspas opcionais
            v = re.sub(r"\s+#.*$", "", v).strip().strip("\"'")
            meta[k.strip().lower()] = v
    return meta, m.group(2)


def render_markdown(md: str) -> str:
    return markdown.markdown(
        md, extensions=["fenced_code", "tables", "sane_lists", "smarty"],
        output_format="html5",
    )


def tags_html(tags: list[str]) -> str:
    return "".join(f'<span class="tag">{html.escape(t)}</span>' for t in tags)


def build_post_page(p: Post) -> str:
    esc = html.escape
    return (
        HEAD.format(title=esc(p.title), description=esc(p.summary), root="../")
        + f"""<header class="detail-hero">
  <div class="wrap">
    <a href="../blog.html" class="detail-back">← voltar ao blog</a>
    <p class="eyebrow">{esc(p.date_pt)} · {p.minutes} min de leitura</p>
    <h1>{esc(p.title)}</h1>
    <p class="detail-tagline">{esc(p.summary)}</p>
    <div class="post-tags">{tags_html(p.tags)}</div>
  </div>
</header>
<main class="detail-body">
  <article class="wrap-narrow post-body">
{render_markdown(p.body_md)}
  </article>
</main>
"""
        + FOOT.format(year=date.today().year, root="../")
    )


def build_listing(posts: list[Post]) -> str:
    esc = html.escape
    if posts:
        items = "\n".join(
            f"""    <a class="post-card" href="blog/{p.slug}.html">
      <div class="post-card-meta">{esc(p.date_pt)} · {p.minutes} min de leitura</div>
      <h2>{esc(p.title)}</h2>
      <p>{esc(p.summary)}</p>
      <div class="post-tags">{tags_html(p.tags)}</div>
    </a>"""
            for p in posts
        )
    else:
        items = '    <p class="post-empty">Os primeiros posts chegam em breve.</p>'
    return (
        HEAD.format(
            title="Blog",
            description="Notas sobre engenharia de dados, pipelines e decisões de arquitetura.",
            root="",
        )
        + f"""<header class="detail-hero">
  <div class="wrap">
    <a href="index.html" class="detail-back">← voltar à home</a>
    <p class="eyebrow">Blog</p>
    <h1>Notas de engenharia de dados</h1>
    <p class="detail-tagline">Pipelines, arquitetura e as decisões por trás dos meus projetos.</p>
  </div>
</header>
<main class="detail-body">
  <div class="wrap-narrow post-list">
{items}
  </div>
</main>
"""
        + FOOT.format(year=date.today().year, root="")
    )


def main() -> None:
    posts = [Post(p) for p in sorted(POSTS_DIR.glob("*.md"))]
    posts = [p for p in posts if not p.draft]
    posts.sort(key=lambda p: p.date, reverse=True)

    # recria blog/ do zero para não sobrar HTML de posts removidos
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir()

    for p in posts:
        (OUT_DIR / f"{p.slug}.html").write_text(build_post_page(p), encoding="utf-8")
    LISTING.write_text(build_listing(posts), encoding="utf-8")
    print(f"{len(posts)} post(s) publicado(s) -> blog.html + blog/")


if __name__ == "__main__":
    main()
