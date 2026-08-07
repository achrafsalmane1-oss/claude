# -*- coding: utf-8 -*-
"""Retroactively stop automation for every Interested lead handed to an agent.
For each assigned positive, look it up in BOTH workspaces, and for any campaign
where its status is still ACTIVE (not already replied/completed/etc.), set the
lead status to COMPLETED so no further automated sequence email is sent."""
import json, os, urllib.request, urllib.error, time
KEY=os.environ.get('PLUSVIBE_API_KEY',''); BASE='https://api.plusvibe.ai/api/v1'
WS={'B2B':'6a3179f64517eb5ecd7c1642','B2C':'6a4645cc305ead1e2243e94f'}
if not KEY:
    raise SystemExit('Set PLUSVIBE_API_KEY in the environment.')
TERMINAL={'REPLIED','COMPLETED','UNSUBSCRIBED','BOUNCED','SKIPPED'}   # already stopped
def g(p):
    for a in range(5):
        try:
            r=urllib.request.Request(BASE+p,headers={'x-api-key':KEY,'Accept':'application/json','User-Agent':'curl/8.5.0'})
            return json.loads(urllib.request.urlopen(r,timeout=40).read())
        except urllib.error.HTTPError as e:
            if e.code in(429,500,502,503): time.sleep(2**a); continue
            return {'ERR':e.code}
        except Exception:
            if a==4: return {}
            time.sleep(2)
def post(path,body):
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode(),method='POST',
        headers={'x-api-key':KEY,'Content-Type':'application/json','Accept':'application/json','User-Agent':'curl/8.5.0'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r: return r.getcode(),r.read().decode()[:120]
    except urllib.error.HTTPError as e: return e.code,e.read().decode()[:120]

# Assigned/handed-off leads: from a CSV arg (email column), else state.json.
import sys, csv
emails=set()
if len(sys.argv)>1:
    for row in csv.DictReader(open(sys.argv[1])):
        e=(row.get('email') or row.get('Email') or '').strip().lower()
        if e: emails.add(e)
else:
    sp=os.path.join(os.path.dirname(os.path.abspath(__file__)),'state.json')
    try: emails|=set(e.lower() for e in json.load(open(sp)).get('processed',[]))
    except Exception: pass
emails=sorted(e for e in emails if '@' in e)
print('assigned leads to check:',len(emails))
stopped=[]; already=0; active_found=0; checked=0
for em in emails:
    checked+=1
    for seg,wid in WS.items():
        d=g(f'/lead/workspace-leads?workspace_id={wid}&email={em}')
        recs=d if isinstance(d,list) else (d.get('data') or [])
        for r in recs:
            st=(r.get('status') or '').upper(); cid=r.get('campaign_id')
            if not cid: continue
            if st in TERMINAL: already+=1; continue
            active_found+=1
            code,resp=post('/lead/update/status',{'workspace_id':wid,'campaign_id':cid,'email':em,'new_status':'COMPLETED'})
            stopped.append((em,seg,r.get('camp_name'),st,code))
            time.sleep(0.25)
    if checked%25==0: print(f'{checked}/{len(emails)} checked, active_stopped={len(stopped)}',flush=True)
    time.sleep(0.1)
ok=sum(1 for x in stopped if x[4] in (200,201))
print('DONE. leads checked:',len(emails))
print('campaign-records already terminal (no action):',already)
print('still-ACTIVE campaign-records found & stopped:',active_found,'| API-confirmed stop:',ok)
for x in stopped[:40]: print('  STOP',x)
json.dump({'stopped':stopped,'already':already,'active_found':active_found},open('stop_automation_result.json','w'),ensure_ascii=False)
