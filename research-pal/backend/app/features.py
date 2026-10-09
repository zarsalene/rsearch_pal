"""Feature switches. Each new feature has a switch in Settings, so a problem in one feature does not block the app.
The list of features is in REGISTRY. The table "features" keeps only the choice of the student. A feature without a row uses its default."""
from fastapi import HTTPException

from . import db

# name -> label, description, default. Add one entry for each new feature.
REGISTRY: dict[str, dict] = {
    "chat": {"label": "Chat", "description": "Ask questions about your papers. Each answer shows its quotes.", "default": True},
    "direction": {"label": "Thesis direction", "description": "Thesis title bar, question helper, sub-questions and paper tags.", "default": True},
    "simple": {"label": "Simple mode", "description": "A switch in the top bar. In Simple mode, the AI texts have shorter sentences and explain the hard terms.", "default": True},
    "feynman": {"label": "Explain it to me", "description": "Write the main idea of a paper in your own words. The AI shows what is right, partly right or wrong, with quotes.", "default": True},
    "eli12": {"label": "Like I am 12", "description": "A simple text, an example and an analogy for one field of a card.", "default": True},
    "quiz": {"label": "Quiz me", "description": "Questions about a paper. Each question has a quote from the PDF as its source.", "default": True},
    "today": {"label": "Today page", "description": "The home page: your goal, three tasks, one next best action, a focus timer and your wins.", "default": True},
    "game": {"label": "Game: points, levels and streak", "description": "Points for real work that the server checks. Levels, a kind streak, badges and your own rewards.", "default": True},
    "review": {"label": "Knowledge Garden: spaced review", "description": "Review your cards, words and quiz questions on the right day. One plant for each paper.", "default": True},
    "map": {"label": "PhD Expedition map", "description": "A map of the PhD road with six regions. Each region fills with color as you work.", "default": True},
    "quests": {"label": "Weekly quests and boss fights", "description": "Each week you choose up to 2 of 3 quests. Mark a hard paper as a boss and defeat it. A quest you do not finish has no penalty.", "default": True},
    "duck": {"label": "Duck companion", "description": "A small Duck in the Understand tab. You explain ideas to it. It gives short, kind messages.", "default": True},
    "cite": {"label": "Citations and metadata", "description": "Authors, year, venue and DOI of each paper. BibTeX and RIS export. A citation with a page number.", "default": True},
    "litreview": {"label": "Literature review builder", "description": "An outline from your sub-questions, an editor, and the checked quotes of your cards. You write the text.", "default": True},
    "glossary": {"label": "Word helper and glossary", "description": "Select a word to see what it means. Save the word in your glossary.", "default": True},
}


def is_enabled(name: str) -> bool:
    if name not in REGISTRY:
        return False
    saved = db.get_feature(name)
    return REGISTRY[name]["default"] if saved is None else saved


def listing() -> list[dict]:
    return [{"name": n, "label": f["label"], "description": f["description"], "enabled": is_enabled(n)} for n, f in REGISTRY.items()]


def set_many(changes: dict[str, bool]) -> None:
    """Save the choice. An unknown name is refused, and nothing is saved."""
    unknown = [n for n in changes if n not in REGISTRY]
    if unknown:
        raise HTTPException(400, "Unknown feature: " + ", ".join(sorted(unknown)))
    for n, on in changes.items():
        db.set_feature(n, bool(on))


def require(name: str):
    """A dependency for an endpoint. It refuses the call (403) when the student switched the feature off."""
    def check() -> None:
        if not is_enabled(name):
            raise HTTPException(403, f"The feature \"{REGISTRY[name]['label']}\" is switched off. Switch it on in Settings.")
    return check
