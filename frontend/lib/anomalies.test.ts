import assert from "node:assert/strict";
import test from "node:test";

import { LIBELLE_ETAT, metaAlerte, motifValide, phraseEvenement, varianteEtat } from "./anomalies";
import type { AlerteAnomalie } from "./types";

const alerte: AlerteAnomalie = {
  id: "a1",
  code: "carburant",
  libelle_ui: "Dépense à justifier",
  detail: "Hors profil du dossier",
  etat: "ouverte",
  libelle_mouvement: "STATION SHELL",
  montant_centimes: -9200,
  date: "2026-03-05",
  moyen_paiement: "card",
};

test("chaque état a un libellé et un badge du vocabulaire", () => {
  assert.equal(LIBELLE_ETAT.en_instruction, "En instruction");
  assert.equal(varianteEtat("ouverte"), "alert");
  assert.equal(varianteEtat("en_instruction"), "pending");
  assert.equal(varianteEtat("justifiee"), "validated");
  assert.equal(varianteEtat("usage_personnel"), "neutral");
  assert.equal(varianteEtat("faux_positif"), "neutral");
});

test("le motif exige trois caractères hors espaces", () => {
  assert.equal(motifValide("  "), null);
  assert.equal(motifValide(" ab "), null);
  assert.equal(motifValide("  Facture reçue  "), "Facture reçue");
});

test("la ligne de contexte donne la date et le moyen de paiement", () => {
  assert.equal(metaAlerte(alerte), "05/03/2026 · Payé par carte");
  assert.equal(metaAlerte({ ...alerte, moyen_paiement: null }), "05/03/2026");
});

test("une ligne d'historique garde le motif et l'état inconnu", () => {
  assert.equal(
    phraseEvenement({ etat: "justifiee", acteur: "Léa", commentaire: "Facture jointe", le: "2026-03-06T10:00:00Z" }),
    "06/03/2026 · Justifiée · Léa · « Facture jointe »",
  );
  assert.equal(
    phraseEvenement({ etat: "autre", acteur: "Léa", commentaire: "", le: "2026-03-06" }),
    "06/03/2026 · autre · Léa",
  );
});
