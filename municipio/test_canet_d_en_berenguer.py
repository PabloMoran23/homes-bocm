import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.canet_d_en_berenguer import (
    BASE, PLANNING, PMUS, CanetDEnBerenguerAyuntamientoAdapter, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def document(name, key):
    return f'<a class="gIconLink" href="{BASE}/preview-document/{key}">{name}</a>'


def folder(name, count, key):
    return f'''<a class="gIconLink exp" onclick="wicketAjaxGet('?x={key}',null)">{name} ( {count} )</a>'''


def more(key):
    return f'''<button onclick="wicketAjaxGet('?x={key}',null)">Mostrar más</button>'''


class CanetTests(unittest.TestCase):
    def test_wicket_cdata_preserves_document_links(self):
        xml = '<?xml version="1.0"?><ajax-response><component><![CDATA[' + document('Plano B', 'b') + ']]></component><evaluate>do_not_execute()</evaluate></ajax-response>'
        entries, next_page = parse_page(xml)
        self.assertEqual(entries, [{'titulo': 'Plano B', 'url': BASE + '/preview-document/b'}])
        self.assertIsNone(next_page)

    def test_recursive_inventory_and_pagination_group_documents(self):
        adapter = CanetDEnBerenguerAyuntamientoAdapter('canet-d-en-berenguer')
        root = (folder('Borrador Catálago Bienes y Espacios Protegidos + DIE', 2, 'catalog')
                + folder('CONVENIO URBANISTICO Y PROYECTO URBANIZACION POLIGONO XX', 2, 'xx')
                + document('PROYECTO URBANIZACION POLIGONO XIII', 'xiii')
                + document('CONVENIO 2022-0008 [CONVENIO CESIÓN POLÍGONO XIII]', 'convenio')
                + document('Convenio urbanístico entre el Ayto. y Abanca', 'excluded'))
        pages = {
            PLANNING: (PLANNING, root),
            PLANNING + '?x=catalog': (BASE + '/catalog/', document('Memoria', 'memoria') + more('next')),
            BASE + '/catalog/?x=next': (BASE + '/catalog/?x=next', '<?xml version="1.0"?><ajax-response><component><![CDATA[' + document('Plano', 'plano') + more('next') + ']]></component></ajax-response>'),
            PLANNING + '?x=xx': (BASE + '/xx/', document('DECRETO 2026-0515 [Aprobación Proyecto de Urbanización Polígono XX) 02/03/2026', 'decreto') + folder('PROYECTO URBANIZACION POLIGONO XX', 1, 'project')),
            BASE + '/xx/?x=project': (BASE + '/project/', document('Proyecto', 'project')),
            PMUS: (PMUS, document('Certificado de acuerdo Pleno 19 junio 2026', 'agreement') + document('ANUNCIO DOGV 7 mayo 2024 Informe ambiental y territorial estratégico', 'environment')),
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda session, url: pages[url]):
                result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(result['rows'], 4)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 2, 2])
        self.assertEqual(rows[1]['fecha_aprob'], '2026-03-02')
        self.assertEqual(rows[3]['fecha_acuerdo'], '2026-06-19')
        self.assertIsNone(rows[3]['fecha_aprob'])
        self.assertTrue(all(r['fecha_publicacion'] is None and r['lat'] is None for r in rows))
        self.assertEqual(len({r['id'] for r in rows}), 4)

    def test_missing_pagination_fails_advertised_count(self):
        adapter = CanetDEnBerenguerAyuntamientoAdapter('canet-d-en-berenguer')
        with patch.object(adapter, '_fetch', return_value=(BASE + '/folder/', document('Memoria', 'a'))):
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                adapter._inventory(None, BASE + '/folder/', expected=2)

    def test_pagination_without_progress_fails(self):
        adapter = CanetDEnBerenguerAyuntamientoAdapter('canet-d-en-berenguer')
        with patch.object(adapter, '_fetch', side_effect=[(BASE + '/folder/', document('Memoria', 'a') + more('next')), (BASE + '/folder/?x=next', '<html>Login</html>')]):
            with self.assertRaisesRegex(ValueError, 'no progress'):
                adapter._inventory(None, BASE + '/folder/', expected=2)

    def test_empty_or_changed_source_does_not_overwrite(self):
        adapter = CanetDEnBerenguerAyuntamientoAdapter('canet-d-en-berenguer')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'records.jsonl'
            path.write_text('previous snapshot\n')
            with patch.object(adapter, '_fetch', return_value=(PLANNING, '<html>Login</html>')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('canet-d-en-berenguer')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46082')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        with self.assertRaises(NotImplementedError):
            CanetDEnBerenguerAyuntamientoAdapter(manifest.slug).backfill_licencias(Path('/tmp/unused-canet'))


if __name__ == '__main__':
    unittest.main()
