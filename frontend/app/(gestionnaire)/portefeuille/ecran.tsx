"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { pourquoiEnvoi } from "@/components/Aide";
import { BarreOutils } from "@/components/portefeuille/BarreOutils";
import { EnTete } from "@/components/portefeuille/EnTete";
import { FicheEntreprise } from "@/components/portefeuille/FicheEntreprise";
import { ListeEntreprises } from "@/components/portefeuille/ListeEntreprises";
import { RetireesDeLaListe } from "@/components/portefeuille/RetireesDeLaListe";
import {
  COMPTES_A_CHOISIR,
  lireCompte,
  lireResultat,
  lireTri,
  nombreDeFiltres,
  type EtatFiltres,
} from "@/components/portefeuille/filtres";
import type { LigneAnalysee } from "@/components/portefeuille/LigneEntreprise";
import { NouveauxChauffeurs, useSynchronisationPortefeuille } from "@/components/SynchronisationPortefeuille";
import { PoseEnLot, ReglageExclusions } from "@/components/TagsEntreprises";
import { Button } from "@/components/ui/button";
import {
  ErreurAuthGestionnaire,
  lireConnexionsBancaires,
  lirePortefeuilleSession,
  listerDossiers,
  listerDossiersRetires,
  listerRegles,
  lireTags,
  restaurerDossier,
  type ConnexionDossier,
  type RegleRappel,
} from "@/lib/auth-gestionnaire";
import { attendUnChoixDeCompte, bandeauComptesAChoisir } from "@/lib/comptes-a-choisir";
import { gardeEtape, rangEtape } from "@/lib/filtres-portefeuille";
import {
  aTraiterEnPremier,
  analyserLigne,
  connexionARenouveler,
  toutesLesRaisons,
} from "@/lib/portefeuille-a-traiter";
import { gardeTag, TOUS_LES_TAGS, totauxPortefeuille } from "@/lib/tags";
import type { DossierAgregat, ReglageTags } from "@/lib/types";
import { useCanauxEnvoi } from "@/lib/use-canaux-envoi";
import { useDroitGestionnaire } from "@/lib/use-droit";

const PAR_PAGE = 25;

/** Écran Entreprises. Il charge, lit l'URL et assemble ; ce qui s'affiche vit
 * dans `components/portefeuille/` et la règle « à traiter » dans
 * `lib/portefeuille-a-traiter.ts`.
 *
 * La liste complète arrive d'un coup et la pagination est faite ici : on peut
 * donc mettre les dossiers « à traiter » en tête de TOUTES les pages, avant de
 * découper. */
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
  const tri = lireTri(params.get("tri"));
  const page = Math.max(1, Number(params.get("page")) || 1);
  const selection = params.get("ouvert");
  const [reglageTags, setReglageTags] = useState<ReglageTags | null>(null);
  const [coches, setCoches] = useState<string[]>([]);
  const [regles, setRegles] = useState<RegleRappel[]>([]);
  const [retires, setRetires] = useState<{ dossier_id: string; nom: string }[]>([]);
  const [connexions, setConnexions] = useState<ConnexionDossier[]>([]);

  const charger = useCallback(() => {
    listerDossiers()
      .then((liste) => {
        // Un « Réessayer » réussi efface le message d'erreur.
        setErreur(null);
        setDossiers(liste);
      })
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
    // Une seule lecture des connexions : elle sert l'avis « À savoir » et la
    // raison « à traiter » de chaque ligne. Sans réponse, rien n'est signalé.
    lireConnexionsBancaires()
      .then((donnees) => setConnexions(donnees.dossiers))
      .catch(() => setConnexions([]));
  }, [charger]);

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

  // Chaque dossier avec ce que la règle en dit. Calculé sur tout le portefeuille :
  // le titre d'accueil compte « à traiter » avant les filtres.
  const analyses = useMemo(() => {
    const parDossier = new Map(connexions.map((connexion) => [connexion.dossier_id, connexion]));
    return (dossiers ?? []).map<LigneAnalysee>((dossier) => ({
      dossier,
      analyse: analyserLigne(dossier, parDossier.get(dossier.dossier_id)),
    }));
  }, [dossiers, connexions]);

  const visibles = useMemo(() => {
    const aiguille = recherche.trim().toLowerCase();
    const filtres = analyses.filter(({ dossier }) => {
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
    const triees = [...filtres].sort((a, b) => {
      if (tri === "resultat") return a.dossier.resultat_cts - b.dossier.resultat_cts;
      if (tri === "etape") {
        return (
          rangEtape(a.dossier.etape_courante, a.dossier.statut_invitation === "actif") -
          rangEtape(b.dossier.etape_courante, b.dossier.statut_invitation === "actif")
        );
      }
      return a.dossier.nom.localeCompare(b.dossier.nom, "fr");
    });
    // « À traiter » d'abord, le tri choisi s'applique dans chaque groupe.
    return aTraiterEnPremier(triees, (ligne) => ligne.analyse.aTraiter);
  }, [analyses, banque, compte, etape, forme, recherche, resultat, tag, tri, tva]);

  const etatFiltres: EtatFiltres = { recherche, compte, resultat, forme, tva, etape, banque, tag, tri };
  const bandeau = useMemo(() => bandeauComptesAChoisir(dossiers ?? []), [dossiers]);
  const pages = Math.max(1, Math.ceil(visibles.length / PAR_PAGE));
  const pageCourante = Math.min(page, pages);
  const tranche = visibles.slice((pageCourante - 1) * PAR_PAGE, pageCourante * PAR_PAGE);
  const totalATraiter = visibles.filter((ligne) => ligne.analyse.aTraiter).length;
  const filtresActifs = recherche !== "" || nombreDeFiltres(etatFiltres) > 0;

  // Les entreprises qu'un tag sort des compteurs restent listées, grisées.
  const totaux = useMemo(
    () =>
      totauxPortefeuille(
        visibles.map(({ dossier }) => ({ ...dossier, exclu_compteurs: dossier.exclu_compteurs ?? false })),
      ),
    [visibles],
  );
  const comptees = analyses.filter(({ dossier }) => !dossier.exclu_compteurs).length;
  const aTraiterEnTout = analyses.filter(({ analyse }) => analyse.aTraiter).length;
  const connexionsARenouveler = connexions.filter(connexionARenouveler).length;

  const choisi = analyses.find(({ dossier }) => dossier.dossier_id === selection) ?? null;

  function reinitialiser() {
    ecrire({
      q: null, compte: null, resultat: null, forme: null, tva: null, etape: null, banque: null, tag: null,
      tri: null,
    });
  }

  return (
    <div>
      <EnTete
        charge={dossiers !== null}
        erreur={erreur !== null}
        aTraiter={aTraiterEnTout}
        autres={comptees - aTraiterEnTout}
        totaux={totaux}
        comptees={comptees}
        connexionsARenouveler={connexionsARenouveler}
        admin={droit.admin}
        ecriture={droit.ecriture}
        synchro={synchro}
      />
      <NouveauxChauffeurs etat={synchro} ecriture={droit.ecriture} />
      <RetireesDeLaListe
        retires={retires}
        admin={droit.admin}
        onRemettre={async (dossierId) => {
          await restaurerDossier(dossierId);
          setRetires(await listerDossiersRetires());
          charger();
        }}
      />
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

      {bandeau && banque !== COMPTES_A_CHOISIR && (
        <div
          role="status"
          className="mt-6 flex flex-wrap items-center gap-3 rounded-md border border-warning/40 bg-pending-subtle px-4 py-3"
        >
          <p className="flex-1 text-sm text-ink">{bandeau}</p>
          <Button type="button" variant="secondary" size="sm" onClick={() => ecrire({ banque: COMPTES_A_CHOISIR })}>
            Voir ces entreprises
          </Button>
        </div>
      )}

      <div className="mt-8">
        <BarreOutils
          charge={dossiers !== null}
          visibles={visibles.length}
          etat={etatFiltres}
          formes={formes}
          tvas={tvas}
          reglageTags={reglageTags}
          filtresActifs={filtresActifs}
          onChanger={(maj) => ecrire(maj)}
          onReinitialiser={reinitialiser}
        />
      </div>

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
      <ListeEntreprises
        charge={dossiers !== null}
        erreur={erreur}
        onReessayer={charger}
        tranche={tranche}
        totalATraiter={totalATraiter}
        totalAutres={visibles.length - totalATraiter}
        portefeuilleVide={dossiers !== null && dossiers.length === 0}
        aucunResultat={dossiers !== null && dossiers.length > 0 && visibles.length === 0}
        selection={selection}
        cochees={coches}
        peutCocher={droit.ecriture && reglageTags !== null}
        onBasculerCoche={(dossierId, cochee) =>
          setCoches((avant) =>
            cochee ? [...avant, dossierId] : avant.filter((id) => id !== dossierId),
          )
        }
        onOuvrir={(dossierId) => ecrire({ ouvert: selection === dossierId ? null : dossierId }, true)}
        page={pageCourante}
        pages={pages}
        onPage={(suivante) => ecrire({ page: String(suivante) }, true)}
        admin={droit.admin}
        onReinitialiser={reinitialiser}
      />

      {choisi && (
        <FicheEntreprise
          key={choisi.dossier.dossier_id}
          dossier={choisi.dossier}
          raisons={toutesLesRaisons(
            choisi.dossier,
            connexions.find((connexion) => connexion.dossier_id === choisi.dossier.dossier_id),
          )}
          regles={regles}
          aideRappels={pourquoiEnvoi(canauxEnvoi)}
          reglageTags={reglageTags}
          admin={droit.admin}
          ecriture={droit.ecriture}
          onFermer={() => ecrire({ ouvert: null }, true)}
          onModifie={charger}
          onRetire={() => {
            ecrire({ ouvert: null }, true);
            charger();
            void listerDossiersRetires().then(setRetires).catch(() => undefined);
          }}
        />
      )}
    </div>
  );
}
