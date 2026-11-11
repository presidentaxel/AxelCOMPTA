"use client";

import { useEffect, useRef } from "react";

import { cn } from "cn";
import { effacerChiffre, ecrireChiffres, LONGUEUR_CODE } from "@/lib/mfa-code";

/** Six cases, un chiffre chacune. Taper avance, effacer une case vide
 * revient à la précédente. */
export function SaisieCode({
  valeur,
  onChange,
  invalide = false,
  idErreur,
  disabled = false,
}: {
  valeur: string;
  onChange: (valeur: string) => void;
  invalide?: boolean;
  idErreur?: string;
  disabled?: boolean;
}) {
  const chiffres = valeur.replace(/\D/g, "").slice(0, LONGUEUR_CODE);
  const cases = Array.from({ length: LONGUEUR_CODE }, (_, i) => chiffres[i] ?? "");
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const toucheGeree = useRef(false);

  useEffect(() => {
    refs.current[0]?.focus();
  }, []);

  useEffect(() => {
    if (!invalide) return;
    const derniere = refs.current[LONGUEUR_CODE - 1];
    derniere?.focus();
    derniere?.select();
  }, [invalide]);

  function viser(index: number) {
    const borne = Math.max(0, Math.min(index, LONGUEUR_CODE - 1));
    const champ = refs.current[borne];
    champ?.focus();
    champ?.select();
  }

  function appliquer(resultat: { cases: string[]; focus: number }) {
    onChange(resultat.cases.join(""));
    viser(resultat.focus);
  }

  return (
    <div
      role="group"
      aria-label="Code à 6 chiffres"
      className="grid grid-cols-6 gap-2"
    >
      {cases.map((chiffre, index) => (
        <input
          key={index}
          ref={(element) => {
            refs.current[index] = element;
          }}
          value={chiffre}
          disabled={disabled}
          inputMode="numeric"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          aria-label={`Chiffre ${index + 1}`}
          aria-invalid={invalide}
          aria-describedby={idErreur}
          className={cn(
            "h-11 w-full min-w-0 rounded-md border border-border bg-canvas text-center text-lg font-semibold tabular-nums text-ink outline-none",
            "focus-visible:border-border-focus focus-visible:shadow-focus",
            "disabled:cursor-not-allowed disabled:opacity-50",
            invalide && "border-danger-border",
          )}
          onFocus={(evenement) => evenement.currentTarget.select()}
          onKeyDown={(evenement) => {
            if (evenement.key === "ArrowLeft") {
              evenement.preventDefault();
              viser(index - 1);
              return;
            }
            if (evenement.key === "ArrowRight") {
              evenement.preventDefault();
              viser(index + 1);
              return;
            }
            if (/^\d$/.test(evenement.key)) {
              evenement.preventDefault();
              toucheGeree.current = true;
              appliquer(ecrireChiffres(cases, index, evenement.key));
              return;
            }
            if (evenement.key !== "Backspace") return;
            evenement.preventDefault();
            toucheGeree.current = true;
            appliquer(effacerChiffre(cases, index));
          }}
          onChange={(evenement) => {
            if (toucheGeree.current) {
              toucheGeree.current = false;
              return;
            }
            const brut = evenement.target.value;
            appliquer(brut === "" ? effacerChiffre(cases, index) : ecrireChiffres(cases, index, brut));
          }}
        />
      ))}
    </div>
  );
}
