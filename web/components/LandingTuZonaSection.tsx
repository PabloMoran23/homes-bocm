import { LandingAddressForm } from "@/components/LandingAddressForm";
import { LandingAreaMap } from "@/components/LandingAreaMap";

export function LandingTuZonaSection() {
  return <section className="landing-area-section" aria-labelledby="landing-tu-zona-heading">
    <div className="landing-area-copy"><p className="landing-eyebrow">Análisis de proximidad · Madrid</p><h2 id="landing-tu-zona-heading">El contexto de<br />tu próxima operación.</h2><p>Consulta las obras y el planeamiento alrededor de una dirección. Una primera lectura del entorno para estudiar un activo, preparar una visita o ampliar una investigación.</p>
      <div className="landing-area-benefits"><span><b>01</b> Localiza una dirección</span><span><b>02</b> Delimita el área de estudio</span><span><b>03</b> Consulta las actuaciones y sus fuentes</span></div>
      <LandingAddressForm submitLabel="Consultar entorno" showSecondaryLink={false} />
    </div>
    <LandingAreaMap />
  </section>;
}
