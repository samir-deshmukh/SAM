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
from .admin.network import client_ip

router = APIRouter(prefix="/api", tags=["Public Portal API"])

# Rate limiting state: client_ip -> list of monotonic timestamps
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 60
RATE_LIMIT_MAX_KEYS = 5000
_request_history: dict[str, list[float]] = {}

# Current public release scope. Expand deliberately when the corresponding
# datasets have been verified and the UI is ready for them.
PUBLIC_COURSES = {"BBA"}


def check_rate_limit(request: Request):
    """Enforce bounded, per-process request limits per client IP."""
    ip = client_ip(request)
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS

    # Bound memory when requests arrive from many distinct source addresses.
    if len(_request_history) >= RATE_LIMIT_MAX_KEYS and ip not in _request_history:
        for key in list(_request_history):
            fresh = [stamp for stamp in _request_history[key] if stamp > cutoff]
            if fresh:
                _request_history[key] = fresh
            else:
                del _request_history[key]
        # Sustained high-cardinality traffic may keep every key active.
        # Eviction can weaken throttling for that key but keeps memory bounded.
        while len(_request_history) >= RATE_LIMIT_MAX_KEYS and _request_history:
            _request_history.pop(next(iter(_request_history)))

    timestamps = [stamp for stamp in _request_history.get(ip, []) if stamp > cutoff]
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        _request_history[ip] = timestamps
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Scraping protection active. Please try again shortly.",
        )

    timestamps.append(now)
    _request_history[ip] = timestamps


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


def _require_public_course(course: str) -> None:
    if course not in PUBLIC_COURSES:
        raise HTTPException(status_code=400, detail="Course is not available in the current public release.")


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
        city_rows = conn.execute(text("""
            SELECT DISTINCT i.city
            FROM institutes i
            WHERE i.city IS NOT NULL
              AND btrim(i.city) <> ''
              AND EXISTS (
                  SELECT 1
                  FROM cutoffs c
                  JOIN programs p ON p.program_id = c.program_id
                  WHERE c.institution_code = i.institution_code
                    AND p.program_family = 'BBA'
              )
            ORDER BY i.city
        """))
        cities = [str(r[0]) for r in city_rows]
    return {"cities": cities, "courses": sorted(PUBLIC_COURSES)}


@router.get("/stats")
def public_stats(request: Request):
    """Return public-facing totals calculated directly from released BBA cutoff facts."""
    check_rate_limit(request)
    try:
        engine = get_active_engine()
        if not _db_available(engine):
            raise RuntimeError("database unavailable")
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT COUNT(DISTINCT c.institution_code) AS colleges,
                       COUNT(*) AS cutoff_records,
                       COUNT(DISTINCT c.round) AS cap_rounds,
                       MAX(c.year) AS latest_year
                FROM cutoffs c
                JOIN programs p ON p.program_id = c.program_id
                WHERE p.program_family = 'BBA'
            """)).mappings().one()
        return {
            "colleges": int(row["colleges"] or 0),
            "cutoff_records": int(row["cutoff_records"] or 0),
            "cap_rounds": int(row["cap_rounds"] or 0),
            "latest_year": int(row["latest_year"] or 0),
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Public database statistics are unavailable.")


class CollegeCard(BaseModel):
    id: str
    institution_code: str
    name: str
    city: Optional[str] = None
    website: Optional[str] = None
    course: str
    cutoff: int
    percentile: float
    highest_cutoff: float
    status: str
    years_on_record: int
    history: list[dict] = []
    graph_history: list[dict] = []
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
        SELECT institution_code, is_ladies, year,
               base_category, section_code
        FROM cutoff_filter_options
        WHERE program_family = :course
          AND institution_code IN ({code_sql})
        ORDER BY institution_code, is_ladies, year,
                 base_category, section_code
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


def _legacy_search_metadata(engine, course: str, institution_codes: list[str]) -> dict[str, dict]:
    """Build the legacy result-card fields used by the public drawer."""
    if not institution_codes:
        return {}

    params = {"course": course}
    placeholders = []
    for index, code in enumerate(institution_codes):
        key = f"code_{index}"
        placeholders.append(f":{key}")
        params[key] = code

    query = text(
        f"""
        SELECT institution_code, year, low_percentile,
               high_percentile, low_rank
        FROM cutoff_college_year_summary
        WHERE program_family = :course
          AND institution_code IN ({", ".join(placeholders)})
        ORDER BY institution_code, year
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(query, params).fetchall()

    result = {}
    for row in rows:
        code = str(row[0])
        year = int(row[1])
        low_pct = float(row[2])
        high_pct = float(row[3])
        low_rank = int(row[4]) if row[4] is not None else 0
        item = result.setdefault(code, {"history": [], "graph_history": []})
        item["history"].append({
            "year": year,
            "percentile": low_pct,
            "low": low_pct,
            "high": high_pct,
            "rank": low_rank,
        })

    for item in result.values():
        item["history"].sort(key=lambda h: h["year"])
        item["graph_history"] = [
            {"year": h["year"], "low": h["low"], "high": h["high"]}
            for h in item["history"]
        ]
        if item["history"]:
            best = min(item["history"], key=lambda h: h["percentile"])
            item["percentile"] = best["percentile"]
            item["cutoff"] = best["rank"]
        else:
            item["percentile"] = 0.0
            item["cutoff"] = 0

    return result


@router.get("/colleges/{institution_code}/trend-options")
def college_trend_options(
    request: Request,
    institution_code: str,
    course: str = Query(...),
):
    """Return only the precomputed category/quota/year options for one college."""
    check_rate_limit(request)
    _require_public_course(course)
    engine = get_active_engine()
    if not _db_available(engine):
        raise HTTPException(status_code=503, detail="Public PostgreSQL data service is unavailable.")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT is_ladies, year, base_category, section_code
            FROM cutoff_filter_options
            WHERE program_family = :course AND institution_code = :institution
            ORDER BY is_ladies, year, base_category, section_code
        """), {"course": course, "institution": institution_code}).fetchall()
    options = {"0": {"years": set(), "categories": {}}, "1": {"years": set(), "categories": {}}}
    for row in rows:
        key = "1" if bool(row[0]) else "0"
        options[key]["years"].add(int(row[1]))
        options[key]["categories"].setdefault(str(row[2]), set()).add(str(row[3]))
    for value in options.values():
        value["years"] = sorted(value["years"])
        value["categories"] = [
            {"value": cat, "quotas": sorted(quotas)}
            for cat, quotas in sorted(value["categories"].items())
        ]
    return {"institution_code": institution_code, "course": course, "options": options}


@router.get("/colleges/{institution_code}/trend")
def college_trend(
    request: Request,
    institution_code: str,
    course: str = Query(...),
    category: Optional[str] = Query(None),
    quota: Optional[str] = Query(None),
    ladies: bool = Query(False),
):
    """Return precomputed trend points for one college/filter combination."""
    check_rate_limit(request)
    _require_public_course(course)
    engine = get_active_engine()
    if not _db_available(engine):
        raise HTTPException(status_code=503, detail="Public PostgreSQL data service is unavailable.")
    sql = """
        SELECT program_id, base_category, is_ladies, section_code,
               year, round, closing_percentile, closing_rank
        FROM cutoff_trend_points
        WHERE program_family = :course
          AND institution_code = :institution
          AND is_ladies = :ladies
    """
    params = {
        "course": course,
        "institution": institution_code,
        "ladies": ladies,
    }
    if category:
        sql += " AND base_category = :category"
        params["category"] = category
    if quota:
        sql += " AND section_code = :quota"
        params["quota"] = quota
    sql += " ORDER BY program_id, base_category, section_code, year, round"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    groups = {}
    for row in rows:
        key = (int(row[0]), str(row[1]), str(row[3]))
        group = groups.setdefault(key, {
            "branch": int(row[0]),
            "college": institution_code,
            "category": str(row[1]),
            "ladies": bool(row[2]),
            "section": str(row[3]),
            "points": [],
        })
        group["points"].append({
            "year": int(row[4]),
            "round": int(row[5]),
            "percentile": round(float(row[6]), 7),
            "rank": int(row[7]) if row[7] is not None else None,
        })
    return {"course": course, "college": institution_code, "groups": list(groups.values())}


@router.get("/colleges/{institution_code}/seats")
def get_college_seats(
    request: Request,
    institution_code: str,
    course: str = Query(..., description="Course family (e.g. MBA)"),
):
    """Fetch the precomputed latest seat matrix for one college."""
    check_rate_limit(request)
    _require_public_course(course)
    engine = get_active_engine()
    if not _db_available(engine):
        raise HTTPException(status_code=503, detail="Public PostgreSQL data service is unavailable.")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT capture_year, choice_code, allocation_lane, base_category,
                   gender_g, gender_l, category_total, is_total
            FROM seat_matrix_runtime
            WHERE institution_code = :institution
              AND program_family = :course
            ORDER BY choice_code, allocation_lane, base_category
        """), {"institution": institution_code, "course": course}).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="No seat matrix on file for this college.")
    capture_year = max(int(r[0]) for r in rows)
    data = {}
    for row in rows:
        choice = str(row[1])
        allocation = str(row[2])
        data.setdefault(choice, {}).setdefault(allocation, []).append({
            "category": str(row[3]),
            "G": int(row[4]) if row[4] is not None else None,
            "L": int(row[5]) if row[5] is not None else None,
            "total": int(row[6]) if row[6] is not None else None,
        })
    return {
        "institution_code": institution_code,
        "course": course,
        "capture_year": capture_year,
        "data": data,
    }


@router.get("/search", response_model=SearchResponse)
def search_colleges(
    request: Request,
    course: str = Query(..., description="Program family, e.g. MBA, MCA, BBA, BCA"),
    percentile: float = Query(
        ..., ge=0.0, le=100.0, description="Candidate CET percentile between 0 and 100"
    ),
    city: Optional[str] = Query(None, description="Optional city filter (case-insensitive)"),
    sort: str = Query("comp", pattern="^(comp|alpha|city|rank)$", description="Sort criteria"),
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

    valid_courses = sorted(PUBLIC_COURSES.intersection(available_program_families(engine)))
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

    if not summary_df.empty:
        rank_idx = raw_df.groupby("institution_code")["cutoff_percentile"].idxmin()
        rank_map = raw_df.loc[rank_idx, ["institution_code", "cutoff_rank"]].copy()
        rank_map["lowest_rank"] = pd.to_numeric(rank_map["cutoff_rank"], errors="coerce").fillna(10**9)
        summary_df = summary_df.merge(
            rank_map[["institution_code", "lowest_rank"]],
            on="institution_code",
            how="left",
        )

    if summary_df.empty:
        return SearchResponse(total=0, page=page, page_size=page_size, results=[])

    # 4. Apply sorting
    if sort == "alpha":
        summary_df = summary_df.sort_values(by="institution_name", ascending=True)
    elif sort == "city":
        summary_df = summary_df.sort_values(by=["city", "highest_cutoff"], ascending=[True, False])
    elif sort == "rank":
        summary_df = summary_df.sort_values(by="lowest_rank", ascending=True)
    else:  # default 'comp' (most competitive first)
        summary_df = summary_df.sort_values(by="highest_cutoff", ascending=False)

    total_count = len(summary_df)

    # 5. Paginate
    start_idx = (page - 1) * page_size
    paged_df = summary_df.iloc[start_idx : start_idx + page_size]

    results = []
    paged_codes = [str(v) for v in paged_df["institution_code"].tolist()]
    drawer_meta = _drawer_metadata(engine, course, paged_codes)
    legacy_meta = _legacy_search_metadata(engine, course, paged_codes)
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
                id=f"{row['institution_code']}_{course}",
                institution_code=str(row["institution_code"]),
                name=str(row["institution_name"]),
                city=str(row["city"]) if pd.notna(row["city"]) else None,
                website=str(row["website"]) if pd.notna(row["website"]) else None,
                course=course,
                cutoff=int(legacy_meta.get(str(row["institution_code"]), {}).get("cutoff", 0)),
                percentile=round(float(legacy_meta.get(str(row["institution_code"]), {}).get("percentile", cutoff_val)), 2),
                highest_cutoff=round(cutoff_val, 2),
                status=status_label,
                years_on_record=int(row["years_on_record"]),
                history=legacy_meta.get(str(row["institution_code"]), {}).get("history", []),
                graph_history=legacy_meta.get(str(row["institution_code"]), {}).get("graph_history", []),
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
