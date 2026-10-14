-- Idempotent invalidation of both old and new municipal publications on correction.
CREATE TABLE IF NOT EXISTS homes.license_territory_rebuild (
  municipio_slug text PRIMARY KEY,
  requested_at timestamptz NOT NULL DEFAULT now(),
  reason text NOT NULL
);
CREATE OR REPLACE FUNCTION homes.invalidate_license_territory() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.municipio_slug IS DISTINCT FROM NEW.municipio_slug
     AND OLD.municipio_slug IS NOT NULL THEN
    INSERT INTO homes.license_territory_rebuild VALUES (OLD.municipio_slug, now(), 'municipality_changed')
    ON CONFLICT (municipio_slug) DO UPDATE SET requested_at=excluded.requested_at, reason=excluded.reason;
  END IF;
  IF NEW.municipio_slug IS NOT NULL THEN
    INSERT INTO homes.license_territory_rebuild VALUES (NEW.municipio_slug, now(), 'license_changed')
    ON CONFLICT (municipio_slug) DO UPDATE SET requested_at=excluded.requested_at, reason=excluded.reason;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS licencia_territory_invalidation ON homes.licencia;
CREATE TRIGGER licencia_territory_invalidation AFTER INSERT OR UPDATE ON homes.licencia
FOR EACH ROW EXECUTE FUNCTION homes.invalidate_license_territory();
