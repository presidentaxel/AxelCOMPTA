import assert from "node:assert/strict";
import test from "node:test";

import { etatPlateforme, etatVersement, motifEnClair, resumePlateformes } from "./plateformes";

const date = (iso: string) => iso.split("-").reverse().join("/");

test("l'état d'une plateforme se lit en clair", () => {
  assert.equal(
    etatPlateforme({ nom: "Uber", etat: "connecte", relie_le: "2026-11-06T10:00:00" }, date),
    "relié le 06/11/2026",
  );
  assert.equal(etatPlateforme({ nom: "Bolt", etat: "a_reconnecter", relie_le: null }, date), "à reconnecter");
});

test("le gestionnaire ne voit que des nombres", () => {
  assert.equal(
    resumePlateformes({ reliees: 1, attendues: 2, a_reconnecter: 1, manquantes: ["bolt"] }),
    "Plateformes reliées : 1/2 · 1 à reconnecter",
  );
  assert.equal(
    resumePlateformes({ reliees: 0, attendues: 0, a_reconnecter: 0, manquantes: [] }),
    "Aucune plateforme reliée",
  );
});

test("l'état d'un versement dit pourquoi il est à vérifier", () => {
  assert.equal(etatVersement("reconcilie", null), "rapproché");
  assert.equal(
    etatVersement("a_verifier", "plusieurs virements possibles"),
    "à vérifier : plusieurs virements possibles",
  );
});

test("les versements à vérifier se comptent côté gestionnaire, sans montant", () => {
  assert.equal(
    resumePlateformes({ reliees: 2, attendues: 2, a_reconnecter: 0, manquantes: [], versements_a_verifier: 3 }),
    "Plateformes reliées : 2/2 · 3 versements à vérifier",
  );
  assert.equal(
    resumePlateformes({ reliees: 2, attendues: 2, a_reconnecter: 0, manquantes: [], versements_a_verifier: 0 }),
    "Plateformes reliées : 2/2",
  );
});

test("le motif d'un versement à vérifier se dit sans jargon comptable", () => {
  assert.equal(motifEnClair("plusieurs virements possibles"), "Plusieurs virements reçus peuvent correspondre.");
  assert.equal(motifEnClair("virement classé en 625100"), "Le virement reçu n'est pas classé en recette.");
  assert.doesNotMatch(motifEnClair("Écriture déséquilibrée : 12 ≠ 13"), /déséquilibrée/);
  assert.doesNotMatch(motifEnClair(null), /null/);
});
