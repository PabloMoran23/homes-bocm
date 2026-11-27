"use client";

import Link from "next/link";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  SEGUIR_EMAIL_ERROR,
  SEGUIR_SAVE_ERROR,
  SEGUIR_SEGMENT_ERROR,
  SEGUIR_SEGMENTOS,
  barDismissed,
  dismissBar,
  normalizeEmail,
  readAttribution,
  readStoredFollow,
  seguirCopy,
  writeStoredFollow,
  type SeguirAviso,
  type SeguirCopy,
  type SeguirPosicion,
  type SeguirSegmento,
} from "@/lib/seguir-proyecto";
import {
  recordSeguirAlta,
  recordSeguirClic,
  recordSeguirSegmento,
  recordSeguirVisto,
} from "@/lib/seguir-proyecto-analytics";
import "./seguir-proyecto.css";

type RegisterResult = "ok" | "invalid" | "error";

type SeguirContextValue = {
  projectId: string;
  municipio: string | null;
  copy: SeguirCopy;
  subscribed: boolean;
  segmento: SeguirSegmento | null;
  confirmedPosition: SeguirPosicion | null;
  busy: boolean;
  register: (email: string, posicion: SeguirPosicion) => Promise<RegisterResult>;
  saveSegmento: (segmento: SeguirSegmento) => Promise<boolean>;
};

const SeguirContext = createContext<SeguirContextValue | null>(null);

function useSeguir() {
  const value = useContext(SeguirContext);
  if (!value) throw new Error("El formulario de seguimiento tiene que ir dentro de su ficha.");
  return value;
}

export function SeguirProyectoProvider({
  projectId,
  municipio,
  aviso,
  lugar,
  children,
}: {
  projectId: string;
  municipio: string | null;
  aviso: SeguirAviso;
  lugar: string | null;
  children: ReactNode;
}) {
  const copy = useMemo(() => seguirCopy(aviso, lugar), [aviso, lugar]);
  const [subscribed, setSubscribed] = useState(false);
  const [segmento, setSegmento] = useState<SeguirSegmento | null>(null);
  const [confirmedPosition, setConfirmedPosition] = useState<SeguirPosicion | null>(null);
  const [busy, setBusy] = useState(false);
  const [barHidden, setBarHidden] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const emailRef = useRef<string | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const barButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const stored = readStoredFollow(projectId);
    if (stored) {
      setSubscribed(true);
      setSegmento(stored.segmento);
      setBarHidden(true);
    } else if (barDismissed(projectId)) {
      setBarHidden(true);
    }
  }, [projectId]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (sheetOpen && !dialog.open) {
      dialog.showModal();
      dialog.querySelector<HTMLElement>("[data-seguir-focus]")?.focus();
      recordSeguirVisto("barra");
    } else if (!sheetOpen && dialog.open) {
      dialog.close();
      barButtonRef.current?.focus();
    }
  }, [sheetOpen]);

  const register = useCallback(async (email: string, posicion: SeguirPosicion): Promise<RegisterResult> => {
    const normalized = normalizeEmail(email);
    if (!normalized) return "invalid";
    const attribution = typeof window === "undefined"
      ? { referrer: null, utm: null }
      : readAttribution(window.location.href, document.referrer);
    setBusy(true);
    try {
      const response = await fetch("/api/launch-waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          intent: "alta",
          email: normalized,
          source: "project",
          contextKey: projectId,
          posicion,
          municipio,
          referrer: attribution.referrer,
          utm: attribution.utm,
          aviso: copy.aviso,
          ambito: copy.lugar,
        }),
        signal: AbortSignal.timeout(10_000),
      });
      if (response.status === 400) return "invalid";
      if (!response.ok) return "error";
      emailRef.current = normalized;
      setSubscribed(true);
      setConfirmedPosition(posicion);
      setBarHidden(true);
      writeStoredFollow(projectId, { segmento: null });
      recordSeguirAlta(posicion, projectId);
      return "ok";
    } catch {
      return "error";
    } finally {
      setBusy(false);
    }
  }, [copy.aviso, copy.lugar, municipio, projectId]);

  const saveSegmento = useCallback(async (next: SeguirSegmento) => {
    const email = emailRef.current;
    if (!email) return false;
    setBusy(true);
    try {
      const response = await fetch("/api/launch-waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          intent: "segmento",
          email,
          source: "project",
          contextKey: projectId,
          segmento: next,
        }),
        signal: AbortSignal.timeout(10_000),
      });
      if (!response.ok) return false;
      setSegmento(next);
      writeStoredFollow(projectId, { segmento: next });
      recordSeguirSegmento(next);
      return true;
    } catch {
      return false;
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  const value = useMemo<SeguirContextValue>(() => ({
    projectId,
    municipio,
    copy,
    subscribed,
    segmento,
    confirmedPosition,
    busy,
    register,
    saveSegmento,
  }), [busy, confirmedPosition, copy, municipio, projectId, register, saveSegmento, segmento, subscribed]);

  function openSheet() {
    recordSeguirClic("barra");
    setSheetOpen(true);
  }

  function closeSheet() {
    setSheetOpen(false);
  }

  function hideBar() {
    dismissBar(projectId);
    setBarHidden(true);
    setSheetOpen(false);
  }

  return (
    <SeguirContext.Provider value={value}>
      <div className={barHidden ? "seguir-proyecto-scope seguir-bar-off" : "seguir-proyecto-scope"}>
        {children}
        {barHidden ? null : (
          <div className="seguir-bar" role="region" aria-label={copy.barra} hidden={sheetOpen || undefined}>
            <button
              ref={barButtonRef}
              type="button"
              className="inline-flex min-h-11 min-w-0 flex-1 items-center justify-center rounded-lg bg-[var(--portal-accent)] px-3 py-2 text-center text-sm font-semibold leading-tight text-white hover:bg-[var(--portal-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--portal-ink)]"
              onClick={openSheet}
            >
              {copy.barra}
            </button>
            <button
              type="button"
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-lg text-[var(--portal-ink)] hover:bg-[var(--portal-paper-deep)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--portal-ink)]"
              aria-label="Cerrar el aviso"
              onClick={hideBar}
            >
              <span aria-hidden="true">×</span>
            </button>
          </div>
        )}
        <dialog
          ref={dialogRef}
          className="seguir-dialog"
          aria-labelledby="seguir-barra-titulo"
          onClose={closeSheet}
          onClick={(event) => {
            if (event.target === event.currentTarget) closeSheet();
          }}
        >
          <div className="p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <div className="mb-3 flex items-start justify-between gap-3">
              <h2 id="seguir-barra-titulo" className="text-base font-semibold leading-snug text-[var(--portal-ink)]">
                {copy.titulo}
              </h2>
              <button
                type="button"
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--portal-ink)]"
                aria-label="Cerrar"
                onClick={closeSheet}
              >
                <span aria-hidden="true">×</span>
              </button>
            </div>
            {sheetOpen ? <SeguirProyectoForm position="barra" /> : null}
          </div>
        </dialog>
      </div>
    </SeguirContext.Provider>
  );
}

function useOnScreen(position: SeguirPosicion) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      recordSeguirVisto(position);
      return;
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry?.isIntersecting) return;
      recordSeguirVisto(position);
      observer.disconnect();
    }, { threshold: 0.25 });
    observer.observe(node);
    return () => observer.disconnect();
  }, [position]);
  return ref;
}

export function SeguirProyectoForm({ position }: { position: SeguirPosicion }) {
  const seguir = useSeguir();
  const headingId = useId();
  const seenRef = useOnScreen(position);
  const confirming = seguir.subscribed && seguir.confirmedPosition === position;
  const already = seguir.subscribed && !confirming;

  return (
    <section
      ref={seenRef}
      data-seguir-posicion={position}
      aria-labelledby={position === "barra" ? undefined : headingId}
      className={position === "pie"
        ? "mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6"
        : "w-full"}
    >
      {already ? (
        <p role="status" className="rounded-xl border border-[#d9e0d2] bg-[#f7f3eb] px-3 py-2 text-sm text-[#344a40]">
          {seguir.copy.ya}
        </p>
      ) : confirming ? (
        <Confirmation headingId={headingId} position={position} />
      ) : (
        <SignupForm headingId={headingId} position={position} />
      )}
    </section>
  );
}

function SignupForm({ position, headingId }: { position: SeguirPosicion; headingId: string }) {
  const seguir = useSeguir();
  const emailId = useId();
  const noteId = useId();
  const errorId = useId();
  const [error, setError] = useState("");
  const [discarded, setDiscarded] = useState(false);
  const buttonLabel = position === "documentos" ? seguir.copy.botonDocumentos : seguir.copy.boton;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (seguir.busy) return;
    const form = new FormData(event.currentTarget);
    const website = form.get("website");
    if (typeof website === "string" && website.trim()) {
      setDiscarded(true);
      void fetch("/api/launch-waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.get("email"), website, source: "project", contextKey: seguir.projectId, posicion: position }),
      }).catch(() => {});
      return;
    }
    if (position !== "barra") recordSeguirClic(position);
    const email = form.get("email");
    if (!normalizeEmail(email)) {
      setError(SEGUIR_EMAIL_ERROR);
      return;
    }
    const result = await seguir.register(String(email), position);
    if (result === "ok") setError("");
    else setError(result === "invalid" ? SEGUIR_EMAIL_ERROR : SEGUIR_SAVE_ERROR);
  }

  if (discarded) {
    return (
      <div className={cardClass(position)} role="status">
        <p className="text-sm text-[#344a40]">Gracias por tu interés.</p>
      </div>
    );
  }

  return (
    <div className={`${cardClass(position)}${position === "cabecera" ? " lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)] lg:items-center lg:gap-10" : ""}`}>
      <div>
        {position === "barra" ? null : (
          <h2 id={headingId} className={position === "pie" ? "text-2xl font-semibold tracking-tight text-[var(--portal-ink)]" : position === "cabecera" ? "text-xl font-semibold tracking-tight text-[var(--portal-ink)]" : "text-base font-semibold text-[var(--portal-ink)]"}>
            {seguir.copy.titulo}
          </h2>
        )}
        <p className={position === "pie" || position === "cabecera" ? "mt-2 max-w-xl text-sm leading-relaxed text-[#52645c]" : "mt-1 text-sm leading-snug text-[#52645c]"}>
          {seguir.copy.texto}
        </p>
      </div>
      <form className={position === "cabecera" ? "mt-4 lg:mt-0" : "mt-3"} onSubmit={onSubmit} noValidate aria-busy={seguir.busy}>
        <label htmlFor={emailId} className="sr-only">Correo electrónico</label>
        <div className={position === "pie" || position === "cabecera" ? "flex flex-col gap-2 sm:flex-row" : "flex flex-col gap-2"}>
          <input
            id={emailId}
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={254}
            required
            placeholder="Tu correo electrónico"
            data-seguir-focus={position === "barra" ? "" : undefined}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${noteId} ${errorId}` : noteId}
            className="min-h-11 w-full rounded-lg border border-[#b8c6b5] bg-white px-3 text-base text-[var(--portal-ink)] outline-none placeholder:text-[#717c72] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--portal-accent)]"
          />
          <button
            type="submit"
            disabled={seguir.busy}
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-[var(--portal-accent)] px-4 text-center text-sm font-semibold text-white hover:bg-[var(--portal-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--portal-ink)] disabled:cursor-wait disabled:opacity-65"
          >
            {seguir.busy ? "Guardando…" : buttonLabel}
          </button>
        </div>
        <div className="absolute h-px w-px overflow-hidden [clip-path:inset(50%)]" aria-hidden="true">
          <label htmlFor={`${emailId}-web`}>Sitio web</label>
          <input id={`${emailId}-web`} name="website" type="text" tabIndex={-1} autoComplete="off" />
        </div>
        <p id={noteId} className="mt-2 text-xs leading-relaxed text-[#596b5c]">
          {seguir.copy.legal}{" "}
          <Link href="/privacidad" className="underline decoration-[#596b5c] underline-offset-2 hover:text-[var(--portal-ink)]">
            Política de privacidad
          </Link>
          .
        </p>
        {error ? (
          <p id={errorId} role="alert" className="mt-2 text-sm leading-snug text-[#98432a]">{error}</p>
        ) : null}
      </form>
    </div>
  );
}

function Confirmation({ position, headingId }: { position: SeguirPosicion; headingId: string }) {
  const seguir = useSeguir();
  const questionId = useId();
  const questionRef = useRef<HTMLParagraphElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    questionRef.current?.focus();
  }, []);

  async function choose(option: SeguirSegmento) {
    if (seguir.busy || seguir.segmento) return;
    setFailed(false);
    const ok = await seguir.saveSegmento(option);
    if (!ok) setFailed(true);
  }

  return (
    <div className={cardClass(position)} role="status">
      {position === "barra" ? null : (
        <h2 id={headingId} className="text-base font-semibold text-[var(--portal-ink)]">{seguir.copy.ya}</h2>
      )}
      <p className="mt-1 text-sm leading-relaxed text-[#52645c]">
        {seguir.copy.confirmacion}
      </p>
      {seguir.segmento ? (
        <p className="mt-3 text-sm text-[#344a40]">Gracias. Hemos anotado tu respuesta.</p>
      ) : (
        <div className="mt-4">
          <p id={questionId} ref={questionRef} tabIndex={-1} className="text-sm font-semibold text-[var(--portal-ink)] outline-none">
            {seguir.copy.pregunta}
          </p>
          <div className="mt-2 flex flex-col gap-2" role="group" aria-labelledby={questionId}>
            {SEGUIR_SEGMENTOS.map((option) => (
              <button
                key={option}
                type="button"
                disabled={seguir.busy}
                onClick={() => choose(option)}
                className="min-h-11 rounded-lg border border-[#b8c6b5] bg-white px-3 text-left text-sm text-[var(--portal-ink)] hover:bg-[#eef2e8] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--portal-accent)] disabled:cursor-wait disabled:opacity-65"
              >
                {option}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-[#596b5c]">Es opcional. El alta ya está hecha si no respondes.</p>
          {failed ? <p role="alert" className="mt-2 text-sm text-[#98432a]">{SEGUIR_SEGMENT_ERROR}</p> : null}
        </div>
      )}
    </div>
  );
}

function cardClass(position: SeguirPosicion) {
  if (position === "pie") {
    return "rounded-2xl border border-[#d9e0d2] bg-[#edf0e7] p-5 text-[var(--portal-ink)] sm:p-8";
  }
  if (position === "barra") return "text-[var(--portal-ink)]";
  if (position === "cabecera") {
    return "rounded-xl border border-[#d9e0d2] bg-[#f7f3eb] p-5 text-[var(--portal-ink)] sm:px-8 sm:py-6";
  }
  return "rounded-xl border border-[#d9e0d2] bg-[#f7f3eb] p-3 text-[var(--portal-ink)] shadow-sm";
}

export function SeguirProyectoPie() {
  return <SeguirProyectoForm position="pie" />;
}
