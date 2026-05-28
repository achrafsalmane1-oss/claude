#!/usr/bin/env python3
import requests

API_TOKEN = "27|lPHnLHDjn3QN9dQmSpNNHK8mvStTRbpKg6O5Iazeaeba52b8"
BASE_URL = "https://personal.ottoresults.com/api"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

RDV_JUIN = "https://bit.ly/RDV-LQ-JUIN-26"

# ─────────────────────────────────────────────────────────────────────────────
# CAMPAIGN 1 — PARIS JUIN 2026 (FR)
# A/B subjects use Bison syntax: {variant A|variant B}
# No em dashes (replaced with commas), no emojis
# Cadence: J0 / J+3 / J+7  →  wait = 1, 3, 4
# ─────────────────────────────────────────────────────────────────────────────

PARIS_STEPS = [
    {
        "email_subject": "{{FIRST_NAME}, Thibaut de retour à Paris les 16-17-18 juin|Suite au succès de mai, nouvelles rencontres à Paris mi-juin}",
        "order": 1,
        "wait_in_days": 1,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>Bonjour {FIRST_NAME},</p>
<p>Thibaut Guéant, co-fondateur de LandQuire, société spécialisée dans le foncier pre-entitlement aux États-Unis. Nous achetons du terrain au Texas et en Floride, nous portons sa requalification administrative pendant 24 à 36 mois, puis nous le revendons aux grands promoteurs américains. C'est un modèle qui offre des rendements que l'immobilier traditionnel ne permet pas d'atteindre, et que nous rendons accessible aux investisseurs internationaux.</p>
<p>Début mai, j'étais à Paris pour rencontrer en personne des investisseurs de notre base française. L'agenda s'est rempli en quelques jours, plus de 40 rendez-vous sur trois journées, et les échanges ont été extrêmement riches. Plusieurs investisseurs qui n'avaient pas pu se libérer m'ont demandé de revenir.</p>
<p>C'est chose faite : je serai de retour à Paris les 16, 17 et 18 juin, dans un lieu de rencontre près de l'Opéra, pour une nouvelle série de rendez-vous individuels.</p>
<p>Le format reste le même :</p>
<ul>
<li>45 minutes en face-à-face pour analyser votre stratégie d'allocation actuelle,</li>
<li>une présentation détaillée des opérations que nous structurons en ce moment au Texas et en Floride,</li>
<li>une discussion concrète sur comment le foncier US peut s'intégrer dans votre patrimoine.</li>
</ul>
<p>Nouveauté cette fois-ci : si vous ne pouvez pas être à Paris ces jours-là, il est également possible de programmer une visioconférence avec moi. Je veux m'assurer que personne ne passe à côté de cette opportunité pour des raisons de géographie ou d'agenda.</p>
<p>Les créneaux de mai sont partis très vite. Si vous souhaitez me rencontrer, je vous invite à remplir ce court formulaire de qualification (2 minutes) :</p>
<p><a href="https://bit.ly/RDV-LQ-JUIN-26">https://bit.ly/RDV-LQ-JUIN-26</a></p>
<p>Je reviens personnellement vers les profils sélectionnés avec une proposition de date et d'heure.</p>
<p>Au plaisir,<br>
<strong>Thibaut Guéant</strong> <em>Co-fondateur, LandQuire</em></p>""",
    },
    {
        "email_subject": "{Re: {FIRST_NAME}, Thibaut de retour à Paris les 16-17-18 juin|Il reste des créneaux, Paris mi-juin}",
        "order": 2,
        "wait_in_days": 3,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>Bonjour {FIRST_NAME},</p>
<p>Thibaut de LandQuire, je reviens sur mon message de lundi.</p>
<p>En mai dernier, j'ai pu rencontrer individuellement plus de 40 investisseurs sur trois jours à Paris. Ce qui est ressorti de ces échanges, c'est que beaucoup d'investisseurs français cherchent activement à diversifier hors de l'Europe mais ne trouvent pas de véhicule structuré, sérieux et accessible pour entrer sur le marché foncier américain. C'est exactement ce que nous proposons chez LandQuire, et les retours de mai m'ont confirmé que le besoin est réel.</p>
<p>Je serai de nouveau à Paris les 16, 17 et 18 juin (près de l'Opéra) pour une deuxième série de rencontres individuelles. Et cette fois, si votre emploi du temps ne vous permet pas de venir physiquement, une visioconférence est aussi possible, l'important, c'est qu'on puisse échanger.</p>
<p>L'agenda de mai s'était bouclé en moins d'une semaine. Je m'attends à ce que celui de juin suive la même trajectoire.</p>
<p>Si vous êtes curieux de comprendre ce que nous structurons en ce moment au Texas et en Floride, ou simplement de discuter 45 minutes de votre stratégie d'allocation, c'est maintenant :</p>
<p><a href="https://bit.ly/RDV-LQ-JUIN-26">https://bit.ly/RDV-LQ-JUIN-26</a></p>
<p>Thibaut</p>""",
    },
    {
        "email_subject": "{Derniers créneaux, Paris 16-18 juin|{FIRST_NAME}, je clôture l'agenda vendredi}",
        "order": 3,
        "wait_in_days": 4,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>Bonjour {FIRST_NAME},</p>
<p>Thibaut Guéant, LandQuire, dernier message de ma part sur ce sujet.</p>
<p>Comme en mai, les demandes de rendez-vous arrivent vite et l'agenda de mes trois journées parisiennes (16, 17 et 18 juin) commence sérieusement à se remplir. Je clôture les inscriptions ce vendredi pour pouvoir organiser les créneaux restants de manière cohérente.</p>
<p>Pour rappel : LandQuire structure des opérations de foncier en pre-entitlement au Texas et en Floride. Nous achetons du terrain, nous portons sa requalification administrative, et nous capturons pour nos investisseurs la plus-value qui en découle, sur des horizons de 2 à 4 ans. Plusieurs centaines d'investisseurs internationaux nous suivent déjà sur ce modèle.</p>
<p>En mai, j'ai rencontré plus de 40 personnes en trois jours. Les retours ont été excellents, et plusieurs investisseurs ont avancé concrètement avec nous suite à ces échanges. J'aimerais que vous ayez la même opportunité.</p>
<p>Deux options pour me rencontrer :</p>
<ul>
<li>En personne à Paris, près de l'Opéra, les 16-17-18 juin</li>
<li>En visioconférence si vous ne pouvez pas vous déplacer</li>
</ul>
<p>Dans les deux cas, le formulaire est ici :</p>
<p><a href="https://bit.ly/RDV-LQ-JUIN-26">https://bit.ly/RDV-LQ-JUIN-26</a></p>
<p>Si ce n'est vraiment pas le bon moment, répondez simplement "pas maintenant" et je ne vous recontacterai pas sur ce passage.</p>
<p>Bien à vous,<br>
<strong>Thibaut Guéant</strong> <em>Co-fondateur, LandQuire</em></p>""",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# CAMPAIGN 2 — ALLAN: FAMILY OFFICES (EN)
# Cadence: Day 1 / Day 7 / Day 21 / Day 45  →  wait = 1, 6, 14, 24
# E2b (reply path) excluded — send manually from master inbox to positive replies
# ─────────────────────────────────────────────────────────────────────────────

ALLAN_FO_STEPS = [
    {
        "email_subject": "US land, quick question",
        "order": 1,
        "wait_in_days": 1,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>{FIRST_NAME},</p>
<p>I noticed your focus on real asset allocation. Still looking at new opportunities in the US market?</p>
<p>[Your Name]</p>""",
    },
    {
        # E2a — no reply path
        "email_subject": "Re: US land",
        "order": 2,
        "wait_in_days": 6,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>{FIRST_NAME},</p>
<p>Quick follow-up. If US real assets aren't in your current mandate, a simple 'not for us' is all I need. If there is any appetite: what does your typical hold tolerance look like for illiquid alternatives?</p>
<p>[Your Name]</p>""",
    },
    {
        # E3
        "email_subject": "One number: 4-7 million",
        "order": 3,
        "wait_in_days": 14,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>{FIRST_NAME},</p>
<p>The US is short 4-7 million housing units. That gap is structural, demographic, regulatory. Not cyclical.</p>
<p>LandQuire converts that deficit into a 22% target IRR with a 10% contractual preferred return on Class A units. No blind pool. SPV per project. Full transparency.</p>
<p>Worth 20 minutes?</p>
<p>[Your Name]</p>""",
    },
    {
        # E4
        "email_subject": "Last note",
        "order": 4,
        "wait_in_days": 24,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>{FIRST_NAME},</p>
<p>Final message from me on this. If the timing doesn't work, completely understood. If it ever becomes relevant, feel free to reach back out.</p>
<p>[Your Name]</p>""",
    },
]

# E2b — Family Offices reply path (manual send only)
ALLAN_FO_E2B = {
    "email_subject": "Re: LandQuire, one-pager",
    "email_body": """<p>{FIRST_NAME},</p>
<p>Appreciate the response. LandQuire, Miami-based land entitlement platform. SPV per project, Class A preferred units, 10% contractual return floor, ~22% IRR target, 12-36 month hold. One-pager attached. If worth 20 minutes, happy to connect.</p>
<p>[Your Name]</p>""",
}

# ─────────────────────────────────────────────────────────────────────────────
# CAMPAIGN 3 — ALLAN: RE INVESTMENT FUNDS (EN)
# Same cadence as Family Offices
# ─────────────────────────────────────────────────────────────────────────────

ALLAN_RE_STEPS = [
    {
        "email_subject": "US land entitlement, quick question",
        "order": 1,
        "wait_in_days": 1,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>{FIRST_NAME},</p>
<p>Saw your focus on US real estate / development strategies. Still looking at pre-development land positions in the Sun Belt?</p>
<p>[Your Name]</p>""",
    },
    {
        # E2a — no reply path
        "email_subject": "Re: US land",
        "order": 2,
        "wait_in_days": 6,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>{FIRST_NAME},</p>
<p>Brief follow-up. If pre-development / land entitlement isn't in your current mandate, just let me know. If there's any interest: what's your typical IRR threshold for a 12-36 month US real assets position?</p>
<p>[Your Name]</p>""",
    },
    {
        # E3
        "email_subject": "Texas land, one data point",
        "order": 3,
        "wait_in_days": 14,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>{FIRST_NAME},</p>
<p>US housing deficit: 4-7 million units. Sun Belt pressure intensifying.</p>
<p>LandQuire scans all 3,243 US counties in real time to identify undervalued land ahead of permit cycles. The model: acquire off-market, entitle, exit to developers at a premium.</p>
<p>Structure: SPV per deal, Class A preferred units, 10% guaranteed return + ~22% IRR target, 12-36 month hold.</p>
<p>If the thesis fits your pipeline, happy to share the term sheet.</p>
<p>[Your Name]</p>""",
    },
    {
        # E4
        "email_subject": "Closing the loop",
        "order": 4,
        "wait_in_days": 24,
        "variant": False,
        "thread_reply": False,
        "email_body": """<p>{FIRST_NAME},</p>
<p>Last note from me. If the timing or mandate doesn't align right now, completely understood. If a Texas land entitlement position fits a future allocation cycle, feel free to reach back out.</p>
<p>[Your Name]</p>""",
    },
]

# E2b — RE Funds reply path (manual send only)
ALLAN_RE_E2B = {
    "email_subject": "Re: LandQuire, deal brief",
    "email_body": """<p>{FIRST_NAME},</p>
<p>Thanks for coming back. LandQuire, Miami-based, Texas Sun Belt focus, 22% target IRR, 10% preferred return, SPV per project, 12-36 month exit. Last closed deal: PF17 Seguin TX, $9.6M raised. Deal brief attached. Happy to walk through the mechanics on a 20-minute call.</p>
<p>[Your Name]</p>""",
}

# ─────────────────────────────────────────────────────────────────────────────

CAMPAIGNS = [
    {
        "name": "Paris Juin 2026 (FR)",
        "sequence_title": "Paris Juin 2026 FR Sequence",
        "steps": PARIS_STEPS,
        "e2b_note": None,
    },
    {
        "name": "Allan - Family Offices (EN)",
        "sequence_title": "Allan Family Offices Sequence",
        "steps": ALLAN_FO_STEPS,
        "e2b_note": ALLAN_FO_E2B,
    },
    {
        "name": "Allan - RE Investment Funds (EN)",
        "sequence_title": "Allan RE Funds Sequence",
        "steps": ALLAN_RE_STEPS,
        "e2b_note": ALLAN_RE_E2B,
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
    result = resp.json()["data"]
    created_steps = result.get("sequence_steps", [])
    print(f"  Created {len(created_steps)} sequence steps")
    return True


def main():
    print("Creating new campaigns...\n")
    results = []

    for campaign in CAMPAIGNS:
        print(f"-> {campaign['name']}")
        cid = create_campaign(campaign["name"])
        ok = create_sequence(cid, campaign["sequence_title"], campaign["steps"])
        results.append({"name": campaign["name"], "id": cid, "ok": ok})

        if campaign["e2b_note"]:
            print(f"  NOTE: E2b (reply path) excluded from automated sequence.")
            print(f"        Send manually to positive replies: subject='{campaign['e2b_note']['email_subject']}'")
        print()

    print("-" * 60)
    print("Summary:")
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        print(f"  [{status}] ID={r['id']} {r['name']}")


if __name__ == "__main__":
    main()
