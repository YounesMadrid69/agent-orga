# 🤖 Agent-Orga

Assistant personnel intelligent via Telegram qui gère vos tâches, projets et calendrier Google.

## 🚀 Fonctionnalités

- ✅ **Gestion de tâches** : Priorisation automatique (matrice d'Eisenhower), sous-tâches et suivi de progression.
- 📋 **Organisation par projets** : Associez tâches et événements à des projets clairs avec des émojis.
- 📅 **Intégration Google Calendar** : Synchronisation bidirectionnelle des tâches et des événements.
- 🧠 **Mémoire Persistante** : L'assistant apprend de vos conversations et se souvient de vos préférences et objectifs.
- 💬 **Interface Naturelle** : Dialoguez avec l'assistant via Telegram comme avec un humain.
- 🤖 **IA Google Gemini** : Le dernier modèle de Google pour une compréhension fine de vos demandes.

## ⚙️ Variables d'environnement nécessaires

- `TELEGRAM_BOT_TOKEN` : Token de votre bot Telegram
- `GOOGLE_API_KEY` : Votre clé API pour Google AI Studio (Gemini).
- `GOOGLE_CREDENTIALS_JSON` : Le contenu de votre fichier `credentials.json` de Google Cloud, pour l'API Calendar.
- `GOOGLE_TOKEN_JSON` : Le contenu du fichier `token.json` généré à la première connexion (pour le déploiement).

## 📦 Déploiement

Ce projet est prêt pour un déploiement sur des plateformes comme Railway, Render ou Heroku. 