import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.argamasilla_de_alba import (
    SOURCE, ArgamasillaDeAlbaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


# Small independent fixture preserving the municipal section/card structure.
HTML = '''<main><h2>Normativa urbanística</h2>
<div class="card-file"><p class="card-file__title"><a href="/sector.pdf">Sector Residencial "El Rincón"</a></p>
<time datetime="23-04-2021">23 abril 2021</time><a href="/sector.pdf">Descargar PDF</a></div>
<div class="card-file"><p class="card-file__title"><a href="/ordenanza.pdf">Ordenanza de Edificación</a></p></div>
<div class="card-file"><p class="card-file__title"><a href="/licencia.pdf">Solicitud de licencia</a></p></div>
<h2>Plan de Ordenación Municipal</h2>
<p>Anuncio de 15/12/2021 publicado en el DOCM Nº 244 de fecha 22 de diciembre de 2021.</p>
<p><a href="/docm.pdf">Anuncio D.O.C.M.</a></p>
<p>Aprobado definitivamente el Plan de Ordenación Municipal de Argamasilla de Alba mediante acuerdo de la Comisión de fecha 23 de mayo de 2019, y previamente aprobado inicialmente el 4 de julio de 2018.</p>
<p><a href="/bop.pdf">Anuncio B.O.P.</a></p><p><a href="https://drive.google.com/drive/folders/example">Documentación</a></p>
<h2>Área de Actuación A3</h2>
<h3>Proyecto de reparcelación voluntaria del área de actuación A3</h3>
<p>Certificado del acuerdo de la Junta de Gobierno Local de fecha 18 de Septiembre de 2025.</p>
<p><a href="/certificado.pdf">Certificado</a></p>
<p>Anuncio de 07/07/2025 sobre información pública.</p><p><a href="/informacion.pdf">Anuncio D.O.C.M.</a></p>
<p><a href="https://drive.google.com/file/d/example/view">Proyecto</a></p>
<h3>Proyecto de urbanización del área A3</h3>
<p>Acuerdo de 06/10/2025, de la Junta de Gobierno Local de fecha 23 de septiembre de 2025, por la que se aprueba definitivamente el Proyecto de Urbanización del área A3.</p>
<p><a href="/urbanizacion.pdf">Anuncio B.O.P.</a></p>
<h2>Últimas Noticias</h2><a href="/news">Inauguración</a>
<div class="pagination"><a rel="next" href="?newsPage=2">Más noticias</a></div>
<iframe src="https://maps.google.com/?q=39,-3"></iframe></main>'''


class ParserTests(unittest.TestCase):
    def test_grouping_exclusions_and_document_boundaries(self):
        rows = parse_inventory(HTML)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({r['id'] for r in rows}), 4)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 3, 3, 1])
        self.assertEqual(rows[-1]['documentos'][0]['url'], 'https://www.argamasilladealba.es/urbanizacion.pdf')
        self.assertNotIn('news', json.dumps(rows))
        self.assertIn('Certificado del acuerdo', rows[2]['documentos'][0]['contexto'])
        self.assertEqual(parse_inventory(HTML)[0]['id'], rows[0]['id'])

    def test_date_semantics_and_no_geometry(self):
        sector, pom, reparcelacion, urbanizacion = parse_inventory(HTML)
        self.assertEqual(sector['fecha_catalogo'], '2021-04-23')
        self.assertIsNone(sector['fecha_publicacion'])
        self.assertIsNone(sector['fecha_aprob'])
        self.assertEqual(pom['fecha_aprob'], '2019-05-23')
        self.assertEqual(pom['fecha_publicacion'], '2021-12-22')
        self.assertEqual(reparcelacion['fecha_acuerdo'], '2025-09-18')
        self.assertNotIn('fase', reparcelacion)
        self.assertIsNone(reparcelacion['fecha_publicacion'])
        self.assertEqual(urbanizacion['fecha_aprob'], '2025-09-23')
        self.assertIsNone(urbanizacion['fecha_publicacion'])
        for row in (sector, pom, reparcelacion, urbanizacion):
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['lon'])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '13019')

    def test_fail_closed_on_layout_loss_documents_or_pagination(self):
        for html in ('<main>Sin datos</main>', '<html>login</html>',
                     HTML.replace('Área de Actuación A3', 'Otra sección'),
                     HTML.replace('<h2>Plan de Ordenación Municipal</h2>', '<h2>Plan de Ordenación Municipal</h2><a rel="next" href="?page=2">2</a>'),
                     HTML.replace('<a href="/urbanizacion.pdf">Anuncio B.O.P.</a>', ''),
                     HTML.replace('/certificado.pdf', 'https://unrelated.example/certificado.pdf')):
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_adapter_live_contract_update_and_error_preserves_output(self):
        adapter = ArgamasillaDeAlbaAyuntamientoAdapter('argamasilla-de-alba')
        response = Mock(url=SOURCE, text=HTML)
        with tempfile.TemporaryDirectory() as tmp, patch(
            'municipio.adapters.argamasilla_de_alba.requests.get', return_value=response
        ) as get:
            out = Path(tmp, 'proyectos.jsonl')
            result = adapter.update_proyectos(out, Path(tmp, 'state.json'))
            self.assertEqual(result['count'], 4)
            self.assertEqual(len(out.read_text().splitlines()), 4)
            get.assert_called_once()
            old = out.read_text()
            response.text = '<main>source changed</main>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), old)
            response.url = 'https://unrelated.example/'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(adapter.backfill_licencias(Path(tmp, 'licencias.jsonl'))['disabled'], True)

    def test_manifest(self):
        manifest = load_manifest('argamasilla-de-alba')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '13019')
        self.assertEqual(manifest.provincia, 'Ciudad Real')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
