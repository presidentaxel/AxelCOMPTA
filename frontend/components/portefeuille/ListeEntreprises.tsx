"use client";

import Link from "next/link";
import { useId } from "react";

import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";

import { LigneATraiter, LigneAutre, type LigneAnalysee } from "./LigneEntreprise";

type Props = {
  charge: boolean;
  erreur: string | null;
  onReessayer: () => void;
  /** Lignes de la page courante, « à traiter » en tête. */
  tranche: LigneAnalysee[];
  /** Totaux de tous les dossiers visibles, pas seulement de la page : l'en-tête
   * d'un groupe annonce le groupe entier, la pagination le découpe ensuite. */
  totalATraiter: number;
  totalAutres: number;
  portefeuilleVide: boolean;
  aucunResultat: boolean;
  selection: string | null;
  cochees: string[];
  /** `false` : pas de sélection groupée (lecture seule, ou tags indisponibles). */
  peutCocher: boolean;
  onBasculerCoche: (dossierId: string, cochee: boolean) => void;
  onOuvrir: (dossierId: string) => void;
  page: number;
  pages: number;
  onPage: (page: number) => void;
  admin: boolean;
  onReinitialiser: () => void;
};

/** La liste en deux groupes : « À traiter » (lignes lavées, repère signal),
 * puis « Autres ». Tous les états y sont : chargement, erreur, portefeuille
 * vide, aucun résultat — chacun avec une action, jamais une page blanche. */
export function ListeEntreprises({
  charge,
  erreur,
  onReessayer,
  tranche,
  totalATraiter,
  totalAutres,
  portefeuilleVide,
  aucunResultat,
  selection,
  cochees,
  peutCocher,
  onBasculerCoche,
  onOuvrir,
  page,
  pages,
  onPage,
  admin,
  onReinitialiser,
}: Props) {
  const idATraiter = useId();
  const idAutres = useId();
  const aTraiter = tranche.filter((ligne) => ligne.analyse.aTraiter);
  const autres = tranche.filter((ligne) => !ligne.analyse.aTraiter);

  function rendre(ligne: LigneAnalysee, Composant: typeof LigneATraiter) {
    const id = ligne.dossier.dossier_id;
    return (
      <Composant
        key={id}
        ligne={ligne}
        selectionne={selection === id}
        coche={
          peutCocher
            ? { cochee: cochees.includes(id), onBasculer: (cochee) => onBasculerCoche(id, cochee) }
            : null
        }
        onOuvrir={() => onOuvrir(id)}
      />
    );
  }

  return (
    <div className="mt-6">
      {erreur && (
        <div role="alert" className="flex flex-wrap items-center gap-3 py-4">
          <p className="text-sm text-danger">
            {erreur} Vérifiez votre connexion, puis réessayez.
          </p>
          <Button type="button" variant="secondary" size="sm" onClick={onReessayer}>
            Réessayer
          </Button>
        </div>
      )}
      {!charge && !erreur && (
        <div aria-hidden>
          <Squelette className="h-9 w-full" />
          {Array.from({ length: 6 }, (_, index) => (
            <Squelette key={index} className="mt-px h-[76px] w-full rounded-none" />
          ))}
        </div>
      )}

      {aTraiter.length > 0 && (
        <section aria-labelledby={idATraiter}>
          <h2 id={idATraiter} className={ENTETE_GROUPE}>
            À traiter · <span className="tabular-nums">{totalATraiter}</span>
          </h2>
          <ul>{aTraiter.map((ligne) => rendre(ligne, LigneATraiter))}</ul>
        </section>
      )}
      {autres.length > 0 && (
        <section aria-labelledby={idAutres} className={aTraiter.length > 0 ? "mt-8" : undefined}>
          <h2 id={idAutres} className={ENTETE_GROUPE}>
            Autres · <span className="tabular-nums">{totalAutres}</span>
          </h2>
          <ul>{autres.map((ligne) => rendre(ligne, LigneAutre))}</ul>
        </section>
      )}

      {charge && portefeuilleVide && (
        <div className="py-12 text-center">
          <p className="text-sm text-muted">Aucune entreprise dans ce portefeuille.</p>
          {admin ? (
            <Button asChild variant="secondary" className="mt-4">
              <Link href="/import-dossiers">Importer des entreprises</Link>
            </Button>
          ) : (
            <p className="mt-2 text-sm text-muted">
              Un administrateur peut les importer, ou lancer une synchronisation.
            </p>
          )}
        </div>
      )}
      {charge && aucunResultat && (
        <div className="py-12 text-center">
          <p className="text-sm text-muted">Aucune entreprise pour ces filtres.</p>
          <Button type="button" variant="secondary" className="mt-4" onClick={onReinitialiser}>
            Réinitialiser les filtres
          </Button>
        </div>
      )}

      {pages > 1 && (
        <nav aria-label="Pagination" className="mt-4 flex items-center gap-3 text-sm text-subtle">
          {/* Un bouton qui ne mène nulle part n'est pas montré, plutôt que grisé. */}
          {page > 1 && (
            <Button type="button" variant="secondary" size="sm" onClick={() => onPage(page - 1)}>
              Page précédente
            </Button>
          )}
          <span className="tabular-nums">
            Page {page} sur {pages}
          </span>
          {page < pages && (
            <Button type="button" variant="secondary" size="sm" onClick={() => onPage(page + 1)}>
              Page suivante
            </Button>
          )}
        </nav>
      )}
    </div>
  );
}

/** `overline` (DESIGN.md) : 12px, 600, +0.06em, majuscules ; filet d'encre
 * dessous comme l'en-tête des tableaux. */
const ENTETE_GROUPE =
  "flex h-9 items-center border-b border-ink px-5 text-xs leading-[1.33] font-semibold tracking-[0.06em] text-subtle uppercase";
