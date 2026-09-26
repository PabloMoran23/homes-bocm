# Lumbrales — investigación portal ayuntamiento

**Municipio:** Lumbrales (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-22  
**BOCYL (referencia):** 1 aviso  
**INE:** 37173

## Resumen

Lumbrales dispone de **web corporativa Wix** (`www.lumbrales.es`) orientada a turismo y servicios
generales, sin sección de urbanismo ni listado de expedientes. La **sede electrónica espublico
gestiona** (`lumbrales.sedelectronica.es`) publica el tablón de anuncios y catálogo de trámites.
El planeamiento urbanístico aprobado está en **PlanPublica / SiuCyL** (Junta de Castilla y León).
No hay visor urbanístico municipal ni dataset de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.lumbrales.es | Wix; enlaza a sede y transparencia provincial |
| Sede electrónica | https://lumbrales.sedelectronica.es/info.0 | espublico gestiona (Wicket) |
| Tablón de anuncios | https://lumbrales.sedelectronica.es/board | Sin anuncios urbanísticos activos (sep 2026) |
| Catálogo de trámites | https://lumbrales.sedelectronica.es/dossier/.0 | ~104 trámites; requiere cookie de sesión |
| Transparencia provincial | http://www.transparenciasalamanca.es/aytoFicha.aspx?idAyto=73 | Ficha Diputación Salamanca |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=173 | 10 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=173 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37173 | Mapa interactivo regional |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NS** (Normas Subsidiarias de Planeamiento Municipal), aprobación definitiva **29/06/1992**
  (`cDocId=278475`).
- Múltiples **modificaciones puntuales** de las NS (2009–2022) y **estudios de detalle** (2008–2016).
- **PORN** Arribes del Duero (2001) — instrumento territorial de ámbito supramunicipal.
- **Proyecto de normalización** de fincas (2019).

### Listado PlanPublica (PLAU)

Página HTML con tabla `#listado`. Cada fila incluye tipo (PU/OT/GU), subtipo (NS/ED/PORN/PN),
fechas, título y enlace `openDocumento.do?cDocId={id}`.

**Documentos identificados (sep 2026):**

| cDocId | Tipo | Fecha | Título |
|--------|------|-------|--------|
| 278475 | PU/NS | 29/06/1992 | NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL |
| 284767 | PU/NS | 29/05/2009 | Modificación puntual recalificación suelo rústico C/. Teso de la Horca |
| 288319 | PU/NS | 15/06/2012 | Modificación NS Calle Los Peligros nº 42 |
| 290441 | OT/PORN | 13/06/2001 | Plan de Ordenación Recursos Naturales Arribes del Duero |
| 290440 | OT/PORN | 20/07/2001 | Corrección errores PORN Arribes del Duero |
| 291742 | PU/ED | 07/04/2015 | Estudio de detalle modificaciones ordenación detallada |
| 293143 | PU/ED | 25/07/2016 | Estudio de detalle parcelas 26 y 28 C/. Juego de la Pelota |
| 293382 | PU/ED | 16/06/2008 | Estudio de detalle reajuste alineaciones C/. Egido de los Morales |
| 295551 | GU/PN | 21/02/2019 | Proyecto normalización fincas C/. Prado Juan Simal y C/. Carretera Bermellar |
| 298555 | PU/NS | 17/10/2022 | Modificación nº 3 NS ampliación suelo urbano 242 m² |

### Tablón de anuncios (sede)

Tabla HTML con columnas: documento, expediente, procedimiento, categoría, descripción, fecha.
Enlaces a `preview-document/{uuid}`. En sep 2026 solo contiene convocatorias de empleo,
presupuesto y ordenanzas — **sin licencias ni planeamiento**.

### Licencias de obra

No hay listado público de concesiones. El catálogo de trámites incluye páginas informativas de:
- Solicitud de Licencia o Autorización Urbanística
- Declaración Responsable o Comunicación en Materia Urbanística
- Solicitud de Modificación o Renuncia de Licencia Urbanística
- Solicitud de Licencia de Ocupación

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 feature (NS, polígono municipal)
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 1 feature (SAU «Suelo Apto para Urbanizar»)
  - SiuCyL visor regional: https://idecyl.jcyl.es/siur/index.html?id=37173
- **Estrategia:** query WFS por `n_mun='Lumbrales'`; enriquecer proyectos PlanPublica con
  geometría del instrumento NS o sector SAU cuando el título/subtipo lo permita.
- **Limitaciones:**
  - Sin visor urbanístico municipal propio
  - Estudios de detalle y modificaciones puntuales sin polígono individual en WFS
  - Tablón sin licencias georreferenciadas
  - Web Wix sin datos GIS

## 3. Limitaciones técnicas

- Sede requiere `insecure_ssl` en algunos entornos CI (certificado intermedio)
- Catálogo `/dossier/.0` tarda ~20–60 s en primera carga (cookie de sesión)
- PlanPublica es HTML tabular sin API JSON
- WFS limitado a 1 instrumento + 1 sector (sin planes parciales individuales)

## 4. Estrategia del adapter

1. **Proyectos:** PlanPublica PLAU (10 docs) + WFS IDECyL (instrumentos + sectores) + tablón sede
2. **Licencias:** páginas informativas del catálogo de trámites urbanísticos (sin concesiones)
3. **Geometría:** polígonos WFS para NS y sector SAU; resto sin `geom_geojson`
