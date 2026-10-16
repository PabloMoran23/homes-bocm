# Soto del Barco (`san-juan-de-la-ar`)

## Nota cola / BOPA

- Entrada en `queue.yaml`: **San Juan de la Ar** (nombre truncado al parsear BOPA).
- El aviso BOPA alude a la parroquia **San Juan de la Arena**, dentro del concejo **Soto del Barco** (Asturias, INE `33069`).
- Portal municipal único: Ayuntamiento de **Soto del Barco** — no existe ayuntamiento propio de la parroquia.

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.sotodelbarco.com |
| Urbanismo (Liferay) | https://www.sotodelbarco.com/web/ayto-sotodelbarco/urbanismo |
| Catálogo urbanístico (PDFs NSP, fichas) | https://www.sotodelbarco.com/catalogo-urbanistico |
| Normativa municipal (ordenanzas, licencias DR) | https://www.sotodelbarco.com/normativa-municipal |
| Bandos | https://www.sotodelbarco.com/bandos |
| RPGUR (registro urbanístico regional) | https://www54.asturias.es/rpgur/action/publico/busquedaConsulta?method=listPublico |
| Sede electrónica | https://sotodelbarco.sede.e-ayuntamiento.es (TLS/timeout frecuente desde redes externas) |
| Info pública sede legacy | https://sedeelectronica.sotodelbarco.com/action/infopublica |

## Cómo se listan expedientes / planeamiento

1. **RPGUR (Principado):** tabla HTML paginada `busquedaConsulta?method=listPublico&idConcejo=69&estado=V`. Detalle por `idInstrumento`. Incluye normas subsidiarias de planeamiento (NSP 2003), instrumentos de gestión, etc.
2. **Web Liferay:** documentos en `/documents/120740/...` enlazados desde catálogo urbanístico y normativa (memoria NSP, acuerdos, fichas catalogadas).
3. **Bandos:** avisos públicos sin API; HTML estático por año.

CMS: **Liferay** (tema `mainresponsive`), rutas amigables bajo `/web/ayto-sotodelbarco/`.

## Licencias de obra

- No hay tablón de concesiones georreferenciadas.
- **Ordenanza** de licencias con declaración responsable (PDF en normativa municipal).
- Trámites genéricos en `/tramites` (instancia general).
- Sede electrónica para solicitudes; sin dataset abierto de licencias concedidas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer RPGUR: `http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows`
  - Capa: `E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS`
  - Filtro: `id_municipio=33069` (INE Soto del Barco)
  - Campo enlace: `Id._Inventario_Registro_Urbanístico` ↔ `idInstrumento` RPGUR
- **Estrategia:** tras listar instrumentos RPGUR, enriquecer filas con polígono WFS (`f=geojson`, EPSG:4326) vía `municipio/geometry.py`.
- **Limitaciones:** WFS/RPGUR a veces lentos o inaccesibles (timeout TLS); licencias sin geometría; parroquia vs concejo no diferenciada en GIS.

## Limitaciones generales

- Nombre erróneo en cola; geocodificación usa centroide Soto del Barco.
- Sin visor municipal propio; dependencia del registro autonómico.
- Sede con certificados/egress problemáticos en algunos entornos CI.
