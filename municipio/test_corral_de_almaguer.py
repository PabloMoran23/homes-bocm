"""Offline structural/semantic tests; live extraction is recorded separately."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.corral_de_almaguer import (
    SOURCE, CorralDeAlmaguerAyuntamientoAdapter, group_instruments, parse_page,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def article(title, identity='mp1', date='05/02/2019', population='Corral de Almaguer', doc='test.pdf'):
    return f'''<article class="node--type-acuerdo-expediente-urbanistico" about="/urbanismo/acuerdos/{identity}">
    <h3 class="article__title">{title}</h3><div class="field--name-field-poblacion">{population}</div>
    <div class="field--name-field-expediente-fecha">{date}</div>
    <div class="field--name-field-expediente-fichero"><a href="/sites/default/files/expedientes/{doc}">
    <span class="file--title">{doc}</span></a></div></article>'''


def page(items, start=1, total=None, next_link=''):
    total = len(items) if total is None else total
    return f'Mostrando {start} - {start + len(items)-1} de {total} expediente/s encontrados' + ''.join(items) + next_link


class ParserTests(unittest.TestCase):
    def test_group_same_pau_and_keep_dates_and_documents(self):
        html = page([
            article('Resolución adjudicación PAU Sector "Polígono Industrial" de las NNSS de Corral de Almaguer', 'pau21', '10/11/2021', doc='2021.pdf'),
            article('Resolución adjudicación PAU Sector P.I. de las NNSS de Corral de Almaguer', 'pau19', '25/11/2019', doc='2019.pdf'),
            article('CROTU Modificación Puntual nº 1 POM Corral de Almaguer'),
        ])
        entries, count, next_url = parse_page(html)
        rows = group_instruments(entries)
        self.assertEqual(count, (1, 3, 3))
        self.assertIsNone(next_url)
        self.assertEqual(len(rows), 2)
        self.assertEqual([d['fecha_acuerdo'] for d in rows[0]['documentos']], ['2021-11-10', '2019-11-25'])
        self.assertEqual(len(rows[1]['documentos']), 1)
        for row in rows:
            self.assertFalse(row['publication_ready'])
            for key in ['fecha', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'fase']:
                self.assertNotIn(key, row)
        self.assertEqual(rows, group_instruments(entries + entries))

    def test_exclude_authorisations_qualifications_forms_and_other_municipality(self):
        items = [article(t, str(i)) for i, t in enumerate([
            'Calificación instalación solar Corral de Almaguer',
            'Autorización provisional vallado S-17 Corral de Almaguer',
            'Modelo solicitud licencia', 'Licitación obras POM', 'Noticias fiestas'])]
        items.append(article('Modificación Puntual POM Almagro', population='Almagro'))
        self.assertEqual(parse_page(page(items))[0], [])
        with self.assertRaises(ValueError):
            group_instruments([])

    def test_missing_structure_or_document_fails(self):
        for html in ['<html>Unavailable</html>', page([article('POM Corral de Almaguer')]).replace('field--name-field-expediente-fichero', 'absent')]:
            with self.assertRaises(ValueError):
                parse_page(html)

    def test_count_mismatch_fails(self):
        with self.assertRaises(ValueError):
            parse_page('Mostrando 1 - 2 de 2 expediente/s encontrados' + article('POM Corral de Almaguer'))

    def test_external_document_fails(self):
        html = page([article('POM Corral de Almaguer')]).replace('/sites/default/files/expedientes/test.pdf', 'https://example.org/test.pdf')
        with self.assertRaises(ValueError):
            parse_page(html)

    def test_pagination_and_incomplete_inventory(self):
        next_link = '<li class="pager__item--next"><a href="?title=Corral+de+Almaguer&amp;page=1">Next</a></li>'
        first = page([article('Modificación Puntual nº 1 POM Corral de Almaguer')], total=2, next_link=next_link)
        second = page([article('Modificación Puntual nº 2 POM Corral de Almaguer', 'mp2')], start=2, total=2)
        def response(html, url):
            r = Mock(text=html, url=url)
            r.raise_for_status.return_value = None
            return r
        adapter = CorralDeAlmaguerAyuntamientoAdapter('corral-de-almaguer')
        with tempfile.TemporaryDirectory() as folder, patch('municipio.adapters.corral_de_almaguer.requests.Session') as session:
            get = session.return_value.__enter__.return_value.get
            get.side_effect = [response(first, SOURCE), response(second, SOURCE + '&page=1')]
            output = Path(folder) / 'projects.jsonl'
            self.assertEqual(adapter.backfill_proyectos(output)['pages'], 2)
            self.assertEqual(len([json.loads(x) for x in output.read_text().splitlines()]), 2)
            get.side_effect = [response(first.replace(next_link, ''), SOURCE)]
            output.write_text('preserve previous complete extraction')
            with self.assertRaisesRegex(ValueError, 'pagination'):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'preserve previous complete extraction')

    def test_lost_filter_fails(self):
        html = page([article('POM Corral de Almaguer')], total=2,
                    next_link='<a rel="next" href="?page=1">Next</a>')
        with self.assertRaisesRegex(ValueError, 'filter'):
            parse_page(html)

    def test_manifest_resolves_and_licences_disabled(self):
        manifest = load_manifest('corral-de-almaguer')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, CorralDeAlmaguerAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with self.assertRaises(NotImplementedError):
            adapter.backfill_licencias(Path('/tmp/unused-corral-licences.jsonl'))


if __name__ == '__main__':
    unittest.main()
