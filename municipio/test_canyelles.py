import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.canyelles import (
    CanyellesAyuntamientoAdapter, PLANNING, SOURCE, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(body):
    return '<main><div class="journal-content-article">' + body + '</div></main>'


def doc(name, number=1):
    return (f'<a href="/documents/28721/0/document/{number:08d}-0000-0000-0000-000000000000">'
            f'Descarrega {name}</a>')


class CanyellesTests(unittest.TestCase):
    def test_inventory_filters_and_deduplicates(self):
        html = page(''.join(f'<a href="{SOURCE}/{slug}">{title}</a>' for slug, title in [
            ('works', 'Projecte d’obres'), ('works', 'Projecte d’obres'),
            ('forms', 'Sol·licitud de llicència'), ('sale', 'Alineació sòl'),
            ('heritage', 'Declaració de Bé Cultural'), ('news', 'Adjudicació del contracte')]))
        self.assertEqual(parse_inventory(html), [(SOURCE + '/works', 'Projecte d’obres')])

    def test_pagination_and_missing_content_fail(self):
        for html in ['<html>Login</html>', page('<a href="?page=2" rel="next">2</a>'),
                     page('<ul class="pagination"><li><a href="?page=2">2</a></li></ul>')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_detail(page('Generic service description'), SOURCE + '/works')

    def test_dates_and_document_provenance(self):
        docs, text, updates = parse_detail(page(doc('Projecte', 1) + doc('Projecte', 1) +
            '<p>Actualització: 23/02/2026 | Font: Propi ens</p>'), SOURCE + '/works')
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['source_urls'], [SOURCE + '/works'])
        self.assertEqual(updates, ['2026-02-23'])

    def test_snapshot_groups_mp2_and_retains_versions(self):
        u = SOURCE + '/modificacio-puntual-num.-2-del-poum-204'
        fixtures = {
            SOURCE: page(f'<a href="{u}">Modificació puntual núm. 2 del POUM</a>'),
            u: page(doc('Certificat aprovació inicial', 1) + doc('Documentació gràfica', 2) +
                    '<p>Actualització: 29/01/2025</p>'),
            PLANNING: page('<h3>MODIFICACIÓ PUNTUAL NÚM. 2 POUM- Verificació del Ple de '
                           "l’Ajuntament, en sessió ordinària de data 18.02.2026.</h3>" +
                           doc('Documentació gràfica', 2) + doc('Memòria verificada', 3) +
                           '<p>Actualització: 23/02/2026</p>'),
        }
        adapter = CanyellesAyuntamientoAdapter('canyelles')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=fixtures.__getitem__):
            out = Path(tmp) / 'projects.jsonl'
            adapter.backfill_proyectos(out)
            rows = [json.loads(x) for x in out.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            r = rows[0]
            self.assertEqual(len(r['documentos']), 3)
            self.assertEqual(r['documentos'][1]['source_urls'], [u, PLANNING])
            self.assertEqual(r['fecha_acuerdo'], '2026-02-18')
            self.assertIsNone(r['fecha_publicacion'])
            self.assertIsNone(r['fecha_aprob'])
            self.assertIsNone(r['lat'])
            before = out.read_bytes()
            adapter.update_proyectos(out, Path(tmp) / 'unused-state.json')
            self.assertEqual(before, out.read_bytes())

    def test_generic_instrument_and_atomic_failure(self):
        u = SOURCE + '/projectes-urbanistics-199'
        adapter = CanyellesAyuntamientoAdapter('canyelles')
        fixtures = {SOURCE: page(f'<a href="{u}">Projectes urbanístics</a>'),
                    u: page('<p>Projecte executiu 7a fase obres urbanització Les Palmeres:</p>' + doc('Projecte'))}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=fixtures.__getitem__):
            out = Path(tmp) / 'projects.jsonl'
            adapter.backfill_proyectos(out)
            self.assertIn('7a fase', json.loads(out.read_text())['titulo'])
            before = out.read_bytes()
            fixtures[u] = page('No documents')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(before, out.read_bytes())
            report = adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual(report['status'], 'disabled')

    def test_manifest_resolves(self):
        manifest = load_manifest('canyelles')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CanyellesAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
