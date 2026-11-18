"use client";

import { CheckCircle2, LoaderCircle, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { lireValidationImport } from "@/lib/auth-gestionnaire";
import type { ValidationImport } from "@/lib/fiches-import";

/** AXE-989 : ce qu'il faut pour que le chauffeur soit importé, pour une
 * section (banque ou plateformes). Exercice à déclarer : complet, relevés ou
 * documents acceptés. Exercice en cours : Digifactory et Rollee à jour. */
export function CriteresImport({
  ficheId,
  section,
  version,
}: {
  ficheId: string;
  section: "banque" | "plateformes";
  version: string;
}) {
  const [validation, setValidation] = useState<ValidationImport | null>(null);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    let actif = true;
    lireValidationImport(ficheId)
      .then((v) => {
        if (!actif) return;
        setErreur("");
        setValidation(v);
      })
      .catch((e: unknown) => actif && setErreur(e instanceof Error ? e.message : "Erreur inattendue."));
    return () => {
      actif = false;
    };
  }, [ficheId, version]);

  if (erreur) return <p className="text-sm text-danger">{erreur}</p>;
  if (!validation) {
    return (
      <p className="flex items-center gap-2 text-sm text-subtle">
        <LoaderCircle className="size-4 animate-spin" aria-hidden /> Vérification des critères…
      </p>
    );
  }
  const siens = validation.criteres.filter((c) => c.section === section);
  const ok = siens.length > 0 && siens.every((c) => c.ok);
  return (
    <section
      aria-labelledby={`criteres-${section}`}
      className={`rounded-md border p-3 text-sm ${ok ? "border-success-border bg-success-subtle" : "border-border"}`}
    >
      <h3 id={`criteres-${section}`} className="font-semibold text-ink">
        Critères d&apos;import {ok ? ": remplis" : ""}
      </h3>
      <p className="mt-0.5 text-xs text-subtle">
        {section === "banque"
          ? "Exercice à déclarer : toutes les écritures, des relevés suffisent. Exercice en cours : Digifactory relié et à jour."
          : "Exercice à déclarer : chaque mois couvert par Rollee ou un document. Exercice en cours : Rollee relié et à jour."}
      </p>
      {!validation.dossier ? (
        <p className="mt-2 text-xs text-subtle">Vérifiés une fois le dossier créé.</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {siens.map((c) => (
            <li key={c.libelle} className="flex items-start gap-2 text-xs">
              {c.ok ? (
                <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" aria-label="Rempli" />
              ) : (
                <XCircle className="mt-0.5 size-3.5 shrink-0 text-danger" aria-label="Manquant" />
              )}
              <span className="text-ink">
                {c.libelle}
                {c.detail && <span className="text-subtle"> · {c.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
