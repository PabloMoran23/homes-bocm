-- Info extra de un proyecto: foto de una investigación, datos genéricos
-- para la ficha y texto crudo que no cabe en un dato.

CREATE TABLE homes.proyecto_investigacion (
  id BIGSERIAL PRIMARY KEY,
  proyecto_id TEXT NOT NULL REFERENCES homes.proyecto (id) ON DELETE CASCADE,
  investigado_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  estado TEXT NOT NULL CHECK (estado IN ('completa', 'parcial')),
  resumen TEXT NOT NULL,
  huecos TEXT
);

COMMENT ON TABLE homes.proyecto_investigacion IS
  'Una pasada de investigación. La web lee la más reciente por proyecto.';
COMMENT ON COLUMN homes.proyecto_investigacion.resumen IS
  'Relato largo: qué ocurre, historia del terreno, timeline, qué falta y fechas previstas.';
COMMENT ON COLUMN homes.proyecto_investigacion.huecos IS
  'Lo que se buscó y no apareció.';

CREATE INDEX idx_homes_proy_inv_proyecto_fecha
  ON homes.proyecto_investigacion (proyecto_id, investigado_at DESC);

CREATE TABLE homes.proyecto_dato_extra (
  id BIGSERIAL PRIMARY KEY,
  investigacion_id BIGINT NOT NULL REFERENCES homes.proyecto_investigacion (id) ON DELETE CASCADE,
  proyecto_id TEXT NOT NULL REFERENCES homes.proyecto (id) ON DELETE CASCADE,
  bloque TEXT NOT NULL CHECK (bloque IN (
    'situacion', 'programa', 'cifras', 'actores', 'prensa', 'cronologia'
  )),
  clave TEXT,
  etiqueta TEXT NOT NULL,
  valor TEXT NOT NULL,
  valor_numero DOUBLE PRECISION,
  unidad TEXT,
  confianza TEXT NOT NULL CHECK (confianza IN ('alta', 'media', 'baja')),
  fuente_tipo TEXT NOT NULL CHECK (fuente_tipo IN ('oficial', 'prensa', 'web')),
  fuente_nombre TEXT,
  fuente_url TEXT,
  fuente_fecha DATE,
  extracto TEXT,
  destacado BOOLEAN NOT NULL DEFAULT false,
  publicable BOOLEAN NOT NULL DEFAULT true,
  orden INTEGER NOT NULL DEFAULT 0
);

COMMENT ON TABLE homes.proyecto_dato_extra IS
  'Hechos genéricos de la ficha. bloque agrupa la sección; clave y etiqueta quedan abiertas.';
COMMENT ON COLUMN homes.proyecto_dato_extra.bloque IS
  'situacion, programa, cifras, actores, prensa, cronologia.';
COMMENT ON COLUMN homes.proyecto_dato_extra.clave IS
  'Identificador estable opcional, por ejemplo num_viviendas o promotor.';
COMMENT ON COLUMN homes.proyecto_dato_extra.destacado IS
  'Entra en la tira de KPIs de la ficha.';
COMMENT ON COLUMN homes.proyecto_dato_extra.publicable IS
  'Si es false, se guarda pero la web no lo enseña.';

CREATE INDEX idx_homes_proy_dato_inv
  ON homes.proyecto_dato_extra (investigacion_id, bloque, orden);
CREATE INDEX idx_homes_proy_dato_proyecto
  ON homes.proyecto_dato_extra (proyecto_id);

CREATE TABLE homes.proyecto_hallazgo (
  id BIGSERIAL PRIMARY KEY,
  investigacion_id BIGINT NOT NULL REFERENCES homes.proyecto_investigacion (id) ON DELETE CASCADE,
  proyecto_id TEXT NOT NULL REFERENCES homes.proyecto (id) ON DELETE CASCADE,
  titulo TEXT NOT NULL,
  cuerpo TEXT NOT NULL,
  fuente_nombre TEXT,
  fuente_url TEXT,
  fuente_fecha DATE,
  nota TEXT,
  publicable BOOLEAN NOT NULL DEFAULT true,
  orden INTEGER NOT NULL DEFAULT 0
);

COMMENT ON TABLE homes.proyecto_hallazgo IS
  'Texto relevante que no cabe en un dato. En la web sale como nota, no como KPI.';
COMMENT ON COLUMN homes.proyecto_hallazgo.nota IS
  'Por qué no es un dato. Uso interno.';

CREATE INDEX idx_homes_proy_hallazgo_inv
  ON homes.proyecto_hallazgo (investigacion_id, orden);

ALTER TABLE homes.proyecto_investigacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.proyecto_dato_extra ENABLE ROW LEVEL SECURITY;
ALTER TABLE homes.proyecto_hallazgo ENABLE ROW LEVEL SECURITY;

CREATE POLICY homes_proy_inv_read ON homes.proyecto_investigacion
  FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY homes_proy_dato_read ON homes.proyecto_dato_extra
  FOR SELECT TO anon, authenticated USING (publicable);
CREATE POLICY homes_proy_hallazgo_read ON homes.proyecto_hallazgo
  FOR SELECT TO anon, authenticated USING (publicable);

GRANT SELECT ON homes.proyecto_investigacion TO anon, authenticated;
GRANT SELECT ON homes.proyecto_dato_extra TO anon, authenticated;
GRANT SELECT ON homes.proyecto_hallazgo TO anon, authenticated;
GRANT ALL ON homes.proyecto_investigacion TO service_role;
GRANT ALL ON homes.proyecto_dato_extra TO service_role;
GRANT ALL ON homes.proyecto_hallazgo TO service_role;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA homes TO service_role;
