
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.begur import BegurAyuntamientoAdapter as Adapter, WORKS, DRAFT, OFFICIAL
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def page(title, body='', extra=''):
    return f'<div class="centerpad"><h1>{title}</h1><div class="content-postTitle">{body}</div>{extra}</div>'


class BegurTests(unittest.TestCase):
    def test_inventory_deduplicates_and_rejects_empty_or_pagination(self):
        a = f'<a href="{WORKS}test/">Work</a>'
        html = page('Projectes municipals en execució', extra=f'<section class="sub-servei-list">{a}{a}</section>')
        self.assertEqual(Adapter.parse_inventory(html), [WORKS + 'test/'])
        for suffix in ['<a rel="next" href="?page=2">2</a>', '<div class="page-links">2</div>']:
            with self.assertRaisesRegex(ValueError, 'pagination'):
                Adapter.parse_inventory(html + suffix)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(page('Projectes municipals en execució'))

    def test_physical_work_dates_and_provenance(self):
        body = "<p>Les obres del projecte estan en fase d'execució; suspeses fins el 15 de setembre.</p><a href='https://drive.google.com/drive/folders/example'>Projecte</a>"
        row = Adapter.parse_work(page('Font de Baix', body), WORKS + 'font/')
        self.assertEqual(row['codigo_ine'], '17013')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['lat'])
        self.assertIn('suspeses', row['descripcion'])
        self.assertEqual(row['documentos'][0]['source_url'], WORKS + 'font/')
        with self.assertRaises(ValueError):
            Adapter.parse_work(page('Formulari', '<p>Sol·licitud de llicència</p>'), WORKS + 'form/')

    def test_draft_groups_documents_and_does_not_infer_approval_from_roadmap(self):
        section = '<div class="accordion_in"><div class="acc_head">Etapa 1. Avanç</div><a href="https://ajbegur.sharepoint.com/example">Documentació</a><a href="https://begur.cat/example.pdf">Anunci</a></div>'
        empty_stage = '<div class="accordion_in"><div class="acc_head">Etapa 4. Aprovacions provisional i definitiva</div></div>'
        row = Adapter.parse_draft(page('POUM en tràmit', '<p>En procés de redacció i tramitació.</p>', section + empty_stage))
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fase'], 'en redacció i tramitació')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(row['url'], DRAFT)
        self.assertEqual(row['documentos'][0]['seccion'], 'Etapa 1. Avanç')

    def test_official_requires_registry_and_does_not_guess_dates(self):
        body = '<a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/205091">Normes</a>'
        row = Adapter.parse_official(page('POUM-oficial', body))
        self.assertEqual(row['url'], OFFICIAL)
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['fecha_aprob'])
        with self.assertRaises(ValueError):
            Adapter.parse_official(page('POUM-oficial', 'Sense registre'))

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('begur')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Begur', 'Girona', '17013'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = adapter.backfill_licencias(output)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(output.read_text(), '')

    def test_snapshot_failure_preserves_previous_output(self):
        adapter = Adapter('begur')
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous snapshot\n')
            with patch.object(adapter, '_fetch', return_value='<html>Unexpected redirect</html>'):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(output.read_text(), 'previous snapshot\n')


if __name__ == '__main__':
    unittest.main()
