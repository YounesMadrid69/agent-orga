# -*- coding: utf-8 -*-

import os
import json
from openai import OpenAI
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
    supprimer_evenement_calendrier, lister_tous_les_calendriers
)

# --- Configuration ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logger = logging.getLogger(__name__)


# --- Définition de la "Boîte à Outils" Complète ---
tools = [
    # Outils pour les Tâches
    {"type": "function", "function": {"name": "lister_taches", "description": "Obtenir la liste de toutes les tâches, triées par priorité (selon la matrice d'Eisenhower)."}},
    {"type": "function", "function": {"name": "ajouter_tache", "description": "Ajouter une nouvelle tâche. L'importance et l'urgence peuvent être spécifiées.", "parameters": {"type": "object", "properties": {"description": {"type": "string", "description": "Description de la tâche."}, "nom_projet": {"type": "string", "description": "Optionnel. Nom du projet associé."}, "important": {"type": "boolean", "description": "La tâche est-elle importante ?"}, "urgent": {"type": "boolean", "description": "La tâche est-elle urgente ?"}}, "required": ["description"]}}},
    {"type": "function", "function": {"name": "modifier_tache", "description": "Modifier une tâche (description, projet, importance, urgence). La priorité sera recalculée automatiquement.", "parameters": {"type": "object", "properties": {"description_actuelle": {"type": "string", "description": "Description actuelle de la tâche à modifier."}, "nouvelle_description": {"type": "string", "description": "Optionnel. La nouvelle description de la tâche."}, "nom_projet": {"type": "string", "description": "Optionnel. Le nouveau nom du projet pour la tâche."}, "nouvelle_importance": {"type": "boolean", "description": "Optionnel. Le nouveau statut d'importance."}, "nouvelle_urgence": {"type": "boolean", "description": "Optionnel. Le nouveau statut d'urgence."}}, "required": ["description_actuelle"]}}},
    {"type": "function", "function": {"name": "changer_statut_tache", "description": "Changer le statut d'une tâche (à faire, en cours, terminée).", "parameters": {"type": "object", "properties": {"description_tache": {"type": "string", "description": "Description de la tâche à modifier."}, "nouveau_statut": {"type": "string", "description": "Le nouveau statut."}}, "required": ["description_tache", "nouveau_statut"]}}},
    {"type": "function", "function": {"name": "supprimer_tache", "description": "Supprimer une tâche.", "parameters": {"type": "object", "properties": {"description_tache": {"type": "string", "description": "Description de la tâche à supprimer."}}, "required": ["description_tache"]}}},
    
    # Outils pour les Sous-Tâches
    {"type": "function", "function": {"name": "ajouter_sous_tache", "description": "Ajouter une sous-tâche à une tâche existante.", "parameters": {"type": "object", "properties": {"description_tache_parent": {"type": "string", "description": "Description de la tâche parent à laquelle ajouter la sous-tâche."}, "description_sous_tache": {"type": "string", "description": "Description de la nouvelle sous-tâche."}, "important": {"type": "boolean", "description": "La sous-tâche est-elle importante ?"}, "urgent": {"type": "boolean", "description": "La sous-tâche est-elle urgente ?"}}, "required": ["description_tache_parent", "description_sous_tache"]}}},
    {"type": "function", "function": {"name": "lister_sous_taches", "description": "Lister toutes les sous-tâches d'une tâche parent, triées par priorité.", "parameters": {"type": "object", "properties": {"description_tache_parent": {"type": "string", "description": "Description de la tâche parent dont on veut voir les sous-tâches."}}, "required": ["description_tache_parent"]}}},
    {"type": "function", "function": {"name": "modifier_sous_tache", "description": "Modifier une sous-tâche existante (description, importance, urgence).", "parameters": {"type": "object", "properties": {"description_tache_parent": {"type": "string", "description": "Description de la tâche parent."}, "description_sous_tache_actuelle": {"type": "string", "description": "Description actuelle de la sous-tâche à modifier."}, "nouvelle_description": {"type": "string", "description": "Optionnel. La nouvelle description de la sous-tâche."}, "nouvelle_importance": {"type": "boolean", "description": "Optionnel. Le nouveau statut d'importance."}, "nouvelle_urgence": {"type": "boolean", "description": "Optionnel. Le nouveau statut d'urgence."}}, "required": ["description_tache_parent", "description_sous_tache_actuelle"]}}},
    {"type": "function", "function": {"name": "changer_statut_sous_tache", "description": "Changer le statut d'une sous-tâche (à faire, en cours, terminée).", "parameters": {"type": "object", "properties": {"description_tache_parent": {"type": "string", "description": "Description de la tâche parent."}, "description_sous_tache": {"type": "string", "description": "Description de la sous-tâche."}, "nouveau_statut": {"type": "string", "description": "Le nouveau statut de la sous-tâche."}}, "required": ["description_tache_parent", "description_sous_tache", "nouveau_statut"]}}},
    {"type": "function", "function": {"name": "supprimer_sous_tache", "description": "Supprimer une sous-tâche d'une tâche parent.", "parameters": {"type": "object", "properties": {"description_tache_parent": {"type": "string", "description": "Description de la tâche parent."}, "description_sous_tache": {"type": "string", "description": "Description de la sous-tâche à supprimer."}}, "required": ["description_tache_parent", "description_sous_tache"]}}},
    
    # Outils pour les Projets
    {"type": "function", "function": {"name": "lister_projets", "description": "Obtenir la liste de tous les projets avec leurs détails (ID, nom, description, calendrier_associe, emoji)."}},
    {"type": "function", "function": {"name": "ajouter_projet", "description": "Créer un nouveau projet. Une description, un calendrier et un émoji peuvent être spécifiés.", "parameters": {"type": "object", "properties": {"nom": {"type": "string", "description": "Le nom du nouveau projet."}, "description": {"type": "string", "description": "Optionnel. Une description détaillée des objectifs du projet."}, "calendrier_associe": {"type": "string", "description": "Optionnel. Le nom du Google Calendar lié à ce projet."}, "emoji": {"type": "string", "description": "Optionnel. Un émoji unique pour représenter le projet (ex: '🚀')."}}, "required": ["nom"]}}},
    {"type": "function", "function": {"name": "modifier_projet", "description": "Mettre à jour le nom, la description, le calendrier ou l'émoji d'un projet existant via son ID.", "parameters": {"type": "object", "properties": {"id_projet": {"type": "string", "description": "ID du projet à modifier."}, "nouveau_nom": {"type": "string", "description": "Optionnel. Le nouveau nom du projet."}, "nouvelle_description": {"type": "string", "description": "Optionnel. La nouvelle description complète du projet."}, "nouveau_calendrier": {"type": "string", "description": "Optionnel. Le nouveau nom du calendrier Google à associer."}, "nouvel_emoji": {"type": "string", "description": "Optionnel. Le nouvel émoji pour le projet."}}, "required": ["id_projet"]}}},
    {"type": "function", "function": {"name": "supprimer_projet", "description": "Supprimer un projet.", "parameters": {"type": "object", "properties": {"nom": {"type": "string", "description": "Nom du projet à supprimer."}}, "required": ["nom"]}}},

    # Outils pour le Calendrier
    {"type": "function", "function": {"name": "lister_tous_les_calendriers", "description": "Obtenir la liste de tous les calendriers Google de l'utilisateur."}},
    {"type": "function", "function": {"name": "lister_prochains_evenements", "description": "Obtenir les prochains événements. Peut chercher dans un calendrier spécifique ou dans tous.", "parameters": {"type": "object", "properties": {"nom_calendrier": {"type": "string", "description": "Optionnel. Le nom du calendrier à consulter."}}}}},
    {"type": "function", "function": {"name": "creer_evenement_calendrier", "description": "Crée un nouvel événement. Si le titre correspond à une tâche existante, il utilisera intelligemment le calendrier du projet associé à cette tâche.", "parameters": {"type": "object", "properties": {"titre": {"type": "string", "description": "Titre de l'événement. Si cela correspond à une tâche, utilise sa description exacte."}, "date_heure_debut": {"type": "string", "description": "Date et heure de début au format ISO 8601 (YYYY-MM-DDTHH:MM:SS)."}, "date_heure_fin": {"type": "string", "description": "Date et heure de fin au format ISO 8601 (YYYY-MM-DDTHH:MM:SS)."}}, "required": ["titre", "date_heure_debut", "date_heure_fin"]}}},
    {"type": "function", "function": {"name": "modifier_evenement_calendrier", "description": "Modifier un événement existant (titre, début, fin) via son ID.", "parameters": {"type": "object", "properties": {"event_id": {"type": "string", "description": "ID de l'événement à modifier."}, "nouveau_titre": {"type": "string", "description": "Optionnel. Le nouveau titre de l'événement."}, "nouvelle_date_heure_debut": {"type": "string", "description": "Optionnel. La nouvelle date et heure de début au format ISO 8601."}, "nouvelle_date_heure_fin": {"type": "string", "description": "Optionnel. La nouvelle date et heure de fin au format ISO 8601."}}, "required": ["event_id"]}}},
    {"type": "function", "function": {"name": "supprimer_evenement_calendrier", "description": "Supprimer un événement du calendrier avec son ID.", "parameters": {"type": "object", "properties": {"event_id": {"type": "string", "description": "ID de l'événement à supprimer."}}, "required": ["event_id"]}}},
]

# Mapping complet des outils
available_functions = {
    "lister_taches": lister_taches, "ajouter_tache": ajouter_tache, "modifier_tache": modifier_tache, "supprimer_tache": supprimer_tache, "changer_statut_tache": changer_statut_tache,
    "ajouter_sous_tache": ajouter_sous_tache, "lister_sous_taches": lister_sous_taches, "modifier_sous_tache": modifier_sous_tache, "supprimer_sous_tache": supprimer_sous_tache, "changer_statut_sous_tache": changer_statut_sous_tache,
    "lister_projets": lister_projets, "ajouter_projet": ajouter_projet, "modifier_projet": modifier_projet, "supprimer_projet": supprimer_projet,
    "lister_prochains_evenements": lister_prochains_evenements, "creer_evenement_calendrier": creer_evenement_calendrier, "modifier_evenement_calendrier": modifier_evenement_calendrier, "supprimer_evenement_calendrier": supprimer_evenement_calendrier,
    "lister_tous_les_calendriers": lister_tous_les_calendriers,
}


# --- Le Cerveau / Routeur Amélioré ---

def router_requete_utilisateur(historique_conversation: list):
    """
    Gère la conversation en se souvenant du contexte et en utilisant les outils
    de manière conversationnelle. Cette version est plus robuste car elle
    travaille sur une copie de l'historique pour éviter les états incohérents.
    """
    logger.info("🧠 ROUTEUR: Nouvelle requête reçue, début de l'analyse.")
    
    # On travaille sur une copie de l'historique pour ce tour de conversation.
    messages = list(historique_conversation)
    logger.debug(f"🧠 ROUTEUR: Historique entrant pour analyse (contient {len(messages)} messages).")


    # Étape 1 : On envoie l'historique de la conversation et les outils à l'IA
    try:
        logger.info("🧠 ROUTEUR: Envoi des informations à OpenAI pour obtenir une décision...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        response_message = response.choices[0].message
    except Exception as e:
        logger.error(f"🔥 ERREUR: L'appel à l'API OpenAI (étape 1) a échoué: {e}")
        return f"Désolé, une erreur de communication est survenue: {e}"

    # On ajoute la réponse de l'IA (qui peut contenir du texte ou des appels d'outils)
    messages.append(response_message)
    
    tool_calls = response_message.tool_calls
    
    # Étape 2 : Si l'IA ne veut pas utiliser d'outil, on met à jour l'historique principal et on retourne la réponse.
    if not tool_calls:
        logger.info("🤖 DÉCISION IA: Répondre directement sans utiliser d'outil.")
        logger.debug(f"Contenu de la réponse directe : {response_message.content}")
        # On met à jour l'historique principal avec la réponse de l'IA.
        historique_conversation.append(response_message)
        return response_message.content

    # Étape 3 : Si l'IA veut utiliser un ou plusieurs outils, on les exécute
    logger.info(f"🤖 DÉCISION IA: Demande d'utilisation d'outil(s): {[tc.function.name for tc in tool_calls]}")
    
    # On prépare une liste pour ne stocker QUE les nouveaux messages d'outils de ce tour
    tool_messages = []
    
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_to_call = available_functions.get(function_name)
        
        if function_to_call:
            try:
                function_args = json.loads(tool_call.function.arguments)
                logger.info(f"🛠️ OUTIL: Exécution de la fonction '{function_name}' avec les arguments: {function_args}")
                function_response = function_to_call(**function_args)
                logger.debug(f"🛠️ OUTIL: Résultat brut de '{function_name}': {function_response}")
                
                # On ajoute le résultat de l'outil à notre liste temporaire
                tool_messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(function_response, ensure_ascii=False),
                })
            except Exception as e:
                logger.error(f"🔥 ERREUR: L'exécution de la fonction '{function_name}' a échoué: {e}")
                tool_messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps({"erreur": str(e)}, ensure_ascii=False),
                })
        else:
            logger.warning(f"⚠️ ATTENTION: L'IA a tenté d'appeler une fonction inconnue: {function_name}")
            tool_messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": json.dumps({"erreur": "Fonction non implémentée"}, ensure_ascii=False),
            })

    # On ajoute les résultats des outils à l'historique temporaire pour l'IA
    messages.extend(tool_messages)

    # Étape 4 : On renvoie TOUT l'historique temporaire mis à jour à l'IA pour qu'il formule une réponse finale
    logger.info("🧠 ROUTEUR: Envoi des résultats des outils à OpenAI pour la synthèse finale...")
    try:
        second_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )
        final_response_message = second_response.choices[0].message
        
        # Maintenant que tout le cycle est terminé, on met à jour l'historique principal
        # avec l'ensemble de l'échange (appel d'outil, résultat, réponse finale).
        historique_conversation.append(response_message)
        # On ajoute uniquement les nouveaux messages d'outils de ce tour
        historique_conversation.extend(tool_messages)
        historique_conversation.append(final_response_message)

        logger.info("✅ ROUTEUR: Réponse finale générée et prête à être envoyée.")
        logger.debug(f"Contenu de la réponse finale : {final_response_message.content}")
        return final_response_message.content
    except Exception as e:
        logger.error(f"🔥 ERREUR: L'appel à l'API OpenAI (étape 2) a échoué: {e}")
        return f"Désolé, une erreur est survenue après l'exécution de l'action: {e}"


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
