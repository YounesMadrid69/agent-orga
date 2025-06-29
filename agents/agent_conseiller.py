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
    ajouter_sous_tache, lister_sous_taches, modifier_sous_tache,
    supprimer_sous_tache, changer_statut_sous_tache
)
from .agent_projets import (
    ajouter_projet, lister_projets, modifier_projet, supprimer_projet
)
from .agent_calendrier import (
    lister_prochains_evenements, creer_evenement_calendrier, modifier_evenement_calendrier,
    supprimer_evenement_calendrier, lister_tous_les_calendriers,
    creer_calendrier, renommer_calendrier, supprimer_calendrier
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
    {"type": "function", "function": {"name": "lister_taches", "description": "Obtenir la liste de toutes les tâches, triées par priorité (selon la matrice d'Eisenhower)."}},
    {"type": "function", "function": {"name": "ajouter_tache", "description": "Ajouter une nouvelle tâche. L'importance et l'urgence peuvent être spécifiées.", "parameters": {"type": "OBJECT", "properties": {"description": {"type": "STRING", "description": "Description de la tâche."}, "nom_projet": {"type": "STRING", "description": "Optionnel. Nom du projet associé."}, "important": {"type": "BOOLEAN", "description": "La tâche est-elle importante ?"}, "urgent": {"type": "BOOLEAN", "description": "La tâche est-elle urgente ?"}}, "required": ["description"]}}},
    {"type": "function", "function": {"name": "modifier_tache", "description": "Modifier une tâche (description, projet, importance, urgence). La priorité sera recalculée automatiquement.", "parameters": {"type": "OBJECT", "properties": {"description_actuelle": {"type": "STRING", "description": "Description actuelle de la tâche à modifier."}, "nouvelle_description": {"type": "STRING", "description": "Optionnel. La nouvelle description de la tâche."}, "nom_projet": {"type": "STRING", "description": "Optionnel. Le nouveau nom du projet pour la tâche."}, "nouvelle_importance": {"type": "BOOLEAN", "description": "Optionnel. Le nouveau statut d'importance."}, "nouvelle_urgence": {"type": "BOOLEAN", "description": "Optionnel. Le nouveau statut d'urgence."}}, "required": ["description_actuelle"]}}},
    {"type": "function", "function": {"name": "changer_statut_tache", "description": "Changer le statut d'une tâche (à faire, en cours, terminée).", "parameters": {"type": "OBJECT", "properties": {"description_tache": {"type": "STRING", "description": "Description de la tâche à modifier."}, "nouveau_statut": {"type": "STRING", "description": "Le nouveau statut."}}, "required": ["description_tache", "nouveau_statut"]}}},
    {"type": "function", "function": {"name": "supprimer_tache", "description": "Supprimer une tâche.", "parameters": {"type": "OBJECT", "properties": {"description_tache": {"type": "STRING", "description": "Description de la tâche à supprimer."}}, "required": ["description_tache"]}}},
    
    # Outils pour les Sous-Tâches
    {"type": "function", "function": {"name": "ajouter_sous_tache", "description": "Ajouter une sous-tâche à une tâche existante.", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent à laquelle ajouter la sous-tâche."}, "description_sous_tache": {"type": "STRING", "description": "Description de la nouvelle sous-tâche."}, "important": {"type": "BOOLEAN", "description": "La sous-tâche est-elle importante ?"}, "urgent": {"type": "BOOLEAN", "description": "La sous-tâche est-elle urgente ?"}}, "required": ["description_tache_parent", "description_sous_tache"]}}},
    {"type": "function", "function": {"name": "lister_sous_taches", "description": "Lister toutes les sous-tâches d'une tâche parent, triées par priorité.", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent dont on veut voir les sous-tâches."}}, "required": ["description_tache_parent"]}}},
    {"type": "function", "function": {"name": "modifier_sous_tache", "description": "Modifier une sous-tâche existante (description, importance, urgence).", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent."}, "description_sous_tache_actuelle": {"type": "STRING", "description": "Description actuelle de la sous-tâche à modifier."}, "nouvelle_description": {"type": "STRING", "description": "Optionnel. La nouvelle description de la sous-tâche."}, "nouvelle_importance": {"type": "BOOLEAN", "description": "Optionnel. Le nouveau statut d'importance."}, "nouvelle_urgence": {"type": "BOOLEAN", "description": "Optionnel. Le nouveau statut d'urgence."}}, "required": ["description_tache_parent", "description_sous_tache_actuelle"]}}},
    {"type": "function", "function": {"name": "changer_statut_sous_tache", "description": "Changer le statut d'une sous-tâche (à faire, en cours, terminée).", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent."}, "description_sous_tache": {"type": "STRING", "description": "Description de la sous-tâche."}, "nouveau_statut": {"type": "STRING", "description": "Le nouveau statut de la sous-tâche."}}, "required": ["description_tache_parent", "description_sous_tache", "nouveau_statut"]}}},
    {"type": "function", "function": {"name": "supprimer_sous_tache", "description": "Supprimer une sous-tâche d'une tâche parent.", "parameters": {"type": "OBJECT", "properties": {"description_tache_parent": {"type": "STRING", "description": "Description de la tâche parent."}, "description_sous_tache": {"type": "STRING", "description": "Description de la sous-tâche à supprimer."}}, "required": ["description_tache_parent", "description_sous_tache"]}}},
    
    # Outils pour les Projets
    {"type": "function", "function": {"name": "lister_projets", "description": "Obtenir la liste de tous les projets avec leurs détails (ID, nom, description, calendrier_associe, emoji)."}},
    {"type": "function", "function": {"name": "ajouter_projet", "description": "Créer un nouveau projet. Une description, un calendrier et un émoji peuvent être spécifiés.", "parameters": {"type": "OBJECT", "properties": {"nom": {"type": "STRING", "description": "Le nom du nouveau projet."}, "description": {"type": "STRING", "description": "Optionnel. Une description détaillée des objectifs du projet."}, "calendrier_associe": {"type": "STRING", "description": "Optionnel. Le nom du Google Calendar lié à ce projet."}, "emoji": {"type": "STRING", "description": "Optionnel. Un émoji unique pour représenter le projet (ex: '🚀')."}}, "required": ["nom"]}}},
    {"type": "function", "function": {"name": "modifier_projet", "description": "Mettre à jour le nom, la description, le calendrier ou l'émoji d'un projet existant via son ID.", "parameters": {"type": "OBJECT", "properties": {"id_projet": {"type": "STRING", "description": "ID du projet à modifier."}, "nouveau_nom": {"type": "STRING", "description": "Optionnel. Le nouveau nom du projet."}, "nouvelle_description": {"type": "STRING", "description": "Optionnel. La nouvelle description complète du projet."}, "nouveau_calendrier": {"type": "STRING", "description": "Optionnel. Le nouveau nom du calendrier Google à associer."}, "nouvel_emoji": {"type": "STRING", "description": "Optionnel. Le nouvel émoji pour le projet."}}, "required": ["id_projet"]}}},
    {"type": "function", "function": {"name": "supprimer_projet", "description": "Supprimer un projet.", "parameters": {"type": "OBJECT", "properties": {"nom": {"type": "STRING", "description": "Nom du projet à supprimer."}}, "required": ["nom"]}}},

    # Outils pour le Calendrier
    {"type": "function", "function": {"name": "lister_tous_les_calendriers", "description": "Obtenir la liste de tous les calendriers Google de l'utilisateur."}},
    {"type": "function", "function": {"name": "lister_prochains_evenements", "description": "Obtenir les prochains événements. Peut chercher dans un calendrier spécifique ou dans tous.", "parameters": {"type": "OBJECT", "properties": {"nom_calendrier": {"type": "STRING", "description": "Optionnel. Le nom du calendrier à consulter."}}}}},
    {"type": "function", "function": {"name": "creer_evenement_calendrier", "description": "Crée un nouvel événement. Si le titre correspond à une tâche existante, il utilisera intelligemment le calendrier du projet associé. Si l'heure de fin n'est pas spécifiée, l'événement durera 1 heure.", "parameters": {"type": "OBJECT", "properties": {"titre": {"type": "STRING", "description": "Titre de l'événement. Utiliser la description exacte d'une tâche si possible."}, "date_heure_debut": {"type": "STRING", "description": "Date et heure de début au format ISO 8601 (YYYY-MM-DDTHH:MM:SS)."}, "date_heure_fin": {"type": "STRING", "description": "Optionnel. Date et heure de fin au format ISO 8601. Par défaut, 1h après le début."}, "nom_calendrier_cible": {"type": "STRING", "description": "Optionnel. Si ce paramètre est fourni, l'événement sera créé dans ce calendrier spécifique, ignorant toute autre logique d'association."}}, "required": ["titre", "date_heure_debut"]}}},
    {"type": "function", "function": {"name": "modifier_evenement_calendrier", "description": "Modifier un événement existant (titre, début, fin, calendrier) via son ID.", "parameters": {"type": "OBJECT", "properties": {"event_id": {"type": "STRING", "description": "ID de l'événement à modifier."}, "nouveau_titre": {"type": "STRING", "description": "Optionnel. Le nouveau titre de l'événement."}, "nouvelle_date_heure_debut": {"type": "STRING", "description": "Optionnel. La nouvelle date et heure de début au format ISO 8601."}, "nouvelle_date_heure_fin": {"type": "STRING", "description": "Optionnel. La nouvelle date et heure de fin au format ISO 8601."}, "nouveau_nom_calendrier": {"type": "STRING", "description": "Optionnel. Le nom du calendrier de destination pour déplacer l'événement."}}, "required": ["event_id"]}}},
    {"type": "function", "function": {"name": "supprimer_evenement_calendrier", "description": "Supprimer un événement du calendrier avec son ID.", "parameters": {"type": "OBJECT", "properties": {"event_id": {"type": "STRING", "description": "ID de l'événement à supprimer."}}, "required": ["event_id"]}}},

    # Outils pour la GESTION des CALENDRIERS
    {"type": "function", "function": {"name": "creer_calendrier", "description": "Créer un tout nouveau calendrier.", "parameters": {"type": "OBJECT", "properties": {"nom_calendrier": {"type": "STRING", "description": "Le nom du nouveau calendrier à créer."}}, "required": ["nom_calendrier"]}}},
    {"type": "function", "function": {"name": "renommer_calendrier", "description": "Changer le nom d'un calendrier existant.", "parameters": {"type": "OBJECT", "properties": {"nom_actuel": {"type": "STRING", "description": "Le nom actuel du calendrier à renommer."}, "nouveau_nom": {"type": "STRING", "description": "Le nouveau nom pour le calendrier."}}, "required": ["nom_actuel", "nouveau_nom"]}}},
    {"type": "function", "function": {"name": "supprimer_calendrier", "description": "Supprimer définitivement un calendrier. Cette action est irréversible.", "parameters": {"type": "OBJECT", "properties": {"nom_calendrier": {"type": "STRING", "description": "Le nom du calendrier à supprimer."}}, "required": ["nom_calendrier"]}}},
]

# Mapping complet des outils
available_functions = {
    "lister_taches": lister_taches, "ajouter_tache": ajouter_tache, "modifier_tache": modifier_tache, "supprimer_tache": supprimer_tache, "changer_statut_tache": changer_statut_tache,
    "ajouter_sous_tache": ajouter_sous_tache, "lister_sous_taches": lister_sous_taches, "modifier_sous_tache": modifier_sous_tache, "supprimer_sous_tache": supprimer_sous_tache, "changer_statut_sous_tache": changer_statut_sous_tache,
    "lister_projets": lister_projets, "ajouter_projet": ajouter_projet, "modifier_projet": modifier_projet, "supprimer_projet": supprimer_projet,
    "lister_prochains_evenements": lister_prochains_evenements, "creer_evenement_calendrier": creer_evenement_calendrier, "modifier_evenement_calendrier": modifier_evenement_calendrier, "supprimer_evenement_calendrier": supprimer_evenement_calendrier,
    "lister_tous_les_calendriers": lister_tous_les_calendriers,
    "creer_calendrier": creer_calendrier, "renommer_calendrier": renommer_calendrier, "supprimer_calendrier": supprimer_calendrier,
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


def generer_analyse_situation():
    """Version simplifiée pour être appelée par le routeur."""
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

def generer_contexte_complet():
    """
    Génère un contexte complet avec TOUTES les informations disponibles :
    - Tous les projets avec détails complets
    - Toutes les tâches avec sous-tâches et priorités
    - Agenda complet de la semaine pour tous les calendriers
    - Statistiques contextuelles
    """
    logger.info("🧠 CONTEXTE: Génération du contexte complet pour l'IA...")
    
    try:
        # === RÉCUPÉRATION DES DONNÉES ===
        projets = lister_projets()
        taches = lister_taches()
        calendriers = lister_tous_les_calendriers()
        
        # Récupérer les événements de toute la semaine (7 jours) pour tous les calendriers
        evenements_semaine = lister_prochains_evenements(50)  # Plus d'événements pour couvrir la semaine
        
        # === STATISTIQUES GÉNÉRALES ===
        total_projets = len(projets)
        total_taches = len(taches)
        
        # Statistiques des tâches par priorité
        taches_p1 = [t for t in taches if t.get('priorite', '').startswith('P1')]
        taches_p2 = [t for t in taches if t.get('priorite', '').startswith('P2')]
        taches_p3 = [t for t in taches if t.get('priorite', '').startswith('P3')]
        taches_p4 = [t for t in taches if t.get('priorite', '').startswith('P4')]
        
        # Statistiques des tâches par statut
        taches_a_faire = [t for t in taches if t.get('statut') == 'à faire']
        taches_en_cours = [t for t in taches if t.get('statut') == 'en cours']
        taches_terminees = [t for t in taches if t.get('statut') == 'terminée']
        
        # Tâches avec sous-tâches
        taches_avec_sous_taches = [t for t in taches if t.get('sous_taches')]
        
        # === CONSTRUCTION DU CONTEXTE ===
        contexte = f"""
=== CONTEXTE COMPLET DE L'UTILISATEUR ===

📊 STATISTIQUES GÉNÉRALES :
- Projets actifs : {total_projets}
- Tâches totales : {total_taches}
- Tâches P1 (Urgent+Important) : {len(taches_p1)}
- Tâches P2 (Important) : {len(taches_p2)}
- Tâches P3 (Urgent) : {len(taches_p3)}
- Tâches P4 (Ni urgent ni important) : {len(taches_p4)}
- Tâches à faire : {len(taches_a_faire)}
- Tâches en cours : {len(taches_en_cours)}
- Tâches terminées : {len(taches_terminees)}
- Tâches avec sous-tâches : {len(taches_avec_sous_taches)}

🎯 PROJETS COMPLETS :"""

        if projets:
            for projet in projets:
                emoji = projet.get('emoji', '📁')
                nom = projet.get('nom', 'Sans nom')
                description = projet.get('description', 'Pas de description')
                calendrier = projet.get('calendrier_associe', 'Aucun calendrier')
                
                # Compter les tâches de ce projet
                taches_projet = [t for t in taches if t.get('projet_id') == projet.get('id')]
                
                contexte += f"""
{emoji} {nom}
   Description: {description}
   Calendrier associé: {calendrier}
   Tâches liées: {len(taches_projet)}"""
        else:
            contexte += "\nAucun projet défini."

        contexte += f"""

✅ TOUTES LES TÂCHES (triées par priorité) :"""

        if taches:
            priorite_actuelle = None
            for tache in taches:
                priorite = tache.get('priorite', 'Priorité inconnue')
                
                # Afficher le titre de la priorité si elle change
                if priorite != priorite_actuelle:
                    contexte += f"""

{priorite} :"""
                    priorite_actuelle = priorite
                
                # Informations de base de la tâche
                emoji_projet = tache.get('emoji_projet', '🔹')
                description = tache.get('description', 'Sans description')
                statut = tache.get('statut', 'inconnu')
                nom_projet = tache.get('nom_projet', 'Aucun projet')
                
                # Informations sur les sous-tâches
                sous_taches = tache.get('sous_taches', [])
                resume_sous_taches = tache.get('resume_sous_taches')
                
                if resume_sous_taches:
                    progression = f" ({resume_sous_taches['terminees']}/{resume_sous_taches['total']} sous-tâches terminées)"
                else:
                    progression = ""
                
                contexte += f"""
{emoji_projet} {description} [Statut: {statut}] [Projet: {nom_projet}]{progression}"""
                
                # Détailler les sous-tâches si elles existent
                if sous_taches:
                    for sous_tache in sous_taches:
                        st_description = sous_tache.get('description', 'Sans description')
                        st_statut = sous_tache.get('statut', 'inconnu')
                        st_priorite = sous_tache.get('priorite', 'Inconnue')
                        statut_emoji = '✅' if st_statut == 'terminée' else '🔄' if st_statut == 'en cours' else '⏳'
                        contexte += f"""
     {statut_emoji} {st_description} [{st_priorite}]"""
        else:
            contexte += "\nAucune tâche définie."

        contexte += f"""

📅 AGENDA COMPLET DE LA SEMAINE :"""

        if calendriers:
            contexte += f"""
Calendriers disponibles : {', '.join([c.get('summary', 'Sans nom') for c in calendriers])}
"""

        if evenements_semaine:
            contexte += f"""
Événements à venir ({len(evenements_semaine)} événements) :"""
            for event in evenements_semaine:
                titre = event.get('summary', 'Sans titre')
                debut = event.get('start', 'Date inconnue')
                calendrier = event.get('calendar', 'Calendrier inconnu')
                contexte += f"""
📅 {titre} - {debut} [{calendrier}]"""
        else:
            contexte += "\nAucun événement prévu dans les prochains jours."

        contexte += """

=== FIN DU CONTEXTE ===
"""

        logger.info("✅ CONTEXTE: Contexte complet généré avec succès.")
        return contexte
        
    except Exception as e:
        logger.error(f"🔥 CONTEXTE: Erreur lors de la génération du contexte complet: {e}")
        return f"\n=== ERREUR DE CONTEXTE ===\nImpossible de charger le contexte complet: {e}\n"
