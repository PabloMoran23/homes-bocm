# Torrevieja — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal (Drupal 10) | https://torrevieja.es |
| Exposición pública (taxonomía) | https://torrevieja.es/es/exposicion-publica |
| Urbanismo | https://torrevieja.es/es/temas/ciudad/urbanismo |
| Consulta pública previa | https://torrevieja.es/es/ayuntamiento/consulta-publica-previa |
| Sede electrónica (espublico gestiona) | https://torrevieja.sedelectronica.es |
| Tablón de anuncios | https://torrevieja.sedelectronica.es/board |
| Trámites licencia (dossier) | https://torrevieja.sedelectronica.es/dossier.1 |
| Gobierno abierto | https://gobiernoabierto.torrevieja.es/ (sin visor urbanístico enlazado) |

## Listado de expedientes / proyectos

- **Exposición pública:** página Drupal con bloques `<h2>` por anuncio (licencias ambientales, modificaciones PGOU, estudios de detalle, etc.). Incluye expediente (`NNNNN/AAAA`), emplazamiento y referencia catastral en texto plano; enlaces a nodos `/es/node/…` cuando existen.
- **Tablón sede:** HTML tabular espublico (`class_name`, `class_folderCode`, …) con preview-document. Filas de Urbanismo / Licencias de Actividad mezcladas con RRHH y subvenciones.
- **Consulta pública previa:** enlaces bajo `/es/consulta-publica-previa/…` descubiertos desde la página índice.

## Licencias de obra

- No hay dataset histórico de concesiones. Las licencias publicadas aparecen como **edictos** en tablón y en exposición pública (licencia ambiental / actividad).
- Trámites informativos en sede: licencia obra mayor, declaración responsable de obra, licencia actividad (catálogo dossier).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Generalitat (ICV): `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `ms:InventarioSuSuz`
  - Filtro: `CQL_FILTER=cod_ine_mun='03133'` (INE Torrevieja)
  - Visor estatal: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
- **Estrategia:** descargar polígonos SU/SUZ del inventario autonómico; enriquecer expedientes del tablón/exposición por coincidencia de tokens de sector en título. Referencia catastral en edictos **no** enlaza a servicio GIS municipal.
- **Limitaciones:** sin visor municipal propio; geometría de licencias puntuales depende del cruce textual con sectores WFS; parcela/catastro no consultable sin login.

## Limitaciones generales

- Tablón mezcla materias no urbanísticas (empleo, subvenciones).
- Consulta de expedientes en curso requiere identificación en sede.
- SSL sede: certificado válido; `insecure_ssl` por consistencia con otros adapters CV.
