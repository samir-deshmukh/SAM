"""
backend/api.py — Public dynamic API for CET CAP portal.

Features:
- Dynamic PostgreSQL-backed queries (no static data files shipped to client)
- Strict input validation (Pydantic / type constraints)
- Parameterized SQL execution (SQL-injection proof)
- In-memory rate limiting to prevent automated scraping
- Server-side pagination & projection (only requested fields, bounded limit)
"""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text

# Ensure src/ is importable
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "src"))

from cet_cap.db import get_engine
from cet_cap.queries import (
    available_program_families,
    available_years,
    search_cutoffs_for_course,
    seat_matrix_for_institute,
)
from cet_cap.search import filter_by_city, summarize_colleges

router = APIRouter(prefix="/api", tags=["Public Portal API"])

# Rate limiting state: client_ip -> list of timestamps
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 60
_request_history: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(request: Request):
    """Enforce rate limits per client IP to prevent bulk data scraping."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    timestamps = _request_history[client_ip]

    # Remove timestamps older than window
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    _request_history[client_ip] = [ts for ts in timestamps if ts > cutoff]

    if len(_request_history[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Scraping protection active. Please try again shortly.",
        )

    _request_history[client_ip].append(now)


_engine_cache = None


def get_active_engine():
    """Return the single configured PostgreSQL engine for public requests."""
    global _engine_cache
    if _engine_cache is None:
        _engine_cache = get_engine()
    return _engine_cache


def _db_available(engine) -> bool:
    """Check connectivity without hiding application/database errors."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/options")
def public_options(request: Request):
    """Return the bounded city/course lists needed to initialize the search UI."""
    check_rate_limit(request)
    try:
        engine = get_active_engine()
    except Exception:
        raise HTTPException(status_code=503, detail="Public PostgreSQL data service is unavailable.")
    if not _db_available(engine):
        raise HTTPException(status_code=503, detail="Public PostgreSQL data service is unavailable.")
    with engine.connect() as conn:
        city_rows = conn.execute(text("SELECT DISTINCT i.city FROM institutes i WHERE i.city IS NOT NULL AND btrim(i.city) <> '' AND (EXISTS (SELECT 1 FROM cutoffs c WHERE c.institution_code = i.institution_code) OR EXISTS (SELECT 1 FROM seats s WHERE s.institution_code = i.institution_code)) ORDER BY i.city"))
        cities = [str(r[0]) for r in city_rows]
    return {"cities": cities, "courses": available_program_families(engine)}


class CollegeCard(BaseModel):
    institution_code: str
    name: str
    city: Optional[str] = None
    website: Optional[str] = None
    course: str
    highest_cutoff: float
    status: str
    years_on_record: int
    drawer: Optional[dict] = None


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[CollegeCard]


def _drawer_metadata(engine, course: str, institution_codes: list[str]) -> dict[str, dict]:
    """Build compact category/quota metadata for the requested colleges.

    The public search response needs only enough metadata to initialize the
    college drawer. Cutoff rows themselves stay server-side and are fetched
    by the detail endpoints. The requested code list is bounded by the
    search page-size limit, so this query cannot become an unbounded dump.
    """
    if not institution_codes:
        return {}

    placeholders = {f"code_{index}": code for index, code in enumerate(institution_codes)}
    code_sql = ", ".join(f":code_{index}" for index in range(len(institution_codes)))
    query = text(
        f"""
        SELECT c.institution_code, c.is_ladies, c.year,
               c.base_category, c.section_code
        FROM cutoffs c
        JOIN programs p ON p.program_id = c.program_id
        WHERE p.program_family = :course
          AND c.institution_code IN ({code_sql})
          AND NOT (c.rank_number = 0 AND c.percentile = 0.0)
        ORDER BY c.institution_code, c.is_ladies, c.year,
                 c.base_category, c.section_code
        """
    )
    params = {"course": course, **placeholders}

    with engine.connect() as conn:
        rows = conn.execute(query, params).fetchall()

    metadata = {}
    for row in rows:
        code = str(row[0])
        record = metadata.setdefault(
            code,
            {"y": set(), "c": {"0": {}, "1": {}}},
        )
        ladies_key = "1" if bool(row[1]) else "0"
        record["y"].add(int(row[2]))
        categories = record["c"][ladies_key]
        category = str(row[3])
        categories.setdefault(category, set()).add(str(row[4]))

    for record in metadata.values():
        record["y"] = sorted(record["y"])
        for ladies_key, categories in record["c"].items():
            record["c"][ladies_key] = [
                {"v": category, "q": sorted(sections)}
                for category, sections in sorted(categories.items())
            ]

    return metadata


@router.get("/search", response_model=SearchResponse)
def search_colleges(
    request: Request,
    course: str = Query(..., description="Program family, e.g. MBA, MCA, BBA, BCA"),
    percentile: float = Query(
        ..., ge=0.0, le=100.0, description="Candidate CET percentile between 0 and 100"
    ),
    city: Optional[str] = Query(None, description="Optional city filter (case-insensitive)"),
    sort: str = Query("comp", pattern="^(comp|alpha|city)$", description="Sort criteria"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=50, description="Items per page (max 50)"),
):
    """Searches for eligible colleges for a candidate based on percentage, course, and city.
    
    Security:
    - Rate-limited to prevent dumping the entire cutoff dataset
    - Parameterized SQLAlchemy query prevents SQL injection
    - Bounded page_size (max 50) prevents excessive memory usage or bulk dumping
    """
    check_rate_limit(request)
    try:
        engine = get_active_engine()
    except Exception:
        raise HTTPException(status_code=503, detail="Public PostgreSQL data service is unavailable.")
    if not _db_available(engine):
        raise HTTPException(status_code=503, detail="Public PostgreSQL data service is unavailable.")

    valid_courses = available_program_families(engine)
    if course not in valid_courses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid course '{course}'. Must be one of: {valid_courses}",
        )

    # 1. Fetch cutoffs at or below percentile
    raw_df = search_cutoffs_for_course(engine, percentage=percentile, program_family=course)

    # 2. Apply city filter if provided
    if city and city.strip():
        raw_df = filter_by_city(raw_df, city.strip())

    # 3. Aggregate per college
    summary_df = summarize_colleges(raw_df)

    if summary_df.empty:
        return SearchResponse(total=0, page=page, page_size=page_size, results=[])

    # 4. Apply sorting
    if sort == "alpha":
        summary_df = summary_df.sort_values(by="institution_name", ascending=True)
    elif sort == "city":
        summary_df = summary_df.sort_values(by=["city", "highest_cutoff"], ascending=[True, False])
    else:  # default 'comp' (most competitive first)
        summary_df = summary_df.sort_values(by="highest_cutoff", ascending=False)

    total_count = len(summary_df)

    # 5. Paginate
    start_idx = (page - 1) * page_size
    paged_df = summary_df.iloc[start_idx : start_idx + page_size]

    results = []
    paged_codes = [str(v) for v in paged_df["institution_code"].tolist()]
    drawer_meta = _drawer_metadata(engine, course, paged_codes)
    for _, row in paged_df.iterrows():
        # Status calculation: safe if candidate percentage >= highest cutoff
        cutoff_val = float(row["highest_cutoff"])
        if percentile >= cutoff_val + 2.0:
            status_label = "safe"
        elif percentile >= cutoff_val:
            status_label = "borderline"
        else:
            status_label = "reach"

        results.append(
            CollegeCard(
                institution_code=str(row["institution_code"]),
                name=str(row["institution_name"]),
                city=str(row["city"]) if pd.notna(row["city"]) else None,
                website=str(row["website"]) if pd.notna(row["website"]) else None,
                course=course,
                highest_cutoff=round(cutoff_val, 2),
                status=status_label,
                years_on_record=int(row["years_on_record"]),
                drawer=drawer_meta.get(str(row["institution_code"])),
            )
        )

    return SearchResponse(
        total=total_count,
        page=page,
        page_size=page_size,
        results=results,
    )


@router.get("/colleges/{institution_code}/details")
def get_college_details(
    request: Request,
    institution_code: str,
    course: str = Query(..., description="Course family (e.g. MBA)"),
):
    """Fetches cutoff trends and category breakdowns for a specific college drawer.
    Returns only data relevant to the single institution requested.
    """
    check_rate_limit(request)
    engine = get_active_engine()
    if not _db_available(engine):
        raise HTTPException(status_code=503, detail="Public PostgreSQL data service is unavailable.")

    query = text("""
        SELECT
            c.year,
            c.round,
            c.base_category,
            c.is_ladies,
            c.section_code,
            c.stage_code,
            c.percentile,
            c.rank_number,
            c.raw_category,
            p.program_name_raw
        FROM cutoffs c
        JOIN programs p ON p.program_id = c.program_id
        WHERE c.institution_code = :inst_code
          AND p.program_family = :course
          AND NOT (c.rank_number = 0 AND c.percentile = 0.0)
        ORDER BY c.year DESC, c.round ASC, c.percentile DESC
    """)

    with engine.connect() as conn:
        rows = conn.execute(
            query, {"inst_code": institution_code, "course": course}
        ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404, detail="No cutoff history found for this college and course."
        )

    # Structure into compact response
    history_by_year = defaultdict(list)
    categories = set()
    quotas = set()
    years = set()

    for r in rows:
        year = r[0]
        round_no = r[1]
        cat = r[2]
        is_ladies = bool(r[3])
        sec = r[4]
        stage = r[5]
        pct = float(r[6])
        rank = r[7]
        raw_cat = r[8]
        branch = r[9]

        years.add(year)
        categories.add(cat)
        quotas.add(sec)

        history_by_year[year].append(
            {
                "round": round_no,
                "category": cat,
                "raw_category": raw_cat,
                "is_ladies": is_ladies,
                "section": sec,
                "stage": stage,
                "percentile": pct,
                "rank": rank,
                "branch": branch,
            }
        )

    return {
        "institution_code": institution_code,
        "course": course,
        "years": sorted(list(years), reverse=True),
        "categories": sorted(list(categories)),
        "quotas": sorted(list(quotas)),
        "history": history_by_year,
    }


@router.get("/colleges/{institution_code}/year/{year}")
def get_college_year_runtime(request: Request, institution_code: str, year: int, course: str = Query(...)):
    """Return only one college/year cutoff payload. Prefer the private DB; use
    the private runtime export only for local development when DB is unavailable."""
    check_rate_limit(request)
    engine = get_active_engine()
    if _db_available(engine):
        q = text("""
            SELECT c.program_id, c.institution_code, c.base_category, c.raw_category,
                   c.is_ladies, c.section_code, c.stage_code, c.year, c.round,
                   c.percentile, c.rank_number, p.program_name_raw
            FROM cutoffs c
            JOIN programs p ON p.program_id = c.program_id
            WHERE c.institution_code = :inst
              AND p.program_family = :course
              AND c.year = :year
              AND NOT (c.rank_number = 0 AND c.percentile = 0.0)
            ORDER BY c.program_id, c.round, c.section_code, c.raw_category
        """)
        with engine.connect() as conn:
            rows = conn.execute(q, {"inst": institution_code, "course": course, "year": year}).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail='Cutoff data not found.')
        branches={}
        categories={}
        sections={}
        pdf_rows=[]
        for r in rows:
            program_id=str(r[0]); branch=str(r[11] or program_id)
            branches[program_id]=branch
            cat=str(r[2] or r[3] or '')
            raw_cat=str(r[3] or r[2] or cat)
            categories[cat]={'full':cat,'group':'Other'}
            sec=str(r[5] or '')
            sections[sec]=sec
            pdf_rows.append({
                'branch':program_id,'college':institution_code,'category':cat,
                'raw_category':raw_cat,'ladies':bool(r[4]),'section':sec,
                'stage':str(r[6] or f'Round {r[8]}'),'year':int(r[7]),
                'round':int(r[8]),'percentile':float(r[9]),'rank':r[10],
            })
        return {'course':course,'year':year,'college':institution_code,
                'branches':branches,'categories':categories,'sections':sections,
                'pdf_rows':pdf_rows}
    raise HTTPException(status_code=404, detail='Cutoff data not found.')


@router.get("/colleges/{institution_code}/seats")
def get_college_seats(
    request: Request,
    institution_code: str,
    course: str = Query(..., description="Course family (e.g. MBA)"),
):
    """Fetches seat matrix capacity for a single institution."""
    check_rate_limit(request)
    engine = get_active_engine()
    if not _db_available(engine):
        raise HTTPException(status_code=503, detail="Public PostgreSQL data service is unavailable.")

    df = seat_matrix_for_institute(
        engine, institution_code=institution_code, program_family=course
    )

    if df.empty:
        raise HTTPException(status_code=404, detail="No seat matrix on file for this college.")

    records = df.where(pd.notna(df), None).to_dict(orient="records")
    # JSON cannot represent NaN/Infinity; normalize any remaining float sentinels.
    for record in records:
        for key, value in list(record.items()):
            if isinstance(value, float) and not pd.notna(value):
                record[key] = None
    return {
        "institution_code": institution_code,
        "course": course,
        "capture_year": int(df["capture_year"].max()) if not df.empty else None,
        "records": records,
    }
