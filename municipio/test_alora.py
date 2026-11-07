"""Offline parser and adapter contract tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.alora import (
    AloraAyuntamientoAdapter, SOURCE, parse_menu, parse_plan,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

MENU = '''<a href="/Ayuntamiento/nnss">Normas Subsidiarias</a>
<a href="/Ayuntamiento/pgom">Avance del PGOM</a>
<ul><li><a href="javascript:void(0)">Estudio detalle Calle Mirasierra →</a><ul>
<li><a href="/Ayuntamiento/Informacion/mirasierra/ANEXO.pdf">Anexo</a></li>
<li><a href="/Ayuntamiento/Informacion/mirasierra/PLANOS.pdf">Planos</a></li>
<li><a href="/Ayuntamiento/Informacion/mirasierra/MEMORIA_EXPOSITIVA.pdf">Memoria Expositiva</a></li>
</ul></li></ul>
<a href="/Ayuntamiento/Urbanismo/DR_obras.pdf">Declaración responsable</a>
<a href="/Inicio/N.asp?IdArticulo=123">Noticia ajena</a>'''
PGOM = '''<table><tr><td><b>PUBLICACIÓN EN LA WEB DEL DOCUMENTO DE AVANCE DEL PGOM</b>
Conforme al Acuerdo de Sesión de pleno de 11/Jul/24 (Bop 12/Agos/24)
que aprobó la consideración del borrador como avance del Plan General de Ordenación Municipal.
</td></tr></table>
<a href="BORRADOR_PLAN_(EAE).pdf">Borrador del plan (EAE) Álora</a>
<a href="Comunicacion_validez.pdf">Comunicación de validez</a>'''
NNSS = '''<h1>NORMAS SUBSIDIARIAS DE PLANEAMIENTO DE ÁLORA</h1>
<a href="alineaciones.pdf">Alineaciones</a><a href="normasurbanisticas.pdf">Normas Urbaníticas</a>
<a href="normasurbanisticas.pdf">Normas Urbaníticas</a>
<a href="/Ayuntamiento/Informacion/mirasierra/ANEXO.pdf">Anexo ajeno</a>'''


class AloraTests(unittest.TestCase):
    def test_menu_groups_and_excludes_forms_and_news(self):
        pages, rows = parse_menu(MENU)
        self.assertEqual(set(pages), {'pgom', 'nnss'})
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertNotIn('fecha_aprob', rows[0])
        self.assertNotIn('lat', rows[0])
        self.assertFalse(rows[0]['publication_ready'])

    def test_dates_are_agreement_and_bop_not_approval(self):
        row = parse_plan(PGOM, 'https://www.alora.es/ayuntamiento/pgom/', 'pgom')
        self.assertEqual(row['fecha_acuerdo'], '2024-07-11')
        self.assertEqual(row['fecha_publicacion'], '2024-08-12')
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('fecha', row)
        self.assertEqual(row['fase'], 'avance')
        self.assertEqual(len(row['documentos']), 2)
        no_dates = parse_plan(PGOM.replace('11/Jul/24 (Bop 12/Agos/24)', 'fecha no indicada'),
                              row['url'], 'pgom')
        self.assertNotIn('fecha_acuerdo', no_dates)
        self.assertNotIn('fecha_publicacion', no_dates)

    def test_documents_deduplicate_and_do_not_leak_between_instruments(self):
        row = parse_plan(NNSS, 'https://www.alora.es/ayuntamiento/nnss/', 'nnss')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all('/nnss/' in d['url'] for d in row['documentos']))
        self.assertNotIn('fase', row)
        self.assertNotIn('fecha_aprob', row)

    def test_fail_closed_on_empty_navigation_only_external_or_pagination(self):
        for html in ['', MENU.replace('/Ayuntamiento/pgom', '/other'),
                     MENU + '<a rel="next" href="?page=2">Siguiente</a>',
                     MENU.replace('/Ayuntamiento/pgom', 'https://example.org/Ayuntamiento/pgom')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_menu(html)
        for html in ['', '<a href="normas.pdf">Normas</a>']:
            with self.assertRaises(ValueError):
                parse_plan(html, SOURCE, 'nnss')
        with self.assertRaises(ValueError):
            parse_plan(PGOM.replace('BORRADOR_PLAN_(EAE).pdf', '/other.pdf'),
                       'https://www.alora.es/ayuntamiento/pgom/', 'pgom')

    def test_manifest_registry_and_snapshot(self):
        manifest = load_manifest('alora')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('29012', 'Álora', 'Málaga'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, AloraAyuntamientoAdapter)
        def fetch(url, name):
            return {'Inicio': MENU, 'pgom': PGOM, 'nnss': NNSS}[name], url
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=fetch):
            out = Path(tmp) / 'proyectos.jsonl'
            report = adapter.backfill_proyectos(out)
            self.assertEqual(report['count'], 3)
            first = out.read_text()
            rows = [json.loads(line) for line in first.splitlines()]
            self.assertEqual(len({r['id'] for r in rows}), 3)
            adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(first, out.read_text())
            licenses = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(licenses)['disabled'])
            self.assertEqual(licenses.read_text(), '')


if __name__ == '__main__':
    unittest.main()
