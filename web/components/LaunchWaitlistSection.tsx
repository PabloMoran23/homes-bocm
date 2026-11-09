"use client";

import { useId, useState, type FormEvent } from "react";
import styles from "./LaunchWaitlistSection.module.css";

const MESSAGES = {
  project: {
    title: "¿Quieres seguir este proyecto?",
    description: "Estamos preparando avisos sobre nueva documentación y cambios en la tramitación de los proyectos que te interesan.",
    invitation: "Déjanos tu correo y te avisaremos cuando puedas seguir proyectos en Homes.",
    confirmation: "Te avisaremos cuando esté disponible el seguimiento de proyectos.",
  },
  boletin: {
    title: "Lo que cambia cerca de ti, en tu correo.",
    description: "Estamos preparando avisos sobre obras, nuevos proyectos y cambios urbanísticos alrededor de las zonas que te interesan.",
    invitation: "Déjanos tu correo y te avisaremos cuando puedas recibir novedades de tu zona.",
    confirmation: "Te avisaremos cuando estén disponibles los avisos de tu zona.",
  },
  dashboard: {
    title: "Sigue la evolución del territorio.",
    description: "Estamos preparando resúmenes por correo para seguir la evolución de las licencias y el planeamiento en los territorios que analizas.",
    invitation: "Déjanos tu correo y te avisaremos cuando estén disponibles los resúmenes de actividad.",
    confirmation: "Te avisaremos cuando estén disponibles los resúmenes de actividad urbanística.",
  },
} as const;

type LaunchWaitlistProps = {
  source: keyof typeof MESSAGES;
  contextKey?: string;
  compact?: boolean;
};

export function LaunchWaitlistSection({ source, contextKey = "", compact = false }: LaunchWaitlistProps) {
  const id = useId();
  const message = MESSAGES[source];
  const [status, setStatus] = useState<"idle" | "sending" | "success" | "error">("idle");

  async function subscribe(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (status === "sending") return;
    const form = new FormData(event.currentTarget);
    setStatus("sending");
    try {
      const response = await fetch("/api/launch-waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.get("email"), website: form.get("website"), source, contextKey }),
        signal: AbortSignal.timeout(10_000),
      });
      if (!response.ok) throw new Error("Subscription unavailable");
      setStatus("success");
    } catch {
      setStatus("error");
    }
  }

  return (
    <section className={`landing-waitlist launch-waitlist-contextual ${compact ? styles.compact : ""}`} aria-labelledby={`${id}-heading`}>
      <div className={`landing-waitlist-inner ${styles.inner}`}>
        <div className="landing-waitlist-copy">
          <p className="landing-eyebrow"><span className="landing-waitlist-dot" aria-hidden="true" />En preparación</p>
          <h2 id={`${id}-heading`}>{message.title}</h2>
          <p>{message.description}</p>
        </div>
        <div className="landing-waitlist-signup">
          {status === "success" ? (
            <div className="landing-waitlist-success" role="status">
              <span aria-hidden="true">✓</span>
              <h3>Gracias por tu interés.</h3>
              <p>{message.confirmation}</p>
            </div>
          ) : (
            <form onSubmit={subscribe} aria-busy={status === "sending"}>
              <label htmlFor={`${id}-email`}>{message.invitation}</label>
              <div className={`landing-waitlist-field ${styles.field}`}>
                <input id={`${id}-email`} name="email" type="email" autoComplete="email" placeholder="Tu correo electrónico" maxLength={254} required aria-describedby={`${id}-note ${id}-status`} />
                <button type="submit" disabled={status === "sending"}>{status === "sending" ? "Guardando…" : "Avisadme"}<span aria-hidden="true">↗</span></button>
              </div>
              <div className="landing-waitlist-trap" aria-hidden="true">
                <label htmlFor={`${id}-website`}>Sitio web</label>
                <input id={`${id}-website`} name="website" type="text" tabIndex={-1} autoComplete="off" />
              </div>
              <p id={`${id}-note`} className="landing-waitlist-note">Solo usaremos tu correo para avisarte del lanzamiento.</p>
              <p id={`${id}-status`} className="landing-waitlist-error" role="status">{status === "error" ? "No hemos podido guardar tu correo. Inténtalo de nuevo en unos minutos." : ""}</p>
            </form>
          )}
        </div>
      </div>
    </section>
  );
}
