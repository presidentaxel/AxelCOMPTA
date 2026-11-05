import { expect, test, type Page, type Route } from "@playwright/test";

/** Jeton non signé : le navigateur ne vérifie que la date d'expiration.
 * La signature est l'affaire de l'API, couverte par les tests Python. */
function jeton(claims: Record<string, unknown>): string {
  // `atob` (session.ts) exige le remplissage « = » ; base64url le retire.
  const coder = (valeur: object) => Buffer.from(JSON.stringify(valeur)).toString("base64");
  return `${coder({ alg: "none", typ: "JWT" })}.${coder(claims)}.signature`;
}

function agregat(id: string, nom: string) {
  return {
    dossier_id: id,
    nom,
    tva_recettes_regime: "franchise",
    plateformes: [],
    exercice_debut: "2025-01-01",
    exercice_fin: "2025-12-31",
    ca_ht_cts: 100_00,
    charges_cts: 40_00,
    resultat_cts: 60_00,
    statut_invitation: "actif",
    mode_acces_bancaire: "gestionnaire",
    forme_juridique: "EURL",
    regime_imposition: "IS",
    regime_tva: "franchise",
    annee_courante: 2026,
    etape_courante: "Compte",
    annee_precedente: 2025,
    etape_precedente: "Compte",
    alerte_regime: null,
    alerte_tva: null,
  };
}

function dossierExercice(
  id: string,
  nom: string,
  extra: { nb_a_trancher?: number; cloture_faite?: boolean } = {},
) {
  return {
    ...DOSSIER_SOPHIE,
    dossier_id: id,
    nom,
    nb_a_trancher: extra.nb_a_trancher ?? DOSSIER_SOPHIE.nb_a_trancher,
    cloture_faite: extra.cloture_faite ?? DOSSIER_SOPHIE.cloture_faite,
  };
}

const DOSSIER_SOPHIE = {
  dossier_id: "DEMO_sophie",
  nom: "Sophie Martin",
  tva_recettes_regime: "franchise",
  plateformes: [],
  exercice_debut: "2025-01-01",
  exercice_fin: "2025-12-31",
  ca_ht_cts: 100_00,
  charges_cts: 40_00,
  resultat_cts: 60_00,
  tresorerie_cts: 20_00,
  tva_a_payer_cts: 0,
  nb_transactions: 1,
  nb_a_trancher: 1,
  statut_invitation: "actif",
  mode_acces_bancaire: "gestionnaire",
  peut_connecter_sa_banque: false,
  cloture_faite: false,
  greffe_inpi_signe: false,
  guide_greffe: { depose: false, lien: "", lignes: [], pieces: [] },
  declaration_resultat: "2065",
  depot_greffe: true,
  alerte_regime: null,
  regimes_a_venir: [],
  alerte_tva: null,
  paie_par_bulletin: false,
  forme_juridique: "EURL",
  regime_libelle: "Impôt sur les sociétés",
};

const ZARA = {
  ecriture_id: "zara-1",
  date: "2025-06-01",
  libelle: "ZARA",
  montant_cts: -4_200,
  compte: "471",
  statut: "à trancher",
  a_justificatif: true,
  proposition: null,
  origine_proposition: null,
  confiance_proposition: null,
};

type TransactionDemo = Omit<
  typeof ZARA,
  "statut" | "compte" | "proposition" | "origine_proposition" | "confiance_proposition"
> & {
  statut: "à trancher" | "validé";
  compte: string;
  proposition: string | null;
  origine_proposition: string | null;
  confiance_proposition: number | null;
};

/** Après une décision, la relecture des opérations renvoie la ligne déjà
 * tranchée : l'écran recharge la liste, il ne garde pas seulement la réponse
 * du POST. */
function bouchon(operations: TransactionDemo[]) {
  return async (route: Route) => {
    const url = route.request().url();
    const methode = route.request().method();
    if (url.endsWith("/dossiers") && methode === "GET") {
      await route.fulfill({
        json: [agregat("DEMO_karim", "Karim"), agregat("DEMO_sophie", "Sophie"), agregat("DEMO_yanis", "Yanis")],
      });
      return;
    }
    if (url.endsWith("/dossiers/DEMO_sophie") && methode === "GET") {
      await route.fulfill({ json: DOSSIER_SOPHIE });
      return;
    }
    if (url.endsWith("/dossiers/DEMO_pret") && methode === "GET") {
      await route.fulfill({ json: dossierExercice("DEMO_pret", "Prêt Clos", { nb_a_trancher: 0 }) });
      return;
    }
    if (url.endsWith("/dossiers/DEMO_clos") && methode === "GET") {
      await route.fulfill({
        json: dossierExercice("DEMO_clos", "Déjà clos", { nb_a_trancher: 0, cloture_faite: true }),
      });
      return;
    }
    if (url.endsWith("/transactions") && methode === "GET") {
      await route.fulfill({ json: operations });
      return;
    }
    if (url.endsWith("/decision") && methode === "POST") {
      const ecritureId = url.split("/").at(-2);
      const ligne = operations.find((operation) => operation.ecriture_id === ecritureId);
      const validee: TransactionDemo = ligne
        ? { ...ligne, statut: "validé", compte: "455" }
        : { ...ZARA, statut: "validé", compte: "455" };
      const index = ligne ? operations.index(ligne) : 0;
      if (ligne) operations.splice(index, 1, validee);
      else operations.splice(0, operations.length, validee);
      await route.fulfill({ json: validee });
      return;
    }
    if (url.includes("/cloture-exercice") && methode === "GET") {
      if (url.includes("DEMO_clos")) {
        await route.fulfill({
          json: {
            possible: false,
            raison: "l'exercice se termine le 31/12/2026, il n'est pas terminé",
            exercice_debut: "2026-01-01",
            exercice_fin: "2026-12-31",
            nouvel_exercice_debut: null,
            ecritures: [],
            changements: [],
            attestation: null,
          },
        });
        return;
      }
      await route.fulfill({
        json: {
          possible: true,
          raison: null,
          exercice_debut: "2025-01-01",
          exercice_fin: "2025-12-31",
          nouvel_exercice_debut: "2026-01-01",
          ecritures: ["Liquidation de la TVA de l'exercice"],
          changements: [],
          attestation: "J'atteste la clôture.",
        },
      });
      return;
    }
    if (url.includes("/provisions-cloture") && methode === "GET") {
      await route.fulfill({ json: { lignes: [] } });
      return;
    }
    if (url.includes("/provisions-cloture") && methode === "PUT") {
      await route.fulfill({ json: route.request().postDataJSON() });
      return;
    }
    if (url.includes("/affectation")) {
      await route.fulfill({
        json: {
          applicable: false,
          raison: url.includes("DEMO_clos") ? "Résultat 2025 affecté." : null,
          annee_exercice: 2025,
        },
      });
      return;
    }
    if (url.includes("/dividendes") && methode === "GET") {
      await route.fulfill({
        json: {
          applicable: url.includes("DEMO_clos"),
          raison: null,
          annee_exercice: 2025,
          declare: false,
          brut_cts: 10_000,
        },
      });
      return;
    }
    if (url.includes("connexions-bancaires")) {
      await route.fulfill({
        json: {
          relance_portefeuille: "auto",
          compteurs: { actif: 0, a_renouveler: 0, expire: 0, jamais_connecte: 0 },
          a_reconnecter: 0,
          dossiers: [],
        },
      });
      return;
    }
    await route.fulfill({ json: [] });
  };
}

async function intercepterApi(page: Page, transactions: TransactionDemo[] = [{ ...ZARA }]) {
  const operations = transactions.map((transaction) => ({ ...transaction }));
  const repondre = bouchon(operations);
  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.includes(":3000") || url.startsWith("data:")) {
      await route.continue();
      return;
    }
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-headers": "*",
          "access-control-allow-methods": "*",
        },
      });
      return;
    }
    await repondre(route);
  });
}

async function session(page: Page, cle: string, corps: object) {
  await page.addInitScript(
    ([storageKey, valeur]) => window.localStorage.setItem(storageKey, valeur),
    [cle, JSON.stringify(corps)] as const,
  );
}

test("le gestionnaire voit les trois dossiers", async ({ page }) => {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  await session(page, "axelcompta_session_gestionnaire", {
    accessToken: jeton({ exp, app_metadata: { tenant_id: "TENANT_DEMO" } }),
    refreshToken: "rafraichissement",
    tenantId: "TENANT_DEMO",
    email: "gestionnaire@example.com",
  });
  await intercepterApi(page);
  await page.goto("/portefeuille");
  await expect(page.getByRole("heading", { name: "Entreprises" })).toBeVisible();
  await expect(page.getByText("Karim")).toBeVisible();
  await expect(page.getByText("Sophie")).toBeVisible();
  await expect(page.getByText("Yanis")).toBeVisible();
});

function sessionChauffeur(page: Page, dossierId: string) {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  return session(page, "axelcompta_session_chauffeur", {
    accessToken: jeton({ exp, app_metadata: { dossier_id: dossierId } }),
    refreshToken: "rafraichissement",
    dossierId,
    email: "sophie@example.com",
  });
}

async function ordonnee(page: Page, nom: string) {
  const boite = await page.getByText(nom, { exact: true }).first().boundingBox();
  expect(boite).not.toBeNull();
  return boite!.y;
}

test("Sophie saisit une facture pas encore reçue", async ({ page }) => {
  await sessionChauffeur(page, "DEMO_sophie");
  await intercepterApi(page);
  await page.goto("/chauffeur/DEMO_sophie/exercice");
  await expect(page.getByRole("heading", { name: "Exercice", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Récupérer la liasse" })).toBeDisabled();
  await expect(page.getByText("Chaque opération").first()).toBeVisible();
  await expect(page.getByText("Grand livre")).toHaveCount(0);
  await expect(page.getByText("Formulaire 2065")).toHaveCount(0);
  const raison = page.getByText("Il reste 1 opération à traiter.");
  await expect(raison).toHaveCount(4);
  await expect(page.getByRole("button", { name: "Signer" })).toBeDisabled();
  await expect(page.getByRole("link", { name: /Mes dividendes/ })).toHaveCount(0);
  const yProvisions = await ordonnee(page, "Une charge de cet exercice n'est pas encore passée ?");
  const yCloture = await ordonnee(page, "Clôture de l'exercice");
  const yDocuments = await ordonnee(page, "Pour les impôts");
  const yGreffe = await ordonnee(page, "Dépôt des comptes");
  const yAffectation = await ordonnee(page, "Affectation du résultat");
  expect(yProvisions).toBeLessThan(yCloture);
  expect(yCloture).toBeLessThan(yDocuments);
  expect(yDocuments).toBeLessThan(yGreffe);
  expect(yGreffe).toBeLessThan(yAffectation);
  await page.getByLabel("De quoi s'agit-il ?").selectOption({ label: "Honoraires" });
  await page.getByLabel("Montant").fill("80");
  await page.getByLabel("Libellé").fill("honoraire de décembre");
  await page.getByRole("button", { name: "Ajouter" }).click();
  await expect(page.getByText("Facture pas encore reçue — honoraire de décembre")).toBeVisible();
  await expect(page.getByText("622")).toHaveCount(0);
});

test("Sophie lit une proposition sans code ni pourcentage", async ({ page }) => {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  await session(page, "axelcompta_session_chauffeur", {
    accessToken: jeton({ exp, app_metadata: { dossier_id: "DEMO_sophie" } }),
    refreshToken: "rafraichissement",
    dossierId: "DEMO_sophie",
    email: "sophie@example.com",
  });
  await intercepterApi(page, [
    {
      ...ZARA,
      ecriture_id: "loyer-1",
      libelle: "SCI DUPONT (loyers_locations)",
      montant_cts: -90_000,
      proposition: "loyers_locations",
      origine_proposition: "modele",
      confiance_proposition: 0.87,
    },
    {
      ...ZARA,
      ecriture_id: "entree-1",
      libelle: "UBER BV",
      date: "2025-06-02",
      montant_cts: 12_000,
      proposition: "non_categorise_a_verifier",
      origine_proposition: "regle",
      confiance_proposition: 0.2,
    },
  ]);
  await page.goto("/chauffeur/DEMO_sophie");
  await expect(page.getByText("Proposition : Loyer")).toBeVisible();
  await expect(page.getByText("modèle")).toHaveCount(0);
  await expect(page.getByText("87 %")).toHaveCount(0);
  await expect(page.getByText("loyers locations")).toHaveCount(0);
  await expect(page.getByText("À quoi correspond cette entrée ?")).toBeVisible();
  await expect(page.getByText("non categorise a verifier")).toHaveCount(0);
  await expect(page.getByText("À classer").first()).toBeVisible();
});

test("la clôture confirme sans recharger et ouvre la liasse", async ({ page }) => {
  await sessionChauffeur(page, "DEMO_pret");
  await intercepterApi(page);
  await page.goto("/chauffeur/DEMO_pret/exercice");
  await expect(
    page.getByText("Les comptes ne sont pas clôturés. La liasse définitive sera disponible"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Récupérer la liasse" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Signer" })).toBeDisabled();
  await page.evaluate(() => {
    (window as unknown as { __vu: number }).__vu = 1;
  });
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Valider la clôture" }).click();
  await expect(page.getByRole("status")).toHaveText("Exercice clos. Les documents sont disponibles.");
  await expect(page.getByText("Les comptes sont clôturés.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Récupérer la liasse" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Signer" })).toBeEnabled();
  expect(await page.evaluate(() => (window as unknown as { __vu?: number }).__vu)).toBe(1);
});

test("Mes dividendes reste accessible une fois l'affectation décidée", async ({ page }) => {
  await sessionChauffeur(page, "DEMO_clos");
  await intercepterApi(page);
  await page.goto("/chauffeur/DEMO_clos/exercice");
  await expect(page.getByRole("link", { name: "Mes dividendes 2025 →" })).toBeVisible();
  await expect(page.getByText("Les comptes sont clôturés.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Récupérer la liasse" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Valider la clôture" })).toHaveCount(0);
});

test("Sophie tranche une dépense et l'écran suit", async ({ page }) => {
  await sessionChauffeur(page, "DEMO_sophie");
  await intercepterApi(page);
  await page.goto("/chauffeur/DEMO_sophie");
  await expect(page.getByRole("heading", { name: "Sophie Martin" })).toBeVisible();
  await expect(page.getByText("ZARA")).toBeVisible();
  await page.getByRole("button", { name: "Personnelle" }).click();
  await expect(page.getByText("Tout est à jour.")).toBeVisible();
});
