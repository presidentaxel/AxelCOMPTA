import assert from "node:assert/strict";
import test from "node:test";

import { destinationAccueil } from "./accueil";

// Le décodeur du test lit le jeton comme du JSON : la signature n'est pas en jeu.
const decoder = (jeton: string): Record<string, unknown> => JSON.parse(jeton) as Record<string, unknown>;

const GESTIONNAIRE = JSON.stringify({ app_metadata: { tenant_id: "T1" } });
const CHAUFFEUR = JSON.stringify({ app_metadata: { dossier_id: "D1" } });
const SANS_LIEN = JSON.stringify({ app_metadata: {} });

test("sans session, la page publique reste affichée", () => {
  assert.equal(destinationAccueil({ gestionnaire: null, chauffeur: null }, decoder), null);
});

test("un gestionnaire connecté arrive toujours sur le portefeuille", () => {
  assert.equal(destinationAccueil({ gestionnaire: GESTIONNAIRE, chauffeur: null }, decoder), "/portefeuille");
});

test("un chauffeur connecté arrive dans son espace", () => {
  assert.equal(destinationAccueil({ gestionnaire: null, chauffeur: CHAUFFEUR }, decoder), "/chauffeur");
});

test("avec les deux sessions, le portefeuille l'emporte", () => {
  assert.equal(destinationAccueil({ gestionnaire: GESTIONNAIRE, chauffeur: CHAUFFEUR }, decoder), "/portefeuille");
});

test("un jeton gestionnaire qui n'ouvre pas le portefeuille ne le fait pas ouvrir", () => {
  assert.equal(destinationAccueil({ gestionnaire: CHAUFFEUR, chauffeur: null }, decoder), null);
  assert.equal(destinationAccueil({ gestionnaire: SANS_LIEN, chauffeur: null }, decoder), null);
});

test("un jeton illisible laisse la vitrine, sans erreur", () => {
  const casse = (): Record<string, unknown> => {
    throw new Error("jeton illisible");
  };
  assert.equal(destinationAccueil({ gestionnaire: "x", chauffeur: "y" }, casse), null);
});

test("un jeton gestionnaire cassé n'empêche pas la session chauffeur", () => {
  const decodeur = (jeton: string): Record<string, unknown> => {
    if (jeton === "casse") throw new Error("illisible");
    return decoder(jeton);
  };
  assert.equal(destinationAccueil({ gestionnaire: "casse", chauffeur: CHAUFFEUR }, decodeur), "/chauffeur");
});
