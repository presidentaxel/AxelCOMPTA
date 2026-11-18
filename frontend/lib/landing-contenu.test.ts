import assert from "node:assert/strict";
import test from "node:test";

import {
  DESCRIPTION_PAGE,
  EXTRAIT_JOURNAL,
  TITRE_PAGE,
  formaterCentimes,
  texteDeLaPage,
  totauxJournal,
} from "./landing-contenu";

// Le brief d'AXE-949, « À ne pas écrire » : si un de ces mots entre dans la
// page, ce test échoue avec le mot.
const INTERDITS: [string, RegExp][] = [
  ["nom de client", /serenity|mk driving|b'?cars/iu],
  ["prix", /€|\bprix\b|\btarifs?\b|gratuit|abonnement|\beuros?\b/iu],
  ["revenus", /revenus?|chiffre d'affaires/iu],
  ["« disponible pour tous »", /disponible pour tous|pour tout le monde|grand public/iu],
  ["pack VTC complet", /pack vtc/iu],
  ["Rollee", /rollee/iu],
  ["application chauffeur", /application (mobile )?(du |des )?chauffeurs?|appli(cation)? mobile|espace chauffeur/iu],
  ["signature RGS", /\bRGS\b|signature (électronique )?qualifiée/iu],
  ["annexes 2054 à 2059", /\b20(5[4-9])\b/u],
  ["fournisseur de données", /digifactory|bridge|supabase/iu],
];

test("la page n'écrit rien de ce que le brief interdit", () => {
  const texte = texteDeLaPage();
  for (const [nom, motif] of INTERDITS) {
    assert.doesNotMatch(texte, motif, `interdit : ${nom}`);
  }
});

test("pas de tiret long dans les textes, qui lisent comme écrits par une machine", () => {
  assert.doesNotMatch(texteDeLaPage(), /—|–/u);
});

test("le titre et la description tiennent dans un aperçu de partage", () => {
  assert.ok(TITRE_PAGE.length <= 60, `titre de ${TITRE_PAGE.length} caractères`);
  assert.ok(DESCRIPTION_PAGE.length <= 160, `description de ${DESCRIPTION_PAGE.length} caractères`);
});

test("l'extrait de journal est équilibré : le débit égale le crédit", () => {
  const { debit, credit } = totauxJournal(EXTRAIT_JOURNAL.lignes);
  assert.equal(debit, credit);
  assert.equal(debit, 9680);
});

test("un montant se lit en euros et centimes, avec l'espace des milliers", () => {
  assert.equal(formaterCentimes(7017), "70,17");
  assert.equal(formaterCentimes(5), "0,05");
  assert.equal(formaterCentimes(1260), "12,60");
  assert.match(formaterCentimes(123456), /^1\s234,56$/u);
});
