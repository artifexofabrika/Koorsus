"""Personal Knowledge Graph – living memory of the user."""
import json, os, datetime

GRAPH_FILE = os.path.expanduser("~/personal_graph.json")

DEFAULT_GRAPH = {
    "identity": {
        "name": "",
        "preferred_address": "sir",
        "age": None,
        "location": "",
        "languages": [],
        "personality": ""
    },
    "biography": {
        "early_life": "",
        "career": [],
        "significant_events": []
    },
    "health_and_wellness": {
        "medications": [],
        "weight": None,
        "height": None,
        "physical_concerns": [],
        "exercise": "",
        "dietary_preferences": ""
    },
    "current_projects": {
        "primary": "",
        "description": "",
        "status": "",
        "deadline": ""
    },
    "emotional_state": {
        "current_mood": "",
        "recent_stressors": [],
        "recent_accomplishments": [],
        "support_network": ""
    },
    "conversation_memory": [],
    "preferences_and_quirks": {
        "favorite_writer": "",
        "communication_style": "",
        "technology_stance": "",
        "coffee": "",
        "philosophy": ""
    }
}

def load_graph():
    """Return the current personal knowledge graph, creating a default if missing."""
    if not os.path.exists(GRAPH_FILE):
        save_graph(DEFAULT_GRAPH)
        return DEFAULT_GRAPH.copy()
    with open(GRAPH_FILE, "r") as f:
        return json.load(f)

def save_graph(graph):
    with open(GRAPH_FILE, "w") as f:
        json.dump(graph, f, indent=2)

def update_field(path, value):
    """Update a dot-separated field, e.g. 'identity.name'."""
    graph = load_graph()
    parts = path.split(".")
    node = graph
    for part in parts[:-1]:
        if part not in node:
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value
    save_graph(graph)
    return graph

def add_conversation_memory(summary, sentiment="neutral"):
    """Add a timestamped entry to the conversation memory."""
    graph = load_graph()
    mem = graph.setdefault("conversation_memory", [])
    mem.append({
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": summary,
        "sentiment": sentiment
    })
    # Keep last 30 entries
    graph["conversation_memory"] = mem[-30:]
    save_graph(graph)

def graph_summary():
    """Return a concise text summary of the entire graph for injection into prompts."""
    g = load_graph()
    parts = []
    identity = g.get("identity", {})
    if identity.get("name"):
        parts.append(f"User's name is {identity['name']}. Preferred address: {identity.get('preferred_address','sir')}.")
    bio = g.get("biography", {})
    if bio.get("career"):
        parts.append("Career: " + "; ".join(bio["career"]))
    if bio.get("significant_events"):
        parts.append("Life events: " + "; ".join(bio["significant_events"]))
    health = g.get("health_and_wellness", {})
    if health.get("medications"):
        meds = ", ".join([f"{m['drug']} {m['dosage']}" if isinstance(m, dict) else m for m in health["medications"]])
        parts.append(f"Medications: {meds}.")
    if health.get("weight"):
        parts.append(f"Weight: {health['weight']} kg.")
    projects = g.get("current_projects", {})
    if projects.get("primary"):
        parts.append(f"Current project: {projects['primary']} – {projects.get('description','')}")
    emotional = g.get("emotional_state", {})
    if emotional.get("current_mood"):
        parts.append(f"Mood: {emotional['current_mood']}")
    if emotional.get("recent_accomplishments"):
        parts.append("Recent accomplishments: " + "; ".join(emotional["recent_accomplishments"]))
    prefs = g.get("preferences_and_quirks", {})
    if prefs.get("coffee"):
        parts.append(f"Coffee habit: {prefs['coffee']}")
    if prefs.get("philosophy"):
        parts.append(f"Personal philosophy: {prefs['philosophy']}")
    # Include any custom facts
    custom = g.get("custom_facts", {})
    if custom:
        for k, v in custom.items():
            parts.append(f"{k}: {v}")
    return "\n".join(parts)
