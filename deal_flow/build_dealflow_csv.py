# -*- coding: utf-8 -*-
import json, re, csv, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import strip_quoted, extract_mandate, valid_sector
from classify import POSITIVE, NEGATIVE, sig, firm_type, NEG_KW

reps, seen = [], set()
for f in ['./replies.jsonl','./replies_buyside.jsonl']:
    if not os.path.exists(f): continue
    for line in open(f):
        try: r=json.loads(line)
        except: continue
        if r['id'] in seen: continue
        seen.add(r['id']); reps.append(r)
print("unique replies analysed:", len(reps), file=sys.stderr)

def cv(lead,name):
    for v in (lead.get('custom_variables') or []):
        if (v.get('name') or '').lower()==name: return v.get('value')
    return None

cands={}
for r in reps:
    ld=r.get('lead') or {}
    email=(ld.get('email') or '').strip().lower()
    if not email: continue
    raw = r.get('text') or ''
    frm = (r.get('from_email_address') or '').strip().lower()
    # Only text the PROSPECT actually typed counts as evidence.
    prospect_authored = (frm == email)
    body = strip_quoted(raw) if prospect_authored else ''
    ftype,fscore = firm_type(ld.get('company'), email, ld.get('title'), raw)
    if not ftype: continue
    blob=f"{ld.get('company') or ''} {email.split('@')[-1]}".lower()
    if re.search(NEG_KW, blob) and fscore < 3: continue
    bounced = (r.get('folder')=='Bounced')
    auto = bool(r.get('automated_reply')) or bounced

    c=cands.setdefault(email,{'first':ld.get('first_name') or '','last':ld.get('last_name') or '',
        'title':ld.get('title') or '','company':ld.get('company') or '','email':email,
        'domain':email.split('@')[-1],'linkedin':cv(ld,'linkedin') or '',
        'sector':cv(ld,'sector_list') or '','website':cv(ld,'website') or '',
        'firm_type':ftype,'cids':set(),'cnames':set(),'interested':False,
        'pos':0,'neg':0,'texts':[],'human':False,'dates':[],'bounced':False,'status':ld.get('status') or ''})
    c['cids'].add(r.get('campaign_id')); c['cnames'].add(r.get('campaign_name') or '')
    c['interested'] = c['interested'] or bool(r.get('interested'))
    c['bounced'] = c['bounced'] or bounced
    if prospect_authored and not auto and body:
        c['human']=True; c['texts'].append(body)
        c['pos']+=sig(body,POSITIVE); c['neg']+=sig(body,NEGATIVE)
    if r.get('date_received'): c['dates'].append(r['date_received'])

out=[]
for em,c in cands.items():
    genuine = c['human'] and c['pos']>0 and c['pos']>c['neg']
    if not (c['interested'] or genuine): continue
    if c['neg']>=2 and not c['interested']: continue
    body=' '.join(c['texts'])[:4000]
    mandate,msrc = extract_mandate(body, c['sector'], c['cids'], c['firm_type'])
    # Otto's `company` field is whatever the prospecting list said -- on sell-side
    # campaigns that is the TARGET business, not the replier's own firm. When the
    # company looks like an operating trade business but the email domain is an
    # investment firm, the domain is the truth.
    _dom_core = c['domain'].rsplit('.',1)[0].replace('-',' ')
    _company_is_target = bool(re.search(NEG_KW, (c['company'] or '').lower()))
    _domain_is_firm = bool(re.search(r'(capital|equity|partners|invest|ventures?|holdings?|fund)', c['domain'].lower()))
    firm_note = ''
    if _domain_is_firm and (_company_is_target or not c['company']):
        firm_note = f"company field is the outreach target; actual firm ~ {_dom_core}"

    conf = 'High' if (c['interested'] and c['human'] and c['pos']>0) else ('Medium' if c['interested'] or genuine else 'Low')
    out.append({'full_name':f"{c['first']} {c['last']}".strip(),'first_name':c['first'],'last_name':c['last'],
      'title':c['title'],'firm':c['company'],'firm_type':c['firm_type'],'firm_note':firm_note,
      'linkedin':c['linkedin'],'email':em,'domain':c['domain'],'website':c['website'],
      'mandate':mandate,'mandate_source':msrc,
      'confidence':conf,'otto_interested_flag':'yes' if c['interested'] else 'no',
      'replied_in_person':'yes' if c['human'] else 'no',
      'pos_signals':c['pos'],'neg_signals':c['neg'],
      'campaigns':'; '.join(sorted(x for x in c['cnames'] if x)),
      'last_reply':max(c['dates']) if c['dates'] else '',
      'reply_excerpt':body[:500]})

order={'High':0,'Medium':1,'Low':2}
out.sort(key=lambda r:(order[r['confidence']], -r['pos_signals'], r['firm']))
COLS=['full_name','first_name','last_name','title','firm','firm_note','firm_type','linkedin','email','domain','website',
      'mandate','mandate_source','confidence','otto_interested_flag','replied_in_person',
      'pos_signals','neg_signals','campaigns','last_reply','reply_excerpt']
with open('./pe_vc_ma_dealflow.csv','w',newline='',encoding='utf-8') as fh:
    w=csv.DictWriter(fh,fieldnames=COLS); w.writeheader()
    for r in out: w.writerow(r)
json.dump(out,open('./final.json','w'),indent=1)
from collections import Counter
print("ROWS:",len(out), file=sys.stderr)
print("by type:",Counter(r['firm_type'] for r in out), file=sys.stderr)
print("by confidence:",Counter(r['confidence'] for r in out), file=sys.stderr)
print("with linkedin:",sum(1 for r in out if r['linkedin']), file=sys.stderr)
print("mandate stated in reply:",sum(1 for r in out if r['mandate_source']=='stated in reply'), file=sys.stderr)
