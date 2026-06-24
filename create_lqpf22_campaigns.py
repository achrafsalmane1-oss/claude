#!/usr/bin/env python3
import requests
import json

API_BASE = "https://personal.ottoresults.com/api"
TOKEN = "27|lPHnLHDjn3QN9dQmSpNNHK8mvStTRbpKg6O5Iazeaeba52b8"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def create_campaign(name):
    resp = requests.post(f"{API_BASE}/campaigns", headers=HEADERS, json={"name": name})
    if resp.status_code in (200, 201):
        data = resp.json()
        cid = data.get("data", {}).get("id") or data.get("id")
        print(f"Created campaign '{name}' -> ID {cid}")
        return cid
    else:
        print(f"ERROR creating campaign '{name}': {resp.status_code} {resp.text}")
        return None

def create_sequence(campaign_id, title, steps):
    payload = {"title": title, "sequence_steps": steps}
    resp = requests.post(
        f"{API_BASE}/campaigns/v1.1/{campaign_id}/sequence-steps",
        headers=HEADERS,
        json=payload,
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        sid = data.get("data", {}).get("id") or data.get("id")
        print(f"Created sequence '{title}' for campaign {campaign_id} -> seq ID {sid}")
        return sid
    else:
        print(f"ERROR creating sequence for campaign {campaign_id}: {resp.status_code} {resp.text}")
        return None

def a(url, text):
    return f'<a href="{url}">{text}</a>'

# ─── LINKS ───────────────────────────────────────────────────────────────────
L = {
    "FR": {
        "teaser":   "https://youtu.be/iG17dTd4Mdk?si=GYLkckMWVpOtKwYI",
        "vsl":      "https://youtu.be/Q4-g6hi0Z7c",
        "webinar":  "https://www.youtube.com/live/KW0Tyeh5T_Q?si=VK7BFYFJRtFSego8",
        "brochure": "https://canva.link/jl2lm00tw0dqcnv",
        "dataroom": "https://landquiremgmt.sharepoint.com/:f:/s/Shared/IgAp237aGDknSIcw4RcggP7oAQ6RHO_uvtl0hSdIz15nUsc?e=zDhcMN",
        "rdv":      "https://api.leadconnectorhq.com/widget/bookings/landquire-rendezvous",
    },
    "EN": {
        "teaser":   "https://youtu.be/4lryy582NnA?si=taz6FmADJwe7KBK1",
        "vsl":      "https://youtu.be/sEqx6JNIPyM",
        "webinar":  "https://www.youtube.com/live/1QyZDwWCD3c?si=EySsKqzsHUsq4ZzS",
        "brochure": "https://canva.link/rjmctbgkn740u51",
        "dataroom": "https://landquiremgmt.sharepoint.com/:f:/s/Shared/IgAp237aGDknSIcw4RcggP7oAQ6RHO_uvtl0hSdIz15nUsc?e=zDhcMN",
        "rdv":      "https://api.leadconnectorhq.com/widget/bookings/take-an-appointment-with-our-experts",
    },
    "ES": {
        "teaser":   "https://youtu.be/4lryy582NnA?si=taz6FmADJwe7KBK1",
        "vsl":      "https://youtu.be/sEqx6JNIPyM",
        "webinar":  "https://www.youtube.com/live/1QyZDwWCD3c?si=EySsKqzsHUsq4ZzS",
        "brochure": "https://canva.link/rjmctbgkn740u51",
        "dataroom": "https://landquiremgmt.sharepoint.com/:f:/s/Shared/IgAp237aGDknSIcw4RcggP7oAQ6RHO_uvtl0hSdIz15nUsc?e=zDhcMN",
        "rdv":      "https://api.leadconnectorhq.com/widget/bookings/landquire-spa-team",
    },
    "PT": {
        "teaser":   "https://youtu.be/4lryy582NnA?si=taz6FmADJwe7KBK1",
        "vsl":      "https://youtu.be/sEqx6JNIPyM",
        "webinar":  "https://www.youtube.com/live/1QyZDwWCD3c?si=EySsKqzsHUsq4ZzS",
        "brochure": "https://canva.link/rjmctbgkn740u51",
        "dataroom": "https://landquiremgmt.sharepoint.com/:f:/s/Shared/IgAp237aGDknSIcw4RcggP7oAQ6RHO_uvtl0hSdIz15nUsc?e=zDhcMN",
        "rdv":      "https://api.leadconnectorhq.com/widget/bookings/landquire-portuguese",
    },
}

SIGNATURE_FR = """<p>Cordialement,</p>
<p><strong>L'équipe LandQuire</strong><br>
<em>Investissez dans l'immobilier qui compte.</em></p>"""

SIGNATURE_EN = """<p>Best regards,</p>
<p><strong>The LandQuire Team</strong><br>
<em>Invest in real estate that matters.</em></p>"""

SIGNATURE_ES = """<p>Atentamente,</p>
<p><strong>El equipo de LandQuire</strong><br>
<em>Invierta en bienes raíces que importan.</em></p>"""

SIGNATURE_PT = """<p>Atenciosamente,</p>
<p><strong>A equipa LandQuire</strong><br>
<em>Invista no imobiliário que importa.</em></p>"""

# ─── EMAIL BODIES ─────────────────────────────────────────────────────────────

def steps_fr(lk):
    return [
        {
            "email_subject": "{Découvrez LQPF22, notre nouvelle opportunité immobilière|{FIRST_NAME}, une nouvelle opportunité immobilière vous attend}",
            "order": 1,
            "wait_in_days": 1,
            "variant": True,
            "thread_reply": False,
            "email_body": f"""<p>Bonjour {"{FIRST_NAME}"},</p>
<p>Je me permets de vous contacter car nous venons de lancer <strong>LQPF22</strong>, notre dernier portefeuille immobilier, et je pense que cette opportunité pourrait vous intéresser.</p>
<p>LQPF22 est un portefeuille d'actifs immobiliers soigneusement sélectionnés, conçu pour offrir un rendement attractif tout en limitant l'exposition au risque grâce à une diversification géographique et sectorielle.</p>
<p>Pour vous donner un premier aperçu, j'ai préparé une courte vidéo de présentation :</p>
<p>{a(lk["teaser"], "Voir la vidéo de présentation LQPF22")}</p>
<p>Vous pouvez également télécharger notre brochure détaillée ici :</p>
<p>{a(lk["brochure"], "Télécharger la brochure LQPF22")}</p>
<p>Si vous souhaitez en savoir plus ou discuter de la manière dont LQPF22 pourrait s'intégrer dans votre stratégie patrimoniale, je reste disponible pour un échange.</p>
{SIGNATURE_FR}
<p><em>P.S. Si vous préférez fixer un rendez-vous directement, vous pouvez le faire ici : {a(lk["rdv"], "Prendre rendez-vous")}</em></p>""",
        },
        {
            "email_subject": "{FIRST_NAME}, avez-vous eu l'occasion de regarder la présentation ?",
            "order": 2,
            "wait_in_days": 3,
            "variant": False,
            "thread_reply": False,
            "email_body": f"""<p>Bonjour {"{FIRST_NAME}"},</p>
<p>Je reviens vers vous suite à mon précédent message concernant <strong>LQPF22</strong>.</p>
<p>J'aimerais vous partager une présentation plus approfondie du projet, réalisée par Romain, notre directeur des investissements. Cette vidéo détaille la thèse d'investissement, les actifs sélectionnés et les projections de rendement :</p>
<p>{a(lk["vsl"], "Regarder la présentation complète par Romain")}</p>
<p>Pour les investisseurs souhaitant aller plus loin, nous avons également mis en place une data room sécurisée contenant l'ensemble des documents due diligence :</p>
<p>{a(lk["dataroom"], "Accéder à la data room LQPF22")}</p>
<p>N'hésitez pas à me faire part de vos questions ou observations après visionnage.</p>
{SIGNATURE_FR}
<p><em>P.S. Vous pouvez également réserver un créneau pour un appel de 20 minutes avec notre équipe : {a(lk["rdv"], "Réserver un créneau")}</em></p>""",
        },
        {
            "email_subject": "{FIRST_NAME}, dernier message de notre part concernant LQPF22",
            "order": 3,
            "wait_in_days": 3,
            "variant": False,
            "thread_reply": False,
            "email_body": f"""<p>Bonjour {"{FIRST_NAME}"},</p>
<p>Je ne voudrais pas vous importuner davantage, aussi ce sera mon dernier message concernant <strong>LQPF22</strong>.</p>
<p>Nous avons récemment organisé un webinaire de présentation du portefeuille. Si vous souhaitez le visionner, il est disponible en replay ici :</p>
<p>{a(lk["webinar"], "Visionner le replay du webinaire LQPF22")}</p>
<p>Pour prendre rendez-vous avec un membre de notre équipe :</p>
<p>{a(lk["rdv"], "Réserver un rendez-vous")}</p>
<p>En résumé, voici les ressources mises à votre disposition :</p>
<ul>
<li>{a(lk["teaser"], "Vidéo de présentation")}</li>
<li>{a(lk["brochure"], "Brochure LQPF22")}</li>
<li>{a(lk["vsl"], "Présentation complète par Romain")}</li>
<li>{a(lk["dataroom"], "Data room (documents due diligence)")}</li>
</ul>
<p>Je reste bien entendu disponible si vous souhaitez reprendre contact à un autre moment.</p>
{SIGNATURE_FR}""",
        },
    ]

def steps_en(lk):
    return [
        {
            "email_subject": "{Discover LQPF22, our latest real estate opportunity|{FIRST_NAME}, a new real estate opportunity awaits}",
            "order": 1,
            "wait_in_days": 1,
            "variant": True,
            "thread_reply": False,
            "email_body": f"""<p>Hi {"{FIRST_NAME}"},</p>
<p>I'm reaching out because we've just launched <strong>LQPF22</strong>, our latest real estate portfolio, and I believe this opportunity could be of interest to you.</p>
<p>LQPF22 is a carefully curated portfolio of real estate assets, designed to deliver attractive returns while limiting risk exposure through geographic and sector diversification.</p>
<p>To give you an initial overview, I've prepared a short introductory video:</p>
<p>{a(lk["teaser"], "Watch the LQPF22 presentation video")}</p>
<p>You can also download our detailed brochure here:</p>
<p>{a(lk["brochure"], "Download the LQPF22 brochure")}</p>
<p>If you'd like to learn more or discuss how LQPF22 could fit into your investment strategy, I'm available for a conversation.</p>
{SIGNATURE_EN}
<p><em>P.S. If you'd prefer to book a meeting directly, you can do so here: {a(lk["rdv"], "Book an appointment")}</em></p>""",
        },
        {
            "email_subject": "{FIRST_NAME}, did you have a chance to watch the presentation?",
            "order": 2,
            "wait_in_days": 3,
            "variant": False,
            "thread_reply": False,
            "email_body": f"""<p>Hi {"{FIRST_NAME}"},</p>
<p>Following up on my previous message about <strong>LQPF22</strong>.</p>
<p>I'd like to share a more in-depth presentation of the project, prepared by Romain, our Head of Investments. This video covers the investment thesis, selected assets and return projections:</p>
<p>{a(lk["vsl"], "Watch the full presentation by Romain")}</p>
<p>For investors who want to go further, we've also set up a secure data room containing all due diligence documents:</p>
<p>{a(lk["dataroom"], "Access the LQPF22 data room")}</p>
<p>Please feel free to share any questions or thoughts after watching.</p>
{SIGNATURE_EN}
<p><em>P.S. You can also book a 20-minute call with our team: {a(lk["rdv"], "Book a time slot")}</em></p>""",
        },
        {
            "email_subject": "{FIRST_NAME}, one last message from us regarding LQPF22",
            "order": 3,
            "wait_in_days": 3,
            "variant": False,
            "thread_reply": False,
            "email_body": f"""<p>Hi {"{FIRST_NAME}"},</p>
<p>I don't want to take up any more of your time, so this will be my last message regarding <strong>LQPF22</strong>.</p>
<p>We recently hosted a portfolio presentation webinar. If you'd like to watch it, the replay is available here:</p>
<p>{a(lk["webinar"], "Watch the LQPF22 webinar replay")}</p>
<p>To schedule a call with a member of our team:</p>
<p>{a(lk["rdv"], "Book an appointment")}</p>
<p>Here's a summary of all resources available to you:</p>
<ul>
<li>{a(lk["teaser"], "Presentation video")}</li>
<li>{a(lk["brochure"], "LQPF22 brochure")}</li>
<li>{a(lk["vsl"], "Full presentation by Romain")}</li>
<li>{a(lk["dataroom"], "Data room (due diligence documents)")}</li>
</ul>
<p>I remain available should you wish to get in touch at a later stage.</p>
{SIGNATURE_EN}""",
        },
    ]

def steps_es(lk):
    return [
        {
            "email_subject": "{Descubra LQPF22, nuestra nueva oportunidad inmobiliaria|{FIRST_NAME}, una nueva oportunidad inmobiliaria le espera}",
            "order": 1,
            "wait_in_days": 1,
            "variant": True,
            "thread_reply": False,
            "email_body": f"""<p>Estimado/a {"{FIRST_NAME}"},</p>
<p>Me pongo en contacto con usted porque acabamos de lanzar <strong>LQPF22</strong>, nuestra última cartera inmobiliaria, y creo que esta oportunidad podría ser de su interés.</p>
<p>LQPF22 es una cartera de activos inmobiliarios cuidadosamente seleccionados, diseñada para ofrecer una rentabilidad atractiva mientras se limita la exposición al riesgo mediante la diversificación geográfica y sectorial.</p>
<p>Para darle una primera visión, he preparado un breve vídeo de presentación:</p>
<p>{a(lk["teaser"], "Ver el vídeo de presentación de LQPF22")}</p>
<p>También puede descargar nuestro folleto detallado aquí:</p>
<p>{a(lk["brochure"], "Descargar el folleto de LQPF22")}</p>
<p>Si desea obtener más información o hablar sobre cómo LQPF22 podría encajar en su estrategia de inversión, estoy a su disposición.</p>
{SIGNATURE_ES}
<p><em>P.D. Si prefiere concertar una cita directamente, puede hacerlo aquí: {a(lk["rdv"], "Reservar una cita")}</em></p>""",
        },
        {
            "email_subject": "{FIRST_NAME}, ¿ha tenido ocasión de ver la presentación?",
            "order": 2,
            "wait_in_days": 3,
            "variant": False,
            "thread_reply": False,
            "email_body": f"""<p>Estimado/a {"{FIRST_NAME}"},</p>
<p>Le escribo en seguimiento a mi mensaje anterior sobre <strong>LQPF22</strong>.</p>
<p>Me gustaría compartir una presentación más detallada del proyecto, realizada por Romain, nuestro Director de Inversiones. Este vídeo cubre la tesis de inversión, los activos seleccionados y las proyecciones de rentabilidad:</p>
<p>{a(lk["vsl"], "Ver la presentación completa de Romain")}</p>
<p>Para los inversores que deseen profundizar más, también hemos habilitado una sala de datos segura con todos los documentos de due diligence:</p>
<p>{a(lk["dataroom"], "Acceder a la sala de datos de LQPF22")}</p>
<p>No dude en compartir sus preguntas o comentarios tras verlo.</p>
{SIGNATURE_ES}
<p><em>P.D. También puede reservar una llamada de 20 minutos con nuestro equipo: {a(lk["rdv"], "Reservar un horario")}</em></p>""",
        },
        {
            "email_subject": "{FIRST_NAME}, último mensaje de nuestra parte sobre LQPF22",
            "order": 3,
            "wait_in_days": 3,
            "variant": False,
            "thread_reply": False,
            "email_body": f"""<p>Estimado/a {"{FIRST_NAME}"},</p>
<p>No quisiera molestarle más, por lo que este será mi último mensaje sobre <strong>LQPF22</strong>.</p>
<p>Recientemente celebramos un webinar de presentación de la cartera. Si desea verlo, el replay está disponible aquí:</p>
<p>{a(lk["webinar"], "Ver el replay del webinar de LQPF22")}</p>
<p>Para programar una llamada con un miembro de nuestro equipo:</p>
<p>{a(lk["rdv"], "Reservar una cita")}</p>
<p>A continuación, un resumen de todos los recursos disponibles:</p>
<ul>
<li>{a(lk["teaser"], "Vídeo de presentación")}</li>
<li>{a(lk["brochure"], "Folleto de LQPF22")}</li>
<li>{a(lk["vsl"], "Presentación completa de Romain")}</li>
<li>{a(lk["dataroom"], "Sala de datos (documentos de due diligence)")}</li>
</ul>
<p>Permanezco a su disposición si desea retomar el contacto en otro momento.</p>
{SIGNATURE_ES}""",
        },
    ]

def steps_pt(lk):
    return [
        {
            "email_subject": "{Descubra o LQPF22, a nossa nova oportunidade imobiliária|{FIRST_NAME}, uma nova oportunidade imobiliária aguarda por si}",
            "order": 1,
            "wait_in_days": 1,
            "variant": True,
            "thread_reply": False,
            "email_body": f"""<p>Caro/a {"{FIRST_NAME}"},</p>
<p>Entro em contacto consigo porque acabámos de lançar o <strong>LQPF22</strong>, o nosso mais recente portefólio imobiliário, e acredito que esta oportunidade pode ser do seu interesse.</p>
<p>O LQPF22 é um portefólio de ativos imobiliários cuidadosamente selecionados, concebido para oferecer rentabilidades atrativas enquanto limita a exposição ao risco através da diversificação geográfica e setorial.</p>
<p>Para lhe dar uma primeira visão geral, preparei um breve vídeo de apresentação:</p>
<p>{a(lk["teaser"], "Ver o vídeo de apresentação do LQPF22")}</p>
<p>Também pode transferir o nosso brochure detalhado aqui:</p>
<p>{a(lk["brochure"], "Transferir o brochure do LQPF22")}</p>
<p>Se desejar saber mais ou discutir como o LQPF22 pode integrar a sua estratégia de investimento, estou disponível para uma conversa.</p>
{SIGNATURE_PT}
<p><em>P.S. Se preferir marcar uma reunião diretamente, pode fazê-lo aqui: {a(lk["rdv"], "Marcar uma reunião")}</em></p>""",
        },
        {
            "email_subject": "{FIRST_NAME}, teve oportunidade de ver a apresentação?",
            "order": 2,
            "wait_in_days": 3,
            "variant": False,
            "thread_reply": False,
            "email_body": f"""<p>Caro/a {"{FIRST_NAME}"},</p>
<p>Dou seguimento à minha mensagem anterior sobre o <strong>LQPF22</strong>.</p>
<p>Gostaria de partilhar uma apresentação mais detalhada do projeto, preparada por Romain, o nosso Diretor de Investimentos. Este vídeo aborda a tese de investimento, os ativos selecionados e as projeções de rentabilidade:</p>
<p>{a(lk["vsl"], "Ver a apresentação completa de Romain")}</p>
<p>Para os investidores que pretendam aprofundar a análise, criámos também uma data room segura com toda a documentação de due diligence:</p>
<p>{a(lk["dataroom"], "Aceder à data room do LQPF22")}</p>
<p>Não hesite em partilhar as suas questões ou comentários após a visualização.</p>
{SIGNATURE_PT}
<p><em>P.S. Pode também reservar uma chamada de 20 minutos com a nossa equipa: {a(lk["rdv"], "Reservar um horário")}</em></p>""",
        },
        {
            "email_subject": "{FIRST_NAME}, última mensagem da nossa parte sobre o LQPF22",
            "order": 3,
            "wait_in_days": 3,
            "variant": False,
            "thread_reply": False,
            "email_body": f"""<p>Caro/a {"{FIRST_NAME}"},</p>
<p>Não quero ocupar mais o seu tempo, pelo que esta será a minha última mensagem sobre o <strong>LQPF22</strong>.</p>
<p>Realizámos recentemente um webinar de apresentação do portefólio. Se desejar vê-lo, o replay está disponível aqui:</p>
<p>{a(lk["webinar"], "Ver o replay do webinar do LQPF22")}</p>
<p>Para agendar uma chamada com um membro da nossa equipa:</p>
<p>{a(lk["rdv"], "Marcar uma reunião")}</p>
<p>Em resumo, eis os recursos disponíveis para si:</p>
<ul>
<li>{a(lk["teaser"], "Vídeo de apresentação")}</li>
<li>{a(lk["brochure"], "Brochure do LQPF22")}</li>
<li>{a(lk["vsl"], "Apresentação completa de Romain")}</li>
<li>{a(lk["dataroom"], "Data room (documentos de due diligence)")}</li>
</ul>
<p>Fico ao seu dispor caso deseje retomar o contacto noutra altura.</p>
{SIGNATURE_PT}""",
        },
    ]

# ─── MAIN ─────────────────────────────────────────────────────────────────────

campaigns = [
    (57, "LQPF22 - Séquence CRM (FR)",   "LQPF22 FR Sequence",  steps_fr(L["FR"])),
    (58, "LQPF22 - CRM Sequence (EN)",   "LQPF22 EN Sequence",  steps_en(L["EN"])),
    (59, "LQPF22 - Secuencia CRM (ES)",  "LQPF22 ES Sequence",  steps_es(L["ES"])),
    (60, "LQPF22 - Sequência CRM (PT)",  "LQPF22 PT Sequence",  steps_pt(L["PT"])),
]

results = []
for cid, camp_name, seq_title, steps in campaigns:
    sid = create_sequence(cid, seq_title, steps)
    results.append({"campaign": camp_name, "campaign_id": cid, "sequence_id": sid})

print("\n=== SUMMARY ===")
print(json.dumps(results, indent=2))
