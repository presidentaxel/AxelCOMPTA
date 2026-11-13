import assert from "node:assert/strict";
import test from "node:test";

import { apercuCompte, bandeauRollee, effetDelier, type AChoisirRollee } from "./liens-rollee";

const COMPTE: AChoisirRollee = {
  rollee_user_id: "u1",
  etat: "a_choisir",
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
