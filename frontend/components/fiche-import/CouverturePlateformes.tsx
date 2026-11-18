"use client";

import { AlertTriangle, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { lireCouverturePlateformes } from "@/lib/auth-gestionnaire";
import {
  ETATS_MOIS_PLATEFORME,
  nomPlateforme,
  type CouverturePlateformes as Couverture,
  type EtatMoisPlateforme,
} from "@/lib/fiches-import";

/** Couleur de chaque état (tokens du design system), comme la frise bancaire. */
const COULEURS: Record<EtatMoisPlateforme, string> = {
  rollee: "bg-success",
  document: "bg-success/60",
  a_completer: "bg-danger",
  banque: "bg-warning",
  sans_activite: "bg-border",
};

/** AXE-987 : mois par mois, Rollee, la banque et les documents de chaque
 * plateforme. Un mois avec des virements en banque mais sans jour Rollee ni
 * document est à compléter : on y dépose le récapitulatif de la plateforme. */
export function CouverturePlateformes({ ficheId, version }: { ficheId: string; version: string }) {
  const [couverture, setCouverture] = useState<Couverture | null>(null);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    let actif = true;
    lireCouverturePlateformes(ficheId)
      .then((c) => {
        if (!actif) return;
        setErreur("");
        setCouverture(c);
      })
      .catch((e: unknown) => actif && setErreur(e instanceof Error ? e.message : "Erreur inattendue."));
    return () => {
      actif = false;
    };
  }, [ficheId, version]);

  if (erreur) return <p className="text-sm text-danger">{erreur}</p>;
  if (!couverture) {
    return (
      <p className="flex items-center gap-2 text-sm text-subtle">
        <LoaderCircle className="size-4 animate-spin" aria-hidden /> Calcul de la couverture des plateformes…
      </p>
    );
  }
  return (
    <section className="space-y-4" aria-labelledby="couverture-plateformes">
      <div>
        <h3 id="couverture-plateformes" className="text-sm font-semibold text-ink">
          Couverture des plateformes
        </h3>
        <p className="mt-0.5 text-xs text-subtle">
          Un mois est couvert quand chaque virement de la plateforme en banque a ses jours Rollee, ou
          qu&apos;un récapitulatif du mois est déposé. Rollee sans virement : c&apos;est la banque qui
          manque.
        </p>
      </div>
      {couverture.a_completer.length > 0 && (
        <div className="rounded-md border border-danger-border bg-danger-subtle p-3 text-sm text-ink">
          <p className="flex items-center gap-2 font-medium">
            <AlertTriangle className="size-4 text-danger" aria-hidden /> Documents à demander
          </p>
          <ul className="mt-1 list-disc pl-6 text-xs">
            {couverture.a_completer.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      {couverture.plateformes.length === 0 ? (
        <p className="text-sm text-subtle">
          {couverture.dossier
            ? "Aucun virement de plateforme en banque, aucun jour Rollee."
            : "La couverture se calcule une fois le dossier créé (banque et Rollee)."}
        </p>
      ) : (
        couverture.plateformes.map((p) => (
          <div key={p.plateforme}>
            <p className="text-sm font-medium text-ink">{nomPlateforme(p.plateforme)}</p>
            <ol className="mt-1 flex flex-wrap gap-1" aria-label={`Mois de ${nomPlateforme(p.plateforme)}`}>
              {p.mois.map((m) => (
                <li
                  key={m.mois}
                  title={`${m.libelle} : ${ETATS_MOIS_PLATEFORME[m.etat]}`}
                  className={`h-6 w-9 rounded-sm text-center text-[10px] leading-6 text-ink ${COULEURS[m.etat]}`}
                >
                  <span className="sr-only">
                    {m.libelle} : {ETATS_MOIS_PLATEFORME[m.etat]}
                  </span>
                  <span aria-hidden>{m.mois.slice(5)}/{m.mois.slice(2, 4)}</span>
                </li>
              ))}
            </ol>
          </div>
        ))
      )}
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-subtle">
        {(Object.keys(ETATS_MOIS_PLATEFORME) as EtatMoisPlateforme[]).map((etat) => (
          <li key={etat} className="flex items-center gap-1.5">
            <span className={`inline-block size-2.5 rounded-sm ${COULEURS[etat]}`} aria-hidden />
            {ETATS_MOIS_PLATEFORME[etat]}
          </li>
        ))}
      </ul>
    </section>
  );
}
