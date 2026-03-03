"""
Create Creative Mint email sequences in EmailBison workspace 26.
Uses VISIBL_BISON_API_KEY with workspace_id=26 parameter.

Campaigns created:
  273 — The Gen Z Opportunity     (4 steps)
  274 — The Founder Story         (4 steps)
  275 — Real-World Tokenization   (4 steps)
  276 — Joelle Flynn Referral     (4 steps)
"""
import requests, os, time
from dotenv import load_dotenv
load_dotenv()

BASE_URL = 'https://send.breakoutcreatives.com/api'
KEY = os.getenv('VISIBL_BISON_API_KEY')
H = {'Authorization': f'Bearer {KEY}', 'Accept': 'application/json', 'Content-Type': 'application/json'}
WS = 26


def create_campaign(name):
    r = requests.post(f'{BASE_URL}/campaigns', headers=H,
        json={'name': name, 'workspace_id': WS}, timeout=30)
    r.raise_for_status()
    cid = r.json()['data']['id']
    print(f'  Campaign created: ID={cid} name={name!r}')
    return cid


def add_steps(cid, title, steps):
    r = requests.post(f'{BASE_URL}/campaigns/{cid}/sequence-steps', headers=H,
        json={'title': title, 'sequence_steps': steps, 'workspace_id': WS}, timeout=60)
    if r.ok:
        ids = [s['id'] for s in r.json().get('data', {}).get('sequence_steps', [])]
        print(f'  Steps OK ({title}): IDs={ids}')
    else:
        print(f'  FAIL ({title}) {r.status_code}: {r.text[:300]}')
    return r.ok


# ══════════════════════════════════════════════════════════════════════════════
# SEQUENCE 1 — The Gen Z Opportunity
# ══════════════════════════════════════════════════════════════════════════════
print('\n=== Sequence 1: The Gen Z Opportunity ===')
cid1 = create_campaign('Creative Mint — The Gen Z Opportunity')

S1_E1 = """Hi {FIRST_NAME},

We've been researching prospective investors who might be interested in what we're building at Creative Mint, and we discovered [fund name].

We're raising $500K-$750K on a SAFE to complete our platform and launch our first project.

The opportunity: Gen Z is drinking 20% less alcohol than millennials. The global NA wine market is \u20ac6.94B and growing ~10% a year, but lacks authentic, premium options.

We're solving this with a Web3 platform that helps established winemakers launch NA brands without risking their own capital. Supporters invest through security tokens and share in the upside.

Our platform is 80% complete. Our alpha partner is a woman-owned winemaker in Austria, interested in showcasing its wine heritage and leading the world in NA wine innovation. We are securing nondilutive grants from the Austrian government to facilitate this project and catalyze our growth.

My background: 30+ years in corporate securities law (Wilson Sonsini), tech investment banking (Merrill Lynch, BofA), and purpose-driven brands. I founded Little Pickle Press, which won Independent Publisher of the Year and was sold to Sourcebooks.

Are you open to a quick call?

Kind regards,
Rana DiOrio
Founder & CEO, Creative Mint"""

S1_E2 = """Hi {FIRST_NAME},

I'd like to add some context on why we started with wine.

Gen Z isn't just drinking less. They're seeking authentic, craft, sustainable options. The NA wine category is exploding, but most products are mass-market and uninspired.

We're partnering with established winemakers who have the craft expertise but lack the capital and distribution to launch new product lines. Our platform gives them a turnkey solution. Supporters invest through security tokens and share in the upside.

First project: a woman-owned, award-winning Austrian winemaker. We already know how we'll distribute the entire vintage before production starts.

The platform model scales beyond wine. We have LOIs with Cyprus Water Fund (clean water infrastructure) and HivedMusic (artist coin offerings).

Does this align with your current investment priorities? Please LMK.

Thank you!
Rana"""

S1_E3 = """Hi {FIRST_NAME},

I'm following up on Creative Mint.

We're raising $500K-$750K on a SAFE to complete our Web3 platform and launch our first project: premium NA wine with an established Austrian winemaker.

The market: Gen Z is drinking 20% less. NA wine is \u20ac6.94B and growing ~10% annually.

My background: 30+ years in securities law, tech investment banking (Merrill Lynch, BofA), and building purpose-driven brands. Founded Little Pickle Press, sold to Sourcebooks.

Our platform is 80% complete. Alpha partner secured. \u20ac2M Austrian innovation grant in process.

Are you open to a quick chat?

All my best,
Rana DiOrio
Founder & CEO, Creative Mint"""

S1_E4 = """Hi {FIRST_NAME},

Last email on Creative Mint.

We're raising $500K-$750K on a SAFE for a Web3 platform that helps established producers launch sustainable products via security tokens. Starting with non-alcoholic wine.

Gen Z is drinking less. The market is growing. We have an alpha partner and a platform that's 80% complete.

If timing works, I'd be pleased to walk you through it. If not, I'll try again when/if it makes sense.

Gratefully,
Rana DiOrio
Founder & CEO, Creative Mint"""

add_steps(cid1, 'Email 1 — Investor Intro', [
    {'email_subject': 'Introducing Creative Mint', 'email_body': S1_E1,
     'wait_in_days': 1, 'thread_reply': False},
])
time.sleep(0.5)
add_steps(cid1, 'Email 2 — Why Wine', [
    {'email_subject': 'Re:', 'email_body': S1_E2, 'wait_in_days': 3, 'thread_reply': True},
])
time.sleep(0.5)
add_steps(cid1, 'Email 3 — Follow-up', [
    {'email_subject': '{Creative Mint // {FIRST_NAME}|Quick follow-up}', 'email_body': S1_E3,
     'wait_in_days': 4, 'thread_reply': False},
])
time.sleep(0.5)
add_steps(cid1, 'Email 4 — Last Note', [
    {'email_subject': '{Last note|Final follow-up}', 'email_body': S1_E4,
     'wait_in_days': 4, 'thread_reply': False},
])
print('Sequence 1 done.')


# ══════════════════════════════════════════════════════════════════════════════
# SEQUENCE 2 — The Founder Story
# ══════════════════════════════════════════════════════════════════════════════
print('\n=== Sequence 2: The Founder Story ===')
cid2 = create_campaign('Creative Mint — The Founder Story')

S2_E1 = """Hi {FIRST_NAME},

Been looking into funds that might have an appetite for what we're building at Creative Mint and {{fund_name}} came up.

We're raising $500K-$750K on a SAFE to complete our platform and launch our first project.

Quick background on me: I've spent 30+ years at the intersection of securities law, capital markets, and purpose-driven brands. I started as a corporate attorney at Wilson Sonsini, moved to tech investment banking at Merrill Lynch and Bank of America, then founded Little Pickle Press, which won Independent Publisher of the Year and was sold to Sourcebooks.

Creative Mint is the synthesis of all of it. We're building a Web3 platform that helps established producers launch sustainable products via security tokens. Supporters invest and share in the upside. We'll also host a marketplace for conscious consumers.

First project: premium NA wine with a woman-owned Austrian winemaker. Gen Z is drinking 20% less alcohol. The NA wine market is \u20ac6.94B and growing ~10% a year.

Are you open to a quick call?

Kind regards,
Rana DiOrio
Founder & CEO, Creative Mint"""

S2_E2 = """Hi {FIRST_NAME},

I wanted to explain why I started Creative Mint.

I've worked in securities law and investment banking my whole career. I know how capital formation works and how broken it is for small producers. Meanwhile, I spent 9 years building Little Pickle Press and saw firsthand how hard it is for creators to fund and commercialize new products.

Creative Mint connects those two worlds. We give established producers a turnkey way to raise capital through security tokens, without giving up control or risking their own money.

Our platform is 80% complete. Our alpha partner is secured. We're 6 months into a \u20ac2M Austrian innovation grant process.

This isn't speculative crypto. It's real-world tokenization of real products.

Does it make sense to have a conversation? Please LMK.

Thank you!
Rana"""

S2_E3 = """Hi {FIRST_NAME},

I'm following up on Creative Mint.

We're raising $500K-$750K on a SAFE to complete our Web3 platform and launch our first project.

My background: 30+ years in securities law (Wilson Sonsini), tech investment banking (Merrill Lynch, BofA), and purpose-driven brands. I founded Little Pickle Press, Independent Publisher of the Year, and sold it to Sourcebooks.

What we're building: a platform that helps established producers launch sustainable products via security tokens. Our first project is a premium NA wine. Gen Z is drinking 20% less. The addressable market is \u20ac6.94B and growing.

The platform is almost complete. Our alpha partner is secured. We have \u20ac2M grants in process.

Are you open to a quick chat?

All my best,
Rana DiOrio
Founder & CEO, Creative Mint"""

S2_E4 = """Hi {FIRST_NAME},

Last email regarding Creative Mint.

We're raising $500K-$750K on a SAFE. We've built a Web3 platform for sustainable product launches, starting with NA wine.

My background: 30+ years of securities law, tech IB, purpose-driven brands. I founded and sold Little Pickle Press.

If timing works, I'd welcome the opportunity to chat. If not, I'll try again when/if it makes sense.

Gratefully,
Rana DiOrio
Founder & CEO, Creative Mint"""

add_steps(cid2, 'Email 1 — Founder Intro', [
    {'email_subject': 'Creative Mint: Web3 platform for consumer brands',
     'email_body': S2_E1, 'wait_in_days': 1, 'thread_reply': False},
])
time.sleep(0.5)
add_steps(cid2, 'Email 2 — Why I Started Creative Mint', [
    {'email_subject': 'Re:', 'email_body': S2_E2, 'wait_in_days': 3, 'thread_reply': True},
])
time.sleep(0.5)
add_steps(cid2, 'Email 3 — Follow-up', [
    {'email_subject': 'Following up on Creative Mint',
     'email_body': S2_E3, 'wait_in_days': 4, 'thread_reply': False},
])
time.sleep(0.5)
add_steps(cid2, 'Email 4 — Final Email', [
    {'email_subject': 'Final email', 'email_body': S2_E4, 'wait_in_days': 4, 'thread_reply': False},
])
print('Sequence 2 done.')


# ══════════════════════════════════════════════════════════════════════════════
# SEQUENCE 3 — Real-World Tokenization
# ══════════════════════════════════════════════════════════════════════════════
print('\n=== Sequence 3: Real-World Tokenization ===')
cid3 = create_campaign('Creative Mint — Real-World Tokenization')

S3_E1 = """Hi {FIRST_NAME},

We've been researching investors who might be interested in real-world applications of Web3, and we discovered {{fund_name}}.

We're raising $500K-$750K on a SAFE to complete our platform and launch our first project.

Most Web3 is speculative. Creative Mint is different. We're building a platform that helps established producers fund, develop, and commercialize sustainable products via security tokens. Supporters invest and share in the upside.

First project: premium NA wine with a woman-owned Austrian winemaker. Gen Z is drinking 20% less alcohol. The NA wine market is \u20ac6.94B and growing ~10% annually.

My background: 30+ years in corporate securities law (Wilson Sonsini), tech investment banking (Merrill Lynch, BofA), and purpose-driven brands. I founded Little Pickle Press, which won the Independent Publisher of the Year award, and sold it to Sourcebooks.

Our platform is 80% complete. Our alpha partner is secured. We have \u20ac2M Austrian innovation grants in process.

Are you open to a quick call?

Kind regards,
Rana DiOrio
Founder & CEO, Creative Mint"""

S3_E2 = """Hi {FIRST_NAME},

I wanted to explain what makes this different from typical Web3.

We're not launching speculative tokens. We're using security tokens to fund real products with real revenue potential made by established producers.

Our revenue model includes platform fees, token allocation, and marketplace inclusion and transaction fees.

The first industry vertical is non-alcoholic wine, but the platform scales across other verticals. We have LOIs with the Cyprus Water Fund (clean-water infrastructure) and HivedMusic (artist coin offerings).

Does this align with your current investment thesis?

All my best,
Rana"""

S3_E3 = """Hi {FIRST_NAME},

I'm following up on Creative Mint. We're raising $500K-$750K on a SAFE to complete our platform and launch our first project.

What we do: Web3 platform for real-world product launches via security tokens. Not speculative crypto. Real products, real revenue.

First project: Premium NA wine.

Why NA wine? And why now?
* Gen Z is drinking 20% less, and people are becoming more health-conscious
* The US Surgeon General issued a warning last year on alcohol's health impact
* \u20ac6.94B market growing ~10% annually
* Existing NA wines are sub-par, with massive room for improvement

Our advantage: We're partnering with an Austrian university to improve the de-alcoholization process. Not just removing alcohol, but engineering a better, premium product.

My background: 30+ years securities law, tech IB, purpose-driven brands. Founded and sold Little Pickle Press.

Traction: Platform nearly complete. Alpha partner secured. \u20ac2M grants in process.

Are you open to a quick conversation? Please LMK.

Thank you!
Rana DiOrio
Founder & CEO, Creative Mint"""

S3_E4 = """Hi {FIRST_NAME},

Last email regarding Creative Mint.

We're raising $500K-$750K on a SAFE. Web3 platform for real-world product launches via security tokens. Starting with NA wine.

Not speculative. Real products, real revenue model.

If timing works, I'd welcome the opportunity to chat. If not, I'll try again when/if it makes sense.

Take care,
Rana DiOrio
Founder & CEO, Creative Mint"""

add_steps(cid3, 'Email 1 — RWT Intro', [
    {'email_subject': 'Real-world tokenization',
     'email_body': S3_E1, 'wait_in_days': 1, 'thread_reply': False},
])
time.sleep(0.5)
add_steps(cid3, 'Email 2 — What Makes This Different', [
    {'email_subject': 'Re:', 'email_body': S3_E2, 'wait_in_days': 3, 'thread_reply': True},
])
time.sleep(0.5)
add_steps(cid3, 'Email 3 — Follow-up', [
    {'email_subject': '{Creative Mint // {FIRST_NAME}|Security tokens for real products}',
     'email_body': S3_E3, 'wait_in_days': 4, 'thread_reply': False},
])
time.sleep(0.5)
add_steps(cid3, 'Email 4 — Final Follow-up', [
    {'email_subject': 'Final follow-up', 'email_body': S3_E4, 'wait_in_days': 4, 'thread_reply': False},
])
print('Sequence 3 done.')


# ══════════════════════════════════════════════════════════════════════════════
# SEQUENCE 4 — Joelle Flynn Referral
# ══════════════════════════════════════════════════════════════════════════════
print('\n=== Sequence 4: Joelle Flynn Referral ===')
cid4 = create_campaign('Creative Mint — Joelle Flynn Referral')

S4_E1 = """Hi {FIRST_NAME},

Joelle Flynn suggested I reach out to {you|{fund_name}}. She thought there might be alignment between what we're building at Creative Mint and your focus on investing in female-founded companies.

We're raising $500K\u2013$750K with a SAFE to complete our platform and launch our first project.

Creative Mint is a Web3 platform that helps established producers fund, develop, and commercialize premium sustainable products via security tokens. Supporters invest and share in the upside.

Our first project is a premium non-alcoholic wine with a woman-owned Austrian winemaker, supported by the Austrian government. Gen Z is drinking 20% less alcohol. The NA wine market is \u20ac6.94B and growing ~10% a year.

Quick background on me: 30+ years in corporate securities law (Wilson Sonsini), tech investment banking (Merrill Lynch, BofA, North Point M&A), and purpose-driven brands. I founded Little Pickle Press, which won Independent Publisher of the Year and sold it to Sourcebooks.

Are you open to a quick call? Please LMK.

Kind regards,
Rana DiOrio
Founder & CEO, Creative Mint"""

S4_E2 = """Hi {FIRST_NAME},

I wanted to add a bit more context on Creative Mint and why Joelle thought this would resonate with you.

Creative Mint is female-founded and led. I've spent my career in securities law and capital markets, and I've seen firsthand how underserved female-led ventures are when it comes to accessing capital\u2014especially in emerging categories like Web3.

Our platform solves a real problem: established producers with craft expertise but no capital to launch new product lines. We give them a turnkey solution leveraging security tokens. Supporters invest and share in the upside.

Our alpha partner is also a woman-owned winemaker in Austria. Together, we are securing non-dilutive grants from the Austrian government. The platform model scales beyond wine\u2014we have LOIs with Cyprus Water Fund and HivedMusic.

Does this align with your current investment priorities?

Thanks for giving it some thought!
Rana"""

S4_E3 = """Hi {FIRST_NAME},

Following up on my earlier note. Joelle Flynn connected us because of your focus on female-founded companies.

We're raising $500K\u2013$750K with a SAFE to complete our Web3 platform and launch our first project: premium NA wine with an established Austrian winemaker.

The market: Gen Z is drinking 20% less. NA wine is \u20ac6.94B and growing ~10% annually.

My background: 30+ years in securities law (Wilson Sonsini), tech investment banking (Merrill Lynch, BofA, North Point M&A), and building purpose-driven brands. Founded Little Pickle Press, sold to Sourcebooks.

Platform is 80% complete. Alpha partner secured. \u20ac2M Austrian innovation grants in process.

Worth a quick chat?

Gratefully,
Rana DiOrio
Founder & CEO, Creative Mint"""

S4_E4 = """Hi {FIRST_NAME},

Last email on Creative Mint.

We're raising $500K\u2013$750K with a SAFE for a female-founded Web3 platform that helps established producers launch sustainable products via security tokens. Starting with premium NA wine.

Joelle Flynn thought there'd be a fit given your focus on backing women-led companies. My background: 30+ years of securities law, tech IB, purpose-driven brands. Founded and sold Little Pickle Press.

If timing works, I'd be happy to walk you through it. If not, I'll circle back when/if our priorities align.

Please take care,
Rana DiOrio
Founder & CEO, Creative Mint"""

add_steps(cid4, 'Email 1 — Joelle Flynn Intro', [
    {'email_subject': 'Joelle Flynn suggested I reach out to you.',
     'email_body': S4_E1, 'wait_in_days': 1, 'thread_reply': False},
])
time.sleep(0.5)
add_steps(cid4, 'Email 2 — Female-Founded Context', [
    {'email_subject': 'Re:', 'email_body': S4_E2, 'wait_in_days': 3, 'thread_reply': True},
])
time.sleep(0.5)
add_steps(cid4, 'Email 3 — Joelle Follow-up', [
    {'email_subject': 'Following up\u2014Joelle Flynn recommendation',
     'email_body': S4_E3, 'wait_in_days': 4, 'thread_reply': False},
])
time.sleep(0.5)
add_steps(cid4, 'Email 4 — Final Follow-up', [
    {'email_subject': 'Final follow-up', 'email_body': S4_E4, 'wait_in_days': 4, 'thread_reply': False},
])
print('Sequence 4 done.')
