import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.montoro import (
    MontoroAyuntamientoAdapter, SOURCE, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


AGENDA = 'https://montoro.es/wp-content/uploads/2024/09/PLAN-DE-ACCION-AGENDA-URBANA.pdf'
PMVS = 'https://montoro.es/plan-municipal-de-vivienda-y-suelo-de-montoro/'
FIRST = f'''<div id="main-content">
<a href="{AGENDA}">PLAN DE ACCIÓN DE AGENDA URBANA</a>
<a href="/modelo.pdf">Solicitud de licencia de obras</a>
<a href="/anuncio/">Licitación de obras</a>
<a href="/noticia/">Reparación de instalaciones</a>
<a href="https://drive.google.com/drive/folders/public">PLANEAMIENTO</a>
<div class="pagination"><a href="/urbanismo/page/2/?et_blog">Antiguas</a></div></div>'''
SECOND = f'<div id="main-content"><h2><a href="{PMVS}">PLAN MUNICIPAL DE VIVIENDA Y SUELO DE MONTORO</a></h2></div>'
DETAIL = '''<meta property="article:published_time" content="2023-09-15T11:31:35+00:00">
<meta property="article:modified_time" content="2024-09-05T10:23:16+00:00">
<div id="main-content"><h1>PLAN MUNICIPAL DE VIVIENDA Y SUELO DE MONTORO</h1>
<div class="et_pb_post_content"><p>Participación antes de proceder a su aprobación.</p>
<a href="/pmvs.pdf">Documento</a><a href="/pmvs.pdf">Duplicado</a>
<a href="/anexo.pdf">Anexo</a></div><a href="/otro.pdf">Fuera del instrumento</a></div>'''


class MontoroTests(unittest.TestCase):
    def test_inventory_filters_and_pagination(self):
        rows, pages = parse_inventory(FIRST)
        self.assertEqual([r['url'] for r in rows], [AGENDA])
        self.assertEqual(pages, [SOURCE + 'page/2/'])

    def test_group_documents_and_publication_semantics(self):
        row = parse_detail(DETAIL, PMVS)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_publicacion'], '2023-09-15')
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('fecha_acuerdo', row)
        self.assertTrue(all(d['provenance_url'] == PMVS for d in row['documentos']))

    def test_invalid_sources_fail(self):
        for html in ['<html>Maintenance</html>', DETAIL.replace('.pdf', '.html')]:
            with self.assertRaises(ValueError):
                parse_detail(html, PMVS)
        with self.assertRaises(ValueError):
            parse_inventory(FIRST.replace(AGENDA, 'https://example.org/plan.pdf'))
        with self.assertRaises(ValueError):
            parse_inventory('<p>Forbidden</p>')

    def test_live_path_follows_pages_and_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = MontoroAyuntamientoAdapter('montoro')
            output = Path(tmp) / 'proyectos.jsonl'
            pages = {SOURCE: FIRST, SOURCE + 'page/2/': SECOND, PMVS: DETAIL}
            with patch.object(adapter, '_fetch', side_effect=lambda session, url: pages[url]) as fetch:
                result = adapter.backfill_proyectos(output)
            self.assertEqual(result['count'], 2)
            self.assertEqual(fetch.call_count, 3)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(rows[1]['documentos']), 2)
            self.assertTrue(all(r['codigo_ine'] == '14043' for r in rows))
            self.assertTrue(all('lat' not in r and 'fase' not in r for r in rows))

    def test_repeated_pages_and_empty_inventory_fail_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = MontoroAyuntamientoAdapter('montoro')
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous output')
            for html in [FIRST, '<div id="main-content"></div>']:
                with patch.object(adapter, '_fetch', return_value=html):
                    with self.assertRaises(ValueError):
                        adapter.backfill_proyectos(output)
                self.assertEqual(output.read_text(), 'previous output')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('montoro')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MontoroAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
