import assert from "node:assert/strict";
import test from "node:test";

import { nomPeriode, periodeParDefaut, phraseTvaADeclarer, type PeriodeTva } from "./tva";

function periode(cle: string, fin: string, declaree: boolean): PeriodeTva {
  return { cle, debut: fin, fin, echeance: null, lignes: [], due_cts: 0, credit_cts: 0, declaree, a_traiter: 0 };
}

test("les périodes se lisent en français", () => {
  assert.equal(nomPeriode("2026-03"), "mars 2026");
  assert.equal(nomPeriode("2026-T1"), "1er trimestre 2026");
  assert.equal(nomPeriode("2026-T3"), "3e trimestre 2026");
});

test("on montre d'abord la plus ancienne période terminée à déclarer", () => {
  const periodes = [
    periode("2026-01", "2026-01-31", true),
    periode("2026-02", "2026-02-28", false),
    periode("2026-03", "2026-03-31", false),
  ];
  assert.equal(periodeParDefaut(periodes, "2026-04-02")?.cle, "2026-02");
  assert.equal(periodeParDefaut([periodes[0]], "2026-04-02")?.cle, "2026-01");
  assert.equal(periodeParDefaut([], "2026-04-02"), null);
});

test("le gestionnaire lit la période et l'échéance, sans montant", () => {
  assert.equal(phraseTvaADeclarer(null, null), null);
  assert.equal(
    phraseTvaADeclarer("2026-10", "2026-11-19"),
    "TVA de octobre 2026 à déclarer avant le 19/11/2026.",
  );
});
