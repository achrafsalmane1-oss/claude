#!/usr/bin/env python3
import requests

API_TOKEN = "27|lPHnLHDjn3QN9dQmSpNNHK8mvStTRbpKg6O5Iazeaeba52b8"
BASE_URL = "https://personal.ottoresults.com/api"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

FR_REG = "https://bit.ly/LQPF22FR"
EN_REG = "https://bit.ly/LQPF22EN"

# ─────────────────────────────────────────────────────────────────────────────
# PF22 WEBINAR — FRANÇAIS
# Cadence: J0 / J+3 / J+5  →  wait = 1, 3, 2
# ─────────────────────────────────────────────────────────────────────────────

PF22_FR_STEPS = [
    {
        "email_subject": "{Nouvelle opportunité LandQuire au Texas : Portfolio 22|Invitation privée, découvrez PF22 à Cibolo, Texas}",
        "order": 1,
        "wait_in_days": 1,
        "variant": False,
        "thread_reply": False,
        "email_body": f"""<p>Bonjour {{FIRST_NAME}},</p>
<p>Nous avons le plaisir de vous inviter à la présentation officielle de notre nouvelle opportunité d'investissement : <strong>LandQuire Portfolio 22 — Cibolo, Texas</strong>.</p>
<p>Ce projet porte sur l'acquisition et le développement d'un terrain off-market de <strong>94 acres</strong>, situé à Cibolo, à moins de 30 minutes de San Antonio, au coeur du corridor de croissance San Antonio–Austin, l'un des marchés résidentiels les plus dynamiques du Texas.</p>
<p>L'objectif du projet est de développer environ <strong>264 lots résidentiels</strong> destinés à des maisons individuelles, dans une zone où la demande de logements continue de dépasser l'offre disponible.</p>
<p>Cette opportunité repose sur une stratégie claire de création de valeur :</p>
<ol>
<li>Acquisition off-market d'un terrain dans une zone en forte croissance</li>
<li>Entitlement et planification des infrastructures</li>
<li>Revente des lots sous forme de "paper lots" ou de lots finis selon le scénario retenu</li>
</ol>
<p><strong>Points clés du projet :</strong></p>
<ul>
<li>Localisation : Cibolo, Texas</li>
<li>Surface : 94 acres</li>
<li>Développement prévu : environ 264 lots résidentiels</li>
<li>Type de projet : développement résidentiel de maisons individuelles</li>
<li>Investissement minimum : 100 000 USD</li>
<li>Rendement préférentiel : 10% par an</li>
<li>TRI cible Phase A : 26% – 49%</li>
<li>TRI cible Phase B : 29% – 41%</li>
<li>Horizon Phase A : 12 à 24 mois</li>
<li>Horizon Phase B : 24 à 60 mois</li>
</ul>
<p>Nous organiserons un webinaire privé pour présenter en détail le projet, le marché, la stratégie de développement, les hypothèses financières et la structure d'investissement.</p>
<p><strong>Webinaire privé — Portfolio 22</strong><br>
Mercredi 10 juin<br>
19h, heure de Paris<br>
En ligne<br>
<a href="{FR_REG}">Inscrivez-vous ici</a></p>
<p>Lors de cette session, vous pourrez également poser vos questions directement à l'équipe LandQuire.</p>
<p>Bien cordialement,<br>
<strong>Thibaut Guéant</strong> <em>Co-fondateur, LandQuire</em></p>""",
    },
    {
        "email_subject": "Pourquoi Cibolo, Texas attire notre attention",
        "order": 2,
        "wait_in_days": 3,
        "variant": False,
        "thread_reply": False,
        "email_body": f"""<p>Bonjour {{FIRST_NAME}},</p>
<p>Dans le cadre du lancement de Portfolio 22, nous souhaitions vous partager quelques éléments sur le marché de Cibolo, Texas, et les raisons pour lesquelles cette zone présente un intérêt stratégique pour LandQuire.</p>
<p>Cibolo se situe à moins de 30 minutes de San Antonio, au coeur du corridor San Antonio–Austin, une région qui concentre une forte croissance démographique, une activité économique soutenue et une demande résidentielle importante.</p>
<p>Selon notre analyse, plusieurs facteurs soutiennent le potentiel du projet :</p>
<ul>
<li>Une forte croissance de la population dans la région</li>
<li>Une demande de logements qui continue de dépasser l'offre disponible</li>
<li>Des prix encore plus accessibles que dans San Antonio</li>
<li>Des investissements importants dans les infrastructures locales</li>
<li>La présence d'employeurs industriels et logistiques majeurs</li>
<li>Une demande soutenue pour des maisons individuelles destinées aux familles et aux ménages de revenus moyens</li>
</ul>
<p>C'est dans ce contexte que LandQuire a sécurisé un terrain off-market de 94 acres, avec pour objectif la création d'environ 264 lots résidentiels.</p>
<p>La stratégie vise à créer de la valeur à travers l'entitlement, la planification des infrastructures et la revente des lots, avec deux scénarios possibles : une sortie après la Phase A sous forme de "paper lots", ou une sortie après la Phase B sous forme de lots finis.</p>
<p>Nous détaillerons l'ensemble du projet lors du webinaire privé :</p>
<p><strong>Webinaire Portfolio 22 — Cibolo, Texas</strong><br>
Mercredi 10 juin<br>
19h, heure de Paris<br>
En ligne<br>
<a href="{FR_REG}">Réservez votre place ici</a></p>
<p>Le webinaire couvrira le marché, la stratégie foncière, les hypothèses financières, les scénarios de sortie et la structure de distribution aux investisseurs.</p>
<p>Bien cordialement,<br>
<strong>Thibaut Guéant</strong> <em>Co-fondateur, LandQuire</em></p>""",
    },
    {
        "email_subject": "Rappel, webinaire PF22 ce mercredi à 19h",
        "order": 3,
        "wait_in_days": 2,
        "variant": False,
        "thread_reply": False,
        "email_body": f"""<p>Bonjour {{FIRST_NAME}},</p>
<p>Petit rappel : nous organisons ce mercredi 10 juin à 19h, heure de Paris, le webinaire privé de présentation de <strong>LandQuire Portfolio 22 — Cibolo, Texas</strong>.</p>
<p>Ce projet consiste à développer un terrain off-market de 94 acres en environ 264 lots résidentiels destinés à des maisons individuelles, dans une zone en forte croissance située à moins de 30 minutes de San Antonio.</p>
<p>Pendant cette session, nous présenterons :</p>
<ul>
<li>Le marché résidentiel de Cibolo et du corridor San Antonio–Austin</li>
<li>La stratégie d'acquisition off-market</li>
<li>Le plan de développement des 264 lots résidentiels</li>
<li>Les deux scénarios de sortie : Phase A et Phase B</li>
<li>Les hypothèses financières du projet</li>
<li>La structure d'investissement et de distribution</li>
<li>Une session de questions/réponses en direct</li>
</ul>
<p><strong>Quelques chiffres clés :</strong></p>
<ul>
<li>Investissement minimum : 100 000 USD</li>
<li>Rendement préférentiel : 10% par an</li>
<li>TRI cible Phase A : 26% – 49%</li>
<li>TRI cible Phase B : 29% – 41%</li>
<li>ROI cible Phase A : 66%</li>
<li>ROI cible Phase B : 111%</li>
</ul>
<p>Inscription obligatoire ici : <a href="{FR_REG}">{FR_REG}</a></p>
<p>Si vous souhaitez analyser cette opportunité ou poser vos questions directement à l'équipe, nous vous invitons à réserver votre place avant le début du webinaire.</p>
<p>Bien cordialement,<br>
<strong>Thibaut Guéant</strong> <em>Co-fondateur, LandQuire</em></p>""",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# PF22 WEBINAR — ENGLISH
# Same cadence: wait = 1, 3, 2
# ─────────────────────────────────────────────────────────────────────────────

PF22_EN_STEPS = [
    {
        "email_subject": "{New LandQuire opportunity in Texas: Portfolio 22|Private invitation, discover PF22 in Cibolo, Texas}",
        "order": 1,
        "wait_in_days": 1,
        "variant": False,
        "thread_reply": False,
        "email_body": f"""<p>Hi {{FIRST_NAME}},</p>
<p>We are pleased to invite you to the official presentation of our newest investment opportunity: <strong>LandQuire Portfolio 22 — Cibolo, Texas</strong>.</p>
<p>This project involves the acquisition and development of a <strong>94-acre off-market</strong> property located in Cibolo, less than 30 minutes from San Antonio, in the heart of the San Antonio–Austin growth corridor, one of the most dynamic residential markets in Texas.</p>
<p>The objective is to develop approximately <strong>264 single-family residential lots</strong> in an area where housing demand continues to outpace available supply.</p>
<p>The opportunity is built around a clear value-creation strategy:</p>
<ol>
<li>Off-market acquisition in a high-growth residential market</li>
<li>Entitlement and infrastructure planning</li>
<li>Resale of the lots either as paper lots or finished residential lots, depending on the exit scenario</li>
</ol>
<p><strong>Key project highlights:</strong></p>
<ul>
<li>Location: Cibolo, Texas</li>
<li>Land size: 94 acres</li>
<li>Development plan: approximately 264 single-family residential lots</li>
<li>Project type: residential land development</li>
<li>Minimum investment: $100,000</li>
<li>Preferred return: 10% annually</li>
<li>Phase A target IRR: 26% – 49%</li>
<li>Phase B target IRR: 29% – 41%</li>
<li>Phase A timeframe: 12 to 24 months</li>
<li>Phase B timeframe: 24 to 60 months</li>
</ul>
<p>We will host a private webinar to present the project in detail, including the market opportunity, development strategy, financial assumptions, exit scenarios, and investment structure.</p>
<p><strong>Private Webinar — Portfolio 22</strong><br>
Wednesday, June 10<br>
11:00 AM EST<br>
Online<br>
<a href="{EN_REG}">Register here</a></p>
<p>You will also have the opportunity to ask your questions directly to the LandQuire team during the live Q&A session.</p>
<p>Best regards,<br>
<strong>Thibaut Guéant</strong> <em>Co-founder, LandQuire</em></p>""",
    },
    {
        "email_subject": "Why Cibolo, Texas is on our radar",
        "order": 2,
        "wait_in_days": 3,
        "variant": False,
        "thread_reply": False,
        "email_body": f"""<p>Hi {{FIRST_NAME}},</p>
<p>As part of the launch of Portfolio 22, we wanted to share why Cibolo, Texas has become an attractive market for LandQuire's residential development strategy.</p>
<p>Cibolo is located less than 30 minutes from San Antonio, in the heart of the San Antonio–Austin growth corridor, a region supported by strong population growth, expanding infrastructure, and sustained residential demand.</p>
<p>Several factors support the project's potential:</p>
<ul>
<li>Strong population growth across the region</li>
<li>Housing demand that continues to exceed available supply</li>
<li>More accessible pricing compared to San Antonio</li>
<li>Significant local infrastructure investments</li>
<li>Major industrial and logistics employers in the area</li>
<li>Strong demand for single-family homes serving families and middle-income households</li>
</ul>
<p>Within this context, LandQuire has secured a 94-acre off-market site with the objective of developing approximately 264 single-family residential lots.</p>
<p>The strategy is to create value through entitlement, infrastructure planning, and the resale of the lots, with two potential exit scenarios: a Phase A exit through paper lots, or a Phase B exit through finished residential lots.</p>
<p>We will walk through the full opportunity during our private webinar:</p>
<p><strong>Portfolio 22 Webinar — Cibolo, Texas</strong><br>
Wednesday, June 10<br>
11:00 AM EST<br>
Online<br>
<a href="{EN_REG}">Reserve your seat here</a></p>
<p>The webinar will cover the market, the land strategy, the financial assumptions, the exit scenarios, and the investor distribution structure.</p>
<p>Best regards,<br>
<strong>Thibaut Guéant</strong> <em>Co-founder, LandQuire</em></p>""",
    },
    {
        "email_subject": "Reminder, PF22 webinar this Wednesday at 11:00 AM EST",
        "order": 3,
        "wait_in_days": 2,
        "variant": False,
        "thread_reply": False,
        "email_body": f"""<p>Hi {{FIRST_NAME}},</p>
<p>Quick reminder: we are hosting the private webinar for <strong>LandQuire Portfolio 22 — Cibolo, Texas</strong> this Wednesday, June 10 at 11:00 AM EST.</p>
<p>This project involves the development of a 94-acre off-market property into approximately 264 single-family residential lots, located in a fast-growing market less than 30 minutes from San Antonio.</p>
<p>During the session, we will cover:</p>
<ul>
<li>The residential market in Cibolo and the San Antonio–Austin growth corridor</li>
<li>LandQuire's off-market acquisition strategy</li>
<li>The development plan for the 264 single-family lots</li>
<li>The two exit scenarios: Phase A and Phase B</li>
<li>The project's financial assumptions</li>
<li>The investment and distribution structure</li>
<li>A live Q&A session with the LandQuire team</li>
</ul>
<p><strong>Key figures:</strong></p>
<ul>
<li>Minimum investment: $100,000</li>
<li>Preferred return: 10% annually</li>
<li>Phase A target IRR: 26% – 49%</li>
<li>Phase B target IRR: 29% – 41%</li>
<li>Phase A target ROI: 66%</li>
<li>Phase B target ROI: 111%</li>
</ul>
<p>Registration required here: <a href="{EN_REG}">{EN_REG}</a></p>
<p>If you would like to review this opportunity and ask your questions directly to the team, we invite you to reserve your seat before the webinar starts.</p>
<p>Best regards,<br>
<strong>Thibaut Guéant</strong> <em>Co-founder, LandQuire</em></p>""",
    },
]

# ─────────────────────────────────────────────────────────────────────────────

CAMPAIGNS = [
    {
        "name": "PF22 Webinar - Séquence (FR)",
        "sequence_title": "PF22 Webinar FR Sequence",
        "steps": PF22_FR_STEPS,
    },
    {
        "name": "PF22 Webinar - Sequence (EN)",
        "sequence_title": "PF22 Webinar EN Sequence",
        "steps": PF22_EN_STEPS,
    },
]


def create_campaign(name):
    resp = requests.post(f"{BASE_URL}/campaigns", headers=HEADERS, json={"name": name})
    resp.raise_for_status()
    data = resp.json()["data"]
    print(f"  Created campaign '{name}' -> ID {data['id']}")
    return data["id"]


def create_sequence(campaign_id, title, steps):
    resp = requests.post(
        f"{BASE_URL}/campaigns/v1.1/{campaign_id}/sequence-steps",
        headers=HEADERS,
        json={"title": title, "sequence_steps": steps},
    )
    if resp.status_code not in (200, 201):
        print(f"  ERROR [{resp.status_code}]: {resp.text[:300]}")
        return False
    created = resp.json()["data"].get("sequence_steps", [])
    print(f"  Created {len(created)} sequence steps")
    return True


def main():
    print("Creating PF22 Webinar campaigns...\n")
    results = []
    for campaign in CAMPAIGNS:
        print(f"-> {campaign['name']}")
        cid = create_campaign(campaign["name"])
        ok = create_sequence(cid, campaign["sequence_title"], campaign["steps"])
        results.append({"name": campaign["name"], "id": cid, "ok": ok})
        print()

    print("-" * 60)
    print("Summary:")
    for r in results:
        print(f"  [{'OK' if r['ok'] else 'FAIL'}] ID={r['id']} {r['name']}")


if __name__ == "__main__":
    main()
