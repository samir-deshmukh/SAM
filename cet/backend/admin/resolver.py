import csv,json,os,re,urllib.parse,urllib.request,urllib.error
from pathlib import Path
BASE=Path(__file__).resolve().parents[2]
CONTACTS=BASE/'data'/'reference'/'institute_contacts.csv'
GEMINI_MODEL=os.getenv('GEMINI_RESOLVER_MODEL','gemini-2.5-flash')

def valid_url(url):
    if not url:
        return None
    url = str(url).strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.scheme:
        url = "https://" + url
    try:
        u=urllib.parse.urlparse(url)
        if u.scheme.lower() not in ('http','https') or not u.netloc:return None
        if (u.hostname or '').lower() in {'localhost','127.0.0.1','0.0.0.0','::1'}:return None
        return urllib.parse.urlunparse((u.scheme.lower(),u.netloc,u.path or '/',u.params,u.query,''))
    except Exception:return None

def verify_url(url,college_name,timeout=7):
    url=valid_url(url)
    if not url:return {'ok':False,'url':None,'note':'Invalid URL'}
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'CET-CAP-Website-Resolver/1.0'})
        with urllib.request.urlopen(req,timeout=timeout) as r:
            final=r.geturl(); status=getattr(r,'status',200); ctype=r.headers.get('content-type','')
            body=r.read(120000).decode('utf-8','ignore') if 'text' in ctype.lower() or 'html' in ctype.lower() else ''
        tokens=[x.lower() for x in re.findall(r'[a-z0-9]+',college_name) if len(x)>2]
        hay=(final+' '+body[:100000]).lower(); hits=sum(t in hay for t in tokens); denom=max(1,min(len(tokens),8))
        return {'ok':200<=status<400,'url':valid_url(final),'status':status,'match_score':hits/denom,'note':f'HTTP {status}; college-name match {hits}/{denom}'}
    except Exception as e:return {'ok':False,'url':url,'note':f'Unreachable: {type(e).__name__}'}

def seed_from_contacts(conn):
    if not CONTACTS.exists():return 0
    n=0
    with CONTACTS.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            code=str(r.get('college_code','')).strip(); name=str(r.get('college_name','')).strip()
            if not code or not name:continue
            city=str(r.get('city','')).strip() or None; w=str(r.get('website','')).strip(); w=None if w.lower() in {'','unknown','nan','none'} else w
            conn.execute('''INSERT INTO college_website_resolver(institution_code,institution_name,city,website,status,source,source_url) VALUES (?,?,?,?,?,?,?) ON CONFLICT(institution_code) DO UPDATE SET institution_name=excluded.institution_name,city=COALESCE(excluded.city,college_website_resolver.city),website=CASE WHEN college_website_resolver.website IS NULL OR college_website_resolver.website='' THEN excluded.website ELSE college_website_resolver.website END''',(code,name,city,w,'CANDIDATE' if w else 'PENDING','reference_csv','data/reference/institute_contacts.csv'))
            conn.execute("UPDATE institutes SET city=COALESCE(?,city), website=COALESCE(?,website), city_source=CASE WHEN ? IS NOT NULL THEN 'reference_csv' ELSE city_source END, website_source=CASE WHEN ? IS NOT NULL THEN 'reference_csv' ELSE website_source END, verified_at=CURRENT_TIMESTAMP WHERE institution_code=?",(city,w,city,w,code)); n+=1
    return n

GITHUB_MAPPING_URL='https://raw.githubusercontent.com/github/india/main/Students/GCP-India.md'

def sync_github_india(conn):
    req=urllib.request.Request(GITHUB_MAPPING_URL,headers={'User-Agent':'CET-CAP-Website-Resolver/1.0'})
    with urllib.request.urlopen(req,timeout=20) as r: text=r.read().decode('utf-8','ignore')
    n=0
    import hashlib
    for line in text.splitlines():
        if not line.startswith('|') or 'University Name' in line or '---' in line: continue
        cells=[x.strip() for x in line.strip().strip('|').split('|')]
        if len(cells)<3: continue
        name,url=cells[0],valid_url(cells[1])
        if not name or not url: continue
        code='GH:'+hashlib.sha1(name.strip().lower().encode()).hexdigest()[:16]
        conn.execute("INSERT INTO college_website_resolver(institution_code,institution_name,website,status,source,source_url) VALUES (?,?,?,?,?,?) ON CONFLICT(institution_code) DO UPDATE SET website=excluded.website,source=excluded.source,source_url=excluded.source_url",(code,name,url,'CANDIDATE','github_india_2021',GITHUB_MAPPING_URL)); n+=1
    return n

def gemini_find(college_name,city=None):
    key=os.getenv('GEMINI_API_KEY','').strip()
    if not key:raise RuntimeError('GEMINI_API_KEY is not configured')
    location=f', {city}' if city else ''
    prompt=f'''Find the official website of this Indian college/institution. College: {college_name}{location}. Use Google Search. Return ONLY valid JSON with keys official_url, city, address, confidence, note. The URL must be the institution's own official website, not a directory, social profile, ranking site, admissions portal, or aggregator. City must be the physical city/town of the institution, not a district or state. Address should be the official campus address when available. If uncertain, set the uncertain field to null and use a low confidence value.'''
    payload={'contents':[{'parts':[{'text':prompt}]}],'tools':[{'google_search':{}}]}
    req=urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(GEMINI_MODEL,safe="")}:generateContent',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','x-goog-api-key':key},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=45) as r:data=json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError(f'Gemini request failed ({e.code})')
    text=''.join(part.get('text','') for c in data.get('candidates',[]) for part in c.get('content',{}).get('parts',[])); m=re.search(r'\{.*\}',text,re.S)
    if not m:raise RuntimeError('Gemini returned no structured result')
    try:return json.loads(m.group(0)),data
    except Exception:raise RuntimeError('Gemini returned invalid JSON')
