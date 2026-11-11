// AXE-878 : ce que la liste des entreprises dit d'un dossier « à traiter ».
//
// Règle d'or (doc 08) : le frontend ne porte aucune logique comptable. Rien
// n'est donc calculé ici à partir d'écritures, de montants ou de dates : un
// dossier est « à traiter » parce que l'API lui attache déjà une alerte
// (régime, TVA, configuration à confirmer, comptes bancaires à choisir, TVA à
// déclarer) ou parce que sa connexion bancaire est à renouveler. Ce module ne
// fait que choisir laquelle dire en premier, et quoi proposer d'en faire.
//
// Pur et testé : aucun accès réseau, aucune horloge (la date est passée).

import { phraseAConfirmer } from "./configuration-dossier";
import { phraseComptesAChoisir } from "./comptes-a-choisir";
import { etapeBloquante, ETAPES_FRISE, rangEtape } from "./filtres-portefeuille";
import { phraseTvaADeclarer } from "./tva";
import type { DossierAgregat } from "./types";

/** Les champs de l'agrégat dont la règle a besoin. Les champs apparus après
 * coup sont optionnels : un portefeuille mémorisé en session peut ne pas les
 * porter. */
export type LignePortefeuille = Pick<
  DossierAgregat,
  | "dossier_id"
  | "alerte_regime"
  | "alerte_tva"
  | "statut_invitation"
  | "etape_courante"
> &
  Partial<
    Pick<
      DossierAgregat,
      | "a_confirmer"
      | "tva_a_declarer"
      | "tva_echeance"
      | "comptes_a_choisir"
      | "comptes_a_choisir_depuis"
      | "operations_en_attente_de_choix"
      | "exclu_compteurs"
    >
  >;

/** Ce que `lireConnexionsBancaires` dit d'un dossier (sous-ensemble). */
export type ConnexionLigne = {
  statut: string;
  sante: string;
  jours_restants: number | null;
};

/** Ce que le lien d'action de la ligne fait : ouvrir la fiche de
 * l'entreprise, ou aller à l'écran qui règle la raison. Le libellé ne porte
 * pas la flèche : c'est l'affichage qui l'ajoute (elle est décorative). */
export type ActionLigne =
  | { type: "ouvrir"; libelle: string }
  | { type: "lien"; libelle: string; href: string };

export type AnalyseLigne = {
  aTraiter: boolean;
  /** Une phrase, la raison la plus pressante. Vide quand rien n'est à traiter. */
  raison: string;
  /** Nombre de raisons de plus que celle affichée. */
  autres: number;
  action: ActionLigne | null;
};

type Raison = { texte: string; action: ActionLigne };

const OUVRIR_LA_FICHE: ActionLigne = { type: "ouvrir", libelle: "Ouvrir la fiche" };

/** La connexion bancaire demande une action du gestionnaire : expirée, à
 * renouveler, ou la banque réclame une nouvelle confirmation. C'est la même
 * condition que l'avis « À savoir » de l'écran. */
export function connexionARenouveler(connexion: ConnexionLigne | null | undefined): boolean {
  if (!connexion) return false;
  return (
    connexion.statut === "expire" ||
    connexion.statut === "a_renouveler" ||
    connexion.sante === "auth_requise"
  );
}

function phraseConnexion(connexion: ConnexionLigne): string {
  if (connexion.statut === "expire") return "La connexion bancaire a expiré.";
  if (connexion.statut === "a_renouveler") {
    const jours = connexion.jours_restants;
    if (jours === null || jours < 0) return "La connexion bancaire est à renouveler.";
    if (jours === 0) return "La connexion bancaire est à renouveler aujourd'hui.";
    return jours === 1
      ? "La connexion bancaire est à renouveler sous 1 jour."
      : `La connexion bancaire est à renouveler sous ${jours} jours.`;
  }
  return "La banque demande une nouvelle confirmation de la connexion.";
}

/** Les raisons, de la plus pressante à la moins pressante : ce qui bloque la
 * collecte des opérations (connexion, comptes à choisir) d'abord, puis la TVA,
 * puis les alertes de configuration. Un dossier exclu des compteurs par un tag
 * (société du gestionnaire, hors périmètre, test) n'en a aucune : on ne lui
 * demande rien, il reste listé, grisé. */
function raisons(ligne: LignePortefeuille, connexion?: ConnexionLigne | null): Raison[] {
  if (ligne.exclu_compteurs) return [];
  const liste: Raison[] = [];
  if (connexion && connexionARenouveler(connexion)) {
    liste.push({
      texte: phraseConnexion(connexion),
      action: { type: "lien", libelle: "Renouveler", href: "/connexions-bancaires" },
    });
  }
  const comptes = phraseComptesAChoisir(ligne);
  if (comptes) liste.push({ texte: comptes, action: OUVRIR_LA_FICHE });
  const tva = phraseTvaADeclarer(ligne.tva_a_declarer, ligne.tva_echeance);
  if (tva) liste.push({ texte: tva, action: OUVRIR_LA_FICHE });
  if (ligne.alerte_regime) liste.push({ texte: ligne.alerte_regime, action: OUVRIR_LA_FICHE });
  if (ligne.alerte_tva) liste.push({ texte: ligne.alerte_tva, action: OUVRIR_LA_FICHE });
  const aConfirmer = phraseAConfirmer(ligne.a_confirmer ?? []);
  if (aConfirmer) liste.push({ texte: aConfirmer, action: OUVRIR_LA_FICHE });
  return liste;
}

export function analyserLigne(
  ligne: LignePortefeuille,
  connexion?: ConnexionLigne | null,
): AnalyseLigne {
  const trouvees = raisons(ligne, connexion);
  const premiere = trouvees[0];
  if (!premiere) return { aTraiter: false, raison: "", autres: 0, action: null };
  return {
    aTraiter: true,
    raison: premiere.texte,
    autres: trouvees.length - 1,
    action: premiere.action,
  };
}

/** Toutes les raisons d'un dossier, pour la fiche : la ligne n'en dit qu'une. */
export function toutesLesRaisons(
  ligne: LignePortefeuille,
  connexion?: ConnexionLigne | null,
): string[] {
  return raisons(ligne, connexion).map((raison) => raison.texte);
}

export type EtatStatut = "a-traiter" | "a-jour" | "sans-compte" | "cloture";

/** Le statut d'un dossier qui n'est pas à traiter (`statut-dossier`).
 * - pas de compte ouvert : « Sans compte », invité ou non (la ligne précise
 *   « Invitation envoyée ») ;
 * - frise de l'exercice complète : « Clôturé » ;
 * - sinon « À jour » : rien n'est en attente. */
export function statutDossier(ligne: LignePortefeuille, aTraiter: boolean): EtatStatut {
  if (aTraiter) return "a-traiter";
  const ouvert = ligne.statut_invitation === "actif";
  if (!ouvert) return "sans-compte";
  return etapeBloquante(ligne.etape_courante, ouvert) === "À jour" ? "cloture" : "a-jour";
}

/** « 3/6 · Signature » : le rang de l'étape bloquante sur les six jalons de la
 * frise, puis son nom. Les exercices sans frise disent « Sans exercice »,
 * et une frise complète « 6/6 · Terminé ». */
export function libelleEtape(etape: string, compteOuvert: boolean): string {
  const bloquante = etapeBloquante(etape, compteOuvert);
  if (bloquante === "Sans exercice") return bloquante;
  const total = ETAPES_FRISE.length;
  if (bloquante === "À jour") return `${total}/${total} · Terminé`;
  return `${rangEtape(etape, compteOuvert) + 2}/${total} · ${bloquante}`;
}

/** À traiter d'abord, sans toucher à l'ordre relatif des autres lignes : le
 * tri choisi par le gestionnaire (nom, étape, résultat) s'applique dans
 * chaque groupe. `Array.prototype.sort` est stable. */
export function aTraiterEnPremier<T>(lignes: readonly T[], estATraiter: (ligne: T) => boolean): T[] {
  return [...lignes].sort((a, b) => Number(estATraiter(b)) - Number(estATraiter(a)));
}

/** Le titre d'accueil, découpé pour que l'écran surligne « N dossiers » :
 * `surligne` est vide quand tout est à jour (pas de surlignage sans chiffre). */
export function titreAccueil(aTraiter: number): { surligne: string; suite: string } {
  if (aTraiter <= 0) return { surligne: "", suite: "Tout est à jour." };
  return {
    surligne: aTraiter === 1 ? "1 dossier" : `${aTraiter} dossiers`,
    suite: " à traiter.",
  };
}

/** La ligne sous le titre. `aTraiter` et `autres` ne comptent que les dossiers
 * qui entrent dans les compteurs. Vide quand il n'y a rien à dire. */
export function sousTitreAccueil(aTraiter: number, autres: number): string {
  if (autres <= 0) return "";
  if (aTraiter <= 0) {
    return autres === 1 ? "1 entreprise suit son cours." : `${autres} entreprises suivent leur cours.`;
  }
  return autres === 1 ? "1 autre suit son cours." : `${autres} autres suivent leur cours.`;
}

/** « Mercredi 11 novembre ». La date vient de l'appelant : pas d'horloge ici. */
export function dateDuJour(maintenant: Date): string {
  const texte = new Intl.DateTimeFormat("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(maintenant);
  return texte.charAt(0).toUpperCase() + texte.slice(1);
}
