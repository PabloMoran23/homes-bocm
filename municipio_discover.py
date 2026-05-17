#!/usr/bin/env python3
"""
Descubrimiento genérico de URLs de documentación urbana en webs municipales.

1) Lee Sitemap: de robots.txt
2) Prueba rutas habituales de sitemap si no hay ninguno
3) Expande sitemap index (recursivo, con límite)
4) Filtra URLs por extensión (.pdf) y/o palabras clave en la ruta

Uso:
  python3 municipio_discover.py
  python3 municipio_discover.py --download --limit-pdfs 3 --out-dir output/municipio_pdfs
"""

from __future__ import annotations

import argparse
import gzip
import random
import re
import socket
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

DEFAULT_UA = "MunicipioDiscover/0.1 (+https://example.local; research)"

# Ayuntamientos CAM (dominios que suelen resolver; ajustar si cambian)
SEED_BASE_URLS = [
    "https://www.madrid.es",
    "https://www.mostoles.es",
    "https://www.getafe.es",
    "https://www.navalcarnero.es",
    "https://www.argandadelrey.es",
    "https://ayto-meco.es",
    "https://www.alcobendas.org",
    "https://www.torrejondeardoz.es",
    "https://www.pozuelodealarcon.es",
    "https://grinon.es",
    "https://www.coslada.org",
    "https://www.alcorcon.org",
]

ROBOTS_PATHS = ("/robots.txt",)

FALLBACK_SITEMAPS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/wp-sitemap.xml",
)

KEYWORDS = re.compile(
    r"|".join(
        re.escape(k)
        for k in (
            "urban",
            "planeam",
            "pgou",
            "plan-parcial",
            "plan_parcial",
            "planparcial",
            "plan-especial",
            "ordenanz",
            "normativ",
            "suelo",
            "licencia",
            "obra",
            "tramit",
            "sede",
            "transparen",
            "document",
            "archivo",
            "public",
            "bop",
        )
    ),
    re.I,
)


def sanitize_xml_text(text: str) -> str:
    t = text.lstrip("\ufeff \t\r\n")
    if not t.startswith("<?xml") and not t.startswith("<"):
        i = t.find("<")
        if i != -1:
            t = t[i:]
    return t


def fetch_text(url: str, timeout: int = 15) -> str | None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": DEFAULT_UA, "Accept": "*/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read()
        if url.lower().endswith(".gz") or (len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B):
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        return raw.decode(charset, errors="replace")
    except Exception:
        return None


def fetch_bytes(url: str, timeout: int = 45) -> bytes | None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": DEFAULT_UA, "Accept": "*/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def parse_robots_sitemaps(robots_body: str, base: str) -> list[str]:
    base = base.rstrip("/")
    out: list[str] = []
    for line in robots_body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"(?i)Sitemap:\s*(\S+)", line)
        if m:
            sm = m.group(1).strip()
            if sm.startswith(("http://", "https://")):
                out.append(sm)
            else:
                out.append(urljoin(base + "/", sm.lstrip("/")))
    return out


def normalize_tag(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """Devuelve (urls_hoja, urls_otras_sitemaps)."""
    leaf_urls: list[str] = []
    child_sitemaps: list[str] = []
    try:
        root = ET.fromstring(sanitize_xml_text(xml_text))
    except ET.ParseError:
        return [], []

    rtag = normalize_tag(root.tag)
    if rtag == "sitemapindex":
        for el in root:
            if normalize_tag(el.tag) != "sitemap":
                continue
            for child in el:
                if normalize_tag(child.tag) == "loc" and (child.text or "").strip():
                    child_sitemaps.append(child.text.strip())
    elif rtag == "urlset":
        for el in root:
            if normalize_tag(el.tag) != "url":
                continue
            for child in el:
                if normalize_tag(child.tag) == "loc" and (child.text or "").strip():
                    leaf_urls.append(child.text.strip())
    else:
        # Algunos sitemaps malformados o namespaces raros: recoger cualquier <loc>
        for el in root.iter():
            if normalize_tag(el.tag) == "loc" and (el.text or "").strip():
                u = el.text.strip()
                if u.endswith(".xml") or "sitemap" in u.lower():
                    child_sitemaps.append(u)
                else:
                    leaf_urls.append(u)
    return leaf_urls, child_sitemaps


def collect_all_urls_from_sitemaps(
    seed_sitemap_urls: list[str],
    max_sitemaps: int = 80,
    delay_s: float = 0.12,
) -> set[str]:
    seen_sitemaps: set[str] = set()
    all_leaf: set[str] = set()
    q: deque[str] = deque()

    for u in seed_sitemap_urls:
        if u:
            q.append(u)

    while q and len(seen_sitemaps) < max_sitemaps:
        sm_url = q.popleft()
        if sm_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sm_url)
        body = fetch_text(sm_url)
        time.sleep(delay_s)
        if not body:
            continue
        leaves, children = parse_sitemap_xml(body)
        all_leaf.update(leaves)
        for c in children:
            if c not in seen_sitemaps:
                q.append(c)
    return all_leaf


def discover_sitemap_seeds(base: str) -> list[str]:
    base = base.rstrip("/")
    seeds: list[str] = []
    robots = fetch_text(base + "/robots.txt")
    time.sleep(0.12)
    if robots and not robots.lstrip().startswith("<"):
        seeds.extend(parse_robots_sitemaps(robots, base))
    if not seeds:
        for path in FALLBACK_SITEMAPS:
            u = base + path
            t = fetch_text(u)
            time.sleep(0.1)
            if t and ("<urlset" in t or "<urlset " in t or "sitemapindex" in t or "<sitemapindex" in t):
                seeds.append(u)
    # Dedup preservando orden
    out, seen = [], set()
    for s in seeds:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def filter_interesting(urls: set[str]) -> dict[str, list[str]]:
    pdfs = sorted(u for u in urls if urlparse(u).path.lower().endswith(".pdf"))
    key_html = sorted(u for u in urls if not u.lower().endswith(".pdf") and KEYWORDS.search(u))
    return {"pdf": pdfs, "html_keyword": key_html}


def pdf_url_relevance(url: str) -> int:
    u = url.lower()
    score = 0
    for k in (
        "urban",
        "planeam",
        "pgou",
        "orden",
        "suelo",
        "licenc",
        "parcial",
        "especial",
        "edific",
        "viviend",
    ):
        if k in u:
            score += 2
    return score


def safe_filename_from_url(url: str, max_len: int = 120) -> str:
    p = urlparse(url)
    name = Path(p.path).name or "doc"
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name[:max_len]


def main() -> None:
    socket.setdefaulttimeout(14)
    ap = argparse.ArgumentParser(description="Descubrir URLs urbanismo via sitemaps municipales")
    ap.add_argument("--bases", nargs="*", help="URLs base (default: muestra aleatoria CAM)")
    ap.add_argument("--sample", type=int, default=6, help="Cuántos ayuntamientos probar si no se pasan --bases")
    ap.add_argument("--max-sitemaps", type=int, default=60)
    ap.add_argument("--download", action="store_true", help="Descargar algunos PDFs candidatos")
    ap.add_argument("--limit-pdfs", type=int, default=5)
    ap.add_argument("--max-pdf-mb", type=float, default=12.0, help="No guardar PDFs mayores que esto (0=sin límite)")
    ap.add_argument("--out-dir", type=str, default="output/municipio_scrape")
    args = ap.parse_args()

    if args.bases:
        bases = args.bases
    else:
        rng = random.Random(42)
        pool = [b for b in SEED_BASE_URLS]
        rng.shuffle(pool)
        bases = pool[: args.sample]

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    print("=== municipio_discover (sitemaps + keywords) ===\n")
    for base in bases:
        print(f"--- {base} ---")
        seeds = discover_sitemap_seeds(base)
        if not seeds:
            print("  [sitemap] ninguna semilla encontrada")
            continue
        print(f"  [sitemap] semillas: {[s.split('/')[-1] for s in seeds[:5]]}{'…' if len(seeds) > 5 else ''}")
        all_urls = collect_all_urls_from_sitemaps(seeds, max_sitemaps=args.max_sitemaps)
        print(f"  [urls]   total en hojas de sitemap: {len(all_urls)}")
        buckets = filter_interesting(all_urls)
        print(f"  [match]  PDF: {len(buckets['pdf'])} | HTML con keyword: {len(buckets['html_keyword'])}")
        for label, lst in buckets.items():
            for u in lst[:8]:
                print(f"    - [{label}] {u}")
            if len(lst) > 8:
                print(f"    … +{len(lst) - 8} más")

        if args.download and buckets["pdf"]:
            host = urlparse(base).netloc.replace(":", "_")
            sub = out_root / host.replace(".", "_")
            sub.mkdir(parents=True, exist_ok=True)
            n = 0
            max_bytes = int(args.max_pdf_mb * 1024 * 1024) if args.max_pdf_mb > 0 else 0
            pdf_order = sorted(buckets["pdf"], key=pdf_url_relevance, reverse=True)
            for u in pdf_order:
                if n >= args.limit_pdfs:
                    break
                fn = sub / safe_filename_from_url(u)
                data = fetch_bytes(u)
                time.sleep(0.4)
                if not data or len(data) < 2000:
                    continue
                if max_bytes and len(data) > max_bytes:
                    print(f"  [skip] PDF demasiado grande ({len(data)} b)")
                    continue
                fn.write_bytes(data)
                print(f"  [saved] {fn} ({len(data)} bytes)")
                n += 1
        print()


if __name__ == "__main__":
    main()
