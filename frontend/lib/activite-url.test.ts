import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { ecrireEtatActivite, lireEtatActivite } from "./activite-url";

describe("état d'activité dans l'URL", () => {
  it("lit les défauts quand l'adresse est vide", () => {
    assert.deepEqual(lireEtatActivite(new URLSearchParams()), {
      vue: "traiter",
      mois: null,
      sens: "sorties",
    });
  });

  it("lit l'onglet, le mois et le sens", () => {
    const params = new URLSearchParams("vue=mouvements&mois=2026-03&sens=entrees");
    assert.deepEqual(lireEtatActivite(params), {
      vue: "mouvements",
      mois: "2026-03",
      sens: "entrees",
    });
  });

  it("ignore un mois mal formé", () => {
    assert.equal(lireEtatActivite(new URLSearchParams("mois=2026-13")).mois, null);
    assert.equal(lireEtatActivite(new URLSearchParams("mois=mars")).mois, null);
  });

  it("n'écrit pas les valeurs par défaut et garde le reste", () => {
    const actuel = new URLSearchParams("vue=mouvements&mois=2026-01&sens=entrees&autre=1");
    assert.equal(ecrireEtatActivite(actuel, { vue: "traiter", sens: "sorties" }), "mois=2026-01&autre=1");
  });

  it("pose un choix sans effacer les autres", () => {
    const actuel = new URLSearchParams("vue=mouvements");
    assert.equal(ecrireEtatActivite(actuel, { mois: "2026-11" }), "vue=mouvements&mois=2026-11");
  });

  it("retire le mois quand on le vide", () => {
    const actuel = new URLSearchParams("vue=mouvements&mois=2026-11");
    assert.equal(ecrireEtatActivite(actuel, { mois: null }), "vue=mouvements");
  });
});
