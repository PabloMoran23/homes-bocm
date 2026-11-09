"""Offline parser/contract tests. Run --live to save a real local extraction."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.moraleja import (
    SOURCE, MoralejaAyuntamientoAdapter, group_notices, instrument,
    parse_inventory, parse_notice,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def board(titles, pager=''):
    return '<div class="view-id-tablon_de_anuncios view-display-id-listado"><div class="view-content"><ul>' + ''.join(
        f'<li class="item"><p class="semibold"><a href="{SOURCE}/{slug}">{title}</a></p></li>'
        for slug, title in titles) + '</ul></div><ul class="pager">' + pager + '</ul></div>'


def detail(node, publication, body, document='proyecto.pdf'):
    docs = f'<section id="archivos"><a href="/sites/default/files/{document}">Proyecto</a></section>' if document else ''
    return f'<div class="node-anuncios-generales" id="node-{node}"><div class="main-node-content"><span class="fecha-publicacion">{publication}</span><p>{body}</p></div>{docs}</div>'


class MoralejaTests(unittest.TestCase):
    def test_families_and_exclusions(self):
        self.assertEqual(instrument('PUBLICACION EN EL DOE MODIFICACION PUNTUAL 5 DEL PLAN GENERAL MUNICIPAL')[0], 'pgm-mod-5')
        self.assertEqual(instrument('MODIFICACIÓN PUNTUAL NÚM. 5 DE LA ORDENACIÓN DEL PLAN GENERAL MUNICIPAL')[0], 'pgm-mod-5')
        self.assertEqual(instrument('REPARCELACIÓN DE UNIDAD DE ACTUACIÓN SAU-10')[0], 'reparcelacion-sau-10')
        for title in ('LICITACIÓN ASFALTADO DE VÍAS PÚBLICAS', 'SOLICITUD DEL PROYECTO', 'ORDENANZA FISCAL', 'JORNADA DE ACCESIBILIDAD'):
            self.assertIsNone(instrument(title))
        with self.assertRaises(ValueError):
            instrument('MODIFICACIÓN DEL PLAN GENERAL MUNICIPAL')

    def test_dates_and_grouping(self):
        title = 'PLAN GENERAL MUNICIPAL'
        n = {'titulo': title, 'url': SOURCE + '/plan'}
        first = parse_notice(detail(1, 'Mar, 17/05/2022 - 11:56',
            'Plan General Municipal, aprobada definitivamente por acuerdo de la Comisión de Urbanismo y Ordenación del Territorio de Extremadura de 22/12/2022.'), n)
        self.assertEqual(first['fecha_publicacion'], '2022-05-17')
        self.assertEqual(first['fecha_acuerdo'], '2022-12-22')
        self.assertIn('advertencia_fechas', first)
        second = parse_notice(detail(2, '26/06/2019', 'Aprobación provisional del Plan General Municipal.'), {**n, 'url': SOURCE + '/provisional'})
        self.assertNotIn('fecha_acuerdo', second)
        provisional = parse_notice(detail(4, '26/06/2019', 'APROBADO PROVISIONALMENTE por el Pleno de la Corporación con fecha 12 de mayo de 2022.'), n)
        self.assertEqual(provisional['fecha_acuerdo'], '2022-05-12')
        self.assertIn('advertencia_fechas', provisional)
        rows = group_notices([first, second, first])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['anuncios']), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)  # same file, both provenances
        self.assertNotIn('fecha_aprob', rows[0])
        self.assertNotIn('lat', rows[0])
        with self.assertRaises(ValueError):
            group_notices([parse_notice(detail(3, '01/02/2019', 'Plan', document=None), n)])
        with self.assertRaises(ValueError):
            parse_notice('<html>error</html>', n)

    def test_full_pagination_and_atomic_failure(self):
        pages = {
            SOURCE: board([('plan', 'PLAN GENERAL MUNICIPAL')], f'<li><a href="{SOURCE}?page=1">2</a></li>'),
            SOURCE + '?page=1': board([('sau', 'PROYECTO DE REPARCELACION SAU-10 MORALEJA')]),
            SOURCE + '/plan': detail(1, '17/05/2022', 'Plan General Municipal.'),
            SOURCE + '/sau': detail(2, '01/02/2019', 'Proyecto reparcelación SAU-10.'),
        }
        adapter = MoralejaAyuntamientoAdapter('moraleja')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
                result = adapter.update_proyectos(output, Path(tmp) / 'unused-state')
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(result['rows'], 2)
            original = output.read_text()
            pages[SOURCE + '?page=1'] = pages[SOURCE]
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), original)
            adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')
        with self.assertRaises(ValueError):
            parse_inventory('<html>unavailable</html>', SOURCE)
        with self.assertRaises(ValueError):
            parse_inventory(board([('p', 'PLAN GENERAL MUNICIPAL')], '<a href="https://example.org/?page=1">2</a>'), SOURCE)

    def test_manifest(self):
        manifest = load_manifest('moraleja')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '10128')
        self.assertEqual(manifest.provincia, 'Cáceres')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), MoralejaAyuntamientoAdapter)


def live(folder):
    folder.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest('moraleja')
    adapter = load_portal_adapter(manifest)
    adapter.config['evidence_dir'] = str(folder / 'captures')
    report = adapter.backfill_proyectos(folder / 'proyectos.jsonl')
    rows = [json.loads(line) for line in (folder / 'proyectos.jsonl').read_text().splitlines()]
    assert rows and len(rows) == report['live_records']
    report['extracted_at'] = datetime.now(timezone.utc).isoformat()
    report['document_urls'] = sorted({d['url'] for row in rows for d in row['documentos']})
    report['municipio'] = {'codigo_ine': '10128', 'nombre': 'Moraleja', 'provincia': 'Cáceres'}
    (folder / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--live':
        live(Path(sys.argv[2] if len(sys.argv) > 2 else 'evidence'))
    else:
        unittest.main()
