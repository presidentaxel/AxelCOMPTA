import assert from "node:assert/strict";
import test from "node:test";

import { estVirementInterne, horsVirementsInternes, phraseVirementsInternes } from "./virements-internes";

test("AXE-930 : les virements internes ne comptent pas chez le chauffeur", () => {
  const operations = [
    { compte: "580", montant_cts: -5_000 },
    { compte: "580", montant_cts: 5_000 },
    { compte: "6061", montant_cts: -3_000 },
  ];
  const { gardees, internes } = horsVirementsInternes(operations);
  assert.deepEqual(gardees, [{ compte: "6061", montant_cts: -3_000 }]);
  assert.equal(internes, 2);
  assert.equal(estVirementInterne({ compte: "580" }), true);
  assert.match(phraseVirementsInternes(2) ?? "", /2 virements entre vos comptes/);
  assert.equal(phraseVirementsInternes(0), null);
});
