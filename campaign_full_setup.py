#!/usr/bin/env python3
"""
Business Sergeant - Full Campaign Setup from Strategy Brief
- Adds all variants + correct copy to existing campaigns 877-882
- Creates Campaign 4 (New to Role) Google + Outlook
- Creates Campaign 5 (Missing Key Role) Google + Outlook
- Every email: proper signature, lowercase spintax subjects, {FIRST_NAME}/{COMPANY} variables
"""

import requests, json, time

API_BASE = "https://send.ottoresults.com/api"
TOKEN = "230|GAOm2ewVrhSBmestue65g7X8i81qkvLnYAOc6Kmv2a6bbcdb"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

SIG = (
    "<p>{Best|All the best|Cheers|Talk soon|Best regards},<br>"
    "Michael Kracyla<br>"
    "President &amp; Co-Founder | Business Sergeant</p>"
)

def post(path, data):
    r = requests.post(f"{API_BASE}/{path}", headers=HEADERS, json=data)
    r.raise_for_status()
    return r.json()

def get(path):
    r = requests.get(f"{API_BASE}/{path}", headers=HEADERS)
    r.raise_for_status()
    return r.json()

def p(text):
    """Wrap plain text paragraph in <p> tags, one sentence per paragraph."""
    return "<p>" + text + "</p>"

def br(text):
    return text.replace("\n", "<br>")

def body(*paragraphs):
    """Join paragraphs with <p><br></p> spacers and append signature."""
    parts = ["<p><br></p>".join(f"<p>{pg}</p>" for pg in paragraphs)]
    parts.append("<p><br></p>")
    parts.append(SIG)
    return "".join(parts)

# ─────────────────────────────────────────────
# ALL EMAIL CONTENT FROM STRATEGY BRIEF
# ─────────────────────────────────────────────

# CAMPAIGN 1: Veterans with Hiring Authority
# 5 variants, lowercase spintax subject on primary

C1_PRIMARY_SUBJ = "{veteran leadership bench|community pipeline|the halo effect|proven operators|ready for their next mission}"

C1_VARIANTS = [
    # (subject, body_html)
    (
        "veteran leadership bench",
        body(
            "{FIRST_NAME}, you already know the value our people bring.",
            "We have built an active community of military veterans and Special Operations leaders who are trained, vetted, and ready for operations leadership roles.",
            "You know the type. Disciplined. Accountable. Figure-it-out mentality.",
            "Can I send over a couple of sample resumes so you can see the bench?"
        )
    ),
    (
        "community pipeline",
        body(
            "{FIRST_NAME}, we run a leadership development community for transitioning veterans, including Special Operations professionals.",
            "We prepare them for ops leadership roles in the private sector. When your team has a gap, we can get proven operators in front of you fast.",
            "These are people you would want in your foxhole.",
            "Want me to send a couple of sample resumes so you can see the caliber?"
        )
    ),
    (
        "the halo effect",
        body(
            "{FIRST_NAME}, you have probably seen it firsthand. One strong veteran leader changes the performance of an entire team.",
            "We have built a pipeline of these leaders. Military veterans and Special Operations professionals, vetted by operators, trained and ready for their next mission.",
            "Hiring one has an immediate impact. Hiring a few is transformational.",
            "Can I send over a couple of resumes so you can see what we are working with?"
        )
    ),
    (
        "proven operators",
        body(
            "{FIRST_NAME}, our candidates have been tested thousands of times in the highest-stakes environments on the planet.",
            "You can put them anywhere and they figure it out. That is the kind of leader we develop through our veteran community and place into operations roles.",
            "Worth seeing a sample resume or two? Happy to send them over."
        )
    ),
    (
        "ready for their next mission",
        body(
            "{FIRST_NAME}, we maintain a community of veteran leaders, including Green Berets, SEALs, and Rangers, who are trained and ready for operations roles in the private sector.",
            "Every one of them has been vetted by Special Operations personnel. They bring discipline, accountability, and the kind of ownership that is hard to find.",
            "They are ready for their next mission. Can I send over a couple of resumes?"
        )
    ),
]


# CAMPAIGN 2: Operations Leaders & SMB Founders
# 6 variants (A-F). Campaigns 879/880 currently have A,B,D,E,F. Adding C (Halo Effect).

C2_PRIMARY_SUBJ = "{leadership bench|accountability|the halo effect|operations leadership|$2m+ in leadership training|portfolio ops leadership}"

C2_ALL_VARIANTS = [
    (
        "leadership bench",
        body(
            "{FIRST_NAME},",
            "If you could hire a leader who has been tested thousands of times under real pressure, would industry-specific experience be a dealbreaker?",
            "Most of our candidates learn the industry in 3-6 months. What they bring from day one, discipline, accountability, team leadership, takes a decade to build.",
            "We maintain an active community of military veterans and Special Operations leaders ready for operations roles.",
            "Can I send over a sample resume to show you what I mean?"
        )
    ),
    (
        "accountability",
        body(
            "{FIRST_NAME}, leadership and accountability are getting harder to find in today's workforce.",
            "We work with military veterans, including Special Operations professionals, who have spent their careers in environments where accountability is not optional.",
            "They are disciplined. They communicate. They figure it out.",
            "We have an active pipeline of these leaders ready for operations roles at companies like {COMPANY}.",
            "Can I send over a couple of resumes so you can see the caliber?"
        )
    ),
    (
        "the halo effect",
        body(
            "{FIRST_NAME}, have you ever noticed how one strong leader can change the performance of an entire team?",
            "We call it the halo effect.",
            "Our candidates, military veterans and Special Operations leaders, do not just fill a seat. They level up everyone around them.",
            "We have built a community where these leaders are trained, vetted by Special Ops personnel, and ready for their next mission.",
            "Worth seeing a sample resume?"
        )
    ),
    (
        "operations leadership",
        body(
            "{FIRST_NAME}, most founders I talk to hit the same wall.",
            "The business is growing but they cannot find leaders who will own the execution the way they do. So they stay stuck in the day-to-day.",
            "We work with a pipeline of military veterans and Special Operations leaders who are built for exactly that. They take ownership. They drive accountability. They do not need hand-holding.",
            "Can I send over a couple of sample resumes so you can see the kind of operators we place?"
        )
    ),
    (
        "$2m+ in leadership training",
        body(
            "{FIRST_NAME}, here is a question most people have not thought about.",
            "It would take you 10+ years and millions of dollars in training to develop ONE leader on par with any of our candidates. We are not exaggerating. That is what the U.S. military invests in developing Special Operations leaders.",
            "Your people can learn what you do in 3-6 months. What our candidates bring takes a career to build.",
            "Can I send a couple of resumes so you can see what that looks like?"
        )
    ),
    (
        "portfolio ops leadership",
        body(
            "{FIRST_NAME}, when a portfolio company needs an operator who can stabilize a team and drive execution from day one, where does that candidate come from?",
            "We maintain a community of military veterans, including Special Operations leaders, who are trained for exactly that environment. High stakes. Fast timelines. No hand-holding.",
            "Can I send over a couple of sample resumes so you can see the bench?"
        )
    ),
]

# Only Variant C (Halo Effect) is missing from existing 879/880
C2_MISSING_VARIANT = C2_ALL_VARIANTS[2]  # "the halo effect"


# CAMPAIGN 3: Open Roles / Hiring Signal
# Existing campaigns 881/882 have 4 steps (Michael intro + 3 brief variants). Complete.
# No additions needed for variants, but subject lines on existing steps are not spintaxed.
# We'll replace entirely when we can — for now: nothing to add.
C3_PRIMARY_SUBJ = "{{open_role_title}}"  # spintax w/ variable → {OPEN_ROLE_TITLE}
# Since all 3 brief variants + Michael's intro are already present, skip.


# CAMPAIGN 4: New to Role
C4_PRIMARY_SUBJ = "{building your team|ops leadership pipeline|first 90 days}"

C4_VARIANTS = [
    (
        "building your team",
        body(
            "{FIRST_NAME}, congrats on the new role at {COMPANY}.",
            "If you are building out your operations team or filling leadership gaps you have inherited, we have a pipeline worth knowing about.",
            "We maintain a community of military veterans, including Special Operations leaders, who are trained, vetted, and ready for ops roles.",
            "Accountable, disciplined, low-drama operators.",
            "Can I send over a couple of sample resumes?"
        )
    ),
    (
        "ops leadership pipeline",
        body(
            "{FIRST_NAME}, new leadership roles usually come with inherited gaps.",
            "If you are evaluating your team, we may be able to help.",
            "We work with a vetted community of military and Special Operations veterans who have led teams in environments where accountability is not a poster on the wall. It is a requirement.",
            "Worth a look? Happy to send over a couple of sample profiles."
        )
    ),
    (
        "first 90 days",
        body(
            "{FIRST_NAME}, the first 90 days in a new ops role are when you figure out who can execute and where the gaps are.",
            "If you are starting to think about adding leadership talent, we have a bench of military veterans and Special Operations professionals ready for operations roles.",
            "Trained. Vetted by operators. They bring accountability from day one.",
            "Can I send over a couple of sample resumes for when you are ready to make moves?"
        )
    ),
]


# CAMPAIGN 5: Missing Key Role
C5_PRIMARY_SUBJ = "{operations gap|no dedicated ops leader|missing ops leader}"

C5_VARIANTS = [
    (
        "operations gap",
        body(
            "{FIRST_NAME}, who handles operations at {COMPANY} when you are in a meeting?",
            "Looked around on LinkedIn and could not find a dedicated ops leader on the team. If that is still accurate, we maintain a bench of operators who have led teams in some of the most demanding environments on the planet.",
            "Can I send over a sample resume?"
        )
    ),
    (
        "no dedicated ops leader",
        body(
            "{FIRST_NAME}, noticed {COMPANY} does not have a dedicated operations leader on the team.",
            "Most founders in that situation tell me they are still the one resolving vendor issues, onboarding new hires, and answering the questions no one else can.",
            "We place military veterans with operational leadership experience into exactly these roles.",
            "Can I send a sample resume?"
        )
    ),
    (
        "missing ops leader",
        body(
            "{FIRST_NAME}, looked at {COMPANY}'s team on LinkedIn and did not see a dedicated operations leader. Is that a gap you are looking to fill?",
            "We maintain a bench of military veterans and Special Operations leaders trained for exactly this kind of role.",
            "Can I send over a sample resume?"
        )
    ),
]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def add_variants_to_existing(campaign_id, primary_step_id, variants):
    """Add new variant steps (A/B tests) to an existing primary step."""
    results = []
    for subj, html_body in variants:
        step_data = {
            "title": f"Added variant - {subj}",
            "sequence_steps": [
                {
                    "email_subject": subj,
                    "email_body": html_body,
                    "wait_in_days": 1,
                    "variant": True,
                    "variant_from_step": primary_step_id,
                }
            ]
        }
        r = post(f"campaigns/{campaign_id}/sequence-steps", step_data)
        step = r.get("data", {})
        print(f"    ✓ Added variant '{subj}' to campaign {campaign_id}")
        results.append(step)
        time.sleep(0.3)
    return results


def create_fresh_sequence(campaign_id, seq_title, primary_subj, variants):
    """Create a brand-new sequence on a campaign with no existing sequence."""
    primary_subj_lc, primary_body = variants[0]
    rest_variants = variants[1:]

    step_list = [
        {
            "email_subject": primary_subj,  # spintax of all subjects
            "email_body": primary_body,
            "wait_in_days": 1,
        }
    ]
    for subj, html_body in rest_variants:
        step_list.append({
            "email_subject": subj,
            "email_body": html_body,
            "wait_in_days": 1,
            "variant": True,
        })

    r = post(f"campaigns/{campaign_id}/sequence-steps", {
        "title": seq_title,
        "sequence_steps": step_list,
    })
    seq = r.get("data", {})
    print(f"  ✓ Created sequence '{seq_title}' (seq_id={seq.get('id')}) for campaign {campaign_id}")
    return seq


def create_campaign_pair(google_name, outlook_name, primary_subj, variants, seq_title_prefix):
    """Create Google + Outlook split campaigns from scratch with a full sequence."""
    created = {}
    for variant_key, name in [("google", google_name), ("outlook", outlook_name)]:
        r = post("campaigns", {
            "name": name,
            "type": "outbound",
            "plain_text": True,
            "open_tracking": False,
            "include_auto_replies_in_stats": True,
            "sequence_prioritization": "followups",
        })
        camp = r["data"]
        camp_id = camp["id"]
        print(f"  Created '{name}' → campaign_id={camp_id}")

        create_fresh_sequence(
            camp_id,
            f"{seq_title_prefix} - {variant_key.capitalize()}",
            primary_subj,
            variants,
        )
        created[variant_key] = camp_id
        time.sleep(0.5)
    return created


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 65)
    print("Business Sergeant - Full Campaign Setup")
    print("=" * 65)

    # ── STEP 1: Campaign 877 (Veterans - Google, ACTIVE, has 2 wrong steps)
    print("\n[1] Campaign 877 – Veterans Google: adding 5 brief variants...")
    print("    NOTE: Steps 6940 & 6942 ('veteran?' subject) are wrong —")
    print("    please DELETE them manually in the platform UI.")
    primary_877 = 6940
    add_variants_to_existing(877, primary_877, C1_VARIANTS)

    # ── STEP 2: Campaign 878 (Veterans - Outlook, no sequence yet)
    print("\n[2] Campaign 878 – Veterans Outlook: creating fresh sequence...")
    create_fresh_sequence(878, "Campaign 1: Veterans – Outlook", C1_PRIMARY_SUBJ, C1_VARIANTS)

    # ── STEP 3: Campaign 879 (Ops - Google, has A/B/D/E/F – add missing C: Halo Effect)
    print("\n[3] Campaign 879 – Ops Google: adding missing Variant C (halo effect)...")
    primary_879 = 6907
    add_variants_to_existing(879, primary_879, [C2_MISSING_VARIANT])
    print("    NOTE: Step 6907 subject spintax should include 'the halo effect'.")
    print("    Update that subject line manually in the platform UI.")

    # ── STEP 4: Campaign 880 (Ops - Outlook, same as 879)
    print("\n[4] Campaign 880 – Ops Outlook: adding missing Variant C (halo effect)...")
    primary_880 = 6912
    add_variants_to_existing(880, primary_880, [C2_MISSING_VARIANT])

    # ── STEP 5: Campaigns 881/882 (Open Roles) – already have all 4 variants. No additions.
    print("\n[5] Campaigns 881/882 – Open Roles: already complete (4 variants each). Skipping additions.")
    print("    NOTE: Existing step subjects in 881/882 need to be updated to lowercase spintax.")
    print("    Recommended primary subject: '{open_role_title}|{open_role_title} at {company}'")
    print("    Update manually in the platform UI.")

    # ── STEP 6: Create Campaign 4 (New to Role) – Google + Outlook
    print("\n[6] Creating Campaign 4: New to Role – Google + Outlook...")
    c4 = create_campaign_pair(
        "Campaign 4: New to Role - Google",
        "Campaign 4: New to Role - Outlook",
        C4_PRIMARY_SUBJ,
        C4_VARIANTS,
        "Campaign 4: New to Role",
    )

    # ── STEP 7: Create Campaign 5 (Missing Key Role) – Google + Outlook
    print("\n[7] Creating Campaign 5: Missing Key Role – Google + Outlook...")
    c5 = create_campaign_pair(
        "Campaign 5: Missing Key Role - Google",
        "Campaign 5: Missing Key Role - Outlook",
        C5_PRIMARY_SUBJ,
        C5_VARIANTS,
        "Campaign 5: Missing Key Role",
    )

    # ── SUMMARY
    print("\n" + "=" * 65)
    print("DONE – Summary")
    print("=" * 65)
    print("""
Campaigns updated / created:
  877  Campaign 1: Veterans – Google         (+5 correct variants added)
  878  Campaign 1: Veterans – Outlook        (fresh 5-variant sequence)
  879  Campaign 2: Ops Leaders – Google      (+halo effect variant added)
  880  Campaign 2: Ops Leaders – Outlook     (+halo effect variant added)
  881  Campaign 3: Open Roles – Google       (no change, already complete)
  882  Campaign 3: Open Roles – Outlook      (no change, already complete)""")
    print(f"  {c4['google']}  Campaign 4: New to Role – Google        (new, 3 variants)")
    print(f"  {c4['outlook']}  Campaign 4: New to Role – Outlook       (new, 3 variants)")
    print(f"  {c5['google']}  Campaign 5: Missing Key Role – Google   (new, 3 variants)")
    print(f"  {c5['outlook']}  Campaign 5: Missing Key Role – Outlook  (new, 3 variants)")

    print("""
Manual actions still needed (API does not allow updating existing steps):
  1. Campaign 877: DELETE steps 6940 & 6942 (subject = 'veteran?') in the UI.
  2. Campaigns 879/880: Update primary step subject to include 'the halo effect'
       in the spintax (e.g. add '|the halo effect' to the existing subject field).
  3. Campaigns 879/880: Existing steps 6907-6916 have 'Hi {FIRST_NAME},' prefix
       and a signature without the comma — update those 10 step bodies in the UI
       to match brief copy exactly.
  4. Campaigns 881/882: Subject lines on existing steps are uppercase — change
       to lowercase in the UI (e.g. '{OPEN_ROLE_TITLE}' → '{open_role_title}').
  5. All new campaigns (4 & 5) need leads imported via CSV.
""")


if __name__ == "__main__":
    main()
