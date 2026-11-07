import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.campo_de_criptana import (
    BASE, CampoDeCriptanaAyuntamientoAdapter, discover_details, parse_detail,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def page(*sections):
    return '<div class="articleContent"><h2>Plan Parcial de Mejora Agrícola</h2>' + ''.join(sections) + '</div>'


def section(label, *files):
    links = ''.join(f'<a href="/wp-content/uploads/{f}.pdf">{f}</a>' for f in files)
    return ('<section class="elementor-top-section"><div class="elementor-container">'
            f'<div class="elementor-column">{label}</div>'
            f'<div class="elementor-column">{links}</div></div></section>')


class CampoDeCriptanaTests(unittest.TestCase):
    def test_group_documents_and_separate_amendments(self):
        html = page(section('Plan Parcial Agrícola 2007', 'tecnico', 'planos'),
                    section('', 'diligencia'),
                    section('Modificación Puntual Parcelas 2012', 'modificacion'),
                    section('Modificación Puntual Ampliación 2024', 'ampliacion'),
                    section('', 'acuerdo', 'normativa'))
        rows = parse_detail(html, BASE + '/plan/', 'Plan Parcial de Mejora Agrícola')
        self.assertEqual([len(r['documentos']) for r in rows], [3, 1, 3])
        self.assertEqual(len({r['id'] for r in rows}), 3)
        for r in rows:
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase'):
                self.assertIsNone(r[field])
            self.assertEqual(r['codigo_ine'], '13028')
            self.assertFalse(r['publication_ready'])
            self.assertTrue(all(d['source_url'] == BASE + '/plan/' for d in r['documentos']))

    def test_single_instrument_with_many_documents(self):
        html = page(section('TRPOM 2022', 'diligencia'), section('Normas', 'normas'), section('Planos', 'mapa')).replace('h2', 'h3')
        rows = parse_detail(html, BASE + '/trpom/', 'Texto Refundido Plan de Ordenación Municipal')
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        # Neither upload years nor section-update text are dates of this instrument.
        self.assertIsNone(rows[0]['fecha_publicacion'])

    def test_navigation_forms_news_not_records(self):
        with self.assertRaises(ValueError):
            discover_details('<nav><a href="/plan/">Plan Parcial de Mejora</a></nav>')
        with self.assertRaises(ValueError):
            discover_details('<div class="articleContent"><a href="/form/">Solicitud licencia</a></div>')
        with self.assertRaises(ValueError):
            parse_detail(page('<a href="/news.pdf">Anuncio</a>'), BASE + '/plan/', 'Plan Parcial de Mejora')
        with self.assertRaises(ValueError):
            parse_detail(page(section('', 'technical')), BASE + '/plan/', 'Plan Parcial de Mejora')

    def test_discovery_excludes_mixed_and_procurement_inventories(self):
        html = '<div class="articleContent">' + ''.join(
            f'<a href="/{p}/">{t}</a>' for p,t in [
                ('trpom', 'Texto Refundido Plan de Ordenación Municipal 2022'),
                ('mod', 'Modificación Puntual 2/2025'),
                ('pending', 'Modificaciones puntuales en tramitación'),
                ('works', 'Proyectos y pliegos licitación de las obras públicas')]) + '</div>'
        self.assertEqual(set(discover_details(html)), {BASE + '/trpom/', BASE + '/mod/'})

    def test_pagination_and_foreign_documents_fail(self):
        for marker in ('<a rel="next" href="/page/2">2</a>', '<div class="pagination"></div>', '<button>Cargar más</button>'):
            with self.assertRaises(ValueError):
                discover_details(page(marker))
        with self.assertRaises(ValueError):
            parse_detail(page(section('Plan Parcial Agrícola', 'one')).replace('/wp-content/uploads/one.pdf', 'https://other.es/doc.pdf'), BASE + '/plan/', 'Plan Parcial de Mejora')

    def test_failure_preserves_existing_snapshot(self):
        adapter = CampoDeCriptanaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[page('<a href="/plan/">Plan Parcial de Mejora Agrícola</a>'), ValueError('unavailable')]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('campo-de-criptana')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '13028')
        self.assertEqual(manifest.provincia, 'Ciudad Real')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, CampoDeCriptanaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'licencias.jsonl'
            with patch('requests.Session') as network:
                self.assertTrue(adapter.backfill_licencias(out)['disabled'])
                network.assert_not_called()
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
