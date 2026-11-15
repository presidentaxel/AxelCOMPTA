import assert from "node:assert/strict";
import test from "node:test";

import { chercheExpert, type LigneCherchable } from "./recherche-expert";

const LIGNES: LigneCherchable[] = [
  {
    libelle: "TOTAL 23/11",
    dossier_nom: "Sophie Martin",
    montant_cts: -2300,
    detail: "Carburant",
    compte_suggere: "6061",
  },
  {
    libelle: "PEAGE",
    dossier_nom: "Karim Benali",
    montant_cts: -450,
    compte_actuel: "625",
  },
];

test("total 23 retrouve le libellé et le montant", () => {
  const trouves = chercheExpert(LIGNES, "total 23");
  assert.deepEqual(
    trouves.map((ligne) => ligne.libelle),
    ["TOTAL 23/11"],
  );
});

test("un mot manquant écarte la ligne", () => {
  assert.equal(chercheExpert(LIGNES, "total karim").length, 0);
});

test("l'entreprise, le compte et une saisie vide", () => {
  assert.equal(chercheExpert(LIGNES, "karim")[0]?.libelle, "PEAGE");
  assert.equal(chercheExpert(LIGNES, "6061")[0]?.libelle, "TOTAL 23/11");
  assert.equal(chercheExpert(LIGNES, "   ").length, 2);
});
