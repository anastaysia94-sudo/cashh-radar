from __future__ import annotations

import csv, hashlib, html, json, re, textwrap, urllib.parse, urllib.request
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data" / "v5-v6-research"
OUT = ROOT / "dist-v5-v6"
PAYPAL = "https://www.paypal.com/invoice/p/#7T6DC9A6WFH3XXCT"
CHECK_DATE = "2026-09-16"

FREE = {"gmail.com","yahoo.com","outlook.com","hotmail.com","icloud.com","aol.com","sbcglobal.net"}
GENERIC = {"info","hello","office","sales","contact","support","admin","estimating","bids","booking","events","team","frontdesk","online","service","services","customerservice"}
HIGH = ("hvac","plumb","electric","roof","restoration","garage","concrete","paving","construction","engineering","dental","auto","collision","remodel","solar","pool","security","moving","landscap","tree","pest")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def domain(email: str) -> str:
    return email.lower().split("@")[-1] if "@" in email else ""


def valid_email(e: str) -> bool:
    e = e.strip().strip("<>[](){}'\".,;:").lower()
    return bool(re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}", e)) and not any(x in e for x in ("example.","noreply","no-reply","donotreply"))


def fetch(url: str) -> tuple[str,str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 CashhRadarResearch/1.0"})
        with urllib.request.urlopen(req, timeout=18) as r:
            ctype = r.headers.get("content-type", "")
            if "text" not in ctype and "html" not in ctype:
                return "", url
            return r.read(1_800_000).decode("utf-8", "ignore"), r.geturl()
    except Exception:
        return "", url


def discover_email(url: str) -> tuple[str,str]:
    html_text, final = fetch(url)
    if not html_text:
        return "", url
    parsed = urlparse(final)
    site_domain = parsed.netloc.lower().removeprefix("www.")
    pages = [(final, html_text)]
    soup = BeautifulSoup(html_text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(final, a["href"])
        txt = (a.get_text(" ", strip=True) + " " + href).lower()
        if urlparse(href).netloc.lower().removeprefix("www.") == site_domain and any(k in txt for k in ("contact","about","team","staff","quote","estimate","booking")):
            links.append(href)
    for href in list(dict.fromkeys(links))[:6]:
        h, u = fetch(href)
        if h:
            pages.append((u,h))
    candidates = []
    for page_url, body in pages:
        ps = BeautifulSoup(body, "html.parser")
        for a in ps.select('a[href^="mailto:"]'):
            e = urllib.parse.unquote(a.get("href","")[7:].split("?")[0]).strip()
            if valid_email(e): candidates.append((e.lower(), page_url, 100))
        for e in re.findall(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", body):
            if valid_email(e): candidates.append((e.lower(), page_url, 50))
    scored=[]
    for e,u,s in candidates:
        d=domain(e); local=e.split("@")[0]
        if d==site_domain or d.endswith("."+site_domain) or site_domain.endswith("."+d): s+=35
        if d not in FREE: s+=12
        if local in GENERIC: s+=6
        scored.append((s,e,u))
    if not scored:
        return "", final
    scored.sort(reverse=True)
    return scored[0][1], scored[0][2]


def parse_seed() -> list[dict]:
    text=(RESEARCH/"seed-2026-09-13.md").read_text(encoding="utf-8")
    rows=[]
    pat=re.compile(r"^\|\s*\d+\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*`([^`]+)`\s*\|\s*(https?://[^| ]+)\s*\|", re.M)
    for business,city,industry,email,source in pat.findall(text):
        rows.append({"Business":business.strip(),"Email":email.strip(),"Website":"","Phone":"","SourceURL":source.strip(),"City":city.strip(),"Industry":industry.strip(),"Observation":f"The current contractor source lists {business.strip()} in {city.strip()} for {industry.strip()}; a concise capability and project-readiness content set can help prospective buyers understand what the business handles before an inquiry.","CheckDate":"2026-09-13","EvidenceNote":"Accepted in the canonical seed gate from the current 2026 contractor source; public business email retained exactly as published."})
    return rows


def parse_roster(path: Path, batch: int) -> list[dict]:
    text=path.read_text(encoding="utf-8")
    start=text.split("## Accepted research roster",1)[-1]
    start=start.split("## ",1)[0]
    rows=[]
    for line in start.splitlines():
        m=re.match(r"\s*\d+\.\s+(?:\*\*)?(.*?)(?:\*\*)?\s+—\s+(.*?)\s+—\s+(.*?)\s+—\s+(https?://\S+)", line)
        if not m: continue
        b,city,industry,url=[x.strip().strip("*") for x in m.groups()]
        email, evidence_url = discover_email(url)
        if not email:
            raise RuntimeError(f"Batch {batch}: no public email recovered for {b} from {url}")
        rows.append({"Business":b,"Email":email,"Website":url,"Phone":"","SourceURL":evidence_url,"City":city,"Industry":industry,"Observation":f"The current business site presents {industry} for {city}; a service-selection, FAQ and customer-next-step content set can make the offer easier to understand before inquiry.","CheckDate":"2026-09-16","EvidenceNote":f"Batch {batch} identity came from the accepted staging roster; email was re-read from the current owned/public business site during final build."})
    return rows


def load_records() -> list[dict]:
    rows=parse_seed()
    for path in sorted(RESEARCH.glob("batch*-accepted.csv")):
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows.append({k:(v or "").strip() for k,v in r.items() if not k.startswith("_")})
    for batch in (10,11):
        rows.extend(parse_roster(RESEARCH/f"batch{batch}-2026-09-13.md", batch))
    # canonical dedupe by business and email. Any collision is a hard failure, not silently dropped.
    nseen, eseen={},{}
    for r in rows:
        nk=norm(r["Business"]); ek=r["Email"].lower()
        if nk in nseen: raise RuntimeError(f"Duplicate business: {r['Business']} / {nseen[nk]}")
        if ek in eseen: raise RuntimeError(f"Duplicate email: {r['Email']} / {eseen[ek]}")
        if not valid_email(ek): raise RuntimeError(f"Invalid/missing email: {r['Business']} {ek}")
        if not r.get("SourceURL"): raise RuntimeError(f"Missing source: {r['Business']}")
        nseen[nk]=r["Business"]; eseen[ek]=r["Business"]
    if len(rows)!=400: raise RuntimeError(f"Expected exactly 400 accepted records, got {len(rows)}")
    return rows


def score(r: dict) -> int:
    s=55; e=r["Email"].lower(); ind=(r.get("Industry") or "").lower(); obs=(r.get("Observation") or "").lower(); d=domain(e); local=e.split("@")[0]
    if d not in FREE: s+=10
    if local not in GENERIC: s+=6
    if any(k in ind for k in HIGH): s+=10
    if any(k in obs for k in ("free","same-day","24/7","quote","estimate","booking","consult","appointment","trial","event","project")): s+=7
    if any(k in (r.get("City") or "").lower() for k in ("san jose","santa clara","sunnyvale","campbell","los gatos","cupertino","milpitas","morgan hill","gilroy","mountain view","palo alto")): s+=5
    return min(99,s)


def service_focus(r:dict)->str:
    x=(r.get("Industry") or "local services").strip()
    return x.lower()


def angle(r:dict)->str:
    ind=service_focus(r)
    if any(k in ind for k in ("restaurant","catering","coffee","food","bakery")): return "menu/service highlights, event or ordering guidance, and local customer CTAs"
    if any(k in ind for k in ("hvac","plumb","electric","roof","restoration","garage","pest","concrete","paving","construction","engineering")): return "service explainers, project/repair education, and estimate or consultation CTAs"
    if any(k in ind for k in ("beauty","wellness","dental","fitness","martial","dance","music","tutor")): return "program/service selection, first-visit guidance, and booking CTAs"
    if any(k in ind for k in ("auto","collision","detail")): return "service comparisons, before/after project content, and estimate or booking CTAs"
    if any(k in ind for k in ("organizing","cleaning","moving","landscap","tree","furniture","interior")): return "before/after process content, service-selection guidance, and quote CTAs"
    return "service highlights, FAQ-style education, and a clear next-step CTA"


def why_fit(r:dict)->str:
    obs=(r.get("Observation") or "").strip().rstrip(".")
    return f"{obs}. The $100 package is useful here because it turns those existing services into clear, reusable customer-facing content without requiring the business to write or design the pieces itself."


def email_v5(r:dict)->tuple[str,str]:
    b=r["Business"]; sf=service_focus(r); a=angle(r); obs=(r.get("Observation") or "").strip().rstrip(".")
    subject=f"Private {sf} sample for {b}"
    body=f"""Hi {b} team,\n\nI was looking at your business and noticed {obs[0].lower()+obs[1:] if obs else sf}. I made the attached private preview around that part of the business so you can judge the direction before spending anything.\n\nFor $100 one time, I can turn it into a complete done-for-you content pack. In plain English, you get:\n\n• 10 ready-to-post Google / Facebook / social posts\n• custom graphics made for {b}\n• customer follow-up messages you can copy and paste\n• review and customer-message reply templates\n• stronger calls-to-action\n• content built around your actual services\n• everything organized and ready to use\n\nNo subscription and no contract. I’d build the first set around {a}.\n\nWhy it may be worth considering: you already have services worth explaining and showing; this package turns those existing strengths into content customers can actually see and understand.\n\nIf you like the sample, reply YES and I’ll finish the complete set.\n\nIf you already know you want it, the $100 PayPal invoice is here:\n{PAYPAL}\n\nIf you’d rather ask something first, just reply. If it isn’t useful, reply “no thanks” and I won’t keep following up.\n\nThanks,\nAnastaysia"""
    return subject,body


def email_v6(r:dict)->tuple[str,str]:
    b=r["Business"]; sf=service_focus(r); a=angle(r); obs=(r.get("Observation") or "").strip().rstrip(".")
    subject=f"Made this {sf} preview for {b}"
    body=f"""Hi {b} team,\n\nI came across your business and noticed {obs[0].lower()+obs[1:] if obs else sf}. I made the attached private preview specifically around that part of the business.\n\nIf you like the direction, the full package is $100 one time. It includes 10 ready-to-post business posts, custom graphics, customer follow-up messages, review/customer-message replies, stronger calls-to-action, and content organized around your real services. Everything is delivered ready to use; there’s no subscription or contract.\n\nFor {b}, I’d start with {a}.\n\nYou can choose whatever is easiest:\n1. Reply YES and I’ll finish the $100 package.\n2. Ask me anything first.\n3. If you already know you want it, you can use the PayPal invoice here: {PAYPAL}\n\nIf it isn’t useful, that’s completely fine — reply “no thanks” and I won’t follow up again.\n\nThanks,\nAnastaysia"""
    return subject,body


def reply_fields(r:dict)->dict:
    b=r["Business"]; sf=service_focus(r); a=angle(r)
    return {
      "InterestedReply":f"Absolutely — I can finish the full {sf} content package for {b}. It’s $100 one time, with no subscription or contract. PayPal invoice: {PAYPAL}\n\nOnce payment is confirmed, I’ll build the complete set around {a} unless you want me to prioritize something else.\n\n– Anastaysia",
      "PriceReply":"It’s $100 total, one time — not per post and not monthly. You keep the 10 posts, custom graphics, customer follow-up messages, review/message replies and CTA copy.",
      "ProofReply":f"The attached sample was made specifically for {b} around {sf}. That is the direction I’d use for the finished set, and I’ll keep every piece tied to the actual services rather than generic filler.",
      "MoreInfoReply":f"I’d make the finished set around {a}. You receive the words + graphics ready to copy, post or reuse, so you do not have to design or write them yourself.",
      "LaterReply":"No problem. I’ll leave the sample with you. If timing changes, reply here and I can pick it back up. I won’t keep chasing you.",
      "Followup":f"Hi {b} team — one quick follow-up on the private {sf} sample I attached. If you want me to finish the full $100 set, reply YES. If not, no worries and I won’t follow up again.\n\n– Anastaysia",
      "BounceFallback":f"Hi — I made a private {sf} sample for {b}, but the public email I tried bounced. What business email should I send the preview to?\n\n– Anastaysia",
      "PaidReply":f"Thanks — payment is confirmed. I’m building the {b} package around {a}. I’ll send the finished files in this email thread when they’re ready.\n\n– Anastaysia",
      "FulfillmentReply":f"Hi {b} team — your finished $100 content package is ready. I’ve organized the posts, graphics, follow-up copy, review/message replies and CTAs so they’re easy to reuse. If you want a different service emphasized in a future set, reply here.\n\n– Anastaysia",
    }


def assign(rows:list[dict])->list[dict]:
    for r in rows:
        r["HitScore"]=score(r); r["ServiceFocus"]=service_focus(r); r["WhyFit"]=why_fit(r)
    rows.sort(key=lambda r:(-r["HitScore"], r["Business"].lower()))
    for i,r in enumerate(rows,1):
        r["MasterRank"]=i
        # matched-pair / alternating assignment keeps quality balanced for the V5-vs-V6 message test.
        r["Version"]="V5" if i%2 else "V6"
        r["VersionRank"]=(i+1)//2
        subject,body=(email_v5(r) if r["Version"]=="V5" else email_v6(r))
        r["Subject"]=subject; r["InitialEmail"]=body
        r.update(reply_fields(r))
        r["ForecastReplyWindow"]="Prioritize first; timing is not guaranteed" if r["HitScore"]>=90 else "Priority-ranked; timing is not guaranteed"
    assert sum(r["Version"]=="V5" for r in rows)==200 and sum(r["Version"]=="V6" for r in rows)==200
    return rows

PALETTES=[("#21d4fd","#b721ff"),("#00f5a0","#00d9f5"),("#ff9966","#ff5e62"),("#f9d423","#ff4e50"),("#a8ff78","#78ffd6"),("#f857a6","#ff5858"),("#43e97b","#38f9d7"),("#30cfd0","#330867")]


def font(size:int,bold:bool=False):
    paths=["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for p in paths:
        try:return ImageFont.truetype(p,size)
        except Exception:pass
    return ImageFont.load_default()


def rgb(h):return tuple(int(h[i:i+2],16) for i in (1,3,5))

def draw_icon(d:ImageDraw.ImageDraw, industry:str, box:tuple, color):
    x1,y1,x2,y2=box; cx=(x1+x2)//2; cy=(y1+y2)//2; w=x2-x1; ind=industry.lower()
    if any(k in ind for k in ("electric","low voltage","security","it")):
        pts=[(cx-w*.08,y1),(cx-w*.30,cy),(cx-w*.05,cy),(cx-w*.20,y2),(cx+w*.30,cy-w*.05),(cx+w*.05,cy-w*.05)]; d.polygon(pts,fill=color)
    elif any(k in ind for k in ("hvac","plumb","water")):
        d.ellipse((cx-w*.28,cy-w*.28,cx+w*.28,cy+w*.28),outline=color,width=16); d.line((cx,cy-w*.35,cx,cy+w*.35),fill=color,width=12); d.line((cx-w*.35,cy,cx+w*.35,cy),fill=color,width=12)
    elif any(k in ind for k in ("auto","collision")):
        d.rounded_rectangle((x1+w*.12,cy-w*.12,x2-w*.12,cy+w*.18),radius=24,outline=color,width=14); d.ellipse((x1+w*.22,cy+w*.10,x1+w*.36,cy+w*.24),fill=color); d.ellipse((x2-w*.36,cy+w*.10,x2-w*.22,cy+w*.24),fill=color)
    elif any(k in ind for k in ("landscap","tree","flor","organizing","cleaning")):
        d.ellipse((cx-w*.24,y1+w*.10,cx+w*.04,cy+w*.05),fill=color); d.ellipse((cx-w*.03,y1+w*.18,cx+w*.27,cy+w*.12),fill=color); d.line((cx,cy-w*.05,cx,cy+w*.35),fill=color,width=12)
    elif any(k in ind for k in ("food","restaurant","cater","coffee","bakery")):
        d.ellipse((x1+w*.12,cy-w*.22,x2-w*.12,cy+w*.22),outline=color,width=14); d.line((cx-w*.28,cy,cx+w*.28,cy),fill=color,width=10)
    elif any(k in ind for k in ("dental","wellness","fitness","martial","dance","music","tutor")):
        d.ellipse((cx-w*.10,y1+w*.08,cx+w*.10,y1+w*.28),fill=color); d.line((cx, y1+w*.28, cx, y2-w*.18),fill=color,width=14); d.line((cx,cy-w*.04,cx-w*.26,cy+w*.08),fill=color,width=10); d.line((cx,cy-w*.04,cx+w*.26,cy+w*.08),fill=color,width=10)
    else:
        d.rectangle((x1+w*.12,cy-w*.12,x2-w*.12,y2-w*.08),outline=color,width=14); d.polygon([(x1+w*.05,cy-w*.12),(cx,y1+w*.08),(x2-w*.05,cy-w*.12)],outline=color)


def graphic(r:dict,out:Path):
    h=int(hashlib.md5(r["Business"].encode()).hexdigest()[:8],16); c1,c2=PALETTES[h%len(PALETTES)]; a1,a2=rgb(c1),rgb(c2)
    im=Image.new("RGB",(1600,1000),(4,12,24)); d=ImageDraw.Draw(im)
    # business-unique geometric field
    for i in range(22):
        x=(h*(i+3)*17)%1600; y=(h*(i+5)*11)%1000; rad=30+((h>>i%16)&95); col=a1 if i%2==0 else a2; d.ellipse((x-rad,y-rad,x+rad,y+rad),fill=(*col,),outline=None)
    d.rectangle((0,0,900,1000),fill=(5,17,31)); d.rectangle((0,0,16,1000),fill=a1)
    d.rounded_rectangle((65,55,390,105),radius=18,fill=a1); d.text((90,68),f"PRIVATE {r['Version']} PREVIEW",font=font(23,True),fill=(3,13,24))
    y=145; nf=font(50 if len(r["Business"])<32 else 40,True)
    for line in textwrap.wrap(r["Business"],30)[:3]: d.text((70,y),line,font=nf,fill="white"); y+=nf.size+6
    d.text((72,y+10),f"{r.get('City','')}  •  {r.get('Industry','')}",font=font(22,True),fill=a2); y+=70
    d.text((72,y),"CONTENT BUILT AROUND",font=font(18,True),fill=(190,210,225)); y+=32
    for line in textwrap.wrap(r["ServiceFocus"].upper(),36)[:2]: d.text((72,y),line,font=font(31,True),fill=a1); y+=39
    y+=16; d.text((72,y),"WHY THIS FITS",font=font(18,True),fill=(190,210,225)); y+=32
    obs=(r.get("Observation") or "").strip()
    for line in textwrap.wrap(obs,62)[:4]: d.text((72,y),line,font=font(21),fill=(235,241,246)); y+=30
    d.rounded_rectangle((72,690,790,820),radius=20,fill=(11,31,48),outline=a2,width=3); d.text((98,711),"$100 ONE TIME • DONE FOR YOU",font=font(24,True),fill=a2); d.text((98,752),"10 POSTS • GRAPHICS • FOLLOW-UPS • REPLY COPY",font=font(17,True),fill="white"); d.text((98,782),"STRONGER CTAs • READY TO USE • NO CONTRACT",font=font(17,True),fill="white")
    d.rounded_rectangle((72,856,790,925),radius=18,fill=a1); d.text((102,875),'LIKE THE SAMPLE?  REPLY “YES”',font=font(23,True),fill=(3,13,24))
    draw_icon(d,r.get("Industry",""),(1070,210,1500,650),a2); d.rounded_rectangle((1040,725,1530,870),radius=24,fill=(5,17,31),outline=a1,width=3); d.text((1080,750),"MADE FOR",font=font(20,True),fill=a2); d.text((1080,790),r["Business"][:28],font=font(25,True),fill="white"); d.text((1080,832),r["ServiceFocus"][:34],font=font(18),fill=(215,229,239))
    d.text((72,956),"Private concept • based on public business information • no guaranteed results",font=font(17),fill=(185,202,214))
    im.save(out,"JPEG",quality=88,optimize=True,progressive=True)


def make_eml(r:dict,img:Path,out:Path):
    msg=EmailMessage(policy=SMTP); msg["To"]=r["Email"]; msg["Subject"]=r["Subject"]; msg["From"]=""; msg["X-Unsent"]="1"; msg.set_content(r["InitialEmail"]); msg.add_attachment(img.read_bytes(),maintype="image",subtype="jpeg",filename=img.name); out.write_bytes(msg.as_bytes())

FIELDS=["Version","VersionRank","MasterRank","Business","City","Industry","HitScore","ForecastReplyWindow","Email","Website","Phone","SourceURL","CheckDate","EvidenceNote","ServiceFocus","Observation","WhyFit","Subject","InitialEmail","GraphicFilename","EMLFilename","InterestedReply","PriceReply","ProofReply","MoreInfoReply","LaterReply","Followup","BounceFallback","PaidReply","FulfillmentReply","Status","LastContact","NextFollowup","Notes"]


def csv_write(path,rs):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore"); w.writeheader(); w.writerows(rs)


def portal(rs,title):
    data=json.dumps(rs,ensure_ascii=False).replace("</","<\\/")
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>body{{margin:0;background:#06111d;color:#eef7fc;font:14px Arial}}header{{position:sticky;top:0;background:#071a2b;padding:14px;border-bottom:1px solid #24506b;z-index:3}}main{{padding:14px}}input,select,textarea{{background:#0a1b28;color:#fff;border:1px solid #28506b;border-radius:9px;padding:9px}}.controls{{display:flex;gap:8px;flex-wrap:wrap}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(390px,1fr));gap:13px;margin-top:14px}}.card{{background:#0d2031;border:1px solid #21475e;border-radius:16px;overflow:hidden}}img{{width:100%;aspect-ratio:16/10;object-fit:cover}}.b{{padding:13px}}.pill{{display:inline-block;padding:5px 8px;border-radius:999px;background:#173b50;margin-right:5px}}a,button{{display:inline-block;background:#35d6c3;color:#05121c;font-weight:bold;text-decoration:none;border:0;border-radius:8px;padding:9px;margin:4px}}details{{margin-top:8px}}pre{{white-space:pre-wrap;background:#06141e;padding:9px;border-radius:8px}}textarea{{width:100%;min-height:55px}}</style></head><body><header><h2>{html.escape(title)}</h2><div class="controls"><input id="q" placeholder="Search business, city, service…"><select id="v"><option value="">All versions</option><option>V5</option><option>V6</option></select><select id="s"><option value="">All statuses</option><option>New</option><option>Contacted</option><option>Replied</option><option>Interested</option><option>Invoice Sent</option><option>Paid</option><option>Fulfilled</option><option>Lost</option><option>Do Not Contact</option></select><span id="count"></span></div></header><main><div id="grid" class="grid"></div></main><script>const P={data},PAY={json.dumps(PAYPAL)};const K=id=>'cashhv56:'+id,st=id=>JSON.parse(localStorage.getItem(K(id))||'{{}}'),save=(id,o)=>localStorage.setItem(K(id),JSON.stringify({{...st(id),...o}}));const esc=x=>String(x??'').replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));function mt(r){{return 'mailto:'+r.Email+'?subject='+encodeURIComponent(r.Subject)+'&body='+encodeURIComponent(r.InitialEmail)}}function card(r){{let z=st(r.MasterRank),ss=z.status||'New';return `<article class="card"><img loading="lazy" src="graphics/${{esc(r.GraphicFilename)}}"><div class="b"><span class="pill">${{r.Version}} #${{r.VersionRank}}</span><span class="pill">Hit ${{r.HitScore}}</span><h3>${{esc(r.Business)}}</h3><div>${{esc(r.City)}} • ${{esc(r.Industry)}} • ${{esc(r.Email)}}</div><p>${{esc(r.WhyFit)}}</p><a href="${{mt(r)}}">Compose email</a><a href="ready-emails/${{esc(r.EMLFilename)}}">Ready .eml</a><a href="${{PAY}}" target="_blank">PayPal $100</a><a href="${{esc(r.SourceURL)}}" target="_blank">Verify source</a><details><summary>First email + replies</summary><pre>${{esc(r.InitialEmail)}}</pre><pre><b>Interested</b>\n${{esc(r.InterestedReply)}}</pre><pre><b>Follow-up</b>\n${{esc(r.Followup)}}</pre></details><select onchange="save('${{r.MasterRank}}',{{status:this.value}});render()">${{['New','Contacted','Replied','Interested','Invoice Sent','Paid','Fulfilled','Lost','Do Not Contact'].map(x=>`<option ${{x===ss?'selected':''}}>${{x}}</option>`).join('')}}</select><textarea placeholder="Notes" oninput="save('${{r.MasterRank}}',{{notes:this.value}})">${{esc(z.notes||'')}}</textarea></div></article>`}}function render(){{let q=document.getElementById('q').value.toLowerCase(),v=document.getElementById('v').value,s=document.getElementById('s').value;let a=P.filter(r=>(!q||(r.Business+' '+r.City+' '+r.Industry+' '+r.Email).toLowerCase().includes(q))&&(!v||r.Version===v)&&(!s||(st(r.MasterRank).status||'New')===s));grid.innerHTML=a.map(card).join('');count.textContent=a.length+' visible'}}document.getElementById('q').oninput=render;v.onchange=render;s.onchange=render;render();</script></body></html>'''


def build():
    if OUT.exists():
        import shutil; shutil.rmtree(OUT)
    rows=assign(load_records())
    for v in ("V5","V6"):
        base=OUT/v; (base/"graphics").mkdir(parents=True); (base/"ready-emails").mkdir()
        subset=[r for r in rows if r["Version"]==v]
        for r in subset:
            slug=re.sub(r"[^a-z0-9]+","-",r["Business"].lower()).strip("-")[:64]
            r["GraphicFilename"]=f"{r['VersionRank']:03d}-{v.lower()}-{slug}.jpg"; r["EMLFilename"]=f"{r['VersionRank']:03d}-{v.lower()}-{slug}.eml"; r["Status"]="New"; r["LastContact"]=""; r["NextFollowup"]=""; r["Notes"]=""
            graphic(r,base/"graphics"/r["GraphicFilename"]); make_eml(r,base/"graphics"/r["GraphicFilename"],base/"ready-emails"/r["EMLFilename"])
        csv_write(base/f"{v}-200-Leads.csv",subset); (base/f"prospects-{v.lower()}.json").write_text(json.dumps(subset,indent=2,ensure_ascii=False),encoding="utf-8"); (base/f"Prospect-Portal-{v}.html").write_text(portal(subset,f"Cashh Radar — Ethical {v} Prospect Portal"),encoding="utf-8"); (base/"index.html").write_text(portal(subset,f"Cashh Radar — Ethical {v} Prospect Portal"),encoding="utf-8")
        with (base/f"Why-{v}-Wins.csv").open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f); w.writerow(["Version Rank","Business","City","Industry","Why this prospect fits","Hit Score","Source"]); [w.writerow([r["VersionRank"],r["Business"],r["City"],r["Industry"],r["WhyFit"],r["HitScore"],r["SourceURL"]]) for r in subset]
        (base/"TOP-25-FIRST.txt").write_text("\n\n".join(f"{r['VersionRank']:03d}. {r['Business']} — {r['City']} — {r['Email']}\nAttach: graphics/{r['GraphicFilename']}\nWhy: {r['WhyFit']}" for r in subset[:25]),encoding="utf-8")
        (base/"README.md").write_text(f"# Cashh Radar Ethical {v}\n\n200 source-backed Santa Clara County prospects. First email includes a private preview, transparent $100 one-time package, optional PayPal buy-now link, questions-first path and explicit opt-out. No guaranteed results or fake scarcity.\n",encoding="utf-8")
    # combined folder
    comb=OUT/"combined"; (comb/"graphics").mkdir(parents=True); (comb/"ready-emails").mkdir()
    import shutil
    for v in ("V5","V6"):
        for p in (OUT/v/"graphics").glob("*.jpg"): shutil.copy2(p,comb/"graphics"/p.name)
        for p in (OUT/v/"ready-emails").glob("*.eml"): shutil.copy2(p,comb/"ready-emails"/p.name)
    csv_write(comb/"V5-V6-400-Leads.csv",rows); (comb/"prospects-v5-v6.json").write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding="utf-8"); (comb/"Prospect-Portal-V5-V6-Combined.html").write_text(portal(rows,"Cashh Radar — V5 + V6 Combined 400-Lead Portal"),encoding="utf-8"); (comb/"index.html").write_text(portal(rows,"Cashh Radar — V5 + V6 Combined 400-Lead Portal"),encoding="utf-8")
    (comb/"RESEARCH-NOTES.md").write_text("""# Ethical persuasion research used in V5/V6\n\nV5/V6 deliberately avoids coercion, fake scarcity, fabricated results and guaranteed-sale language. The copy uses: (1) processing fluency — concise, easy-to-process offer language (Alter & Oppenheimer, 2009, https://doi.org/10.1177/1088868309341564); (2) autonomy-supportive wording — high freedom-threatening language increases reactance and reactance is negatively associated with persuasion outcomes (Human Communication Research meta-analysis, 2025, https://academic.oup.com/hcr/article/52/1/38/8178818); (3) reduced decision complexity — choice overload is moderated by task difficulty, preference uncertainty and choice-set complexity (Chernev, Böckenholt & Goodman, 2015, https://doi.org/10.1016/j.jcps.2014.08.002); and (4) concrete proof — every email includes a business-specific preview so the recipient can evaluate the work rather than relying on unsupported claims.\n\nThese findings do not guarantee response, purchase or revenue. V5 and V6 should be compared using actual campaign outcomes.\n""",encoding="utf-8")
    # QA
    qa={"records":len(rows),"v5":sum(r["Version"]=="V5" for r in rows),"v6":sum(r["Version"]=="V6" for r in rows),"unique_businesses":len({norm(r["Business"]) for r in rows}),"unique_emails":len({r["Email"].lower() for r in rows}),"graphics":len(list(OUT.glob("V[56]/graphics/*.jpg"))),"eml":len(list(OUT.glob("V[56]/ready-emails/*.eml"))),"missing_source":sum(not r.get("SourceURL") for r in rows),"guessed_email_allowed":False,"payment":PAYPAL,"status":"PASS"}
    if qa["records"]!=400 or qa["v5"]!=200 or qa["v6"]!=200 or qa["unique_businesses"]!=400 or qa["unique_emails"]!=400 or qa["graphics"]!=400 or qa["eml"]!=400 or qa["missing_source"]: qa["status"]="FAIL"; raise RuntimeError(json.dumps(qa))
    (comb/"QA-Report.json").write_text(json.dumps(qa,indent=2),encoding="utf-8")
    print(json.dumps(qa,indent=2))

if __name__=="__main__": build()
