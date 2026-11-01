# Rosinos de la Requejada — investigación portal ayuntamiento

**Municipio:** Rosinos de la Requejada (provincia Zamora, Castilla y León)  
**Fecha:** 2026-10-15  
**BOCYL (referencia):** 1 aviso  
**INE:** 49215 | **DIR3:** L01491815

## Resumen

El municipio **no tiene web corporativa activa** (`www.rosinosdelarequejada.es` está en reserva por la
Diputación Provincial de Zamora). La publicación administrativa se concentra en la **sede electrónica
espublico gestiona** (`rosinosdelarequejada.sedelectronica.es`): tablón de anuncios, catálogo de
trámites (~110) y sección *Urbanismo y Vivienda*. El planeamiento se consulta en **PlanPublica / SiuCyL**
(código municipio JCyL **215** en provincia **49**) y en el visor regional **IDECyL WFS**.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Dominio municipal (inactivo) | http://www.rosinosdelarequejada.es/ | Reservado Dip. Zamora |
| Sede electrónica | https://rosinosdelarequejada.sedelectronica.es/info | Inicio |
| Tablón de anuncios | https://rosinosdelarequejada.sedelectronica.es/board | Tabla HTML; vacío oct 2026 (histórico en portada) |
| Catálogo de trámites | https://rosinosdelarequejada.sedelectronica.es/dossier | Enlaces `/catalog/t/{uuid}` |
| Urbanismo (dossier) | Enlace Wicket desde menú *Urbanismo y Vivienda* | Agrupa trámites urbanísticos |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=49&municipio=215 | Tabla HTML instrumentos aprobados |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=49&municipio=215 | Exposiciones públicas |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=49215 | Mapa interactivo |

**Contacto:** C/ Santa Colomba 70, 49322 · Tel. 980 626 127 · aytorosinosdelarequejada@gmail.com

## 2. Urbanismo / expedientes

### Tablón y portada

- El **tablón** (`/board`) usa tabla espublico con columnas documento, expediente, procedimiento,
  categoría, descripción y fecha; enlaces `preview-document/{uuid}` cuando hay PDF.
- En octubre 2026 el tablón aparece **sin filas**, pero la portada (`/info`) ha mostrado anuncios de
  **modificación puntual de delimitación de suelo urbano en Doney de la Requejada** (PDSU) — contenido
  cargado vía widget AJAX (`gestionaEhomeOpenBorningTramit`).

### PlanPublica (JCyL)

Listado HTML con `doGoBoletin` / `openDocumento.do?cDocId=`. El adapter pagina PLAI y parsea PLAU.

### Catálogo sede (trámites informativos)

Trámites urbanísticos relevantes detectados en `/dossier` (no son concesiones):

- Declaración Responsable o Comunicación en Materia Urbanística
- Solicitud de Licencia o Autorización Urbanística
- Modificación del Planeamiento de Desarrollo / Planeamiento General (Modificación)
- Solicitud de Actuación Urbanística
- Solicitud de Certificado o Informe Urbanístico

## 3. Licencias de obra

No hay dataset abierto de licencias concedidas con coordenadas. Estrategia del adapter:

1. Filas del tablón si publican licencias (actualmente ninguna).
2. Páginas informativas de trámites de licencia del catálogo sede.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_sectores`, `plau_cyl_planes_parciales`,
  `plau_cyl_instrumentos_ambito` con `CQL_FILTER n_mun = 'Rosinos de la Requejada'`; SiUR `id=49215`.
- **Estrategia:** ingestar polígonos WFS como proyectos; enriquecer anuncios/tablon/PLAU con geometría
  por código de sector (`n_num_sect`) cuando el texto lo cite.
- **Limitaciones:** WFS/SiuCyL puede bloquear egress en algunos entornos; sin visor municipal propio;
  tablón sin georreferencia; dominio web inactivo. Si WFS no responde, el orquestador usa centroide
  manifest + jitter.

## 4. Limitaciones técnicas

- Dominio municipal reservado — solo sede + JCyL.
- Tablón vacío de forma intermitente; conviene combinar portada + PLAI/PLAU.
- PlanPublica y WFS requieren User-Agent de navegador; sede usa cookies de sesión (JSESSIONID) tras `/board`.
