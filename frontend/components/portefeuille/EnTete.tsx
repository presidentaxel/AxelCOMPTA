"use client";

import Link from "next/link";
import { useState } from "react";

import { Squelette } from "@/components/Squelette";
import {
  BoutonSynchroniser,
  PhraseSynchronisation,
  type SynchronisationEtat,
} from "@/components/SynchronisationPortefeuille";
import { Button } from "@/components/ui/button";
import { formatMontant } from "@/lib/format";
import { dateDuJour, sousTitreAccueil, titreAccueil } from "@/lib/portefeuille-a-traiter";
import type { TotauxPortefeuille } from "@/lib/tags";

import { Surligneur } from "./Surligneur";
import { couleurMontant, LIEN_ACTION } from "./style";

type Props = {
  /** `false` tant que la liste n'est pas arrivée : squelettes de même emprise. */
  charge: boolean;
  erreur: boolean;
  /** Dossiers à traiter et autres, hors dossiers exclus des compteurs. */
  aTraiter: number;
  autres: number;
  totaux: TotauxPortefeuille;
  /** Entreprises comptées avant filtres, pour « N sur M ». */
  comptees: number;
  connexionsARenouveler: number;
  admin: boolean;
  ecriture: boolean;
  synchro: SynchronisationEtat;
};

/** Tête de l'écran Entreprises (direction C2) : la date, le titre d'accueil
 * avec son unique surlignage, les deux boutons, la bande de chiffres.
 *
 * Le heading « Entreprises » reste un vrai `<h1>`, discret : c'est lui que
 * les lecteurs d'écran et les tests e2e cherchent. Le titre de 56 px est un
 * paragraphe, sinon la page aurait deux titres de premier niveau. */
export function EnTete({
  charge,
  erreur,
  aTraiter,
  autres,
  totaux,
  comptees,
  connexionsARenouveler,
  admin,
  ecriture,
  synchro,
}: Props) {
  // Lu une fois au montage : `new Date()` pendant le rendu rendrait le composant
  // impur. Le texte peut différer entre serveur et navigateur autour de minuit.
  const [aujourdhui] = useState(() => dateDuJour(new Date()));
  const titre = titreAccueil(aTraiter);
  const sousTitre = sousTitreAccueil(aTraiter, autres);

  return (
    <header>
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="text-[13px] leading-[1.38]">
            <h1 className="inline font-semibold text-ink">Entreprises</h1>
            <span className="text-muted" suppressHydrationWarning>
              {" "}
              · {aujourdhui}
            </span>
          </div>
          {charge ? (
            <>
              <p className="mt-3 text-[56px] leading-[1.05] font-semibold tracking-[-0.04em] text-ink">
                {titre.surligne && <Surligneur>{titre.surligne}</Surligneur>}
                {titre.suite}
              </p>
              {sousTitre && <p className="mt-3 text-lg text-body">{sousTitre}</p>}
            </>
          ) : (
            !erreur && (
              <div className="mt-3" aria-hidden>
                <Squelette className="h-[59px] w-[min(28rem,100%)]" />
                <Squelette className="mt-3 h-7 w-64" />
              </div>
            )
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2 pt-1">
          {admin && (
            <Button asChild variant="secondary">
              <Link href="/import-dossiers">Importer</Link>
            </Button>
          )}
          {ecriture && <BoutonSynchroniser etat={synchro} />}
        </div>
      </div>
      {/* Hauteur réservée : la phrase arrive après la relecture de la synchro. */}
      <div className="mt-2 flex min-h-[18px] items-center justify-end gap-4">
        <Link href="/invitations" className="rounded-sm text-[13px] font-semibold text-ink underline underline-offset-[3px] outline-none focus-visible:shadow-focus-detache">
          Invitations
        </Link>
        <PhraseSynchronisation etat={synchro} />
      </div>

      <div className="mt-6 border-t border-ink pt-4">
        {charge ? (
          <dl className="grid grid-cols-2 gap-x-10 gap-y-4 sm:grid-cols-4">
            <Chiffre
              libelle="Entreprises"
              valeur={totaux.nombre === comptees ? String(totaux.nombre) : `${totaux.nombre} sur ${comptees}`}
            />
            <Chiffre libelle="Sans compte" valeur={String(totaux.sansCompte)} />
            <Chiffre
              libelle="Résultat cumulé"
              valeur={formatMontant(totaux.resultat)}
              couleur={couleurMontant(totaux.resultat)}
            />
            {connexionsARenouveler > 0 && (
              <div>
                <dt className="text-[13px] leading-[1.38] text-muted">À savoir</dt>
                <dd className="mt-1 text-sm text-ink">
                  {connexionsARenouveler === 1
                    ? "Une connexion bancaire est à renouveler."
                    : `${connexionsARenouveler} connexions bancaires sont à renouveler.`}{" "}
                  <Link href="/connexions-bancaires" className={LIEN_ACTION}>
                    Renouveler
                    <span aria-hidden> →</span>
                  </Link>
                </dd>
              </div>
            )}
          </dl>
        ) : (
          <div className="grid grid-cols-2 gap-x-10 gap-y-4 sm:grid-cols-4" aria-hidden>
            <Squelette className="h-[58px]" />
            <Squelette className="h-[58px]" />
            <Squelette className="h-[58px]" />
          </div>
        )}
      </div>
    </header>
  );
}

function Chiffre({ libelle, valeur, couleur = "text-ink" }: { libelle: string; valeur: string; couleur?: string }) {
  return (
    <div>
      <dt className="text-[13px] leading-[1.38] text-muted">{libelle}</dt>
      <dd className={`mt-1 text-[28px] leading-[1.25] font-semibold tabular-nums ${couleur}`}>{valeur}</dd>
    </div>
  );
}
