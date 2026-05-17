-- RLS: lectura pública (POC); escritura solo service_role (sync / backend).

ALTER TABLE homes.source ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.project_boletin ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.sigma_catalog_expediente ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.link_project_sigma ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.sigma_ambito_geom ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.inmueble ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.actuacion_edificacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.link_licencia_sigma ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.sigma_expediente_metric ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.sigma_pdf_metric ENABLE ROW LEVEL SECURITY;

CREATE POLICY homes_source_read ON homes.source FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_project_read ON homes.project_boletin FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_sigma_cat_read ON homes.sigma_catalog_expediente FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_link_proj_read ON homes.link_project_sigma FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_sigma_geom_read ON homes.sigma_ambito_geom FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_inmueble_read ON homes.inmueble FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_act_read ON homes.actuacion_edificacion FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_link_lic_read ON homes.link_licencia_sigma FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_sigma_metric_read ON homes.sigma_expediente_metric FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_sigma_pdf_read ON homes.sigma_pdf_metric FOR SELECT TO anon, authenticated USING (true);
