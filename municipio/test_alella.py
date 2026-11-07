"""Offline parser/coverage regressions; no evidence files or network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.alella import (
    INVENTORY, AlellaAyuntamientoAdapter, parse_date, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest, load_yaml

TITLE = 'PROJECTE DE REFORMA DE CAN GAZA'
URL = 'https://alella.cat/fitxa.php?id=25951'


def inventory(identifier=25951, more=''):
    return f'''<title>Ajuntament d'Alella - Projectes obres</title>
    <div id="LLISTAT"><ul class="llista-fitxes"><li class="fitxes">
    <div class="titol"><a href="fitxa.php?id={identifier}">{TITLE}</a></div>
    </li></ul></div>{more}'''


def field(label, value):
    return f'<div class="camp_fitxa"><span class="txt_titol_fitxa">{label}</span><div class="cos_fitxa">{value}</div></div>'


def detail(title=TITLE, dates=True):
    fields = field('Nom del projecte', 'Reforma física de l’edifici')
    fields += field('Descripció', 'Projecte que acompanya un pla aprovat el 29 de maig de 2025.')
    if dates:
        fields += field('Data aprovació inicial', '12 de març de 2026')
        fields += field('Data aprovació definitiva', "Aprovat Junta de Govern 1 d'octubre de 2026")
        fields += field('Data anunci BOPB', 'Publicat el 25 de març de 2026')
    fields += field('Documents', '''<a href="ARXIUS/memoria.pdf">Memòria</a>
        <a href="ARXIUS/memoria.pdf"><img alt="Memòria"></a>
        <a href="ARXIUS/planols.pdf">Plànols</a>
        <a href="Ahttps://tauler.seu-e.cat/detall?id=1">Anunci</a>''')
    return f'''<div id="COLDRETA2"><div class="DOCUMENT">
    <div class="CAP"><div class="PUBLICACIO"><span class="DMA">06.10.2026</span></div></div>
    <div class="COS"><div class="TITOL"><span class="eltitol">{title}</span></div>
    <div id="FCBE">{fields}</div></div></div></div>
    <div>Informació relacionada: <a href="fitxa.php?id=999">Projecte aliè</a></div>'''


class AlellaTests(unittest.TestCase):
    def test_dates_and_document_grouping(self):
        row = parse_project(detail(), URL, TITLE)
        self.assertEqual(row['fecha_publicacion'], '2026-10-06')
        self.assertEqual(row['fecha_anuncio_bopb'], '2026-03-25')
        self.assertEqual(row['fecha_aprobacion_inicial'], '2026-03-12')
        self.assertEqual(row['fecha_aprobacion_definitiva'], '2026-10-01')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][2]['link_status'], 'malformed_source_href')
        self.assertEqual(row['documentos'][0]['source_field'], 'Documents')
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])

    def test_missing_approval_not_inferred_from_publication_or_narrative(self):
        row = parse_project(detail(dates=False), URL, TITLE)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fase'])
        self.assertEqual(row['fecha_publicacion'], '2026-10-06')

    def test_explicit_execution_phase(self):
        html = detail().replace('<div id="FCBE">', '<div class="sotstitol">En execució</div><div id="FCBE">')
        self.assertEqual(parse_project(html, URL, TITLE)['fase'], 'En execució')

    def test_reject_login_nav_and_mismatched_records(self):
        for html in ['<a href="fitxa.php?id=25951">Projecte</a>', '<form>Login</form>']:
            with self.assertRaises(ValueError):
                parse_inventory(html)
            with self.assertRaises(ValueError):
                parse_project(html, URL, TITLE)
        with self.assertRaises(ValueError):
            parse_project(detail('Unrelated news'), URL, TITLE)
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace(TITLE, 'Sol·licitud de llicència'))

    def test_dates_catalan_and_ambiguity(self):
        self.assertEqual(parse_date('23 gener de 2026'), '2026-01-23')
        self.assertEqual(parse_date("10 d’abril de 2024"), '2024-04-10')
        self.assertIsNone(parse_date('sense data'))
        with self.assertRaises(ValueError):
            parse_date('1 de maig de 2025 i 2 de maig de 2025')
        with self.assertRaises(ValueError):
            parse_date('31 de febrer de 2025')

    def test_pagination_and_multiple_pages(self):
        page2 = INVENTORY + '&pagina=2'
        html = inventory(more='<a href="#MENUCEL">Menú</a><a rel="next" href="fitxes.php?id=68&amp;pagina=2">Següent</a>')
        self.assertEqual(parse_inventory(html)[1], [page2])
        adapter = AlellaAyuntamientoAdapter()
        sources = {INVENTORY: html, page2: inventory(25952), URL: detail(),
                   'https://alella.cat/fitxa.php?id=25952': detail()}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=sources.__getitem__):
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['rows'], 2)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len({r['id'] for r in rows}), 2)

    def test_pagination_failure_preserves_existing_output(self):
        html = inventory(more='<a href="#MENUCEL">Menú</a><a rel="next" href="fitxes.php?id=68&amp;pagina=2">Següent</a>')
        adapter = AlellaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=html):
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with self.assertRaisesRegex(ValueError, 'Repeated inventory'):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')
        with self.assertRaises(ValueError):
            parse_inventory(inventory(more='<a rel="next" href="https://other.example/page2">Next</a>'))
        with self.assertRaises(ValueError):
            parse_inventory(inventory(more='<form><select name="pagina"></select></form>'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('alella')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08003')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = AlellaAyuntamientoAdapter().backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
