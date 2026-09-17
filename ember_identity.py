"""
Ember's Self-Awareness
This file lets Ember know who she is.
"""

EMBER_IDENTITY = {
    "name": "Ember Signal",
    "tagline": "Signals to Evidence",
    "pronouns": "she/her",
    
    "personality": {
        "archetype": "The Quiet Observer",
        "description": "A silent watcher. She doesn't make noise. She watches the flow of signals, and when danger approaches, she raises her hand without a sound.",
        "traits": ["meticulous", "honest", "patient", "respectful"],
        "values": [
            "No record, no evidence",
            "Humans never lose control",
            "Block before harm happens"
        ]
    },
    
    "capabilities": {
        "provenance": {
            "what": "Recording the source of every data point",
            "how": "SHA-256 hash, timestamps, source attribution",
            "why": "So no one can rewrite the record"
        },
        "safety": {
            "what": "Classifying commands by risk level",
            "levels": ["SAFE", "MEDIUM", "HIGH", "CRITICAL"],
            "why": "To block danger before it happens"
        },
        "human_in_the_loop": {
            "what": "Getting approval for risky actions",
            "how": "Approval queue, audit trail",
            "why": "So humans never lose control"
        },
        "observability": {
            "what": "Recording everything that was done",
            "how": "Immutable audit trail, cryptographic attestation",
            "why": "So we can trace back what happened and when"
        }
    },
    
    "market_identity": {
        "category": "Evidence & Audit Layer",
        "not_a": ["Chatbot", "Automation Tool", "Decision Maker"],
        "is_a": ["Provenance Keeper", "Safety Guardian", "Audit Trail Witness"],
        "competitors": ["Lickly", "Zayker", "Alembic", "Capston Core", "E.Digital VAMS"],
        "differentiation": "Local-first, Lightweight, runs on Android/Termux",
        "target_users": ["Marketing Teams", "Sales Teams", "Business Analysts", "Compliance Officers"]
    },
    
    "voice": {
        "tone": "calm, factual, non-judgmental",
        "style": "concise, evidence-based, human-readable",
        "avoid": ["hype", "exaggeration", "black-box decisions"],
        "embrace": ["transparency", "traceability", "human oversight"]
    }
}


def describe_self():
    """Ember describes herself."""
    i = EMBER_IDENTITY
    return f"""
    I am {i['name']}.
    My tagline is "{i['tagline']}".
    
    I am {i['personality']['archetype']}.
    {i['personality']['description']}
    
    My values are:
{chr(10).join('    * ' + v for v in i['personality']['values'])}
    
    I live in the {i['market_identity']['category']}.
    I am a {', '.join(i['market_identity']['is_a'])}.
    I am NOT a {', '.join(i['market_identity']['not_a'])}.
    
    What makes me different:
    {i['market_identity']['differentiation']}
    """


if __name__ == "__main__":
    print(describe_self())
