"""Offline parser and adapter contract tests; fixtures model municipal markup."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.aretxabaleta import AretxabaletaAyuntamientoAdapter as Adapter, SOURCE, explicit_dates
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def page(body, title='Estudio de detalle del Área 16'):
    return f'<h1 class="documentFirstHeading">{title}</h1><div id="parent-fieldname-text">{body}</div>'


def inventory(extra=''):
    return page(f'''<h3>Normas en tramitación</h3><ul>
    <li><a href="{SOURCE}/estudio">ESTUDIO DE DETALLE DEL ÁREA 16</a></li>
    <li><a href="{SOURCE}/estudio">ESTUDIO DE DETALLE DEL ÁREA 16</a></li>
    <li><a href="{SOURCE}/ordenanza">ORDENANZA DE OBRAS MENORES</a></li>
    <li><a href="{SOURCE}/noticia">Anuncio de contratación de obras</a></li></ul>
    <h3>Normas tramitadas</h3>{extra}''')


class ParserTests(unittest.TestCase):
    def test_inventory_deduplicates_and_excludes_forms_news(self):
        rows = Adapter.parse_inventory(inventory())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['tipo'], 'estudio_de_detalle')
        self.assertEqual(rows[0]['situacion_inventario'], 'en_tramitacion')

    def test_pagination_and_missing_content_fail(self):
        for html in [inventory('<a rel="next" href="?b_start:int=20">Más</a>'),
                     inventory('<div class="pagination"></div>'),
                     inventory('<a href="?page=2">2</a>'),
                     inventory('<a href="?b_start:int=20">Más</a>'),
                     '<h1>Error</h1>', page('<h3>Normas en tramitación</h3>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_group_documents_and_preserve_date_roles(self):
        entry = Adapter.parse_inventory(inventory())[0]
        html = page('''<h3>Aprobación</h3>
        <p>En sesión de 10 de mayo de 2023 se aprobó definitivamente el estudio de detalle del Área 16.</p>
        <p>El acuerdo se publicó en el BOG el 31 de mayo de 2023.</p>
        <p>El plazo finaliza el 15 de junio.</p>
        <p><a href="/es/dokumentuak/plan.pdf">Plano</a>
        <a href="/es/dokumentuak/plan.pdf">Plano repetido</a>
        <a href="https://uzt.gipuzkoa.eus/PortalV/r/0/13/AAAA.X">Documento urbanístico</a>
        <a href="https://uzt.gipuzkoa.eus/PortalV/7.00/Default.aspx">Alegaciones</a>
        <a href="https://example.org/no.pdf">No oficial</a></p>''')
        row = Adapter.parse_detail(html, entry)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['eventos'][0]['tipo_fecha'], 'fecha_acuerdo')
        self.assertEqual(row['eventos'][0]['fechas'], ['2023-05-10'])
        self.assertEqual(row['eventos'][1]['tipo_fecha'], 'fecha_publicacion')
        self.assertEqual(row['eventos'][1]['fechas'], ['2023-05-31'])
        self.assertEqual(len(row['eventos']), 2)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['lat'])
        self.assertIn('aprobó definitivamente', row['descripcion'])
        self.assertTrue(all(d['source_url'] == entry['url'] for d in row['documentos']))
        self.assertEqual(row['id'], Adapter.parse_detail(html, entry)['id'])

    def test_narrative_only_instrument_is_not_fabricated_document(self):
        entry = Adapter.parse_inventory(inventory())[0]
        row = Adapter.parse_detail(page('<p>El Ayuntamiento ha iniciado la redacción del estudio de detalle para modificar la ordenación y ampliar el frontón existente.</p>'), entry)
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['documentacion_status'], 'solo_ficha_municipal')
        self.assertEqual(row['eventos'], [])
        with self.assertRaises(ValueError):
            Adapter.parse_detail(page('<p>Sin información.</p>'), entry)
        with self.assertRaises(ValueError):
            Adapter.parse_detail(page('<p>Texto de ordenanza</p>', 'Ordenanza municipal'), entry)

    def test_agreement_and_publication_in_same_paragraph(self):
        entry = Adapter.parse_inventory(inventory())[0]
        html = page('<p>En sesión de 18 de diciembre de 2024 se aprobó definitivamente la modificación. El acuerdo se ha publicado en el BOG el 13 de enero de 2025. Se acordó su inicio el 17 de enero del 2024 (B.O.G.) junto a su programa de participación para esta consulta pública.</p>')
        events = Adapter.parse_detail(html, entry)['eventos']
        self.assertEqual([e['tipo_fecha'] for e in events], ['fecha_acuerdo', 'fecha_publicacion', 'fecha_acuerdo'])
        self.assertEqual([e['fechas'] for e in events], [['2024-12-18'], ['2025-01-13'], ['2024-01-17']])

    def test_dates_do_not_infer_year_or_allow_invalid_dates(self):
        self.assertEqual(explicit_dates('BOG el 31 de mayo y firma 11 de octubre del 2023'), ['2023-10-11'])
        self.assertEqual(explicit_dates('Fecha del acuerdo: 11/05/2020'), ['2020-05-11'])
        with self.assertRaises(ValueError):
            explicit_dates('31/02/2024')

    def test_live_path_traverses_every_inventory_detail(self):
        inv = inventory(f'<a href="{SOURCE}/otro">PLAN GENERAL DE ORDENACIÓN URBANA DE ARETXABALETA</a>')
        def response(url, **kwargs):
            from requests import Response
            r = Response()
            r.status_code = 200
            r.url = url
            r.headers['Content-Type'] = 'text/html; charset=utf-8'
            title = 'Plan General de Ordenación Urbana de Aretxabaleta' if url.endswith('/otro') else 'Estudio de detalle del Área 16'
            r._content = (inv if url == SOURCE else page('<p>Documento municipal de planeamiento: instrumento en elaboración para ordenar los espacios y edificaciones del municipio de Aretxabaleta.</p>', title)).encode()
            r.encoding = 'utf-8'
            return r
        with tempfile.TemporaryDirectory() as directory, patch('requests.Session.get', side_effect=response) as get, patch('time.sleep'):
            path = Path(directory) / 'proyectos.jsonl'
            adapter = Adapter('aretxabaleta')
            report = adapter.backfill_proyectos(path)
            self.assertEqual(report['rows'], 2)
            self.assertEqual(get.call_count, 3)
            self.assertEqual(len(path.read_text().splitlines()), 2)
            # A failed refresh must preserve the last good snapshot.
            previous = path.read_text()
            with patch.object(Adapter, 'parse_detail', side_effect=ValueError('source changed')):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(path.read_text(), previous)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_manifest_contract(self):
        manifest = load_manifest('aretxabaleta')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '20013')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)


if __name__ == '__main__':
    unittest.main()
