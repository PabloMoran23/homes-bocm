export type PresentacionCount = { name: string; count: number };

export type PresentacionYear = {
  year: number;
  aperturas: number;
  reformasMenores: number;
  obraVivienda: number;
  obraLocal: number;
  nuevaPlanta: number;
  reforma: number;
  demolicion: number;
  primeraOcupacion: number;
  localAVivienda: number;
  total: number;
};

export type MadridPresentacion = {
  generatedAt: string;
  lastCompleteMonth: string;
  licencias: {
    total: number;
    sinDistrito: number;
    hastaMes: number;
    comparativa: PresentacionYear[];
    ritmo: { month: string; total: number }[];
    procedimiento: PresentacionCount[];
    porDistrito: PresentacionCount[];
    barriosLocal2025: PresentacionCount[];
    barriosReforma2025: PresentacionCount[];
    cambiosLocal2025: number;
    reformasMenores2025: number;
  };
  planes: {
    total: number;
    conGeometria: number;
    abiertos: number;
    abiertosGranAmbito: number;
    iniciativaConDato: number;
    superficieConDato: number;
    porFase: PresentacionCount[];
    abiertosPorTipo: PresentacionCount[];
    incoados: { year: number; count: number }[];
    porEscala: PresentacionCount[];
    porInstrumento: PresentacionCount[];
    iniciativa: PresentacionCount[];
    superficie: PresentacionCount[];
    promotores: PresentacionCount[];
  };
  cruce: { name: string; licencias: number; planes: number }[];
};

export type EspanaPresentacion = {
  anuncios: number;
  yearMin: string | null;
  yearMax: string | null;
  comunidades: number;
  territorios: PresentacionCount[];
  territoriosMenores: PresentacionCount[];
  instrumentos: PresentacionCount[];
  municipios: PresentacionCount[];
  porAno: { year: number; count: number }[];
};

export type ProyectoInvestigado = {
  proyectoId: string;
  municipio: string | null;
  denominacion: string;
  nombrePublico: string | null;
  resumen: string;
  estado: string;
  viviendas: number | null;
  superficieM2: number | null;
  promotor: string | null;
};
