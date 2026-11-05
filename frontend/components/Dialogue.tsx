"use client";

import { useEffect, type ReactNode } from "react";

/** Feuille du bas, au-dessus de la barre. Échap et le fond ferment.
 * La hauteur suit le visual viewport et l'encoche : le clavier ne coupe
 * pas le bas de la feuille. */
export function Dialogue({
  titre,
  titreId,
  onFermer,
  children,
}: {
  titre: string;
  titreId: string;
  onFermer: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    function onTouche(event: KeyboardEvent) {
      if (event.key === "Escape") onFermer();
    }
    document.addEventListener("keydown", onTouche);
    return () => document.removeEventListener("keydown", onTouche);
  }, [onFermer]);

  return (
    <div
      className="fond-feuille fixed inset-0 z-20 flex items-end justify-center bg-ink/40 px-4"
      onClick={onFermer}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titreId}
        className="feuille-chauffeur w-full max-w-md overflow-y-auto rounded-lg bg-canvas p-5"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id={titreId} className="text-base font-semibold text-ink">
          {titre}
        </h2>
        {children}
      </div>
    </div>
  );
}
