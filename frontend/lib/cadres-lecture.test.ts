import assert from "node:assert/strict";
import { test } from "node:test";

import { formesMontant, trouverCadres } from "./cadres-lecture";

const morceau = (str: string, x = 0) => ({ str, x, y: 0, largeur: 10, hauteur: 5 });

test("un montant se reconnaît sous ses formes imprimées", () => {
  assert.deepEqual(formesMontant(55074), ["55074"]);
  assert.deepEqual(formesMontant(-61600), ["61600", "616"]);
});

test("chaque valeur lue est encadrée là où le PDF l'imprime", () => {
  const lu = {
    banque: "Société Générale",
    iban: "",
    montants: [
      { nom: "solde_fin_cts", valeur_cts: 55074 },
      { nom: "solde_debut_cts", valeur_cts: 0 },
    ],
  };
  const cadres = trouverCadres(
    [morceau("SOCIETE GENERALE"), morceau("Société Générale", 1), morceau("Nouveau solde 550,74 €", 2), morceau("0,00", 3)],
    lu,
  );
  assert.deepEqual(
    cadres.map((c) => [c.champ, c.x]),
    [
      ["banque", 1],
      ["solde_fin_cts", 2],
    ],
  );
});
