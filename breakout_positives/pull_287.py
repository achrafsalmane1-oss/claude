import os, json, time
# token comes from the BISON_TOKEN env var - never commit it
import bison
out=open("c287.jsonl","w"); n=0; t0=time.time()
for r in bison.paginate("/replies", folder="inbox", status="interested", campaign_id=287):
    slim={k:r.get(k) for k in ("id","subject","date_received","campaign_id","lead_id","from_email_address","from_name","automated_reply")}
    slim["text_body"]=(r.get("text_body") or "")[:4000]
    slim["lead"]=r.get("lead"); out.write(json.dumps(slim)+"\n"); n+=1
    if n%200==0: out.flush(); print(n, int(time.time()-t0), flush=True)
out.close(); print("DONE",n,int(time.time()-t0), flush=True)
