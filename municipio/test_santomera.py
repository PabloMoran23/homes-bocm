import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santomera import (
    SOURCE, SantomeraAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


INVENTORY = '''<main>
<h2>Plan General Municipal de Ordenación</h2>
<p>El PGMO de Santomera se aprobó de forma definitiva el 9 de septiembre de 2008.</p>
<a href="/planeamiento/pgmo/">VER EL PLAN</a>
<h2>Plan General Municipal de Ordenación - Modificación puntual nº 10</h2>
<a href="/wp-content/uploads/2026/01/final.pdf">Publicación en el BORM (21 de febrero de 2025)</a>
<a href="/wp-content/uploads/2026/01/pleno.pdf">Certificado de aprobación por el Pleno municipal (30 de enero de 2025)</a>
<a href="/wp-content/uploads/2026/01/inicial.pdf">Certificado del aprobación inicial del Pleno municipal (29 de febrero de 2024)</a>
<h2>Plan Parcial del Sector CB-01 (planeamiento en trámite – versión preliminar)</h2>
<a href="/planeamiento/plan-parcial-sector-cb01/">VER EL PLAN</a>
<h2>Instancias y solicitudes</h2><a href="/licencia.pdf">Solicitud de licencia</a>
</main>'''
DETAIL = '<main><h2>Plan General</h2><a href="/memoria.pdf">Memoria</a><a href="/planos.PDF">Planos</a></main>'


class SantomeraTests(unittest.TestCase):
    def test_groups_documents_and_preserves_semantic_dates(self):
        rows = parse_inventory(INVENTORY)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['fecha_aprob'], '2008-09-09')
        docs = rows[1]['documentos']
        self.assertEqual(len(docs), 3)
        self.assertEqual(docs[0]['fecha_publicacion'], '2025-02-21')
        self.assertEqual(docs[1]['fecha_acuerdo'], '2025-01-30')
        self.assertEqual(docs[2]['fecha_acuerdo'], '2024-02-29')
        self.assertNotIn('fecha_aprob', rows[1])
        self.assertEqual(rows[2]['documentos'], [])
        self.assertNotIn('fase', rows[2])
        self.assertFalse(any('Solicitud' in str(r) for r in rows))
        self.assertFalse(any('lat' in r or 'lon' in r for r in rows))

    def test_detail_retains_all_documents_and_provenance(self):
        docs = parse_detail(DETAIL, SOURCE + 'pgmo/')
        self.assertEqual(len(docs), 2)
        self.assertTrue(all(d['source_url'] == SOURCE + 'pgmo/' for d in docs))

    def test_rejects_empty_changed_paginated_and_external_sources(self):
        for html in ('<p>Unavailable</p>', '<main><h2>Plan General</h2></main>',
                     INVENTORY + '<a rel="next" href="?page=2">Next</a>',
                     INVENTORY.replace('/planeamiento/pgmo/', 'https://example.com/pgmo/')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_detail('<main>Sin documentos</main>', SOURCE)

    def test_snapshot_fetches_details_and_update_does_not_duplicate(self):
        adapter = SantomeraAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda url: INVENTORY if url == SOURCE else DETAIL):
                adapter.backfill_proyectos(output)
                before = output.read_text()
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
                self.assertEqual(output.read_text(), before)
                self.assertEqual(result['count'], 3)
                rows = [json.loads(line) for line in before.splitlines()]
                self.assertEqual(len(rows[0]['documentos']), 2)
                self.assertEqual(len(result['source_urls']), 3)

    def test_manifest_identity_and_disabled_features(self):
        raw = load_yaml(Path('data/municipios/santomera/manifest.yaml'))
        self.assertEqual((raw['codigo_ine'], raw['nombre'], raw['provincia']), ('30901', 'Santomera', 'Murcia'))
        self.assertIs(raw['schedule']['enabled'], False)
        self.assertIs(raw['geocode']['jitter_missing'], False)
        self.assertFalse(load_manifest('santomera').licencias.enabled)


if __name__ == '__main__':
    unittest.main()
