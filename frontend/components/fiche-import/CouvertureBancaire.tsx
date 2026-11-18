"use client";

import { AlertTriangle, LoaderCircle, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  lireCouvertureBanque,
  rattacherCompteBanque,
  retirerSoldeBanque,
  saisirSoldeBanque,
} from "@/lib/auth-gestionnaire";
import {
  ciblesPossibles,
  euros,
  largeurs,
  libelleEtatBanque,
  type CompteBanque,
  type CompteConnu,
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
export function CouvertureBancaire({
  ficheId,
  version,
  modifiable,
}: {
  ficheId: string;
  version: string;
  modifiable: boolean;
}) {
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

  /** Un réglage rend la couverture recalculée ; une erreur s'affiche. */
  async function regler(appel: Promise<CouvertureBanque>): Promise<void> {
    try {
      setCouverture(await appel);
      setErreur("");
    } catch (e: unknown) {
      setErreur(e instanceof Error ? e.message : "Erreur inattendue.");
    }
  }

  if (erreur && !couverture) return <p className="text-sm text-danger">{erreur}</p>;
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
      {erreur && <p className="text-sm text-danger">{erreur}</p>}
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
        couverture.comptes.map((c) => (
          <Compte
            key={c.cle}
            compte={c}
            connus={couverture.comptes_connus ?? []}
            reglages={
              modifiable
                ? {
                    rattacher: (source, cible) => regler(rattacherCompteBanque(ficheId, source, cible)),
                    saisir: (solde) => regler(saisirSoldeBanque(ficheId, solde)),
                    retirer: (rang) => regler(retirerSoldeBanque(ficheId, rang)),
                  }
                : null
            }
          />
        ))
      )}
    </section>
  );
}

type Reglages = {
  rattacher: (source: string, cible: string | null) => Promise<void>;
  saisir: (solde: { compte: string; le: string; montant: string; source: string }) => Promise<void>;
  retirer: (rang: number) => Promise<void>;
};

function Compte({
  compte,
  connus,
  reglages,
}: {
  compte: CompteBanque;
  connus: CompteConnu[];
  reglages: Reglages | null;
}) {
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
              <li key={`${s.le}-${s.source}`} className="flex items-center gap-2">
                <span>
                  {new Date(s.le).toLocaleDateString("fr-FR")} : {euros(s.cts)} · {s.source}
                </span>
                {reglages && s.rang != null && (
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Retirer le solde du ${new Date(s.le).toLocaleDateString("fr-FR")}`}
                    onClick={() => void reglages.retirer(s.rang as number)}
                  >
                    <Trash2 className="size-3.5" aria-hidden />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
      {compte.incoherences.map((i) => (
        <p key={i} className="text-xs text-danger">{i}</p>
      ))}
      {(compte.reunit ?? []).length > 0 && (
        <ul className="text-xs text-subtle">
          {(compte.reunit ?? []).map((r) => (
            <li key={r.cle} className="flex items-center gap-2">
              Réunit : {r.libelle}
              {reglages && (
                <Button size="sm" variant="ghost" onClick={() => void reglages.rattacher(r.cle, null)}>
                  Détacher
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {reglages && compte.origine !== "digifactory" && (
        <label className="flex flex-wrap items-center gap-2 text-xs text-subtle">
          C&apos;est en fait le compte
          <select
            value=""
            onChange={(e) => e.target.value && void reglages.rattacher(compte.cle, e.target.value)}
            className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-ink"
            aria-label={`Rattacher ${compte.libelle} à un autre compte`}
          >
            <option value="">— choisir —</option>
            {ciblesPossibles(compte, connus).map((c) => (
              <option key={c.cle} value={c.cle}>
                {c.libelle}
              </option>
            ))}
          </select>
        </label>
      )}
      {reglages && <SaisieSolde compte={compte.cle} saisir={reglages.saisir} />}
    </div>
  );
}

/** Un solde lu sur un relevé PDF, en fin de journée, en attendant l'OCR. */
function SaisieSolde({ compte, saisir }: { compte: string; saisir: Reglages["saisir"] }) {
  const [le, setLe] = useState("");
  const [montant, setMontant] = useState("");
  const [source, setSource] = useState("");
  const [envoi, setEnvoi] = useState(false);
  return (
    <form
      className="flex flex-wrap items-end gap-2 border-t border-border pt-2 text-xs"
      onSubmit={async (e) => {
        e.preventDefault();
        setEnvoi(true);
        try {
          await saisir({ compte, le, montant, source: source || "Relevé" });
          setLe("");
          setMontant("");
          setSource("");
        } finally {
          setEnvoi(false);
        }
      }}
    >
      <span className="w-full text-subtle">Ajouter un solde lu sur un relevé (fin de journée)</span>
      <input type="date" required value={le} onChange={(e) => setLe(e.target.value)}
        className="h-9 rounded-md border border-border bg-surface px-2 text-ink" aria-label="Date du solde" />
      <input required inputMode="decimal" placeholder="1 367,16" value={montant}
        onChange={(e) => setMontant(e.target.value)}
        className="h-9 w-28 rounded-md border border-border bg-surface px-2 text-ink" aria-label="Solde en euros" />
      <input placeholder="Relevé Bred septembre 2025" value={source} onChange={(e) => setSource(e.target.value)}
        className="h-9 min-w-40 flex-1 rounded-md border border-border bg-surface px-2 text-ink"
        aria-label="Relevé d'où vient le solde" />
      <Button type="submit" size="sm" disabled={envoi || !le || !montant}>
        {envoi && <LoaderCircle className="size-3.5 animate-spin" aria-hidden />}
        Ajouter
      </Button>
    </form>
  );
}
