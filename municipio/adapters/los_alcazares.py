"""Named public-building work commencement notices in the municipal news API."""
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter


class LosAlcazaresAyuntamientoAdapter(AyuntamientoAdapter):
    API = 'https://losalcazares.es/wp-json/wp/v2/posts'

    @staticmethod
    def parse_posts(posts):
        rows = []
        for post in posts:
            body = BeautifulSoup(post['content']['rendered'], 'html.parser')
            description = body.get_text(' ', strip=True)
            title = BeautifulSoup(post['title']['rendered'], 'html.parser').get_text(' ', strip=True)
            heading = body.find(['h1', 'h2'])
            if heading and len(title) < 35:
                title = heading.get_text(' ', strip=True)
            # Restrict to actual commencement of named municipal building works.
            # Meeting announcements, awards and completion stories are not new projects.
            if not re.match(r'^Comienzan las obras (?:de|del|para)\b', title, re.I):
                continue
            if not re.search(r'edificio|oficina|pabell[oó]n|centro|colegio|aulas|escuela', title, re.I):
                continue
            if len(description) < 150:
                raise ValueError('Construction notice has no substantive source text')
            documents = [{'titulo': a.get_text(' ', strip=True), 'url': urljoin(post['link'], a['href'])}
                         for a in body.select('a[href]') if re.search(r'\.pdf(?:\?|$)', a['href'], re.I)]
            date = datetime.fromisoformat(post['date']).date().isoformat()
            rows.append({'id': f'los-alcazares-proy-wp-{post["id"]}', 'municipio': 'Los Alcázares',
                         'titulo': title, 'descripcion': description, 'url': post['link'],
                         'descripcion_source_url': post['link'], 'tipo': 'obra_publica',
                         'fecha': date, 'fecha_publicacion': date, 'source': 'ayuntamiento',
                         'origen': 'anuncio_inicio_obra_publica', 'documentos': documents})
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'rows': len(rows), 'status': 'ok'}

    def backfill_proyectos(self, out_jsonl):
        posts = []
        for page in range(1, 21):
            response = requests.get(self.API, params={'search': 'obra', 'per_page': 100, 'page': page, '_fields': 'id,title,content,date,link'},
                                    headers={'User-Agent': 'poc-bocm-los-alcazares/1.0'}, timeout=25)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError('Municipal API did not return a list')
            posts.extend(data)
            pages = int(response.headers['X-WP-TotalPages'])
            if page >= pages:
                break
            time.sleep(0.35)
        else:
            raise ValueError('Municipal API pagination exceeded safety limit; refusing truncated snapshot')
        rows = self.parse_posts(posts)
        if not rows:
            raise ValueError('No named building commencement notices found; review API and filters')
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return self._write(out_jsonl, [])

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
