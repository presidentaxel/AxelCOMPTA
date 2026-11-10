"use client";

import { useState } from "react";

/** Pourquoi une relance n'envoie rien. Les canaux sont prévus, pas reliés. */
/** AXE-808 : le texte suit ce qui est branché dans Intégrations. */
export function pourquoiEnvoi(canaux: readonly string[] | null): string {
  if (!canaux || canaux.length === 0) return POURQUOI_RIEN_N_EST_ENVOYE;
  const noms = canaux.map((c) => (c === "mail" ? "e-mail" : "SMS")).join(" et ");
  return `Les rappels partent par ${noms}, branché(s) dans Intégrations. L'appel n'est pas encore relié. Chaque envoi se suit sur la fiche de l'entreprise.`;
}

export const POURQUOI_RIEN_N_EST_ENVOYE =
  "Les canaux SMS, e-mail et appel sont prévus. Ils ne sont pas encore reliés : Intégrations les marque « Prévu ». La relance est enregistrée. L'entreprise ne reçoit rien pour l'instant.";

/** Un « ? » qui ouvre l'explication. Le texte court à côté ne suffit pas. */
export function Aide({ texte, tactile = false }: { texte: string; tactile?: boolean }) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <span className="relative inline-block align-middle">
      <button
        type="button"
        aria-expanded={ouvert}
        aria-label="Pourquoi ?"
        onClick={() => setOuvert((actuel) => !actuel)}
        className={
          tactile
            ? "ml-1 inline-flex h-11 w-11 items-center justify-center rounded-full border border-border text-xs leading-none text-subtle outline-none hover:border-ink hover:text-ink focus-visible:shadow-focus"
            : "ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-border text-xs leading-none text-subtle outline-none hover:border-ink hover:text-ink focus-visible:shadow-focus"
        }
      >
        ?
      </button>
      {ouvert && (
        <span
          role="note"
          className="absolute left-0 top-6 z-20 w-64 rounded-md border border-border bg-canvas p-3 text-left text-sm font-normal text-subtle shadow-sm"
        >
          {texte}
        </span>
      )}
    </span>
  );
}
