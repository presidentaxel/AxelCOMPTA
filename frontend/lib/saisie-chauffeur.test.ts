import assert from "node:assert/strict";
import test from "node:test";

import { lireEuros, listeAEnregistrer, type LectureListe } from "./saisie-chauffeur";

test("1 000,50 et l'espace insécable sont acceptés", () => {
  assert.deepEqual(lireEuros("1 000,50"), { centimes: 100050 });
  assert.deepEqual(lireEuros("1\u00a0000,50"), { centimes: 100050 });
  assert.deepEqual(lireEuros("12,3"), { centimes: 1230 });
});

test("une saisie vide ou illisible est refusée, jamais convertie en zéro", () => {
  assert.deepEqual(lireEuros(""), { message: "Indiquez un montant." });
  assert.deepEqual(lireEuros("   "), { message: "Indiquez un montant." });
  const illisible = lireEuros("abc");
  assert.ok("message" in illisible);
  assert.equal("centimes" in lireEuros(""), false);
});

test("un GET en échec puis un ajout n'envoie aucune liste", () => {
  const lecture: LectureListe<{ libelle: string }> = {
    statut: "erreur",
    message: "Impossible de charger.",
  };
  let envois = 0;
  const lignes = listeAEnregistrer(lecture, { libelle: "nouvelle" });
  if (lignes !== null) {
    envois += 1;
  }
  assert.equal(lignes, null);
  assert.equal(envois, 0);
});

test("une lecture réussie ajoute à la liste déjà lue", () => {
  const lecture: LectureListe<{ libelle: string }> = {
    statut: "pret",
    lignes: [{ libelle: "déjà là" }],
  };
  assert.deepEqual(listeAEnregistrer(lecture, { libelle: "nouvelle" }), [
    { libelle: "déjà là" },
    { libelle: "nouvelle" },
  ]);
});
