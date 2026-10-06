#!/usr/bin/env python3
"""Concurrency ladder for the CET Find API (same method as phase2_capacity.py).

Each level fires N requests at the same instant (one burst per level), exactly
like the baseline, and reports the metrics requested for the comparison.

  python3 loadtest/ladder.py --base https://TEST-SERVICE.onrender.com --mode search-identical
  python3 loadtest/ladder.py --base ...  --mode search-varied     # defeats the search cache
  python3 loadtest/ladder.py --base ...  --mode options|stats|healthz

Percentiles use the baseline's index rule: sorted[max(0, int(p*n)-1)].
"""
import argparse, json, random, statistics, threading, time, urllib.parse
import concurrent.futures
import requests

IDENT = "/api/search?course=BBA&percentile=95&city=Pune&sort=comp&page=1&page_size=50"
CITIES = ["Pune", "Mumbai", "Nagpur", "Nashik", "Thane", "Aurangabad", None]
SORTS = ["comp", "alpha", "city", "rank"]


def path_for(mode, rnd, serial):
    if mode == "search-identical":
        return IDENT
    if mode == "search-varied":
        # unique percentile per request => unique cache key => cache cannot help
        q = {"course": "BBA", "percentile": f"{rnd.uniform(40, 99.99):.4f}",
             "sort": rnd.choice(SORTS), "page": rnd.choice([1, 1, 2]), "page_size": 50}
        city = rnd.choice(CITIES)
        if city:
            q["city"] = city
        return "/api/search?" + urllib.parse.urlencode(q)
    return {"options": "/api/options", "stats": "/api/stats", "healthz": "/healthz"}[mode]


def pct(sorted_vals, p):
    return sorted_vals[max(0, int(p * len(sorted_vals)) - 1)]


def run_level(base, mode, n, timeout, seed):
    rnd = random.Random(seed)
    paths = [path_for(mode, rnd, i) for i in range(n)]
    gate = threading.Barrier(n)

    def one(i):
        gate.wait()
        t = time.perf_counter()
        try:
            r = requests.get(base + paths[i], headers={"Accept": "application/json"}, timeout=timeout)
            return r.status_code, (time.perf_counter() - t) * 1000
        except Exception as e:
            return "ERR:" + type(e).__name__, (time.perf_counter() - t) * 1000

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        res = list(ex.map(one, range(n)))
    wall = time.perf_counter() - t0
    lat = sorted(x[1] for x in res)
    st = {}
    for s, _ in res:
        st[str(s)] = st.get(str(s), 0) + 1
    ok = st.get("200", 0)
    return {"n": n, "requests": n, "200": ok,
            "429": st.get("429", 0),
            "5xx": sum(v for k, v in st.items() if k.isdigit() and 500 <= int(k) < 600),
            "errors": sum(v for k, v in st.items() if k.startswith("ERR")),
            "statuses": st, "p50_ms": round(statistics.median(lat)), "p95_ms": round(pct(lat, .95)),
            "p99_ms": round(pct(lat, .99)), "max_ms": round(lat[-1]), "wall_s": round(wall, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--mode", default="search-identical",
                    choices=["search-identical", "search-varied", "options", "stats", "healthz"])
    ap.add_argument("--levels", default="2,5,10,20,30,40,50")
    ap.add_argument("--pause", type=float, default=3.0)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-warmup", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    if not a.no_warmup:  # wake a sleeping free-tier instance; not part of the results
        t = time.perf_counter()
        try:
            requests.get(base + "/healthz", timeout=120)
        except Exception as e:
            print("warm-up failed:", e)
        print(f"warm-up /healthz {time.perf_counter()-t:.1f}s", flush=True)
    rows = []
    print(f"{'N':>3} {'req':>4} {'200':>4} {'429':>4} {'5xx':>4} {'err':>4} {'p50':>7} {'p95':>7} {'p99':>7} {'max':>7} {'wall':>6}  mode={a.mode}")
    for n in [int(x) for x in a.levels.split(",")]:
        time.sleep(a.pause)
        r = run_level(base, a.mode, n, a.timeout, a.seed + n)
        rows.append(r)
        print(f"{n:>3} {r['requests']:>4} {r['200']:>4} {r['429']:>4} {r['5xx']:>4} {r['errors']:>4} "
              f"{r['p50_ms']:>6}ms {r['p95_ms']:>6}ms {r['p99_ms']:>6}ms {r['max_ms']:>6}ms {r['wall_s']:>5}s", flush=True)
    if a.out:
        json.dump({"base": base, "mode": a.mode, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "levels": rows},
                  open(a.out, "w"), indent=2)


if __name__ == "__main__":
    main()
