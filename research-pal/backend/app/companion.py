"""The study companion "Duck" (Sprint 07). The student explains ideas to it (the "rubber duck" method).
No AI call. The messages are fixed texts in ASD-STE100. They are kind, short and never childish."""
import hashlib

# event -> messages. An event is something that the server verified.
MESSAGES = {
    "start": ["Duck is ready. Explain the idea in your own words.", "Duck listens. Tell it the main idea of the paper."],
    "feynman_pass": ["Duck understood you. Good explanation.", "Well done. Duck can now explain this paper to a friend."],
    "feynman_try": ["Duck is not sure yet. Add one more point and try again.", "Good start. Read the missing points, then explain again."],
    "level_up": ["You reached a new level. Duck is proud of you.", "A new level. Your work shows."],
    "welcome_back": ["Welcome back. Your knowledge is still here.", "Good to see you. Start small. One card is enough."],
    "boss_defeated": ["You defeated a boss. This was a hard paper.", "The boss is down. Take a short rest."],
    "quest_done": ["Quest done. Good work.", "You finished a quest. Choose the next one when you are ready."],
    "quiz_done": ["Good work. Each answer from memory makes the idea stronger.", "Quiz done. Duck is happy."],
}


def message(event: str, seed: str = "") -> str:
    """One message for an event. The same seed gives the same message, so a page does not change its text at each draw."""
    options = MESSAGES.get(event) or []
    if not options:
        return ""
    return options[int(hashlib.sha256(f"{event}:{seed}".encode()).hexdigest(), 16) % len(options)]
