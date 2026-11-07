"""Parser contracts tested with small representative municipal HTML fragments."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_roda import (
    LaRodaAyuntamientoAdapter, PAI, POM, parse_pai, parse_pom,
)
from municipio.manifest import load_manifest


def article(body):
    return '<main><article><div class="entry-content">' + body + '</div></article></main>'


POM_HTML = article('''
<p>Puedes consultar el Plan de Ordenación Municipal de La Roda.</p>
<a href="http://laroda.es/pom/memoria.pdf">Memoria Informativa</a>
<a href="http://laroda.es/pom/memoria.pdf">PORTADA TOMO I</a>
<a href="/pom/normas.pdf">NORMAS URBANÍSTICAS</a>
<a href="https://example.org/pom/fake.pdf">Otro municipio</a>
<p>Las alegaciones serán admitidas hasta 07/04/2021.</p>
''')
PAI_HTML = article('''
<h2>Documentación general</h2>
<a href="/general.pdf">Plan de Actuación Integrado de La Roda</a>
<a href="/resolucion.pdf">Resolución concesión subvenciones</a>
<div><h2>Centro Sociocultural «La Báscula»</h2></div>
<a href="/bascula.pdf">Proyecto básico y de ejecución</a>
<a href="https://contrataciondelestado.es/wps/poc?id=123">Procedimiento de licitación</a>
<h2>Centro Joven y Deportivo</h2>
<a href="/escrita.pdf">Proyecto básico y de ejecución – Doc. escrita</a>
<a href="/grafica.pdf">Proyecto básico y de ejecución – Doc. gráfica</a>
''')


class LaRodaTests(unittest.TestCase):
    def test_pom_is_one_instrument_with_all_document_aliases(self):
        rows = parse_pom(POM_HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['titulos_fuente'], ['Memoria Informativa', 'PORTADA TOMO I'])
        self.assertEqual(row['documentos'][0]['source_url'], POM)
        self.assertEqual(row['codigo_ine'], '02069')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_building_documents_grouped_and_procurement_not_a_project(self):
        rows = parse_pai(PAI_HTML)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2])
        self.assertEqual(rows[0]['enlaces_relacionados'][0]['role'], 'licitacion_contexto')
        self.assertEqual(rows[1]['documentos'][1]['url'], 'https://laroda.es/grafica.pdf')
        self.assertTrue(all(r['fecha_aprob'] is None for r in rows))
        # Document version changes must not produce another instrument identity.
        updated = parse_pai(PAI_HTML.replace('/escrita.pdf', '/escrita-v2.pdf'))
        self.assertEqual(rows[1]['id'], updated[1]['id'])

    def test_no_document_count_truncation(self):
        extra = ''.join(f'<a href="/pom/{i}.pdf">Plano {i}</a>' for i in range(150))
        self.assertEqual(len(parse_pom(POM_HTML.replace('</div>', extra + '</div>'))[0]['documentos']), 152)

    def test_rejects_forms_menus_and_procurement_only(self):
        for parser in (parse_pom, parse_pai):
            for html in ('<nav>Plan de Ordenación Municipal de La Roda</nav>',
                         article('<h2>Centro Joven y Deportivo</h2><a href="/form.pdf">Solicitud de licencia</a>'),
                         article('<h2>Centro Joven y Deportivo</h2><a href="https://contrataciondelestado.es/wps/poc">Licitación</a>')):
                with self.subTest(parser=parser.__name__, html=html), self.assertRaises(ValueError):
                    parser(html)

    def test_pagination_fails_explicitly(self):
        for parser, html in ((parse_pom, POM_HTML), (parse_pai, PAI_HTML)):
            with self.assertRaisesRegex(ValueError, 'pagination'):
                parser(html + '<a rel="next" href="?page=2">Siguiente</a>')

    def test_refresh_and_failure_do_not_write_partial_inventory(self):
        adapter = LaRodaAyuntamientoAdapter('la-roda')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda url: POM_HTML if url == POM else PAI_HTML):
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 3)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 3)
            original = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[POM_HTML, '<html>login</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), original)

    def test_manifest_adapter_and_disabled_licences(self):
        manifest = load_manifest('la-roda')
        self.assertEqual(manifest.provincia, 'Albacete')
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.la_roda:LaRodaAyuntamientoAdapter')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = LaRodaAyuntamientoAdapter('la-roda').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
