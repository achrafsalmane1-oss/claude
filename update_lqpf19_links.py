#!/usr/bin/env python3
import requests

API_TOKEN = "27|lPHnLHDjn3QN9dQmSpNNHK8mvStTRbpKg6O5Iazeaeba52b8"
BASE_URL = "https://personal.ottoresults.com/api"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# ─── LINKS ────────────────────────────────────────────────────────────────────

FR = {
    "teaser":   "https://youtu.be/Dg_XnveI4-M?si=-_P3AVjt8cAeZGWY",
    "vsl":      "https://youtu.be/gMtHv7NBXzI?si=ibTKf2id8k6Mv05C",
    "webinar":  "https://www.youtube.com/live/HrBvC2KDVP4?si=O-XVxiE7bKazaY32",
    "brochure": "https://canva.link/99aba5hiqj556uu",
    "dataroom": "[DATA ROOM LINK]",  # not found in document — add manually
    "rdv":      "https://api.leadconnectorhq.com/widget/bookings/landquire-rendezvous",
}
EN = {
    "teaser":   "https://youtu.be/tT95pEn-i8c?si=Kt9CKkCzh4lkRpdE",
    "vsl":      "https://youtu.be/oWiISTboN28?si=O3p9B7frUAw3zz8E",
    "webinar":  "https://www.youtube.com/live/F6ZI-kl1lss?si=tcq5G0fo5t0W0L6X",
    "brochure": "https://canva.link/mx7etsahmxgb6l6",
    "dataroom": "[DATA ROOM LINK]",
    "rdv":      "https://api.leadconnectorhq.com/widget/bookings/take-an-appointment-with-our-experts",
}
ES = {**EN, "rdv": "https://api.leadconnectorhq.com/widget/bookings/landquire-spa-team"}
PT = {**EN, "rdv": "https://api.leadconnectorhq.com/widget/bookings/landquire-portuguese"}


def a(url, text):
    if url.startswith("["):
        return text  # placeholder, no link yet
    return f'<a href="{url}">{text}</a>'


# ─── EMAIL BODIES ─────────────────────────────────────────────────────────────

def fr_email_1(L):
    return f"""<p>Bonjour {{FIRST_NAME}},</p>
<p>Cela fait peut-être un moment que nous ne nous sommes pas écrit. Ou peut-être que vous suivez LandQuire depuis nos premiers projets — dans tous les cas, je voulais vous présenter personnellement notre dernière opportunité.</p>
<p>Nous venons d'ouvrir <strong>LQPF19</strong> : 60 acres à Greenville, Texas. À 45 minutes de Dallas, dans une zone qui a gagné <strong>+21,5% de population depuis 2020</strong>.</p>
<p>Trois éléments que je souhaite mettre en avant dès maintenant :</p>
<ul>
<li><strong>Une acquisition off-market à 20 300 $/acre</strong>, alors que les comparables locaux se négocient entre 27 000 et 33 000 $/acre.</li>
<li><strong>352 lots résidentiels</strong> prévus (mobile homes + RV), une typologie en forte demande dans la région.</li>
<li><strong>Un IRR cible de 21 à 35%</strong> sur un horizon de 24 à 36 mois, en 100% equity.</li>
</ul>
<p>Pour une vue d'ensemble en 2 minutes, voici un teaser que nous venons de publier :<br>
→ {a(L['teaser'], 'Voir le teaser vidéo')}</p>
<p>Ou si vous voulez tout de suite plonger dans les détails :<br>
→ {a(L['brochure'], 'Télécharger la brochure complète')}</p>
<p>Je reviens vers vous très bientôt avec la structure financière du deal et une présentation détaillée par mon associé Romain Daniellou.</p>
<p>À très vite,<br>
<strong>Thibaut Guéant</strong> <em>Co-fondateur, LandQuire</em></p>
<p><strong>P.S.</strong> — Si vous préférez en discuter directement avec notre équipe plutôt que de parcourir les documents, vous pouvez réserver un échange ici : {a(L['rdv'], 'Prendre rendez-vous')}</p>"""

def fr_email_2(L):
    return f"""<p>Bonjour {{FIRST_NAME}},</p>
<p>Suite à mon message sur LQPF19, je voulais entrer dans la structure du deal — c'est souvent là que les bonnes opportunités se distinguent des autres.</p>
<p><strong>Les chiffres clés à retenir :</strong></p>
<ul>
<li>Levée de <strong>2,45 millions $</strong> en 100% equity</li>
<li><strong>Retour préférentiel de 10% par an</strong> pour les investisseurs</li>
<li><strong>55 à 70% du profit du projet</strong> distribués aux LPs (selon le montant investi)</li>
<li>Investissement minimum : <strong>100 000 $</strong></li>
<li>ROI total projeté du deal : <strong>91%</strong></li>
</ul>
<p>Pour comprendre pourquoi nous structurons les choses ainsi — et pourquoi Greenville est selon nous le bon pari à ce moment précis — Romain Daniellou (mon associé et COO) a enregistré une présentation de 6 minutes qui passe en revue les fondamentaux du marché, l'acquisition et la stratégie de sortie.</p>
<p>→ {a(L['vsl'], 'Voir la présentation complète par Romain (6 min)')}</p>
<p>Et pour les investisseurs qui souhaitent faire leur propre due diligence, l'intégralité des documents du projet est dans une data room sécurisée :<br>
→ {a(L['dataroom'], 'Accéder à la data room LQPF19')}</p>
<p>Dans mon prochain message, je vous donnerai accès au webinaire complet d'une heure que nous avons fait sur le projet.</p>
<p>À très vite,<br>
<strong>Thibaut Guéant</strong> <em>Co-fondateur, LandQuire</em></p>
<p><strong>P.S.</strong> — Vous préférez un échange direct avec notre équipe plutôt que d'attendre le prochain email ? Réservez un créneau ici : {a(L['rdv'], 'Prendre rendez-vous')}</p>"""

def fr_email_3(L):
    return f"""<p>Bonjour {{FIRST_NAME}},</p>
<p>Dernier message de cette série sur LQPF19.</p>
<p>À ce stade, deux options pour aller plus loin :</p>
<p><strong>1. Le webinaire complet d'une heure</strong><br>
Romain Daniellou a animé un webinaire détaillé qui couvre tout : la dynamique du marché texan, l'acquisition off-market à Greenville, la structure financière, le calendrier du projet, et les scénarios de sortie. C'est le format le plus complet que nous proposons sur ce deal.<br>
→ {a(L['webinar'], 'Voir le webinaire complet (1h)')}</p>
<p><strong>2. Un échange direct avec notre équipe</strong><br>
Si vous préférez une discussion personnalisée — pour clarifier des points spécifiques, comprendre comment ce projet s'intègre à votre stratégie patrimoniale, ou simplement poser vos questions — réservez un créneau directement dans notre agenda :<br>
→ {a(L['rdv'], "Prendre rendez-vous avec l'équipe")}</p>
<p>LQPF19 est en phase active de levée de fonds. Les allocations se font dans l'ordre d'arrivée des engagements, alors n'attendez pas si le projet vous intéresse.</p>
<p>Quelle que soit votre décision, merci d'avoir lu jusqu'ici. Je reste à votre disposition pour toute question.</p>
<p>À très vite,<br>
<strong>Thibaut Guéant</strong> <em>Co-fondateur, LandQuire</em></p>
<p><strong>P.S.</strong> — Si vous avez raté les messages précédents :<br>
→ {a(L['teaser'], 'Teaser 2 min')}<br>
→ {a(L['brochure'], 'Brochure complète')}<br>
→ {a(L['vsl'], 'Présentation par Romain (6 min)')}<br>
→ {a(L['dataroom'], 'Data Room')}</p>"""

def en_email_1(L):
    return f"""<p>Hi {{FIRST_NAME}},</p>
<p>It may have been a while since we last connected. Or perhaps you've been following LandQuire since our early projects — either way, I wanted to introduce you personally to our latest opportunity.</p>
<p>We've just opened <strong>LQPF19</strong>: 60 acres in Greenville, Texas. 45 minutes from Dallas, in an area that has gained <strong>+21.5% in population since 2020</strong>.</p>
<p>Three things I want to highlight upfront:</p>
<ul>
<li><strong>An off-market acquisition at $20,300/acre</strong>, while local comparables trade between $27,000 and $33,000/acre.</li>
<li><strong>352 residential lots</strong> planned (manufactured homes + RV), a typology with strong local demand.</li>
<li><strong>A target IRR of 21 to 35%</strong> over a 24-to-36-month horizon, in 100% equity.</li>
</ul>
<p>For a 2-minute overview, here's a teaser we just released:<br>
→ {a(L['teaser'], 'Watch the video teaser')}</p>
<p>Or if you'd rather get straight to the details:<br>
→ {a(L['brochure'], 'Download the full brochure')}</p>
<p>I'll be back in touch shortly with the financial structure and a detailed presentation by my co-founder Romain Daniellou.</p>
<p>Talk soon,<br>
<strong>Thibaut Guéant</strong> <em>Co-founder, LandQuire</em></p>
<p><strong>P.S.</strong> — If you'd rather skip the materials and talk directly with our team, you can book a call here: {a(L['rdv'], 'Schedule a call')}</p>"""

def en_email_2(L):
    return f"""<p>Hi {{FIRST_NAME}},</p>
<p>Following up on my message about LQPF19, I wanted to walk you through the structure of this deal — that's often where the real opportunities separate themselves from the rest.</p>
<p><strong>The key numbers:</strong></p>
<ul>
<li><strong>$2.45 million raise</strong> in 100% equity</li>
<li><strong>10% annual preferred return</strong> for investors</li>
<li><strong>55 to 70% of project profit</strong> distributed to LPs (depending on commitment size)</li>
<li>Minimum investment: <strong>$100,000</strong></li>
<li>Projected total deal ROI: <strong>91%</strong></li>
</ul>
<p>To understand why we've structured it this way — and why we believe Greenville is the right bet at this specific moment — my co-founder and COO Romain Daniellou recorded a 6-minute presentation walking through the market fundamentals, the acquisition, and the exit strategy.</p>
<p>→ {a(L['vsl'], "Watch Romain's full overview (6 min)")}</p>
<p>And for investors who want to run their own due diligence, all project documents are in a secure data room:<br>
→ {a(L['dataroom'], 'Access the LQPF19 data room')}</p>
<p>In my next message, I'll share access to the full 1-hour webinar we recorded on this project.</p>
<p>Talk soon,<br>
<strong>Thibaut Guéant</strong> <em>Co-founder, LandQuire</em></p>
<p><strong>P.S.</strong> — Prefer to talk directly with our team rather than wait for the next email? Book a slot here: {a(L['rdv'], 'Schedule a call')}</p>"""

def en_email_3(L):
    return f"""<p>Hi {{FIRST_NAME}},</p>
<p>Final note in this series on LQPF19.</p>
<p>At this point, two ways to go deeper:</p>
<p><strong>1. The full 1-hour webinar</strong><br>
Romain Daniellou hosted a detailed webinar covering everything: Texas market dynamics, the off-market acquisition in Greenville, the financial structure, the project timeline, and exit scenarios. It's the most complete format we offer on this deal.<br>
→ {a(L['webinar'], 'Watch the full webinar (1h)')}</p>
<p><strong>2. A direct conversation with our team</strong><br>
If you'd prefer a personalized discussion — to clarify specific points, understand how this project fits into your wealth strategy, or simply ask your questions — book a slot directly on our calendar:<br>
→ {a(L['rdv'], 'Book a call with the team')}</p>
<p>LQPF19 is in active fundraising. Allocations are processed in the order commitments are received, so don't wait if the project interests you.</p>
<p>Whatever your decision, thank you for reading this far. I remain at your disposal for any questions.</p>
<p>Talk soon,<br>
<strong>Thibaut Guéant</strong> <em>Co-founder, LandQuire</em></p>
<p><strong>P.S.</strong> — If you missed the earlier messages:<br>
→ {a(L['teaser'], '2-min teaser')}<br>
→ {a(L['brochure'], 'Full brochure')}<br>
→ {a(L['vsl'], '6-min overview with Romain')}<br>
→ {a(L['dataroom'], 'Data Room')}</p>"""

def es_email_1(L):
    return f"""<p>Hola {{FIRST_NAME}},</p>
<p>Quizás haya pasado un tiempo desde nuestro último contacto. O quizás siga LandQuire desde nuestros primeros proyectos — en cualquier caso, quería presentarle personalmente nuestra última oportunidad.</p>
<p>Acabamos de abrir <strong>LQPF19</strong>: 60 acres en Greenville, Texas. A 45 minutos de Dallas, en una zona que ha crecido <strong>+21,5% en población desde 2020</strong>.</p>
<p>Tres elementos clave que quiero destacar desde ya:</p>
<ul>
<li><strong>Una adquisición off-market a USD 20.300/acre</strong>, mientras los comparables locales se negocian entre USD 27.000 y USD 33.000/acre.</li>
<li><strong>352 lotes residenciales</strong> planificados (mobile homes + RV), una tipología con fuerte demanda local.</li>
<li><strong>Un IRR objetivo de 21 a 35%</strong> en un horizonte de 24 a 36 meses, en 100% equity.</li>
</ul>
<p>Para una visión general en 2 minutos, le dejo el teaser que acabamos de publicar:<br>
→ {a(L['teaser'], 'Ver el video teaser')}</p>
<p>O si prefiere ir directamente a los detalles:<br>
→ {a(L['brochure'], 'Descargar el folleto completo')}</p>
<p>Volveré pronto con la estructura financiera del deal y una presentación detallada de mi socio Romain Daniellou.</p>
<p>Hasta pronto,<br>
<strong>Thibaut Guéant</strong> <em>Cofundador, LandQuire</em></p>
<p><strong>P.D.</strong> — Si prefiere conversar directamente con nuestro equipo en lugar de revisar los documentos, puede agendar una llamada aquí: {a(L['rdv'], 'Agendar una reunión')}</p>"""

def es_email_2(L):
    return f"""<p>Hola {{FIRST_NAME}},</p>
<p>Siguiendo mi mensaje sobre LQPF19, quería entrar en la estructura del deal — suele ser ahí donde las verdaderas oportunidades se diferencian del resto.</p>
<p><strong>Las cifras clave:</strong></p>
<ul>
<li>Levantamiento de <strong>USD 2,45 millones</strong> en 100% equity</li>
<li><strong>Retorno preferencial del 10% anual</strong> para los inversionistas</li>
<li><strong>55 a 70% del lucro del proyecto</strong> distribuido a los LPs (según el monto comprometido)</li>
<li>Inversión mínima: <strong>USD 100.000</strong></li>
<li>ROI total proyectado del deal: <strong>91%</strong></li>
</ul>
<p>Para entender por qué estructuramos las cosas así — y por qué consideramos que Greenville es la apuesta correcta en este momento específico — Romain Daniellou (mi socio y COO) grabó una presentación de 6 minutos que recorre los fundamentales del mercado, la adquisición y la estrategia de salida.</p>
<p>→ {a(L['vsl'], 'Ver la presentación de Romain (6 min)')}</p>
<p>Y para los inversionistas que quieran hacer su propia due diligence, todos los documentos del proyecto están en un data room seguro:<br>
→ {a(L['dataroom'], 'Acceder al data room LQPF19')}</p>
<p>En mi próximo mensaje le daré acceso al webinar completo de una hora que hicimos sobre el proyecto.</p>
<p>Hasta pronto,<br>
<strong>Thibaut Guéant</strong> <em>Cofundador, LandQuire</em></p>
<p><strong>P.D.</strong> — ¿Prefiere conversar directamente con nuestro equipo antes de esperar el próximo email? Reserve un horario aquí: {a(L['rdv'], 'Agendar una reunión')}</p>"""

def es_email_3(L):
    return f"""<p>Hola {{FIRST_NAME}},</p>
<p>Último mensaje de esta serie sobre LQPF19.</p>
<p>En este punto, dos formas de profundizar:</p>
<p><strong>1. El webinar completo de 1 hora</strong><br>
Romain Daniellou condujo un webinar detallado que cubre todo: la dinámica del mercado texano, la adquisición off-market en Greenville, la estructura financiera, el cronograma del proyecto y los escenarios de salida. Es el formato más completo que ofrecemos sobre este deal.<br>
→ {a(L['webinar'], 'Ver el webinar completo (1h)')}</p>
<p><strong>2. Una conversación directa con nuestro equipo</strong><br>
Si prefiere una discusión personalizada — para aclarar puntos específicos, entender cómo este proyecto se integra a su estrategia patrimonial, o simplemente hacer sus preguntas — reserve un horario directamente en nuestra agenda:<br>
→ {a(L['rdv'], 'Agendar una reunión con el equipo')}</p>
<p>LQPF19 está en fase activa de levantamiento de capital. Las asignaciones se procesan en el orden en que se reciben los compromisos, así que si el proyecto le interesa, no espere.</p>
<p>Cualquiera que sea su decisión, gracias por leer hasta aquí. Quedo a su disposición para cualquier consulta.</p>
<p>Hasta pronto,<br>
<strong>Thibaut Guéant</strong> <em>Cofundador, LandQuire</em></p>
<p><strong>P.D.</strong> — Si se perdió los mensajes anteriores:<br>
→ {a(L['teaser'], 'Teaser 2 min')}<br>
→ {a(L['brochure'], 'Folleto completo')}<br>
→ {a(L['vsl'], 'Presentación de 6 min con Romain')}<br>
→ {a(L['dataroom'], 'Data Room')}</p>"""

def pt_email_1(L):
    return f"""<p>Olá {{FIRST_NAME}},</p>
<p>Pode ter passado um tempo desde nosso último contato. Ou talvez você acompanhe a LandQuire desde nossos primeiros projetos — de qualquer forma, queria apresentar pessoalmente nossa mais recente oportunidade.</p>
<p>Acabamos de abrir o <strong>LQPF19</strong>: 60 acres em Greenville, Texas. A 45 minutos de Dallas, em uma região que cresceu <strong>+21,5% em população desde 2020</strong>.</p>
<p>Três pontos que quero destacar de imediato:</p>
<ul>
<li><strong>Uma aquisição off-market a USD 20.300/acre</strong>, enquanto os comparáveis locais são negociados entre USD 27.000 e USD 33.000/acre.</li>
<li><strong>352 lotes residenciais</strong> previstos (mobile homes + RV), uma tipologia com forte demanda local.</li>
<li><strong>Um IRR alvo de 21 a 35%</strong> em um horizonte de 24 a 36 meses, em 100% equity.</li>
</ul>
<p>Para uma visão geral em 2 minutos, deixo o teaser que acabamos de publicar:<br>
→ {a(L['teaser'], 'Assistir ao vídeo teaser')}</p>
<p>Ou se preferir ir direto aos detalhes:<br>
→ {a(L['brochure'], 'Baixar o folheto completo')}</p>
<p>Em breve volto a entrar em contato com a estrutura financeira do deal e uma apresentação detalhada do meu sócio Romain Daniellou.</p>
<p>Até breve,<br>
<strong>Thibaut Guéant</strong> <em>Cofundador, LandQuire</em></p>
<p><strong>P.S.</strong> — Se preferir conversar diretamente com nossa equipe em vez de revisar os documentos, você pode agendar uma chamada aqui: {a(L['rdv'], 'Agendar uma reunião')}</p>"""

def pt_email_2(L):
    return f"""<p>Olá {{FIRST_NAME}},</p>
<p>Dando sequência à minha mensagem sobre o LQPF19, queria entrar na estrutura do deal — é geralmente onde as boas oportunidades se diferenciam das demais.</p>
<p><strong>Os números-chave:</strong></p>
<ul>
<li>Captação de <strong>USD 2,45 milhões</strong> em 100% equity</li>
<li><strong>Retorno preferencial de 10% ao ano</strong> para os investidores</li>
<li><strong>55 a 70% do lucro do projeto</strong> distribuído aos LPs (dependendo do valor comprometido)</li>
<li>Investimento mínimo: <strong>USD 100.000</strong></li>
<li>ROI total projetado do deal: <strong>91%</strong></li>
</ul>
<p>Para entender por que estruturamos o deal dessa forma — e por que consideramos Greenville a aposta certa neste momento específico — Romain Daniellou (meu sócio e COO) gravou uma apresentação de 6 minutos que percorre os fundamentos do mercado, a aquisição e a estratégia de saída.</p>
<p>→ {a(L['vsl'], 'Assistir à apresentação do Romain (6 min)')}</p>
<p>E para os investidores que queiram fazer sua própria due diligence, todos os documentos do projeto estão em uma data room segura:<br>
→ {a(L['dataroom'], 'Acessar a data room do LQPF19')}</p>
<p>Na minha próxima mensagem darei acesso ao webinar completo de uma hora que fizemos sobre o projeto.</p>
<p>Até breve,<br>
<strong>Thibaut Guéant</strong> <em>Cofundador, LandQuire</em></p>
<p><strong>P.S.</strong> — Prefere conversar diretamente com nossa equipe antes de esperar o próximo email? Reserve um horário aqui: {a(L['rdv'], 'Agendar uma reunião')}</p>"""

def pt_email_3(L):
    return f"""<p>Olá {{FIRST_NAME}},</p>
<p>Última mensagem dessa série sobre o LQPF19.</p>
<p>Neste ponto, duas formas de aprofundar:</p>
<p><strong>1. O webinar completo de 1 hora</strong><br>
Romain Daniellou conduziu um webinar detalhado cobrindo tudo: a dinâmica do mercado texano, a aquisição off-market em Greenville, a estrutura financeira, o cronograma do projeto e os cenários de saída. É o formato mais completo que oferecemos sobre este deal.<br>
→ {a(L['webinar'], 'Assistir ao webinar completo (1h)')}</p>
<p><strong>2. Uma conversa direta com nossa equipe</strong><br>
Se preferir uma discussão personalizada — para esclarecer pontos específicos, entender como este projeto se integra à sua estratégia patrimonial, ou simplesmente fazer suas perguntas — reserve um horário diretamente em nossa agenda:<br>
→ {a(L['rdv'], 'Agendar uma reunião com a equipe')}</p>
<p>O LQPF19 está em fase ativa de captação. As alocações são processadas na ordem em que os compromissos são recebidos, então se o projeto lhe interessa, não espere.</p>
<p>Seja qual for sua decisão, obrigado por ler até aqui. Permaneço à sua disposição para qualquer dúvida.</p>
<p>Até breve,<br>
<strong>Thibaut Guéant</strong> <em>Cofundador, LandQuire</em></p>
<p><strong>P.S.</strong> — Se perdeu as mensagens anteriores:<br>
→ {a(L['teaser'], 'Teaser 2 min')}<br>
→ {a(L['brochure'], 'Folheto completo')}<br>
→ {a(L['vsl'], 'Apresentação de 6 min com Romain')}<br>
→ {a(L['dataroom'], 'Data Room')}</p>"""


# ─── SEQUENCES TO UPDATE ─────────────────────────────────────────────────────
# sequence_id → (title, [step_id, subject, body_fn, links], ...)

SEQUENCES = [
    (33, "LQPF19 FR Sequence", [
        (374, "Notre nouveau projet au Texas (LQPF19)",    fr_email_1, FR),
        (375, "LQPF19 : la structure du deal en détail",   fr_email_2, FR),
        (376, "LQPF19 : parlons-en directement",           fr_email_3, FR),
    ]),
    (34, "LQPF19 EN Sequence", [
        (377, "Our new Texas project (LQPF19)",            en_email_1, EN),
        (378, "LQPF19: the deal structure in detail",      en_email_2, EN),
        (379, "LQPF19: let's talk directly",               en_email_3, EN),
    ]),
    (35, "LQPF19 ES Sequence", [
        (380, "Nuestro nuevo proyecto en Texas (LQPF19)",  es_email_1, ES),
        (381, "LQPF19: la estructura del deal en detalle", es_email_2, ES),
        (382, "LQPF19: hablemos directamente",             es_email_3, ES),
    ]),
    (36, "LQPF19 PT Sequence", [
        (383, "Nosso novo projeto no Texas (LQPF19)",      pt_email_1, PT),
        (384, "LQPF19: a estrutura do deal em detalhes",   pt_email_2, PT),
        (385, "LQPF19: vamos conversar diretamente",       pt_email_3, PT),
    ]),
]


def update_sequence(seq_id, title, steps):
    payload = {
        "title": title,
        "sequence_steps": [
            {
                "id": step_id,
                "email_subject": subject,
                "order": i + 1,
                "email_body": body_fn(links),
                "wait_in_days": 1 if i == 0 else 3,
                "variant": False,
                "thread_reply": False,
            }
            for i, (step_id, subject, body_fn, links) in enumerate(steps)
        ],
    }
    resp = requests.put(
        f"{BASE_URL}/campaigns/v1.1/sequence-steps/{seq_id}",
        headers=HEADERS,
        json=payload,
    )
    if resp.status_code in (200, 201):
        print(f"  ✓ Sequence {seq_id} updated")
        return True
    else:
        print(f"  ✗ Sequence {seq_id} failed [{resp.status_code}]: {resp.text[:200]}")
        return False


def main():
    print("Updating LQPF19 sequences with real links...\n")
    for seq_id, title, steps in SEQUENCES:
        print(f"→ {title}")
        update_sequence(seq_id, title, steps)
        print()
    print("Done. Note: Data Room links are still placeholders — add the URL manually in Bison.")


if __name__ == "__main__":
    main()
