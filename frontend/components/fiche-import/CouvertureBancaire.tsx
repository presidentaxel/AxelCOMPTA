"use client";

import { AlertTriangle, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { lireCouvertureBanque } from "@/lib/auth-gestionnaire";
import {
  euros,
  largeurs,
  libelleEtatBanque,
  type CompteBanque,
  type CouvertureBanque,
  type EtatPeriodeBanque,
} from "@/lib/fiches-import";

/** AXE-973 : couleur de chaque état sur la frise (tokens du design system). */
const COULEURS: Record<EtatPeriodeBanque, string> = {
  complet: "bg-success",
  couvert: "bg-border-strong",
  ecart: "bg-warning",
  manquant: "bg-danger",
};

/** La couverture bancaire de la fiche : pour chaque compte, ce que le solde
 * prouve, ce qui manque et de combien. Relue à chaque dépôt (`version`). */
export function CouvertureBancaire({ ficheId, version }: { ficheId: string; version: string }) {
  const [couverture, setCouverture] = useState<CouvertureBanque | null>(null);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    let actif = true;
    lireCouvertureBanque(ficheId)
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
        <LoaderCircle className="size-4 animate-spin" aria-hidden /> Calcul de la couverture bancaire…
      </p>
    );
  }
  return (
    <section className="space-y-4" aria-labelledby="couverture-banque">
      <div>
        <h3 id="couverture-banque" className="text-sm font-semibold text-ink">
          Couverture bancaire
        </h3>
        <p className="mt-0.5 text-xs text-subtle">
          Une période est complète quand le solde le prouve : solde au début + opérations = solde à la
          fin, au centime près. Les jours sans opération sont alors des jours calmes.
        </p>
      </div>
      {couverture.a_completer.length > 0 && (
        <div className="rounded-md border border-danger-border bg-danger-subtle p-3 text-sm text-ink">
          <p className="flex items-center gap-2 font-medium">
            <AlertTriangle className="size-4 text-danger" aria-hidden /> Relevés à demander
          </p>
          <ul className="mt-1 list-disc pl-6 text-xs">
            {couverture.a_completer.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      {couverture.comptes.length === 0 ? (
        <p className="text-sm text-subtle">
          Aucune donnée bancaire : déposez un FEC, un relevé QIF, ou reliez Digifactory.
        </p>
      ) : (
        couverture.comptes.map((c) => <Compte key={c.cle} compte={c} />)
      )}
    </section>
  );
}

function Compte({ compte }: { compte: CompteBanque }) {
  const tailles = largeurs(compte.periodes);
  const debut = compte.periodes[0]?.debut;
  const fin = compte.periodes.at(-1)?.fin;
  return (
    <div className="space-y-2 rounded-lg border border-border p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-medium text-ink">{compte.libelle}</p>
        <p className="text-xs text-subtle">
          {compte.suivi ? "Compte de l'activité" : "Archive"} ·{" "}
          {compte.origine === "digifactory" ? "Digifactory" : compte.origine === "fec" ? "FEC" : "Relevé"}
        </p>
      </div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-canvas-app" role="img"
        aria-label={`Couverture de ${compte.libelle}`}>
        {compte.periodes.map((p, i) => (
          <div key={p.debut} className={COULEURS[p.etat]} style={{ width: `${tailles[i]}%` }}
            title={p.phrase} />
        ))}
      </div>
      {debut && fin && (
        <p className="flex justify-between text-xs text-muted">
          <span>{new Date(debut).toLocaleDateString("fr-FR")}</span>
          <span>{new Date(fin).toLocaleDateString("fr-FR")}</span>
        </p>
      )}
      <ul className="space-y-1 text-xs">
        {compte.periodes
          .filter((p) => p.etat !== "complet" || compte.periodes.length === 1)
          .map((p) => (
            <li key={p.debut}>
              <span className="font-medium text-ink">{libelleEtatBanque(p.etat)}</span>
              <span className="text-subtle"> · {p.phrase}</span>
              {p.sources.length > 0 && <span className="text-muted"> ({p.sources.join(", ")})</span>}
              {p.indices.map((i) => (
                <span key={i} className="block pl-3 text-warning">{i}</span>
              ))}
            </li>
          ))}
      </ul>
      {compte.soldes.length > 0 && (
        <details className="text-xs text-subtle">
          <summary className="cursor-pointer">Soldes connus ({compte.soldes.length})</summary>
          <ul className="mt-1 space-y-0.5">
            {compte.soldes.map((s) => (
              <li key={`${s.le}-${s.source}`}>
                {new Date(s.le).toLocaleDateString("fr-FR")} : {euros(s.cts)} · {s.source}
              </li>
            ))}
          </ul>
        </details>
      )}
      {compte.incoherences.map((i) => (
        <p key={i} className="text-xs text-danger">{i}</p>
      ))}
    </div>
  );
}
