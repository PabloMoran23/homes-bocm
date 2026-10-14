import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent))
from license_territory import resolve_territory, territorial_raw
from replay_license_territory import replay_record, evidence_index
from sector_geometry.madrid_licencias_download import _download_url_for_year
from ingest import save_licencias
from export_web_data_from_supabase import export_licencias


class Cursor:
    def __init__(self, rows): self.rows = rows
    def execute(self, *args): pass
    def fetchall(self): return self.rows


def record(i, **kw):
    return {'id': i, 'anio_dataset': 2024, 'raw_json': {}, **kw}


class TerritoryTests(unittest.TestCase):
    def test_evidence_and_unknown(self):
        self.assertEqual(resolve_territory({'source': 'madrid-opendata'})['municipioCode'], '28079')
        for row in ({}, {'municipio_slug': 'madrid'}, {'lat': 40.4, 'lng': -3.7}):
            self.assertEqual(resolve_territory(row)['reason'], 'missing_municipality_provenance')
        self.assertEqual(resolve_territory({'fuente': 'portal', 'municipio_slug': 'valladolid'})['municipioCode'], '47186')
        self.assertEqual(resolve_territory({'source': 'madrid-opendata', 'municipio_slug': 'valladolid'})['reason'], 'conflicting_municipality_evidence')

    def test_original_and_replay_ignore_derived(self):
        original = {'id': 'x', 'source': 'madrid-opendata', 'objeto': 'vivienda'}
        normalized = territorial_raw(original)
        self.assertEqual({k: v for k, v in normalized.items() if k != '_territory'}, original)
        self.assertEqual(normalized, territorial_raw(normalized))
        t, raw = replay_record({'raw_json': {'_territory': {'municipioCode': '28079'}}}, {})
        self.assertEqual(t['status'], 'quarantined')
        self.assertEqual(raw['_territory'], t)

    def test_ingestion_does_not_restore_unknown_source_or_old_scope(self):
        conn = MagicMock()
        with patch('ingest._next_licencia_ids', return_value={'a': 1}), patch('ingest.execute_values') as execute:
            save_licencias([{'id': 'a', 'municipio_slug': 'madrid'}], conn=conn)
            sql, tuples = execute.call_args.args[1:3]
            self.assertIn('municipio_slug = EXCLUDED.municipio_slug', sql)
            self.assertIn('fuente = EXCLUDED.fuente', sql)
            self.assertIsNone(tuples[0][16])
            self.assertIsNone(tuples[0][17])
            self.assertEqual(tuples[0][14].adapted['_territory']['reason'], 'missing_municipality_provenance')
            save_licencias([{'id': 'a', 'municipio_slug': 'valladolid', 'source': 'portal'}], conn=conn)
            self.assertEqual(execute.call_args.args[2][0][16], 'valladolid')

    def test_historical_replay_requires_exact_registered_evidence(self):
        original = {'anio_dataset': 2024, 'ndp_edificio': '123', 'objeto': 'reforma'}
        evidence = {**original, 'source': 'madrid-opendata', '_territorial_origin': {
            'municipio_slug': 'madrid', 'adapter': 'madrid-opendata', 'url': _download_url_for_year(2024)}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'evidence.jsonl'
            path.write_text(json.dumps(evidence))
            index = evidence_index(path)
            territory, raw = replay_record({'raw_json': original}, index)
            self.assertEqual(territory['municipioCode'], '28079')
            self.assertEqual({k: raw[k] for k in original}, original)
            self.assertEqual(replay_record({'raw_json': {**original, 'objeto': 'obra distinta'}}, index)[0]['status'], 'quarantined')
            evidence['_territorial_origin']['url'] = 'https://example.org/not-evidence'
            path.write_text(json.dumps(evidence))
            with self.assertRaises(ValueError): evidence_index(path)

    def test_export_same_cut_and_change_removes_old_year(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            rows = [record(1, fuente='madrid-opendata', lat=40.4, lng=-3.7),
                    record(2, fuente='madrid-opendata'),
                    record(3, municipio_slug='valladolid', fuente='portal', lat=40.4, lng=-3.7),
                    record(4)]
            export_licencias(out, Cursor(rows), 2022)
            idx = json.loads((out/'madrid-licencias-index.json').read_text())
            self.assertEqual((idx['totalRows'], idx['withCoords'], idx['withoutCoords']), (2, 1, 1))
            self.assertEqual(sum(idx['byYear'].values()), idx['totalRows'])
            self.assertEqual(idx['excludedTerritory'], 2)
            exported = json.loads((out/'madrid-licencias-2024.json').read_text())
            self.assertEqual([r['id'] for r in exported], [1, 2])
            self.assertTrue(all(r['municipioCode'] == '28079' for r in exported))
            rows[0].update(fuente='portal', municipio_slug='valladolid')
            rows[1].update(fuente='portal', municipio_slug='valladolid')
            export_licencias(out, Cursor(rows), 2022)
            self.assertFalse((out/'madrid-licencias-2024.json').exists())
            self.assertEqual(json.loads((out/'madrid-licencias-index.json').read_text())['totalRows'], 0)

    def test_failure_preserves_valid_artifact_and_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            rows = [record(1, fuente='madrid-opendata')]
            export_licencias(out, Cursor(rows), 2022)
            before = (out/'madrid-licencias-2024.json').read_bytes()
            with patch('export_web_data_from_supabase.resolve_territory', side_effect=RuntimeError('policy unavailable')):
                with self.assertRaises(RuntimeError):
                    export_licencias(out, Cursor(rows), 2022)
            self.assertEqual(before, (out/'madrid-licencias-2024.json').read_bytes())
            export_licencias(out, Cursor(rows), 2022)
            self.assertEqual(before, (out/'madrid-licencias-2024.json').read_bytes())

if __name__ == '__main__': unittest.main()
