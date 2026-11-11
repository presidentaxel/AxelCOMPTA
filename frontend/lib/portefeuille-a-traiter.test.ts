import assert from "node:assert/strict";
import test from "node:test";

import {
  aTraiterEnPremier,
  analyserLigne,
  connexionARenouveler,
  dateDuJour,
  libelleEtape,
  sousTitreAccueil,
  statutDossier,
  titreAccueil,
  toutesLesRaisons,
  type LignePortefeuille,
} from "./portefeuille-a-traiter";

function ligne(extra: Partial<LignePortefeuille> = {}): LignePortefeuille {
  return {
    dossier_id: "D1",
    alerte_regime: null,
    alerte_tva: null,
    statut_invitation: "actif",
    etape_courante: "Compte",
    ...extra,
  };
}

test("rien d'alerté : pas à traiter, pas de raison ni d'action", () => {
  const analyse = analyserLigne(ligne());
  assert.deepEqual(analyse, { aTraiter: false, raison: "", autres: 0, action: null });
});

test("les champs absents d'un portefeuille mémorisé ne comptent pas", () => {
  assert.equal(analyserLigne(ligne({ a_confirmer: undefined, comptes_a_choisir: undefined })).aTraiter, false);
});

test("alerte de régime : la phrase de l'API, ouvrir la fiche", () => {
  const analyse = analyserLigne(ligne({ alerte_regime: "Option à l'IR à vérifier." }));
  assert.equal(analyse.aTraiter, true);
  assert.equal(analyse.raison, "Option à l'IR à vérifier.");
  assert.deepEqual(analyse.action, { type: "ouvrir", libelle: "Ouvrir la fiche" });
});

test("alerte de TVA", () => {
  const analyse = analyserLigne(ligne({ alerte_tva: "Franchise en base dépassée." }));
  assert.equal(analyse.aTraiter, true);
  assert.equal(analyse.raison, "Franchise en base dépassée.");
});

test("configuration à confirmer : un code inconnu ne déclenche rien", () => {
  assert.equal(analyserLigne(ligne({ a_confirmer: ["forme_juridique"] })).aTraiter, true);
  assert.match(analyserLigne(ligne({ a_confirmer: ["forme_juridique"] })).raison, /à confirmer par le dirigeant/);
  assert.equal(analyserLigne(ligne({ a_confirmer: ["inconnu"] })).aTraiter, false);
});

test("comptes bancaires à choisir", () => {
  const analyse = analyserLigne(ligne({ comptes_a_choisir: 2, comptes_a_choisir_depuis: "2026-11-03" }));
  assert.equal(analyse.aTraiter, true);
  assert.match(analyse.raison, /2 comptes bancaires attendent le choix du dirigeant depuis le 03\/11\/2026/);
});

test("TVA à déclarer", () => {
  const analyse = analyserLigne(ligne({ tva_a_declarer: "2026-03", tva_echeance: "2026-04-12" }));
  assert.equal(analyse.aTraiter, true);
  assert.equal(analyse.raison, "TVA de mars 2026 à déclarer avant le 12/04/2026.");
});

test("connexion bancaire : expirée, à renouveler, à confirmer, et le lien vers l'écran des connexions", () => {
  const lien = { type: "lien", libelle: "Renouveler", href: "/connexions-bancaires" };
  const expiree = analyserLigne(ligne(), { statut: "expire", sante: "ok", jours_restants: null });
  assert.equal(expiree.raison, "La connexion bancaire a expiré.");
  assert.deepEqual(expiree.action, lien);

  const bientot = analyserLigne(ligne(), { statut: "a_renouveler", sante: "ok", jours_restants: 5 });
  assert.equal(bientot.raison, "La connexion bancaire est à renouveler sous 5 jours.");
  const demain = analyserLigne(ligne(), { statut: "a_renouveler", sante: "ok", jours_restants: 1 });
  assert.equal(demain.raison, "La connexion bancaire est à renouveler sous 1 jour.");
  const sansDate = analyserLigne(ligne(), { statut: "a_renouveler", sante: "ok", jours_restants: null });
  assert.equal(sansDate.raison, "La connexion bancaire est à renouveler.");

  const confirmer = analyserLigne(ligne(), { statut: "actif", sante: "auth_requise", jours_restants: 80 });
  assert.equal(confirmer.aTraiter, true);
  assert.match(confirmer.raison, /nouvelle confirmation/);
});

test("connexion saine, en pause ou jamais connectée : rien à faire", () => {
  assert.equal(connexionARenouveler(null), false);
  assert.equal(connexionARenouveler(undefined), false);
  assert.equal(connexionARenouveler({ statut: "actif", sante: "ok", jours_restants: 80 }), false);
  assert.equal(connexionARenouveler({ statut: "actif", sante: "en_pause", jours_restants: 80 }), false);
  assert.equal(connexionARenouveler({ statut: "jamais_connecte", sante: "jamais_connecte", jours_restants: null }), false);
  assert.equal(analyserLigne(ligne(), { statut: "actif", sante: "ok", jours_restants: 80 }).aTraiter, false);
});

test("plusieurs raisons : la plus pressante d'abord, les autres comptées", () => {
  const dossier = ligne({
    alerte_tva: "Franchise en base dépassée.",
    comptes_a_choisir: 1,
    tva_a_declarer: "2026-03",
    tva_echeance: "2026-04-12",
  });
  const analyse = analyserLigne(dossier);
  assert.match(analyse.raison, /Un compte bancaire attend le choix du dirigeant/);
  assert.equal(analyse.autres, 2);
  const avecConnexion = analyserLigne(dossier, { statut: "expire", sante: "ok", jours_restants: null });
  assert.equal(avecConnexion.raison, "La connexion bancaire a expiré.");
  assert.equal(avecConnexion.autres, 3);
  assert.equal(toutesLesRaisons(dossier).length, 3);
  assert.equal(toutesLesRaisons(dossier, { statut: "expire", sante: "ok", jours_restants: null }).length, 4);
});

test("un dossier exclu des compteurs n'est jamais à traiter", () => {
  const exclu = ligne({ exclu_compteurs: true, alerte_regime: "Option à l'IR à vérifier." });
  assert.equal(analyserLigne(exclu, { statut: "expire", sante: "ok", jours_restants: null }).aTraiter, false);
  assert.deepEqual(toutesLesRaisons(exclu), []);
});

test("statut du dossier", () => {
  assert.equal(statutDossier(ligne({ alerte_tva: "x" }), true), "a-traiter");
  assert.equal(statutDossier(ligne({ statut_invitation: null }), false), "sans-compte");
  assert.equal(statutDossier(ligne({ statut_invitation: "invité" }), false), "sans-compte");
  assert.equal(statutDossier(ligne({ etape_courante: "Clôture" }), false), "a-jour");
  assert.equal(statutDossier(ligne({ etape_courante: "Signature légale" }), false), "cloture");
});

test("étape en texte", () => {
  assert.equal(libelleEtape("Compte", false), "1/6 · Compte");
  assert.equal(libelleEtape("Compte", true), "2/6 · Clôture");
  assert.equal(libelleEtape("Clôture", true), "3/6 · Signature");
  assert.equal(libelleEtape("Impôts", true), "6/6 · Signature légale");
  assert.equal(libelleEtape("Signature légale", true), "6/6 · Terminé");
  assert.equal(libelleEtape("Sans exercice", true), "Sans exercice");
});

test("à traiter d'abord, l'ordre relatif des autres est gardé", () => {
  const lignes = [
    { nom: "A", t: false },
    { nom: "B", t: true },
    { nom: "C", t: false },
    { nom: "D", t: true },
  ];
  assert.deepEqual(
    aTraiterEnPremier(lignes, (l) => l.t).map((l) => l.nom),
    ["B", "D", "A", "C"],
  );
  assert.deepEqual(lignes.map((l) => l.nom), ["A", "B", "C", "D"]);
});

test("titre d'accueil : singulier, pluriel, zéro sans surlignage", () => {
  assert.deepEqual(titreAccueil(3), { surligne: "3 dossiers", suite: " à traiter." });
  assert.deepEqual(titreAccueil(1), { surligne: "1 dossier", suite: " à traiter." });
  assert.deepEqual(titreAccueil(0), { surligne: "", suite: "Tout est à jour." });
});

test("sous-titre d'accueil", () => {
  assert.equal(sousTitreAccueil(3, 12), "12 autres suivent leur cours.");
  assert.equal(sousTitreAccueil(3, 1), "1 autre suit son cours.");
  assert.equal(sousTitreAccueil(3, 0), "");
  assert.equal(sousTitreAccueil(0, 4), "4 entreprises suivent leur cours.");
  assert.equal(sousTitreAccueil(0, 1), "1 entreprise suit son cours.");
});

test("date du jour en français", () => {
  assert.equal(dateDuJour(new Date(2026, 10, 11, 12)), "Mercredi 11 novembre");
});
