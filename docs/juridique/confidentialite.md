# Confidentialité et sous-traitance des données

> Version du 2026-11-10. Projet, à relire par un juriste (AXE-813). Écrit à
> partir des services réellement branchés dans le code le 2026-11-10.

## 1. Qui fait quoi

- Pour les données d'un dossier (opérations, justificatifs, comptes),
  l'**entreprise cliente** (le gestionnaire de portefeuille, ou l'entreprise
  qui suit sa propre comptabilité) est **responsable de traitement**.
  **AXEL PROJECT** est son **sous-traitant** au sens de l'article 28 du RGPD.
- Pour les comptes utilisateurs (e-mail de connexion, journal des accès),
  AXEL PROJECT est responsable de traitement.

Contact : contact@axelproject.fr.
[À COMPLÉTER : délégué à la protection des données, s'il est désigné.]

## 2. Les données traitées

- Opérations bancaires des comptes professionnels : date, libellé, montant,
  compte, moyen de paiement, catégorie donnée par la banque.
- Justificatifs (photos de tickets et de factures) déposés par le dirigeant.
- Écritures comptables, FEC, liasses fiscales, déclarations de TVA préparées.
- Identité de l'entreprise, de son dirigeant et de ses associés (nom,
  naissance, adresse, titres détenus), saisie par le dirigeant.
- Comptes utilisateurs : e-mail, rôle, facteurs de double authentification,
  journal des connexions, des consultations et des exports.
- Pour un expert-comptable habilité : nom, cabinet, numéro d'inscription à
  l'Ordre, lettre de mission, engagement accepté, chacun de ses changements.

## 3. Pourquoi

- Produire la comptabilité, les comptes annuels et les déclarations de
  l'entreprise (exécution du contrat).
- Signaler des anomalies dans les dépenses (intérêt légitime). Ce
  traitement compare des dépenses à un profil : une analyse d'impact est à
  documenter. [À COMPLÉTER : AIPD, doc 02 §8.]
- Améliorer le classement automatique : les libellés d'opérations et les
  catégories choisies peuvent servir à entraîner le modèle de classement,
  **sur nos propres machines**. [À COMPLÉTER par le juriste : couverture
  contractuelle de cette réutilisation, doc 02 §8.]
- Sécuriser les accès (double authentification, journal des accès).

**Aucune donnée n'est envoyée à un service d'intelligence artificielle
externe.** Le classement automatique se fait par des règles et par un
modèle statistique exécuté sur nos serveurs.

## 4. Sous-traitants et services utilisés

| Service | Rôle | Où sont les données |
|---|---|---|
| **Supabase, Inc.** | Base de données (PostgreSQL), authentification, stockage de fichiers | Région AWS **eu-west-1 (Irlande)** |
| **Digifactory** | Transmission des opérations bancaires de l'entreprise (`entrepreneur.digifactory.fr`) | [À COMPLÉTER : localisation des données chez Digifactory] |
| **Sentry** (Functional Software, Inc.), seulement s'il est activé | Rapports d'erreurs techniques, sans donnée personnelle (`send_default_pii` désactivé côté serveur) | [À COMPLÉTER : région du projet Sentry] |
| Hébergeur de l'application | Serveur web et API | [À COMPLÉTER : hébergeur applicatif, AXE-811] |

**Chaîne bancaire.** AxeLCompta n'interroge pas les banques. Le dirigeant
(ou son gestionnaire, avec son accord) autorise l'accès à ses comptes auprès
de Digifactory, qui s'appuie sur un agrégateur agréé (Bridge). AxeLCompta
reçoit les opérations de Digifactory. Le consentement DSP2 et la répartition
des rôles entre ces acteurs restent à formaliser.
[À COMPLÉTER par le juriste : consentement DSP2 et article 28 à trois
parties, doc 10 §3.]

**Services choisis par le gestionnaire.** Pour les rappels, le gestionnaire
peut brancher son propre serveur d'e-mail ou fournisseur de SMS. Ces
services sont les siens : AxeLCompta leur transmet l'adresse ou le numéro
du dirigeant, le texte du rappel et un lien, jamais de montant.

**Données publiques.** Pour pré-remplir l'identité d'une société,
AxeLCompta interroge l'annuaire public « Recherche d'entreprises » de
l'État avec le seul numéro SIREN.

**Transferts hors de l'Union européenne.** Supabase, Inc. est une société
de droit américain : même hébergées en Irlande, les données peuvent être
soumises à une demande d'une autorité américaine (CLOUD Act, ADR-003).
[À COMPLÉTER par le juriste : mécanisme d'encadrement (clauses
contractuelles types, DPA Supabase).]

## 5. Combien de temps

| Donnée | Durée | Ensuite |
|---|---|---|
| Écritures, FEC, liasses | 10 ans (C. com. L.123-22) | Suppression |
| Justificatifs | 10 ans | Suppression |
| Opérations bancaires brutes non comptabilisées | Durée du dossier + 1 an | Suppression |
| Journaux techniques | 12 mois, sans donnée nominative | Rotation |
| Comptes utilisateurs inactifs | 24 mois | Anonymisation |

## 6. Cookies et traceurs

AxeLCompta ne dépose **aucun traceur de mesure d'audience ni publicitaire**.
La session de connexion est gardée dans le stockage local du navigateur,
uniquement pour vous garder connecté. La police de caractères est servie
par l'application elle-même.

## 7. Vos droits

Vous pouvez demander l'accès, la rectification, l'effacement ou la
limitation de vos données, et vous opposer à un traitement fondé sur
l'intérêt légitime. Les écritures et pièces comptables ne peuvent pas être
effacées avant la fin de leur durée légale de conservation. Pour les
données d'un dossier, la demande passe par l'entreprise responsable de
traitement ; AXEL PROJECT l'aide à y répondre.

Chaque dossier peut exporter son FEC à tout moment.

Vous pouvez saisir la CNIL (www.cnil.fr).

## Annexe — Engagements de sous-traitance (article 28)

AXEL PROJECT, sous-traitant, s'engage envers le client responsable de
traitement à :

1. ne traiter les données que pour produire la comptabilité et les
   déclarations des dossiers du client, et sur ses instructions ;
2. faire respecter la confidentialité par toute personne qui y a accès ;
3. protéger les données : séparation stricte des dossiers en base
   (sécurité par ligne), double authentification des administrateurs et des
   experts-comptables, journal des accès et des exports, écritures
   comptables non modifiables ;
4. n'ajouter un sous-traitant qu'après en avoir informé le client, qui peut
   s'y opposer ; la liste à jour est la section 4 ;
5. aider le client à répondre aux demandes des personnes et à ses
   obligations (sécurité, notification de violation, analyse d'impact) ;
6. notifier au client toute violation de données dans les meilleurs délais
   [À COMPLÉTER : délai contractuel] ;
7. à la fin du contrat, restituer les données (export FEC) puis les
   supprimer, sauf obligation légale de conservation ;
8. permettre les audits raisonnables du client.

[À COMPLÉTER par le juriste : forme du DPA signé avec chaque client.]
