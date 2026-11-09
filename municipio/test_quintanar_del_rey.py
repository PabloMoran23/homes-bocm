"""Offline semantic and pagination tests; live evidence is produced separately."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.quintanar_del_rey import (
    SOURCE, QuintanarDelReyAyuntamientoAdapter, group_instruments, parse_page,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def card(title, key, date='25/03/2019', population='Quintanar del Rey', docs=None):
    docs = docs or [key + '.pdf']
    return f'''<article class="node--type-acuerdo-expediente-urbanistico" about="/urbanismo/acuerdos/{key}">
    <h3 class="article__title">{title}</h3>
    <div class="field--name-field-poblacion">{population}</div>
    <div class="field--name-field-expediente-fecha">{date}</div>
    <div class="field--name-field-expediente-fichero">{''.join(f'<a href="/sites/default/files/expedientes/{d}">{d}</a>' for d in docs)}</div>
    </article>'''


def page(cards, start=1, total=None, next_href=None):
    total = len(cards) if total is None else total
    following = f'<a rel="next" href="{next_href}">Siguiente</a>' if next_href else ''
    return f'<main>Mostrando {start} - {start + len(cards) - 1} de {total} expediente/s encontrados {"".join(cards)}{following}</main>'


class QuintanarTests(unittest.TestCase):
    def test_groups_documents_without_confusing_agreement_dates(self):
        html = page([
            card('CCI Modificación Puntual nº 6 POM de Quintanar del Rey (Cuenca)', 'cci'),
            card('CPOTU Cuenca Modificación Puntual nº 6 del POM de Quintanar del Rey', 'cpotu', '10/05/2019', docs=['acuerdo.pdf', 'anexo.pdf']),
            card('CPOTU Cuenca Aprobación definitiva Modificación Puntual nº 8 POM de Quintanar del Rey', 'mp8', '31/07/2020'),
            card('Calificación ampliación explotación avícola en Quintanar del Rey (Cuenca)', 'avicola'),
            card('Solicitud de licencia de obra', 'licencia'),
            card('Licitación obra piscina cubierta', 'contrato'),
            card('Modificación Puntual nº 6 POM de Quintanar del Rey', 'wrong', population='Quintanar de la Orden'),
        ])
        rows = group_instruments(parse_page(html)[0])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual([a['fecha_acuerdo'] for a in rows[0]['acuerdos']], ['2019-03-25', '2019-05-10'])
        self.assertIsNone(rows[0]['fecha_acuerdo'])
        self.assertEqual(rows[1]['fecha_acuerdo'], '2020-07-31')
        self.assertEqual(len(rows[1]['documentos']), 1)
        for row in rows:
            for key in ['fecha_publicacion', 'fecha_aprob', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[key])
            self.assertNotIn('fase', row)
            self.assertFalse(row['publication_ready'])

    def test_empty_changed_or_truncated_inventory_fails(self):
        for html in ['<main>Web en mantenimiento</main>', page([]), page([card('Something', 'x')], total=2)]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_page(html)
        with self.assertRaises(ValueError):
            group_instruments(parse_page(page([card('Formulario licencia', 'x')]))[0])
        with self.assertRaises(ValueError):
            parse_page(page([card('Something', 'x', docs=['../../../external.html'])]))

    def test_live_method_follows_pagination_and_keeps_filter(self):
        pages = [
            page([card('CCI Modificación Puntual nº5 del POM de Quintanar del Rey (Cuenca)', 'mp5')], total=2, next_href='?page=1'),
            page([card('CCI Modificación Puntual nº 6 POM de Quintanar del Rey (Cuenca)', 'mp6')], start=2, total=2),
        ]
        responses = [Mock(text=h, url=SOURCE) for h in pages]
        adapter = QuintanarDelReyAyuntamientoAdapter('quintanar-del-rey')
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.quintanar_del_rey.requests.get', side_effect=responses) as get:
            out = Path(tmp) / 'out.jsonl'
            report = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(report['count'], 2)
            self.assertEqual(len(out.read_text().splitlines()), 2)
            self.assertIn('page=1', get.call_args_list[1].args[0])
            self.assertIn('title=Quintanar+del+Rey', get.call_args_list[1].args[0])

    def test_pagination_repeated_range_rejected_before_output(self):
        html = page([card('CCI Modificación Puntual nº5 del POM de Quintanar del Rey', 'mp5')], total=2, next_href='?page=1')
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.quintanar_del_rey.requests.get', return_value=Mock(text=html, url=SOURCE)):
            out = Path(tmp) / 'out.jsonl'
            with self.assertRaises(ValueError):
                QuintanarDelReyAyuntamientoAdapter('quintanar-del-rey').backfill_proyectos(out)
            self.assertFalse(out.exists())

    def test_manifest_contract_and_disabled_licences(self):
        manifest = load_manifest('quintanar-del-rey')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('16175', 'Quintanar del Rey', 'Cuenca'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
