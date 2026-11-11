"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Aide } from "@/components/Aide";
import { SuiviEnvois } from "@/components/SuiviEnvois";
import { TagsDuDossier } from "@/components/TagsEntreprises";
import { Button } from "@/components/ui/button";
import { declencherRappel, retirerDossier, type RegleRappel } from "@/lib/auth-gestionnaire";
import {
  libelleBanque,
  libelleCompte,
  libelleImposition,
  libelleRegimeTva,
  libelleTvaRecettes,
} from "@/lib/dossier-libelles";
import { formatDate, formatMontant } from "@/lib/format";
import type { DossierAgregat, ReglageTags } from "@/lib/types";

import { Frise } from "./Frise";
import { LIEN_ACTION } from "./style";

const CANAL: Record<string, string> = { mail: "E-mail", sms: "SMS", appel: "Appel" };

function libelleCanaux(canaux: string[]): string {
  return canaux.map((canal) => CANAL[canal] ?? canal).join(", ");
}

type Props = {
  dossier: DossierAgregat;
  /** Toutes les raisons « à traiter », la liste n'en dit qu'une. */
  raisons: string[];
  regles: RegleRappel[];
  /** Texte de l'aide « Pourquoi ? » des rappels. */
  aideRappels: string;
  reglageTags: ReglageTags | null;
  admin: boolean;
  ecriture: boolean;
  onFermer: () => void;
  /** Un tag ou un retrait a changé : relire le portefeuille. */
  onModifie: () => void;
  onRetire: () => void;
};

/** Fiche d'une entreprise, en panneau fixe à droite de l'écran.
 *
 * Elle est posée hors du flux (`fixed`) et non en colonne : la largeur de la
 * page, 1180 px et ses marges, appartient à la mise en page de l'espace
 * gestionnaire, la liste ne doit pas s'en trouver réduite quand on ouvre une
 * fiche. Le panneau ne bloque pas la liste (pas de fond sombre) : on peut
 * passer d'une entreprise à l'autre. Échap le ferme.
 *
 * À monter avec `key={dossier.dossier_id}` : l'info de rappel et la
 * confirmation de retrait repartent de zéro d'une entreprise à l'autre. */
export function FicheEntreprise({
  dossier,
  raisons,
  regles,
  aideRappels,
  reglageTags,
  admin,
  ecriture,
  onFermer,
  onModifie,
  onRetire,
}: Props) {
  const [infoRappel, setInfoRappel] = useState<string | null>(null);
  const [confirmerRetrait, setConfirmerRetrait] = useState(false);
  const [erreurRetrait, setErreurRetrait] = useState<string | null>(null);

  useEffect(() => {
    function surTouche(evenement: KeyboardEvent) {
      if (evenement.key === "Escape") onFermer();
    }
    document.addEventListener("keydown", surTouche);
    return () => document.removeEventListener("keydown", surTouche);
  }, [onFermer]);

  const compteOuvert = dossier.statut_invitation === "actif";
  const titreId = `fiche-${dossier.dossier_id}`;

  return (
    <aside
      aria-labelledby={titreId}
      className="fixed inset-y-0 right-0 z-30 flex w-96 max-w-full flex-col overflow-hidden border-l border-border bg-canvas shadow-overlay"
    >
      <div className="flex shrink-0 items-start justify-between gap-4 p-6 pb-4">
        <h2 id={titreId} className="min-w-0 truncate text-lg font-semibold text-ink">
          {dossier.nom}
        </h2>
        <span className="flex shrink-0 flex-nowrap gap-1">
          {admin && (
            <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmerRetrait(true)}>
              Retirer
            </Button>
          )}
          <Button type="button" variant="ghost" size="sm" onClick={onFermer}>
            Fermer
          </Button>
        </span>
      </div>
      <p className="mt-1 px-6 text-sm text-subtle">{libelleCompte(dossier.statut_invitation)}</p>
      <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6">
        <Link href={`/anomalies/${dossier.dossier_id}`} className={`mt-3 inline-block text-sm ${LIEN_ACTION}`}>
          Anomalies
        </Link>
        {raisons.length > 0 && (
          <div className="mt-6">
            <p className="text-sm font-medium text-ink">À traiter</p>
            <ul className="mt-2 space-y-1">
              {raisons.map((raison) => (
                <li key={raison} className="text-sm text-body">
                  {raison}
                </li>
              ))}
            </ul>
          </div>
        )}
        <TagsDuDossier
          dossierId={dossier.dossier_id}
          tags={dossier.tags ?? []}
          reglage={reglageTags}
          ecriture={ecriture}
          onModifie={onModifie}
        />
        <div className="mt-6 space-y-1">
          <Frise annee={dossier.annee_courante} etape={dossier.etape_courante} compteOuvert={compteOuvert} />
          <Frise annee={dossier.annee_precedente} etape={dossier.etape_precedente} compteOuvert={compteOuvert} />
        </div>
        <dl className="mt-6 space-y-4 text-sm">
          <Ligne libelle="Résultat" valeur={formatMontant(dossier.resultat_cts)} montant />
          <Ligne libelle="CA HT" valeur={formatMontant(dossier.ca_ht_cts)} montant />
          <Ligne libelle="Charges" valeur={formatMontant(dossier.charges_cts)} montant />
          <Ligne libelle="Forme" valeur={dossier.forme_juridique} />
          <Ligne libelle="Imposition" valeur={libelleImposition(dossier.regime_imposition)} />
          <Ligne libelle="Régime de TVA" valeur={libelleRegimeTva(dossier.regime_tva)} />
          <Ligne libelle="TVA sur les recettes" valeur={libelleTvaRecettes(dossier.tva_recettes_regime)} />
          <Ligne libelle="Banque" valeur={libelleBanque(dossier.mode_acces_bancaire)} />
          {dossier.plateformes.length > 0 && <Ligne libelle="Plateformes" valeur={dossier.plateformes.join(", ")} />}
          {dossier.exercice_debut && (
            <Ligne
              libelle="Exercice"
              valeur={
                dossier.exercice_fin
                  ? `${formatDate(dossier.exercice_debut)} au ${formatDate(dossier.exercice_fin)}`
                  : formatDate(dossier.exercice_debut)
              }
            />
          )}
        </dl>
        <div className="mt-8">
          <p className="text-sm font-medium text-ink">
            Rappels
            <Aide texte={aideRappels} />
          </p>
          {regles.length === 0 && (
            <p className="mt-2 text-sm text-subtle">Aucune règle. Elles se préparent dans Rappels.</p>
          )}
          <div className="mt-2 flex flex-col gap-2">
            {regles
              .filter((regle) => regle.declencheur === "manuel")
              .filter((regle) => regle.portee !== "selection" || regle.dossier_ids.includes(dossier.dossier_id))
              .map((regle) => (
                <div key={regle.id}>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={!ecriture}
                    onClick={async () => {
                      setInfoRappel(null);
                      try {
                        await declencherRappel(regle.id, dossier.dossier_id);
                        setInfoRappel(`${regle.libelle} enregistré. Envoi prévu quand le canal sera branché.`);
                      } catch (exception) {
                        setInfoRappel(exception instanceof Error ? exception.message : "Échec du rappel.");
                      }
                    }}
                  >
                    {regle.libelle}
                  </Button>
                  <p className="mt-1 text-xs text-subtle">
                    {libelleCanaux(regle.canaux)} — {regle.message}
                  </p>
                </div>
              ))}
          </div>
          {infoRappel && <p className="mt-2 text-sm text-subtle">{infoRappel}</p>}
          <SuiviEnvois dossierId={dossier.dossier_id} />
        </div>
        {confirmerRetrait && (
          <div className="mt-6 rounded-lg border border-border bg-canvas-app p-4">
            <p className="text-sm text-ink">
              Retirer {dossier.nom} de la liste ? Les écritures restent. Vous pourrez remettre l&apos;entreprise
              dans la liste.
            </p>
            {erreurRetrait && <p className="mt-2 text-sm text-danger">{erreurRetrait}</p>}
            <div className="mt-3 flex justify-end gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmerRetrait(false)}>
                Annuler
              </Button>
              <Button
                type="button"
                variant="danger"
                size="sm"
                onClick={async () => {
                  setErreurRetrait(null);
                  try {
                    await retirerDossier(dossier.dossier_id);
                    setConfirmerRetrait(false);
                    onRetire();
                  } catch (exception) {
                    setErreurRetrait(exception instanceof Error ? exception.message : "Échec du retrait.");
                  }
                }}
              >
                Retirer
              </Button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

function Ligne({ libelle, valeur, montant = false }: { libelle: string; valeur: string; montant?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-subtle">{libelle}</dt>
      <dd className={`text-right text-ink ${montant ? "tabular-nums" : ""}`}>{valeur}</dd>
    </div>
  );
}
