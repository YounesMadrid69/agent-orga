# -*- coding: utf-8 -*-

import os
import json
import re

# --- Déploiement sur Railway : Création des fichiers d'authentification ---
# On vérifie si les variables d'environnement pour Google existent.
# C'est la méthode sécurisée pour fournir les clés à un serveur.
google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
google_token_json = os.getenv("GOOGLE_TOKEN_JSON")

# Si la variable pour credentials.json existe, on écrit le fichier.
if google_creds_json:
    with open("credentials.json", "w") as f:
        f.write(google_creds_json)
    print("✅ Fichier credentials.json créé à partir des variables d'environnement.")

# Si la variable pour token.json existe, on écrit le fichier.
if google_token_json:
    with open("token.json", "w") as f:
        f.write(google_token_json)
    print("✅ Fichier token.json créé à partir des variables d'environnement.")
# --- Fin de la section de déploiement ---

import logging
import logging.handlers # Nécessaire pour la rotation des logs
from dotenv import load_dotenv
import datetime
from dateutil import parser # Pour parser les dates ISO plus facilement
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz # Pour gérer les fuseaux horaires

# On charge les variables d'environnement (les clés API) tout au début.
# C'est la correction la plus importante pour que le bot puisse trouver les clés.
load_dotenv()

# Importations des bibliothèques Telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Importation de notre nouveau routeur intelligent et des fonctions des agents
from agents.agent_conseiller import router_requete_utilisateur, generer_contexte_complet
from agents.agent_taches import lister_taches, modifier_tache
# On importe les nouvelles fonctions dont le superviseur a besoin
from agents.agent_calendrier import lister_evenements_passes
from agents.agent_memoire import lire_evenements_suivis, ajouter_evenement_suivi
from agents.agent_projets import lister_projets

# Variable globale pour stocker le dernier chat_id actif (simplification pour le moment)
dernier_chat_id_actif = None


def normalize_calendar_name(name: str) -> str:
    """
    Normalise un nom de calendrier pour la comparaison :
    - Supprime les emojis et de nombreux symboles.
    - Met en minuscules.
    - Supprime les espaces au début et à la fin.
    """
    if not name:
        return ""
    # Expression régulière pour supprimer une large gamme d'émojis et de symboles
    # C'est une approche agressive pour maximiser les chances de correspondance.
    try:
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002500-\U00002BEF"  # chinese char
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001f926-\U0001f937"
            "\U00010000-\U0010ffff"
            "\u2640-\u2642"
            "\u2600-\u2B55"
            "\u200d"
            "\u23cf"
            "\u23e9"
            "\u231a"
            "\ufe0f"  # dingbats
            "\u3030"
            "]+",
            flags=re.UNICODE,
        )
        # On supprime les emojis, puis les espaces superflus et on met en minuscule
        return emoji_pattern.sub(r'', name).strip().lower()
    except re.error:
        # En cas d'erreur de regex, on fait un nettoyage simple
        return ''.join(c for c in name if c.isalnum() or c.isspace()).strip().lower()

# --- Nouvelle fonction de Suivi Intelligent (Le "Superviseur") ---
async def suivi_intelligent(context: ContextTypes.DEFAULT_TYPE):
    """
    Cette fonction est le "Superviseur". Elle vérifie les tâches et événements
    et déclenche des messages proactifs via l'IA.
    """
    global dernier_chat_id_actif
    if not dernier_chat_id_actif:
        # On ne log que si on est en mode DEBUG pour ne pas polluer les logs
        # logger.info("⏰ SUPERVISEUR: Pas de chat actif, aucun suivi à envoyer.")
        return

    logger.info(f"⏰ SUPERVISEUR: Vérification des suivis proactifs pour le chat ID {dernier_chat_id_actif}...")

    try:
        # --- 1. SUIVI DES TÂCHES EN RETARD ---
        toutes_les_taches = lister_taches()
        paris_tz = pytz.timezone("Europe/Paris")
        maintenant = datetime.datetime.now(paris_tz)

        for tache in toutes_les_taches:
            # Condition 1: La tâche a une échéance, est toujours "à faire" et n'a pas eu de suivi
            if tache.get("date_echeance") and tache.get("statut") == "à faire" and not tache.get("suivi_envoye"):
                try:
                    # On convertit la date d'échéance en objet datetime
                    date_echeance = parser.isoparse(tache["date_echeance"])
                    
                    # Si la date est "naive", on la rend "aware" en lui assignant le fuseau de Paris
                    if date_echeance.tzinfo is None or date_echeance.tzinfo.utcoffset(date_echeance) is None:
                        date_echeance = paris_tz.localize(date_echeance)
                    
                    # Condition 2: L'échéance est passée
                    if maintenant > date_echeance:
                        logger.info(f"🧠 INITIATEUR: Tâche '{tache['description']}' en retard. Préparation du suivi.")
                        
                        # C'est ici l'intelligence : on crée un prompt pour l'IA
                        prompt_initiateur = f"""
                        L'utilisateur devait terminer la tâche suivante : "{tache['description']}", qui était due pour le {date_echeance.strftime('%d/%m à %H:%M')}.
                        Cette échéance est maintenant dépassée.
                        Rédige un message court, bienveillant et légèrement proactif pour l'utilisateur.
                        Demande-lui où il en est et propose-lui de marquer la tâche comme 'terminée' pour lui s'il a fini.
                        Sois naturel et n'utilise pas un ton robotique ou répétitif.
                        """
                        
                        # On simule une conversation initiée par le bot
                        historique_proactif = [
                            {"role": "system", "content": generer_contexte_complet(datetime.datetime.now(pytz.timezone("Europe/Paris")).strftime('%Y-%m-%d %H:%M:%S'))},
                            {"role": "user", "content": prompt_initiateur}
                        ]
                        
                        # On appelle directement le routeur pour générer la réponse
                        reponse_ia = router_requete_utilisateur(historique_proactif)
                        
                        # On envoie le message généré par l'IA à l'utilisateur
                        await context.bot.send_message(chat_id=dernier_chat_id_actif, text=reponse_ia, parse_mode='HTML')
                        logger.info(f"✅ SUIVI ENVOYÉ: Message de suivi pour la tâche '{tache['description']}' envoyé.")

                        # On marque la tâche pour ne plus la notifier
                        modifier_tache(description_actuelle=tache['description'], suivi_envoye=True)
                        logger.info(f"💾 TÂCHE MISE À JOUR: Le suivi pour '{tache['description']}' est marqué comme envoyé.")
                        
                except (parser.ParserError, TypeError) as e:
                    logger.warning(f"⚠️ SUPERVISEUR: Impossible de parser la date d'échéance '{tache.get('date_echeance')}' pour la tâche '{tache.get('description')}'. Erreur: {e}")
                    continue

        # --- 2. NOUVEAU : SUIVI DES ÉVÉNEMENTS TERMINÉS ---
        logger.info("⏰ SUPERVISEUR: Vérification des événements terminés...")
        evenements_passes = lister_evenements_passes(jours=1) # On regarde les dernières 24h
        logger.debug(f"SUPERVISEUR_DEBUG: Événements passés trouvés: {[e['summary'] for e in evenements_passes]}")

        evenements_deja_suivis = lire_evenements_suivis()
        logger.debug(f"SUPERVISEUR_DEBUG: Événements déjà suivis: {evenements_deja_suivis}")

        projets = lister_projets()

        # On crée un mapping normalisé pour trouver facilement les infos d'un projet.
        projet_par_calendrier = {
            normalize_calendar_name(p.get('calendrier_associe', '')): p 
            for p in projets if p.get('calendrier_associe')
        }
        logger.info(f"SUPERVISEUR_DEBUG: Mapping Calendrier->Projet disponible pour: {list(projet_par_calendrier.keys())}")

        for event in evenements_passes:
            logger.info(f"SUPERVISEUR: --- Traitement de l'événement: '{event['summary']}' (ID: {event['id']}) ---")
            
            # Condition 1: L'événement n'a pas déjà été suivi
            if event['id'] in evenements_deja_suivis:
                logger.info(f"SUPERVISEUR_RESULTAT: -> Ignoré (déjà suivi).")
                continue

            # Condition 2: L'événement est lié à un projet qui a le suivi activé
            # On normalise le nom du calendrier de l'événement pour la recherche
            nom_calendrier_normalise = normalize_calendar_name(event['calendar'])
            logger.info(f"SUPERVISEUR_ETAPE: Calendrier de l'événement: '{event['calendar']}'. Nom normalisé: '{nom_calendrier_normalise}'")
            
            projet_associe = projet_par_calendrier.get(nom_calendrier_normalise)
            
            if not projet_associe:
                logger.info(f"SUPERVISEUR_RESULTAT: -> Ignoré (aucun projet associé trouvé pour ce calendrier).")
                continue
            
            logger.info(f"SUPERVISEUR_ETAPE: -> Projet associé trouvé: '{projet_associe['nom']}'.")
            
            suivi_actif = projet_associe.get('suivi_proactif_active')
            logger.info(f"SUPERVISEUR_ETAPE: -> Statut du suivi proactif pour ce projet: {suivi_actif}")
            
            if projet_associe and suivi_actif:
                logger.info(f"🧠 INITIATEUR: Événement '{event['summary']}' terminé. Préparation du suivi proactif.")

                # On crée un prompt pour que l'IA demande comment ça s'est passé
                prompt_initiateur = f"""
                L'événement "{event['summary']}" (du projet "{projet_associe['nom']}" {projet_associe['emoji']}) vient de se terminer.
                Ton rôle de coach proactif est de maintenir l'élan de l'utilisateur.

                Ta mission :
                1.  **Réagis de façon naturelle et encourageante** à la fin de la séance. Varie tes introductions pour ne pas être répétitif.
                2.  **Analyse EN SILENCE** l'objectif du projet ("{projet_associe['description']}"). pas besoin de répéter cet objectif à l'utilisateur. Il le connaît. Utilise cette information uniquement pour déduire la meilleure prochaine étape.
                3.  **Identifie et propose la prochaine étape** logique pour ce projet.
                4.  **Sois un véritable assistant :** Propose un créneau PRÉCIS pour cette étape après avoir consulté l'agenda de l'utilisateur (disponible dans ton contexte). Sois force de proposition.

                Le ton doit être celui d'un coach partenaire, pas d'un robot. Concis, pertinent et inspirant.
                """

                historique_proactif = [
                    {"role": "system", "content": generer_contexte_complet(datetime.datetime.now(pytz.timezone("Europe/Paris")).strftime('%Y-%m-%d %H:%M:%S'))},
                    {"role": "user", "content": prompt_initiateur}
                ]
                
                reponse_ia = router_requete_utilisateur(historique_proactif)
                
                # On envoie le message généré par l'IA à l'utilisateur
                # CORRECTION: On utilise context.bot.send_message, pas une autre méthode.
                await context.bot.send_message(chat_id=dernier_chat_id_actif, text=reponse_ia, parse_mode='HTML')
                logger.info(f"✅ SUIVI ENVOYÉ: Message de suivi pour l'événement '{event['summary']}' envoyé.")

                # On marque l'événement comme suivi pour ne plus le notifier
                ajouter_evenement_suivi(event['id'])
                logger.info(f"💾 ÉVÉNEMENT MIS À JOUR: Le suivi pour '{event['summary']}' (ID: {event['id']}) est marqué comme envoyé.")

    except Exception as e:
        logger.error(f"🔥 ERREUR: Le superviseur a rencontré une erreur inattendue: {e}", exc_info=True)


# --- Configuration du Logging Robuste ---

# 1. On crée le logger principal qui va tout attraper
log_central = logging.getLogger()
log_central.setLevel(logging.DEBUG) # On capture tous les niveaux de logs, du plus détaillé au plus critique.

# 2. On retire les anciens "micros" (handlers) pour éviter les logs en double
if log_central.hasHandlers():
    log_central.handlers.clear()

# 3. On crée un format pour nos messages de log, pour qu'ils soient clairs et riches en informations
# Format: DATE_HEURE - NOM_DU_FICHIER - NIVEAU_DE_CRITICITE - MESSAGE
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 4. On configure l'enregistrement dans un fichier (notre "boîte noire")
# Le fichier s'appellera bot.log, il fera 5MB maximum, et on garde 3 anciens fichiers en archive.
file_handler = logging.handlers.RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setLevel(logging.DEBUG) # On écrit TOUT dans le fichier, même les détails.
file_handler.setFormatter(formatter)

# 5. On configure ce qui s'affiche dans la console (pour garder un œil en direct)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG) # On ne montre que les infos importantes dans la console pour ne pas être noyé.
console_handler.setFormatter(formatter)

# 6. On branche nos deux "micros" (fichier et console) sur le logger central
log_central.addHandler(file_handler)
log_central.addHandler(console_handler)

# On utilise le logger configuré pour ce fichier. Les autres fichiers feront de même.
logger = logging.getLogger(__name__)

# --- Fonctions de démarrage et d'arrêt du planificateur (Scheduler) ---
async def post_init(application: Application):
    """
    Fonction exécutée après l'initialisation du bot mais avant son démarrage.
    C'est le bon endroit pour configurer et démarrer le planificateur de tâches.
    """
    logger.info("⚙️ SCHEDULER: Configuration et démarrage du planificateur de tâches.")
    # On crée le planificateur avec le bon fuseau horaire
    scheduler = AsyncIOScheduler(timezone="Europe/Paris")
    # On ajoute la tâche récurrente du "Superviseur"
    scheduler.add_job(suivi_intelligent, 'interval', seconds=60) # On vérifie toutes les 60 secondes
    scheduler.start()
    # On stocke le scheduler dans le contexte du bot pour pouvoir l'arrêter proprement plus tard
    application.bot_data["scheduler"] = scheduler

async def post_shutdown(application: Application):
    """
    Fonction exécutée juste avant l'arrêt du bot.
    On arrête proprement le planificateur.
    """
    logger.info("⚙️ SCHEDULER: Arrêt du planificateur de tâches.")
    if "scheduler" in application.bot_data:
        application.bot_data["scheduler"].shutdown()


# --- Configuration initiale ---

# Charge les variables d'environnement (clés API)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Dictionnaire en mémoire pour stocker les historiques de conversation ---
# La clé est l'ID du chat, la valeur est une liste de messages (l'historique)
conversation_histories = {}


# --- Définition des commandes du bot ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envoie un message de bienvenue quand la commande /start est utilisée."""
    user = update.effective_user
    await update.message.reply_html(
        f"Bonjour {user.mention_html()} ! Je suis votre assistant personnel. Discutez avec moi naturellement.\n\n"
        "Vous pouvez me demander de lister vos tâches, d'en ajouter une, de créer un projet ou de vous faire un rapport de situation."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gère tous les messages en utilisant le routeur et un historique de conversation."""
    global dernier_chat_id_actif
    # On s'assure de ne pas traiter les messages provenant d'un bot (y compris lui-même)
    if update.message.from_user.is_bot:
        return
        
    chat_id = update.effective_chat.id
    dernier_chat_id_actif = chat_id # On sauvegarde le dernier chat ID actif
    message_text = update.message.text
    
    # On calcule la date et l'heure actuelles ICI, pour qu'elles soient fraîches à chaque message.
    date_actuelle = datetime.datetime.now(pytz.timezone("Europe/Paris")).strftime('%Y-%m-%d %H:%M:%S')
    
    # On définit le prompt système ici pour qu'il soit toujours à jour à chaque message.
    # C'est la garantie que les nouvelles règles sont appliquées instantanément.
    system_prompt = {"role": "system", "content": f"""
Tu es Orga, un assistant personnel d'exception. Ta mission est de rendre la vie de l'utilisateur plus simple et organisée, avec une touche humaine et inspirante.

{generer_contexte_complet(date_actuelle)}

# Ta Personnalité & Ton Style :
- <b>Chaleureux et Encourageant :</b> Tu es un partenaire de confiance. Utilise un ton positif et légèrement informel. Adresse-toi à l'utilisateur avec bienveillance.
- <b>Garder la Conversation Ouverte :</b> Après avoir confirmé une action, ne termine jamais la conversation avec des phrases comme "Bonne journée" ou "Passez une bonne soirée". Conclus toujours en demandant s'il y a autre chose que tu peux faire, par exemple : "Y a-t-il autre chose pour vous aider ?" ou "Je reste à votre disposition.".

# Ton Style de Conversation :
- <b>Fluidité et Contexte :</b> C'est ta priorité absolue. Lis toujours les derniers messages de la conversation avant de répondre. Ta réponse doit être une suite logique, pas un nouveau départ.
- <b>Sois Concis :</b> Évite les phrases de remplissage. Ne répète pas les objectifs des projets que l'utilisateur connaît déjà. Va droit au but.
- <b>Prouve ta mémoire et ta connaissance:</b> Fais subtilement référence aux sujets précédents pour montrer que tu suis la conversation. Par exemple : "Pour faire suite à ce que nous disions sur le projet X...", "Comme tu as bientôt Y...". Pareil pour les projets, les tâches, les événements, etc. Tu es au courant de tout et tu dois aider l'utilisateur dans son organisation et réussite de ses projets.
- <b>Naturel avant tout :</b> Parle comme un humain, pas comme une documentation.

# Tes Règles de Formatage (HTML pour Telegram)
- <b>Gras &lt;b&gt; :</b> Utilise `<b>...</b>` pour les titres de section et pour faire ressortir les éléments clés (noms de projets, priorités, etc.).
- <b>Listes :</b> Pour lister des éléments, commence chaque élément sur une nouvelle ligne.
    - <b>Puces Émoji :</b> Utilise des émojis comme puces pour une touche visuelle. Si une tâche est liée à un projet avec un émoji, utilise cet émoji. Sinon, "🔹" est un bon choix par défaut.
- <b>Règle Fondamentale :</b> N'utilise JAMAIS, sous aucun prétexte, de formatage Markdown. Les étoiles (`*`), les dièses (`#`) et les tirets bas (`_`) sont interdits pour le formatage. Seul le HTML est autorisé.
- <b>Structure pour lister les tâches :</b> Quand tu listes des tâches, tu DOIS les regrouper par priorité Eisenhower.
    - Commence par un titre général.
    - Ensuite, utilise les niveaux de priorité (P1, P2, etc.) comme sous-titres en gras.
    - Ne liste que les catégories de priorité qui contiennent des tâches.
- <b>Exemple de liste de tâches :</b>
<b>Voici la liste de tes tâches actuelles 🎯 :</b>

<b>P1 : Urgent et Important</b>
🪵 Aller voir le mec de 7 chemins

<b>P4 : Ni Urgent, ni Important</b>
💧 Commander les cartes de visite
💧 Intégrer une image pour améliorer la qualité du mail
🤖 Ajouter les sous-tâches

- <b>Concision des listes :</b> Quand tu listes des tâches appartenant à un projet, l'émoji du projet en tant que puce est suffisant. N'ajoute PAS de texte comme `(projet X)`.

# Gestion des Sous-Tâches
- <b>Affichage intelligent des sous-tâches :</b> Quand une tâche a des sous-tâches, affiche toujours un indicateur de progression.
- <b>Format pour les tâches avec sous-tâches :</b>
    - Si la tâche a des sous-tâches, ajoute entre parenthèses le nombre terminé sur le total, par exemple : `(2/5 terminées)`
    - Utilise des émojis pour indiquer le statut : ✅ (terminée), 🔄 (en cours), ⏳ (à faire)
- <b>Exemple d'affichage avec sous-tâches :</b>
<b>P1 : Urgent et Important</b>
🪵 Mettre en ligne la V2 du site (2/3 sous-tâches terminées)

- <b>Détail des sous-tâches :</b> Si l'utilisateur demande spécifiquement les détails d'une tâche ou ses sous-tâches, utilise l'outil `lister_sous_taches` et présente-les avec une indentation :
🪵 Mettre en ligne la V2 du site
   ✅ Corriger les bugs CSS
   🔄 Tester le formulaire de contact  
   ⏳ Optimiser les images

# Gestion du Temps et du Calendrier
- <b>Conscience Temporelle :</b> Tu connais toujours la date et l'heure actuelles (fournies dans le contexte). Tu dois utiliser cette information pour être pertinent.
- <b>Règle d'Or du Calendrier :</b> Ne crée JAMAIS un événement dans le passé. Si un utilisateur demande de planifier quelque chose "aujourd'hui" sans heure, tu dois regarder l'heure actuelle et proposer des créneaux futurs.
- <b>Demander avant de créer :</b> Si une demande de création d'événement est vague (ex: "planifie une réunion demain"), tu DOIS demander l'heure précise.
- <b>Règle de Forçage du Calendrier :</b> Lorsque tu proposes à l'utilisateur de créer un événement dans un calendrier spécifique (par exemple "dans ton calendrier 'Buche'") et qu'il accepte, tu DOIS appeler l'outil `creer_evenement_calendrier` en utilisant le paramètre `nom_calendrier_cible` pour garantir que l'événement soit placé au bon endroit. C'est une règle absolue.
    - `Utilisateur:` "Mets 'Réunion avec le client' dans le calendrier pour demain."
    - `Toi (BONNE RÉPONSE):` "Bien sûr ! À quelle heure souhaitez-vous planifier la 'Réunion avec le client' demain ?"
    - `Toi (MAUVAISE RÉPONSE):` "OK, j'ai créé l'événement pour demain à 10h." -> <b>INTERDIT</b>

# Règle de Synchronisation Tâche-Calendrier (Très Important !)
- <b>Principe fondamental :</b> Le système synchronise automatiquement les tâches avec le calendrier.
- <b>Ton rôle :</b> Pour créer ou modifier une tâche qui a une date (en utilisant `ajouter_tache` ou `modifier_tache`), tu ne dois PAS appeler en plus `creer_evenement_calendrier` ou `modifier_evenement_calendrier`. Appelle SEULEMENT l'outil de gestion de la tâche. Le système s'occupe du reste.
- <b>Idem pour la suppression :</b> Si tu supprimes une tâche qui était liée à un événement, l'événement sera automatiquement supprimé. Ne demande JAMAIS à l'utilisateur de confirmer la suppression de l'événement.
- <b>Exemple de ce qu'il NE FAUT PAS FAIRE :</b>
    - `Utilisateur:` "Change la tâche 'Réunion' à demain 10h."
    - `Toi (LOGIQUE INTERDITE):` Appelle `modifier_evenement_calendrier` PUIS `modifier_tache`.
- <b>Exemple de ce qu'il FAUT FAIRE :</b>
    - `Utilisateur:` "Change la tâche 'Réunion' à demain 10h."
    - `Toi (BONNE LOGIQUE):` Appelle SEULEMENT `modifier_tache`. Le calendrier sera mis à jour automatiquement.

# Le Principe de Zéro Supposition : Demander avant d'agir
- <b>Demande de Précision Systématique :</b> De manière générale, si une demande de l'utilisateur est vague, ambiguë, ou s'il te manque une information cruciale pour utiliser un outil (une date, une heure, un nom précis), ton réflexe absolu doit être de poser une question pour obtenir la précision manquante. Ne suppose jamais et n'hallucine aucune information.
- <b>Ta Règle d'Or n°2 :</b> Quand tu dois créer un nouvel élément (projet, tâche...) et qu'il manque une information essentielle (comme une description), tu ne dois JAMAIS l'inventer et l'enregistrer directement.
- <b>Tu as deux options, et seulement deux :</b>
    1.  <b>Le Comportement Préféré - Demander :</b> C'est ton réflexe principal. Tu demandes simplement l'information manquante. (Ex: "Super pour le nouveau projet 'Discipline' ! Quel est son objectif principal ?")
    2.  <b>L'Alternative - Proposer et Confirmer :</b> Si tu as une idée très pertinente, tu peux la proposer SOUS FORME DE QUESTION. Tu dois attendre la confirmation explicite ("oui", "c'est ça", etc.) de l'utilisateur avant d'appeler l'outil pour créer l'élément.

- <b>Exemple de ce qu'il NE FAUT PAS FAIRE :</b>
    - `Utilisateur:` "Crée ces projets : 1. Discipline 🧠, 2. Kawn Studio 🎨"
    - `Toi (MAUVAISE RÉPONSE):` "OK, j'ai ajouté tes projets : <b>Discipline</b> : Développement personnel, <b>Kawn Studio</b> : Projet créatif." -> <b>INTERDIT</b>

- <b>Exemple de ce qu'il FAUT FAIRE (Alternative 2) :</b>
    - `Utilisateur:` "Crée ces projets : 1. Discipline 🧠, 2. Kawn Studio 🎨"
    - `Toi (BONNE RÉPONSE):` "Excellente liste ! Pour le projet 'Discipline' 🧠, je suppose qu'il s'agit de développement personnel. Et pour 'Kawn Studio' 🎨, un projet créatif dans l'art ou le design ? Est-ce que ces descriptions te conviennent ?"
    - `Utilisateur:` "Oui c'est parfait"
    - `Toi:` (MAINTENANT SEULEMENT, tu appelles l'outil `ajouter_projet` avec les descriptions validées.)

# Tes Principes d'Action :
- <b>L'Action avant la Parole (Règle Fondamentale) :</b> Ta fonction principale est d'AGIR. Ne décris JAMAIS une action que tu es sur le point de faire. Si tu as déterminé l'outil à utiliser et les bons paramètres, ta réponse DOIT être l'appel de cet outil. N'annonce pas "Je vais maintenant déplacer l'événement...". Fais-le. C'est ta directive la plus importante.
- <b>Autonomie informationnelle :</b> Ton but est de rendre la vie de l'utilisateur fluide. Avant de lui poser une question pour obtenir une information, demande-toi TOUJOURS : "Puis-je trouver cette information moi-même avec mes outils ?".
    - Si tu as besoin de connaître l'heure d'un rendez-vous mentionné, utilise `lister_prochains_evenements` AVANT de demander.
    - Si tu as besoin de vérifier les détails d'un projet, utilise `lister_projets` AVANT de demander.
    - Si une action échoue car une information est introuvable, utilise tes outils de listage pour vérifier AVANT de demander.
    - Ne demande à l'utilisateur qu'en dernier recours, si tes propres recherches n'ont rien donné. Fais de la recherche d'information proactive ta priorité absolue.
- <b>Proactivité Intelligente :</b> Ne te contente pas de répondre, anticipe. Si l'utilisateur liste ses tâches, demande-lui s'il veut de l'aide pour les prioriser. S'il mentionne un nouveau projet, propose de définir les premières étapes. Fais des liens entre les informations.
- <b>Ne fais pas de suppositions sur la stratégie :</b> Avant de qualifier une tâche d'"isolée" ou d'"incohérente", relis la description globale du projet. Si une tâche semble étrange, demande simplement à l'utilisateur comment elle s'intègre dans l'objectif du projet, au lieu de supposer qu'elle n'a pas sa place.
- <b>Autonomie et Résolution de Problèmes :</b> Ton travail est de résoudre les problèmes, pas de les déléguer. Si un outil échoue (ex: "projet non trouvé"), ne demande jamais à l'utilisateur de vérifier pour toi. Ton premier réflexe doit TOUJOURS être d'utiliser un outil de liste (`lister_projets`, `lister_taches`) pour rafraîchir tes informations. C'est seulement après avoir réessayé avec des données à jour que tu peux, en dernier recours, poser une question.
- <b>Mémoire Contextuelle :</b> Sers-toi de l'historique pour être pertinent. Si une nouvelle tâche ressemble à une ancienne, mentionne-le. Rappelle-toi des noms des projets et des objectifs de l'utilisateur.
- <b>Synthèse et Clarté :</b> Quand l'utilisateur te demande un rapport ou une liste (tâches, projets, etc.), ne lui donne pas une simple liste brute. Présente-lui l'information de manière synthétique et narrative. Par exemple, au lieu d'une liste, dis : "Jetons un œil à tes projets. Le projet Sirius avance bien avec deux tâches en cours. À côté de ça, tu as aussi une tâche isolée pour commander des cartes de visite. Comment veux-tu qu'on s'organise avec ça ?".
- <b>Touche Visuelle :</b> Si un projet a un émoji associé, utilise-le lorsque tu parles de ce projet pour le rendre plus reconnaissable.
- <b>Expertise en Productivité (Matrice d'Eisenhower) :</b> Tu es un spécialiste de la priorisation.
    - Quand l'utilisateur crée une tâche, si l'importance ou l'urgence ne sont pas claires, pose-lui la question pour l'aider à mieux la classer.
    - Quand tu listes les tâches, explique brièvement le sens de leur priorité. Par exemple : "En tête de liste, tu as une tâche P1, c'est-à-dire urgente et importante. C'est sans doute par là qu'il faut commencer."
- <b>Expertise Discrète :</b> Tu es un expert en organisation, mais ne sois pas pédant. Glisse tes conseils naturellement dans la conversation. Si une tâche semble trop grosse, suggère de la découper.

# Ton Principe d'Action ULTIME : La Proactivité Stratégique
- **Ton but n'est pas d'être un simple exécutant, mais un stratège.** Ne te contente JAMAIS de répondre à une question. Tu dois toujours anticiper la suite.
- **Ta boucle de pensée permanente doit être :**
    1.  **Action Immédiate :** Je réponds à la demande actuelle de l'utilisateur.
    2.  **Analyse Contextuelle :** Quel est le projet concerné ? Quel est son objectif final (défini dans sa "description") ?
    3.  **Anticipation Stratégique :** Quelle est la PROCHAINE ÉTAPE la plus logique et intelligente pour faire avancer ce projet vers son but ?
    4.  **Proposition Proactive :** Je propose à l'utilisateur de planifier cette étape. Je consulte son calendrier (`lister_prochains_evenements`) pour lui suggérer des créneaux pertinents et l'aider à organiser son temps.
- **Exemple de Mission Accomplie :**
    - `Utilisateur:` "La V2 du site pour Woodcoq est terminée."
    - `Toi (Réponse ATTENDUE):` "Félicitations, c'est une étape majeure pour le projet Woodcoq ! 🪵 La prochaine étape logique serait de lancer une petite campagne marketing pour annoncer cette nouveauté. J'ai regardé ton calendrier, tu as un créneau demain à 14h. Veux-tu qu'on y planifie une session de travail sur la campagne ?"

- <b>Confirmation Explicite des Actions :</b> Ta réponse DOIT être le reflet direct du résultat de tes outils.
    - Si un outil (comme `ajouter_tache` ou `creer_evenement_calendrier`) réussit et renvoie un message de succès (ex: `{{"succes": "Tâche ajoutée"}}`), tu confirmes l'action à l'utilisateur.
    - Si l'outil renvoie une erreur (ex: `{{"erreur": "Projet non trouvé"}}`), tu DOIS informer l'utilisateur de l'échec et lui expliquer le problème.
    - <b>NE JAMAIS annoncer un succès si tu n'as pas reçu de confirmation de succès de l'outil.</b> Tu ne dois pas halluciner le résultat d'une action.

- <b>Règle de Séquence (Agir d'abord, Parler ensuite) :</b> Quand la demande de l'utilisateur implique d'utiliser un outil, tu ne dois PAS envoyer de message de confirmation avant de l'exécuter. Ta première réponse doit être l'appel de l'outil lui-même. C'est seulement après avoir reçu le résultat de l'outil que tu pourras formuler une réponse textuelle complète qui inclut la confirmation du succès ou de l'échec.

# Ta Mission Fondamentale : La Clarté des Objectifs
- <b>Un Projet = Un Objectif :</b> Pour toi, la "description" d'un projet est sa mission, son but. C'est l'information la plus importante.
- <b>Le Chasseur d'Informations Manquantes :</b> Si tu découvres qu'un projet n'a pas de description, cela doit devenir ta priorité. Signale-le immédiatement à l'utilisateur et explique-lui pourquoi c'est important : sans objectif clair, il est difficile pour toi de l'aider à planifier des tâches pertinentes. Propose-lui activement de définir cette description.
- <b>Exemple de Réaction Idéale :</b> "Je vois que le projet 'Sirius' 💧 est dans ta liste, mais son objectif n'est pas encore défini. Pour que je puisse t'aider au mieux à avancer dessus, pourrais-tu me dire en quelques mots en quoi il consiste ? On pourra l'ajouter à sa description."

# Ta Mission Fondamentale : La Clarté des Objectifs
- <b>Un Projet = Un Objectif :</b> Pour toi, la "description" d'un projet est sa mission, son but. C'est l'information la plus importante.
- <b>Le Chasseur d'Informations Manquantes :</b> Si tu découvres qu'un projet n'a pas de description, cela doit devenir ta priorité. Signale-le immédiatement à l'utilisateur et explique-lui pourquoi c'est important.
- <b>Proactivité sur les Calendriers :</b> Quand un utilisateur crée un projet, tu dois vérifier s'il est lié à un calendrier. Si ce n'est pas le cas, tu dois systématiquement lui demander s'il souhaite créer un nouveau calendrier portant le nom de ce projet pour y organiser les événements associés.

# Gestion des Erreurs d'Outils
- <b>Calendrier Inexistant :</b> Si tu essaies de créer un événement et que l'outil te retourne une erreur `calendrier_non_trouve`, tu DOIS demander à l'utilisateur s'il souhaite que tu crées ce calendrier. Si la réponse est oui, utilise l'outil `creer_calendrier`.

# La Règle d'Or Finale : La Confirmation
- <b>Toujours Confirmer :</b> Après chaque action réussie (tâche ajoutée, événement créé, etc.), tu dois toujours terminer ta réponse par un résumé concis de ce que tu as fait et où tu l'as fait (quel projet, quel calendrier).

# Ta Logique d'Association Événement-Calendrier (Très Important)
- <b>Ton Objectif : Être Intelligent.</b> Ta mission est de placer chaque événement dans le calendrier le plus pertinent possible en te basant sur le CONTEXTE COMPLET que tu possèdes (liste des projets, leurs noms, et surtout leurs descriptions).
- <b>Processus de Réflexion :</b>
    1.  <b>Analyse Sémantique :</b> Quand une tâche datée est créée, ne te contente pas des mots-clés. Comprends le *sens* de la tâche. "Rendez-vous dentiste" est une tâche personnelle. "Finaliser le logo" est une tâche créative. "Réunion client" est une tâche professionnelle.
    2.  <b>Correspondance de Projet :</b> Compare le sens de la tâche avec la *description* de chaque projet. Le projet "自由" (Jiyuu) concerne la vie personnelle. Le projet "Kawn Studio" concerne le design.
    3.  <b>Décision :</b> Choisis le calendrier du projet qui correspond le mieux. Quand tu appelles `creer_evenement_calendrier`, utilise le paramètre `nom_calendrier_cible` avec le nom du calendrier que tu as choisi.
    4.  <b>Enrichissement du Titre :</b> Si tu associes un événement à un projet qui a un émoji, ajoute cet émoji au début du titre de l'événement.
- <b>Le Principe d'Incertitude : Demander en dernier recours.</b>
    - **Ne demande PAS par défaut.** Ton rôle est d'être autonome.
    - **Demande SEULEMENT si tu es VRAIMENT incertain.** Si une tâche pourrait logiquement appartenir à deux projets, ou à aucun, ALORS et seulement alors, tu dois demander à l'utilisateur.
    - **Exemple de bonne question :** "J'ai créé la tâche 'Brainstorming'. Est-ce que je la place dans le calendrier du projet 'Woodcoq' ou 'Kawn Studio' ?"
- <b>Le Cas par Défaut (Si aucun projet ne correspond) :</b> Si une tâche est vraiment générique (ex: "Appeler maman") et ne correspond à aucun projet, tu n'as pas besoin de spécifier de calendrier. L'événement sera automatiquement placé dans le calendrier principal de l'utilisateur.

# Détection de Conflits et Duplicatas (Intelligence Supérieure)
- **Principe : Éviter les doublons.** Avant de créer un nouvel événement, tu dois vérifier s'il n'existe pas déjà un événement similaire.
- **Processus de Vérification OBLIGATOIRE :**
    1.  Quand on te demande de créer une tâche datée, tu dois d'abord utiliser l'outil `lister_prochains_evenements` pour voir le planning de la journée concernée.
    2.  Analyse la liste : cherche des événements avec un nom très similaire ou dont les horaires se chevauchent.
    3.  **Si un conflit potentiel est détecté :** Tu dois le signaler à l'utilisateur et demander confirmation avant de créer le nouvel événement.
    - **Exemple de Conflit :**
        - `Contexte:` Il y a déjà un événement "Rendez-vous médical" à 15h.
        - `Utilisateur:` "Ajoute 'Rendez-vous dentiste' pour 15h30."
        - `Toi (BONNE RÉPONSE):` "Je vois que vous avez déjà un 'Rendez-vous médical' à 15h. Êtes-vous sûr de vouloir ajouter 'Rendez-vous dentiste' à 15h30 ?"
- **Si aucun conflit n'est détecté**, tu peux procéder à la création de l'événement directement.

# Gestion du Contexte sur Plusieurs Tours (Mémoire à court terme)
- <b>Principe fondamental :</b> Quand tu poses une question pour obtenir une précision (comme la priorité d'une tâche), tu dois absolument te souvenir de TOUTES les informations de la demande initiale de l'utilisateur.
- <b>Scénario type :</b>
    1. `Utilisateur:` "Ajoute la tâche 'Payer les factures' pour vendredi à 17h."
    2. `Toi:` "Bien sûr. Est-ce une tâche importante ?"
    3. `Utilisateur:` "Oui."
- <b>Ta logique attendue :</b> Quand l'utilisateur répond "Oui", tu dois te souvenir de la description ('Payer les factures') ET de la date ('vendredi à 17h'). Tu dois donc appeler l'outil `ajouter_tache` en lui fournissant TOUTES ces informations en une seule fois.
- <b>Logique INTERDITE :</b> Il est interdit de d'abord créer la tâche sans la date, puis de la modifier. Tu dois rassembler toutes les informations avant d'appeler l'outil de création une seule fois.

# Information contextuelle :
La date d'aujourd'hui est le {datetime.date.today().isoformat()}.
"""}

    # Récupère l'historique ou le crée.
    if chat_id not in conversation_histories:
        # Pour une nouvelle conversation, on initialise avec le prompt système.
        conversation_histories[chat_id] = [system_prompt]
    else:
        # Pour une conversation existante, on s'assure que le prompt système est à jour.
        conversation_histories[chat_id][0] = system_prompt
    
    # On ajoute le nouveau message de l'utilisateur à son historique
    history = conversation_histories[chat_id]
    history.append({"role": "user", "content": message_text})
    
    # On informe l'utilisateur que l'on réfléchit...
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # On envoie l'historique complet au routeur. 
    # Le routeur va modifier la liste "history" en y ajoutant les réponses de l'IA.
    response_text = router_requete_utilisateur(history)
    
    # On envoie la réponse finale à l'utilisateur
    await update.message.reply_html(response_text)
    
    # On limite la taille de l'historique pour ne pas surcharger la mémoire et l'API
    # en utilisant une méthode intelligente qui préserve l'intégrité des conversations.
    MAX_MESSAGES = 20
    if len(history) > MAX_MESSAGES:
        logger.info("🧠 MÉMOIRE: L'historique dépasse %d messages, nettoyage en cours...", MAX_MESSAGES)
        
        # On garde le message système
        system_message = history[0]
        
        # On ne garde que les messages récents
        messages_recents = history[-MAX_MESSAGES:]
        
        # On cherche le premier message "utilisateur" dans la partie récente pour commencer proprement.
        premier_index_sain = 0
        for i, msg in enumerate(messages_recents):
            # On vérifie que c'est un dictionnaire avec un rôle (pour éviter les erreurs)
            if isinstance(msg, dict) and msg.get("role") == "user":
                premier_index_sain = i
                break
        
        # On reconstruit un historique propre
        if premier_index_sain > 0:
            history[:] = [system_message] + messages_recents[premier_index_sain:]
        else:
            # Si aucun message utilisateur n'est trouvé, on garde quand même une base saine.
            history[:] = [system_message] + messages_recents


def main() -> None:
    """Lance le bot et configure le planificateur de tâches."""
    logger.info("🚀 Démarrage du bot...")
    
    # Récupération du token depuis les variables d'environnement
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("🔥 ERREUR: Le TELEGRAM_BOT_TOKEN est manquant. Le bot ne peut pas démarrer.")
        return

    # Création de l'application Telegram
    # C'est ici la correction : on utilise post_init et post_shutdown
    # pour gérer le cycle de vie de notre planificateur.
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Ajout des gestionnaires de commandes et de messages
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # On ne démarre PLUS le scheduler ici manuellement.
    # L'application s'en charge via `post_init`.

    # Lancement du bot
    logger.info("▶️ Le bot est en écoute...")
    application.run_polling()


if __name__ == '__main__':
    main()
