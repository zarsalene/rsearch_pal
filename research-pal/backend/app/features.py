"""Feature switches. Each new feature has a switch in Settings, so a problem in one feature does not block the app.
The list of features is in REGISTRY. The table "features" keeps only the choice of the student. A feature without a row uses its default."""
from fastapi import HTTPException

from . import db

# name -> label, description, default. Add one entry for each new feature.
REGISTRY: dict[str, dict] = {
    "chat": {"label": "Chat", "description": "Ask questions about your papers. Each answer shows its quotes.", "default": True},
    "direction": {"label": "Thesis direction", "description": "Thesis title bar, question helper, sub-questions and paper tags.", "default": True},
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
