import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.zumaia import SOURCE, ZumaiaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest


def inventory(entries, total=None, extra=''):
    rows = ''.join(f'<tr><td>{number}</td><td><a href="{SOURCE}/{slug}">{title}</a></td>'
                   '<td>Planes de Urbanismo</td><td>02/01/2024</td><td>26/02/2024</td></tr>'
                   for number, slug, title in entries)
    return ('<div id="content-core"><a href="#tab-abiertos">Abiertos (0)</a>'
            '<div id="tab-abiertos"><table></table></div>'
            f'<a href="#tab-cerrados">Cerrados ({len(entries) if total is None else total})</a>'
            f'<div id="tab-cerrados"><table>{rows}</table></div></div>{extra}')


ENTRIES = [
    ('2023HPXA0002', 'delimitacion', 'Delimitación de Unidad de Ejecución U.E. 4 (aprobación inicial)'),
    ('2023HPXA0002', 'estudio', 'Estudio de detalle del AU 04 (aprobación inicial)'),
    ('2024HBLH0007', 'solicitud', 'SOLICITUD DE LICENCIA DE INSTALACIÓN DE ASCENSOR'),
    ('2023KCRE0002', 'credito', '5ª modificación de crédito municipal'),
    ('2023HIOZ0004', 'ruido', 'Mapa de ruido de Zumaia (aprobación inicial)'),
    ('2021HUUU0002', 'torreaga', 'Proyecto de urbanización del área de Torreaga'),
]


def detail(row, docs=True):
    return (f'<h1 class="documentFirstHeading">{row["titulo"]}</h1><div id="content-core">'
            f'<h2 id="file-number">Número de expediente: {row["expediente"]}</h2>'
            '<dl class="contract-dates"><dt>Fecha publicación</dt><dd>02/01/2024</dd>'
            '<dt>Último día</dt><dd>26/02/2024</dd></dl>'
            + ('<dl class="contract-information"><dd><a href="memoria.pdf">Memoria</a></dd></dl>'
               '<dl class="contract-files"><dt>Proyecto</dt><dd>'
               '<a href="memoria.pdf/@@download/file/Memoria.pdf">Memoria.pdf</a></dd>'
               '<dt>Anuncio BOG</dt><dd><a href="anuncio.pdf">anuncio.pdf</a></dd></dl>' if docs else '')
            + '</div>')


class ZumaiaTests(unittest.TestCase):
    def test_selection_identity_and_date_semantics(self):
        rows = Adapter.parse_inventory(inventory(ENTRIES))
        self.assertEqual(len(rows), 3)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[0]['expediente'], rows[1]['expediente'])
        self.assertEqual(rows[0]['fecha_publicacion'], '2024-01-02')
        for row in rows:
            self.assertIsNone(row['fecha'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['geometry'])
        self.assertEqual(rows[0]['fase'], 'aprobación inicial')
        self.assertIsNone(rows[2]['fase'])

    def test_documents_grouped_with_aliases_and_provenance(self):
        row = Adapter.parse_inventory(inventory(ENTRIES))[0]
        result = Adapter.parse_detail(detail(row), row)
        self.assertEqual(len(result['documentos']), 2)
        doc = result['documentos'][0]
        self.assertEqual(len(doc['enlaces']), 2)
        self.assertEqual(doc['titulo'], 'Proyecto')
        self.assertIn('/@@download/', doc['url'])
        self.assertEqual(doc['source_url'], row['url'])
        self.assertFalse(result['publication_ready'])

    def test_pagination_and_incomplete_tabs_rejected(self):
        for html in (inventory(ENTRIES, total=99),
                     inventory(ENTRIES, extra='<a rel="next" href="?b_start:int=20">2</a>'),
                     inventory(ENTRIES, extra='<div class="pagination">2</div>'),
                     '<div id="content-core"></div>'):
            with self.subTest(html=html[-100:]), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_missing_documents_changed_identity_and_dates_rejected(self):
        row = Adapter.parse_inventory(inventory(ENTRIES))[0]
        for html in (detail(row, False), detail(row).replace('2023HPXA0002', '2023HPXA9999'),
                     detail(row).replace('02/01/2024', '03/01/2024')):
            with self.assertRaises(ValueError):
                Adapter.parse_detail(html, row)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(inventory([ENTRIES[2]]))

    def test_snapshot_and_failure_preserve_previous_output(self):
        adapter = Adapter()
        source = inventory(ENTRIES)
        rows = Adapter.parse_inventory(source)
        pages = {SOURCE: source, **{row['url']: detail(row) for row in rows}}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
                self.assertEqual(adapter.backfill_proyectos(out)['rows'], 3)
                self.assertEqual(adapter.update_proyectos(out, Path(directory) / 'state.json')['rows'], 3)
            before = out.read_text()
            self.assertEqual(len([json.loads(line) for line in before.splitlines()]), 3)
            pages[rows[-1]['url']] = detail(rows[-1], False)
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__), self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), before)
            self.assertEqual(adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest_loads_exact_municipality_and_adapter(self):
        manifest = load_manifest('zumaia')
        self.assertEqual(manifest.nombre, 'Zumaia')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.zumaia:ZumaiaAyuntamientoAdapter')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
