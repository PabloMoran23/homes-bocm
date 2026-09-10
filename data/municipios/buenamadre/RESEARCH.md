# Buenamadre — investigación portal ayuntamiento

**Municipio:** Buenamadre (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-10  
**BOCYL (referencia):** 1 aviso  
**INE:** 37059

## Resumen

Buenamadre es un municipio pequeño (~119 hab.) sin web corporativa operativa (`www.buenamadre.es` devuelve 502).
La presencia digital pasa por la **sede electrónica espublico gestiona** y la **Diputación de Salamanca**
(La Salina), que publica información urbanística municipal. El planeamiento vigente es **DSU**
(Delimitación de Suelo Urbano, normativa anterior) en PlanPublica/JCYL. No hay listado público de
licencias de obra concedidas con coordenadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | http://www.buenamadre.es | **502 Bad Gateway** (sep 2026) |
| Sede electrónica | https://buenamadre.sedelectronica.es | espublico gestiona (Wicket); `/info.0` con bucle 302 sin sesión |
| Tablón de anuncios | https://buenamadre.sedelectronica.es/board/ | Responde; 4 anuncios recientes (IAE, juez de paz, DNI) |
| Catálogo trámites | https://buenamadre.sedelectronica.es/dossier/.0 | Requiere cookie de sesión (semilla `/board/`) |
| Info urbanística Diputación | http://www.lasalina.es/Aplicaciones/GestorInter.jsp?codMunicipio=59&funcion=VerNormasUrbanisticas&nombre=Buenamadre&prestacion=NormasUrbanisticas | 1 PDF urbanístico (2018) |
| PlanPublica — archivo (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=59 | Instrumento DSU; sin filas documentales adicionales |
| PlanPublica — info pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=59 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37059 | Visor regional |
| Ficha municipal Diputación | http://www.lasalina.es/Aplicaciones/GestorInter.jsp?codMunicipio=59&funcion=MuestraInformacionMunicipio&prestacion=Cipublico | INE 37059, sede, contacto |

**Contacto:** C/ Larga, 26 · 37209 Buenamadre · Tel. 923 45 00 03

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **DSU** — Delimitación de Suelo Urbano (normativa anterior, sin PGOU/NUM).
- En suelo rústico aplican de forma complementaria las **NSAP** provinciales de Salamanca.

### Diputación — Otra Información Urbanística

Tabla HTML en La Salina con campos Fecha / Título / Descripción / Tipo / enlace PDF:

| Fecha | Título | PDF |
|-------|--------|-----|
| 07/05/2018 | SOLICITUD AUTORIZACIÓN DE USO EXCEPCIONAL EN SUELO RÚSTICO | `59_1_SOLICITUD DE AUTORIZACIÓN DE USO EXCEPCIONAL EN S. R. er.extrarradio nº1 Buenamadre.pdf` |

Ubicación citada: Er. Extrarradio, 1 (bar + vivienda en suelo rústico).

### PlanPublica (PLAU)

Página con leyenda de instrumentos (PU, NUM, DSU, SPG…). Para Buenamadre el instrumento activo es **DSU**.
Sin filas adicionales en tabla `#listado` con `doOpen(cDocId)` (ago 2026).

Códigos PlanPublica: **provincia=37**, **municipio=59**.

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Tabla espublico: Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha.

- Anuncios visibles (2026): cobranza IAE, edictos juez de paz, renovación DNI en Tamames.
- **Sin licencias de obra** en ventana visible.
- PDFs: `https://buenamadre.sedelectronica.es/preview-document/{uuid}`.

### Catálogo de trámites (`/dossier/.0`)

Trámites informativos (no histórico de concesiones). Relevantes:

| Trámite | UUID |
|---------|------|
| Declaración Responsable o Comunicación en Materia Urbanística | `5d383e20-32a5-4fcf-8725-e51c51e83e6a` |
| Solicitud de Licencia o Autorización Urbanística | `15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de Modificación o Renuncia de Licencia Urbanística | `a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Solicitud de Licencia de Ocupación | `b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Solicitud de Certificado o Informe Urbanístico | `e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Modificación del Planeamiento de Desarrollo | `6e8237a3-0b83-469d-b0ad-70159b9a9c26` |
| Planeamiento General (Modificación) | `96514574-aca1-40e1-a800-e06485e6d016` |
| Solicitud de Actuación Urbanística | `f91e4a50-d23d-45c1-a19b-b148da37c59f` |

## 4. GIS / geometría

| Fuente | URL | Formato | Contenido Buenamadre |
|--------|-----|---------|----------------------|
| WFS IDECyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON | **1** polígono DSU (`plau_cyl_instrumentos_ambito`) |
| WFS sectores | `urbanismo:plau_cyl_sectores` | GeoJSON | 0 features |
| WFS planes parciales | `urbanismo:plau_cyl_planes_parciales` | GeoJSON | 0 features |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=37059` | JS | Visor regional |

**No hay:** visor urbanístico municipal, ArcGIS local, WFS del ayuntamiento.

### WFS — ejemplo

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_instrumentos_ambito
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Buenamadre'
```

Resultado: `MultiPolygon` del ámbito DSU municipal.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_instrumentos_ambito` (polígono DSU municipal); centroide `[40.857, -6.250]` para expedientes sin sector (PDF La Salina, trámites).
- **Estrategia:** ingestar polígono DSU vía WFS; adjuntar a instrumentos DSU/NUM en PlanPublica; fallback centroide + jitter.
- **Limitaciones:** licencias y tablón sin GIS; PDF uso excepcional sin georreferencia; web corporativa caída; `/info.0` inaccesible sin sesión.

## Limitaciones

- Web municipal caída; sede parcialmente inestable (`/info.0` bucle redirect).
- Tablón: ventana corta, sin licencias urbanísticas visibles.
- PlanPublica: solo DSU, sin documentos adicionales en listado.
- Transparencia urbanismo: no investigada (sección probablemente vacía en municipios similares).

## Estrategia adapter

1. **WFS IDECyL** → polígono DSU + metadatos instrumento.
2. **La Salina** → parsear tabla «Otra Información Urbanística» (PDFs).
3. **PlanPublica PLAU/PLAI** → tabla documental (vacía salvo leyenda DSU).
4. **Tablón sede** (`/board/`) → filtrar keywords urbanismo/licencia.
5. **Catálogo dossier** → licencias/proyectos informativos (`/catalog/t/{uuid}`).
6. **IDs:** `buenamadre-{lic|proy}-{sha256[:14]}`.
