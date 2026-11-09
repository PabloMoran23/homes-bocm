"""Offline parser and adapter contract tests; fixtures model the municipal markup."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.borja import BorjaAyuntamientoAdapter, SOURCE, parse_projects
from municipio.manifest import load_manifest


def document(name, label):
    return (f'<li>{label}<strong><a href="http://borja.cumpletransparencia.es/'
            f'Entidades/borja/Ordenacion/{name}.pdf">(Consultar información)</a></strong></li>')


def inventory(groups=None):
    if groups is None:
        groups = ('<p><strong>Plan Integral del Casco Histórico de Borja</strong></p><ul>'
                  + document('memoria', 'Memoria')
                  + '<li>Planos<ul>' + document('parte1', 'Planos 1')
                  + document('parte2', 'Planos 2') + '</ul></li></ul>')
    return ('<header>Ayuntamiento de Borja</header><main>'
            '<h3>Plan General de Ordenación Urbana</h3><div class="mainHtmlContent">'
            '<p>Puede consultar el Plan General de Ordenación Urbana de Borja en SIUa.</p>'
            + groups + '</div><div class="msgPublicacion">Última actualización el jueves, '
            '13 de junio de 2024 a 16:27</div></main>')


class BorjaTests(unittest.TestCase):
    def test_grouped_documents_and_provenance(self):
        rows = parse_projects(inventory())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['titulo'], 'Plan Integral del Casco Histórico de Borja')
        self.assertEqual([d['titulo'] for d in row['documentos']], ['Memoria', 'Planos 1', 'Planos 2'])
        self.assertEqual(row['codigo_ine'], '50055')
        self.assertEqual(row['provincia'], 'Zaragoza')
        for doc in row['documentos']:
            self.assertEqual(doc['source_url'], SOURCE)
            self.assertTrue(doc['url'].startswith('https://'))
            self.assertTrue(doc['url_original'].startswith('http://'))

    def test_no_inferred_dates_phase_or_geometry(self):
        row = parse_projects(inventory().replace('memoria.pdf', 'MEMORIA_APROBADO_2024.pdf'))[0]
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertIn('13 de junio de 2024', row['fuente_actualizacion_texto'])
        self.assertFalse(row['publication_ready'])

    def test_second_instrument_keeps_its_own_documents(self):
        html = inventory().replace('</div><div class="msgPublicacion">',
            '<p>Plan de Prueba de Borja</p><ul>' + document('otro', 'Memoria segunda')
            + '</ul></div><div class="msgPublicacion">')
        rows = parse_projects(html)
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertTrue(rows[1]['documentos'][0]['url'].endswith('/otro.pdf'))

    def test_empty_forms_and_changed_pages_fail(self):
        for html in ('', '<h1>Access denied</h1>', inventory(''),
                     inventory('<p>Solicitud de licencia</p><ul>' + document('form', 'Modelo') + '</ul>'),
                     inventory().replace('Ayuntamiento de Borja', 'Ayuntamiento de Otro')):
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                parse_projects(html)

    def test_pagination_fails_explicitly(self):
        for pagination in ('<a rel="next" href="?page=2">2</a>',
                           '<ul class="pagination"><li>2</li></ul>',
                           '<a href="?page=2">Siguiente</a>'):
            with self.subTest(pagination=pagination), self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_projects(inventory() + pagination)

    def test_ungrouped_documents_fail(self):
        with self.assertRaisesRegex(ValueError, 'ungrouped'):
            parse_projects(inventory().replace('</div><div class="msgPublicacion">',
                document('unassigned', 'Otro') + '</div><div class="msgPublicacion">'))

    def test_wrong_document_municipality_fails(self):
        with self.assertRaises(ValueError):
            parse_projects(inventory().replace('/Entidades/borja/', '/Entidades/otro/'))

    def test_duplicate_links_do_not_duplicate_documents_or_ids(self):
        html = inventory().replace('</ul></li>', document('parte1', 'Duplicado') + '</ul></li>')
        self.assertEqual(len(parse_projects(html)[0]['documentos']), 3)
        self.assertEqual(parse_projects(html)[0]['id'], parse_projects(inventory())[0]['id'])

    def test_backfill_update_and_invalid_pdf(self):
        adapter = BorjaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            def fetch(url, limit):
                return inventory().encode() if url == SOURCE else b'%PDF-1.6\nfixture'
            with patch.object(adapter, '_fetch', side_effect=fetch):
                result = adapter.backfill_proyectos(out)
                self.assertEqual(result['count'], 1)
                self.assertEqual(len(result['source_urls']), 4)
                before = out.read_text()
                self.assertEqual(len(json.loads(before)['documentos'][0]['sha256']), 64)
                adapter.update_proyectos(out, Path(tmp) / 'state.json')
                self.assertEqual(out.read_text(), before)
            with patch.object(adapter, '_fetch', side_effect=lambda url, limit:
                              inventory().encode() if url == SOURCE else b'<html>error</html>'):
                with self.assertRaisesRegex(ValueError, 'not a PDF'):
                    adapter.backfill_proyectos(out)
                self.assertEqual(out.read_text(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('borja')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Zaragoza')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(BorjaAyuntamientoAdapter().backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
