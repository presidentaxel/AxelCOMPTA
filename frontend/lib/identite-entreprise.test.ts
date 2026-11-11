import assert from "node:assert/strict";
import test from "node:test";

import {
  appliquerRegistre,
  associeVide,
  copierAdresseDuSiege,
  formulaireDepuis,
  lireFormulaire,
  type Formulaire,
  type IdentiteDossierVue,
} from "./identite-entreprise";

const VUE_VIDE: IdentiteDossierVue = {
  identite: null,
  forme_juridique: "SASU",
  associe_unique: true,
  qualite_par_defaut: "Président",
  siren_connu: "987142031",
};

function rempli(): Formulaire {
  const formulaire = formulaireDepuis(VUE_VIDE);
  return {
    ...formulaire,
    denomination: "AMRANI VTC",
    nic: "00010",
    adresse_siege: { numero: "14", voie: "rue X", code_postal: "75011", commune: "Paris", pays: "France" },
    capital_euros: "1 000,50",
    associes: [
      {
        ...associeVide("Président"),
        nom: "AMRANI",
        prenoms: "Karim",
        date_naissance: "1990-04-02",
        commune_naissance: "Paris",
        nb_titres: "100",
      },
    ],
  };
}

test("un formulaire vide part du SIREN connu et d'un associé avec sa qualité", () => {
  const formulaire = formulaireDepuis(VUE_VIDE);
  assert.equal(formulaire.siren, "987142031");
  assert.equal(formulaire.associes.length, 1);
  assert.equal(formulaire.associes[0]?.qualite, "Président");
});

test("une identité déjà saisie se relit avec le capital en euros", () => {
  const lecture = lireFormulaire(rempli());
  assert.equal(lecture.message, null);
  const relu = formulaireDepuis({ ...VUE_VIDE, identite: lecture.corps });
  assert.equal(relu.capital_euros, "1000,50");
  assert.equal(relu.associes[0]?.nb_titres, "100");
});

test("le formulaire donne le corps en centimes et en nombres", () => {
  const lecture = lireFormulaire({ ...rempli(), siren: "987 142 031" });
  assert.equal(lecture.message, null);
  assert.equal(lecture.corps?.capital_social_cts, 100050);
  assert.equal(lecture.corps?.siren, "987142031");
  assert.equal(lecture.corps?.associes[0]?.nb_titres, 100);
  assert.equal("capital_euros" in (lecture.corps ?? {}), false);
});

test("capital, titres ou date de naissance manquants : une phrase", () => {
  assert.match(lireFormulaire({ ...rempli(), capital_euros: "" }).message ?? "", /Capital/u);
  const sansTitres = rempli();
  sansTitres.associes = sansTitres.associes.map((a) => ({ ...a, nb_titres: "0" }));
  assert.match(lireFormulaire(sansTitres).message ?? "", /titres/u);
  const sansDate = rempli();
  sansDate.associes = sansDate.associes.map((a) => ({ ...a, date_naissance: "" }));
  assert.match(lireFormulaire(sansDate).message ?? "", /naissance/u);
});

test("le registre remplit sans effacer ce qui est déjà saisi", () => {
  const avant = { ...formulaireDepuis(VUE_VIDE), denomination: "Mon nom" };
  const apres = appliquerRegistre(avant, {
    siren: "987142031",
    denomination: "",
    nic: "00010",
    code_ape: "49.32Z",
    adresse_siege: { numero: "14", voie: "RUE X", code_postal: "75011", commune: "PARIS", pays: "France" },
  });
  assert.equal(apres.denomination, "Mon nom");
  assert.equal(apres.nic, "00010");
  assert.equal(apres.adresse_siege.commune, "PARIS");
});

test("l'adresse du siège se recopie sur un associé", () => {
  const copie = copierAdresseDuSiege(rempli(), 0);
  assert.deepEqual(copie.associes[0]?.adresse, rempli().adresse_siege);
});
