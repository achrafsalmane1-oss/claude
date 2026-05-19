#!/usr/bin/env python3
import json
import requests

API_TOKEN = "27|lPHnLHDjn3QN9dQmSpNNHK8mvStTRbpKg6O5Iazeaeba52b8"
BASE_URL = "https://personal.ottoresults.com/api"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# ─────────────────────────────────────────────
# EMAIL BODIES (HTML)
# ─────────────────────────────────────────────

FR_EMAIL_1_BODY = """<p>Bonjour {FIRST_NAME},</p>
<p>Cela fait peut-être un moment que nous ne nous sommes pas écrit. Ou peut-être que vous suivez LandQuire depuis nos premiers projets — dans tous les cas, je voulais vous présenter personnellement notre dernière opportunité.</p>
<p>Nous venons d'ouvrir LQPF19 : 60 acres à Greenville, Texas. À 45 minutes de Dallas, dans une zone qui a gagné +21,5% de population depuis 2020.</p>
<p>Trois éléments que je souhaite mettre en avant dès maintenant :</p>
<p>- Une acquisition off-market à 20 300 $/acre, alors que les comparables locaux se négocient entre 27 000 et 33 000 $/acre.<br>
- 352 lots résidentiels prévus (mobile homes + RV), une typologie en forte demande dans la région.<br>
- Un IRR cible de 21 à 35% sur un horizon de 24 à 36 mois, en 100% equity.</p>
<p>Pour une vue d'ensemble en 2 minutes, voici un teaser que nous venons de publier :<br>
→ Voir le teaser vidéo</p>
<p>Ou si vous voulez tout de suite plonger dans les détails :<br>
→ Télécharger la brochure complète</p>
<p>Je reviens vers vous très bientôt avec la structure financière du deal et une présentation détaillée par mon associé Romain Daniellou.</p>
<p>À très vite,<br>
Thibaut Guéant<br>
Co-fondateur, LandQuire</p>
<p>P.S. — Si vous préférez en discuter directement avec notre équipe plutôt que de parcourir les documents, vous pouvez réserver un échange ici : Prendre rendez-vous</p>"""

FR_EMAIL_2_BODY = """<p>Bonjour {FIRST_NAME},</p>
<p>Suite à mon message sur LQPF19, je voulais entrer dans la structure du deal — c'est souvent là que les bonnes opportunités se distinguent des autres.</p>
<p>Les chiffres clés à retenir :</p>
<p>- Levée de 2,45 millions $ en 100% equity<br>
- Retour préférentiel de 10% par an pour les investisseurs<br>
- 55 à 70% du profit du projet distribués aux LPs (selon le montant investi)<br>
- Investissement minimum : 100 000 $<br>
- ROI total projeté du deal : 91%</p>
<p>Pour comprendre pourquoi nous structurons les choses ainsi — et pourquoi Greenville est selon nous le bon pari à ce moment précis — Romain Daniellou (mon associé et COO) a enregistré une présentation de 6 minutes qui passe en revue les fondamentaux du marché, l'acquisition et la stratégie de sortie.</p>
<p>→ Voir la présentation complète par Romain (6 min)</p>
<p>Et pour les investisseurs qui souhaitent faire leur propre due diligence, l'intégralité des documents du projet est dans une data room sécurisée :<br>
→ Accéder à la data room LQPF19</p>
<p>Dans mon prochain message, je vous donnerai accès au webinaire complet d'une heure que nous avons fait sur le projet.</p>
<p>À très vite,<br>
Thibaut Guéant<br>
Co-fondateur, LandQuire</p>
<p>P.S. — Vous préférez un échange direct avec notre équipe plutôt que d'attendre le prochain email ? Réservez un créneau ici : Prendre rendez-vous</p>"""

FR_EMAIL_3_BODY = """<p>Bonjour {FIRST_NAME},</p>
<p>Dernier message de cette série sur LQPF19.</p>
<p>À ce stade, deux options pour aller plus loin :</p>
<p><strong>1. Le webinaire complet d'une heure</strong><br>
Romain Daniellou a animé un webinaire détaillé qui couvre tout : la dynamique du marché texan, l'acquisition off-market à Greenville, la structure financière, le calendrier du projet, et les scénarios de sortie. C'est le format le plus complet que nous proposons sur ce deal.<br>
→ Voir le webinaire complet (1h)</p>
<p><strong>2. Un échange direct avec notre équipe</strong><br>
Si vous préférez une discussion personnalisée — pour clarifier des points spécifiques, comprendre comment ce projet s'intègre à votre stratégie patrimoniale, ou simplement poser vos questions — réservez un créneau directement dans notre agenda :<br>
→ Prendre rendez-vous avec l'équipe</p>
<p>LQPF19 est en phase active de levée de fonds. Les allocations se font dans l'ordre d'arrivée des engagements, alors n'attendez pas si le projet vous intéresse.</p>
<p>Quelle que soit votre décision, merci d'avoir lu jusqu'ici. Je reste à votre disposition pour toute question.</p>
<p>À très vite,<br>
Thibaut Guéant<br>
Co-fondateur, LandQuire</p>
<p>P.S. — Si vous avez raté les messages précédents :<br>
→ Teaser 2 min<br>
→ Brochure complète<br>
→ Présentation par Romain (6 min)<br>
→ Data Room</p>"""

# ─────────────────────────────────────────────

EN_EMAIL_1_BODY = """<p>Hi {FIRST_NAME},</p>
<p>It may have been a while since we last connected. Or perhaps you've been following LandQuire since our early projects — either way, I wanted to introduce you personally to our latest opportunity.</p>
<p>We've just opened LQPF19: 60 acres in Greenville, Texas. 45 minutes from Dallas, in an area that has gained +21.5% in population since 2020.</p>
<p>Three things I want to highlight upfront:</p>
<p>- An off-market acquisition at $20,300/acre, while local comparables trade between $27,000 and $33,000/acre.<br>
- 352 residential lots planned (manufactured homes + RV), a typology with strong local demand.<br>
- A target IRR of 21 to 35% over a 24-to-36-month horizon, in 100% equity.</p>
<p>For a 2-minute overview, here's a teaser we just released:<br>
→ Watch the video teaser</p>
<p>Or if you'd rather get straight to the details:<br>
→ Download the full brochure</p>
<p>I'll be back in touch shortly with the financial structure and a detailed presentation by my co-founder Romain Daniellou.</p>
<p>Talk soon,<br>
Thibaut Guéant<br>
Co-founder, LandQuire</p>
<p>P.S. — If you'd rather skip the materials and talk directly with our team, you can book a call here: Schedule a call</p>"""

EN_EMAIL_2_BODY = """<p>Hi {FIRST_NAME},</p>
<p>Following up on my message about LQPF19, I wanted to walk you through the structure of this deal — that's often where the real opportunities separate themselves from the rest.</p>
<p>The key numbers:</p>
<p>- $2.45 million raise in 100% equity<br>
- 10% annual preferred return for investors<br>
- 55 to 70% of project profit distributed to LPs (depending on commitment size)<br>
- Minimum investment: $100,000<br>
- Projected total deal ROI: 91%</p>
<p>To understand why we've structured it this way — and why we believe Greenville is the right bet at this specific moment — my co-founder and COO Romain Daniellou recorded a 6-minute presentation walking through the market fundamentals, the acquisition, and the exit strategy.</p>
<p>→ Watch Romain's full overview (6 min)</p>
<p>And for investors who want to run their own due diligence, all project documents are in a secure data room:<br>
→ Access the LQPF19 data room</p>
<p>In my next message, I'll share access to the full 1-hour webinar we recorded on this project.</p>
<p>Talk soon,<br>
Thibaut Guéant<br>
Co-founder, LandQuire</p>
<p>P.S. — Prefer to talk directly with our team rather than wait for the next email? Book a slot here: Schedule a call</p>"""

EN_EMAIL_3_BODY = """<p>Hi {FIRST_NAME},</p>
<p>Final note in this series on LQPF19.</p>
<p>At this point, two ways to go deeper:</p>
<p><strong>1. The full 1-hour webinar</strong><br>
Romain Daniellou hosted a detailed webinar covering everything: Texas market dynamics, the off-market acquisition in Greenville, the financial structure, the project timeline, and exit scenarios. It's the most complete format we offer on this deal.<br>
→ Watch the full webinar (1h)</p>
<p><strong>2. A direct conversation with our team</strong><br>
If you'd prefer a personalized discussion — to clarify specific points, understand how this project fits into your wealth strategy, or simply ask your questions — book a slot directly on our calendar:<br>
→ Book a call with the team</p>
<p>LQPF19 is in active fundraising. Allocations are processed in the order commitments are received, so don't wait if the project interests you.</p>
<p>Whatever your decision, thank you for reading this far. I remain at your disposal for any questions.</p>
<p>Talk soon,<br>
Thibaut Guéant<br>
Co-founder, LandQuire</p>
<p>P.S. — If you missed the earlier messages:<br>
→ 2-min teaser<br>
→ Full brochure<br>
→ 6-min overview with Romain<br>
→ Data Room</p>"""

# ─────────────────────────────────────────────

ES_EMAIL_1_BODY = """<p>Hola {FIRST_NAME},</p>
<p>Quizás haya pasado un tiempo desde nuestro último contacto. O quizás siga LandQuire desde nuestros primeros proyectos — en cualquier caso, quería presentarle personalmente nuestra última oportunidad.</p>
<p>Acabamos de abrir LQPF19: 60 acres en Greenville, Texas. A 45 minutos de Dallas, en una zona que ha crecido +21,5% en población desde 2020.</p>
<p>Tres elementos clave que quiero destacar desde ya:</p>
<p>- Una adquisición off-market a USD 20.300/acre, mientras los comparables locales se negocian entre USD 27.000 y USD 33.000/acre.<br>
- 352 lotes residenciales planificados (mobile homes + RV), una tipología con fuerte demanda local.<br>
- Un IRR objetivo de 21 a 35% en un horizonte de 24 a 36 meses, en 100% equity.</p>
<p>Para una visión general en 2 minutos, le dejo el teaser que acabamos de publicar:<br>
→ Ver el video teaser</p>
<p>O si prefiere ir directamente a los detalles:<br>
→ Descargar el folleto completo</p>
<p>Volveré pronto con la estructura financiera del deal y una presentación detallada de mi socio Romain Daniellou.</p>
<p>Hasta pronto,<br>
Thibaut Guéant<br>
Cofundador, LandQuire</p>
<p>P.D. — Si prefiere conversar directamente con nuestro equipo en lugar de revisar los documentos, puede agendar una llamada aquí: Agendar una reunión</p>"""

ES_EMAIL_2_BODY = """<p>Hola {FIRST_NAME},</p>
<p>Siguiendo mi mensaje sobre LQPF19, quería entrar en la estructura del deal — suele ser ahí donde las verdaderas oportunidades se diferencian del resto.</p>
<p>Las cifras clave:</p>
<p>- Levantamiento de USD 2,45 millones en 100% equity<br>
- Retorno preferencial del 10% anual para los inversionistas<br>
- 55 a 70% del lucro del proyecto distribuido a los LPs (según el monto comprometido)<br>
- Inversión mínima: USD 100.000<br>
- ROI total proyectado del deal: 91%</p>
<p>Para entender por qué estructuramos las cosas así — y por qué consideramos que Greenville es la apuesta correcta en este momento específico — Romain Daniellou (mi socio y COO) grabó una presentación de 6 minutos que recorre los fundamentales del mercado, la adquisición y la estrategia de salida.</p>
<p>→ Ver la presentación de Romain (6 min)</p>
<p>Y para los inversionistas que quieran hacer su propia due diligence, todos los documentos del proyecto están en un data room seguro:<br>
→ Acceder al data room LQPF19</p>
<p>En mi próximo mensaje le daré acceso al webinar completo de una hora que hicimos sobre el proyecto.</p>
<p>Hasta pronto,<br>
Thibaut Guéant<br>
Cofundador, LandQuire</p>
<p>P.D. — ¿Prefiere conversar directamente con nuestro equipo antes de esperar el próximo email? Reserve un horario aquí: Agendar una reunión</p>"""

ES_EMAIL_3_BODY = """<p>Hola {FIRST_NAME},</p>
<p>Último mensaje de esta serie sobre LQPF19.</p>
<p>En este punto, dos formas de profundizar:</p>
<p><strong>1. El webinar completo de 1 hora</strong><br>
Romain Daniellou condujo un webinar detallado que cubre todo: la dinámica del mercado texano, la adquisición off-market en Greenville, la estructura financiera, el cronograma del proyecto y los escenarios de salida. Es el formato más completo que ofrecemos sobre este deal.<br>
→ Ver el webinar completo (1h)</p>
<p><strong>2. Una conversación directa con nuestro equipo</strong><br>
Si prefiere una discusión personalizada — para aclarar puntos específicos, entender cómo este proyecto se integra a su estrategia patrimonial, o simplemente hacer sus preguntas — reserve un horario directamente en nuestra agenda:<br>
→ Agendar una reunión con el equipo</p>
<p>LQPF19 está en fase activa de levantamiento de capital. Las asignaciones se procesan en el orden en que se reciben los compromisos, así que si el proyecto le interesa, no espere.</p>
<p>Cualquiera que sea su decisión, gracias por leer hasta aquí. Quedo a su disposición para cualquier consulta.</p>
<p>Hasta pronto,<br>
Thibaut Guéant<br>
Cofundador, LandQuire</p>
<p>P.D. — Si se perdió los mensajes anteriores:<br>
→ Teaser 2 min<br>
→ Folleto completo<br>
→ Presentación de 6 min con Romain<br>
→ Data Room</p>"""

# ─────────────────────────────────────────────

PT_EMAIL_1_BODY = """<p>Olá {FIRST_NAME},</p>
<p>Pode ter passado um tempo desde nosso último contato. Ou talvez você acompanhe a LandQuire desde nossos primeiros projetos — de qualquer forma, queria apresentar pessoalmente nossa mais recente oportunidade.</p>
<p>Acabamos de abrir o LQPF19: 60 acres em Greenville, Texas. A 45 minutos de Dallas, em uma região que cresceu +21,5% em população desde 2020.</p>
<p>Três pontos que quero destacar de imediato:</p>
<p>- Uma aquisição off-market a USD 20.300/acre, enquanto os comparáveis locais são negociados entre USD 27.000 e USD 33.000/acre.<br>
- 352 lotes residenciais previstos (mobile homes + RV), uma tipologia com forte demanda local.<br>
- Um IRR alvo de 21 a 35% em um horizonte de 24 a 36 meses, em 100% equity.</p>
<p>Para uma visão geral em 2 minutos, deixo o teaser que acabamos de publicar:<br>
→ Assistir ao vídeo teaser</p>
<p>Ou se preferir ir direto aos detalhes:<br>
→ Baixar o folheto completo</p>
<p>Em breve volto a entrar em contato com a estrutura financeira do deal e uma apresentação detalhada do meu sócio Romain Daniellou.</p>
<p>Até breve,<br>
Thibaut Guéant<br>
Cofundador, LandQuire</p>
<p>P.S. — Se preferir conversar diretamente com nossa equipe em vez de revisar os documentos, você pode agendar uma chamada aqui: Agendar uma reunião</p>"""

PT_EMAIL_2_BODY = """<p>Olá {FIRST_NAME},</p>
<p>Dando sequência à minha mensagem sobre o LQPF19, queria entrar na estrutura do deal — é geralmente onde as boas oportunidades se diferenciam das demais.</p>
<p>Os números-chave:</p>
<p>- Captação de USD 2,45 milhões em 100% equity<br>
- Retorno preferencial de 10% ao ano para os investidores<br>
- 55 a 70% do lucro do projeto distribuído aos LPs (dependendo do valor comprometido)<br>
- Investimento mínimo: USD 100.000<br>
- ROI total projetado do deal: 91%</p>
<p>Para entender por que estruturamos o deal dessa forma — e por que consideramos Greenville a aposta certa neste momento específico — Romain Daniellou (meu sócio e COO) gravou uma apresentação de 6 minutos que percorre os fundamentos do mercado, a aquisição e a estratégia de saída.</p>
<p>→ Assistir à apresentação do Romain (6 min)</p>
<p>E para os investidores que queiram fazer sua própria due diligence, todos os documentos do projeto estão em uma data room segura:<br>
→ Acessar a data room do LQPF19</p>
<p>Na minha próxima mensagem darei acesso ao webinar completo de uma hora que fizemos sobre o projeto.</p>
<p>Até breve,<br>
Thibaut Guéant<br>
Cofundador, LandQuire</p>
<p>P.S. — Prefere conversar diretamente com nossa equipe antes de esperar o próximo email? Reserve um horário aqui: Agendar uma reunião</p>"""

PT_EMAIL_3_BODY = """<p>Olá {FIRST_NAME},</p>
<p>Última mensagem dessa série sobre o LQPF19.</p>
<p>Neste ponto, duas formas de aprofundar:</p>
<p><strong>1. O webinar completo de 1 hora</strong><br>
Romain Daniellou conduziu um webinar detalhado cobrindo tudo: a dinâmica do mercado texano, a aquisição off-market em Greenville, a estrutura financeira, o cronograma do projeto e os cenários de saída. É o formato mais completo que oferecemos sobre este deal.<br>
→ Assistir ao webinar completo (1h)</p>
<p><strong>2. Uma conversa direta com nossa equipe</strong><br>
Se preferir uma discussão personalizada — para esclarecer pontos específicos, entender como este projeto se integra à sua estratégia patrimonial, ou simplesmente fazer suas perguntas — reserve um horário diretamente em nossa agenda:<br>
→ Agendar uma reunião com a equipe</p>
<p>O LQPF19 está em fase ativa de captação. As alocações são processadas na ordem em que os compromissos são recebidos, então se o projeto lhe interessa, não espere.</p>
<p>Seja qual for sua decisão, obrigado por ler até aqui. Permaneço à sua disposição para qualquer dúvida.</p>
<p>Até breve,<br>
Thibaut Guéant<br>
Cofundador, LandQuire</p>
<p>P.S. — Se perdeu as mensagens anteriores:<br>
→ Teaser 2 min<br>
→ Folheto completo<br>
→ Apresentação de 6 min com Romain<br>
→ Data Room</p>"""

# ─────────────────────────────────────────────
# CAMPAIGN DEFINITIONS
# ─────────────────────────────────────────────

CAMPAIGNS = [
    {
        "name": "LQPF19 - Séquence CRM (FR)",
        "sequence_title": "LQPF19 FR Sequence",
        "steps": [
            {
                "email_subject": "Notre nouveau projet au Texas (LQPF19)",
                "email_body": FR_EMAIL_1_BODY,
                "order": 1,
                "wait_in_days": 1,
                "variant": False,
                "thread_reply": False,
            },
            {
                "email_subject": "LQPF19 : la structure du deal en détail",
                "email_body": FR_EMAIL_2_BODY,
                "order": 2,
                "wait_in_days": 3,
                "variant": False,
                "thread_reply": False,
            },
            {
                "email_subject": "LQPF19 : parlons-en directement",
                "email_body": FR_EMAIL_3_BODY,
                "order": 3,
                "wait_in_days": 3,
                "variant": False,
                "thread_reply": False,
            },
        ],
    },
    {
        "name": "LQPF19 - CRM Sequence (EN)",
        "sequence_title": "LQPF19 EN Sequence",
        "steps": [
            {
                "email_subject": "Our new Texas project (LQPF19)",
                "email_body": EN_EMAIL_1_BODY,
                "order": 1,
                "wait_in_days": 1,
                "variant": False,
                "thread_reply": False,
            },
            {
                "email_subject": "LQPF19: the deal structure in detail",
                "email_body": EN_EMAIL_2_BODY,
                "order": 2,
                "wait_in_days": 3,
                "variant": False,
                "thread_reply": False,
            },
            {
                "email_subject": "LQPF19: let's talk directly",
                "email_body": EN_EMAIL_3_BODY,
                "order": 3,
                "wait_in_days": 3,
                "variant": False,
                "thread_reply": False,
            },
        ],
    },
    {
        "name": "LQPF19 - Secuencia CRM (ES)",
        "sequence_title": "LQPF19 ES Sequence",
        "steps": [
            {
                "email_subject": "Nuestro nuevo proyecto en Texas (LQPF19)",
                "email_body": ES_EMAIL_1_BODY,
                "order": 1,
                "wait_in_days": 1,
                "variant": False,
                "thread_reply": False,
            },
            {
                "email_subject": "LQPF19: la estructura del deal en detalle",
                "email_body": ES_EMAIL_2_BODY,
                "order": 2,
                "wait_in_days": 3,
                "variant": False,
                "thread_reply": False,
            },
            {
                "email_subject": "LQPF19: hablemos directamente",
                "email_body": ES_EMAIL_3_BODY,
                "order": 3,
                "wait_in_days": 3,
                "variant": False,
                "thread_reply": False,
            },
        ],
    },
    {
        "name": "LQPF19 - Sequência CRM (PT)",
        "sequence_title": "LQPF19 PT Sequence",
        "steps": [
            {
                "email_subject": "Nosso novo projeto no Texas (LQPF19)",
                "email_body": PT_EMAIL_1_BODY,
                "order": 1,
                "wait_in_days": 1,
                "variant": False,
                "thread_reply": False,
            },
            {
                "email_subject": "LQPF19: a estrutura do deal em detalhes",
                "email_body": PT_EMAIL_2_BODY,
                "order": 2,
                "wait_in_days": 3,
                "variant": False,
                "thread_reply": False,
            },
            {
                "email_subject": "LQPF19: vamos conversar diretamente",
                "email_body": PT_EMAIL_3_BODY,
                "order": 3,
                "wait_in_days": 3,
                "variant": False,
                "thread_reply": False,
            },
        ],
    },
]


def create_campaign(name):
    resp = requests.post(
        f"{BASE_URL}/campaigns",
        headers=HEADERS,
        json={"name": name},
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    print(f"  Created campaign '{name}' → ID {data['id']}")
    return data["id"]


def create_sequence_steps(campaign_id, title, steps):
    payload = {"title": title, "sequence_steps": steps}
    resp = requests.post(
        f"{BASE_URL}/campaigns/v1.1/{campaign_id}/sequence-steps",
        headers=HEADERS,
        json=payload,
    )
    if resp.status_code != 200:
        print(f"  ERROR creating steps for campaign {campaign_id}: {resp.status_code}")
        print(resp.text[:500])
        return False
    print(f"  Created {len(steps)} sequence steps for campaign {campaign_id}")
    return True


def main():
    print("Creating LQPF19 CRM campaigns in Email Bison...\n")
    # Campaigns were already created (IDs 36-39); just push the sequence steps
    existing_ids = [36, 37, 38, 39]
    results = []
    for campaign, cid in zip(CAMPAIGNS, existing_ids):
        print(f"→ {campaign['name']} (ID {cid})")
        ok = create_sequence_steps(cid, campaign["sequence_title"], campaign["steps"])
        results.append({"name": campaign["name"], "id": cid, "ok": ok})
        print()

    print("─" * 60)
    print("Summary:")
    for r in results:
        status = "✓" if r["ok"] else "✗"
        print(f"  {status} [{r['id']}] {r['name']}")


if __name__ == "__main__":
    main()
