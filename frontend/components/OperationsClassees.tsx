"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { imputerExpert, lireClassees, noterVerdict } from "@/lib/auth-gestionnaire";
import {
  changer,
  type Cle,
  type EtatClassees,
  formatConfiance,
  ORIGINES,
  phraseCompteurs,
  SENS,
  STATUTS,
  TRANCHES,
  TRIS,
  versApi,
} from "@/lib/classees";
import { formatDate, formatMontant } from "@/lib/format";
import type { OperationClassee, OperationsClassees as Donnees } from "@/lib/types";

/** Ce qui est déjà classé, et par qui ou quoi (AXE-823). « Juste » note sans
 * écrire ; « Ce classement est faux » note, puis propose l'imputation. */
export function OperationsClassees({
  etat,
  comptes,
  ecriture,
  onChanger,
}: {
  etat: EtatClassees;
  comptes: { compte: string; libelle: string }[];
  ecriture: boolean;
  onChanger: (suivant: EtatClassees) => void;
}) {
  const [donnees, setDonnees] = useState<Donnees | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const requete = versApi(etat).toString();

  useEffect(() => {
    let actif = true;
    lireClassees(new URLSearchParams(requete))
      .then((reponse) => actif && setDonnees(reponse))
      .catch((exception) => actif && setErreur(exception instanceof Error ? exception.message : "Erreur."));
    return () => {
      actif = false;
    };
  }, [requete, version]);

  function choisir(cle: Cle, valeur: string) {
    onChanger(changer(etat, cle, valeur));
  }

  return (
    <div className="mt-6">
      {donnees && <p className="text-sm text-ink">{phraseCompteurs(donnees.compteurs)}.</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Choix libelle="Origine" valeur={etat.origine} options={ORIGINES} onChoisir={(v) => choisir("origine", v)} />
        <Choix
          libelle="Catégorie"
          valeur={etat.categorie}
          options={Object.fromEntries((donnees?.categories ?? []).map((c) => [c, c]))}
          onChoisir={(v) => choisir("categorie", v)}
        />
        <Choix libelle="Confiance" valeur={etat.tranche} options={TRANCHES} onChoisir={(v) => choisir("tranche", v)} />
        <Choix libelle="Sens" valeur={etat.sens} options={SENS} onChoisir={(v) => choisir("sens", v)} />
        <Choix libelle="Tri" valeur={etat.tri} options={TRIS} onChoisir={(v) => choisir("tri", v)} sansTous />
      </div>
      {erreur && <p className="mt-4 text-sm text-danger">{erreur}</p>}
      {donnees && donnees.operations.length === 0 && (
        <p className="mt-6 text-sm text-subtle">Aucune opération pour ces filtres.</p>
      )}
      <ul className="mt-4">
        {donnees?.operations.map((operation) => (
          <Ligne
            key={`${operation.dossier_id}-${operation.ecriture_id}`}
            operation={operation}
            comptes={comptes}
            ecriture={ecriture}
            onFait={() => setVersion((v) => v + 1)}
          />
        ))}
      </ul>
      {donnees && donnees.pages > 1 && (
        <div className="mt-4 flex items-center gap-3 text-sm text-subtle">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={donnees.page <= 1}
            onClick={() => choisir("page", String(donnees.page - 1))}
          >
            Page précédente
          </Button>
          <span>
            Page {donnees.page} sur {donnees.pages} · {donnees.total} opérations
          </span>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={donnees.page >= donnees.pages}
            onClick={() => choisir("page", String(donnees.page + 1))}
          >
            Page suivante
          </Button>
        </div>
      )}
    </div>
  );
}

function Choix({
  libelle,
  valeur,
  options,
  onChoisir,
  sansTous = false,
}: {
  libelle: string;
  valeur: string;
  options: Record<string, string>;
  onChoisir: (valeur: string) => void;
  sansTous?: boolean;
}) {
  return (
    <label className="text-sm text-subtle">
      {libelle}
      <select
        value={valeur}
        onChange={(evenement) => onChoisir(evenement.target.value)}
        className="ml-2 h-9 rounded-md border border-border bg-canvas px-3 text-sm text-ink"
      >
        {!sansTous && <option value="">Toutes</option>}
        {Object.entries(options).map(([id, texte]) => (
          <option key={id} value={id}>
            {texte}
          </option>
        ))}
      </select>
    </label>
  );
}

function Ligne({
  operation,
  comptes,
  ecriture,
  onFait,
}: {
  operation: OperationClassee;
  comptes: { compte: string; libelle: string }[];
  ecriture: boolean;
  onFait: () => void;
}) {
  const [corriger, setCorriger] = useState(false);
  const [compte, setCompte] = useState("");
  const [motif, setMotif] = useState(""); // AXE-800 : obligatoire
  const [erreur, setErreur] = useState<string | null>(null);

  function verdict(valeur: "juste" | "faux") {
    setErreur(null);
    noterVerdict(operation.dossier_id, operation.ecriture_id, valeur)
      .then(() => {
        if (valeur === "faux") setCorriger(true);
        onFait();
      })
      .catch((exception) => setErreur(exception instanceof Error ? exception.message : "Erreur."));
  }

  function imputer() {
    setErreur(null);
    imputerExpert(operation.dossier_id, operation.ecriture_id, compte, motif.trim())
      .then(() => {
        setCorriger(false);
        onFait();
      })
      .catch((exception) => setErreur(exception instanceof Error ? exception.message : "Erreur."));
  }

  return (
    <li className="border-b border-hairline py-3">
      <div className="flex items-baseline justify-between gap-4">
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-ink">{operation.libelle}</span>
          <span className="block text-xs text-subtle">
            {formatDate(operation.date)} · {operation.dossier_nom} · {STATUTS[operation.statut] ?? operation.statut}
          </span>
        </span>
        <span
          className={`shrink-0 tabular-nums text-sm ${operation.montant_cts < 0 ? "text-amount-negative" : "text-amount-positive"}`}
        >
          {formatMontant(operation.montant_cts)}
        </span>
      </div>
      <p className="mt-1 text-xs text-subtle">
        Compte {operation.compte}
        {operation.categorie ? ` · ${operation.categorie}` : ""} · {ORIGINES[operation.origine] ?? operation.origine} ·
        confiance {formatConfiance(operation.confiance)}
        {operation.verdict ? ` · noté ${operation.verdict}` : ""}
      </p>
      {ecriture && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={() => verdict("juste")}>
            Juste
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => verdict("faux")}>
            Ce classement est faux
          </Button>
          {corriger && (
            <>
              <select
                aria-label="Compte correct"
                value={compte}
                onChange={(evenement) => setCompte(evenement.target.value)}
                className="h-8 rounded-md border border-border bg-canvas px-2 text-sm text-ink"
              >
                <option value="">Compte correct…</option>
                {comptes.map((choix) => (
                  <option key={choix.compte} value={choix.compte}>
                    {choix.compte} · {choix.libelle}
                  </option>
                ))}
              </select>
              <input
                aria-label="Motif de la correction"
                placeholder="Motif (obligatoire)"
                value={motif}
                onChange={(evenement) => setMotif(evenement.target.value)}
                className="h-8 rounded-md border border-border bg-canvas px-2 text-sm text-ink"
              />
              <Button
                type="button"
                size="sm"
                disabled={!compte || motif.trim().length < 3}
                onClick={imputer}
              >
                Imputer
              </Button>
            </>
          )}
        </div>
      )}
      {erreur && <p className="mt-1 text-xs text-danger">{erreur}</p>}
    </li>
  );
}
