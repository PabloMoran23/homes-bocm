# Garrafe de Torío — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web OpenCms (Diputación León) | https://www.aytogarrafedetorio.es | Normativa urbanística, trámites licencias, enlaces JCyL |
| Web WordPress | https://www.ayuntamientogarrafedetorio.com | Normas urbanísticas — 25+ PDFs por localidad (término, Riosequino, Ruiforco, etc.) |
| Sede electrónica | https://garrafedetorio.sedelectronica.es | espublico gestiona — tablón `/board/`, trámites `/dossier.0`, transparencia |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=24&municipio=076 | Archivo planeamiento aprobado |
| PlanPublica IP | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=076 | Instrumentos en información pública |

## Listado de expedientes / proyectos

- **Normativa NUM**: PDFs estáticos en WordPress (`/documentos/*.pdf`) — planos desglosados por núcleo (1A–14B término municipal, Riosequino, Garrafe-Flecha, etc.).
- **OpenCms**: página normativa urbanística con enlaces a JCyL; sin listado dinámico de expedientes.
- **Tablón sede**: HTML tabla Wicket con `preview-document` UUIDs; anuncios de contratos/obras (PCE), notificaciones BOE; categoría urbanismo esporádica.
- **IDECyL WFS**: sectores S-SUNC y S-SUR con polígonos MultiPolygon.

## Licencias

- No hay tablón público de concesiones de licencia urbanística.
- Trámites informativos en OpenCms: licencia urbanística, primera ocupación, comunicación ambiental, licencia de apertura.
- Ordenanzas fiscales de tasas por licencias (PDF en web).

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — filtro `c_mun=24076` o `n_mun='Garrafe de Torío'`
  - Capas adicionales: `plau_cyl_instrumentos_ambito` (NUM), `plau_cyl_planes_parciales`
  - URL base: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Campos enlace: `c_id_sect`, `n_num_sect` (S-SUNC-01…04, S-SUR-01…07)
- **Estrategia:** query WFS por municipio → 11 sectores con geometría; enriquecer anuncios del tablón si mencionan código de sector (S-SUR, S-SUNC).
- **Limitaciones:** PDFs de normativa por localidad sin georreferencia; tablón sin coords; sin visor municipal propio.

## Limitaciones

- Dos dominios web (OpenCms legacy + WordPress nuevo); sede en subdominio separado.
- Tablón mayoritariamente contratación/obras municipales, no expedientes de planeamiento.
- Licencias: solo páginas de trámite, sin registro público de concesiones.
