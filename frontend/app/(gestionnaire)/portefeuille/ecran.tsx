"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Aide, pourquoiEnvoi } from "@/components/Aide";
import { useCanauxEnvoi } from "@/lib/use-canaux-envoi";
import { IntegrationsDossier } from "@/components/IntegrationsDossier";
import { SuiviEnvois } from "@/components/SuiviEnvois";
import { SynthesePlateformes } from "@/components/SynthesePlateformes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  declencherRappel,
  ErreurAuthGestionnaire,
  lireConnexionsBancaires,
  lirePortefeuilleSession,
  listerDossiers,
  listerDossiersRetires,
  listerRegles,
  lireTags,
  restaurerDossier,
  retirerDossier,
  type RegleRappel,
} from "@/lib/auth-gestionnaire";
import {
  attendUnChoixDeCompte,
  bandeauComptesAChoisir,
  phraseComptesAChoisir,
} from "@/lib/comptes-a-choisir";
import { phraseAConfirmer } from "@/lib/configuration-dossier";
import { phraseTvaADeclarer } from "@/lib/tva";
import {
  libelleBanque,
  libelleCompte,
  libelleImposition,
  libelleRegimeTva,
  libelleTvaRecettes,
} from "@/lib/dossier-libelles";
import {
  ETAPES_FRISE,
  etapeBloquante,
  gardeEtape,
  rangEtape,
} from "@/lib/filtres-portefeuille";
import { formatDate, formatMontant } from "@/lib/format";
import { gardeTag, libelleTag, SANS_TAG, TOUS_LES_TAGS, totauxPortefeuille } from "@/lib/tags";
import type { DossierAgregat, ReglageTags } from "@/lib/types";
import { useDroitGestionnaire } from "@/lib/use-droit";
import { Squelette } from "@/components/Squelette";
import {
  BoutonSynchroniser,
  NouveauxChauffeurs,
  PhraseSynchronisation,
  useSynchronisationPortefeuille,
} from "@/components/SynchronisationPortefeuille";
import {
  PastillesTags,
  PoseEnLot,
  ReglageExclusions,
  TagsDuDossier,
} from "@/components/TagsEntreprises";

const COMPTES_A_CHOISIR = "a_choisir";
type FiltreCompte = "tous" | "sans_compte" | "invite" | "ouvert";
type FiltreResultat = "tous" | "negatif" | "positif";

const PAR_PAGE = 25;

export function EcranEntreprises() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const droit = useDroitGestionnaire();
  const canauxEnvoi = useCanauxEnvoi();
  const [dossiers, setDossiers] = useState<DossierAgregat[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const recherche = params.get("q") ?? "";
  const compte = lireCompte(params.get("compte"));
  const resultat = lireResultat(params.get("resultat"));
  const forme = params.get("forme") ?? "toutes";
  const tva = params.get("tva") ?? "toutes";
  const etape = params.get("etape") ?? "toutes";
  const banque = params.get("banque") === COMPTES_A_CHOISIR ? COMPTES_A_CHOISIR : "toutes";
  const tag = params.get("tag") ?? TOUS_LES_TAGS;
  const [reglageTags, setReglageTags] = useState<ReglageTags | null>(null);
  const [coches, setCoches] = useState<string[]>([]);
  const tri = lireTri(params.get("tri"));
  const page = Math.max(1, Number(params.get("page")) || 1);
  const selection = params.get("ouvert");
  const [regles, setRegles] = useState<RegleRappel[]>([]);
  const [infoRappel, setInfoRappel] = useState<string | null>(null);
  const [confirmerRetrait, setConfirmerRetrait] = useState(false);
  const [erreurRetrait, setErreurRetrait] = useState<string | null>(null);
  const [retires, setRetires] = useState<{ dossier_id: string; nom: string }[]>([]);

  const charger = useCallback(() => {
    listerDossiers()
      .then(setDossiers)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) {
          router.replace("/connexion");
        } else {
          setErreur("Impossible de charger les entreprises.");
        }
      });
  }, [router]);
  const synchro = useSynchronisationPortefeuille(charger);

  useEffect(() => {
    const memo = lirePortefeuilleSession();
    // Lecture de sessionStorage avant le rafraîchissement réseau.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (memo) setDossiers(memo);
    charger();
    listerRegles().then(setRegles).catch(() => setRegles([]));
    lireTags().then(setReglageTags).catch(() => setReglageTags(null));
    listerDossiersRetires().then(setRetires).catch(() => setRetires([]));
  }, [charger]);

  useEffect(() => {
    // Le message d'un rappel ne doit pas rester affiché sur l'entreprise suivante.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setInfoRappel(null);
    setErreurRetrait(null);
    setConfirmerRetrait(false);
  }, [selection]);

  const formes = useMemo(
    () => [...new Set((dossiers ?? []).map((dossier) => dossier.forme_juridique))].sort(),
    [dossiers],
  );
  const tvas = useMemo(
    () => [...new Set((dossiers ?? []).map((dossier) => dossier.tva_recettes_regime))].sort(),
    [dossiers],
  );
  function ecrire(maj: Record<string, string | null>, garderPage = false) {
    const suivant = new URLSearchParams(params.toString());
    for (const [cle, valeur] of Object.entries(maj)) {
      if (valeur === null || valeur === "" || valeur === "tous" || valeur === "toutes" || valeur === "nom") {
        suivant.delete(cle);
      } else {
        suivant.set(cle, valeur);
      }
    }
    if (!garderPage) suivant.delete("page");
    const requete = suivant.toString();
    router.replace(requete ? `${pathname}?${requete}` : pathname, { scroll: false });
  }

  const visibles = useMemo(() => {
    const aiguille = recherche.trim().toLowerCase();
    const filtres = (dossiers ?? []).filter((dossier) => {
      if (compte === "sans_compte" && dossier.statut_invitation !== null) return false;
      if (compte === "invite" && dossier.statut_invitation !== "invité") return false;
      if (compte === "ouvert" && dossier.statut_invitation !== "actif") return false;
      if (resultat === "negatif" && dossier.resultat_cts >= 0) return false;
      if (resultat === "positif" && dossier.resultat_cts < 0) return false;
      if (forme !== "toutes" && dossier.forme_juridique !== forme) return false;
      if (tva !== "toutes" && dossier.tva_recettes_regime !== tva) return false;
      if (etape !== "toutes" && !gardeEtape(dossier, etape)) return false;
      if (banque === COMPTES_A_CHOISIR && !attendUnChoixDeCompte(dossier)) return false;
      if (!gardeTag({ tags: dossier.tags ?? [] }, tag)) return false;
      if (!aiguille) return true;
      return `${dossier.nom} ${dossier.plateformes.join(" ")}`.toLowerCase().includes(aiguille);
    });
    return filtres.sort((a, b) => {
      if (tri === "resultat") return a.resultat_cts - b.resultat_cts;
      if (tri === "etape") {
        return (
          rangEtape(a.etape_courante, a.statut_invitation === "actif") -
          rangEtape(b.etape_courante, b.statut_invitation === "actif")
        );
      }
      return a.nom.localeCompare(b.nom, "fr");
    });
  }, [banque, compte, dossiers, etape, forme, recherche, resultat, tag, tri, tva]);

  const bandeau = useMemo(() => bandeauComptesAChoisir(dossiers ?? []), [dossiers]);
  const pages = Math.max(1, Math.ceil(visibles.length / PAR_PAGE));
  const pageCourante = Math.min(page, pages);
  const tranche = visibles.slice((pageCourante - 1) * PAR_PAGE, pageCourante * PAR_PAGE);
  const filtresActifs =
    recherche !== "" ||
    compte !== "tous" ||
    resultat !== "tous" ||
    forme !== "toutes" ||
    tva !== "toutes" ||
    etape !== "toutes" ||
    banque !== "toutes" ||
    tag !== TOUS_LES_TAGS ||
    tri !== "nom";

  // Les entreprises qu'un tag sort des compteurs restent listées, grisées.
  const totaux = useMemo(
    () => totauxPortefeuille(visibles.map((d) => ({ ...d, exclu_compteurs: d.exclu_compteurs ?? false }))),
    [visibles],
  );
  const comptees = useMemo(
    () => (dossiers ?? []).filter((dossier) => !dossier.exclu_compteurs).length,
    [dossiers],
  );

  const choisi = dossiers?.find((dossier) => dossier.dossier_id === selection) ?? null;

  return (
    <div className="flex items-start gap-6">
    <div className="min-w-0 flex-1">
      <div className="flex items-start justify-between gap-6">
        <h1 className="text-[22px] font-bold tracking-tight text-ink">Entreprises</h1>
        <Link href="/invitations" className="mt-2 text-sm font-medium text-signal hover:underline">
          Invitations
        </Link>
      </div>
      <AlerteConnexions />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {droit.ecriture && <BoutonSynchroniser etat={synchro} />}
        <PhraseSynchronisation etat={synchro} />
        {droit.admin && (
          <Link href="/import-dossiers" className="text-sm font-semibold text-signal underline decoration-2 underline-offset-[3px] hover:text-signal-deep">
            Importer des entreprises depuis un fichier
          </Link>
        )}
      </div>
      <NouveauxChauffeurs etat={synchro} ecriture={droit.ecriture} />
      {retires.length > 0 && (
        <section className="mt-6 rounded-md border border-border bg-canvas p-4">
          <h2 className="text-sm font-semibold text-ink">Retirées de la liste</h2>
          <p className="mt-1 text-sm text-subtle">Les écritures sont gardées.</p>
          <ul className="mt-3">
            {retires.map((dossier) => (
              <li
                key={dossier.dossier_id}
                className="flex items-center justify-between border-b border-hairline py-2"
              >
                <span className="text-sm text-ink">{dossier.nom}</span>
                {droit.admin && (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      void restaurerDossier(dossier.dossier_id).then(async () => {
                        setRetires(await listerDossiersRetires());
                        charger();
                      });
                    }}
                  >
                    Remettre
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {reglageTags && (
        <ReglageExclusions
          reglage={reglageTags}
          ecriture={droit.ecriture}
          onModifie={(reglage) => {
            setReglageTags(reglage);
            charger();
          }}
        />
      )}
      {dossiers ? (
        <dl className="mt-8 flex flex-wrap gap-x-12 gap-y-4">
          <Total
            libelle="Entreprises"
            valeur={totaux.nombre === comptees ? String(totaux.nombre) : `${totaux.nombre} sur ${comptees}`}
          />
          <Total libelle="Sans compte" valeur={String(totaux.sansCompte)} />
          <Total libelle="Résultat" valeur={formatMontant(totaux.resultat)} montant={totaux.resultat} />
        </dl>
      ) : (
        !erreur && (
          <div className="mt-8 flex gap-12" aria-hidden>
            <Squelette className="h-12 w-28" />
            <Squelette className="h-12 w-28" />
            <Squelette className="h-12 w-36" />
          </div>
        )
      )}

      {bandeau && banque !== COMPTES_A_CHOISIR && (
        <div
          role="status"
          className="mt-4 flex flex-wrap items-center gap-3 rounded-md border border-warning/40 bg-pending-subtle px-4 py-2.5"
        >
          <p className="flex-1 text-sm text-ink">{bandeau}</p>
          <Button type="button" variant="secondary" size="sm" onClick={() => ecrire({ banque: COMPTES_A_CHOISIR })}>
            Voir ces entreprises
          </Button>
        </div>
      )}

      <div className="mt-8 flex items-center gap-2">
        <Input
          value={recherche}
          onChange={(evenement) => ecrire({ q: evenement.target.value })}
          placeholder="Rechercher une entreprise"
          aria-label="Rechercher une entreprise"
        />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Filtre
          libelle="Compte"
          valeur={compte}
          options={ORDRE_COMPTE.map((id) => ({ id, libelle: LIBELLES_COMPTE[id] }))}
          onChoisir={(valeur) => ecrire({ compte: valeur })}
        />
        <Filtre
          libelle="Résultat"
          valeur={resultat}
          options={ORDRE_RESULTAT.map((id) => ({ id, libelle: LIBELLES_RESULTAT[id] }))}
          onChoisir={(valeur) => ecrire({ resultat: valeur })}
        />
        <Filtre
          libelle="Forme"
          valeur={forme}
          options={["toutes", ...formes].map((id) => ({ id, libelle: id === "toutes" ? "Toutes" : id }))}
          onChoisir={(valeur) => ecrire({ forme: valeur })}
        />
        <Filtre
          libelle="TVA"
          valeur={tva}
          options={["toutes", ...tvas].map((id) => ({
            id,
            libelle: id === "toutes" ? "Toutes" : libelleTvaRecettes(id),
          }))}
          onChoisir={(valeur) => ecrire({ tva: valeur })}
        />
        <Filtre
          libelle="Étape restante"
          valeur={etape}
          options={["toutes", ...ETAPES_FRISE].map((id) => ({
            id,
            libelle: id === "toutes" ? "Toutes" : id,
          }))}
          onChoisir={(valeur) => ecrire({ etape: valeur })}
        />
        <Filtre
          libelle="Comptes bancaires"
          valeur={banque}
          options={[
            { id: "toutes", libelle: "Tous" },
            { id: COMPTES_A_CHOISIR, libelle: "À choisir" },
          ]}
          onChoisir={(valeur) => ecrire({ banque: valeur })}
        />
        {reglageTags && (
          <Filtre
            libelle="Tag"
            valeur={tag}
            options={[
              { id: TOUS_LES_TAGS, libelle: "Tous" },
              { id: SANS_TAG, libelle: "Sans tag" },
              ...reglageTags.tags.map((option) => ({ id: option.nom, libelle: libelleTag(option.nom) })),
            ]}
            onChoisir={(valeur) => ecrire({ tag: valeur })}
          />
        )}
        <Filtre
          libelle="Tri"
          valeur={tri}
          options={[
            { id: "nom", libelle: "Nom" },
            { id: "etape", libelle: "Étape bloquante" },
            { id: "resultat", libelle: "Résultat" },
          ]}
          onChoisir={(valeur) => ecrire({ tri: valeur })}
        />
        {filtresActifs && (
          <Button type="button" variant="ghost" size="sm" onClick={() => ecrire({
            q: null, compte: null, resultat: null, forme: null, tva: null, etape: null, banque: null, tag: null,
            tri: null,
          })}>
            Réinitialiser
          </Button>
        )}
      </div>

      {erreur && (
        <div className="mt-6 flex items-center gap-3">
          <p className="text-sm text-danger">{erreur}</p>
          <Button type="button" variant="secondary" size="sm" onClick={charger}>
            Réessayer
          </Button>
        </div>
      )}
      {!dossiers && !erreur && (
        <div className="mt-8 space-y-3" aria-hidden>
          <Squelette className="h-16 w-full" />
          <Squelette className="h-16 w-full" />
          <Squelette className="h-16 w-full" />
        </div>
      )}

      {droit.ecriture && (
        <PoseEnLot
          coches={coches}
          reglage={reglageTags}
          onFait={() => {
            setCoches([]);
            charger();
          }}
        />
      )}
      <ul className="mt-4">
        {tranche.map((dossier) => {
          const bloque = etapeBloquante(dossier.etape_courante, dossier.statut_invitation === "actif");
          return (
          <li
            key={dossier.dossier_id}
            className={`flex items-start gap-2 border-b border-hairline ${dossier.exclu_compteurs ? "opacity-60" : ""}`}
          >
            {droit.ecriture && reglageTags && (
              <input
                type="checkbox"
                className="mt-4 ml-1"
                aria-label={`Cocher ${dossier.nom}`}
                checked={coches.includes(dossier.dossier_id)}
                onChange={(evenement) =>
                  setCoches((avant) =>
                    evenement.target.checked
                      ? [...avant, dossier.dossier_id]
                      : avant.filter((id) => id !== dossier.dossier_id),
                  )
                }
              />
            )}
            <button
              type="button"
              aria-current={selection === dossier.dossier_id ? "true" : undefined}
              className={`flex w-full items-start justify-between gap-6 rounded-md px-3 py-2 text-left hover:bg-surface-soft ${
                selection === dossier.dossier_id ? "bg-surface-soft" : ""
              }`}
              onClick={() => {
                setConfirmerRetrait(false);
                ecrire(
                  { ouvert: selection === dossier.dossier_id ? null : dossier.dossier_id },
                  true,
                );
              }}
            >
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span className="truncate text-sm font-semibold text-ink">{dossier.nom}</span>
                  <span className="shrink-0 text-sm text-subtle">{libelleCompte(dossier.statut_invitation)}</span>
                  <span className="shrink-0 text-sm font-medium text-ink">{bloque}</span>
                  <PastillesTags tags={dossier.tags ?? []} />
                </span>
                <span className="mt-2 block space-y-1">
                  <Frise
                    annee={dossier.annee_courante}
                    etape={dossier.etape_courante}
                    compteOuvert={dossier.statut_invitation === "actif"}
                  />
                  <Frise
                    annee={dossier.annee_precedente}
                    etape={dossier.etape_precedente}
                    compteOuvert={dossier.statut_invitation === "actif"}
                  />
                  {[
                    dossier.alerte_regime,
                    dossier.alerte_tva,
                    phraseAConfirmer(dossier.a_confirmer ?? []),
                    phraseComptesAChoisir(dossier),
                    phraseTvaADeclarer(dossier.tva_a_declarer, dossier.tva_echeance),
                  ]
                    .filter((alerte): alerte is string => alerte !== null)
                    .map((alerte) => (
                      <span key={alerte} className="block text-sm text-subtle">
                        {alerte}
                      </span>
                    ))}
                  {(dossier.ecarts_registre ?? []).map((ecart) => (
                    <span key={ecart} className="block text-sm text-warning">
                      {ecart}
                    </span>
                  ))}
                </span>
              </span>
              <span
                className={`shrink-0 text-base font-semibold tabular-nums ${
                  dossier.resultat_cts < 0 ? "text-amount-negative" : "text-amount-positive"
                }`}
              >
                {formatMontant(dossier.resultat_cts)}
              </span>
            </button>
          </li>
          );
        })}
      </ul>
      {dossiers && dossiers.length === 0 && (
        <p className="py-10 text-sm text-subtle">Aucune entreprise dans ce portefeuille.</p>
      )}
      {dossiers && dossiers.length > 0 && visibles.length === 0 && (
        <p className="py-10 text-sm text-subtle">Aucune entreprise pour ces filtres.</p>
      )}
      {pages > 1 && (
        <div className="mt-4 flex items-center gap-3 text-sm text-subtle">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={pageCourante <= 1}
            onClick={() => ecrire({ page: String(pageCourante - 1) }, true)}
          >
            Page précédente
          </Button>
          <span>
            Page {pageCourante} sur {pages}
          </span>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={pageCourante >= pages}
            onClick={() => ecrire({ page: String(pageCourante + 1) }, true)}
          >
            Page suivante
          </Button>
        </div>
      )}
      </div>
      {choisi ? (
        <aside className="sticky top-6 flex max-h-[calc(100vh-3rem)] w-96 shrink-0 flex-col overflow-hidden rounded-md border border-border bg-canvas">
          <div className="flex shrink-0 items-start justify-between gap-4 p-6 pb-4">
            <h2 className="min-w-0 truncate text-lg font-semibold text-ink">{choisi.nom}</h2>
            <span className="flex shrink-0 flex-nowrap gap-1">
              {droit.admin && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-danger"
                  onClick={() => setConfirmerRetrait(true)}
                >
                  Retirer
                </Button>
              )}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => ecrire({ ouvert: null }, true)}
              >
                Fermer
              </Button>
            </span>
          </div>
          <p className="mt-1 px-6 text-sm text-subtle">{libelleCompte(choisi.statut_invitation)}</p>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6">
          <Link
            href={`/anomalies/${choisi.dossier_id}`}
            className="mt-3 inline-block text-sm font-medium text-signal hover:underline"
          >
            Anomalies
          </Link>
          <TagsDuDossier
            dossierId={choisi.dossier_id}
            tags={choisi.tags ?? []}
            reglage={reglageTags}
            ecriture={droit.ecriture}
            onModifie={charger}
          />
          <dl className="mt-6 space-y-4 text-sm">
            <Ligne libelle="Résultat" valeur={formatMontant(choisi.resultat_cts)} />
            <Ligne libelle="CA HT" valeur={formatMontant(choisi.ca_ht_cts)} />
            <Ligne libelle="Charges" valeur={formatMontant(choisi.charges_cts)} />
            <Ligne libelle="Forme" valeur={choisi.forme_juridique} />
            <Ligne libelle="Imposition" valeur={libelleImposition(choisi.regime_imposition)} />
            <Ligne libelle="Régime de TVA" valeur={libelleRegimeTva(choisi.regime_tva)} />
            <Ligne libelle="TVA sur les recettes" valeur={libelleTvaRecettes(choisi.tva_recettes_regime)} />
            <Ligne libelle="Banque" valeur={libelleBanque(choisi.mode_acces_bancaire)} />
            {choisi.plateformes.length > 0 && (
              <Ligne libelle="Plateformes" valeur={choisi.plateformes.join(", ")} />
            )}
            {choisi.exercice_debut && (
              <Ligne
                libelle="Exercice"
                valeur={
                  choisi.exercice_fin
                    ? `${formatDate(choisi.exercice_debut)} au ${formatDate(choisi.exercice_fin)}`
                    : formatDate(choisi.exercice_debut)
                }
              />
            )}
          </dl>
          <SynthesePlateformes dossierId={choisi.dossier_id} />
          <IntegrationsDossier dossierId={choisi.dossier_id} admin={droit.admin} />
          <div className="mt-8">
            <p className="text-sm font-medium text-ink">
              Rappels
              <Aide texte={pourquoiEnvoi(canauxEnvoi)} />
            </p>
            {regles.length === 0 && (
              <p className="mt-2 text-sm text-subtle">
                Aucune règle. Elles se préparent dans Rappels.
              </p>
            )}
            <div className="mt-2 flex flex-col gap-2">
              {regles
                .filter((regle) => regle.declencheur === "manuel")
                .filter(
                  (regle) =>
                    regle.portee !== "selection" || regle.dossier_ids.includes(choisi.dossier_id),
                )
                .map((regle) => (
                <div key={regle.id}>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={!droit.ecriture}
                    onClick={async () => {
                      setInfoRappel(null);
                      try {
                        await declencherRappel(regle.id, choisi.dossier_id);
                        setInfoRappel(
                          `${regle.libelle} enregistré. Envoi prévu quand le canal sera branché.`,
                        );
                      } catch (exception) {
                        setInfoRappel(
                          exception instanceof Error ? exception.message : "Échec du rappel.",
                        );
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
            <SuiviEnvois dossierId={choisi.dossier_id} />
          </div>
          {confirmerRetrait && (
            <div className="mt-6 rounded-md border border-border bg-canvas-app p-4">
              <p className="text-sm text-ink">
                Retirer {choisi.nom} de la liste ? Les écritures restent. Vous pourrez remettre
                l&apos;entreprise dans la liste.
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
                      await retirerDossier(choisi.dossier_id);
                      setConfirmerRetrait(false);
                      ecrire({ ouvert: null }, true);
                      charger();
                      setRetires(await listerDossiersRetires());
                    } catch (exception) {
                      setErreurRetrait(
                        exception instanceof Error ? exception.message : "Échec du retrait.",
                      );
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
      ) : null}
    </div>
  );
}

function Total({ libelle, valeur, montant }: { libelle: string; valeur: string; montant?: number }) {
  const couleur =
    montant === undefined ? "text-ink" : montant < 0 ? "text-amount-negative" : "text-amount-positive";
  return (
    <div>
      <dt className="text-sm text-subtle">{libelle}</dt>
      <dd className={`mt-0.5 text-xl font-bold tabular-nums tracking-tight ${couleur}`}>{valeur}</dd>
    </div>
  );
}

const ORDRE_COMPTE: FiltreCompte[] = ["tous", "sans_compte", "invite", "ouvert"];
const ORDRE_RESULTAT: FiltreResultat[] = ["tous", "positif", "negatif"];
const LIBELLES_COMPTE: Record<FiltreCompte, string> = {
  tous: "Tous",
  sans_compte: "Sans compte",
  invite: "Invitation envoyée",
  ouvert: "Compte ouvert",
};
const LIBELLES_RESULTAT: Record<FiltreResultat, string> = {
  tous: "Tous",
  positif: "Positif",
  negatif: "Négatif",
};

function Filtre<T extends string>({
  libelle,
  valeur,
  options,
  onChoisir,
}: {
  libelle: string;
  valeur: T;
  options: { id: T; libelle: string }[];
  onChoisir: (id: T) => void;
}) {
  return (
    <div className="flex items-center gap-2 text-sm whitespace-nowrap text-subtle">
      {libelle}
      <Select
        aria-label={libelle}
        value={valeur}
        onValueChange={(id) => onChoisir(id as T)}
        options={options.map((option) => ({ value: option.id, label: option.libelle }))}
        className="min-w-28"
      />
    </div>
  );
}

function lireCompte(valeur: string | null): FiltreCompte {
  if (valeur === "sans_compte" || valeur === "invite" || valeur === "ouvert") return valeur;
  return "tous";
}

function lireResultat(valeur: string | null): FiltreResultat {
  if (valeur === "positif" || valeur === "negatif") return valeur;
  return "tous";
}

function lireTri(valeur: string | null): "nom" | "etape" | "resultat" {
  if (valeur === "etape" || valeur === "resultat") return valeur;
  return "nom";
}

const CANAL: Record<string, string> = { mail: "E-mail", sms: "SMS", appel: "Appel" };

function libelleCanaux(canaux: string[]): string {
  return canaux.map((canal) => CANAL[canal] ?? canal).join(", ");
}

/** Le compte se prépare une fois. Ensuite, par exercice : clôture, signature
 * de validation, dépôt au greffe, dépôt aux impôts, signature légale
 * (doc 02 §4 et §6, doc 19 §5.3, doc 20 §4bis). */
function Frise({
  annee,
  etape,
  compteOuvert,
}: {
  annee: number;
  etape: string;
  compteOuvert: boolean;
}) {
  const index = rangEtape(etape, compteOuvert);
  const lecture = ETAPES_FRISE.map((nom, rang) => `${nom} ${rang <= index ? "faite" : "à faire"}`).join(", ");
  return (
    <span role="img" className="flex items-start gap-3" aria-label={`${annee} : ${lecture}`}>
      <span className="w-8 shrink-0 pt-px text-xs leading-none text-subtle">{annee}</span>
      <span className="grid min-w-0 flex-1 grid-cols-6">
        {ETAPES_FRISE.map((nom, rang) => {
          const fait = rang <= index;
          const traitFait = rang < index;
          return (
            <span key={nom} className="relative flex flex-col items-center">
              {rang > 0 && (
                <span
                  className={`absolute right-1/2 top-[3px] left-0 h-px ${traitFait || fait ? "bg-primary" : "bg-border"}`}
                />
              )}
              {rang < ETAPES_FRISE.length - 1 && (
                <span
                  className={`absolute top-[3px] right-0 left-1/2 h-px ${traitFait ? "bg-primary" : "bg-border"}`}
                />
              )}
              <span className={`relative z-10 h-2 w-2 rounded-full ${fait ? "bg-primary" : "bg-border"}`} />
              <span className={`mt-1 text-center text-[10px] leading-tight ${fait ? "text-ink" : "text-subtle"}`}>
                {nom}
              </span>
            </span>
          );
        })}
      </span>
    </span>
  );
}

function Ligne({ libelle, valeur }: { libelle: string; valeur: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-subtle">{libelle}</dt>
      <dd className="text-right text-ink">{valeur}</dd>
    </div>
  );
}

/** doc 14 §2.2 : les connexions qui demandent une action se voient dès
 * l'arrivée, sans aller les chercher. */
function AlerteConnexions() {
  const [nombre, setNombre] = useState(0);
  useEffect(() => {
    lireConnexionsBancaires()
      .then((donnees) =>
        setNombre(
          donnees.dossiers.filter(
            (dossier) =>
              dossier.statut === "expire" ||
              dossier.statut === "a_renouveler" ||
              dossier.sante === "auth_requise",
          ).length,
        ),
      )
      .catch(() => undefined);
  }, []);
  if (nombre === 0) return null;
  return (
    <Link
      href="/connexions-bancaires"
      className="mt-4 block rounded-md border border-warning/40 bg-pending-subtle px-4 py-2.5 text-sm text-ink hover:border-warning"
    >
      {nombre === 1
        ? "Une connexion bancaire expire ou doit être confirmée."
        : `${nombre} connexions bancaires expirent ou doivent être confirmées.`}{" "}
      <span className="font-medium text-signal">Voir</span>
    </Link>
  );
}
