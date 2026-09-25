# -*- coding: utf-8 -*-
"""Tests de lecture des reponses. Le robot ne doit jamais repondre a tort."""
import sys, os
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import intent, pick_slot

OK = FAIL = 0
def eq(got, want, label):
    global OK, FAIL
    if got == want:
        OK += 1
    else:
        FAIL += 1
        print(f"  ECHEC {label}: attendu {want!r}, obtenu {got!r}")

# ------------------------------------------------ intentions
for txt, want in [
    ("Yes I'm interested, send me more info", "positive"),
    ("Sounds good, happy to chat", "positive"),
    ("Ok tx", "unclear"),                      # la vraie reponse de Bob
    ("sure, send it over", "positive"),
    ("Not interested, we already have a vendor", "negative"),
    ("No thanks", "negative"),
    ("Please remove me from your list", "optout"),
    ("unsubscribe", "optout"),
    ("I am out of office until October 3rd", "out_of_office"),
    ("Automatic reply: I have limited access to my email", "out_of_office"),
    ("How much does this cost?", "human"),
    ("Who are you and where did you get my email?", "human"),
    ("I've left the company, reach out to Maria", "human"),
    ("This is spam", "human"),
    ("Interested but not at this time", "unclear"),   # contradictoire
    ("", "unclear"),
]:
    eq(intent(txt), want, f"intent({txt[:32]!r})")

# un en-tete d'auto-reponse l'emporte, meme sur un texte enthousiaste
eq(intent("Yes! Very interested.", has_auto_header=True), "out_of_office", "en-tete auto")
# un desabonnement l'emporte sur un positif dans le meme message
eq(intent("sounds interesting but please unsubscribe me"), "optout", "optout > positive")

# ------------------------------------------------ choix du creneau
TZ = timezone.utc
slots = [datetime(2026, 9, 29, 14, 0, tzinfo=TZ),   # mardi 14h
         datetime(2026, 9, 30, 10, 0, tzinfo=TZ),   # mercredi 10h
         datetime(2026, 10, 1, 16, 30, tzinfo=TZ)]  # jeudi 16h30

eq(pick_slot("Tuesday works", slots)[0], slots[0], "par jour")
eq(pick_slot("Wednesday at 10 is good", slots)[0], slots[1], "jour + heure")
eq(pick_slot("the 4:30 one", slots)[0], slots[2], "heure avec minutes")
eq(pick_slot("let's do the first one", slots)[0], slots[0], "rang")
eq(pick_slot("option 3", slots)[0], slots[2], "option n")
eq(pick_slot("any of those works", slots)[0], slots[0], "n'importe lequel")
eq(pick_slot("none of those work for me", slots)[0], None, "refus")
eq(pick_slot("sounds good", slots)[0], None, "trop vague -> escalade")
eq(pick_slot("how about Friday?", slots)[0], None, "autre jour -> escalade")
eq(pick_slot("Tuesday or Wednesday both fine", slots)[0], None, "deux jours -> ambigu")
eq(pick_slot("10am", [])[0], None, "aucun creneau en memoire")

# ---------------------------------------------------------------- cas reels
# Reponses reellement recues dans la boite Haven. Chacune etait mal classee
# avant que le texte cite ne soit coupe : le robot lisait notre propre
# argumentaire et prenait un "STOP" pour un oui.
REELS = [
    ("STOP\nDan Minor\nV.P. of Sales\n-----Original Message-----\n"
     "From: James Thompson <james_thompson@haven...>\nSent: ...\n"
     "Happy to build you a list of 2,000 to 5,000 buyers, interested?", "optout"),
    ("remove\nMike Campbell\nPrincipal\n737 Regal Row Dallas TX", "optout"),
    ("All set. Please remove/unsubscribe\nDean Burrows, President", "optout"),
    ("Wrong! We don't sell mechanical seals.\nMilan\nSent from my iPhone\n"
     "> On Sep 25, 2026, at 8:36 AM, Joshua Flores wrote:\n"
     "> Happy to build you a list, just confirm and I'll send it over.", "negative"),
    ("0.00% chance! I'm in a very, very niche market... only manufacturer in "
     "Canada. I know my customers!\nSent from my iPhone", "negative"),
    # une reponse qui n'est QUE de la citation ne dit rien : jamais "positive"
    ("Sent from my iPhone\n> On Sep 25, 2026, at 10:42 AM, Betty Lopez wrote:\n"
     "> CAUTION: EXTERNAL EMAIL\n> Happy to build you a list of 2,000 buyers, "
     "interested? Just confirm that's the right market.", "unclear"),
    ("Ok Tx\nGet Outlook for Android\nFrom: Charles Hill\nSent: Friday\n"
     "Happy to build you a list of 2,000 to 5,000 paving contractors", "unclear"),
    ("So if I look at the list and feel like they're not the right contacts, "
     "we're not obligated to do anything?\nGreg", "unclear"),
    ("Morning David... I'm fully retired from Bentley World Packaging! "
     "My son Todd owns it now.", "unclear"),
]
for txt, want in REELS:
    eq(intent(txt), want, f"reel({txt[:34]!r})")

# et le garde-fou central : aucune de ces reponses ne declenche un envoi
for txt, _ in REELS:
    got = intent(txt)
    eq(got in ("optout", "negative", "unclear", "human", "out_of_office"), True,
       f"pas de reponse auto pour {txt[:24]!r}")

print(f"\n{OK} tests passes, {FAIL} echecs")
sys.exit(1 if FAIL else 0)
