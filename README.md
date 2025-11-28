C'est la touche finale indispensable pour rendre ton projet professionnel. Un bon `README.md` montre que tu maîtrises ton environnement de déploiement.

Voici un fichier `README.md` complet, structuré et formaté. Tu peux copier-coller ce contenu directement dans un fichier texte nommé **`README.md`** à la racine de ton projet.

***

# 🤖 Agent IA de Réservation Intelligent (Architecture BDI)

Ce projet implémente un **Agent Conversationnel Intelligent** capable de gérer les réservations d'un restaurant. Contrairement à un simple formulaire, cet agent utilise une architecture **BDI (Beliefs-Desires-Intentions)** pour raisonner, négocier et optimiser le remplissage du planning.

## 🚀 Fonctionnalités Clés

*   **🧠 Intelligence Artificielle (NLP) :** Compréhension du langage naturel (*"Je veux une table pour 3 le 5 à 20h"*).
*   **🗣️ Négociation & Mémoire :** L'agent se souvient du contexte de la conversation. Si un créneau est complet, il négocie une alternative pertinente basée sur la proximité horaire.
*   **⚖️ Algorithme de Décision BDI :** Calcul de score en temps réel prenant en compte la proximité de l'heure demandée et la charge du restaurant (Load Balancing).
*   **⚙️ Back-Office Administrateur :** Tableau de bord pour gérer la capacité en temps réel, voir les clients (Nom/Email) et modifier la configuration globale.
*   **🎨 Interface Double Mode :** Le client peut choisir entre une discussion avec le Chatbot ou un Formulaire classique (qui se met à jour automatiquement selon les suggestions de l'IA).

---

## 🛠️ Pré-requis

*   **Python 3.8** ou supérieur.
*   Un navigateur web moderne (Chrome, Firefox, Safari).

---

## 📦 Installation

1.  **Cloner ou télécharger le projet** dans un dossier.
2.  **Créer un environnement virtuel** (recommandé) :
    ```bash
    python3 -m venv venv
    source venv/bin/activate   # Sur Mac/Linux
    # ou
    venv\Scripts\activate      # Sur Windows
    ```
3.  **Installer les dépendances** :
    ```bash
    pip install fastapi uvicorn
    ```

---

## ⚠️ Instructions de Démarrage (Important)

Pour que l'application fonctionne correctement (et éviter les blocages de sécurité CORS du navigateur), vous devez lancer **deux terminaux** simultanément.

### 1️⃣ TERMINAL 1 : Le Cerveau (Backend API)
Ce terminal gère l'intelligence, la base de données et les calculs.

Dans le dossier du projet :
```bash
# Assurez-vous que l'environnement virtuel est activé
uvicorn main:app --reload
```
*Le terminal affichera : `Uvicorn running on http://127.0.0.1:8000`*

### 2️⃣ TERMINAL 2 : L'Interface (Frontend)
Ce terminal sert les fichiers HTML pour qu'ils soient vus comme un vrai site web.

Ouvrez une **nouvelle fenêtre** de terminal, allez dans le dossier du projet et lancez :
```bash
python3 -m http.server 9000
```
*Le terminal affichera : `Serving HTTP on :: port 9000`*

---

## 🖥️ Accès à l'Application

Une fois les deux terminaux lancés :

*   👉 **Interface Client (Chatbot & Formulaire) :**
    [http://localhost:9000/client.html](http://localhost:9000/client.html)

*   👉 **Interface Administrateur (Back-Office) :**
    [http://localhost:9000/admin.html](http://localhost:9000/admin.html)

---

## 🧪 Scénario de Démonstration (Pour le Jury)

Pour tester l'intelligence de l'agent :

1.  **Test de compréhension :**
    *   Ouvrez le chat client.
    *   Écrivez : *"Une table pour 3 personnes le 12"*.
    *   L'agent comprendra la date et vous proposera l'heure par défaut (souvent 19h).

2.  **Test de saturation & Négociation :**
    *   Allez dans l'Admin et réduisez la capacité d'un créneau (ex: 20h) à 0.
    *   Dans le chat client, demandez : *"Je veux venir le 12 à 20h"*.
    *   L'agent répondra : *"⚠️ 20h est complet. Je vous propose 19h ou 21h."*

3.  **Test Formulaire assisté :**
    *   Utilisez le formulaire classique.
    *   Sélectionnez un créneau complet.
    *   L'IA force la sélection d'une alternative et le bouton change pour demander confirmation.

4.  **Test Admin :**
    *   Validez une réservation via le Chat (avec Nom et Email).
    *   Allez sur l'Admin : le nom et l'email du client apparaissent instantanément dans le tableau de bord.

---

## 📂 Structure du Projet

*   `main.py` : Le **Cerveau**. Contient l'API FastAPI, la logique BDI, le moteur NLP (Regex) et la gestion de la mémoire.
*   `client.html` : L'**Interface**. Contient le Chatbot, le Formulaire et la logique d'affichage dynamique.
*   `admin.html` : Le **Contrôle**. Tableau de bord pour visualiser les KPIs et modifier les règles du système.
*   `agent_data.json` : La **Mémoire persistante** (Base de données JSON générée automatiquement).