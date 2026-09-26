import os,uuid,json,time,re,secrets,logging,html
from pathlib import Path
from fastapi import FastAPI,Request,UploadFile,File,HTTPException,Form
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse,RedirectResponse,JSONResponse,FileResponse,Response
from .admin.db import connect,init_admin_schema,event
from .admin.security import verify_password,make_session,read_session
from .admin.pipeline import run_preflight,MAX_PDF_BYTES
from .admin.processing import process_import,approve_import,rollback_release
from .admin.publishing import publish_release
from .admin.migrations import ensure_part4_schema
from .admin.state import JobStatus
from .admin_ui import dashboard, import_center, review_center, releases_page, health_page, audit_page, live_processing, feedback_page, resolver_page
from .admin.resolver import seed_from_contacts, sync_github_india, verify_url, gemini_find
from .api import router as public_api_router
BASE = Path(__file__).resolve().parent.parent
SITE = BASE / 'site'
IMPORTS = BASE / 'data' / 'imports'
IMPORTS.mkdir(parents=True, exist_ok=True)
@asynccontextmanager
async def lifespan(_app):
    init_admin_schema()
    ensure_part4_schema()
    yield

app=FastAPI(title='CET CAP Admin API', lifespan=lifespan)
app.include_router(public_api_router)
log=logging.getLogger('cet-cap-admin')
_PRODUCTION=os.getenv('CET_ENV','production').lower() == 'production'
_COOKIE_SECURE=os.getenv('CET_ADMIN_COOKIE_SECURE','1' if _PRODUCTION else '0') == '1'
_CSRF_COOKIE='cet_admin_csrf'
_SESSION_COOKIE='cet_admin_session'


# ── Simple in-process rate limiter for the public data API ──
_rate_store: dict[str, list[float]] = {}
_RATE_WINDOW = 60.0      # seconds
_RATE_LIMIT   = 120       # max requests per IP per window

def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    hits = _rate_store.get(ip, [])
    hits = [t for t in hits if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_LIMIT:
        _rate_store[ip] = hits
        return False
    hits.append(now)
    _rate_store[ip] = hits
    # Prune store to avoid unbounded growth
    if len(_rate_store) > 5000:
        cutoff = now - _RATE_WINDOW
        for k in list(_rate_store):
            _rate_store[k] = [t for t in _rate_store[k] if t > cutoff]
            if not _rate_store[k]: del _rate_store[k]
    return True

# Allowed origins for the public data API (Referer / Origin check).
# In production add your real domain.  An empty env var disables the check
# so local file:// and dev server access still work.
_ALLOWED_ORIGINS_ENV = os.getenv('CET_DATA_ALLOWED_ORIGINS', '')
_ALLOWED_ORIGINS: list[str] = [o.strip() for o in _ALLOWED_ORIGINS_ENV.split(',') if o.strip()]

_SAFE_DATA_PATTERN = re.compile(r'^[a-zA-Z0-9/_.-]+\.(?:js|json)$')
_DATA_DIR = SITE / 'data'

# ── Login brute-force limiter: 5 attempts per IP per 60 seconds ──
_LOGIN_RATE: dict[str, list[float]] = {}
_LOGIN_LIMIT = 5

def _login_ok(ip: str) -> bool:
    now = time.monotonic()
    hits = _LOGIN_RATE.get(ip, [])
    hits = [t for t in hits if now - t < 60]
    if len(hits) >= _LOGIN_LIMIT:
        _LOGIN_RATE[ip] = hits
        return False
    hits.append(now)
    _LOGIN_RATE[ip] = hits
    return True

_LOGIN_ACCOUNT: dict[str, list[float]] = {}
_LOGIN_LOCK: dict[str, float] = {}

def _login_account_ok(username: str) -> bool:
    now = time.monotonic()
    key = username.strip().lower()[:128]
    until=_LOGIN_LOCK.get(key,0)
    if until > now: return False
    hits=[t for t in _LOGIN_ACCOUNT.get(key,[]) if now-t < 300]
    _LOGIN_ACCOUNT[key]=hits
    return len(hits) < 5

def _record_login_failure(username: str) -> None:
    now = time.monotonic()
    key = username.strip().lower()[:128]
    hits=[t for t in _LOGIN_ACCOUNT.get(key,[]) if now-t < 300]
    hits.append(now)
    _LOGIN_ACCOUNT[key] = hits
    if len(hits) >= 5: _LOGIN_LOCK[key]=now+300

def _csrf_value(request: Request) -> str:
    token=request.cookies.get(_CSRF_COOKIE)
    if token and re.fullmatch(r'[A-Za-z0-9_-]{32,128}',token): return token
    return secrets.token_urlsafe(32)

def _set_csrf(response, token: str):
    response.set_cookie(_CSRF_COOKIE, token, httponly=False, secure=_COOKIE_SECURE,
                        samesite='strict', path='/admin', max_age=28800)

def _check_csrf(request: Request, supplied: str|None=None) -> None:
    cookie=request.cookies.get(_CSRF_COOKIE)
    header=request.headers.get('x-csrf-token')
    candidate=header or supplied
    if not cookie or not candidate or not hmac_compare(cookie,candidate):
        raise HTTPException(403,'CSRF validation failed')

def hmac_compare(a: str,b: str) -> bool:
    import hmac
    return hmac.compare_digest(a,b)



@app.middleware('http')
async def security_headers(request: Request, call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data:; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/admin') else response.headers.get('Cache-Control','no-cache')
    if _COOKIE_SECURE:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response
@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    # Keep API/admin 404s machine-readable; render the candidate-facing 404 page for browser routes.
    if request.url.path.startswith('/api/') or request.url.path.startswith('/admin/'):
        return JSONResponse(status_code=404, content={'detail': 'Not Found'})
    return FileResponse(SITE/'404.html', status_code=404, media_type='text/html')

# ── Public candidate site ──
@app.get('/', include_in_schema=False)
def public_home():
    return FileResponse(SITE/'index.html', media_type='text/html')

@app.get('/privacy.html', include_in_schema=False)
def public_privacy():
    return FileResponse(SITE/'privacy.html', media_type='text/html')

@app.get('/knowledge.html', include_in_schema=False)
def public_knowledge():
    return FileResponse(SITE/'knowledge.html', media_type='text/html')

# Public feedback uses a separate limiter so normal data browsing is unaffected.
_FEEDBACK_RATE: dict[str, list[float]] = {}
_FEEDBACK_WINDOW = 600.0
_FEEDBACK_LIMIT = 3

def _feedback_ok(ip: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _FEEDBACK_RATE.get(ip, []) if now - t < _FEEDBACK_WINDOW]
    if len(hits) >= _FEEDBACK_LIMIT:
        _FEEDBACK_RATE[ip] = hits
        return False
    hits.append(now)
    _FEEDBACK_RATE[ip] = hits
    if len(_FEEDBACK_RATE) > 5000:
        for k in list(_FEEDBACK_RATE):
            _FEEDBACK_RATE[k] = [t for t in _FEEDBACK_RATE[k] if now - t < _FEEDBACK_WINDOW]
            if not _FEEDBACK_RATE[k]: del _FEEDBACK_RATE[k]
    return True

@app.post('/api/feedback')
async def public_feedback(request: Request):
    ip=(request.headers.get('x-forwarded-for') or '').split(',')[0].strip() or (request.client.host if request.client else 'unknown')
    if not _feedback_ok(ip):
        raise HTTPException(429, 'Please wait before sending more feedback.')
    try:
        body=await request.json()
    except Exception:
        raise HTTPException(400, 'Invalid feedback payload')
    # Honeypot: silently accept bot submissions without storing them.
    if str(body.get('website','')).strip():
        return {'ok': True}
    message=str(body.get('message','')).strip()
    if not message or len(message) > 2000:
        raise HTTPException(400, 'Feedback must be between 1 and 2000 characters.')
    rating=body.get('rating')
    if rating in ('', None): rating=None
    else:
        try: rating=int(rating)
        except (TypeError, ValueError): raise HTTPException(400, 'Rating must be a number from 1 to 5.')
        if rating < 1 or rating > 5: raise HTTPException(400, 'Rating must be a number from 1 to 5.')
    page=str(body.get('page','/'))[:300]
    ua=request.headers.get('user-agent','')[:500]
    with connect() as c:
        c.execute('INSERT INTO public_feedback(rating,message,page,user_agent) VALUES (?,?,?,?)',(rating,message,page,ua))
        c.commit()
    return {'ok': True}

# Public data files are intentionally NOT mounted. Master datasets remain server-side.

def user(request):
    session = request.cookies.get(_SESSION_COOKIE)
    if not session:
        return None

    payload = read_session(session)
    if not payload or 'uid' not in payload or 'av' not in payload:
        return None

    try:
        with connect() as connection:
            row = connection.execute(
                'SELECT id,role,is_active,auth_version FROM admin_users WHERE id=?',
                (int(payload['uid']),),
            ).fetchone()
        if (
            not row
            or not row['is_active']
            or int(row['auth_version']) != int(payload['av'])
            or row['role'] != payload.get('role')
        ):
            return None
        return {
            'uid': int(row['id']),
            'role': row['role'],
            'av': int(row['auth_version']),
        }
    except Exception:
        log.exception('Session validation failed')
        return None


def require(request, roles=None, csrf=False, csrf_value=None):
    current_user = user(request)
    if not current_user:
        raise HTTPException(401, 'Authentication required')
    if roles and current_user['role'] not in roles:
        raise HTTPException(403, 'Insufficient role')
    if csrf:
        _check_csrf(request, csrf_value)
    return current_user


@app.get('/admin/login', response_class=HTMLResponse)
def login(request: Request):
    token = _csrf_value(request)
    resp = HTMLResponse(
        f'<h1>CET CAP Admin</h1><form method="post">'
        f'<input type="hidden" name="csrf_token" value="{token}">'
        '<input name="username" autocomplete="username">'
        '<input name="password" type="password" autocomplete="current-password">'
        '<button>Sign in</button></form>'
    )
    _set_csrf(resp, token)
    return resp


@app.post('/admin/login')
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    ip = (request.headers.get('x-forwarded-for') or '').split(',')[0].strip()
    ip = ip or (request.client.host if request.client else 'unknown')
    if not _login_ok(ip) or not _login_account_ok(username):
        raise HTTPException(429, 'Too many login attempts. Please wait before trying again.')
    _check_csrf(request, csrf_token)

    with connect() as connection:
        row = connection.execute(
            'SELECT * FROM admin_users WHERE username=? AND is_active=TRUE',
            (username,),
        ).fetchone()
        if not row or not verify_password(password, row['password_hash']):
            _record_login_failure(username)
            log.warning(
                'Failed admin login for username=%r from %s',
                username[:64],
                ip,
            )
            raise HTTPException(401, 'Invalid credentials')

        connection.execute(
            'UPDATE admin_users SET last_login_at=CURRENT_TIMESTAMP WHERE id=?',
            (row['id'],),
        )
        connection.commit()

    resp = RedirectResponse('/admin', 303)
    resp.set_cookie(
        _SESSION_COOKIE,
        make_session(row['id'], row['role'], row['auth_version']),
        httponly=True,
        samesite='strict',
        secure=_COOKIE_SECURE,
        path='/admin',
        max_age=28800,
    )
    _set_csrf(resp, _csrf_value(request))
    return resp


@app.post('/admin/logout')
def logout(request: Request):
    require(request, csrf=True)
    resp = RedirectResponse('/admin/login', 303)
    resp.delete_cookie(_SESSION_COOKIE, path='/admin')
    resp.delete_cookie(_CSRF_COOKIE, path='/admin')
    return resp


@app.get('/admin', response_class=HTMLResponse)
def admin(request: Request):
    require(request)
    return dashboard()


@app.post('/admin/api/imports')
def upload(request: Request, file: UploadFile = File(...)):
    current_user = require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    name = Path(file.filename or '').name
    if not name.lower().endswith('.pdf'):
        raise HTTPException(400, 'Only PDF files are accepted')

    job_key = 'IMPORT-' + uuid.uuid4().hex[:12].upper()
    tmp = IMPORTS / (job_key + '.upload')
    stored = None
    total = 0
    try:
        with open(tmp, 'wb') as output:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    raise HTTPException(413, 'PDF exceeds 50 MiB limit')
                output.write(chunk)

        stored = IMPORTS / (job_key + '.pdf')
        tmp.replace(stored)
        with connect() as connection:
            cursor = connection.execute(
                'INSERT INTO import_jobs(job_key,original_filename,stored_path,sha256,size_bytes,status,created_by) VALUES (?,?,?,?,?,?,?)',
                (
                    job_key,
                    name,
                    str(stored.relative_to(BASE)),
                    '',
                    total,
                    'RECEIVED',
                    current_user['uid'],
                ),
            )
            job_id = cursor.lastrowid
            event(connection, job_id, 'RECEIVED', 'File received', 0)
            connection.commit()
            run_preflight(connection, job_id, stored, name)
        return RedirectResponse(f'/admin/imports/{job_id}', 303)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        if stored is not None and stored.exists():
            stored.unlink()
        raise


@app.post('/admin/api/imports/{job_id}/process')
def process_job(request: Request, job_id: int):
    require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        job = connection.execute(
            'SELECT * FROM import_jobs WHERE id=?',
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if job['status'] != JobStatus.REVIEW_REQUIRED.value:
            raise HTTPException(409, f'Import is not ready for processing: {job["status"]}')
        if not job['data_type'] or not job['course_family'] or not job['year'] or not job['round']:
            raise HTTPException(
                409,
                'Source metadata is incomplete; identify year, round and course before processing',
            )

        path = BASE / job['stored_path']
        if not path.exists():
            raise HTTPException(404, 'Stored source PDF is missing')

        claimed = connection.execute(
            "UPDATE import_jobs SET status='EXTRACTING',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='REVIEW_REQUIRED'",
            (job_id,),
        ).rowcount
        if not claimed:
            raise HTTPException(409, 'Import is already being processed')
        connection.commit()

        try:
            result = process_import(
                connection,
                job_id,
                path,
                data_type=job['data_type'],
                family=job['course_family'],
                year=int(job['year']),
                round_name=job['round'],
                claimed=True,
            )
        except Exception:
            connection.execute(
                "UPDATE import_jobs SET status='FAILED',error_message='Processing failed',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (job_id,),
            )
            connection.commit()
            raise HTTPException(500, 'Import processing failed; see the job timeline for details')

        if not result['ok']:
            raise HTTPException(500, 'Import processing failed; see the job timeline for details')
        return result


@app.get('/admin/api/imports')
def imports(request: Request):
    require(request)
    with connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                'SELECT * FROM import_jobs ORDER BY id DESC LIMIT 100'
            )
        ]


@app.get('/admin/api/imports/{job_id}')
def detail(request: Request, job_id: int):
    require(request)
    with connect() as connection:
        job = connection.execute(
            'SELECT * FROM import_jobs WHERE id=?',
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        events = connection.execute(
            'SELECT * FROM import_events WHERE job_id=? ORDER BY id',
            (job_id,),
        ).fetchall()
        return {'job': dict(job), 'events': [dict(row) for row in events]}


@app.get('/admin/imports', response_class=HTMLResponse)
def import_center_page(request: Request):
    require(request)
    return import_center()


@app.get('/admin/imports/{job_id}', response_class=HTMLResponse)
def live(request: Request, job_id: int):
    require(request)
    return live_processing(job_id)

@app.get('/admin/review', response_class=HTMLResponse)
def review_center_page(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    return review_center()

@app.get('/admin/api/review')
def review_list(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    with connect() as c:
        rows=c.execute("""
            SELECT j.*,
                   (SELECT COUNT(*) FROM import_staging_records r WHERE r.job_id=j.id) AS staging_row_count,
                   (SELECT COUNT(*) FROM import_staging_records r WHERE r.job_id=j.id AND UPPER(COALESCE(r.validation_status,'')) <> 'VALID') AS validation_issue_count
            FROM import_jobs j
            WHERE j.status IN ('REVIEW_REQUIRED','COMMITTING')
            ORDER BY j.id DESC
        """).fetchall()
        return [dict(r) for r in rows]

@app.get('/admin/api/imports/{job_id}/review')
def review_detail(request: Request, job_id: int):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    with connect() as c:
        job=c.execute("SELECT * FROM import_jobs WHERE id=?",(job_id,)).fetchone()
        if not job: raise HTTPException(404,'Import not found')
        results=[dict(r) for r in c.execute("SELECT * FROM import_results WHERE job_id=? ORDER BY id",(job_id,))]
        rows=c.execute("SELECT id,result_type,source_file,source_page,normalized_json,validation_status,validation_message "
                       "FROM import_staging_records WHERE job_id=? ORDER BY id LIMIT 500",(job_id,)).fetchall()
        return {'job':dict(job),'results':results,'rows':[dict(r) for r in rows]}

@app.post('/admin/api/imports/{job_id}/approve')
async def approve(request: Request, job_id: int):
    u=require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER'},csrf=True)
    try: body=await request.json()
    except Exception: body={}
    notes=str(body.get('notes','')).strip()[:4000]
    with connect() as c:
        try: return approve_import(c,job_id,u['uid'],notes)
        except ValueError as e: raise HTTPException(409,str(e))

@app.post('/admin/api/imports/{job_id}/reject')
async def reject(request: Request, job_id: int):
    u=require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER'},csrf=True)
    try: body=await request.json()
    except Exception: body={}
    reason=str(body.get('reason','')).strip()[:4000]
    if not reason: raise HTTPException(400,'Rejection reason is required')
    with connect() as c:
        j=c.execute("SELECT * FROM import_jobs WHERE id=?",(job_id,)).fetchone()
        if not j: raise HTTPException(404,'Import not found')
        if j['status'] != JobStatus.REVIEW_REQUIRED.value:
            raise HTTPException(409,f"Import is not awaiting review: {j['status']}")
        c.execute("UPDATE import_jobs SET status='QUARANTINED',error_message=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(reason,job_id))
        event(c,job_id,'REJECT',f'Import rejected/quarantined: {reason}',100)
        sql=("INSERT INTO audit_log(actor_user_id,action,entity_type,entity_id,before_json,after_json,reason) "
             "VALUES (?,?,?,?,?,?,?)")
        c.execute(sql,(u['uid'],'REJECT_IMPORT','IMPORT',str(job_id),
                       json.dumps({'status':j['status']}),json.dumps({'status':'QUARANTINED'}),reason))
        c.commit()
        return {'ok':True,'job_id':job_id,'status':'QUARANTINED'}

@app.post('/admin/api/releases/{release_id}/rollback')
async def rollback(request: Request, release_id: int):
    u=require(request, {'SUPER_ADMIN'},csrf=True)
    try: body=await request.json()
    except Exception: body={}
    reason=str(body.get('reason','')).strip()[:4000]
    if not reason: raise HTTPException(400,'Rollback reason is required')
    with connect() as c:
        try: return rollback_release(c,release_id,u['uid'],reason)
        except ValueError as e: raise HTTPException(409,str(e))


@app.post('/admin/api/releases/{release_id}/publish')
def publish(request: Request, release_id: int):
    u=require(request, {'SUPER_ADMIN','DATA_ADMIN'},csrf=True)
    with connect() as c:
        rel=c.execute('SELECT * FROM data_releases WHERE id=?',(release_id,)).fetchone()
        if not rel: raise HTTPException(404,'Release not found')
        if rel['approved_by'] != u['uid'] and u['role'] != 'SUPER_ADMIN': raise HTTPException(403,'Only the approving admin or a super admin can publish this release')
        try: return publish_release(c, int(rel['source_job_id']), release_id)
        except ValueError as e: raise HTTPException(409,str(e))
        except Exception:
            log.exception('Release publish failed: release_id=%s', release_id)
            raise HTTPException(500,'Release publication failed; check the release timeline or server logs')

@app.get('/admin/releases', response_class=HTMLResponse)
def releases_page_route(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    return releases_page()

@app.get('/admin/api/releases')
def releases_api(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    with connect() as c: return [dict(r) for r in c.execute("SELECT * FROM data_releases ORDER BY id DESC LIMIT 100")]

@app.get('/admin/health', response_class=HTMLResponse)
def health_page_route(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    return health_page()

@app.get('/admin/api/overview')
def overview_api(request: Request):
    require(request)
    with connect() as c:
        imports_today=c.execute("SELECT COUNT(*) n FROM import_jobs WHERE created_at >= CURRENT_DATE AND created_at < CURRENT_DATE + INTERVAL '1 day'").fetchone()['n']
        pending=c.execute("SELECT COUNT(*) n FROM import_jobs WHERE status='REVIEW_REQUIRED'").fetchone()['n']
        production=sum(c.execute(f'SELECT COUNT(*) n FROM {t}').fetchone()['n'] for t in ['institutes','programs','cutoffs','seats'])
        storage_ok=IMPORTS.exists() and IMPORTS.is_dir()
        site_ok=SITE.exists() and (SITE/'index.html').exists()
        return {'imports_today':imports_today,'pending_review':pending,'production_rows':production,'health':{'ok':storage_ok and site_ok,'application':True,'database':True,'storage':storage_ok,'site':site_ok}}

@app.get('/admin/api/health')
def health_api(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    with connect() as c:
        counts={t:c.execute(f'SELECT COUNT(*) n FROM {t}').fetchone()['n'] for t in ['institutes','programs','cutoffs','seats','import_jobs','data_releases','audit_log']}
        latest=c.execute("SELECT release_key,status,published_at,verified_at FROM data_releases ORDER BY id DESC LIMIT 1").fetchone()
        return {'ok':True,'counts':counts,'runtime':{'site_exists':SITE.exists(),'latest_release':dict(latest) if latest else None}}

@app.get('/admin/feedback', response_class=HTMLResponse)
def feedback_page_route(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    with connect() as c:
        rows=[dict(r) for r in c.execute('SELECT id,rating,message,page,status,created_at FROM public_feedback ORDER BY id DESC LIMIT 500')]
    return feedback_page(rows)

@app.get('/admin/api/feedback')
def feedback_api(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    with connect() as c:
        return [dict(r) for r in c.execute('SELECT id,rating,message,page,status,created_at FROM public_feedback ORDER BY id DESC LIMIT 500')]

@app.post('/admin/api/feedback/{feedback_id}/status')
async def feedback_status(request: Request, feedback_id: int):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER'}, csrf=True)
    try: body=await request.json()
    except Exception: body={}
    status=str(body.get('status','')).upper()
    if status not in {'NEW','REVIEWED','RESOLVED','SPAM'}:
        raise HTTPException(400,'Invalid feedback status')
    with connect() as c:
        row=c.execute('SELECT id,status FROM public_feedback WHERE id=?',(feedback_id,)).fetchone()
        if not row: raise HTTPException(404,'Feedback not found')
        c.execute('UPDATE public_feedback SET status=? WHERE id=?',(status,feedback_id))
        c.execute("INSERT INTO audit_log(actor_user_id,action,entity_type,entity_id,before_json,after_json) VALUES (?,?,?,?,?,?)",
                  (user(request)['uid'],'FEEDBACK_STATUS','FEEDBACK',str(feedback_id),json.dumps({'status':row['status']}),json.dumps({'status':status})))
        c.commit()
    return {'ok':True,'status':status}


@app.get('/admin/resolver', response_class=HTMLResponse)
def resolver_page_route(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER'})
    with connect() as c: rows=[dict(r) for r in c.execute('SELECT * FROM college_website_resolver ORDER BY LOWER(institution_name) LIMIT 5000')]
    return resolver_page(rows)

@app.get('/admin/api/resolver')
def resolver_api(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER'})
    with connect() as c: return [dict(r) for r in c.execute('SELECT * FROM college_website_resolver ORDER BY LOWER(institution_name) LIMIT 5000')]

@app.post('/admin/api/resolver/seed')
def resolver_seed(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        count = seed_from_contacts(connection)
        connection.commit()
        return {'ok': True, 'count': count}

@app.post('/admin/api/resolver/github-seed')
def resolver_github_seed(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN'}, csrf=True)
    with connect() as c:
        try:
            count = sync_github_india(c)
            c.commit()
            return {'ok': True, 'count': count, 'source': 'github_india_2021'}
        except Exception:
            c.rollback()
            raise HTTPException(502, 'GitHub seed source could not be synchronized')

@app.post('/admin/api/resolver/find')
async def resolver_find(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN'}, csrf=True)
    try: body=await request.json()
    except Exception: body={}
    ids=[str(x).strip() for x in body.get('ids',[]) if str(x).strip()][:25]
    if not ids: raise HTTPException(400,'No colleges selected')
    results=[]
    with connect() as c:
        for code in ids:
            row=c.execute('SELECT * FROM college_website_resolver WHERE institution_code=?',(code,)).fetchone()
            if not row: continue
            r = dict(row)
            candidate = r.get('website')
            v = verify_url(candidate, r['institution_name']) if candidate else {'ok': False}
            if v.get('ok') and v.get('match_score',0)>=0.15:
                c.execute('UPDATE college_website_resolver SET website=?,status=?,source=?,verification_note=?,last_checked_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE institution_code=?',(v['url'],'VERIFIED',r.get('source') or 'reference_csv',v['note'],code))
                c.execute(
                    "UPDATE institutes SET website=?, website_source=?, verified_at=CURRENT_TIMESTAMP WHERE institution_code=?",
                    (v['url'], r.get('source') or 'reference_csv', code),
                )
                results.append({
                    'institution_code': code,
                    'institution_name': r['institution_name'],
                    'city': r.get('city'),
                    'website': v['url'],
                    'status': 'VERIFIED',
                    'note': v['note'],
                })
                continue
            try:
                ai, _ = gemini_find(r['institution_name'], r.get('city'))
                url = ai.get('official_url')
                city = str(ai.get('city')).strip() if ai.get('city') else r.get('city')
                address = str(ai.get('address')).strip() if ai.get('address') else None
                v = (
                    verify_url(url, r['institution_name'])
                    if url
                    else {'ok': False, 'url': None, 'note': 'Gemini returned no official URL'}
                )
                status = (
                    'VERIFIED'
                    if v.get('ok') and v.get('match_score', 0) >= 0.15
                    else ('NEEDS_REVIEW' if v.get('ok') else 'FAILED')
                )
                note = (ai.get('note') or '') + ' ' + v.get('note', '')
                c.execute('UPDATE college_website_resolver SET city=?,website=?,address=?,status=?,source=?,source_url=?,verification_note=?,last_checked_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE institution_code=?',(city,v.get('url') or url,address,status,'gemini_google_search',v.get('url') or url,note,code))
                if city or address or v.get('url'):
                    c.execute('UPDATE institutes SET city=COALESCE(?,city), address=COALESCE(?,address), website=COALESCE(?,website), city_source=CASE WHEN ? IS NOT NULL THEN ? ELSE city_source END, address_source=CASE WHEN ? IS NOT NULL THEN ? ELSE address_source END, website_source=CASE WHEN ? IS NOT NULL THEN ? ELSE website_source END, verified_at=CURRENT_TIMESTAMP WHERE institution_code=?',(city,address,v.get('url') or url,city,'gemini_google_search',address,'gemini_google_search',v.get('url') or url,'gemini_google_search',code))
                results.append({'institution_code':code,'institution_name':r['institution_name'],'city':city,'address':address,'website':v.get('url') or url,'status':status,'note':note})
            except Exception as e:
                c.execute(
                    'UPDATE college_website_resolver SET status=?,verification_note=?,last_checked_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE institution_code=?',
                    ('FAILED', str(e)[:500], code),
                )
                results.append({
                    'institution_code': code,
                    'institution_name': r['institution_name'],
                    'website': candidate,
                    'status': 'FAILED',
                    'note': str(e)[:500],
                })
        c.commit()
    return {'ok':True,'results':results}

@app.get('/admin/audit', response_class=HTMLResponse)
def audit_page_route(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    with connect() as c: rows=[dict(r) for r in c.execute('SELECT a.*,u.username FROM audit_log a LEFT JOIN admin_users u ON u.id=a.actor_user_id ORDER BY a.id DESC LIMIT 200')]
    return audit_page(rows)
