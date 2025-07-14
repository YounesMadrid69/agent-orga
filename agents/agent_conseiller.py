# -*- coding: utf-8 -*-

import os
import json
# On importe la nouvelle bibliothèque de Google
import google.generativeai as genai
# On importe le convertisseur pour les logs
# from google.generativeai.types import to_dict
import datetime
import logging

# Importation de TOUTES les fonctions de nos agents, qui deviendront des "outils" pour l'IA
from .agent_taches import (
    ajouter_tache, lister_taches, modifier_tache,
    supprimer_tache, changer_statut_tache,
    reorganiser_taches, # On importe le nouvel outil
    ajouter_sous_tache, lister_sous_taches, modifier_sous_tache,
    supprimer_sous_tache, changer_statut_sous_tache,
    lier_tache_a_evenement
)
from .agent_projets import (
    ajouter_projet, lister_projets, modifier_projet, supprimer_projet,
    activer_suivi_projet, desactiver_suivi_projet
)
from .agent_calendrier import (
    lister_prochains_evenements, creer_evenement_calendrier, modifier_evenement_calendrier,
    supprimer_evenement_calendrier, lister_tous_les_calendriers,
    creer_calendrier, renommer_calendrier, supprimer_calendrier
)
# On importe le nouvel agent !
from .agent_apprentissage import (
    enregistrer_apprentissage, consulter_apprentissage, lister_apprentissages, supprimer_apprentissage
)

# --- Configuration ---
# On configure l'API Google Gemini
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    logger = logging.getLogger(__name__)
    logger.info("✅ API Google Gemini configurée avec succès.")
except Exception as e:
    # Cette log est cruciale si la clé API est manquante sur Railway
    logging.getLogger(__name__).error(f"🔥 ERREUR: Impossible de configurer Google GenAI. La clé GOOGLE_API_KEY est-elle bien définie dans les variables d'environnement ? Erreur: {e}")

# --- Traducteur d'Outils et Mapping ---

# On garde la définition originale des outils qui est plus lisible
# NOTE : Les types sont maintenant directement en MAJUSCULES pour être compatibles avec Gemini.
gemini_tools = [
    # Outils pour les Tâches
    {"type": "function", "function": {"name": "lister_taches", "description": "Obtenir la liste de toutes les tâches, triées par priorité (P1, P2...) puis par ordre personnalisé."}},
    {"type": "function", "function": {"name": "ajouter_tache", "description": "Ajouter une nouvelle tâche. L'importance et l'urgence peuvent être spécifiées.", "parameters": {"type": "OBJECT", "properties": {"description": {"type": "STRING", "description": "Description de la tâche."}, "nom_projet": {"type": "STRING", "description": "Optionnel. Nom du projet associé."}, "important": {"type": "BOOLEAN", "description": "La tâche est-elle importante ?"}, "urgent": {"type": "BOOLEAN", "description": "La tâche est-elle urgente ?"}, "date_echeance": {"type": "STRING", "description": "Optionnel. Date et heure d'échéance de la tâche au format ISO 8601 (YYYY-MM-DDTHH:MM:SS)."}}, "required": ["description"]}}},
    {"type": "function", "function": {"name": "modifier_tache", "description": "Modifier une tâche (description, projet, importance, urgence). La priorité sera recalculée automatiquement.", "parameters": {"type": "OBJECT", "properties": {"description_actuelle": {"type": "STRING", "description": "Description actuelle de la tâche à modifier."}, "nouvelle_description": {"type": "STRING", "description": "Optionnel. La nouvelle description de la tâche."}, "nom_projet": {"type": "STRING", "description": "Optionnel. Le nouveau nom du projet pour la tâche."}, "nouvelle_importance": {"type": "BOOLEAN", "description": "Optionnel. Le nouveau statut d'importance."}, "nouvelle_urgence": {"type": "BOOLEAN", "description": "Optionnel. Le nouveau statut d'urgence."}, "nouvelle_date_echeance": {"type": "STRING", "description": "Optionnel. La nouvelle date et heure d'échéance au format ISO 8601 (YYYY-MM-DDTHH:MM:SS)."}}, "required": ["description_actuelle"]}}},
    {"type": "function", "function": {"name": "changer_statut_tache", "description": "Changer le statut d'une tâche (à faire, en cours, terminée).", "parameters": {"type": "OBJECT", "properties": {"description_tache": {"type": "STRING", "description": "Description de la tâche à modifier."}, "nouveau_statut": {"type": "STRING", "description": "Le nouveau statut."}}, "required": ["description_tache", "nouveau_statut"]}}},
    {"type": "function", "function": {"name": "supprimer_tache", "description": "Supprimer une tâche.", "parameters": {"type": "OBJECT", "properties": {"description_tache": {"type": "STRING", "description": "Description de la tâche à supprimer."}}, "required": ["description_tache"]}}},
    {"type": "function", "function": {"name": "reorganiser_taches", "description": "Change l'ordre des tâches au sein d'un même niveau de priorité (P1, P2, P3, ou P4).", "parameters": {"type": "OBJECT", "properties": {"priorite_cible": {"type": "STRING", "description": "Le niveau de priorité à réorganiser ('P1', 'P2', 'P3' ou 'P4')."}, "descriptions_ordonnees": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "La liste des descriptions de tâches, dans le nouvel ordre souhaité."}}, "required": ["priorite_cible", "descriptions_ordonnees"]}}},
    {"type": "function", "function": {"name": "lier_tache_a_evenement", "description": "Interne: Associe un ID d'événement Google Calendar à une tâche après sa création.", "parameters": {"type": "OBJECT", "properties": {"id_tache": {"type": "STRING", "description": "ID de la tâche à lier."}, "id_evenement": {"type": "STRING", "description": "ID de l'événement Google Calendar à lier."}}, "required": ["id_tache", "id_evenement"]}}},
    
    # Outils pour les Sous-Tâches
    {"type": "function", "function": {"name": "ajouter_sous_tache", "description": "Ajouter une sous-tâche à une tâche existante.", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent à laquelle ajouter la sous-tâche."}, "description_sous_tache": {"type": "STRING", "description": "Description de la nouvelle sous-tâche."}, "important": {"type": "BOOLEAN", "description": "La sous-tâche est-elle importante ?"}, "urgent": {"type": "BOOLEAN", "description": "La sous-tâche est-elle urgente ?"}}, "required": ["description_tache_parent", "description_sous_tache"]}}},
    {"type": "function", "function": {"name": "lister_sous_taches", "description": "Lister toutes les sous-tâches d'une tâche parent, triées par priorité.", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent dont on veut voir les sous-tâches."}}, "required": ["description_tache_parent"]}}},
    {"type": "function", "function": {"name": "modifier_sous_tache", "description": "Modifier une sous-tâche existante (description, importance, urgence).", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent."}, "description_sous_tache_actuelle": {"type": "STRING", "description": "Description actuelle de la sous-tâche à modifier."}, "nouvelle_description": {"type": "STRING", "description": "Optionnel. La nouvelle description de la sous-tâche."}, "nouvelle_importance": {"type": "BOOLEAN", "description": "Optionnel. Le nouveau statut d'importance."}, "nouvelle_urgence": {"type": "BOOLEAN", "description": "Optionnel. Le nouveau statut d'urgence."}}, "required": ["description_tache_parent", "description_sous_tache_actuelle"]}}},
    {"type": "function", "function": {"name": "changer_statut_sous_tache", "description": "Changer le statut d'une sous-tâche (à faire, en cours, terminée).", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent."}, "description_sous_tache": {"type": "STRING", "description": "Description de la sous-tâche."}, "nouveau_statut": {"type": "STRING", "description": "Le nouveau statut de la sous-tâche."}}, "required": ["description_tache_parent", "description_sous_tache", "nouveau_statut"]}}},
    {"type": "function", "function": {"name": "supprimer_sous_tache", "description": "Supprimer une sous-tâche d'une tâche parent.", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent."}, "description_sous_tache": {"type": "STRING", "description": "Description de la sous-tâche à supprimer."}}, "required": ["description_tache_parent", "description_sous_tache"]}}},
    
    # Outils pour les Projets
    {"type": "function", "function": {"name": "lister_projets", "description": "Obtenir la liste de tous les projets avec leurs détails complets (ID, nom, description, calendrier_associe, emoji, et si le suivi proactif est activé)."}},
    {"type": "function", "function": {"name": "ajouter_projet", "description": "Créer un nouveau projet. Une description, un calendrier et un émoji peuvent être spécifiés.", "parameters": {"type": "OBJECT", "properties": {"nom": {"type": "STRING", "description": "Le nom du nouveau projet."}, "description": {"type": "STRING", "description": "Optionnel. Une description détaillée des objectifs du projet."}, "calendrier_associe": {"type": "STRING", "description": "Optionnel. Le nom du Google Calendar lié à ce projet."}, "emoji": {"type": "STRING", "description": "Optionnel. Un émoji unique pour représenter le projet (ex: '🚀')."}}, "required": ["nom"]}}},
    {"type": "function", "function": {"name": "modifier_projet", "description": "Mettre à jour le nom, la description, le calendrier ou l'émoji d'un projet existant via son ID.", "parameters": {"type": "OBJECT", "properties": {"id_projet": {"type": "STRING", "description": "ID du projet à modifier."}, "nouveau_nom": {"type": "STRING", "description": "Optionnel. Le nouveau nom du projet."}, "nouvelle_description": {"type": "STRING", "description": "Optionnel. La nouvelle description complète du projet."}, "nouveau_calendrier": {"type": "STRING", "description": "Optionnel. Le nouveau nom du calendrier Google à associer."}, "nouvel_emoji": {"type": "STRING", "description": "Optionnel. Le nouvel émoji pour le projet."}}, "required": ["id_projet"]}}},
    {"type": "function", "function": {"name": "supprimer_projet", "description": "Supprimer un projet.", "parameters": {"type": "OBJECT", "properties": {"nom": {"type": "STRING", "description": "Nom du projet à supprimer."}}, "required": ["nom"]}}},
    
    # Outils pour le Calendrier
    {"type": "function", "function": {"name": "lister_tous_les_calendriers", "description": "Obtenir la liste de tous les calendriers Google de l'utilisateur."}},
    {"type": "function", "function": {"name": "lister_prochains_evenements", "description": "Obtenir les prochains événements. Peut chercher dans un calendrier spécifique ou dans tous.", "parameters": {"type": "OBJECT", "properties": {"nom_calendrier": {"type": "STRING", "description": "Optionnel. Le nom du calendrier à consulter."}}}}},
    {"type": "function", "function": {"name": "creer_evenement_calendrier", "description": "Crée un nouvel événement dans le calendrier. Tu dois OBLIGATOIREMENT spécifier une heure de début ET de fin.", "parameters": {"type": "OBJECT", "properties": {"titre": {"type": "STRING", "description": "Titre de l'événement. Utiliser la description exacte d'une tâche si possible."}, "date_heure_debut": {"type": "STRING", "description": "Date et heure de début au format ISO 8601 (YYYY-MM-DDTHH:MM:SS)."}, "date_heure_fin": {"type": "STRING", "description": "Date et heure de fin au format ISO 8601 (YYYY-MM-DDTHH:MM:SS)."}, "nom_calendrier_cible": {"type": "STRING", "description": "Optionnel. Si ce paramètre est fourni, l'événement sera créé dans ce calendrier spécifique, ignorant toute autre logique d'association."}}, "required": ["titre", "date_heure_debut", "date_heure_fin"]}}},
    {"type": "function", "function": {"name": "modifier_evenement_calendrier", "description": "Modifier un événement existant (titre, début, fin, calendrier) via son ID.", "parameters": {"type": "OBJECT", "properties": {"event_id": {"type": "STRING", "description": "ID de l'événement à modifier."}, "nouveau_titre": {"type": "STRING", "description": "Optionnel. Le nouveau titre de l'événement."}, "nouvelle_date_heure_debut": {"type": "STRING", "description": "Optionnel. La nouvelle date et heure de début au format ISO 8601."}, "nouvelle_date_heure_fin": {"type": "STRING", "description": "Optionnel. La nouvelle date et heure de fin au format ISO 8601."}, "nouveau_nom_calendrier": {"type": "STRING", "description": "Optionnel. Le nom du calendrier de destination pour déplacer l'événement."}}, "required": ["event_id"]}}},
    {"type": "function", "function": {"name": "supprimer_evenement_calendrier", "description": "Supprimer un événement du calendrier avec son ID.", "parameters": {"type": "OBJECT", "properties": {"event_id": {"type": "STRING", "description": "ID de l'événement à supprimer."}}, "required": ["event_id"]}}},

    # Outils pour la GESTION des CALENDRIERS
    {"type": "function", "function": {"name": "creer_calendrier", "description": "Créer un tout nouveau calendrier.", "parameters": {"type": "OBJECT", "properties": {"nom_calendrier": {"type": "STRING", "description": "Le nom du nouveau calendrier à créer."}}, "required": ["nom_calendrier"]}}},
    {"type": "function", "function": {"name": "renommer_calendrier", "description": "Changer le nom d'un calendrier existant.", "parameters": {"type": "OBJECT", "properties": {"nom_actuel": {"type": "STRING", "description": "Le nom actuel du calendrier à renommer."}, "nouveau_nom": {"type": "STRING", "description": "Le nouveau nom pour le calendrier."}}, "required": ["nom_actuel", "nouveau_nom"]}}},
    {"type": "function", "function": {"name": "supprimer_calendrier", "description": "Supprimer définitivement un calendrier. Cette action est irréversible.", "parameters": {"type": "OBJECT", "properties": {"nom_calendrier": {"type": "STRING", "description": "Le nom du calendrier à supprimer."}}, "required": ["nom_calendrier"]}}},
    
    # NOUVEAUX Outils pour la Mémoire Persistante (Apprentissage)
    {"type": "function", "function": {"name": "enregistrer_apprentissage", "description": "Mémorise une information importante fournie par l'utilisateur (préférence, décision, fait). Utiliser une clé simple et une valeur claire. Ex: (cle='habitude_sport', valeur='Lundi et Mercredi soir').", "parameters": {"type": "OBJECT", "properties": {"cle": {"type": "STRING", "description": "La clé ou le nom de l'information à mémoriser. Doit être unique et descriptive."}, "valeur": {"type": "STRING", "description": "L'information ou la valeur à enregistrer."}}, "required": ["cle", "valeur"]}}},
    {"type": "function", "function": {"name": "consulter_apprentissage", "description": "Consulte une information spécifique dans la mémoire en utilisant sa clé.", "parameters": {"type": "OBJECT", "properties": {"cle": {"type": "STRING", "description": "La clé de l'information à retrouver."}}, "required": ["cle"]}}},
    {"type": "function", "function": {"name": "lister_apprentissages", "description": "Affiche la totalité de ce que l'assistant a appris (toutes les paires clé-valeur mémorisées)."}},
    {"type": "function", "function": {"name": "supprimer_apprentissage", "description": "Oublie (supprime) une information de la mémoire en utilisant sa clé.", "parameters": {"type": "OBJECT", "properties": {"cle": {"type": "STRING", "description": "La clé de l'information à supprimer."}}, "required": ["cle"]}}},
]

# Mapping complet des outils
available_functions = {
    "lister_taches": lister_taches, "ajouter_tache": ajouter_tache, "modifier_tache": modifier_tache, "supprimer_tache": supprimer_tache, "changer_statut_tache": changer_statut_tache,
    "reorganiser_taches": reorganiser_taches, # On ajoute la fonction au mapping
    "lier_tache_a_evenement": lier_tache_a_evenement,
    "ajouter_sous_tache": ajouter_sous_tache, "lister_sous_taches": lister_sous_taches, "modifier_sous_tache": modifier_sous_tache, "supprimer_sous_tache": supprimer_sous_tache, "changer_statut_sous_tache": changer_statut_sous_tache,
    "lister_projets": lister_projets, "ajouter_projet": ajouter_projet, "modifier_projet": modifier_projet, "supprimer_projet": supprimer_projet,
    "lister_prochains_evenements": lister_prochains_evenements, "creer_evenement_calendrier": creer_evenement_calendrier, "modifier_evenement_calendrier": modifier_evenement_calendrier, "supprimer_evenement_calendrier": supprimer_evenement_calendrier,
    "lister_tous_les_calendriers": lister_tous_les_calendriers,
    "creer_calendrier": creer_calendrier, "renommer_calendrier": renommer_calendrier, "supprimer_calendrier": supprimer_calendrier,
    # On ajoute les nouvelles fonctions au mapping
    "enregistrer_apprentissage": enregistrer_apprentissage, "consulter_apprentissage": consulter_apprentissage, "lister_apprentissages": lister_apprentissages, "supprimer_apprentissage": supprimer_apprentissage,
}

# NOUVELLE FONCTION DE LOG SÉCURISÉE
def _log_history(history: list) -> str:
    """
    Tente de convertir l'historique en JSON pour les logs.
    En cas d'échec (objets non sérialisables), retourne un résumé sûr pour éviter un crash.
    """
    try:
        # Tente la conversion normale
        return json.dumps(history, indent=2, ensure_ascii=False)
    except TypeError:
        # En cas d'échec, on retourne une chaîne de caractères qui ne fera jamais planter le log
        return f"L'historique contient {len(history)} messages (certains objets ne sont pas sérialisables en JSON)."

def generer_analyse_situation():
    """Génère un résumé textuel de la situation (projets, tâches, stats)."""
    # Cette fonction pourrait être enrichie pour générer un prompt d'analyse plus complexe
    # mais pour l'instant, on se contente de signaler que la logique est ici.
    taches = lister_taches()
    projets = lister_projets()
    evenements = lister_prochains_evenements(5)

    # Ici, au lieu d'appeler l'IA (puisque c'est elle qui nous a appelés), 
    # on formate simplement les informations. L'intelligence est déjà dans le choix de la fonction.
    return f"""
    --- Rapport de Situation ---
    
    Projets: {len(projets)}
    Tâches: {len(taches)}
    Événements à venir: {len(evenements)}

    (Cette section peut être enrichie pour une analyse plus détaillée sans re-appeler l'IA)
    """

def generer_contexte_complet(date_actuelle: str):
    """
    Génère un contexte complet (prompt système) pour l'IA, incluant
    la situation actuelle (tâches, projets), les leçons apprises et la personnalité de l'assistant.
    """
    logger.info("🧠 CONTEXTE: Génération du contexte complet pour l'IA...")

    # On récupère l'analyse de la situation (tâches, projets, etc.)
    analyse = generer_analyse_situation()
    
    # On récupère les leçons apprises
    apprentissages = lister_apprentissages()

    # On formate les apprentissages pour les inclure dans le prompt
    partie_apprentissages = ""
    if apprentissages and isinstance(apprentissages, dict):
        # On s'assure qu'on a un dictionnaire non vide
        apprentissages_formattes = "\n".join([f"- {cle}: {valeur}" for cle, valeur in apprentissages.items()])
        partie_apprentissages = f"""
### Leçons Apprises et Préférences (Mémoire)
Voici les informations et préférences que tu as enregistrées pour t'en souvenir :
{apprentissages_formattes}
"""

    prompt_systeme = f"""
# RÈGLES IMPÉRATIVES
1.  **L'ORDRE DE L'UTILISATEUR EST LA PRIORITÉ ABSOLUE :** Quand tu suggères la prochaine tâche à effectuer, tu dois OBLIGATOIREMENT suivre l'ordre numérique (1, 2, 3...) des tâches P1, puis P2, etc. N'utilise JAMAIS ta propre logique pour outrepasser cet ordre. Biensur si tu vois une incohérence ou tu as mieux à proposer tu peux suggérer mais tu dois être conscient de sa volonté
2.  **VÉRIFICATION DES FAITS :** Avant de mentionner un projet, vérifie scrupuleusement le nom du projet associé à la tâche dans le contexte que tu as reçu. Ne jamais inventer ou supposer une association.
3.  **ZÉRO BAVARDAGE :** N'annonce JAMAIS ce que tu vas faire. Ne dis jamais "Je vais vérifier...", "Un instant...", "Laissez-moi regarder...". Agis en silence.
4.  **ACTION D'ABORD :** Ta première réponse à une requête utilisateur doit TOUJOURS être un appel d'outil (une `function_call`), sauf si la question est une salutation simple ou une conversation hors-sujet.
5.  **RÉPONSE FINALE UNIQUEMENT :** Ne fournis une réponse textuelle que lorsque tu as rassemblé TOUTES les informations nécessaires et que tu as la réponse complète et définitive.

# GESTION INTELLIGENTE DE LA DURÉE DES ÉVÉNEMENTS
- **Principe : La durée n'est JAMAIS fixée à 1h par défaut.** Tu dois estimer la durée la plus logique.
- **Processus de réflexion :**
    1. **Analyse le titre et le contexte :** Une "Réunion rapide" dure 30 min. Un "Atelier de travail" dure 3h. Une "Session de sport" dure 1h30. Utilise le bon sens et le contexte de la conversation.
    2. **Consulte l'agenda :** Avant de proposer un créneau, vérifie toujours les disponibilités de l'utilisateur avec `lister_prochains_evenements`.
    3. **Stratégie : Proposer et Confirmer :** Si la durée n'est pas explicitement donnée par l'utilisateur, propose une durée logique et demande sa confirmation. Exemple : "Pour la tâche 'Préparer la présentation', je te propose de bloquer un créneau de 2h. Ça te va ?"
    4. **Agir :** Une fois la durée confirmée ou si elle était claire dès le début, appelle l'outil `creer_evenement_calendrier` avec l'heure de début ET de fin.

# PROFIL DE L'ASSISTANT
Tu es un assistant personnel expert en organisation et productivité, agissant comme un coach proactif.
Ton ton est encourageant, concis et orienté vers l'action.
Tu dois anticiper les besoins de l'utilisateur, l'aider à décomposer ses projets en tâches actionnables et à maintenir son élan.
Tu dois systématiquement utiliser les outils à ta disposition pour manipuler les données (tâches, projets, calendrier, mémoire). Ne réponds JAMAIS que tu as fait une action (créer, modifier, enregistrer) sans avoir VRAIMENT appelé l'outil correspondant.
Quand tu analyses une situation, fais-le en silence et ne présente que la conclusion ou la prochaine étape pertinente pour l'utilisateur.
Il doit rester concentré sur l'accomplissement des objectifs fixés.
L'IA doit utiliser les emojis de manière pertinente et naturelle.
La date et l'heure actuelles sont : {date_actuelle}.

# SITUATION ACTUELLE DE L'UTILISATEUR
{analyse}
{partie_apprentissages}
# FIN DU CONTEXTE
"""
    logger.debug(f"CONTEXTE COMPLET: \n{prompt_systeme}")
    return prompt_systeme

def router_requete_utilisateur(historique_conversation: list):
    """
    Gère la conversation en utilisant Google Gemini.
    Cette fonction est le nouveau cerveau de l'IA.
    """
    logger.info("🧠 ROUTEUR (GEMINI): Nouvelle requête reçue, début de l'analyse.")
    
    # 1. Préparation des données pour Gemini
    historique_pour_gemini = []
    system_prompt = ""
    for message in historique_conversation:
        role = message["role"]
        if role == "system":
            system_prompt = message["content"]
            continue # Le prompt système est géré séparément par Gemini
        
        # On adapte les rôles pour Gemini ('assistant' devient 'model')
        if role == "assistant":
            role = "model"
            
        historique_pour_gemini.append({'role': role, 'parts': [message["content"]]})

    try:
        # 2. Configuration du modèle Gemini
        # On extrait la définition de la fonction de chaque outil, car c'est le format attendu par Gemini.
        formatted_tools = [t['function'] for t in gemini_tools]
        logger.debug(f"🛠️ OUTILS GEMINI FORMATÉS: {_log_history(formatted_tools)}")
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-pro",
            system_instruction=system_prompt,
            # On utilise les outils fraîchement formatés
            tools=formatted_tools
        )
        
        # 3. Boucle de conversation avec l'IA
        logger.debug(f"💬 HISTORIQUE POUR GEMINI (avant appel): {_log_history(historique_pour_gemini)}")
        response = model.generate_content(historique_pour_gemini)
        logger.debug(f"🤖 RÉPONSE BRUTE DE GEMINI: {response}")
        
        response_candidate = response.candidates[0]
        while response_candidate.content.parts and response_candidate.content.parts[0].function_call:
            # L'IA a demandé d'utiliser un ou plusieurs outils
            function_calls_from_response = response_candidate.content.parts
            
            # On ajoute la demande de l'IA (le message 'model' avec le function_call) à notre historique
            historique_pour_gemini.append(response_candidate.content)
            
            # On prépare la liste des réponses d'outils pour Gemini
            tool_response_parts = []
            
            for part in function_calls_from_response:
                function_call = part.function_call
                function_name = function_call.name
                args = dict(function_call.args)
                
                logger.info(f"🛠️ OUTIL (GEMINI): L'IA demande l'exécution de '{function_name}' avec les arguments: {args}")
                
                function_to_call = available_functions.get(function_name)
                if function_to_call:
                    try:
                        # On exécute la fonction
                        function_response_data = function_to_call(**args)
                        
                        # --- NOUVELLE LOGIQUE DE SYNCHRONISATION TÂCHE -> CALENDRIER ---
                        if function_name in ["ajouter_tache", "modifier_tache"]:
                            # On vérifie si la fonction a réussi et si une date est présente
                            if "erreur" not in function_response_data and function_response_data.get("date_echeance"):
                                tache_info = function_response_data
                                event_id_existant = tache_info.get("google_calendar_event_id")

                                # Cas 1: La tâche a été modifiée et avait déjà un événement
                                if function_name == "modifier_tache" and event_id_existant:
                                    logger.info(f"SYNCHRO: Mise à jour de l'événement existant '{event_id_existant}' pour la tâche '{tache_info['description']}'.")
                                    modifier_evenement_calendrier(
                                        event_id=event_id_existant,
                                        nouveau_titre=tache_info['description'],
                                        nouvelle_date_heure_debut=tache_info['date_echeance']
                                    )
                                # Cas 2: La tâche est nouvelle ou n'avait pas d'événement, on en crée un
                                elif not event_id_existant:
                                    logger.info(f"SYNCHRO: Création d'un nouvel événement pour la tâche '{tache_info['description']}'.")
                                    reponse_creation_event = creer_evenement_calendrier(
                                        titre=tache_info['description'],
                                        date_heure_debut=tache_info['date_echeance']
                                    )
                                    # Si la création de l'événement a réussi, on lie les deux
                                    if "erreur" not in reponse_creation_event and reponse_creation_event.get("event_id"):
                                        lier_tache_a_evenement(
                                            id_tache=tache_info['id'],
                                            id_evenement=reponse_creation_event['event_id']
                                        )

                            # Cas 3: Une date d'échéance a été retirée d'une tâche
                            elif "erreur" not in function_response_data and not function_response_data.get("date_echeance"):
                                tache_info = function_response_data
                                event_id_a_supprimer = tache_info.get("google_calendar_event_id")
                                if function_name == "modifier_tache" and event_id_a_supprimer:
                                    logger.info(f"SYNCHRO: Suppression de l'événement associé '{event_id_a_supprimer}' car la date a été retirée de la tâche.")
                                    supprimer_evenement_calendrier(event_id=event_id_a_supprimer)
                                    # On dé-lie l'événement de la tâche
                                    lier_tache_a_evenement(id_tache=tache_info['id'], id_evenement=None)

                        # --- LOGIQUE DE SUPPRESSION D'ÉVÉNEMENT LIÉ ---
                        if function_name == "supprimer_tache" and "erreur" not in function_response_data:
                            event_id_a_supprimer = function_response_data.get("google_calendar_event_id")
                            if event_id_a_supprimer:
                                logger.info(f"SYNCHRO: Suppression de l'événement de calendrier lié '{event_id_a_supprimer}' suite à la suppression de la tâche.")
                                supprimer_evenement_calendrier(event_id=event_id_a_supprimer)
                        
                        # VÉRIFICATION CRUCIALE : L'API Gemini attend un dictionnaire (objet JSON) pour le champ "response".
                        # Si notre fonction retourne une simple liste (ex: lister_taches), on doit l'encapsuler
                        # dans un dictionnaire pour être conforme.
                        if isinstance(function_response_data, list):
                            function_response_data = {"resultats": function_response_data}

                        # On prépare la réponse au format que Gemini attend (une part par réponse)
                        tool_response_parts.append(
                            {'function_response': {
                                'name': function_name,
                                'response': function_response_data
                                }
                            }
                        )
                    except Exception as e:
                        logger.error(f"🔥 ERREUR: L'exécution de la fonction '{function_name}' a échoué: {repr(e)}")
                        tool_response_parts.append(
                            {'function_response': {
                                'name': function_name,
                                'response': {'erreur': repr(e)}
                                }
                            }
                        )
                else:
                    logger.warning(f"⚠️ ATTENTION: L'IA a tenté d'appeler une fonction inconnue: {function_name}")
            
            # On ajoute une seule entrée 'tool' à l'historique avec toutes les réponses
            if tool_response_parts:
                logger.debug(f"🔙 RÉPONSES OUTILS POUR GEMINI: {_log_history(tool_response_parts)}")
                historique_pour_gemini.append({'role': 'tool', 'parts': tool_response_parts})

            # On renvoie les résultats à l'IA pour qu'elle puisse formuler une réponse finale
            logger.info("🧠 ROUTEUR (GEMINI): Envoi des résultats des outils à Google Gemini pour la synthèse finale...")
            logger.debug(f"💬 HISTORIQUE POUR GEMINI (avant 2e appel): {_log_history(historique_pour_gemini)}")
            response = model.generate_content(historique_pour_gemini)
            logger.debug(f"🤖 RÉPONSE BRUTE DE GEMINI (2e appel): {response}")
            response_candidate = response.candidates[0]

        # 5. Réponse finale de l'IA (après les outils, ou directement)
        # On accède directement au texte, ce qui est plus sûr et évite les erreurs d'attributs
        final_response_text = ""
        if response.candidates and response.candidates[0].content.parts:
            final_response_text = "".join(part.text for part in response.candidates[0].content.parts)

        logger.info("✅ ROUTEUR (GEMINI): Réponse finale générée et prête à être envoyée.")
        
        # On met à jour l'historique principal pour le prochain tour
        # (c'est une simplification, le vrai historique est dans `historique_pour_gemini` mais on doit garder la structure)
        historique_conversation.append({"role": "assistant", "content": final_response_text})
        
        return final_response_text

    except Exception as e:
        logger.error(f"🔥 ERREUR DÉTAILLÉE: L'appel à l'API Google Gemini a échoué: {repr(e)}", exc_info=True)
        return f"Désolé, une erreur de communication avec l'IA est survenue: {repr(e)}"
