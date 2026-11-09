import assert from "node:assert/strict";
import test from "node:test";

import { choixCompte, rapprochement, titreCompte, type CompteAffiche } from "./comptes-bancaires";

const base: CompteAffiche = {
  compte: "5121",
  nom: "Compte PRO",
  solde_comptable_cts: 11_000,
  solde_banque_cts: 11_000,
  ecart_cts: 0,
};

test("le titre est le nom du compte, ou son numéro", () => {
  assert.equal(titreCompte(base), "Compte PRO");
  assert.equal(titreCompte({ ...base, nom: null }), "Compte 5121");
  assert.equal(titreCompte({ ...base, compte: "512" }), "Opérations sans compte identifié");
});

test("un compte rapproché est à jour", () => {
  assert.deepEqual(rapprochement(base), { etat: "a_jour" });
});

test("un écart est signalé avec son montant", () => {
  assert.deepEqual(rapprochement({ ...base, ecart_cts: -250 }), { etat: "ecart", ecartCts: -250 });
});

test("un compte jamais relevé n'a pas d'écart", () => {
  assert.deepEqual(rapprochement({ ...base, solde_banque_cts: null, ecart_cts: null }), {
    etat: "jamais_releve",
  });
});

test("le 512 non ventilé n'est pas rapproché", () => {
  assert.deepEqual(rapprochement({ ...base, compte: "512" }), { etat: "non_ventile" });
});

test("choix d'un compte : retenu, écarté ou à décider (AXE-729)", () => {
  const base: CompteAffiche = {
    compte: "5122",
    nom: "Livret",
    solde_comptable_cts: 0,
    solde_banque_cts: 90_000,
    ecart_cts: null,
  };
  assert.equal(choixCompte(base), "retenu");
  assert.equal(choixCompte({ ...base, retenu: null }), "a_decider");
  assert.equal(choixCompte({ ...base, retenu: false }), "ecarte");
  assert.deepEqual(rapprochement({ ...base, retenu: null }), { etat: "jamais_releve" });
});
