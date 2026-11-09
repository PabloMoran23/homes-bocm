import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.cedeira import CedeiraAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(title, body):
    return f'<main id="main"><h1>{title}</h1><div class="page__content">{body}</div></main>'


def inventory():
    return page('PLAN DE URBANISMO', ''.join(
        f'<h3><a href="{url}">{title}</a></h3>' for url, title in (
            ('interpretacion-2008/', 'INTERPRETACIÓN DO PXOM 2008'),
            ('interpretacion-2023/', 'INTERPRETACIÓN DO PXOM 2023'),
            ('modificacion-2/', 'MODIFICACIÓN PUNTUAL Nº2 DO PLAN XERAL DE ORDENACIÓN URBANA CENTRO DE SAÚDE'))))


class CedeiraTests(unittest.TestCase):
    def test_grouping_documents_and_date_semantics(self):
        entries = Adapter.parse_inventory(inventory())
        details = []
        for entry in entries:
            html = page(entry['titulo'], '<p>Acordo en 2023.</p>'
                '<a href="/wp-content/uploads/2025/07/plan-26.05.2023.pdf">APROBACIÓN INICIAL</a>'
                '<a href="/wp-content/uploads/2025/07/plan-26.05.2023.pdf">Plano</a>'
                '<a href="http://unrelated.example/image.jpg">Image</a>')
            details.append(Adapter.parse_detail(html, entry))
        rows = Adapter.assemble(entries, details)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['secciones']), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertEqual(rows[1]['documentos'][0]['titulos'], ['APROBACIÓN INICIAL', 'Plano'])
        self.assertEqual(rows[1]['fase'], 'aprobación inicial')
        for row in rows:
            for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])

    def test_reject_empty_changed_and_unreviewed_inventory(self):
        for html in ('<html>Login</html>', page('PLAN DE URBANISMO', '<a>Licencias</a>'),
                     page('PLAN DE URBANISMO', '<h3><a href="nuevo/">PLAN ESPECIAL NUEVO</a></h3>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_pagination_fails_in_inventory_and_detail(self):
        entry = Adapter.parse_inventory(inventory())[0]
        for nav in ('<a rel="next" href="/mas/">Más</a>', '<div class="page-numbers">2</div>',
                    '<a href="?paged=2">2</a>', '<a href="/mas/">Seguinte</a>'):
            with self.subTest(nav=nav), self.assertRaises(ValueError):
                Adapter.parse_inventory(inventory() + nav)
            with self.subTest(nav=nav), self.assertRaises(ValueError):
                Adapter.parse_detail(page(entry['titulo'], nav), entry)

    def test_detail_requires_matching_title_and_real_document_links(self):
        entry = Adapter.parse_inventory(inventory())[0]
        for html in (page('Wrong instrument', '<a href="a.pdf">Plan</a>'),
                     page(entry['titulo'], '<a href="form.html">Formulario</a>'),
                     page(entry['titulo'], '<a href="https://unofficial.example/plan.pdf">Plan</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_detail(html, entry)

    def test_manifest_loading_and_full_snapshot_update(self):
        manifest = load_manifest('cedeira')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        entries = Adapter.parse_inventory(inventory())
        pages = {SOURCE: inventory()}
        for i, entry in enumerate(entries):
            pages[entry['url']] = page(entry['titulo'], f'<a href="/{i}.pdf">Memoria</a>')
        with TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('stale record\n')
            result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(result['source_urls']), 4)
            adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')
            self.assertEqual((Path(directory) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
