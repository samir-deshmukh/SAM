# Security hardening applied

This release incorporates the security fixes identified in `SECURITY_REVIEW.docx`.

## Authentication and sessions
- Login is throttled by both source address and username, with temporary lockout after repeated failures.
- Production uses Secure + HttpOnly + SameSite=Strict admin session cookies by default.
- Sessions contain an authentication version and are checked against the current database user on every authenticated request.
- Disabled users and changed roles immediately invalidate existing sessions.
- `/admin/logout` explicitly clears the session and CSRF cookies.
- The bundled database contains no admin accounts or test import/audit state.

## CSRF
- State-changing admin endpoints require a CSRF token.
- Login uses a synchronizer-style token delivered in the login form and CSRF cookie.
- Admin JavaScript sends the CSRF token on process, approve, reject, publish, and rollback requests.

## Upload and processing safety
- Failed uploads clean up both temporary and renamed PDF files.
- Import processing atomically claims a REVIEW_REQUIRED job before starting, preventing duplicate processing by concurrent requests in the same database.
- Client-facing processing/publishing failures no longer expose raw internal exception details.

## Public-site URL safety
- Institute enrichment accepts only absolute HTTP(S) URLs without embedded credentials or control characters.
- Public rendering validates the URL again and HTML-escapes it before inserting it into the link attribute.

## Database hygiene
- The empty duplicate `db/cet-cap.db` artifact was removed.
- `admin_users.auth_version` is part of the schema and is added automatically to older PostgreSQL databases.

## Important deployment notes
- Set `CET_ADMIN_SESSION_SECRET` to a long random secret in production.
- Keep `CET_ENV=production` (the default) and do not disable `CET_ADMIN_COOKIE_SECURE` in production.
- Create the first real administrator after deployment using `backend/admin/create_admin.py`; do not ship administrator credentials in source/data artifacts.
- PostgreSQL production deployment still requires validating the complete admin workflow against the target PostgreSQL schema before enabling it as the runtime database.
