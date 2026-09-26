# Benifaió, Sagunt i Xàbia — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `benifaio-sagunt-i-xabia` |
| Comunidad | Comunitat Valenciana (`dogv`) |
| Municipios | Benifaió (46071), Sagunt (46220), Xàbia/Jávea (03094) |

---

## Benifaió

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.benifaio.es | **Inaccesible** (timeout desde CI/agente) |
| Sede electrónica | https://benifaio.sedelectronica.es | espublico gestiona |
| Tablón | https://benifaio.sedelectronica.es/board | Tabla HTML `class_name`, `class_folderCode`, preview-document |
| Trámites | https://benifaio.sedelectronica.es/dossier | Catálogo licencias (sin histórico) |
| Expedientes | https://benifaio.sedelectronica.es/expedientes | Requiere identificación |

**Expedientes:** tablón espublico con filas HTML; no hay RSS ni sede Diputación (dival) activa.

**Licencias:** edictos puntuales en tablón; trámites informativos en sede.

---

## Sagunt (Sagunto)

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.aytosagunto.es | Umbraco CMS (Azure) |
| Tablón sede Diputación | https://sagunt.sedipualba.es/tablondeanuncios/ | RSS `tablon_rss.aspx` |
| Sede espublico | https://sagunto.sedelectronica.es | Página «Indeterminada» sin sesión — no usable |
| Sede alternativa | https://sede.sagunto.es | SharePoint (convocatorias, no urbanismo indexado) |
| Observatorio urbano | https://observatorio-de-la-agenda-urbana-de-sagunto-2-aytosagunto.hub.arcgis.com/ | Hub ArcGIS informativo, sin capa enlazable a expedientes |

**Expedientes:** tablón sedipualba vía RSS (20 ítems recientes); planeamiento principal en ICV WFS (76 SUZ).

**Licencias:** tablón sedipualba (filtrado regex urbanismo); trámites vía sede.

---

## Xàbia (Jávea)

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.ajxabia.com | CMS VG Agencia Digital |
| Sede electrónica | https://xabia.sedelectronica.es | espublico gestiona |
| Tablón | https://xabia.sedelectronica.es/board | Tabla HTML espublico |
| Transparencia urbanismo | https://xabia.sedelectronica.es/transparency/fcfa421c-24d4-4865-8f58-3ea515cd827e/ | Sección 7 (AJAX Wicket, metadatos carpetas) |

**Expedientes:** ICV WFS (41 SUZ) + tablón + carpetas transparencia (metadatos).

**Licencias:** tablón + trámites sede (sin histórico público).

*(Investigación detallada previa en `data/municipios/javea/RESEARCH.md`.)*

---

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` — `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Filtro cliente `cod_ine_mun`: 46071 (2), 46220 (76), 03094 (41)
  - Parámetros: `outputFormat=GML3`, `srsName=EPSG:4326`, paginación `STARTINDEX`/`count=200`
  - Campos: `pp`, `ue`, `clasificacion`, `uso`, `f_aprob`, `f_public`
- **Estrategia:** descarga WFS paginada por municipio; conversión GML `posList` → GeoJSON Polygon WGS84; enriquecimiento tablón por coincidencia de título.
- **Limitaciones:**
  - WFS no admite `CQL_FILTER` ni GeoJSON directo.
  - Benifaió: web caída; solo 2 polígonos WFS + tablón escaso.
  - Sagunt: sede espublico indeterminada; visor ArcGIS Hub sin query por expediente.
  - Xàbia: transparencia 2741 docs vía AJAX; CartoXàbia sin API pública.
  - Licencias tablón/PDF sin georreferencia.

---

## Adapter

- `municipio.adapters.benifaio_sagunt_i_xabia:BenifaioSaguntIXabiaAyuntamientoAdapter`
- Fuentes: ICV WFS (×3) + tablón espublico (Benifaió, Xàbia) + RSS sedipualba (Sagunt) + páginas informativas licencias.
