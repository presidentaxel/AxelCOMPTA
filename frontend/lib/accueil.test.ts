import assert from "node:assert/strict";
import test from "node:test";

import { destinationAccueil } from "./accueil";

// Le décodeur du test lit le jeton comme du JSON : la signature n'est pas en jeu.
const decoder = (jeton: string): Record<string, unknown> => JSON.parse(jeton) as Record<string, unknown>;

const GESTIONNAIRE = JSON.stringify({ app_metadata: { tenant_id: "T1" } });
const CHAUFFEUR = JSON.stringify({ app_metadata: { dossier_id: "D1" } });
const SANS_LIEN = JSON.stringify({ app_metadata: {} });

test("sans session, « Se connecter » va à la page de connexion", () => {
  assert.equal(destinationAccueil({ gestionnaire: null }, decoder), null);
});

test("« Se connecter » ouvre le portefeuille d'un gestionnaire", () => {
  assert.equal(destinationAccueil({ gestionnaire: GESTIONNAIRE }, decoder), "/portefeuille");
});

test("un jeton chauffeur n'ouvre pas le portefeuille", () => {
  assert.equal(destinationAccueil({ gestionnaire: CHAUFFEUR }, decoder), null);
});

test("un jeton gestionnaire sans portefeuille ne l'ouvre pas", () => {
  assert.equal(destinationAccueil({ gestionnaire: SANS_LIEN }, decoder), null);
});

test("un jeton illisible n'ouvre pas le portefeuille", () => {
  const casse = (): Record<string, unknown> => {
    throw new Error("jeton illisible");
  };
  assert.equal(destinationAccueil({ gestionnaire: "x" }, casse), null);
});
