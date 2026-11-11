"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { indexFocusPiege } from "@/lib/piege-focus";

const FOCALISABLES =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Fenêtre modale (DESIGN.md § `modal`), en feuille du bas sur l'espace
 * chauffeur : au-dessus de la barre, la hauteur suit le visual viewport et
 * l'encoche pour que le clavier ne coupe pas le bas de la feuille (classes
 * `fond-feuille` et `feuille-chauffeur`, globals.css).
 *
 * Accessibilité : le focus entre dans la fenêtre à l'ouverture, Tab et
 * Maj+Tab y restent piégés, Échap et un clic sur le fond ferment, le focus
 * revient à l'élément qui l'avait à l'ouverture, et la page ne défile plus
 * derrière. */
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
  const fenetre = useRef<HTMLDivElement>(null);
  // `onFermer` change à chaque rendu de l'appelant : on lit toujours la
  // dernière, sans relancer l'effet (qui rendrait le focus à chaque rendu).
  const fermer = useRef(onFermer);
  useEffect(() => {
    fermer.current = onFermer;
  });

  useEffect(() => {
    const declencheur = document.activeElement;
    const defilementInitial = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    fenetre.current?.focus();

    function onTouche(event: KeyboardEvent) {
      if (event.key === "Escape") {
        fermer.current();
        return;
      }
      if (event.key !== "Tab" || !fenetre.current) return;
      const elements = Array.from(fenetre.current.querySelectorAll<HTMLElement>(FOCALISABLES));
      const cible = indexFocusPiege(
        elements.length,
        elements.indexOf(document.activeElement as HTMLElement),
        event.shiftKey,
      );
      if (cible !== null) {
        event.preventDefault();
        elements[cible].focus();
      } else if (elements.length === 0) {
        event.preventDefault();
      }
    }
    document.addEventListener("keydown", onTouche);
    return () => {
      document.removeEventListener("keydown", onTouche);
      document.body.style.overflow = defilementInitial;
      if (declencheur instanceof HTMLElement && declencheur.isConnected) declencheur.focus();
    };
  }, []);

  return (
    <div
      className="fond-feuille fixed inset-0 z-20 flex items-end justify-center bg-ink/50 px-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onFermer();
      }}
    >
      <div
        ref={fenetre}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titreId}
        tabIndex={-1}
        className="feuille-chauffeur w-full max-w-[520px] overflow-y-auto rounded-xl border border-border bg-canvas p-6 text-ink shadow-overlay outline-none"
      >
        <h2 id={titreId} className="text-xl font-semibold">
          {titre}
        </h2>
        {children}
      </div>
    </div>
  );
}
