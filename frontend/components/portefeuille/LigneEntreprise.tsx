"use client";

import Link from "next/link";

import { StatutDossier } from "@/components/StatutDossier";
import { PastillesTags } from "@/components/TagsEntreprises";
import { libelleCompte } from "@/lib/dossier-libelles";
import { formatMontant } from "@/lib/format";
import {
  libelleEtape,
  statutDossier,
  type AnalyseLigne,
} from "@/lib/portefeuille-a-traiter";
import type { DossierAgregat } from "@/lib/types";

import { couleurMontant, LIEN_ACTION } from "./style";

export type LigneAnalysee = { dossier: DossierAgregat; analyse: AnalyseLigne };

type Props = {
  ligne: LigneAnalysee;
  selectionne: boolean;
  /** `null` : pas de sélection groupée (lecture seule, ou tags indisponibles). */
  coche: { cochee: boolean; onBasculer: (cochee: boolean) => void } | null;
  /** Clic sur la ligne : ouvre la fiche, ou la referme si elle est déjà ouverte. */
  onOuvrir: () => void;
  /** Lien d'action « Ouvrir la fiche » : ouvre toujours, ne referme jamais. */
  onAction: () => void;
};

/** Colonne de droite, la même dans les deux groupes : le montant reste ainsi
 * aligné d'une ligne à l'autre, du haut en bas de la liste. */
const COLONNE_DROITE = "w-36 shrink-0";

const BOUTON_LIGNE =
  "rounded-sm text-left outline-none focus-visible:shadow-focus-detache motion-reduce:transition-none";

/** Case de sélection groupée. Les lignes sont de vrais éléments interactifs :
 * un bouton pour ouvrir la fiche, la case et le lien d'action à côté (jamais
 * imbriqués : un lien dans un bouton n'est pas valide et se lit mal au
 * clavier). */
function Cocher({ nom, coche }: { nom: string; coche: NonNullable<Props["coche"]> }) {
  return (
    <input
      type="checkbox"
      className="mt-1.5 size-4 shrink-0 accent-primary"
      aria-label={`Cocher ${nom}`}
      checked={coche.cochee}
      onChange={(evenement) => coche.onBasculer(evenement.target.checked)}
    />
  );
}

function Montant({ centimes }: { centimes: number }) {
  return (
    <span
      className={`w-32 shrink-0 text-right text-[15px] leading-[1.4] font-medium tabular-nums ${couleurMontant(centimes)}`}
    >
      {formatMontant(centimes)}
    </span>
  );
}

/** `row-a-traiter` (DESIGN.md) : lavis, repère `signal` de 3 px à gauche, nom
 * en 16/600, la raison en une phrase, le montant, puis le lien d'action. */
export function LigneATraiter({ ligne, selectionne, coche, onOuvrir, onAction }: Props) {
  const { dossier, analyse } = ligne;
  const action = analyse.action;
  return (
    <li
      className={`flex items-start gap-3 border-b border-l-[3px] border-b-border border-l-signal px-5 py-4 transition-colors duration-100 hover:bg-surface-soft motion-reduce:transition-none ${
        selectionne ? "bg-surface-soft" : "bg-highlight-wash"
      }`}
    >
      {coche && <Cocher nom={dossier.nom} coche={coche} />}
      <button
        type="button"
        aria-current={selectionne ? "true" : undefined}
        className={`flex min-w-0 flex-1 items-start justify-between gap-6 ${BOUTON_LIGNE}`}
        onClick={onOuvrir}
      >
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className="truncate text-base leading-6 font-semibold text-ink">{dossier.nom}</span>
            <PastillesTags tags={dossier.tags ?? []} />
          </span>
          <span className="mt-1 block text-[13px] leading-[1.38] text-body">
            {analyse.raison}
            {analyse.autres > 0 && (
              <span className="text-muted">
                {" "}
                · {analyse.autres === 1 ? "1 autre point" : `${analyse.autres} autres points`}
              </span>
            )}
          </span>
        </span>
        <Montant centimes={dossier.resultat_cts} />
      </button>
      <span className={`${COLONNE_DROITE} pt-[3px] text-sm`}>
        {action?.type === "lien" && (
          <Link href={action.href} className={LIEN_ACTION} aria-label={`${action.libelle} : ${dossier.nom}`}>
            {action.libelle}
            <span aria-hidden> →</span>
          </Link>
        )}
        {action?.type === "ouvrir" && (
          <button
            type="button"
            className={LIEN_ACTION}
            aria-label={`${action.libelle} : ${dossier.nom}`}
            onClick={onAction}
          >
            {action.libelle}
            <span aria-hidden> →</span>
          </button>
        )}
      </span>
    </li>
  );
}

/** Dossier qui suit son cours : le nom et la forme en discret, l'étape en
 * texte (les frises vivent dans la fiche), le montant, le statut. */
export function LigneAutre({ ligne, selectionne, coche, onOuvrir }: Props) {
  // Pas de lien d'action sur ces lignes : `onAction` ne sert pas ici.
  const { dossier, analyse } = ligne;
  const ouvert = dossier.statut_invitation === "actif";
  const precedente = dossier.etape_precedente !== "Sans exercice";
  return (
    <li
      className={`flex items-start gap-3 border-b border-l-[3px] border-b-border border-l-transparent px-5 py-3 transition-colors duration-100 hover:bg-surface-soft motion-reduce:transition-none ${
        selectionne ? "bg-surface-soft" : "bg-canvas"
      } ${dossier.exclu_compteurs ? "opacity-60" : ""}`}
    >
      {coche && <Cocher nom={dossier.nom} coche={coche} />}
      <button
        type="button"
        aria-current={selectionne ? "true" : undefined}
        className={`flex min-w-0 flex-1 items-start justify-between gap-6 ${BOUTON_LIGNE}`}
        onClick={onOuvrir}
      >
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className="truncate text-base leading-6 font-medium text-ink">{dossier.nom}</span>
            <PastillesTags tags={dossier.tags ?? []} />
          </span>
          <span className="mt-0.5 block text-[13px] leading-[1.38] text-muted">
            {[dossier.forme_juridique, dossier.statut_invitation === "invité" ? libelleCompte("invité") : null]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </span>
        <span className="hidden w-44 shrink-0 md:block">
          <span className="block text-[13px] leading-[1.38] text-ink">
            <span className="text-muted">{dossier.annee_courante}</span>{" "}
            {libelleEtape(dossier.etape_courante, ouvert)}
          </span>
          {precedente && (
            <span className="mt-0.5 block text-xs leading-[1.33] text-muted">
              {dossier.annee_precedente} {libelleEtape(dossier.etape_precedente, ouvert)}
            </span>
          )}
        </span>
        <Montant centimes={dossier.resultat_cts} />
      </button>
      <span className={`${COLONNE_DROITE} pt-[3px]`}>
        <StatutDossier etat={statutDossier(dossier, analyse.aTraiter)} />
      </span>
    </li>
  );
}
