# 17 — Plan de démo produit

> Plan court de la démo : but, contenu, périmètre, lancement, risques. Il ne
> tient pas de journal. Ce qui a été fait, jour par jour, du 06/09 au 25/09,
> est archivé tel quel dans
> [archive/17-plan-demo-journal-2026-09.md](archive/17-plan-demo-journal-2026-09.md).
> Les renvois « doc 17 §9 », « §12 », « §14 à 16 » du code et des autres docs
> pointent vers cette archive. L'état d'avancement du projet est dans le
> [doc 12](12-roadmap-todo.md). Dernière mise à jour : 2026-09-27.

## 1. But

Faire tourner le produit entier sur trois dossiers chauffeur fabriqués à la
main mais crédibles : l'écran gestionnaire (PC), l'écran chauffeur (mobile)
et le vrai moteur de calcul derrière (réconciliation, catégorisation,
écritures, clôture, liasse). Il ne s'agit pas de conformité DGFiP. Il faut
pouvoir dire « ça marche, il reste à affiner », pas « c'est un jouet ». Les
mots de Louis, le 06/09 : *« la démo est un peu un produit final mais sans
la précision de tout, donc tout marche mais le résultat a le droit d'être
un poil foireux »*.

Principe : le parcours d'abord, le moteur dessous. Un écran qui existe est
branché sur le vrai calcul, jamais sur des données figées.

## 2. Les trois dossiers

| Dossier | Profil | Ce qu'il montre |
|---|---|---|
| **Karim** | SASU à l'IS, TVA taux réduit 10 %, Uber | Le cas nominal : aucune fausse alerte |
| **Sophie** | EURL à l'IS, TVA, Uber et Bolt, une dépense Zara ambiguë | L'autoliquidation Bolt, et une dépense que le chauffeur tranche lui-même (471 vers 455) |
| **Yanis** | Franchise de TVA, Uber, véhicule en LOA | Le régime franchise, le loyer passé en 613 |

**Dossiers réels (depuis le 2026-09-26/27)** : un dossier `DIGI_<nr>` par
contact Digifactory, compte fictif `demo-digi-<nr>@axelcompta.fr`
(`scripts/ajouter_chauffeurs_digifactory.py`). Leurs transactions viennent de
l'API, jamais du dépôt. Ce ne sont pas des chauffeurs VTC : ils montrent le
produit sur des données bancaires vraies, pas le parcours type. La remise à
neuf (§6) ne les touche pas.

Exercice déclaré : 06/01/2025 au 31/12/2025. Identités légales fictives
(SIREN à clé valide, non attribués). Génération :
`ingestion/providers/chauffeurs_demo.py`, amorçage : `demo_seed.py`. Le
détail des écritures attendues par profil est dans l'archive (§4).

## 3. Ce que la démo montre

**Le produit qui apprend, sur un dossier réel (depuis le 2026-09-27)** :
se connecter en `demo-digi-4952@axelcompta.fr` (mot de passe commun des
chauffeurs de démo). Ses 337 opérations à trancher sont surtout des
salaires versés, que le modèle ne connaît pas : « pas de proposition
automatique », et quelques propositions du modèle affichées avec leur
confiance. Classer une seule ligne « SOLDE SALAIRE » en « Salaire d'un
salarié » (sous « Autre chose ») : la liste se relit, et un encart annonce
que 295 opérations ressemblent à ce classement, liste consultable, puis
« Tout classer » en un geste. Vérifié en simulation sur les vraies données
le 2026-09-27 : les 295 sont exactement les lignes « SOLDE SALAIRE » et
« ACOMPTE SALAIRE ». Pour rejouer, cocher « Dépenses tranchées des
dossiers Digifactory » dans le menu Démo (§6).

**Gestionnaire (web)** : la liste des entreprises du portefeuille, deux
frises réglementaires par entreprise (l'exercice en cours, et celui
d'avant qu'on traite au début de l'année), les invitations individuelles ou
en masse, les règles de rappel, l'équipe et ses rôles. Le gestionnaire ne
voit jamais le détail d'un dossier (doc 19 §2.1).

**Chauffeur (mobile)** : ses transactions catégorisées, les questions à
trancher, la photo de justificatif, la clôture, la liasse fiscale et la
signature du dépôt greffe (simulée). Le parcours est en refonte UX
(retour de Louis du 22/09 : « c'est pas une app, c'est un flow continuel
vers le bas »).

**Documents produits** : liasse fiscale complète sur les formulaires
officiels 2026 (2065, 2065-bis, 2033-A à G), FEC au format légal, grand livre
et balance en PDF, dossier de dépôt greffe/INPI.

## 4. Hors périmètre, assumé

- OCR des justificatifs : la photo s'attache, son contenu n'est pas lu.
- Détection d'anomalies statistique : la dépense de Sophie est écrite à la
  main, pas détectée.
- Signature qualifiée : simulateur, aucun prestataire (ADR-004).
- L'étage ML sur les trois profils : Karim, Sophie et Yanis sont entièrement
  catégorisés par les règles. Le ML (modèle v2, abstention sous 0,5,
  propositions apprises des décisions) ne se voit que sur les dossiers
  `DIGI_`.
- Envoi réel des rappels (SMS, e-mail, appel) : les règles s'enregistrent,
  rien ne part. La page Intégrations annonce ce qui est prévu.
- Matrice complète statut × pack : seulement les trois profils.
- Inscription libre, synchro API gestionnaire, application native.
- Expert-comptable : aucun pour la démo (décision de Louis, 23/09). La table
  comptes → rubriques 2033 suit la notice, sans relecture professionnelle.

## 5. Lancer la démo

Commandes détaillées : [backend/README.md](../backend/README.md), section
« Lancer l'API de démo ». En bref, base Supabase déjà migrée et amorcée :

```bash
# backend/
set -a && . ../.env && set +a
.venv/bin/uvicorn axelcompta.api.app:app --port 8000
# frontend/
npm run dev
```

Pièges connus :
- Le CORS n'accepte que `http://localhost:3000`. Un `next dev` qui traîne
  d'une session précédente fait démarrer le nouveau sur 3001, et toutes les
  actions échouent. Vérifier que le port 3000 est libre avant de lancer.
- `DATABASE_URL_WEB` doit être défini (`set -a && . ../.env && set +a`
  avant `uvicorn`), sinon l'API démarre mais chaque requête répond 500
  (elle ne retombe jamais sur la connexion propriétaire).
- Comptes : trois chauffeurs (`scripts/creer_comptes_demo_chauffeurs.py`)
  et deux gestionnaires, persistants dans Supabase Auth. Mot de passe
  commun des trois chauffeurs : `DemoChauffeur2026!` (`frontend/README.md`).
  Les mots de passe gestionnaire restent hors du repo.

## 6. Remettre la démo à neuf

**Fait le 2026-09-25 (PR #17)** : menu Démo dans la barre latérale du
gestionnaire, remise à neuf à la carte (dépenses tranchées, frise,
justificatifs, rappels, notifications). Les décisions et les signatures
sont verrouillées en base (triggers `*_immuables`, doc 12 §1.3) : le menu
passe par la connexion propriétaire (`DATABASE_URL`) et suspend ces
verrous le temps d'une seule transaction, annulée en entier au moindre
échec. Seuls le portefeuille de démo et un admin y ont accès, et le grand
livre, le journal d'audit et les comptes Supabase ne sont jamais touchés
(`demo_admin.py`).

Les dossiers `DIGI_` échappent à toutes les parties, sauf une qui leur est
propre depuis le 2026-09-27 : « Dépenses tranchées des dossiers
Digifactory » efface leurs seules décisions, pour rejouer le « tout
classer » du §3. Leurs opérations ne sont jamais touchées. Rien n'est coché
par défaut.

## 7. Risques

| Risque | Parade |
|---|---|
| Une répétition abîme l'état de départ | §6. Tant que la remise à neuf n'existe pas, répéter sur Karim ou Yanis et garder Sophie intacte |
| Aucune répétition complète depuis le 11/09 (base, auth et écran gestionnaire ont changé depuis) | Une répétition entière en navigateur avant la vraie |
| Le parcours chauffeur n'est pas prêt | Refonte en cours ; à défaut, montrer Sophie seulement |
| Supabase Auth gardé en V1 (ADR-003, mise à jour du 2026-09-08) | En sortir plus tard est une vraie réécriture de l'auth, pas un `pg_dump` : le déclencheur CLOUD Act de l'ADR couvre aussi l'auth |
| Digifactory tombe ou change | La démo tourne sur les fixtures, jamais sur l'API réelle |

## 8. Tests de référence

- Karim : le golden test Uber (doc 13 §5.3) est son mois type.
- Sophie : la dépense reste au 471 tant que personne ne la tranche, puis
  passe au 455 par l'API (`test_trancher_en_usage_personnel_reclasse_vers_le_compte_455`).
- Yanis : balance équilibrée sans TVA collectée
  (`tests/ingestion/test_ecritures_settlement.py`).
