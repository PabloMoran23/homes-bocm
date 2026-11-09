import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.balmaseda import BASE, PAGES, SOURCE, BalmasedaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml


def page(links):
    return '<main id="main-content"><h1>PGOU</h1><div id="x_content__ControlWrapper_RichHtmlField">' + links + '</div></main>'


class BalmasedaTests(unittest.TestCase):
    def test_inventory_and_phase_changes(self):
        html = page('<a href="PGOU_Fase0.aspx"></a><a href="pgou_fase6.aspx"></a>')
        self.assertEqual(set(Adapter.parse_inventory(html)), {0, 6})
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(html.replace('fase6', 'fase7'))
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(html.replace('</main>', '<a href="?page=2">Siguiente</a></main>'))

    def test_links_provenance_and_fail_closed(self):
        docs, children = Adapter.parse_page(page('<a href="../docs/a b.pdf">Plano</a><a href="child.aspx">Anexos</a>'), BASE + PAGES + 'root.aspx')
        self.assertTrue(docs[0]['url'].endswith('/docs/a%20b.pdf'))
        self.assertEqual(children, [BASE + PAGES + 'child.aspx'])
        self.assertEqual(docs[0]['source_page'], BASE + PAGES + 'root.aspx')
        embedded = '<main id="main-content"><div id="SectionBody"><div id="x_content__ControlWrapper_RichHtmlField"></div><div class="ms-rte-embedcode"><a href="child.aspx">Documentación</a></div><div class="viewMore"><a href="/es-ES/Servicios/Urbanismo/">Ir a lista</a></div></div></main>'
        self.assertEqual(Adapter.parse_page(embedded, BASE + PAGES + 'root.aspx')[1], children)
        for html in ('<h1>Login</h1>', page(''), page('<a href="https://example.org/a.pdf">PDF</a>'), page('<a rel="next" href="more.aspx">Más</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_page(html, SOURCE)

    def test_crawl_groups_cycle_and_shared_documents(self):
        phase = BASE + PAGES + 'pgou_fase6.aspx'
        child = BASE + PAGES + 'child.aspx'
        fixtures = {
            SOURCE: page('<a href="pgou_fase6.aspx">Fase 6</a>'),
            phase: page('<a href="../a.pdf">Certificado de pleno - Aprobación inicial</a><a href="child.aspx">Documentación</a>'),
            child: page('<a href="../a.pdf">Certificado</a><a href="../b.pdf">Normativa</a><a href="pgou_fase6.aspx">Volver</a>'),
        }
        adapter = Adapter('balmaseda')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=lambda session, url: fixtures[url]) as fetch:
            path = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['rows'], 1)
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(rows[0]['documentos'][0]['source_pages'], [phase, child])
            self.assertIsNone(rows[0]['fecha_publicacion'])
            self.assertIsNone(rows[0]['fecha_acuerdo'])
            self.assertIsNone(rows[0]['geometry'])
            self.assertEqual(rows[0]['fase'], 'aprobación inicial')
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=lambda session, url: fixtures[url].replace('Aprobación inicial', 'Documento')):
            path = Path(directory) / 'out.jsonl'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertFalse(path.exists())

    def test_manifest(self):
        manifest = load_manifest('balmaseda')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('48090', 'Balmaseda', 'Bizkaia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
