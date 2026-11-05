import { expect, test, type Page, type Route } from "@playwright/test";

/** AXE-685 : une lecture ratée n'est pas une liste vide. L'ajout qui suit
 * ne doit pas envoyer de PUT, et l'erreur reste visible. */

function jeton(claims: Record<string, unknown>): string {
  const coder = (valeur: object) => Buffer.from(JSON.stringify(valeur)).toString("base64");
  return `${coder({ alg: "none", typ: "JWT" })}.${coder(claims)}.signature`;
}

const ASSURANCE = {
  nature: "fnp",
  compte_charge: "616",
  centimes: 15_000,
  libelle: "Assurance",
};

type Etat = {
  provisions: "echec" | "vide" | "assurance";
  cloture: "echec" | "pas-termine";
  bulletins: "echec" | "vide";
  dividendes: "echec" | "absent";
  notifications: "echec" | "vide";
  paie: boolean;
};

function dossier(paie: boolean) {
  return {
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
    nb_a_trancher: 0,
    statut_invitation: "actif",
    mode_acces_bancaire: "gestionnaire",
    peut_connecter_sa_banque: false,
    cloture_faite: false,
    greffe_inpi_signe: false,
    guide_greffe: { depose: false, lien: "", lignes: [], pieces: [] },
    declaration_resultat: "2065",
    depot_greffe: false,
    alerte_regime: null,
    regimes_a_venir: [],
    alerte_tva: null,
    paie_par_bulletin: paie,
    forme_juridique: "EURL",
    regime_libelle: "Impôt sur les sociétés",
  };
}

const AFFECTATION = {
  applicable: false,
  raison: "Rien à affecter.",
  annee_exercice: null,
  resultat_cts: 0,
  reserve_legale_cts: 0,
  distribuable_cts: 0,
  disponible_cts: 0,
  scenarios: [],
  avertissements: [],
};

function echec(detail: string) {
  return { status: 500, json: { detail } };
}

async function repondre(route: Route, etat: Etat, puts: unknown[]) {
  const url = route.request().url();
  const methode = route.request().method();
  if (url.endsWith("/dossiers/DEMO_sophie") && methode === "GET") {
    await route.fulfill({ json: dossier(etat.paie) });
    return;
  }
  if (url.includes("/provisions-cloture")) {
    if (methode === "PUT") {
      const corps = route.request().postDataJSON();
      puts.push(corps);
      await route.fulfill({ json: corps });
      return;
    }
    if (etat.provisions === "echec") {
      await route.fulfill(echec("lecture des provisions impossible"));
      return;
    }
    await route.fulfill({
      json: { lignes: etat.provisions === "assurance" ? [ASSURANCE] : [] },
    });
    return;
  }
  if (url.includes("/cloture-exercice") && methode === "GET") {
    if (etat.cloture === "echec") {
      await route.fulfill(echec("lecture de la clôture impossible"));
      return;
    }
    await route.fulfill({
      json: {
        possible: false,
        raison: "L'exercice n'est pas terminé.",
        exercice_debut: "2025-01-01",
        exercice_fin: "2025-12-31",
        nouvel_exercice_debut: null,
        ecritures: [],
        changements: [],
        attestation: null,
      },
    });
    return;
  }
  if (url.includes("/bulletins")) {
    if (methode === "POST") {
      await route.fulfill({ status: 500, json: { detail: "ne devrait pas partir" } });
      return;
    }
    if (etat.bulletins === "echec") {
      await route.fulfill(echec("lecture des bulletins impossible"));
      return;
    }
    await route.fulfill({ json: [] });
    return;
  }
  if (url.includes("/dividendes") && methode === "GET") {
    if (etat.dividendes === "echec") {
      await route.fulfill(echec("lecture des dividendes impossible"));
      return;
    }
    await route.fulfill({ json: { applicable: false, raison: "Pas de dividendes." } });
    return;
  }
  if (url.includes("/notifications") && methode === "GET") {
    if (etat.notifications === "echec") {
      await route.fulfill(echec("lecture des notifications impossible"));
      return;
    }
    await route.fulfill({ json: [] });
    return;
  }
  if (url.includes("/affectation") && methode === "GET") {
    await route.fulfill({ json: AFFECTATION });
    return;
  }
  await route.fulfill({ json: [] });
}

async function ouvrir(page: Page, chemin: string, etat: Etat, puts: unknown[]) {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  await page.addInitScript(
    ([cle, valeur]) => window.localStorage.setItem(cle, valeur),
    [
      "axelcompta_session_chauffeur",
      JSON.stringify({
        accessToken: jeton({ exp, app_metadata: { dossier_id: "DEMO_sophie" } }),
        refreshToken: "rafraichissement",
        dossierId: "DEMO_sophie",
        email: "sophie@example.com",
      }),
    ] as const,
  );
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
    await repondre(route, etat, puts);
  });
  await page.goto(chemin);
}

function zoneProvisions(page: Page) {
  return page.locator("section").filter({
    has: page.getByText("Une charge de cet exercice n'est pas encore passée ?"),
  });
}

async function masquerIndicateurDev(page: Page) {
  await page.evaluate(() => {
    document.querySelectorAll("nextjs-portal").forEach((noeud) => noeud.remove());
  });
}

test.use({ viewport: { width: 375, height: 812 } });

test("un GET en échec puis un ajout n'envoie aucun PUT", async ({ page }) => {
  const puts: unknown[] = [];
  const etat: Etat = {
    provisions: "echec",
    cloture: "pas-termine",
    bulletins: "vide",
    dividendes: "absent",
    notifications: "vide",
    paie: false,
  };
  await ouvrir(page, "/chauffeur/DEMO_sophie/exercice", etat, puts);
  const zone = zoneProvisions(page);
  await expect(zone.getByRole("alert")).toHaveText("Lecture des provisions impossible.");
  const reessayer = zone.getByRole("button", { name: "Réessayer" });
  await expect(reessayer).toBeVisible();
  expect((await reessayer.boundingBox())!.height).toBeGreaterThanOrEqual(44);

  await zone.getByLabel("Montant").fill("120");
  await zone.getByLabel("Libellé").fill("Honoraires de décembre");
  const ajouter = zone.getByRole("button", { name: "Ajouter" });
  await expect(ajouter).toBeDisabled();

  const putParti = page
    .waitForRequest(
      (demande) => demande.url().includes("/provisions-cloture") && demande.method() === "PUT",
      { timeout: 1_000 },
    )
    .then(
      () => true,
      () => false,
    );
  await ajouter.click({ force: true });
  expect(await putParti).toBe(false);
  expect(puts).toEqual([]);

  await masquerIndicateurDev(page);
  await page.screenshot({
    path: "/opt/cursor/artifacts/provisions-lecture-echouee.png",
    fullPage: true,
  });
});

test("une liste vide reste saisissable", async ({ page }) => {
  const puts: unknown[] = [];
  await ouvrir(
    page,
    "/chauffeur/DEMO_sophie/exercice",
    {
      provisions: "vide",
      cloture: "pas-termine",
      bulletins: "vide",
      dividendes: "absent",
      notifications: "vide",
      paie: false,
    },
    puts,
  );
  const zone = zoneProvisions(page);
  await expect(zone.getByRole("alert")).toHaveCount(0);
  const ajouter = zone.getByRole("button", { name: "Ajouter" });
  await expect(ajouter).toBeEnabled();
  await zone.getByLabel("Montant").fill("120");
  await zone.getByLabel("Libellé").fill("Honoraires de décembre");
  const [requete] = await Promise.all([
    page.waitForRequest(
      (demande) => demande.url().includes("/provisions-cloture") && demande.method() === "PUT",
    ),
    ajouter.click(),
  ]);
  expect(requete.postDataJSON()).toEqual({
    lignes: [
      {
        nature: "fnp",
        compte_charge: "6226",
        centimes: 12_000,
        libelle: "Honoraires de décembre",
      },
    ],
  });
});

test("après une relecture, l'ajout conserve les provisions déjà saisies", async ({ page }) => {
  const puts: unknown[] = [];
  const etat: Etat = {
    provisions: "echec",
    cloture: "pas-termine",
    bulletins: "vide",
    dividendes: "absent",
    notifications: "vide",
    paie: false,
  };
  await ouvrir(page, "/chauffeur/DEMO_sophie/exercice", etat, puts);
  const zone = zoneProvisions(page);
  await expect(zone.getByRole("alert")).toHaveText("Lecture des provisions impossible.");
  etat.provisions = "assurance";
  await zone.getByRole("button", { name: "Réessayer" }).click();
  await expect(zone.getByRole("button", { name: "Retirer Assurance" })).toBeVisible();
  await expect(zone.getByRole("alert")).toHaveCount(0);
  await zone.getByLabel("Montant").fill("80");
  await zone.getByLabel("Libellé").fill("Carburant manquant");
  const [requete] = await Promise.all([
    page.waitForRequest(
      (demande) => demande.url().includes("/provisions-cloture") && demande.method() === "PUT",
    ),
    zone.getByRole("button", { name: "Ajouter" }).click(),
  ]);
  expect(requete.postDataJSON()).toEqual({
    lignes: [
      ASSURANCE,
      {
        nature: "fnp",
        compte_charge: "6226",
        centimes: 8_000,
        libelle: "Carburant manquant",
      },
    ],
  });
});

test("retirer une provision enregistre la liste sans elle", async ({ page }) => {
  const puts: unknown[] = [];
  await ouvrir(
    page,
    "/chauffeur/DEMO_sophie/exercice",
    {
      provisions: "assurance",
      cloture: "pas-termine",
      bulletins: "vide",
      dividendes: "absent",
      notifications: "vide",
      paie: false,
    },
    puts,
  );
  const retirer = page.getByRole("button", { name: "Retirer Assurance" });
  await expect(retirer).toBeVisible();
  expect((await retirer.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await masquerIndicateurDev(page);
  await retirer.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "/opt/cursor/artifacts/provisions-retirer.png",
    fullPage: false,
  });
  const [requete] = await Promise.all([
    page.waitForRequest(
      (demande) => demande.url().includes("/provisions-cloture") && demande.method() === "PUT",
    ),
    retirer.click(),
  ]);
  expect(requete.postDataJSON()).toEqual({ lignes: [] });
  await expect(page.getByRole("button", { name: "Retirer Assurance" })).toHaveCount(0);
  await expect(page.getByText("Facture pas encore reçue — Assurance")).toHaveCount(0);
});

test("dividendes, paie, clôture et cloche montrent l'échec de lecture", async ({ page }) => {
  const puts: unknown[] = [];
  await ouvrir(
    page,
    "/chauffeur/DEMO_sophie/exercice",
    {
      provisions: "echec",
      cloture: "echec",
      bulletins: "echec",
      dividendes: "echec",
      notifications: "echec",
      paie: true,
    },
    puts,
  );

  await expect(page.getByRole("heading", { name: "Clôture de l'exercice" })).toBeVisible();
  await expect(page.getByText("Lecture de la clôture impossible.")).toBeVisible();

  const paie = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Ma paie" }),
  });
  await expect(paie.getByText("Lecture des bulletins impossible.")).toBeVisible();
  await paie.getByLabel("Mois du bulletin").fill("2026-01");
  await paie.getByLabel("Salaire avant retenues").fill("2000");
  const enregistrer = paie.getByRole("button", { name: "Enregistrer le bulletin" });
  await expect(enregistrer).toBeDisabled();
  const postParti = page
    .waitForRequest(
      (demande) => demande.url().includes("/bulletins") && demande.method() === "POST",
      { timeout: 1_000 },
    )
    .then(
      () => true,
      () => false,
    );
  await enregistrer.click({ force: true });
  expect(await postParti).toBe(false);
  expect(puts).toEqual([]);

  await masquerIndicateurDev(page);
  await page.screenshot({
    path: "/opt/cursor/artifacts/exercice-lectures-echouees.png",
    fullPage: true,
  });

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByRole("button", { name: "Notifications indisponibles" }).click();
  const panneau = page.getByRole("dialog", { name: "Notifications" });
  await expect(panneau.getByText("Lecture des notifications impossible.")).toBeVisible();
  await expect(panneau.getByText("Aucune notification.")).toHaveCount(0);
  await expect(panneau.getByRole("button", { name: "Réessayer" })).toBeVisible();
  await page.screenshot({
    path: "/opt/cursor/artifacts/cloche-lecture-echouee.png",
    fullPage: false,
  });

  await page.goto("/chauffeur/DEMO_sophie/resultat");
  await expect(page.getByRole("heading", { name: "Mes dividendes" })).toBeVisible();
  await expect(page.getByText("Lecture des dividendes impossible.")).toBeVisible();
  await expect(page.getByRole("button", { name: "J'ai versé mes dividendes" })).toHaveCount(0);
  await masquerIndicateurDev(page);
  await page.screenshot({
    path: "/opt/cursor/artifacts/dividendes-lecture-echouee.png",
    fullPage: true,
  });
});
