import assert from "node:assert/strict";
import test from "node:test";

import {
  apercuCompte,
  bandeauRollee,
  detailFiche,
  rechercheAssezLongue,
  effetDelier,
  phraseRapprochement,
  rapprochementEnCours,
  type AChoisirRollee,
  type PassageRollee,
} from "./liens-rollee";

const COMPTE: AChoisirRollee = {
  rollee_user_id: "u1",
  etat: "a_choisir",
  nom: "",
  initiales: "K.B.",
  plateformes: ["Bolt", "Uber"],
  iban_fin: "0189",
  candidats: [],
};

test("l'aperçu ne montre que des initiales, des plateformes et la fin de l'IBAN", () => {
  assert.equal(apercuCompte(COMPTE), "K.B. · Bolt, Uber · IBAN …0189");
  assert.equal(apercuCompte({ ...COMPTE, initiales: "", plateformes: [], iban_fin: null }), "Sans nom · aucune plateforme");
});

test("le bandeau compte les comptes à choisir et les non trouvés", () => {
  assert.equal(bandeauRollee({ etats: {}, a_choisir: [] }), null);
  const texte = bandeauRollee({ etats: {}, a_choisir: [COMPTE, { ...COMPTE, etat: "non_trouve" }] });
  assert.equal(
    texte,
    "1 compte Rollee attend votre choix, 1 n'a été rapproché d'aucune entreprise. Sans ce lien, les revenus Uber et Bolt n'arrivent pas.",
  );
});

test("retirer un lien dit ce qui sera contre-passé", () => {
  assert.match(effetDelier(0), /Aucun versement/);
  assert.match(effetDelier(3), /Les 3 versements déjà importés seront contre-passés, jamais supprimé/);
});

const PASSAGE: PassageRollee = {
  statut: "fait",
  resultat: "TENANT : 1 relié(s) automatiquement, 2 à choisir, 3 non trouvé(s)",
  erreur: null,
  demandee_le: "2026-11-14T08:00:00Z",
  terminee_le: "2026-11-14T08:03:00Z",
};

test("AXE-918 : la phrase du rapprochement dit où il en est", () => {
  const date = () => "14/11/2026";
  assert.equal(phraseRapprochement(null, date), null);
  assert.equal(phraseRapprochement({ ...PASSAGE, statut: "en_attente" }, date), "Rapprochement demandé…");
  assert.match(phraseRapprochement({ ...PASSAGE, statut: "en_cours" }, date) ?? "", /quelques minutes/);
  assert.equal(
    phraseRapprochement({ ...PASSAGE, statut: "echec", erreur: "Rollee indisponible" }, date),
    "Le rapprochement a échoué : Rollee indisponible.",
  );
  assert.equal(
    phraseRapprochement(PASSAGE, date),
    "Dernier rapprochement le 14/11/2026 : TENANT : 1 relié(s) automatiquement, 2 à choisir, 3 non trouvé(s).",
  );
});

test("AXE-918 : un rapprochement en attente ou en cours bloque le bouton", () => {
  assert.equal(rapprochementEnCours(null), false);
  assert.equal(rapprochementEnCours({ ...PASSAGE, statut: "en_cours" }), true);
  assert.equal(rapprochementEnCours({ ...PASSAGE, statut: "en_attente" }), true);
  assert.equal(rapprochementEnCours(PASSAGE), false);
});

test("AXE-919 : l'aperçu montre le nom en clair quand on l'a", () => {
  assert.equal(apercuCompte({ ...COMPTE, nom: "Karim Benali" }), "Karim Benali · Bolt, Uber · IBAN …0189");
});

test("AXE-919 : le détail d'un user de l'annuaire, et la recherche à 2 lettres", () => {
  const fiche = {
    rollee_user_id: "u1",
    nom: "Karim Benali",
    plateformes: ["uber.com-rev"],
    compte: "Serenity Mobilité",
    email_masque: "k•••i@exemple.fr",
    relie_a: null,
  };
  assert.equal(detailFiche(fiche), "uber.com-rev · Serenity Mobilité · k•••i@exemple.fr");
  assert.equal(detailFiche({ ...fiche, plateformes: [], email_masque: null }), "aucune plateforme · Serenity Mobilité");
  assert.equal(rechercheAssezLongue("k"), false);
  assert.equal(rechercheAssezLongue(" é1"), false);
  assert.equal(rechercheAssezLongue("ka"), true);
});
