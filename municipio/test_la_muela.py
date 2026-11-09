import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_muela import LaMuelaAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest


DETAIL_URL = 'https://lamuela.org/memoria-justificativa-de-modificacion-del-pgou/'


def archive(extra='', title='Memoria Justificativa de Modificación del PGOU', url=DETAIL_URL):
    return f'''<div class="the7-simple-widget-posts" data-pagination-mode="standard" data-post-limit="-1">
    <article><a class="post-title" href="{url}">{title}</a>
    <time datetime="2024-08-28T08:33:50+02:00">28 de agosto de 2024</time></article></div>{extra}'''


def detail(expediente='1808/2024', document='memoria.pdf'):
    # Reduced municipal markup, preserving the distinctions between dates.
    return f'''<div class="elementor-widget-theme-post-content">
    <p><strong>Expediente n.º:</strong> {expediente}<br>Memoria Justificativa<br>
    Procedimiento: Planeamiento General (Modificación)</p>
    <p>Asunto: Modificación del PGOU de La Muela relativa a terrenos reservados a equipamiento,
    con cambio de destino deportivo, ampliado a un destino educativo .<br>
    Se redacta la documentación en virtud Providencia de Alcaldía de fecha de 19 de agosto del 2024,
    y del informe de secretaria de fecha 28 de junio del 2024.</p>
    <a href="/wp-content/uploads/{document}">Memoria Justificativa</a>
    <a href="/wp-content/uploads/bop.pdf">BOPZ</a></div>
    <aside><a href="/unrelated.pdf">Unrelated attachment</a></aside>'''


class LaMuelaTests(unittest.TestCase):
    def test_instrument_documents_and_date_semantics(self):
        notices, pages = LaMuelaAyuntamientoAdapter.parse_inventory(archive())
        row = LaMuelaAyuntamientoAdapter.parse_detail(detail(), notices[0])
        self.assertEqual(row['expediente'], '1808/2024')
        self.assertEqual(row['fecha_publicacion'], '2024-08-28')
        for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all(d['url_procedencia'] == DETAIL_URL for d in row['documentos']))
        self.assertEqual(pages, [])
        self.assertFalse(row['publication_ready'])

    def test_unrelated_notices_and_forms_are_excluded(self):
        for title in ('CORTE DE CALLE VIERNES 06/02/2026.', 'Afecciones de Tráfico',
                      'Solicitud de modificación del PGOU', 'Licitación proyecto de urbanización'):
            self.assertEqual(LaMuelaAyuntamientoAdapter.parse_inventory(archive(title=title))[0], [])

    def test_source_drift_and_undocumented_notice_fail(self):
        notice = LaMuelaAyuntamientoAdapter.parse_inventory(archive())[0][0]
        for html in ('<html>Unavailable</html>', detail().replace('1808/2024', 'sin expediente'),
                     '<div class="elementor-widget-theme-post-content">Expediente n.º: 1/2024 Asunto: Plan general</div>'):
            with self.assertRaises(ValueError):
                LaMuelaAyuntamientoAdapter.parse_detail(html, notice)
        with self.assertRaises(ValueError):
            LaMuelaAyuntamientoAdapter.parse_inventory('<html>Consent required</html>')
        with self.assertRaises(ValueError):
            LaMuelaAyuntamientoAdapter.parse_inventory(archive().replace('standard', 'ajax'))

    def test_paginated_crawl_groups_same_instrument_and_isolates_others(self):
        page2 = SOURCE + 'page/2/'
        url2, url3 = 'https://lamuela.org/segundo-anuncio/', 'https://lamuela.org/otro-plan/'
        pages = {
            SOURCE: archive(f'<div class="pagination"><a href="{page2}">2</a></div>'),
            page2: archive(url=url2).replace('</div>', '') + archive(url=url3).split('>', 1)[1],
            DETAIL_URL: detail(), url2: detail(document='plano.pdf'), url3: detail('900/2025', 'otro.pdf'),
        }
        adapter = LaMuelaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
            path = Path(directory) / 'rows.jsonl'
            report = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(report['rows'], 2)
        self.assertEqual(fetch.call_count, 5)
        first = next(r for r in rows if r['expediente'] == '1808/2024')
        other = next(r for r in rows if r['expediente'] == '900/2025')
        self.assertEqual(len(first['publicaciones']), 2)
        self.assertEqual(len(first['documentos']), 3)
        self.assertNotIn('plano.pdf', ' '.join(d['url'] for d in other['documentos']))

    def test_empty_inventory_does_not_replace_previous_output(self):
        adapter = LaMuelaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', return_value=archive(title='Corte de calle')):
            path = Path(directory) / 'rows.jsonl'
            path.write_text('previous snapshot\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot\n')

    def test_manifest_contract(self):
        manifest = load_manifest('la-muela')
        self.assertEqual(manifest.provincia, 'Zaragoza')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.la_muela:LaMuelaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
