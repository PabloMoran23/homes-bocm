"""Parser and adapter contract tests, independent of the live website."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.villamalea import (
    SOURCE_URLS, VillamaleaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def page(body, index=0):
    title = ('Plan de Ordenación Municipal', 'Modificaciones Puntuales del POM')[index]
    return f'<main><h1 class="entry-title">{title}</h1>{body}</main>'


def widget(body):
    return f'<div class="elementor-widget-text-editor">{body}</div>'


def link(label, filename):
    return f'<a href="/wp-content/uploads/{filename}.pdf">{label}</a>'


POM = page(widget(link('POM_Villamalea Normas', 'POM_Villamalea_Normas') +
                  link('REFUNDIDO_2016.pdf', 'REFUNDIDO_2016') +
                  link('Publicación Modificación Puntual 20', 'mp20')))
MODS = page(widget(link('Publicación Modificación Puntual Nº 16', 'mp16') +
                   link('Catálogo de Bienes y Espacios Protegidos Aprobado definitivamente 10-12-2024', 'catalogo') +
                   link('Anuncio aprobación de la interpretación C1 del POM', 'c1')) +
            widget('<h5>Modificación nº 18</h5>' +
                   link('Anuncio exposición pública Modificación Puntual nº 18', 'mp18') +
                   link('Planos comprimido parte 1', 'plano1') +
                   link('Memoria comprimido', 'memoria')), 1)


class ParserTests(unittest.TestCase):
    def test_group_pom_and_keep_modification_separate(self):
        rows = {r['id']: r for r in parse_inventory(POM, SOURCE_URLS[0])}
        self.assertEqual(set(rows), {'villamalea-pom', 'villamalea-mp-20'})
        self.assertEqual(len(rows['villamalea-pom']['documentos']), 2)
        self.assertEqual(len(rows['villamalea-mp-20']['documentos']), 1)

    def test_section_context_retains_all_mp18_documents(self):
        rows = {r['id']: r for r in parse_inventory(MODS, SOURCE_URLS[1])}
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(rows['villamalea-mp-18']['documentos']), 3)
        self.assertEqual(len(rows['villamalea-mp-16']['documentos']), 1)
        for row in rows.values():
            self.assertEqual(row['codigo_ine'], '02079')
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['geometry_status'], 'unavailable')
            self.assertFalse({'fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion',
                              'lat', 'lon', 'fase'} & row.keys())
            self.assertTrue(all(d['source_url'] == SOURCE_URLS[1] for d in row['documentos']))

    def test_duplicate_documents_and_navigation_excluded(self):
        doc = link('REFUNDIDO_2016.pdf', 'REFUNDIDO_2016')
        html = '<nav>' + link('Modificación Puntual 99', 'mp99') + '</nav>'
        rows = parse_inventory(html + page(widget(doc + doc)), SOURCE_URLS[0])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)

    def test_fail_closed_on_empty_unknown_host_and_pagination(self):
        bad = [page(''), '<main>Error</main>',
               page(widget(link('Nueva documentación', 'unknown'))),
               POM + '<a rel="next" href="?page=2">Next</a>',
               POM + '<div class="page-links">2</div>',
               POM.replace('/wp-content/uploads/mp20.pdf', 'https://other.example/mp20.pdf')]
        for html in bad:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE_URLS[0])

    def test_unrelated_forms_are_not_records(self):
        with self.assertRaises(ValueError):
            parse_inventory(page(widget(link('Solicitud licencia de obra mayor', 'solicitud'))), SOURCE_URLS[0])

    def test_manifest_and_live_fetch_contract(self):
        raw = load_yaml(Path('data/municipios/villamalea/manifest.yaml'))
        self.assertEqual(raw['codigo_ine'], '02079')
        self.assertEqual(raw['provincia'], 'Albacete')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['licencias']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        adapter = load_portal_adapter(load_manifest('villamalea'))
        self.assertIsInstance(adapter, VillamaleaAyuntamientoAdapter)
        session = Mock()
        session.headers = {}
        session.get.side_effect = [Mock(text=html, url=url) for html, url in zip((POM, MODS), SOURCE_URLS)]
        with TemporaryDirectory() as tmp, patch('municipio.adapters.villamalea.requests.Session') as factory:
            factory.return_value.__enter__.return_value = session
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['count'], 6)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 6)
            self.assertEqual([c.args[0] for c in session.get.call_args_list], list(SOURCE_URLS))
            self.assertTrue(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['disabled'])


if __name__ == '__main__':
    unittest.main()
