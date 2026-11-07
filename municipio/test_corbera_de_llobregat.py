"""Offline semantic and inventory regression tests; no live network needed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.corbera_de_llobregat import (
    BASE, INVENTORY, CorberaDeLlobregatAyuntamientoAdapter as Adapter, inventory_links,
)


def page(title, body='', extra=''):
    return f'<main><div id="readspeakerPage"><h1>{title}</h1>{body}<span class="updated">Darrera actualització: 23.07.2026 | 13:21</span></div>{extra}</main>'


def doc(name, path):
    return f'<a href="/media/repository/{path}.pdf">{name}</a>'


class CorberaTests(unittest.TestCase):
    def test_dossier_groups_documents_and_distinguishes_dates(self):
        title = 'Projecte de reparcel·lació de la UA de Can Margarit aprovat definitivament per la Junta de Govern Local de 22 de juny de 2026'
        html = page(title, extra='<div class="documents">' + doc('Memòria', 'mem') + doc('Annex', 'annex') + doc('Memòria', 'mem') + '</div>')
        rows = Adapter.parse_dossier(html, INVENTORY + '/can-margarit')
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(len(r['documentos']), 2)
        self.assertEqual(r['fecha_acuerdo'], '2026-06-22')
        self.assertEqual(r['fecha_actualizacion_pagina'], '2026-07-23')
        self.assertIsNone(r['fecha_publicacion'])
        self.assertIsNone(r['geometry'])
        self.assertFalse(r['publication_ready'])

    def test_document_label_phase_without_invented_approval_date(self):
        html = page('Projecte de reparcel·lació i urbanització de la Servera', extra='<div class="documents">' + doc('Aprovació definitiva del Projecte', 'cert') + '</div>')
        r = Adapter.parse_dossier(html, INVENTORY + '/servera')[0]
        self.assertEqual(r['fase'], 'aprobación definitiva')
        self.assertIsNone(r['fecha_aprob'])

    def test_fire_instruments_grouped_separately(self):
        html = page("Ca n'Armengol", '<div class="ddbbtext"><h2>Projecte de reducció de la franja exterior</h2><blockquote>' + doc('Memòria', 'FP/mem') + doc('Pressupost', 'FP/press') + '</blockquote><h2>Projecte de reducció en parcel·les municipals</h2><blockquote>' + doc('Memòria', 'PP/mem') + '</blockquote></div>')
        rows = Adapter.parse_fire_projects(html, INVENTORY + '/incendis/armengol', INVENTORY + '/incendis', 'Aprovació inicial dels projectes executius')
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertTrue(all(r['fase'] == 'aprobación inicial' and r['fecha_acuerdo'] is None for r in rows))

    def test_inventory_deduplicates_responsive_menus(self):
        link = '<div class="widgetMenu"><a href="/ajuntament/urbanisme-i-territori/example">Example</a></div>'
        self.assertEqual(inventory_links(page('Urbanisme i territori', link * 2), INVENTORY, '.widgetMenu a[href]'), [INVENTORY + '/example'])

    def test_empty_layout_headings_cannot_hide_documents(self):
        body = '<div class="ddbbtext"><h2>Projecte de reducció exterior</h2>' + doc('Memòria', 'mem') + '<h2>&nbsp;</h2>{}</div>'
        args = (INVENTORY + '/fire/place', INVENTORY + '/fire', 'Aprovació inicial')
        self.assertEqual(len(Adapter.parse_fire_projects(page('Place', body.format('')), *args)), 1)
        with self.assertRaisesRegex(ValueError, 'Ungrouped'):
            Adapter.parse_fire_projects(page('Place', body.format(doc('Orphan', 'orphan'))), *args)

    def test_pagination_is_never_silently_ignored(self):
        for pager in ['<div class="pager"><a href="?page=2">2</a></div>', '<a href="?page=2" rel="next">Next</a>']:
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                inventory_links(page('Index', pager), INVENTORY, '.widgetMenu a[href]')

    def test_rejects_login_forms_and_missing_documents(self):
        for html in ['<h1>Login</h1>', page('Sol·licitud de llicència', doc('Formulari', 'form')), page('Projecte de reparcel·lació de prova')]:
            with self.assertRaises(ValueError):
                Adapter.parse_dossier(html, INVENTORY + '/example')

    def test_fetch_failure_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous snapshot\n')
            with patch.object(Adapter, '_fetch', side_effect=ValueError('Source unavailable')):
                with self.assertRaises(ValueError):
                    Adapter('corbera-de-llobregat').backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot\n')
            result = Adapter('corbera-de-llobregat').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
