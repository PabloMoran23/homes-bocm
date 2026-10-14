export const TERRITORIAL_POLICY = 'license-territory-v1';
export function licenseTerritory(row) {
  const raw = row.raw_json && typeof row.raw_json === 'object' ? row.raw_json : row;
  const source = String(row.fuente || row.source || raw.fuente || raw.source || '').trim().toLowerCase();
  const slug = String(row.municipio_slug || raw.municipio_slug || '').trim().toLowerCase();
  const origin = raw._territorial_origin || {};
  const originSlug = origin.adapter && origin.url ? String(origin.municipio_slug || '').trim().toLowerCase() : '';
  const scoped = source === 'madrid-opendata' ? 'madrid' : '';
  const candidates = new Set([slug, originSlug, scoped].filter(Boolean));
  const reason = candidates.size > 1 ? 'conflicting_municipality_evidence'
    : !candidates.size || !(originSlug || source) ? 'missing_municipality_provenance' : null;
  const municipality = reason ? null : [...candidates][0];
  return { municipioCode: municipality === 'madrid' ? '28079' : municipality === 'valladolid' ? '47186' : null,
    municipio_slug: municipality, reason };
}
