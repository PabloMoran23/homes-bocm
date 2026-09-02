# Tamames — investigación portal ayuntamiento

**Municipio:** Tamames (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-02  
**BOCYL (referencia):** 2 avisos  
**INE:** 37316 | **PlanPublica municipio:** 316 (provincia 37)

## Resumen

Tamames **no dispone de web corporativa** accesible (`tamames.es`, `ayuntamientodetamames.es` sin respuesta).
La presencia digital municipal pasa por la **sede electrónica espublico gestiona**
(`tamames.sedelectronica.es`). El planeamiento urbanístico vigente (NUM + modificaciones) está en
**PlanPublica / SiuCyL**. Geometría disponible vía **WFS IDECyL** (instrumento municipal + 11 sectores).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica | https://tamames.sedelectronica.es/info | Redirige a `/info`; espublico gestiona |
| Tablón de anuncios | https://tamames.sedelectronica.es/board/ | 7 anuncios (ago–sep 2026); sin urbanismo |
| Catálogo de trámites | https://tamames.sedelectronica.es/dossier/.0 | Redirige a `/dossier/.1`; ~50 KB HTML |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=316 | 4 documentos NUM |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=316 | Sin IP activa (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37316 | Visor regional |
| WFS IDECyL | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | GeoJSON por `n_mun='Tamames'` |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), revisión aprobada **02/02/2020** (`cDocId=296464`).
- Tres modificaciones posteriores (2022, 2023, 2025) sobre alineaciones y reclasificación de suelo.

### Listado PlanPublica (PLAU)

Tabla HTML con filas `PU / NUM / fecha BOCYL / fecha aprobación / título`.

| Fecha BOCYL | Fecha aprob. | Título |
|-------------|--------------|--------|
| 12/03/2020 | 03/02/2020 | NORMAS URBANÍSTICAS MUNICIPALES (REVISIÓN) |
| 25/02/2022 | 31/01/2022 | MODIFICACIÓN DE LAS NUM, REFERIDO A CAMBIO DE ALINEACIÓN |
| 10/05/2023 | 20/04/2023 | MODIFICACIÓN Nº 2 DE LAS NUM (reclasificación SUC, alineaciones) |
| 12/02/2025 | 30/01/2025 | MODIFICACIÓN Nº 3 DE LAS NUM (alineaciones) |

PDFs vía `openDocumento.do?cDocId={id}` o `openDocuIndice.do?cDocId={id}`.

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Tabla espublico: convocatorias pleno, prórroga piscinas, pliegos fiestas, edicto notarial.
**Sin licencias de obra** en ventana visible.

### Catálogo de trámites (`/dossier/.1`)

Trámites informativos relevantes (UUIDs estándar espublico):

| Trámite | URL |
|---------|-----|
| Declaración Responsable o Comunicación en Materia Urbanística | `/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a` |
| Solicitud de Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de Modificación o Renuncia de Licencia Urbanística | `/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Solicitud de Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Solicitud de Certificado o Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Solicitud de Actuación Urbanística | `/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f` |

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. GIS / geometría

| Fuente | Capa | Features Tamames |
|--------|------|------------------|
| WFS `plau_cyl_instrumentos_ambito` | Polígono NUM municipal | 1 |
| WFS `plau_cyl_sectores` | Sectores SU-NC | 11 |
| WFS `plau_cyl_planes_parciales` | Planes parciales | 0 |

Ejemplo consulta:

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeNames=urbanismo:plau_cyl_sectores
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Tamames'
```

Propiedades: `c_id_sect`, `n_num_sect`, `n_sector`, `c_instrum=NUM`, `url_doc_info`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS IDECyL `plau_cyl_instrumentos_ambito` (polígono NUM) + `plau_cyl_sectores` (11 polígonos SU-NC); visor SiUR `id=37316`.
- **Estrategia:** ingestar features WFS con `geom_geojson`; cruzar códigos de sector en títulos PLAU/tablón; fallback centroide municipal `[40.695, -6.053]`.
- **Limitaciones:** licencias y tablón sin GIS; SiUR no expone API directa al scrapeador; sin web corporativa.

## Limitaciones

- Sin web municipal propia.
- Tablón: ventana corta, sin licencias urbanísticas.
- `/dossier/.0` redirige a `.1` (requiere seguir redirects).
- Catálogo: formularios informativos, no resoluciones históricas.

## Estrategia adapter

1. **WFS IDECyL** → instrumento + sectores con geometría.
2. **PlanPublica PLAU** → parsear tabla HTML (4 documentos NUM).
3. **Tablón sede** → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → páginas informativas de trámites de licencia.
5. **IDs:** `tamames-{lic|proy}-{sha256[:14]}`.
