import os,uuid,json,time,re,secrets,logging,sys,subprocess,threading,hashlib,csv
from pathlib import Path
from fastapi import FastAPI,Request,UploadFile,File,HTTPException,Form,BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse,RedirectResponse,JSONResponse,FileResponse,Response
from .admin.db import connect,init_admin_schema,event
from .admin.security import verify_password,make_session,read_session,hash_password
from .admin.network import client_ip
from .admin.pipeline import run_preflight,MAX_PDF_BYTES,sha256_file
from .admin.source_storage import store_source_pdf, materialize_source, delete_source, storage_backend, StorageNotConfigured
from .admin.processing import process_import,approve_import,rollback_release,purge_rolled_back_release,revalidate_legacy_mh_staging
from .admin.publishing import publish_release
from .admin.migrations import ensure_part4_schema
from .admin.state import JobStatus
from .admin_ui import dashboard, import_center, review_center, releases_page, health_page, audit_page, feedback_page, resolver_page, derived_data
from .admin.resolver import (seed_from_contacts, sync_github_india, verify_url, gemini_find,
                              gemini_verify_candidate, _same_site, sync_institutes_to_resolver,
                              resolve_import_job)
from .api import router as public_api_router, invalidate_public_caches
BASE = Path(__file__).resolve().parent.parent
SITE = BASE / 'site'
IMPORTS = BASE / 'data' / 'imports'
IMPORTS.mkdir(parents=True, exist_ok=True)
def _recover_interrupted_imports():
    """Requeue jobs whose database lease expired; never steal a live worker's job."""
    with connect() as connection:
        rows = connection.execute(
            "SELECT id,stored_path FROM import_jobs WHERE status IN ('EXTRACTING','NORMALIZING','VALIDATING','COMPARING') AND (worker_lease_until IS NULL OR worker_lease_until < CURRENT_TIMESTAMP) ORDER BY id"
        ).fetchall()
        for row in rows:
            job_id = int(row['id'])
            source = str(row['stored_path'] or '')
            source_exists = source.startswith('s3://') or (
                not source.startswith('local://') and (BASE / source).is_file()
            )
            connection.execute('DELETE FROM import_staging_records WHERE job_id=?', (job_id,))
            connection.execute('DELETE FROM import_results WHERE job_id=?', (job_id,))
            if source_exists:
                connection.execute(
                    "UPDATE import_jobs SET status='QUEUED',worker_id=NULL,worker_lease_until=NULL,current_page=0,current_chunk=0,error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (job_id,),
                )
                event(connection, job_id, 'RECOVERED', 'Worker lease expired; requeued from retained source PDF', 0)
            else:
                connection.execute(
                    "UPDATE import_jobs SET status='FAILED',worker_id=NULL,worker_lease_until=NULL,error_message=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    ('Worker stopped and the source PDF is missing. Re-upload the original PDF.', job_id),
                )
                event(connection, job_id, 'RECOVERY_FAILED', 'Source PDF missing after worker lease expired; upload again', None)
        connection.commit()


def _heartbeat_import_job(job_id: int, stop: threading.Event):
    """Renew the DB lease so another server cannot claim a live extraction."""
    while not stop.wait(20):
        try:
            with connect() as connection:
                connection.execute(
                    "UPDATE import_jobs SET worker_lease_until=CURRENT_TIMESTAMP + INTERVAL '2 minutes' WHERE id=? AND worker_id=? AND status IN ('EXTRACTING','PAUSED','NORMALIZING','VALIDATING','COMPARING','CANCELLED')",
                    (job_id, _WORKER_ID),
                )
                connection.commit()
        except Exception:
            log.exception('Could not renew import worker lease: job_id=%s', job_id)


def _import_queue_loop():
    """Poll the durable PostgreSQL queue; a browser request does not own the job."""
    global _ACTIVE_IMPORT_JOB_ID, _LAST_QUEUE_RECOVERY
    while True:
        job_id = None
        heartbeat_stop = None
        heartbeat_thread = None
        try:
            if time.monotonic() - _LAST_QUEUE_RECOVERY > 30:
                _recover_interrupted_imports()
                _LAST_QUEUE_RECOVERY = time.monotonic()
            with connect() as connection:
                row = connection.execute(
                    "SELECT id FROM import_jobs WHERE status='QUEUED' ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED"
                ).fetchone()
                if row:
                    candidate = int(row['id'])
                    claimed = connection.execute(
                        "UPDATE import_jobs SET status='EXTRACTING',worker_id=?,worker_lease_until=CURRENT_TIMESTAMP + INTERVAL '2 minutes',error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='QUEUED'",
                        (_WORKER_ID, candidate),
                    ).rowcount
                    if claimed:
                        job_id = candidate
                        event(connection, job_id, 'WORKER_CLAIMED', 'Server worker claimed the queued PDF', 42)
                connection.commit()
            if job_id is None:
                time.sleep(2)
                continue
            log.info('Import queue worker claimed job_id=%s worker_id=%s', job_id, _WORKER_ID)
            _ACTIVE_IMPORT_JOB_ID = job_id
            heartbeat_stop = threading.Event()
            heartbeat_thread = threading.Thread(
                target=_heartbeat_import_job, args=(job_id, heartbeat_stop),
                daemon=True, name=f'import-heartbeat-{job_id}',
            )
            heartbeat_thread.start()
            with _IMPORT_PROCESS_LOCK:
                _process_import_background_locked(job_id)
        except Exception:
            log.exception('Import queue worker iteration failed')
            time.sleep(3)
        finally:
            if heartbeat_stop:
                heartbeat_stop.set()
            if heartbeat_thread:
                heartbeat_thread.join(timeout=2)
            if job_id is not None:
                try:
                    with connect() as connection:
                        connection.execute(
                            'UPDATE import_jobs SET worker_id=NULL,worker_lease_until=NULL WHERE id=? AND worker_id=?',
                            (job_id, _WORKER_ID),
                        )
                        connection.commit()
                except Exception:
                    log.exception('Could not release import worker lease: job_id=%s', job_id)
                _ACTIVE_IMPORT_JOB_ID = None


@asynccontextmanager
async def lifespan(_app):
    # Do database migrations/recovery in the background. During a rolling
    # deploy an older instance can still hold a transaction, and PostgreSQL
    # DDL can otherwise block Uvicorn startup long enough for Render's port
    # scanner to declare the new instance unhealthy.
    def _startup_database_maintenance():
        try:
            init_admin_schema()
            ensure_part4_schema()

            with connect() as c:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS site_analytics_events (
                        id BIGSERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        event_name TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                c.execute("CREATE INDEX IF NOT EXISTS idx_site_analytics_created ON site_analytics_events(created_at)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_site_analytics_event ON site_analytics_events(event_name,created_at)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_cutoffs_program_percentile_inst ON cutoffs(program_id, percentile, institution_code)")
                c.execute("""
                    CREATE TABLE IF NOT EXISTS admin_active_lock (
                        user_id BIGINT PRIMARY KEY,
                        client_id TEXT NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                c.commit()

            # One-time recovery hook used to rebuild all derived public data
            # after schema/query optimizations. The flag is removed after the
            # successful deployment so normal restarts never rebuild production.
            if os.getenv('REBUILD_DERIVED_ON_START') == '1':
                script = BASE / 'scripts' / 'refresh_derived_data.py'
                build_env = os.environ.copy()
                build_env['PYTHONPATH'] = str(BASE) + (
                    os.pathsep + build_env['PYTHONPATH']
                    if build_env.get('PYTHONPATH') else ''
                )
                subprocess.run(
                    [sys.executable, str(script)],
                    cwd=str(BASE),
                    env=build_env,
                    check=True,
                    timeout=1700,
                )
                log.info('One-time full derived-data rebuild completed')
        except Exception:
            log.exception('Database startup maintenance failed')
            return

        # STAGED imports must remain pending until an administrator explicitly
        # approves them in the Review Center. A service restart is not approval.
        log.info('Startup maintenance will leave STAGED imports pending')

        # Start the durable import worker before the independent college website
        # resolver sync. That sync can take time on a cold deployment; it must
        # never delay PDF jobs from being claimed and processed.
        try:
            _recover_interrupted_imports()
            threading.Thread(target=_import_queue_loop, daemon=True,
                             name='durable-import-queue').start()
            log.info('Durable import queue worker started before resolver sync')
        except Exception:
            log.exception('Import queue recovery/startup failed')

        # Rebuild the derived website-resolver view after every deploy so an
        # admin page visit is never required to make current CAP colleges appear.
        try:
            with connect() as c:
                resolver_count = sync_institutes_to_resolver(c)
            log.info('Startup resolver sync completed: colleges=%s', resolver_count)
        except Exception:
            log.exception('Startup resolver sync failed')

    threading.Thread(target=_startup_database_maintenance, daemon=True,
                     name='database-startup-maintenance').start()
    yield

app=FastAPI(title='CET CAP Admin API', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get('/healthz', include_in_schema=False)
def healthz():
    """Cheap liveness endpoint for the hosting platform."""
    return {'ok': True}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cetfind.onrender.com"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)
app.include_router(public_api_router)
log=logging.getLogger('cet-cap-admin')
# PDF extraction/normalization is memory-heavy on the free Render instance.
# Keep a single import processor active at a time even if multiple upload
# requests or background tasks arrive together.
_IMPORT_PROCESS_LOCK = threading.Lock()
_ACTIVE_IMPORT_JOB_ID = None
_WORKER_ID = f"{os.getenv('HOSTNAME', 'capfind')}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
_LAST_QUEUE_RECOVERY = 0.0
_PRODUCTION=os.getenv('CET_ENV','production').lower() == 'production'
_COOKIE_SECURE=os.getenv('CET_ADMIN_COOKIE_SECURE','1' if _PRODUCTION else '0') == '1'
_CSRF_COOKIE='cet_admin_csrf'
_SESSION_COOKIE='cet_admin_session'
# Equal-cost password verification for unknown usernames reduces account enumeration by timing.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


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
_LOGIN_WINDOW = 60.0
_LOGIN_MAX_KEYS = 5000

def _login_ok(ip: str) -> bool:
    now = time.monotonic()
    # Expire old keys as well as old hits so spoofed/rotating source addresses
    # cannot grow this process-local limiter without bound.
    if len(_LOGIN_RATE) >= _LOGIN_MAX_KEYS and ip not in _LOGIN_RATE:
        cutoff = now - _LOGIN_WINDOW
        for key in list(_LOGIN_RATE):
            fresh = [stamp for stamp in _LOGIN_RATE[key] if stamp > cutoff]
            if fresh:
                _LOGIN_RATE[key] = fresh
            else:
                del _LOGIN_RATE[key]
        # Under a sustained high-cardinality flood, cap memory even if every
        # key remains active. Eviction only affects throttling, not accounts.
        while len(_LOGIN_RATE) >= _LOGIN_MAX_KEYS and _LOGIN_RATE:
            _LOGIN_RATE.pop(next(iter(_LOGIN_RATE)))
    hits = [stamp for stamp in _LOGIN_RATE.get(ip, []) if now - stamp < _LOGIN_WINDOW]
    if len(hits) >= _LOGIN_LIMIT:
        _LOGIN_RATE[ip] = hits
        return False
    hits.append(now)
    _LOGIN_RATE[ip] = hits
    return True

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
    # The canonical frontend is hosted by the dedicated static-site service.
    # Keep this backend host API/admin-only and prevent a stale duplicate homepage.
    return RedirectResponse('https://cetfind.onrender.com/', status_code=307)

@app.get('/privacy.html', include_in_schema=False)
def public_privacy():
    return RedirectResponse('https://cetfind.onrender.com/privacy.html', status_code=307)

@app.get('/knowledge.html', include_in_schema=False)
def public_knowledge():
    return RedirectResponse('https://cetfind.onrender.com/knowledge.html', status_code=307)

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
    ip=client_ip(request)
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

@app.post('/api/analytics/event')
async def analytics_event(request: Request):
    """Store anonymous website usage events without IPs or personal details."""
    try:
        raw = await request.body()
        body = json.loads(raw.decode('utf-8'))
    except Exception:
        raise HTTPException(400, 'Invalid analytics payload')
    if not isinstance(body, dict):
        raise HTTPException(400, 'Invalid analytics payload')
    event_name = str(body.get('event', '')).strip().lower()[:80]
    session_id = re.sub(r'[^a-zA-Z0-9_-]', '', str(body.get('session_id', '')))[:80]
    allowed = {'page_view', 'search_started', 'search_completed', 'college_opened',
               'college_website_clicked', 'seat_matrix_opened', 'trend_opened'}
    if event_name not in allowed or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', session_id):
        raise HTTPException(400, 'Invalid analytics event')
    with connect() as c:
        c.execute('INSERT INTO site_analytics_events(session_id,event_name) VALUES (?,?)',
                  (session_id, event_name))
        c.commit()
    return {'ok': True}

@app.get('/admin/api/analytics/summary')
def analytics_summary(request: Request, days: int = 30):
    require(request)
    days = max(1, min(int(days or 30), 90))
    with connect() as c:
        totals = c.execute("""
            SELECT COUNT(DISTINCT session_id) AS visitors,
                   COUNT(*) FILTER (WHERE event_name='search_started') AS searches,
                   COUNT(*) FILTER (WHERE event_name='college_opened') AS college_opens,
                   COUNT(*) FILTER (WHERE event_name='college_website_clicked') AS website_clicks
            FROM site_analytics_events
            WHERE created_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 day')
        """, (days,)).fetchone()
    return {'days': days, 'totals': dict(totals) if totals else {}}

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
    except Exception as exc:
        # A transient database/pool failure is not an invalid login session.
        # Returning None here made require() emit HTTP 401 and forced the UI
        # to redirect the administrator to login during pool exhaustion.
        log.exception('Session validation temporarily unavailable')
        raise HTTPException(status_code=503, detail='Admin session validation temporarily unavailable') from exc


_ADMIN_LOCK_TTL_SECONDS = 45
_ADMIN_TAB_HEADER = 'x-admin-client-id'


def _admin_tab_id(request: Request) -> str | None:
    value = (request.headers.get(_ADMIN_TAB_HEADER) or '').strip()
    return value if re.fullmatch(r'[A-Za-z0-9_-]{20,128}', value) else None


def _acquire_admin_lock(connection, user_id: int, client_id: str):
    return connection.execute(
        """INSERT INTO admin_active_lock(user_id,client_id,updated_at)
           VALUES (?,?,CURRENT_TIMESTAMP)
           ON CONFLICT (user_id) DO UPDATE
           SET client_id=EXCLUDED.client_id, updated_at=CURRENT_TIMESTAMP
           WHERE admin_active_lock.client_id=EXCLUDED.client_id
              OR admin_active_lock.updated_at < CURRENT_TIMESTAMP - INTERVAL '45 seconds'
           RETURNING client_id""",
        (user_id, client_id),
    ).fetchone()


def require(request, roles=None, csrf=False, csrf_value=None, check_tab=True):
    current_user = user(request)
    if not current_user:
        # Browser-facing admin pages should go back to the login screen instead
        # of exposing FastAPI's raw JSON 401 document (which Brave displays as
        # a "Pretty print" page). Keep API endpoints machine-readable.
        if request.url.path.startswith('/admin/api'):
            raise HTTPException(401, 'Authentication required')
        raise HTTPException(303, 'Authentication required', headers={'Location': '/admin/login'})
    if check_tab and (request.url.path.startswith('/admin/api/') or request.url.path == '/admin/logout'):
        client_id = _admin_tab_id(request)
        if not client_id:
            raise HTTPException(409, 'Admin tab identity missing. Please sign in again.')
        with connect() as connection:
            lock = connection.execute(
                "SELECT client_id FROM admin_active_lock WHERE user_id=? AND updated_at >= CURRENT_TIMESTAMP - INTERVAL '45 seconds'",
                (current_user['uid'],),
            ).fetchone()
        if not lock or lock['client_id'] != client_id:
            raise HTTPException(409, 'Admin panel is active in another tab. Use the tab that signed in.')
    if roles and current_user['role'] not in roles:
        raise HTTPException(403, 'Insufficient role')
    if csrf:
        _check_csrf(request, csrf_value)
    return current_user


@app.get('/admin/login', response_class=HTMLResponse)
def login(request: Request):
    token = _csrf_value(request)
    error = ('<p style="color:#b42333;font-weight:600">Invalid username or password.</p>' if request.query_params.get('error') == '1' else
             '<p style="color:#b42333;font-weight:600">Admin panel is already active in another tab. Close it or wait for its lock to expire.</p>' if request.query_params.get('locked') == '1' else
             '<p style="color:#b42333;font-weight:600">The server/database is temporarily unavailable. Wait a minute and try again; your password may be correct.</p>' if request.query_params.get('server') == '1' else
             '<p style="color:#b42333;font-weight:600">Too many login attempts. Wait 60 seconds before trying again.</p>' if request.query_params.get('throttled') == '1' else '')
    resp = HTMLResponse(
        f'<h1>CET CAP Admin</h1>{error}<form method="post">'
        f'<input type="hidden" name="csrf_token" value="{token}">'
        '<input name="username" autocomplete="username">'
        '<input name="password" type="password" autocomplete="current-password">'
        '<button type="submit">Sign in</button></form>'
        '<script>'
        "const f=document.querySelector('form');"
        "f.addEventListener('submit',async e=>{"
        "e.preventDefault();"
        "const b=f.querySelector('button');"
        "const TAB_KEY='cet-cap-admin-tab-id-v1';let tabId=sessionStorage.getItem(TAB_KEY);"
        "if(!tabId){tabId=crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random().toString(36).slice(2);sessionStorage.setItem(TAB_KEY,tabId);}"
        "b.disabled=true;b.textContent='Signing in…';"
        "try{const r=await fetch('/admin/login',{method:'POST',headers:{'X-Admin-Client-ID':tabId},body:new FormData(f),redirect:'follow'});"
        "if(r.ok && new URL(r.url).pathname==='/admin'){"
        "sessionStorage.setItem('cet-cap-admin-auth-v1','1');window.location.replace('/admin');return;}"
        "sessionStorage.removeItem('cet-cap-admin-auth-v1');const u=new URL(r.url);"
        "if(r.status===429){window.location.replace('/admin/login?throttled=1');return;}"
        "if(r.status>=500){window.location.replace('/admin/login?server=1');return;}"
        "window.location.replace(u.searchParams.get('locked')==='1'?'/admin/login?locked=1':'/admin/login?error=1');"
        "}catch(_){sessionStorage.removeItem('cet-cap-admin-auth-v1');window.location.replace('/admin/login?server=1')}"
        "});"
        "</script>"
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
    ip = client_ip(request)
    if not _login_ok(ip):
        raise HTTPException(429, 'Too many login attempts. Please wait before trying again.')
    _check_csrf(request, csrf_token)
    client_id = _admin_tab_id(request)
    if not client_id:
        raise HTTPException(400, 'Admin tab identity missing. Refresh the login page and try again.')

    with connect() as connection:
        row = connection.execute(
            'SELECT * FROM admin_users WHERE username=? AND is_active=TRUE',
            (username,),
        ).fetchone()
        # Perform the same expensive password-hash operation for unknown users.
        # This reduces timing differences that could reveal valid usernames.
        password_ok = verify_password(password, row['password_hash']) if row else verify_password(password, _DUMMY_PASSWORD_HASH)
        if not row or not password_ok:
            log.warning(
                'Failed admin login for username=%r from %s',
                username[:64],
                ip,
            )
            return RedirectResponse('/admin/login?error=1', 303)

        lock = _acquire_admin_lock(connection, int(row['id']), client_id)
        if not lock:
            return RedirectResponse('/admin/login?locked=1', 303)

        # A successful login starts a fresh authentication session. Bumping
        # auth_version invalidates every older browser session for this admin.
        connection.execute(
            'UPDATE admin_users SET last_login_at=CURRENT_TIMESTAMP, auth_version=auth_version+1 WHERE id=?',
            (row['id'],),
        )
        connection.commit()
        fresh_auth_version = int(row['auth_version']) + 1

    resp = RedirectResponse('/admin', 303)
    resp.set_cookie(
        _SESSION_COOKIE,
        make_session(row['id'], row['role'], fresh_auth_version),
        httponly=True,
        samesite='strict',
        secure=_COOKIE_SECURE,
        path='/admin',
        max_age=28800,
    )
    _set_csrf(resp, _csrf_value(request))
    return resp


@app.post('/admin/api/admin-lock/acquire')
def admin_lock_acquire(request: Request):
    current = require(request, csrf=True, check_tab=False)
    client_id = _admin_tab_id(request)
    if not client_id:
        raise HTTPException(409, 'Admin tab identity missing')
    with connect() as connection:
        lock = _acquire_admin_lock(connection, current['uid'], client_id)
        if not lock:
            raise HTTPException(409, 'Admin panel is active in another tab')
        connection.commit()
    return {'ok': True}


@app.post('/admin/api/admin-lock/release')
def admin_lock_release(request: Request):
    current = require(request, csrf=True, check_tab=False)
    client_id = _admin_tab_id(request)
    if not client_id:
        raise HTTPException(409, 'Admin tab identity missing')
    with connect() as connection:
        connection.execute(
            'DELETE FROM admin_active_lock WHERE user_id=? AND client_id=?',
            (current['uid'], client_id),
        )
        connection.commit()
    return {'ok': True}


@app.post('/admin/api/admin-lock/heartbeat')
def admin_lock_heartbeat(request: Request):
    current = require(request, csrf=True, check_tab=False)
    client_id = _admin_tab_id(request)
    if not client_id:
        raise HTTPException(409, 'Admin tab identity missing')
    with connect() as connection:
        row = connection.execute(
            'UPDATE admin_active_lock SET updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND client_id=? RETURNING client_id',
            (current['uid'], client_id),
        ).fetchone()
        if not row:
            raise HTTPException(409, 'Admin panel is active in another tab')
        connection.commit()
    return {'ok': True}


@app.post('/admin/logout')
def logout(request: Request):
    current = require(request, csrf=True)
    client_id = _admin_tab_id(request)
    if not client_id:
        raise HTTPException(409, 'Admin tab identity missing')
    with connect() as connection:
        connection.execute('DELETE FROM admin_active_lock WHERE user_id=? AND client_id=?', (current['uid'], client_id))
        connection.commit()
    resp = RedirectResponse('/admin/login', 303)
    resp.delete_cookie(_SESSION_COOKIE, path='/admin')
    resp.delete_cookie(_CSRF_COOKIE, path='/admin')
    return resp


@app.get('/admin', response_class=HTMLResponse)
def admin(request: Request):
    require(request)
    return dashboard()


def _run_derived_data_build(job_id: int, course_family: str | None):
    try:
        with connect() as connection:
            connection.execute(
                "UPDATE derived_data_build_jobs SET status='RUNNING',progress=5,message='Starting database-side calculation',started_at=CURRENT_TIMESTAMP WHERE id=?",
                (job_id,),
            )
            connection.commit()
        script = BASE / 'scripts' / 'refresh_derived_data.py'
        cmd = [sys.executable, str(script), '--job-id', str(job_id)]
        if course_family:
            cmd += ['--course', course_family]
        build_env = os.environ.copy()
        existing_pythonpath = build_env.get('PYTHONPATH', '')
        build_env['PYTHONPATH'] = str(BASE) + (os.pathsep + existing_pythonpath if existing_pythonpath else '')
        subprocess.run(
            cmd,
            cwd=str(BASE),
            env=build_env,
            check=True,
            stdout=None,
            stderr=None,
            text=True,
            timeout=1800,
        )
        with connect() as connection:
            connection.execute(
                "UPDATE derived_data_build_jobs SET status='COMPLETED',progress=100,message='Graph, category and seat-matrix data is ready',finished_at=CURRENT_TIMESTAMP WHERE id=?",
                (job_id,),
            )
            connection.commit()
    except Exception as exc:
        log.exception('Derived data build failed: job_id=%s', job_id)
        with connect() as connection:
            connection.execute(
                "UPDATE derived_data_build_jobs SET status='FAILED',progress=100,message=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",
                (str(exc)[-4000:], job_id),
            )
            connection.commit()


@app.get('/admin/derived-data', response_class=HTMLResponse)
def derived_data_page(request: Request):
    require(request, {'SUPER_ADMIN', 'DATA_ADMIN'})
    return derived_data()


@app.post('/admin/api/derived-data/build')
def start_derived_data_build(request: Request, background_tasks: BackgroundTasks, course: str | None = Form(None)):
    current_user = require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    course = (course or '').strip() or None
    with connect() as connection:
        active = connection.execute(
            "SELECT id FROM derived_data_build_jobs WHERE status IN ('QUEUED','RUNNING') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if active:
            raise HTTPException(409, f'Derived data build #{active["id"]} is already running')
        if course:
            exists = connection.execute(
                "SELECT 1 FROM programs WHERE program_family=? LIMIT 1", (course,)
            ).fetchone()
            if not exists:
                raise HTTPException(400, f'Unknown course family: {course}')
        row = connection.execute(
            "INSERT INTO derived_data_build_jobs(course_family,status,progress,message,created_by) VALUES (?,?,?,?,?) RETURNING id",
            (course, 'QUEUED', 0, 'Queued by admin', current_user['uid']),
        ).fetchone()
        job_id = int(row['id'])
        connection.commit()
    background_tasks.add_task(_run_derived_data_build, job_id, course)
    return JSONResponse(status_code=202, content={"ok": True, "job_id": job_id, "status": "QUEUED"})


@app.post('/admin/api/derived-data/retry/{job_id}')
def retry_derived_data_build(job_id: int, request: Request, background_tasks: BackgroundTasks):
    current_user = require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        job = connection.execute(
            "SELECT id,course_family,status FROM derived_data_build_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(404, 'Build job not found')
        if str(job['status']).upper() not in {'FAILED', 'CANCELLED'}:
            raise HTTPException(409, 'Only failed or cancelled builds can be retried')
        active = connection.execute(
            "SELECT id FROM derived_data_build_jobs WHERE status IN ('QUEUED','RUNNING') LIMIT 1"
        ).fetchone()
        if active:
            raise HTTPException(409, f'Derived data build #{active["id"]} is already running')
        row = connection.execute(
            "INSERT INTO derived_data_build_jobs(course_family,status,progress,message,created_by) VALUES (?,?,?,?,?) RETURNING id",
            (job['course_family'], 'QUEUED', 0, f'Retry of build #{job_id}', current_user['uid']),
        ).fetchone()
        new_id = int(row['id'])
        connection.commit()
    background_tasks.add_task(_run_derived_data_build, new_id, job['course_family'])
    return JSONResponse(status_code=202, content={"ok": True, "job_id": new_id, "status": "QUEUED"})


@app.delete('/admin/api/derived-data/{job_id}')
def delete_derived_data_build(job_id: int, request: Request):
    require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        job = connection.execute(
            "SELECT id,status FROM derived_data_build_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(404, 'Build job not found')
        if str(job['status']).upper() in {'QUEUED', 'RUNNING'}:
            raise HTTPException(409, 'A running build cannot be deleted')
        connection.execute("DELETE FROM derived_data_build_jobs WHERE id=?", (job_id,))
        connection.commit()
    return {"ok": True}


@app.get('/admin/api/derived-data/status')
def derived_data_status(request: Request):
    require(request, {'SUPER_ADMIN', 'DATA_ADMIN'})
    with connect() as connection:
        rows = connection.execute(
            "SELECT id,course_family,status,progress,message,started_at,finished_at,created_at FROM derived_data_build_jobs ORDER BY id DESC LIMIT 10"
        ).fetchall()
        courses = connection.execute(
            "SELECT DISTINCT program_family FROM programs WHERE program_family IS NOT NULL ORDER BY program_family"
        ).fetchall()
    return {
        "jobs": [dict(row) for row in rows],
        "courses": [str(row['program_family']) for row in courses],
    }


LOCAL_ARTIFACT_MAX_BYTES = 150 * 1024 * 1024
LOCAL_WORKER_FAMILIES = {'BCA', 'BBA', 'MBA', 'MCA'}
LOCAL_WORKER_ROUNDS = {'C1', 'C2', 'C3', 'C4'}


def _local_worker_token(request: Request, job_id: int):
    """Validate a one-job capability token without exposing it via admin APIs."""
    header = (request.headers.get('authorization') or '').strip()
    scheme, _, token = header.partition(' ')
    if scheme.lower() != 'bearer' or not token or len(token) > 256:
        raise HTTPException(401, 'Local worker authorization required')
    digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
    with connect() as connection:
        row = connection.execute(
            "SELECT token_hash FROM local_worker_tokens WHERE job_id=? AND expires_at>CURRENT_TIMESTAMP",
            (job_id,),
        ).fetchone()
    if not row or not secrets.compare_digest(str(row['token_hash']), digest):
        raise HTTPException(401, 'Local worker token is invalid or expired')
    return token


def _local_worker_fail(job_id: int, message: str):
    message = str(message or 'Local extraction failed')[:4000]
    with connect() as connection:
        job = connection.execute('SELECT status FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            return
        if job['status'] in {'STAGED', 'REVIEW_REQUIRED', 'COMPLETED', 'CANCELLED', 'QUARANTINED'}:
            return
        connection.execute(
            "UPDATE import_jobs SET status='FAILED',error_message=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (message, job_id),
        )
        event(connection, job_id, 'ERROR', message[:1000], None)
        connection.commit()


def _process_local_import_background(job_id: int, artifact_path: str,
                                     data_type: str, family: str, year: int,
                                     round_name: str | None, summary: dict):
    """Validate/stage a locally extracted artifact using the existing pipeline."""
    with _IMPORT_PROCESS_LOCK:
        with connect() as connection:
            job = connection.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
            if not job:
                return
            try:
                result = process_import(
                    connection, job_id, Path(job['original_filename']),
                    data_type=data_type, family=family, year=year,
                    round_name=round_name or '', claimed=True,
                    pre_extracted_path=Path(artifact_path), extraction_summary=summary,
                )
                if not result.get('ok'):
                    log.error('Local-artifact import failed: job_id=%s error=%s', job_id, result.get('error'))
                if result.get('status') not in {'FAILED', 'CANCELLED'}:
                    connection.execute('DELETE FROM local_worker_tokens WHERE job_id=?', (job_id,))
                    connection.commit()
            except Exception as exc:
                log.exception('Unexpected local-artifact processing failure: job_id=%s', job_id)
                connection.rollback()
                connection.execute(
                    "UPDATE import_jobs SET status='FAILED',error_message=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (str(exc)[:4000], job_id),
                )
                event(connection, job_id, 'ERROR', str(exc)[:1000], None)
                connection.commit()


@app.post('/admin/api/local-imports')
def create_local_import(request: Request, payload: dict):
    current_user = require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    filename = Path(str(payload.get('filename') or '')).name
    size_bytes = payload.get('size_bytes')
    sha256 = str(payload.get('sha256') or '').lower()
    if not filename.lower().endswith('.pdf'):
        raise HTTPException(400, 'Only PDF files are accepted')
    if not isinstance(size_bytes, int) or size_bytes < 5 or size_bytes > MAX_PDF_BYTES:
        raise HTTPException(413, 'PDF size is invalid or exceeds 50 MiB')
    if not re.fullmatch(r'[a-f0-9]{64}', sha256):
        raise HTTPException(400, 'A valid SHA-256 fingerprint is required')

    job_key = 'LOCAL-' + uuid.uuid4().hex[:12].upper()
    upload_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(upload_token.encode('utf-8')).hexdigest()
    with connect() as connection:
        connection.execute(
            "INSERT INTO import_jobs(job_key,original_filename,stored_path,sha256,size_bytes,status,created_by) VALUES (?,?,?,?,?,?,?)",
            (job_key, filename, 'local://pending', sha256, size_bytes, 'RECEIVED', current_user['uid']),
        )
        row = connection.execute('SELECT id FROM import_jobs WHERE job_key=?', (job_key,)).fetchone()
        if not row:
            raise RuntimeError('Local import job could not be created')
        job_id = int(row['id'])
        connection.execute('UPDATE import_jobs SET stored_path=? WHERE id=?', (f'local://job_{job_id}', job_id))
        connection.execute(
            "INSERT INTO local_worker_tokens(job_id,token_hash,expires_at) VALUES (?,?,CURRENT_TIMESTAMP + INTERVAL '30 days')",
            (job_id, token_hash),
        )
        event(connection, job_id, 'LOCAL_QUEUED', 'Waiting for the local extraction worker on this PC', 0)
        connection.commit()
    return JSONResponse(status_code=201, content={
        'ok': True, 'job_id': job_id, 'job_key': job_key,
        'status': 'RECEIVED', 'upload_token': upload_token,
    })


@app.post('/admin/api/local-imports/{job_id}/progress')
def local_import_progress(request: Request, job_id: int, payload: dict):
    _local_worker_token(request, job_id)
    page = max(0, min(100000, int(payload.get('page') or 0)))
    total = max(0, min(100000, int(payload.get('total') or 0)))
    state = str(payload.get('state') or 'RUNNING').upper()
    if state not in {'RUNNING', 'PAUSED'}:
        state = 'RUNNING'
    with connect() as connection:
        job = connection.execute('SELECT status FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if job['status'] in {'FAILED', 'CANCELLED', 'STAGED', 'REVIEW_REQUIRED', 'COMPLETED'}:
            return {'ok': True, 'status': job['status']}
        progress = 40 if total <= 0 else min(58, 40 + int(18 * min(page, total) / total))
        message = f'Local extraction {state.lower()} at page {page}' + (f' of {total}' if total else '')
        next_status = 'PAUSED' if state == 'PAUSED' else 'EXTRACTING'
        connection.execute(
            "UPDATE import_jobs SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (next_status, job_id),
        )
        event(connection, job_id, 'LOCAL_EXTRACT', message, progress)
        connection.commit()
    return {'ok': True, 'status': next_status, 'progress': progress}


@app.post('/admin/api/local-imports/{job_id}/fail')
def local_import_fail(request: Request, job_id: int, payload: dict):
    _local_worker_token(request, job_id)
    message = str(payload.get('error') or 'Local extraction failed')[:4000]
    _local_worker_fail(job_id, message)
    return {'ok': True, 'job_id': job_id}


@app.post('/admin/api/local-imports/{job_id}/cancel')
def local_import_cancel(request: Request, job_id: int):
    _local_worker_token(request, job_id)
    marker = BASE / 'data' / 'import_staging' / f'job_{job_id}' / 'CANCEL'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    with connect() as connection:
        job = connection.execute('SELECT status FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if job['status'] not in {'RECEIVED', 'IDENTIFIED', 'EXTRACTING', 'NORMALIZING', 'VALIDATING', 'COMPARING', 'PAUSED', 'FAILED', 'CANCELLED'}:
            raise HTTPException(409, f"Import cannot be cancelled while in {job['status']}")
        connection.execute(
            "UPDATE import_jobs SET status='CANCELLED',error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        event(connection, job_id, 'CANCELLED', 'Local worker cancellation requested', None)
        connection.commit()
    return {'ok': True, 'job_id': job_id, 'status': 'CANCELLED'}


@app.post('/admin/api/local-imports/{job_id}/restart')
def local_import_restart(request: Request, job_id: int):
    _local_worker_token(request, job_id)
    marker = BASE / 'data' / 'import_staging' / f'job_{job_id}' / 'CANCEL'
    if marker.exists():
        marker.unlink()
    with connect() as connection:
        job = connection.execute('SELECT status,stored_path FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if not str(job['stored_path'] or '').startswith('local://'):
            raise HTTPException(409, 'This is not a local-worker import')
        if job['status'] not in {'FAILED', 'CANCELLED'}:
            raise HTTPException(409, f"Import cannot be restarted while in {job['status']}")
        connection.execute('DELETE FROM local_worker_receipts WHERE job_id=?', (job_id,))
        connection.execute('DELETE FROM import_staging_records WHERE job_id=?', (job_id,))
        connection.execute('DELETE FROM import_results WHERE job_id=?', (job_id,))
        connection.execute(
            "UPDATE import_jobs SET status='EXTRACTING',error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        event(connection, job_id, 'LOCAL_RETRY', 'Local extraction retry queued', 0)
        connection.commit()
    return {'ok': True, 'job_id': job_id, 'status': 'EXTRACTING'}


@app.get('/admin/api/local-imports/{job_id}/status')
def local_import_status(request: Request, job_id: int):
    _local_worker_token(request, job_id)
    with connect() as connection:
        job = connection.execute('SELECT id,status,error_message,updated_at FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        latest = connection.execute('SELECT progress,message FROM import_events WHERE job_id=? ORDER BY id DESC LIMIT 1', (job_id,)).fetchone()
        return {'job_id': job_id, 'status': job['status'], 'error': job['error_message'],
                'progress': latest['progress'] if latest else 0,
                'message': latest['message'] if latest else '', 'updated_at': job['updated_at']}


@app.post('/admin/api/local-imports/{job_id}/revalidate')
def revalidate_local_import(request: Request, job_id: int, background_tasks: BackgroundTasks):
    _local_worker_token(request, job_id)
    with connect() as connection:
        job = connection.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if not str(job['stored_path'] or '').startswith('local://'):
            raise HTTPException(409, 'This is not a local-worker import')
        if job['status'] not in {'FAILED', 'CANCELLED'}:
            raise HTTPException(409, f"Import cannot be revalidated while in {job['status']}")
        receipt = connection.execute('SELECT artifact_sha256 FROM local_worker_receipts WHERE job_id=?', (job_id,)).fetchone()
        if not receipt or not job['data_type'] or not job['course_family'] or not job['year']:
            raise HTTPException(409, 'No complete extracted artifact is available; rerun local extraction instead')
        suffix = '_cutoffs.csv' if job['data_type'] == 'CUTOFFS' else '_seats_long.csv'
        artifact = BASE / 'data' / 'local_import_artifacts' / f'job_{job_id}' / f"{Path(job['original_filename']).stem}{suffix}"
        if not artifact.is_file():
            raise HTTPException(404, 'Saved extracted artifact is missing; rerun local extraction')
        connection.execute('DELETE FROM import_staging_records WHERE job_id=?', (job_id,))
        connection.execute('DELETE FROM import_results WHERE job_id=?', (job_id,))
        connection.execute(
            "UPDATE import_jobs SET status='EXTRACTING',error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        event(connection, job_id, 'LOCAL_REVALIDATE', 'Revalidating the previously extracted CSV artifact', 60)
        connection.commit()
    background_tasks.add_task(
        _process_local_import_background, job_id, str(artifact),
        job['data_type'], job['course_family'], int(job['year']), job['round'] or '',
        {},
    )
    return {'ok': True, 'job_id': job_id, 'status': 'EXTRACTING'}


@app.post('/admin/api/local-imports/{job_id}/artifact')
def receive_local_artifact(
    request: Request, job_id: int, background_tasks: BackgroundTasks,
    file: UploadFile = File(...), data_type: str = Form(...),
    family: str = Form(...), year: int = Form(...),
    round_name: str = Form(''), source_sha256: str = Form(...),
    summary_json: str = Form('{}'),
):
    _local_worker_token(request, job_id)
    data_type = str(data_type).upper().strip()
    family = str(family).upper().strip()
    round_name = str(round_name).upper().strip() or None
    if data_type not in {'CUTOFFS', 'SEATS'} or family not in LOCAL_WORKER_FAMILIES or not 2000 <= year <= 2100:
        raise HTTPException(400, 'Local worker returned invalid source metadata')
    if data_type == 'CUTOFFS' and round_name not in LOCAL_WORKER_ROUNDS:
        raise HTTPException(400, 'Cutoff PDF must identify CAP round C1-C4')
    if not re.fullmatch(r'[a-fA-F0-9]{64}', source_sha256):
        raise HTTPException(400, 'Invalid source fingerprint')
    try:
        summary = json.loads(summary_json)
    except Exception:
        raise HTTPException(400, 'Invalid extraction summary JSON')
    if not isinstance(summary, dict):
        raise HTTPException(400, 'Extraction summary must be an object')

    with connect() as connection:
        job = connection.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if not secrets.compare_digest(str(job['sha256']).lower(), source_sha256.lower()):
            raise HTTPException(400, 'The local PDF fingerprint does not match the queued import')
        if job['status'] in {'STAGED', 'REVIEW_REQUIRED'}:
            return {'ok': True, 'job_id': job_id, 'status': job['status'], 'duplicate': True}
        receipt = connection.execute('SELECT artifact_sha256 FROM local_worker_receipts WHERE job_id=?', (job_id,)).fetchone()
        if receipt and job['status'] not in {'FAILED', 'CANCELLED'}:
            return {'ok': True, 'job_id': job_id, 'status': job['status'], 'duplicate': True}

    expected_header = (
        {'source_pdf', 'page', 'institution_code', 'program_name', 'category', 'percentage'}
        if data_type == 'CUTOFFS'
        else {'source_pdf', 'page', 'institution_code', 'choice_code', 'allocation_type', 'category', 'seats'}
    )
    suffix = '_cutoffs.csv' if data_type == 'CUTOFFS' else '_seats_long.csv'
    stem = Path(str(job['original_filename'])).stem
    artifact_dir = BASE / 'data' / 'local_import_artifacts' / f'job_{job_id}'
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f'{stem}{suffix}'
    temp_path = artifact_dir / (artifact_path.name + '.upload')
    total = 0
    digest = hashlib.sha256()
    try:
        with temp_path.open('wb') as output:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > LOCAL_ARTIFACT_MAX_BYTES:
                    raise HTTPException(413, 'Extracted CSV exceeds 150 MiB limit')
                digest.update(chunk)
                output.write(chunk)
        if total == 0:
            raise HTTPException(400, 'Extracted artifact is empty')
        with temp_path.open('r', encoding='utf-8-sig', newline='') as check_file:
            header = set(next(csv.reader(check_file), []))
        if not expected_header.issubset(header):
            raise HTTPException(400, 'Extracted artifact columns do not match the expected CAP schema')
        temp_path.replace(artifact_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    with connect() as connection:
        current = connection.execute('SELECT status FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not current:
            raise HTTPException(404, 'Import not found')
        if current['status'] == 'CANCELLED':
            raise HTTPException(409, 'Import was cancelled before artifact receipt')
        connection.execute('DELETE FROM import_staging_records WHERE job_id=?', (job_id,))
        connection.execute('DELETE FROM import_results WHERE job_id=?', (job_id,))
        connection.execute('DELETE FROM local_worker_receipts WHERE job_id=?', (job_id,))
        connection.execute(
            "UPDATE import_jobs SET data_type=?,course_family=?,year=?,round=?,status='EXTRACTING',error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (data_type, family, year, round_name, job_id),
        )
        connection.execute(
            'INSERT INTO local_worker_receipts(job_id,artifact_sha256) VALUES (?,?)',
            (job_id, digest.hexdigest()),
        )
        event(connection, job_id, 'LOCAL_ARTIFACT_RECEIVED',
              f'Received {total:,} bytes of locally extracted {data_type.lower()} records', 60)
        connection.commit()
    background_tasks.add_task(
        _process_local_import_background, job_id, str(artifact_path),
        data_type, family, year, round_name, summary,
    )
    return JSONResponse(status_code=202, content={'ok': True, 'job_id': job_id, 'status': 'EXTRACTING'})


@app.post('/admin/api/imports')
def upload(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    current_user = require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    name = Path(file.filename or '').name
    if not name.lower().endswith('.pdf'):
        raise HTTPException(400, 'Only PDF files are accepted')
    try:
        backend = storage_backend()
        if backend == 's3':
            pass  # Optional private durable storage; local mode is the no-card fallback.
    except StorageNotConfigured as exc:
        raise HTTPException(503, str(exc)) from exc

    job_key = 'IMPORT-' + uuid.uuid4().hex[:12].upper()
    tmp = IMPORTS / (job_key + '.upload')
    stored_value = None
    total = 0
    digest = hashlib.sha256()
    try:
        with open(tmp, 'wb') as output:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    raise HTTPException(413, 'PDF exceeds 50 MiB limit')
                digest.update(chunk)
                output.write(chunk)
        if total < 5:
            raise HTTPException(400, 'PDF upload is empty or too small')
        fingerprint = digest.hexdigest()
        try:
            stored_value = store_source_pdf(tmp, f'imports/{job_key}.pdf', fingerprint)
        except StorageNotConfigured as exc:
            raise HTTPException(503, str(exc)) from exc

        with connect() as connection:
            connection.execute(
                'INSERT INTO import_jobs(job_key,original_filename,stored_path,sha256,size_bytes,status,created_by) VALUES (?,?,?,?,?,?,?)',
                (job_key, name, stored_value, fingerprint, total, 'RECEIVED', current_user['uid']),
            )
            job_row = connection.execute(
                'SELECT id FROM import_jobs WHERE job_key=?', (job_key,)
            ).fetchone()
            if not job_row:
                raise RuntimeError('Import job could not be created')
            job_id = int(job_row['id'])
            event(connection, job_id, 'RECEIVED', 'PDF uploaded to private source storage', 0)
            connection.commit()
            with materialize_source(stored_value) as source_path:
                ok = run_preflight(connection, job_id, source_path, name)
            if ok:
                connection.execute(
                    "UPDATE import_jobs SET status='QUEUED',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='IDENTIFIED'",
                    (job_id,),
                )
                event(connection, job_id, 'QUEUED', 'Waiting for the server extraction worker', 40)
                connection.commit()
            current = connection.execute('SELECT status FROM import_jobs WHERE id=?', (job_id,)).fetchone()
            current_status = str(current['status']) if current else 'FAILED'
        return JSONResponse(status_code=202 if current_status == 'QUEUED' else 400,
                            content={'ok': current_status == 'QUEUED', 'id': job_id,
                                     'job_key': job_key, 'status': current_status})
    except HTTPException:
        if tmp.exists():
            tmp.unlink()
        # Once the DB job exists, retain its source for admin inspection. Before
        # that point, remove an orphaned upload object if creation failed.
        if stored_value:
            try:
                with connect() as c:
                    exists = c.execute('SELECT 1 AS n FROM import_jobs WHERE job_key=?', (job_key,)).fetchone()
                if not exists:
                    delete_source(stored_value)
            except Exception:
                log.exception('Could not clean unreferenced source upload %s', job_key)
        raise
    except Exception:
        if tmp.exists():
            tmp.unlink()
        if stored_value:
            try:
                with connect() as c:
                    exists = c.execute('SELECT 1 AS n FROM import_jobs WHERE job_key=?', (job_key,)).fetchone()
                if not exists:
                    delete_source(stored_value)
            except Exception:
                log.exception('Could not clean unreferenced source upload %s', job_key)
        raise


def _resolver_server_busy():
    """Keep AI resolver work out of the critical path on the small web instance."""
    with connect() as c:
        active = c.execute(
            "SELECT COUNT(*) AS n FROM import_jobs WHERE status IN ('RECEIVED','IDENTIFIED','EXTRACTING','NORMALIZING','VALIDATING','COMPARING')"
        ).fetchone()['n']
    if active:
        return True, f'{active} PDF import(s) are processing'
    try:
        with open('/sys/fs/cgroup/memory.current', 'r', encoding='utf-8') as f:
            used = int(f.read().strip())
        with open('/sys/fs/cgroup/memory.max', 'r', encoding='utf-8') as f:
            raw_max = f.read().strip()
        if raw_max != 'max':
            limit = int(raw_max)
            if limit > 0 and used / limit >= 0.72:
                return True, 'server memory is above the resolver safety threshold'
    except Exception:
        pass
    return False, None


def _resolve_one_import_background(job_id: int):
    """Run exactly one resolver step in a short-lived child process.

    The web service is intentionally small (512 MB on the current Render
    instance). Gemini's Google-search response handling is isolated from the
    long-lived FastAPI process so temporary allocations are returned to the OS
    when the resolver step exits. The worker itself takes a PostgreSQL advisory
    lock, preventing concurrent resolver children from multiplying memory use.
    """
    try:
        busy, reason = _resolver_server_busy()
        if busy:
            log.info('Website resolver deferred after import %s: %s', job_id, reason)
            return
        env = os.environ.copy()
        env.setdefault('PYTHONIOENCODING', 'utf-8')
        env.setdefault('PYTHONUTF8', '1')
        env.setdefault('OMP_THREAD_LIMIT', '1')
        env.setdefault('OPENBLAS_NUM_THREADS', '1')
        env.setdefault('MKL_NUM_THREADS', '1')
        cmd = [
            sys.executable,
            str(BASE / 'scripts' / 'resolver_worker.py'),
            str(job_id),
            '--limit', '1',
        ]
        completed = subprocess.run(
            cmd,
            cwd=str(BASE),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=150,
            check=False,
        )
        output = (completed.stdout or '').strip()
        if completed.returncode != 0:
            log.error(
                'Automatic website resolver worker failed: job_id=%s exit=%s output=%s',
                job_id, completed.returncode, output[-4000:],
            )
        else:
            log.info('Automatic website resolver worker: job_id=%s output=%s',
                     job_id, output[-4000:])
    except subprocess.TimeoutExpired:
        log.error('Automatic website resolver worker timed out: job_id=%s', job_id)
    except Exception:
        # Resolver failure must never turn a clean data import into a failed
        # import. The queue remains visible in the Resolver admin page.
        log.exception('Automatic website resolver step failed: job_id=%s', job_id)


def _process_import_background(job_id: int):
    """Run one memory-heavy import at a time on the web instance."""
    with _IMPORT_PROCESS_LOCK:
        _process_import_background_locked(job_id)


def _process_import_background_locked(job_id: int):
    """Process an import while the global PDF-processing lock is held."""
    with connect() as connection:
        job = connection.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            return
        try:
            with materialize_source(job['stored_path']) as source_path:
                expected_hash = str(job.get('sha256') or '').strip().lower()
                if expected_hash and sha256_file(source_path).lower() != expected_hash:
                    raise RuntimeError('Retained source PDF fingerprint does not match the upload record')
                result = process_import(
                    connection,
                    job_id,
                    source_path,
                    data_type=job['data_type'],
                    family=job['course_family'],
                    year=int(job['year']),
                    round_name=job['round'],
                    claimed=True,
                    source_filename=job['original_filename'],
                    worker_id=job.get('worker_id'),
                )
            if not result.get('ok'):
                log.error('Background import processing failed: job_id=%s error=%s', job_id, result.get('error'))
            elif result.get('status') == JobStatus.STAGED.value:
                # The final combined artifacts remain available for review/publish;
                # per-chunk intermediate files are no longer needed after staging.
                import shutil
                shutil.rmtree(BASE / 'data' / 'import_work' / f'job_{job_id}' / 'raw' / '.chunk_work', ignore_errors=True)
                log.info('Import is staged and awaiting explicit admin approval: job_id=%s', job_id)
        except Exception:
            log.exception('Unexpected background import processing failure: job_id=%s', job_id)
            connection.rollback()
            connection.execute(
                "UPDATE import_jobs SET status='FAILED',error_message='Processing failed; see server logs',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (job_id,),
            )
            connection.commit()


@app.post('/admin/api/imports/{job_id}/process')
def process_job(request: Request, job_id: int, background_tasks: BackgroundTasks):
    require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        job = connection.execute(
            'SELECT *, (worker_lease_until > CURRENT_TIMESTAMP) AS worker_alive FROM import_jobs WHERE id=?',
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if job.get('source_deleted'):
            raise HTTPException(409, 'The source PDF was manually deleted. Re-upload it to retry extraction.')
        if job['status'] not in {JobStatus.REVIEW_REQUIRED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
            raise HTTPException(409, f'Import is not ready for processing: {job["status"]}')
        if job['status'] == JobStatus.CANCELLED.value:
            if job.get('worker_alive') or _ACTIVE_IMPORT_JOB_ID == job_id:
                raise HTTPException(409, 'Cancellation is still stopping the worker; wait a moment before retrying')
            marker = BASE / 'data' / 'import_staging' / f'job_{job_id}' / 'CANCEL'
            if marker.exists():
                marker.unlink()
        if str(job['stored_path'] or '').startswith('local://'):
            raise HTTPException(409, 'This import runs on the local worker. Retry it from Import Center while that worker is running.')
        try:
            with materialize_source(job['stored_path']) as path:
                # Re-run preflight on every retry. A previous run may have classified
                preflight_ok = run_preflight(connection, job_id, path, job['original_filename'])
        except FileNotFoundError as exc:
            raise HTTPException(404, 'Stored source PDF is missing') from exc
        except StorageNotConfigured as exc:
            raise HTTPException(503, str(exc)) from exc

        # Re-run preflight on every retry. A previous run may have classified
        # a generic filename incorrectly (especially a seat matrix named like
        # `BBA 26 C1.pdf`), and retrying stale metadata would repeat the error.
        if not preflight_ok:
            raise HTTPException(409, 'PDF preflight failed; inspect the import error before retrying')
        job = connection.execute(
            'SELECT * FROM import_jobs WHERE id=?',
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found after preflight')

        required_metadata = (
            not job['data_type']
            or not job['course_family']
            or not job['year']
            or (job['data_type'] == 'CUTOFFS' and not job['round'])
        )
        if required_metadata:
            raise HTTPException(
                409,
                'Source metadata is incomplete; identify year and course before processing'
                if job['data_type'] == 'SEATS'
                else 'Source metadata is incomplete; identify year, round and course before processing',
            )

        claimed = connection.execute(
            "UPDATE import_jobs SET status='QUEUED',current_page=0,current_chunk=0,error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='IDENTIFIED'",
            (job_id,),
        ).rowcount
        if not claimed:
            raise HTTPException(409, 'Import is already being processed')

        # A retry clears any previous stop marker before starting a fresh run.
        cancel_marker = BASE / 'data' / 'import_staging' / f'job_{job_id}' / 'CANCEL'
        if cancel_marker.exists():
            cancel_marker.unlink()
        (cancel_marker.parent / 'PAUSE').unlink(missing_ok=True)
        connection.execute('DELETE FROM import_staging_records WHERE job_id=?', (job_id,))
        connection.execute('DELETE FROM import_results WHERE job_id=?', (job_id,))
        event(connection, job_id, 'QUEUED', 'Retry queued for the server extraction worker', 0)
        connection.commit()
        return JSONResponse(
            status_code=202,
            content={"ok": True, "job_id": job_id, "status": "QUEUED"},
        )


@app.post('/admin/api/imports/{job_id}/pause')
def pause_import(request: Request, job_id: int):
    require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        job = connection.execute('SELECT status,stored_path FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if str(job['stored_path'] or '').startswith('local://'):
            raise HTTPException(409, 'This legacy import belongs to the local worker')
        if job['status'] not in {'QUEUED', 'EXTRACTING', 'PAUSED'}:
            raise HTTPException(409, f'Only a queued or extracting import can be paused (current status: {job["status"]})')
        control = BASE / 'data' / 'import_staging' / f'job_{job_id}'
        control.mkdir(parents=True, exist_ok=True)
        (control / 'PAUSE').touch()
        connection.execute("UPDATE import_jobs SET status='PAUSED',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status IN ('QUEUED','EXTRACTING','PAUSED')", (job_id,))
        event(connection, job_id, 'PAUSE_REQUESTED', 'Pause requested; extraction will stop at a safe page checkpoint', None)
        connection.commit()
    return {'ok': True, 'job_id': job_id, 'status': 'PAUSE_REQUESTED'}


@app.post('/admin/api/imports/{job_id}/resume')
def resume_import(request: Request, job_id: int):
    require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        job = connection.execute('SELECT status,stored_path,worker_id,(worker_lease_until > CURRENT_TIMESTAMP) AS worker_alive FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if str(job['stored_path'] or '').startswith('local://'):
            raise HTTPException(409, 'This legacy import belongs to the local worker')
        if job['status'] not in {'EXTRACTING', 'PAUSED'}:
            raise HTTPException(409, f'Only an extracting import can be resumed (current status: {job["status"]})')
        control = BASE / 'data' / 'import_staging' / f'job_{job_id}'
        (control / 'PAUSE').unlink(missing_ok=True)
        next_status = 'EXTRACTING' if job.get('worker_id') and job.get('worker_alive') else 'QUEUED'
        connection.execute("UPDATE import_jobs SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='PAUSED'", (next_status, job_id))
        event(connection, job_id, 'RESUME_REQUESTED', 'Pause marker removed; extraction will continue', None)
        connection.commit()
    return {'ok': True, 'job_id': job_id, 'status': next_status}


@app.get('/admin/api/runtime')
def runtime_metrics(request: Request):
    require(request, {'SUPER_ADMIN', 'DATA_ADMIN', 'REVIEWER', 'READ_ONLY'})
    import shutil
    def read_int(path):
        try:
            raw = Path(path).read_text(encoding='utf-8').strip()
            return None if raw in {'max', ''} else int(raw)
        except (OSError, ValueError):
            return None

    mem_used = read_int('/sys/fs/cgroup/memory.current')
    mem_limit = read_int('/sys/fs/cgroup/memory.max')
    if mem_limit is None:
        mem_limit = read_int('/sys/fs/cgroup/memory/memory.limit_in_bytes')
    if mem_used is None:
        mem_used = read_int('/sys/fs/cgroup/memory/memory.usage_in_bytes')
    cpu_quota = None
    cpu_period = None
    try:
        quota_raw, period_raw = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota_raw != 'max':
            cpu_quota, cpu_period = int(quota_raw), int(period_raw)
    except (OSError, ValueError):
        try:
            cpu_quota = read_int('/sys/fs/cgroup/cpu/cpu.cfs_quota_us')
            cpu_period = read_int('/sys/fs/cgroup/cpu/cpu.cfs_period_us')
        except Exception:
            pass

    # Calculate usage from cgroup cumulative CPU time between dashboard polls.
    cpu_percent = None
    try:
        values = {}
        for line in Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines():
            key, value = line.split()
            values[key] = int(value)
        usage_usec = values.get('usage_usec')
        if usage_usec is not None:
            now = time.monotonic()
            previous = getattr(runtime_metrics, '_cpu_previous', None)
            if previous:
                elapsed = max(0.001, now - previous[0])
                capacity = ((cpu_quota / cpu_period) if cpu_quota and cpu_period else 1.0)
                cpu_percent = round(max(0.0, (usage_usec - previous[1]) / 1_000_000 / elapsed / capacity * 100), 1)
            runtime_metrics._cpu_previous = (now, usage_usec)
    except (OSError, ValueError, ZeroDivisionError):
        pass

    def tree_bytes(path):
        total = 0
        try:
            for item in Path(path).rglob('*'):
                if item.is_file():
                    try:
                        total += item.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    with connect() as connection:
        storage = connection.execute('SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes),0) AS bytes FROM import_jobs WHERE source_deleted=FALSE AND stored_path NOT LIKE ?',
                                     ('local://%',)).fetchone()
        active = connection.execute("SELECT id,status,original_filename,size_bytes,current_page,total_pages,current_chunk,total_chunks,worker_id,(worker_lease_until > CURRENT_TIMESTAMP) AS worker_alive FROM import_jobs WHERE status IN ('EXTRACTING','PAUSED','NORMALIZING','VALIDATING','COMPARING') OR (status='CANCELLED' AND worker_lease_until > CURRENT_TIMESTAMP) ORDER BY id DESC LIMIT 1").fetchone()
        queued_count = connection.execute("SELECT COUNT(*) AS n FROM import_jobs WHERE status='QUEUED'").fetchone()['n']
    job_progress = None
    if active:
        control = BASE / 'data' / 'import_staging' / f"job_{active['id']}"
        progress_path = control / 'progress.json'
        manifest_path = BASE / 'data' / 'import_work' / f"job_{active['id']}" / 'raw' / '.chunk_work' / 'manifest.json'
        progress = {}
        manifest = {}
        try:
            progress = json.loads(progress_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        if manifest_path:
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
        total_pages = int(progress.get('total') or active.get('total_pages') or manifest.get('total_pages') or 0)
        current_page = int(progress.get('page') or active.get('current_page') or 0)
        chunk_size = max(1, int(progress.get('chunk_pages') or manifest.get('chunk_pages') or 10))
        completed_chunks = len([x for x in manifest.get('parts', []) if x.get('status') == 'COMPLETED'])
        pause_requested = (control / 'PAUSE').exists()
        job_progress = {
            'id': active['id'], 'status': active['status'], 'filename': active['original_filename'],
            'page': current_page, 'total_pages': total_pages,
            'percent': round(min(100, current_page / total_pages * 100), 1) if total_pages else 0,
            'chunk_count': int(progress.get('chunk_count') or active.get('current_chunk') or completed_chunks),
            'total_chunks': int(progress.get('total_chunks') or active.get('total_chunks') or (((total_pages + chunk_size - 1) // chunk_size) if total_pages else 0)),
            'pause_requested': pause_requested,
            'paused_at_checkpoint': active['status'] == 'PAUSED' or progress.get('state') == 'PAUSED',
        }
    disk = shutil.disk_usage(BASE)
    return {
        'ok': True,
        'memory': {'used_bytes': mem_used, 'limit_bytes': mem_limit,
                   'used_percent': round(mem_used / mem_limit * 100, 1) if mem_used is not None and mem_limit else None},
        'cpu': {'percent_of_available_capacity': cpu_percent,
                'quota_cores': round(cpu_quota / cpu_period, 2) if cpu_quota and cpu_period else None},
        'disk': {'total_bytes': disk.total, 'free_bytes': disk.free,
                 'used_percent': round((disk.total - disk.free) / disk.total * 100, 1) if disk.total else None,
                 'temporary_files_bytes': tree_bytes(BASE / 'data' / 'import_work') + tree_bytes(BASE / 'data' / 'import_staging')},
        'source_pdfs': {'tracked_files': int(storage['n']), 'tracked_bytes': int(storage['bytes'])},
        'queued_jobs': int(queued_count),
        'storage': {'backend': storage_backend(), 'durable_configured': all(os.getenv(k, '').strip() for k in ('CET_S3_ENDPOINT_URL', 'CET_S3_BUCKET', 'CET_S3_ACCESS_KEY_ID', 'CET_S3_SECRET_ACCESS_KEY')) if storage_backend() == 's3' else False},
        'active_job': job_progress,
    }


@app.post('/admin/api/imports/{job_id}/cancel')
def cancel_import(request: Request, job_id: int):
    require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        job = connection.execute('SELECT * FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        active = {
            JobStatus.RECEIVED.value, JobStatus.IDENTIFIED.value,
            JobStatus.QUEUED.value, 'PAUSED',
            JobStatus.EXTRACTING.value, JobStatus.NORMALIZING.value,
            JobStatus.VALIDATING.value, JobStatus.COMPARING.value,
        }
        if str(job['stored_path'] or '').startswith('local://'):
            raise HTTPException(409, 'Use the local worker controls in Import Center to pause or cancel this extraction.')
        if job['status'] not in active:
            raise HTTPException(409, f"Import cannot be stopped while in {job['status']}")
        marker = BASE / 'data' / 'import_staging' / f'job_{job_id}' / 'CANCEL'
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        connection.execute(
            "UPDATE import_jobs SET status='CANCELLED',error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status IN ('RECEIVED','IDENTIFIED','QUEUED','PAUSED','EXTRACTING','NORMALIZING','VALIDATING','COMPARING')",
            (job_id,),
        )
        event(connection, job_id, 'CANCELLED', 'Processing stop requested by admin', None)
        connection.commit()
    return {'ok': True, 'job_id': job_id, 'status': 'CANCELLED'}


@app.delete('/admin/api/imports/{job_id}/source')
def delete_import_source(request: Request, job_id: int):
    user = require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        job = connection.execute(
            'SELECT *, (worker_lease_until > CURRENT_TIMESTAMP) AS worker_alive FROM import_jobs WHERE id=?',
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if _ACTIVE_IMPORT_JOB_ID == job_id or job.get('worker_alive') or job['status'] in {'QUEUED','EXTRACTING','PAUSED','NORMALIZING','VALIDATING','COMPARING'}:
            raise HTTPException(409, 'Cannot delete the source while the job is queued or a worker may still be using it.')
        if job.get('source_deleted'):
            return {'ok': True, 'job_id': job_id, 'source_deleted': True, 'already_deleted': True}
        if str(job.get('stored_path') or '').startswith('local://'):
            raise HTTPException(409, 'This legacy local-worker source is not stored on the server.')
        if str(job.get('stored_path') or '').startswith('gdrive://'):
            raise HTTPException(409, 'CAPFind has read-only access to Google Drive. Delete the original file directly in Drive; this action does not delete Drive files.')
        try:
            delete_source(str(job.get('stored_path') or ''))
        except Exception as exc:
            log.exception('Manual source-PDF deletion failed: job_id=%s', job_id)
            raise HTTPException(503, 'Source PDF deletion failed; no database records were removed.') from exc
        connection.execute(
            'UPDATE import_jobs SET source_deleted=TRUE,source_deleted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (job_id,),
        )
        event(connection, job_id, 'SOURCE_PDF_DELETED', 'Admin manually deleted the stored source PDF; import results and audit metadata were retained', None)
        connection.execute(
            "INSERT INTO audit_log(actor_user_id,action,entity_type,entity_id,before_json,after_json,reason) VALUES (?,?,?,?,?,?,?)",
            (user['uid'], 'DELETE_SOURCE_PDF', 'IMPORT', str(job_id),
             json.dumps({'job_key': job['job_key'], 'source_deleted': False}),
             json.dumps({'source_deleted': True}), 'Source PDF manually deleted; import metadata retained'),
        )
        connection.commit()
    return {'ok': True, 'job_id': job_id, 'source_deleted': True}


@app.delete('/admin/api/imports/{job_id}')
def delete_import(request: Request, job_id: int):
    u = require(request, {'SUPER_ADMIN', 'DATA_ADMIN'}, csrf=True)
    with connect() as c:
        job = c.execute('SELECT *, (worker_lease_until > CURRENT_TIMESTAMP) AS worker_alive FROM import_jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Import not found')
        if _ACTIVE_IMPORT_JOB_ID == job_id or job.get('worker_alive') or job['status'] in {'QUEUED','EXTRACTING','PAUSED','NORMALIZING','VALIDATING','COMPARING'}:
            raise HTTPException(409, 'This job is queued or still has a live worker. Cancel it and wait until processing stops before deleting.')
        deletable = {
            JobStatus.RECEIVED.value,
            JobStatus.IDENTIFIED.value,
            JobStatus.QUEUED.value,
            'PAUSED',
            JobStatus.REVIEW_REQUIRED.value,
            JobStatus.STAGED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
            JobStatus.QUARANTINED.value,
        }
        if job['status'] not in deletable:
            raise HTTPException(409, f"Import cannot be deleted while in {job['status']}")

        # A committed/released import is part of the audit trail. PostgreSQL
        # correctly prevents deleting its source job, so surface a useful 409
        # instead of leaking a 500 IntegrityError from the FK constraint.
        release = c.execute(
            'SELECT release_key,status FROM data_releases WHERE source_job_id=? ORDER BY id DESC LIMIT 1',
            (job_id,),
        ).fetchone()
        if release:
            raise HTTPException(
                409,
                f"Import is referenced by release {release['release_key']} ({release['status']}) and cannot be deleted; keep it for audit history.",
            )

        stored_value = str(job['stored_path'] or '')
        try:
            if not job.get('source_deleted'):
                delete_source(stored_value)
        except Exception as exc:
            log.exception('Source PDF deletion failed; retaining import metadata: job_id=%s', job_id)
            raise HTTPException(503, 'Source PDF could not be deleted; the import record was retained. Check storage configuration and retry.') from exc

        c.execute('DELETE FROM import_events WHERE job_id=?', (job_id,))
        c.execute('DELETE FROM import_staging_records WHERE job_id=?', (job_id,))
        c.execute('DELETE FROM import_results WHERE job_id=?', (job_id,))
        c.execute('DELETE FROM import_jobs WHERE id=?', (job_id,))
        c.execute(
            "INSERT INTO audit_log(actor_user_id,action,entity_type,entity_id,before_json,after_json,reason) "
            "VALUES (?,?,?,?,?,?,?)",
            (u['uid'], 'DELETE_IMPORT', 'IMPORT', str(job_id),
             json.dumps({'job_key': job['job_key'], 'status': job['status']}),
             None, 'Import deleted before production commit'),
        )
        c.commit()
    local_artifacts = BASE / 'data' / 'local_import_artifacts' / f'job_{job_id}'
    if local_artifacts.exists():
        import shutil
        shutil.rmtree(local_artifacts, ignore_errors=True)
    for directory in (
        BASE / 'data' / 'import_work' / f"job_{job_id}",
        BASE / 'data' / 'import_staging' / f"job_{job_id}",
        BASE / 'data' / 'work' / f"job_{job_id}",
        BASE / 'data' / 'staging' / f"job_{job_id}",
    ):
        if directory.exists():
            import shutil
            shutil.rmtree(directory, ignore_errors=True)
    return {'ok': True, 'job_id': job_id}


@app.get('/admin/api/imports')
def imports(request: Request):
    require(request)
    with connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT j.*, COALESCE((SELECT progress FROM import_events e WHERE e.job_id=j.id ORDER BY e.id DESC LIMIT 1),0) AS progress "
                "FROM import_jobs j ORDER BY j.id DESC LIMIT 100"
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
                   (SELECT COUNT(*) FROM import_staging_records r WHERE r.job_id=j.id AND UPPER(COALESCE(r.validation_status,'')) = 'REVIEW') AS validation_issue_count
            FROM import_jobs j
            WHERE j.status IN ('STAGED','REVIEW_REQUIRED','COMMITTING')
            ORDER BY j.id DESC
        """).fetchall()
        response = [dict(r) for r in rows]
        # Older imports stored the complete file-level validator output on
        # every row. Count the affected category records from that report
        # rather than presenting every staged record as an individual error.
        for item in response:
            if not item.get("validation_issue_count"):
                continue
            repeated = c.execute(
                "SELECT validation_message FROM import_staging_records WHERE job_id=? "
                "AND validation_status='REVIEW' LIMIT 1", (item["id"],)
            ).fetchone()
            message = str(repeated["validation_message"] or "") if repeated else ""
            if "Total issues:" not in message:
                continue
            result = c.execute(
                "SELECT summary_json FROM import_results WHERE job_id=? ORDER BY id DESC LIMIT 1",
                (item["id"],)
            ).fetchone()
            try:
                summary = json.loads(result["summary_json"] or "{}") if result else {}
                report = str(summary.get("validation", ""))
                unknown_categories = set(re.findall(r"\[([^\]]+)\]\s*:\s*\d+", report))
                if unknown_categories:
                    staged = c.execute(
                        "SELECT normalized_json FROM import_staging_records WHERE job_id=?",
                        (item["id"],)
                    ).fetchall()
                    item["validation_issue_count"] = sum(
                        1 for staged_row in staged
                        if str(json.loads(staged_row["normalized_json"] or "{}").get("category", "")).strip().upper() in unknown_categories
                    )
                else:
                    item["validation_issue_count"] = 0
            except (TypeError, ValueError, json.JSONDecodeError):
                # Preserve the conservative count if an old report is malformed.
                pass
        return response

@app.post('/admin/api/imports/{job_id}/revalidate-legacy-mh')
def revalidate_legacy_mh(request: Request, job_id: int):
    u = require(request, {'SUPER_ADMIN','DATA_ADMIN'}, csrf=True)
    with connect() as c:
        try:
            return revalidate_legacy_mh_staging(c, job_id, u['uid'])
        except ValueError as e:
            raise HTTPException(409, str(e))


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
        try:
            result = approve_import(c,job_id,u['uid'],notes)
            invalidate_public_caches()
            return result
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
        try:
            result = rollback_release(c,release_id,u['uid'],reason)
            invalidate_public_caches()
            return result
        except ValueError as e: raise HTTPException(409,str(e))



@app.delete('/admin/api/releases/{release_id}')
def delete_rolled_back_release(request: Request, release_id: int):
    u=require(request, {'SUPER_ADMIN'}, csrf=True)
    with connect() as c:
        try:
            result = purge_rolled_back_release(c,release_id,u['uid'])
            invalidate_public_caches()
            return result
        except ValueError as e:
            raise HTTPException(409,str(e))


@app.post('/admin/api/releases/{release_id}/publish')
def publish(request: Request, release_id: int):
    u=require(request, {'SUPER_ADMIN','DATA_ADMIN'},csrf=True)
    # Read authorization metadata in a short transaction; publishing performs
    # filesystem work and must not keep this request's database connection open.
    with connect() as c:
        rel=c.execute('SELECT * FROM data_releases WHERE id=?',(release_id,)).fetchone()
        if not rel: raise HTTPException(404,'Release not found')
        if rel['approved_by'] != u['uid'] and u['role'] != 'SUPER_ADMIN': raise HTTPException(403,'Only the approving admin or a super admin can publish this release')
        job_id=int(rel['source_job_id'])
    try:
        result = publish_release(job_id, release_id)
        invalidate_public_caches()
        return result
    except ValueError as e: raise HTTPException(409,str(e))
    except Exception:
        log.exception('Release publish failed: release_id=%s', release_id)
        raise HTTPException(500,'Release publication failed; check the release timeline or server logs')

@app.get('/admin/releases', response_class=HTMLResponse)
def releases_page_route(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    return releases_page()


@app.get('/admin/rollback', response_class=HTMLResponse)
def rollback_page_route(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    return releases_page(active='rollback', title='Rollback History')

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
        # Dashboard production records are actual CAP facts, not reference rows.
        # Institutes/programs are dimensions and must not inflate this KPI.
        production=sum(c.execute(f'SELECT COUNT(*) n FROM {t}').fetchone()['n'] for t in ['cutoffs','seats'])
        activity=c.execute("""
            SELECT TO_CHAR(d.day,'Mon DD') AS label, COUNT(j.id) AS count
            FROM generate_series(CURRENT_DATE - INTERVAL '6 day', CURRENT_DATE, INTERVAL '1 day') AS d(day)
            LEFT JOIN import_jobs j
              ON j.created_at >= d.day
             AND j.created_at < d.day + INTERVAL '1 day'
            GROUP BY d.day
            ORDER BY d.day
        """).fetchall()
        storage_ok=IMPORTS.exists() and IMPORTS.is_dir()
        site_ok=SITE.exists() and (SITE/'index.html').exists()
        return {'imports_today':imports_today,'pending_review':pending,'production_rows':production,
                'activity':[dict(r) for r in activity],
                'health':{'ok':storage_ok and site_ok,'application':True,'database':True,'storage':storage_ok,'site':site_ok}}

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
    with connect() as c:
        sync_institutes_to_resolver(c)
        c.commit()
        rows=[dict(r) for r in c.execute(
            """SELECT i.institution_code,
                      COALESCE(r.institution_name,i.institution_name) AS institution_name,
                      COALESCE(r.city,i.city) AS city,
                      COALESCE(r.website,i.website) AS website,
                      COALESCE(r.status,'PENDING') AS status,
                      COALESCE(r.source,i.website_source) AS source,
                      COALESCE(r.source_url,i.website) AS source_url,
                      r.address, r.city_source, r.website_source, r.address_source,
                      r.verification_note, r.last_checked_at, r.updated_at
               FROM institutes i
               LEFT JOIN college_website_resolver r
                 ON r.institution_code=i.institution_code
              ORDER BY LOWER(COALESCE(r.institution_name,i.institution_name))
              LIMIT 5000"""
        )]
    return resolver_page(rows)

@app.get('/admin/api/resolver')
def resolver_api(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER'})
    with connect() as c:
        sync_institutes_to_resolver(c)
        c.commit()
        return [dict(r) for r in c.execute(
            """SELECT i.institution_code,
                      COALESCE(r.institution_name,i.institution_name) AS institution_name,
                      COALESCE(r.city,i.city) AS city,
                      COALESCE(r.website,i.website) AS website,
                      COALESCE(r.status,'PENDING') AS status,
                      COALESCE(r.source,i.website_source) AS source,
                      COALESCE(r.source_url,i.website) AS source_url,
                      r.address, r.city_source, r.website_source, r.address_source,
                      r.verification_note, r.last_checked_at, r.updated_at
               FROM institutes i
               LEFT JOIN college_website_resolver r
                 ON r.institution_code=i.institution_code
              ORDER BY LOWER(COALESCE(r.institution_name,i.institution_name))
              LIMIT 5000"""
        )]

@app.post('/admin/api/resolver/seed')
def resolver_seed(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN'}, csrf=True)
    with connect() as connection:
        count = sync_institutes_to_resolver(connection)
        connection.commit()
        return {'ok': True, 'count': count, 'source': 'cap_institutes'}

@app.post('/admin/api/resolver/github-seed')
def resolver_github_seed(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN'}, csrf=True)
    raise HTTPException(410, 'GitHub seed is disabled; resolver scope is the CAP institutes table')

@app.post('/admin/api/resolver/next')
def resolver_next(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN'}, csrf=True)
    if not os.getenv('GEMINI_API_KEY', '').strip():
        return {
            'ok': True,
            'configured': False,
            'busy': False,
            'processed': 0,
            'remaining': 0,
            'reason': 'Gemini AI resolver is not configured: GEMINI_API_KEY is missing.',
        }
    busy, reason = _resolver_server_busy()
    if busy:
        with connect() as c:
            pending = c.execute("SELECT COUNT(*) AS n FROM college_website_resolver WHERE status IN ('PENDING','CANDIDATE','NEEDS_REVIEW')").fetchone()['n']
        return {'ok': True, 'busy': True, 'reason': reason, 'processed': 0, 'remaining': int(pending)}
    try:
        with connect() as c:
            current = c.execute(
                "SELECT institution_code,institution_name,status FROM college_website_resolver "
                "WHERE status IN ('PENDING','CANDIDATE','NEEDS_REVIEW') "
                "ORDER BY CASE status WHEN 'CANDIDATE' THEN 0 WHEN 'PENDING' THEN 1 "
                "WHEN 'NEEDS_REVIEW' THEN 2 ELSE 3 END, LOWER(institution_name) LIMIT 1"
            ).fetchone()
        result = resolve_import_job(None, limit=1)
        return {'ok': True, 'busy': False,
                'current': dict(current) if current else None,
                'processed': result.get('resolved', 0) + result.get('failed', 0), **result}
    except Exception as exc:
        log.exception('Single resolver step failed')
        raise HTTPException(500, f'Resolver step failed: {str(exc)[:300]}')


@app.post('/admin/api/resolver/find')
async def resolver_find(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN'}, csrf=True)
    try: body=await request.json()
    except Exception: body={}
    ids=[str(x).strip() for x in body.get('ids',[]) if str(x).strip()][:25]
    force_research=bool(body.get('force_research'))
    excluded_website=str(body.get('exclude_website') or '').strip()
    if not ids: raise HTTPException(400,'No colleges selected')
    results=[]
    with connect() as c:
        for code in ids:
            row=c.execute('SELECT * FROM college_website_resolver WHERE institution_code=?',(code,)).fetchone()
            if not row: continue
            r = dict(row)
            candidate = r.get('website')
            v = ({'ok': False, 'url': None, 'note': 'Forced AI re-research after website rejection'}
                 if force_research else (verify_url(candidate, r['institution_name']) if candidate else {'ok': False}))
            if v.get('ok'):
                try:
                    ai_check = gemini_verify_candidate(r['institution_name'], v['url'], r.get('city'))
                    ai_conf = float(ai_check.get('confidence') or 0)
                    ai_url = ai_check.get('official_url')
                except Exception as exc:
                    ai_check = {'verified': False, 'confidence': 0, 'official_url': None,
                                'note': f'AI verification failed: {exc}'}
                    ai_conf = 0
                    ai_url = None
                if bool(ai_check.get('verified')) and ai_conf >= 0.70 and (not ai_url or _same_site(v['url'], ai_url)):
                    note = (ai_check.get('note') or '') + ' ' + v.get('note', '')
                    c.execute(
                        'UPDATE college_website_resolver SET website=?,status=?,source=?,verification_note=?,last_checked_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE institution_code=?',
                        (v['url'], 'VERIFIED', r.get('source') or 'reference_csv', note, code),
                    )
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
                        'note': note,
                    })
                    continue
            try:
                ai, _ = gemini_find(r['institution_name'], r.get('city'), excluded_website if force_research else None)
                url = ai.get('official_url')
                city = str(ai.get('city')).strip() if ai.get('city') else r.get('city')
                address = str(ai.get('address')).strip() if ai.get('address') else None
                v = (
                    verify_url(url, r['institution_name'])
                    if url
                    else {'ok': False, 'url': None, 'note': 'Gemini returned no official URL'}
                )
                ai_check = {}
                if v.get('ok'):
                    try:
                        ai_check = gemini_verify_candidate(r['institution_name'], v['url'], city)
                    except Exception as exc:
                        ai_check = {'verified': False, 'confidence': 0, 'official_url': None,
                                    'note': f'AI verification failed: {exc}'}
                ai_conf = float(ai_check.get('confidence') or 0)
                ai_url = ai_check.get('official_url')
                verified_by_ai = bool(ai_check.get('verified')) and ai_conf >= 0.70 and (
                    not ai_url or _same_site(v.get('url'), ai_url)
                )
                status = 'VERIFIED' if verified_by_ai else ('NEEDS_REVIEW' if v.get('ok') else 'FAILED')
                note = ' '.join(x for x in (
                    (ai.get('note') or ''),
                    (ai_check.get('note') or ''),
                    v.get('note', ''),
                ) if x)
                c.execute('UPDATE college_website_resolver SET city=?,website=?,address=?,status=?,source=?,source_url=?,verification_note=?,last_checked_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE institution_code=?',(city,v.get('url') or url,address,status,'gemini_google_search',v.get('url') or url,note,code))
                if city or address or (verified_by_ai and v.get('url')):
                    c.execute('UPDATE institutes SET city=COALESCE(?,city), address=COALESCE(?,address), website=COALESCE(?,website), city_source=CASE WHEN ? IS NOT NULL THEN ? ELSE city_source END, address_source=CASE WHEN ? IS NOT NULL THEN ? ELSE address_source END, website_source=CASE WHEN ? IS NOT NULL THEN ? ELSE website_source END, verified_at=CURRENT_TIMESTAMP WHERE institution_code=?',(city,address,v.get('url') if verified_by_ai else None,city,'gemini_google_search',address,'gemini_google_search',v.get('url') if verified_by_ai else None,'gemini_google_search',code))
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

@app.post('/admin/api/resolver/verify')
async def resolver_manual_verify(request: Request):
    u=require(request, {'SUPER_ADMIN','DATA_ADMIN'}, csrf=True)
    try:
        body=await request.json()
    except Exception:
        body={}
    code=str(body.get('institution_code','')).strip()
    posted_name=str(body.get('institution_name','')).strip()
    posted_website=str(body.get('website','')).strip()
    if not code and not posted_website and not posted_name:
        raise HTTPException(400,'College identity is required')
    with connect() as c:
        row=None
        if code:
            row=c.execute('SELECT institution_code,institution_name,city,website,status FROM college_website_resolver WHERE institution_code=?',(code,)).fetchone()
        # The browser row can outlive a resolver sync. Fall back to the exact
        # website or college name that was rendered in that row.
        if not row and posted_website:
            row=c.execute('SELECT institution_code,institution_name,city,website,status FROM college_website_resolver WHERE LOWER(TRIM(website))=LOWER(TRIM(?))',(posted_website,)).fetchone()
        if not row and posted_name:
            row=c.execute('SELECT institution_code,institution_name,city,website,status FROM college_website_resolver WHERE LOWER(TRIM(institution_name))=LOWER(TRIM(?))',(posted_name,)).fetchone()
        if not row and code:
            institute=c.execute('SELECT institution_code,institution_name,city,website FROM institutes WHERE institution_code=?',(code,)).fetchone()
            if institute:
                row=dict(institute)
                row['status']='PENDING'
        if not row:
            raise HTTPException(404,'College not found in current CAP data')
        code=str(row['institution_code']).strip()
        website=str(row['website'] or '').strip()
        if not website:
            raise HTTPException(409,'This college has no website URL to verify')
        old_status=str(row['status'] or '')
        note='Manually verified by admin after checking the website.'
        c.execute("INSERT INTO college_website_resolver (institution_code,institution_name,city,website,status,source,source_url,verification_note,last_checked_at,updated_at) VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) ON CONFLICT (institution_code) DO UPDATE SET institution_name=excluded.institution_name,city=COALESCE(excluded.city,college_website_resolver.city),website=excluded.website,status='VERIFIED',source='manual_admin',source_url=excluded.source_url,verification_note=excluded.verification_note,last_checked_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP",(code,row['institution_name'],row['city'],website,'VERIFIED','manual_admin',website,note))
        c.execute("UPDATE institutes SET website=?,website_source='manual_admin',verified_at=CURRENT_TIMESTAMP WHERE institution_code=?",(website,code))
        c.execute("INSERT INTO audit_log (actor_user_id,action,entity_type,entity_id,before_json,after_json,reason) VALUES (?,?,?,?,?,?,?)",(u['uid'],'MANUAL_VERIFY_WEBSITE','INSTITUTE',code,json.dumps({'status':old_status,'website':website}),json.dumps({'status':'VERIFIED','website':website}),'Admin manually checked the website and marked it verified'))
        c.commit()
    return {'ok':True,'institution_code':code,'status':'VERIFIED','website':website}

@app.get('/admin/audit', response_class=HTMLResponse)
def audit_page_route(request: Request):
    require(request, {'SUPER_ADMIN','DATA_ADMIN','REVIEWER','READ_ONLY'})
    with connect() as c: rows=[dict(r) for r in c.execute('SELECT a.*,u.username FROM audit_log a LEFT JOIN admin_users u ON u.id=a.actor_user_id ORDER BY a.id DESC LIMIT 200')]
    return audit_page(rows)
