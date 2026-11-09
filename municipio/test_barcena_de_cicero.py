"""Offline structural fixtures model the observed municipal HTML, not live results."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.barcena_de_cicero import (
    BASE, URBANISMO, BarcenaDeCiceroAyuntamientoAdapter,
    discover_pgou, parse_nnss, parse_pgou,
)
from municipio.manifest import load_manifest, load_yaml

PGOU_URL = BASE + 'informacion-publica-pgou.html'
HOME = '<a href="/informacion-publica-pgou.html">PGOU EXPOSICIÓN PÚBLICA PGOU</a>'
NNSS = '''<h3>NORMAS SUBSIDIARIAS DE BÁRCENA DE CICERO</h3>
<div class="from-fckdiv">
<a href="/ftp//DOCUMENTOS/NNSS/normas-urbansticas.pdf">Normas Urbanisticas</a>
<a href="/ftp//DOCUMENTOS/NNSS/memoria-de-informacin.pdf">Memoria de Información</a>
<a href="/ftp//DOCUMENTOS/NNSS/normas-urbansticas.pdf">Duplicado</a>
<a href="/formularios/licencia.pdf">SOLICITUD DE LICENCIA DE OBRA</a></div>
<a href="/ftp/DOCUMENTOS/PGOU_2025/resto.zip">Otro instrumento fuera del bloque</a>'''
PGOU = '''<title>INFORMACIÓN PÚBLICA DE LA MODIFICACIÓN DEL PLAN GENERAL DE ORDENACIÓN URBANA
APROBADO PROVISIONALMENTE - Ayuntamiento de Bárcena de Cicero</title>
<div class="single-page"><div class="meta">21 de Abril de 2025</div></div>
<div class="from-fckdiv"><p>Mediante acuerdo adoptado por el Pleno del Ayuntamiento en su sesión
ordinaria celebrada en fecha de 31 de marzo de 2025 se ha acordado disponer la apertura de un nuevo
trámite de información pública de la modificación del Plan General de Ordenación Urbana aprobado
provisionalmente mediante acuerdo de veintiocho de junio de 2021.</p>
<a href="/ftp/DOCUMENTOS/PGOU_2025/1.Memoria.zip">MEMORIA PGOU</a>
<a href="/ftp/DOCUMENTOS/PGOU_2025/2.planosinf.zip">PLANOS DE INFORMACIÓN PGOU</a></div>'''


class ParserTests(unittest.TestCase):
    def test_nnss_grouping_and_semantics(self):
        row = parse_nnss(NNSS)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '39009')
        self.assertEqual(row['url'], URBANISMO)
        self.assertTrue(all(d['source_url'] == URBANISMO for d in row['documentos']))
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('fecha_acuerdo', row)
        self.assertNotIn('lat', row)
        self.assertFalse(row['publication_ready'])

    def test_pgou_dates_and_document_isolation(self):
        row = parse_pgou(PGOU, PGOU_URL)
        self.assertEqual(row['fecha_publicacion'], '2025-04-21')
        self.assertEqual(row['fecha_acuerdo'], '2025-03-31')
        self.assertIn('apertura', row['fecha_acuerdo_tipo'])
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('fase', row)
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all('/PGOU_' in d['url'] for d in row['documentos']))
        self.assertIn('veintiocho de junio de 2021', row['descripcion'])
        no_date = PGOU.replace('<div class="meta">21 de Abril de 2025</div>', '')
        self.assertNotIn('fecha_publicacion', parse_pgou(no_date, PGOU_URL))

    def test_discovery_deduplicates_and_rejects_ambiguity(self):
        self.assertEqual(discover_pgou(HOME + HOME), PGOU_URL)
        with self.assertRaises(ValueError):
            discover_pgou(HOME + HOME.replace('informacion-publica-pgou', 'otro-pgou'))
        with self.assertRaises(ValueError):
            discover_pgou(HOME.replace('/informacion-publica-pgou.html', 'https://example.org/pgou'))

    def test_empty_or_changed_inventory_fails(self):
        for html in ('', '<a href="/solicitud.pdf">Solicitud de licencia</a>',
                     NNSS.replace('/DOCUMENTOS/NNSS/', '/formularios/')):
            with self.assertRaises(ValueError):
                parse_nnss(html)
        with self.assertRaises(ValueError):
            parse_pgou(PGOU.replace('/DOCUMENTOS/PGOU_', '/formularios/'), PGOU_URL)

    def test_pagination_never_silently_truncated(self):
        for extra in ('<a rel="next" href="?page=2">2</a>',
                      '<div class="pagination"><a href="?page=2">2</a></div>',
                      '<a href="?page=2">Siguiente</a>'):
            with self.assertRaises(ValueError):
                parse_nnss(NNSS + extra)
            with self.assertRaises(ValueError):
                parse_pgou(PGOU + extra, PGOU_URL)

    def test_adapter_full_refresh_and_failure_keeps_output(self):
        adapter = BarcenaDeCiceroAyuntamientoAdapter('barcena-de-cicero')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[NNSS, HOME, PGOU]):
                result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['count'], 2)
            self.assertEqual(len({r['id'] for r in rows}), 2)
            original = out.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[NNSS, HOME, '<html>Changed</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(original, out.read_bytes())
            lic = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(lic)['disabled'])
            self.assertEqual(lic.read_text(), '')

    def test_manifest_contract(self):
        manifest = load_manifest('barcena-de-cicero')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '39009')
        self.assertEqual(manifest.provincia, 'Cantabria')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertEqual(manifest.portal.adapter.rsplit(':', 1)[1], BarcenaDeCiceroAyuntamientoAdapter.__name__)


if __name__ == '__main__':
    unittest.main()
