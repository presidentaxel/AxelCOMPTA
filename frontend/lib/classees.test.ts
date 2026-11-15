import assert from "node:assert/strict";
import test from "node:test";

import {
  avecRecherche,
  changer,
  formatConfiance,
  lireEtat,
  phraseCompteurs,
  versApi,
  versRecherche,
  VUE_A_TRAITER,
} from "./classees";
import type { OperationsClassees } from "./types";

test("l'état se lit dans l'URL, avec des défauts", () => {
  const etat = lireEtat("?vue=auto&origine=regle&categorie=carburant");
  assert.equal(etat.vue, "auto");
  assert.equal(etat.origine, "regle");
  assert.equal(etat.tri, "recentes");
  assert.equal(lireEtat("?vue=inventee").vue, VUE_A_TRAITER);
  assert.equal(lireEtat("").page, "1");
});

test("changer un filtre ramène à la première page", () => {
  const etat = changer(lireEtat("?vue=auto&page=3"), "origine", "regle");
  assert.equal(etat.page, "1");
  assert.equal(changer(etat, "page", "2").page, "2");
});

test("l'URL ne garde que ce qui diffère du défaut", () => {
  assert.equal(versRecherche(lireEtat("")), "");
  assert.equal(versRecherche(lireEtat("?vue=auto&tri=confiance")), "?vue=auto&tri=confiance");
});

test("paramètres de l'API", () => {
  assert.equal(versApi(lireEtat("?vue=auto&origine=regle")).toString(), "statut=auto&origine=regle&tri=recentes&page=1");
  assert.equal(versApi(lireEtat("?vue=toutes")).get("statut"), null);
  const parChauffeur = versApi(lireEtat("?vue=auto&tri=chauffeur&chauffeur=DEMO_sophie"));
  assert.equal(parChauffeur.get("dossier"), "DEMO_sophie");
  assert.equal(parChauffeur.get("tri"), "chauffeur");
  assert.equal(versApi(lireEtat("?vue=auto&q=total%2023")).get("q"), "total 23");
  assert.equal(versApi(lireEtat("?vue=auto")).get("q"), null);
});

test("la recherche réunit les pages et garde le montant", async () => {
  const page = (libelle: string, montant: number, numero: number, pages: number): OperationsClassees => ({
    operations: [
      {
        dossier_id: "d",
        dossier_nom: "Sophie",
        ecriture_id: libelle,
        date: "2026-03-01",
        libelle,
        montant_cts: montant,
        compte: "6061",
        categorie: null,
        origine: "regle",
        confiance: null,
        statut: "auto",
        sens: "sortie",
        verdict: null,
      },
    ],
    total: pages,
    page: numero,
    pages,
    compteurs: { auto: pages, chauffeur: 0, expert: 0, justes: 0, fausses: 0 },
    categories: [],
  });
  const resultat = await avecRecherche(lireEtat("?vue=auto&q=total%2023"), async (params) =>
    params.get("page") === "2" ? page("TOTAL 23/11", -2300, 2, 2) : page("PEAGE", -450, 1, 2),
  );
  assert.deepEqual(
    resultat.operations.map((operation) => operation.libelle),
    ["TOTAL 23/11"],
  );
  assert.equal(resultat.pages, 1);
});

test("affichages", () => {
  assert.equal(formatConfiance(0.5), "0,50");
  assert.equal(formatConfiance(null), "—");
  assert.equal(
    phraseCompteurs({ auto: 140, justes: 12, fausses: 3 }),
    "140 classées automatiquement, 12 validées justes, 3 marquées fausses",
  );
});
