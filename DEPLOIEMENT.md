à# 🚀 Guide de Déploiement - Assistant Orga

Ce guide vous explique comment héberger votre assistant Orga sur Railway pour qu'il fonctionne 24h/24, même quand votre ordinateur est éteint.

## 📋 Prérequis

1. **Compte GitHub** (pour stocker votre code)
2. **Compte Railway** (gratuit pour commencer)
3. **Vos clés API** (Telegram, OpenAI, Google Calendar)

## 🔧 Étape 1 : Préparer vos credentials

### 1.1 Token Telegram Bot
- Gardez votre token Telegram sous la main (celui de @BotFather)

### 1.2 Clé OpenAI
- Récupérez votre clé API OpenAI depuis https://platform.openai.com/api-keys

### 1.3 Credentials Google Calendar
- Ouvrez votre fichier `token.json` local
- Copiez TOUT le contenu de `google_credentials` (c'est un gros bloc JSON)
- Exemple : `{"token": "ya29...", "refresh_token": "1//...", ...}`

## 🌐 Étape 2 : Créer un repository GitHub

1. Allez sur https://github.com
2. Créez un nouveau repository (ex: `mon-assistant-orga`)
3. Uploadez tous vos fichiers SAUF `token.json` (pour la sécurité)

## 🚄 Étape 3 : Déployer sur Railway

### 3.1 Connexion
1. Allez sur https://railway.app
2. Connectez-vous avec votre compte GitHub
3. Cliquez sur "New Project"
4. Sélectionnez "Deploy from GitHub repo"
5. Choisissez votre repository `mon-assistant-orga`

### 3.2 Configuration des variables d'environnement
Dans l'onglet "Variables" de Railway, ajoutez :

```
TELEGRAM_BOT_TOKEN=1234567890:AAAA...
OPENAI_API_KEY=sk-proj-...
GOOGLE_CREDENTIALS={"token":"ya29...","refresh_token":"1//...","token_uri":"https://oauth2.googleapis.com/token","client_id":"...","client_secret":"...","scopes":["https://www.googleapis.com/auth/calendar"],"expiry":"2024-..."}
```

⚠️ **Important** : Pour `GOOGLE_CREDENTIALS`, copiez EXACTEMENT le contenu JSON sur UNE SEULE LIGNE.

### 3.3 Déploiement
1. Railway va automatiquement détecter que c'est une app Python
2. Il va installer les dépendances depuis `requirements.txt`
3. Il va lancer votre bot avec `python main.py`

## ✅ Étape 4 : Vérification

### 4.1 Logs
- Dans Railway, allez dans l'onglet "Logs"
- Vous devriez voir : "✅ Configuration chargée avec succès"
- Et : "🤖 Bot Orga démarré et prêt à recevoir des messages"

### 4.2 Test
- Envoyez un message à votre bot Telegram
- Il devrait répondre normalement avec le contexte complet

## 💰 Coûts

### Railway
- **Gratuit** : 5$ de crédit gratuit par mois
- **Hobby** : 5$/mois pour usage personnel
- **Pro** : 20$/mois pour usage intensif

### Estimation mensuelle
- **Railway** : ~5$/mois
- **OpenAI** : 2-10$/mois selon usage
- **Total** : ~7-15$/mois pour un assistant personnel 24h/24

## 🔧 Maintenance

### Mise à jour du code
1. Modifiez votre code localement
2. Poussez les changements sur GitHub
3. Railway redéploiera automatiquement

### Surveillance
- Consultez les logs Railway régulièrement
- Surveillez votre usage OpenAI sur platform.openai.com

## 🆘 Dépannage

### Le bot ne répond pas
1. Vérifiez les logs Railway
2. Vérifiez que toutes les variables d'environnement sont correctes
3. Testez vos clés API individuellement

### Erreur "Credentials Google"
- Vérifiez que `GOOGLE_CREDENTIALS` est sur une seule ligne
- Vérifiez que les guillemets sont bien échappés
- Le bot peut fonctionner sans Google Calendar (fonctionnalités limitées)

### Erreur "OpenAI API"
- Vérifiez votre clé API OpenAI
- Vérifiez votre crédit OpenAI restant
- La clé doit commencer par `sk-proj-` ou `sk-`

## 🎉 Félicitations !

Votre assistant Orga fonctionne maintenant 24h/24 dans le cloud ! 🌟

Vous pouvez l'utiliser depuis n'importe où, sur n'importe quel appareil, tant que vous avez Telegram. 