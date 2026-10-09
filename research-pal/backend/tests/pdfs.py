"""Test PDFs. They are made with reportlab, so the tests never need a real paper."""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PAPERS = {
    "a.pdf": ("AUTOMA: Multi-agent threat hunting", [
        "AUTOMA: Multi-agent threat hunting\nAbstract\nWe present AUTOMA, a multi agent system for cyber threat hunting. Analysts spend many hours on manual log review and miss attacks.",
        "Method\nOur system uses a hypothesis agent and a validation agent. The hypothesis agent reads Sysmon logs and proposes attack hypotheses that map to MITRE ATT&CK techniques.",
        "Results\nOn the OpTC dataset, AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent. The baseline reaches 72.0 percent precision on the same logs.\nLimitations\nWe test only on one dataset. Future work will add more datasets and real networks.",
        "Conclusion\nThe multi agent design reduces manual work for threat hunting analysts.\nReferences\n[1] Smith. Old paper about firewalls. 2001.",
    ]),
    "b.pdf": ("Cooking pasta with tomatoes", [
        "Cooking pasta with tomatoes\nAbstract\nThis paper explains how to cook pasta with tomato sauce and basil for dinner. Boil water with salt and add the pasta.",
        "Method\nWe boil the pasta for nine minutes and stir the tomato sauce slowly with fresh basil leaves.",
        "Results\nTen testers liked the dish. The sauce tastes better with basil and olive oil.",
        "Conclusion\nPasta with tomato sauce is easy to cook at home and cheap for students.",
    ]),
}

# The text of each PDF that the server must find. A quote that is not in these pages is false.
INVENTED_QUOTE = "The system completely fails on encrypted network traffic in all cases."


def make_pdf(path, pages) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for text in pages:
        y = 800
        for line in text.split("\n"):
            while line:
                c.drawString(50, y, line[:95])
                line = line[95:]
                y -= 16
        c.showPage()
    c.save()
