"""Mind map of a paper, built from its cards. There is no AI call.
The map shows what the cards already say, with the same checked quotes, so it cannot add a claim that a card does not have.
The map is built again each time you open the card, so it is always in step with the cards."""
import time

from . import db

# The claims of a card that have quotes. "question" and "use" are not claims of the paper.
FIELDS = [("focus", "Focus"), ("problem", "Problem"), ("method", "Method"), ("result", "Result"), ("limitation", "Limitation")]


def _node(nid: str, parent: str, label: str, f: dict) -> dict:
    return {"id": nid, "parent": parent, "label": label, "answer": f.get("answer", ""), "status": f.get("status", "unverified"),
            "evidence": f.get("evidence") or [], "draft": f.get("draft", ""), "unverified_numbers": f.get("unverified_numbers") or []}


def _fields(card: dict, prefix: str, parent: str, skip: tuple = ()) -> list[dict]:
    fields = card.get("fields") or {}
    return [_node(f"{prefix}{k}", parent, label, fields[k]) for k, label in FIELDS if k in fields and k not in skip]


def _notes(card: dict) -> list[dict]:
    """Notes from the chat. The server kept only the quotes that it found in the PDF."""
    notes = card.get("notes") or []
    if not notes:
        return []
    out = [{"id": "notes", "parent": "root", "label": "Notes from the chat", "answer": f"{len(notes)} note" + ("s" if len(notes) > 1 else ""),
            "status": "suggestion", "evidence": [], "draft": "", "unverified_numbers": []}]
    for i, n in enumerate(notes):
        out.append({"id": f"notes.{i}", "parent": "notes", "label": (n.get("question") or "From the chat")[:80], "answer": n.get("answer", ""),
                    "status": "verified" if n.get("evidence") else "suggestion", "evidence": [{**e, "verified": True} for e in n.get("evidence") or []],
                    "draft": "", "unverified_numbers": []})
    return out


def _wrap(nodes: list[dict]) -> dict:
    return {"nodes": nodes, "source": "cards", "generated_at": time.time()}


def build_card(card: dict) -> dict:
    """The map of one card: its claims, and its notes."""
    return _wrap(_fields(card, "", "root") + _notes(card))


def build(pid: str) -> dict:
    """The map of the whole paper. One card: its claims. Several cards: one branch for each card, with its claims inside."""
    first = db.get_card(pid)
    extra = [x for x in db.list_extra(pid) if x["card"]]
    if not extra:
        return build_card(first or {})
    groups = ([(first.get("focus", ""), first)] if first else []) + [(x["focus"], x["card"]) for x in extra]
    nodes = []
    for i, (focus, card) in enumerate(groups):
        gid = f"c{i}"
        label = focus or "Whole paper"
        f = (card.get("fields") or {}).get("focus")
        if f:  # a card with a focus: the focus answer is the top of its branch
            nodes.append(_node(gid, "root", label, f))
        else:
            nodes.append({"id": gid, "parent": "root", "label": label, "answer": card.get("verdict_reason") or card.get("title", ""),
                          "status": "suggestion", "evidence": [], "draft": "", "unverified_numbers": []})
        nodes += _fields(card, gid + ".", gid, skip=("focus",))
    return _wrap(nodes + (_notes(first) if first else []))
