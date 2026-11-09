import assert from "node:assert/strict";
import test from "node:test";

import { libelleMoyenPaiement } from "./moyens-paiement";

test("libellé du moyen de paiement", () => {
  assert.equal(libelleMoyenPaiement("card"), "Payé par carte");
  assert.equal(libelleMoyenPaiement("transfer"), "Virement");
  assert.equal(libelleMoyenPaiement("crypto"), "crypto");
  assert.equal(libelleMoyenPaiement(null), null);
});
