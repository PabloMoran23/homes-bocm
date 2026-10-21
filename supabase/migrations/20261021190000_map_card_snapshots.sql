-- No-op. The first version of this file computed list_sigma_map_cards and
-- web_summary inside the migration. That scan of visor_ficha exceeded the
-- 60s apply limit and the transaction rolled back, so this version was
-- never recorded in production.
--
-- Do not put that body back. The replacement is
-- 20261021220000_map_card_snapshots_light.sql (DDL and cron only; the
-- first cron run fills the rows). Applying this file only marks the
-- version as done so a later migrate does not retry the timed-out body.

DO $noop$
BEGIN
  RAISE NOTICE '20261021190000 is a no-op. Apply 20261021220000_map_card_snapshots_light.sql.';
END
$noop$;
