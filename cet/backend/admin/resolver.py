import csv,json,os,re,logging,urllib.parse,urllib.request,urllib.error
from pathlib import Path

log = logging.getLogger(__name__)
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

def _same_site(a, b):
    """Compare hostnames while allowing www/subdomains of the same site."""
    try:
        ha = (urllib.parse.urlparse(valid_url(a)).hostname or "").lower().removeprefix("www.")
        hb = (urllib.parse.urlparse(valid_url(b)).hostname or "").lower().removeprefix("www.")
        return bool(ha and hb and (ha == hb or ha.endswith("." + hb) or hb.endswith("." + ha)))
    except Exception:
        return False


def gemini_verify_candidate(college_name, candidate_url, city=None):
    """Use Gemini + Google Search to verify that a working URL belongs to the college."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    location = f", {city}" if city else ""
    prompt = f'''Verify whether this URL is the official website of the exact Indian college/institution.
College: {college_name}{location}
Candidate URL: {candidate_url}
Search the web and inspect the candidate identity. Do not accept directories, social profiles,
ranking sites, admission aggregators, unrelated universities, or another institution with a
similar name. Return ONLY JSON with keys verified, confidence, official_url, city, address, note.
Set verified=true only when the candidate clearly belongs to the named institution.'''
    payload = {"contents":[{"parts":[{"text":prompt}]}],"tools":[{"google_search":{}}]}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(GEMINI_MODEL,safe='')}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type":"application/json","x-goog-api-key":key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini verification failed ({e.code})")
    text = "".join(part.get("text","") for c in data.get("candidates",[])
                   for part in c.get("content",{}).get("parts",[]))
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError("Gemini returned no structured verification result")
    try:
        result = json.loads(m.group(0))
    except Exception:
        raise RuntimeError("Gemini returned invalid verification JSON")
    result["official_url"] = valid_url(result.get("official_url"))
    return result


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

def _reference_contacts():
    """Load the maintained contact file, supporting both headered and legacy headerless CSVs."""
    contacts = {}
    if not CONTACTS.exists():
        return contacts
    with CONTACTS.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    if not rows:
        return contacts
    header = [str(x).strip().lower() for x in rows[0]]
    if {'college_code', 'college_name', 'city', 'website'}.issubset(header):
        data_rows = [dict(zip(header, r)) for r in rows[1:]]
    else:
        data_rows = [
            {'college_code': r[0] if len(r) > 0 else '',
             'college_name': r[1] if len(r) > 1 else '',
             'city': r[2] if len(r) > 2 else '',
             'website': r[3] if len(r) > 3 else ''}
            for r in rows
        ]
    for r in data_rows:
        code = str(r.get('college_code', '')).strip()
        if not code:
            continue
        website = str(r.get('website', '')).strip()
        if website.lower() in {'', 'unknown', 'nan', 'none'}:
            website = None
        contacts[code] = {
            'institution_name': str(r.get('college_name', '')).strip() or None,
            'city': str(r.get('city', '')).strip() or None,
            'website': valid_url(website) if website else None,
        }
    return contacts


def seed_from_import(conn, job_id):
    """Create resolver rows from the colleges actually present in an import.

    The PDF/import is the scope of work. Existing institute/reference data is
    preferred for city and website; no broad external dataset is used to
    invent unrelated resolver institutions.
    """
    refs = _reference_contacts()
    source_rows = conn.execute(
        "SELECT normalized_json FROM import_staging_records "
        "WHERE job_id=? AND result_type IN ('CUTOFFS','SEATS') "
        "ORDER BY id",
        (job_id,),
    ).fetchall()
    colleges = {}
    for row in source_rows:
        try:
            data = json.loads(row['normalized_json'] or '{}')
        except Exception:
            continue
        code = str(data.get('institution_code', '')).strip()
        if not code:
            continue
        colleges.setdefault(code, {
            'institution_name': str(data.get('institution_name', '')).strip() or code
        })

    seeded = 0
    for code, incoming in colleges.items():
        inst = conn.execute(
            "SELECT institution_code,institution_name,city,website,address "
            "FROM institutes WHERE institution_code=?",
            (code,),
        ).fetchone()
        ref = refs.get(code, {})
        name = (
            (inst['institution_name'] if inst else None)
            or incoming['institution_name']
            or code
        )
        city = (
            (inst['city'] if inst else None)
            or ref.get('city')
            or None
        )
        website = valid_url(inst['website']) if inst and inst['website'] else None
        website_source = 'institutes' if website else None
        if not website and ref.get('website'):
            website = ref['website']
            website_source = 'reference_csv'

        existing = conn.execute(
            "SELECT status,website,city FROM college_website_resolver "
            "WHERE institution_code=?",
            (code,),
        ).fetchone()
        if existing and existing['status'] == 'VERIFIED':
            # Never downgrade an already verified resolver result.
            conn.execute(
                "UPDATE college_website_resolver SET institution_name=?,"
                "city=COALESCE(city,?),updated_at=CURRENT_TIMESTAMP "
                "WHERE institution_code=?",
                (name, city, code),
            )
        else:
            status = 'CANDIDATE' if website else 'PENDING'
            conn.execute(
                """INSERT INTO college_website_resolver
                   (institution_code,institution_name,city,website,status,
                    source,source_url,updated_at)
                   VALUES (?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(institution_code) DO UPDATE SET
                     institution_name=excluded.institution_name,
                     city=COALESCE(college_website_resolver.city,excluded.city),
                     website=CASE
                         WHEN college_website_resolver.website IS NULL
                              OR college_website_resolver.website=''
                         THEN excluded.website
                         ELSE college_website_resolver.website
                     END,
                     status=CASE
                         WHEN college_website_resolver.website IS NOT NULL
                              AND college_website_resolver.website<>'' THEN college_website_resolver.status
                         ELSE excluded.status
                     END,
                     source=CASE
                         WHEN college_website_resolver.website IS NOT NULL
                              AND college_website_resolver.website<>'' THEN college_website_resolver.source
                         ELSE excluded.source
                     END,
                     source_url=CASE
                         WHEN college_website_resolver.website IS NOT NULL
                              AND college_website_resolver.website<>'' THEN college_website_resolver.source_url
                         ELSE excluded.source_url
                     END,
                     updated_at=CURRENT_TIMESTAMP""",
                (code, name, city, website, status, website_source, website,
                 ),
            )
        seeded += 1
    return seeded


def _update_institute_resolution(conn, code, city=None, address=None, website=None, source=None):
    """Mirror trusted resolver fields into the institute reference when present."""
    if not (city or address or website):
        return
    conn.execute(
        """UPDATE institutes
           SET city=COALESCE(?,city),
               address=COALESCE(?,address),
               website=COALESCE(?,website),
               city_source=CASE WHEN ? IS NOT NULL THEN ? ELSE city_source END,
               address_source=CASE WHEN ? IS NOT NULL THEN ? ELSE address_source END,
               website_source=CASE WHEN ? IS NOT NULL THEN ? ELSE website_source END,
               verified_at=CURRENT_TIMESTAMP
           WHERE institution_code=?""",
        (
            city, address, website,
            city, source, address, source, website, source, code,
        ),
    )


def resolve_import_job(job_id=None, limit=None):
    """Resolve a bounded number of colleges without running a long background loop.

    When job_id is supplied, only colleges from that import are considered.
    When job_id is None, the resolver queue is taken from the CAP resolver table.
    A small limit lets the admin UI process one college at a time and keeps the
    web service responsive on small Render instances.

    Order is deliberate:
      1. existing resolver/institute/reference website
      2. verify that URL and capture its redirect target
      3. only then use Gemini + Google Search for unresolved colleges

    City follows the same local-data-first rule. Network discovery is never
    used to create extra institutions outside the uploaded PDF.
    """
    from .db import connect

    seeded = 0
    with connect() as c:
        if job_id is not None:
            seeded = seed_from_import(c, job_id)
            c.commit()

        if job_id is None:
            rows = [
                dict(r) for r in c.execute(
                    "SELECT institution_code,institution_name,city,website,status,source "
                    "FROM college_website_resolver "
                    "WHERE status IN ('PENDING','CANDIDATE','NEEDS_REVIEW') "
                    "ORDER BY CASE status WHEN 'CANDIDATE' THEN 0 WHEN 'PENDING' THEN 1 "
                    "WHEN 'NEEDS_REVIEW' THEN 2 ELSE 3 END, LOWER(institution_name)"
                )
            ]
        else:
            source_rows = c.execute(
                "SELECT normalized_json FROM import_staging_records "
                "WHERE job_id=? AND result_type IN ('CUTOFFS','SEATS') ORDER BY id",
                (job_id,),
            ).fetchall()
            codes = set()
            for item in source_rows:
                try:
                    data = json.loads(item['normalized_json'] or '{}')
                except Exception:
                    continue
                code = str(data.get('institution_code', '')).strip()
                if code:
                    codes.add(code)
            rows = [
                dict(r) for r in c.execute(
                    "SELECT institution_code,institution_name,city,website,status,source "
                    "FROM college_website_resolver ORDER BY institution_name"
                ) if r['institution_code'] in codes and r['status'] != 'VERIFIED'
            ]

    if limit is not None:
        rows = rows[:max(1, int(limit))]
    if not rows:
        return {'ok': True, 'seeded': seeded, 'resolved': 0, 'searched': 0, 'failed': 0, 'remaining': 0}

    resolved = searched = failed = 0
    refs = _reference_contacts()

    for row in rows:
        code = row['institution_code']
        name = row['institution_name']
        city = row.get('city')
        candidate_urls = []
        if row.get('website'):
            candidate_urls.append((row['website'], row.get('source') or 'existing_data'))
        ref_url = refs.get(code, {}).get('website')
        if ref_url and all(ref_url != u for u, _ in candidate_urls):
            candidate_urls.append((ref_url, 'reference_csv'))

        verified = None
        ai_unavailable = False
        reachable_candidate = None
        for url, source in candidate_urls:
            result = verify_url(url, name)
            if result.get('ok'):
                reachable_candidate = (result, source)
            else:
                continue
            # A reachable URL is only a candidate. Gemini + Google Search must
            # confirm the site's identity before we mark it VERIFIED.
            try:
                ai_check = gemini_verify_candidate(name, result['url'], city)
                ai_conf = float(ai_check.get('confidence') or 0)
                ai_url = ai_check.get('official_url')
                if bool(ai_check.get('verified')) and ai_conf >= 0.70 and (
                    not ai_url or _same_site(result['url'], ai_url)
                ):
                    verified = (result, source, ai_check)
                    break
            except Exception as exc:
                if 'GEMINI_API_KEY is not configured' in str(exc):
                    ai_unavailable = True
                    break
                log.warning("AI website verification failed for %s: %s", code, exc)

        if ai_unavailable:
            # Do not misclassify a reachable college website as FAILED just
            # because the optional AI verifier is not configured.
            result, source = reachable_candidate if reachable_candidate else (None, None)
            with connect() as c:
                c.execute(
                    """UPDATE college_website_resolver
                       SET website=COALESCE(?,website),status='NEEDS_REVIEW',
                           source=COALESCE(?,source),
                           source_url=COALESCE(?,source_url),
                           verification_note=?,
                           last_checked_at=CURRENT_TIMESTAMP,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE institution_code=?""",
                    (
                        result.get('url') if result else None,
                        source,
                        result.get('url') if result else None,
                        'Reachable candidate found; Gemini AI verification is not configured on the server.',
                        code,
                    ),
                )
                c.commit()
            continue

        if verified:
            result, source, ai_check = verified
            found_city = city or (str(ai_check.get('city')).strip() if ai_check.get('city') else None)
            found_address = None
            if not city:
                # The website is already verified, but city is still missing.
                # Use search only for the missing location field; never replace
                # the already verified website with the search result.
                try:
                    location_ai, _ = gemini_find(name, None)
                    found_city = str(location_ai.get('city')).strip() if location_ai.get('city') else None
                    found_address = str(location_ai.get('address')).strip() if location_ai.get('address') else None
                except Exception:
                    pass
            with connect() as c:
                c.execute(
                    """UPDATE college_website_resolver
                       SET city=COALESCE(?,city),address=COALESCE(?,address),
                           website=?,status='VERIFIED',source=?,
                           source_url=?,verification_note=?,
                           last_checked_at=CURRENT_TIMESTAMP,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE institution_code=?""",
                    (
                        found_city, found_address, result['url'], source,
                        result['url'], result['note'], code,
                    ),
                )
                _update_institute_resolution(
                    c, code, city=found_city, address=found_address,
                    website=result['url'], source=source
                )
                c.commit()
            resolved += 1
            continue

        try:
            searched += 1
            ai, _ = gemini_find(name, city)
            url = ai.get('official_url')
            found_city = str(ai.get('city')).strip() if ai.get('city') else city
            address = str(ai.get('address')).strip() if ai.get('address') else None
            result = (
                verify_url(url, name)
                if url
                else {'ok': False, 'url': None, 'note': 'Search returned no official URL'}
            )
            ai_check = {}
            if result.get('ok'):
                try:
                    ai_check = gemini_verify_candidate(name, result['url'], found_city)
                except Exception as exc:
                    ai_check = {'verified': False, 'confidence': 0, 'note': f'AI verification failed: {exc}'}
            ai_conf = float(ai_check.get('confidence') or 0)
            ai_url = ai_check.get('official_url')
            if (
                result.get('ok')
                and bool(ai_check.get('verified'))
                and ai_conf >= 0.70
                and (not ai_url or _same_site(result['url'], ai_url))
            ):
                status = 'VERIFIED'
            elif result.get('ok'):
                status = 'NEEDS_REVIEW'
            else:
                status = 'FAILED'
                failed += 1
            final_url = result.get('url') or url
            note = ' '.join(x for x in (
                (ai.get('note') or '').strip(),
                (ai_check.get('note') or '').strip(),
                result.get('note', ''),
            ) if x)
            with connect() as c:
                c.execute(
                    """UPDATE college_website_resolver
                       SET city=?,website=?,address=?,status=?,source=?,
                           source_url=?,verification_note=?,
                           last_checked_at=CURRENT_TIMESTAMP,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE institution_code=?""",
                    (
                        found_city, final_url, address, status,
                        'gemini_google_search', final_url, note, code,
                    ),
                )
                _update_institute_resolution(
                    c, code, city=found_city, address=address,
                    website=final_url if status == 'VERIFIED' else None,
                    source='gemini_google_search',
                )
                c.commit()
            if status == 'VERIFIED':
                resolved += 1
        except Exception as exc:
            message = str(exc)
            if 'GEMINI_API_KEY is not configured' in message:
                # Search cannot run without Gemini, so leave the college queued
                # for a real AI attempt instead of marking it as a dead website.
                failed_note = 'Gemini AI verification/search is not configured on the server.'
                with connect() as c:
                    c.execute(
                        """UPDATE college_website_resolver
                           SET status='NEEDS_REVIEW',verification_note=?,
                               last_checked_at=CURRENT_TIMESTAMP,
                               updated_at=CURRENT_TIMESTAMP
                           WHERE institution_code=?""",
                        (failed_note, code),
                    )
                    c.commit()
                continue
            failed += 1
            with connect() as c:
                c.execute(
                    """UPDATE college_website_resolver
                       SET status='FAILED',verification_note=?,
                           last_checked_at=CURRENT_TIMESTAMP,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE institution_code=?""",
                    (message[:500], code),
                )
                c.commit()

    with connect() as c:
        remaining = c.execute(
            "SELECT COUNT(*) AS n FROM college_website_resolver "
            "WHERE status IN ('PENDING','CANDIDATE','NEEDS_REVIEW')"
        ).fetchone()['n']
    return {
        'ok': True,
        'seeded': seeded,
        'resolved': resolved,
        'searched': searched,
        'failed': failed,
        'remaining': int(remaining),
    }


def sync_institutes_to_resolver(conn):
    """Synchronize resolver only from institutes still backed by production data.

    Older rollback flows could leave orphan institute rows behind. Those rows
    must never reappear in the resolver queue after the underlying production
    data has been deleted.
    """
    refs = _reference_contacts()
    # Resolver is a derived view of production-backed institutes. Never delete
    # rows from the authoritative institutes table while merely opening this page.
    # Use EXISTS instead of NOT IN so NULLs in imported data cannot empty the scope.
    conn.execute(
        "DELETE FROM college_website_resolver r "
        "WHERE r.institution_code LIKE 'GH:%' "
        "OR NOT EXISTS ("
        "SELECT 1 FROM cutoffs c WHERE c.institution_code=r.institution_code "
        "UNION ALL "
        "SELECT 1 FROM seats s WHERE s.institution_code=r.institution_code)"
    )
    # Production records are the ultimate source of scope. Do not require
    # the derived institutes table to already exist; older rollback/import flows
    # can leave cutoffs/seats intact while institutes needs reconstruction.
    rows = conn.execute(
        "SELECT x.institution_code, "
        "       COALESCE(i.institution_name,'') AS institution_name, "
        "       i.city, i.website, i.address "
        "FROM ("
        "  SELECT DISTINCT institution_code FROM cutoffs "
        "  UNION "
        "  SELECT DISTINCT institution_code FROM seats"
        ") x "
        "LEFT JOIN institutes i ON i.institution_code=x.institution_code "
        "ORDER BY x.institution_code"
    ).fetchall()
    count = 0
    for r in rows:
        code = str(r['institution_code']).strip()
        if not code:
            continue
        ref = refs.get(code, {})
        ref_name = str(ref.get('institution_name') or '').strip()
        db_name = str(r['institution_name'] or '').strip()
        # Imports can temporarily store only the CAP choice code as the name.
        # Prefer the maintained reference name when it is available.
        name = ref_name if ref_name and (not db_name or db_name == code) else (db_name or ref_name or code)
        # Repair a missing derived institute row from production-backed scope.
        conn.execute(
            "INSERT INTO institutes(institution_code,institution_name) VALUES(?,?) "
            "ON CONFLICT(institution_code) DO UPDATE SET "
            "institution_name=CASE WHEN institutes.institution_name IS NULL OR institutes.institution_name='' "
            "THEN excluded.institution_name ELSE institutes.institution_name END",
            (code, name),
        )
        city = r['city'] or ref.get('city')
        website = valid_url(r['website']) if r['website'] else ref.get('website')
        source = 'institutes' if r['website'] else ('reference_csv' if website else None)
        # Keep the public institute metadata aligned with the same maintained
        # reference source used by the resolver, without overwriting admin data.
        if ref_name or city or website:
            conn.execute(
                "UPDATE institutes SET "
                "institution_name=CASE WHEN (institution_name IS NULL OR institution_name=?) AND ? IS NOT NULL THEN ? ELSE institution_name END,"
                "city=COALESCE(city,?),website=COALESCE(website,?),"
                "city_source=CASE WHEN city IS NULL AND ? IS NOT NULL THEN 'reference_csv' ELSE city_source END,"
                "website_source=CASE WHEN website IS NULL AND ? IS NOT NULL THEN 'reference_csv' ELSE website_source END,"
                "verified_at=CASE WHEN (? IS NOT NULL OR ? IS NOT NULL) THEN COALESCE(verified_at,CURRENT_TIMESTAMP) ELSE verified_at END "
                "WHERE institution_code=?",
                (code, ref_name or None, ref_name or None, city, website,
                 city, website, city, website, code),
            )
        existing = conn.execute(
            "SELECT status,website FROM college_website_resolver WHERE institution_code=?",
            (code,),
        ).fetchone()
        if existing and existing['status'] == 'VERIFIED':
            conn.execute(
                "UPDATE college_website_resolver SET institution_name=?,"
                "city=COALESCE(city,?),updated_at=CURRENT_TIMESTAMP "
                "WHERE institution_code=?",
                (name, city, code),
            )
        else:
            conn.execute(
                """INSERT INTO college_website_resolver
                   (institution_code,institution_name,city,website,status,source,source_url)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(institution_code) DO UPDATE SET
                     institution_name=excluded.institution_name,
                     city=COALESCE(college_website_resolver.city,excluded.city),
                     website=CASE
                       WHEN college_website_resolver.website IS NULL
                            OR college_website_resolver.website=''
                       THEN excluded.website
                       ELSE college_website_resolver.website
                     END,
                     status=CASE
                       WHEN college_website_resolver.website IS NOT NULL
                            AND college_website_resolver.website<>'' THEN college_website_resolver.status
                       ELSE excluded.status
                     END,
                     source=CASE
                       WHEN college_website_resolver.website IS NOT NULL
                            AND college_website_resolver.website<>'' THEN college_website_resolver.source
                       ELSE excluded.source
                     END,
                     source_url=CASE
                       WHEN college_website_resolver.website IS NOT NULL
                            AND college_website_resolver.website<>'' THEN college_website_resolver.source_url
                       ELSE excluded.source_url
                     END,
                     updated_at=CURRENT_TIMESTAMP""",
                (
                    code, name, city, website,
                    'CANDIDATE' if website else 'PENDING',
                    source, website,
                ),
            )
        count += 1
    return count


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
