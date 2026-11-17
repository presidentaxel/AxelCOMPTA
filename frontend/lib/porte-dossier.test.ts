import assert from "node:assert/strict";
import test from "node:test";

import { HOTE_DOSSIER, HOTE_VITRINE, decisionPorte } from "./porte-dossier";

test("en local, l'accueil reste l'accueil et l'ancienne adresse rejoint /dossier", () => {
  assert.deepEqual(decisionPorte("localhost:3000", "/", ""), { action: "continuer" });
  assert.deepEqual(decisionPorte("localhost:3000", "/dossier/login", ""), { action: "continuer" });
  assert.deepEqual(decisionPorte("localhost:3000", "/chauffeur/login", "?mode=lien"), {
    action: "rediriger",
    url: "/dossier/login?mode=lien",
  });
});

test("sur la porte d'un dossier, / ouvre l'espace et jamais la vitrine", () => {
  assert.deepEqual(decisionPorte(HOTE_DOSSIER, "/", ""), {
    action: "rediriger",
    url: "/dossier",
  });
  assert.deepEqual(decisionPorte(HOTE_DOSSIER, "/chauffeur/DIGI_1/exercice", ""), {
    action: "rediriger",
    url: "/dossier/DIGI_1/exercice",
  });
  assert.deepEqual(decisionPorte(HOTE_DOSSIER, "/dossier/login", ""), { action: "continuer" });
});

test("sur la vitrine, un chemin de dossier part vers l'autre nom", () => {
  assert.deepEqual(decisionPorte(HOTE_VITRINE, "/", ""), { action: "continuer" });
  assert.deepEqual(decisionPorte(HOTE_VITRINE, "/portefeuille", ""), { action: "continuer" });
  assert.deepEqual(decisionPorte(`${HOTE_VITRINE}:443`, "/chauffeur/accepter-invitation", ""), {
    action: "rediriger",
    url: `https://${HOTE_DOSSIER}/dossier/accepter-invitation`,
  });
  assert.deepEqual(decisionPorte(HOTE_VITRINE, "/dossier/DIGI_1", "?onglet=tva"), {
    action: "rediriger",
    url: `https://${HOTE_DOSSIER}/dossier/DIGI_1?onglet=tva`,
  });
});
