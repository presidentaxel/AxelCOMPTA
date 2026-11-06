import assert from "node:assert/strict";
import test from "node:test";

import { aConfirmer, libelleForme, phraseIdentiteManquante } from "./confirmation-configuration";
import type { ConfigurationDossier } from "./types";

const BASE: ConfigurationDossier = {
  forme_juridique: "SAS",
  formes_proposees: ["SAS", "SASU"],
  regime_imposition: "IS",
  regime_tva: "reel_normal",
  exercice_debut: "2025-01-01",
  exercice_fin: "2025-12-31",
  a_confirmer: ["forme_juridique"],
  identite_manquante: [],
  raison_blocage: "Le dirigeant doit d'abord confirmer la forme juridique.",
};

test("libellés de forme parlants pour le chauffeur", () => {
  assert.equal(libelleForme("SASU"), "SASU (vous êtes le seul associé)");
  assert.equal(libelleForme("XYZ"), "XYZ");
});

test("à confirmer seulement si Sirene a laissé un doute", () => {
  assert.equal(aConfirmer(BASE), true);
  assert.equal(aConfirmer({ ...BASE, a_confirmer: [] }), false);
});

test("phrase d'identité manquante", () => {
  assert.equal(phraseIdentiteManquante([]), null);
  assert.equal(
    phraseIdentiteManquante(["capital", "associes"]),
    "Votre comptable doit encore renseigner le capital et les associés de la société.",
  );
});
