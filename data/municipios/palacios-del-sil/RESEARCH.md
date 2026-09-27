# Palacios del Sil — investigación portal ayuntamiento

Municipio: **Palacios del Sil** (`palacios-del-sil`)  
Provincia: León · CCAA: Castilla y León · Boletín: BOCYL

## URLs base y semillas

| Fuente | URL | Notas |
|--------|-----|--------|
| Web corporativa | https://www.palaciosdelsil.es | WordPress (tema Invicta), Wordfence |
| Trámites (urbanismo PDFs) | https://www.palaciosdelsil.es/ayuntamiento/tramites/ | Acordeones «URBANISMO Y MEDIO AMBIENTE» con formularios PDF |
| Normas subsidiarias | https://www.palaciosdelsil.es/ayuntamiento/normas-subsidiarias-municipales/ | Enlace a documentación de planeamiento |
| Sede electrónica | https://palaciosdelsil.sedelectronica.es | espublico/gestiona; `/board/` tablón, `/info` |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=105 | Instrumentos aprobados |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=105 | Información pública |

Código PlanPublica: provincia **24** (León), municipio **105** (INE 24105).

## Expedientes / proyectos

- **PlanPublica**: listado HTML tabular con `cDocId` → `openDocuIndice.do` (PDFs por índice).
- **IDECyL WFS**: capa `urbanismo:plau_cyl_instrumentos_ambito` con instrumento «NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL».
- **Web**: no hay visor urbanístico propio; planeamiento vía normas subsidiarias y JCyL.
- **Tablón sede**: enlaces `preview-document/{uuid}` con atributo `title` (sin `<tbody>`; parseo por enlaces).

## Licencias

- No hay listado público de licencias concedidas (coordenadas).
- Formularios de solicitud/comunicación en la página de trámites (declaración responsable, primera ocupación, uso excepcional, segregación, etc.).
- Tablón sede: anuncios genéricos (empleo, IAE, etc.); escasas entradas de urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `https://idecyl.jcyl.es/geoserver/urbanismo/ows` — capas `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores` filtradas por `n_mun = 'Palacios del Sil'`.
- **Estrategia:** GetFeature GeoJSON EPSG:4326 en el adapter; enriquecimiento por similitud de título con filas PlanPublica/web.
- **Limitaciones:** sin visor municipal ArcGIS; geometría solo a nivel de instrumentos/sectores CYL (no por expediente de licencia); tablón sin coords.

## Limitaciones generales

- Sede: certificado gestiona; adapter usa `insecure_ssl: true`.
- WordPress sin sección «urbanismo» dedicada (solo trámites).
- Sin API JSON de expedientes en el ayuntamiento.
