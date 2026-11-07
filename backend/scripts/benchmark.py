"""Score the app against products whose right answers were checked by hand.

The 20 cases come from the reviewer's test (2026-11-07). "found" means the store
sells this exact product (in stock or out of stock); "not_listed" means it does not.

    uv run python scripts/benchmark.py                    # local backend, port 8000
    uv run python scripts/benchmark.py --api https://product-finder-api.vercel.app

Stores refuse some connections (see docs/access-check.md), so a store that could not
be checked is reported as "skipped" and left out of the score.
"""

import argparse
import json
import time

import httpx

FOUND, NOT_LISTED = "found", "not_listed"

# (amazon id, label, {platform: expected})
CASES = [
    ("B0FDB9ZCTD", "Samsung Galaxy M36 8/128", {"flipkart": FOUND, "croma": NOT_LISTED}),
    ("B0CWPC2W5V", "Samsung Galaxy A55 12/256", {"flipkart": FOUND, "croma": NOT_LISTED}),
    ("B0GS5SM6JR", "REDMI A7 Pro 5G 4/64", {"flipkart": FOUND, "croma": NOT_LISTED}),
    ("B0HJB3GZ2C", "Apple iPhone 18 Pro 512", {"flipkart": FOUND}),
    ("B0H3KZHC8L", "vivo Y31 5G 6/128", {"flipkart": FOUND, "croma": NOT_LISTED}),
    ("B0F7X5FC43", "Sony BRAVIA 2M2 55in", {"flipkart": NOT_LISTED, "croma": FOUND}),
    ("B0F7WVPWG8", "Sony BRAVIA 2M2 43in", {"flipkart": FOUND, "croma": FOUND}),
    ("B0GTZ9TSDJ", "LG 43NU870BPLA", {"flipkart": FOUND, "croma": FOUND}),
    ("B0F3JM1YP5", "Xiaomi 32in F Series", {"flipkart": FOUND, "croma": NOT_LISTED}),
    ("B0GXB76VRW", "Samsung 43in Crystal UHD", {"flipkart": NOT_LISTED, "croma": NOT_LISTED}),
    ("B0000ATCP4", "Converse Chuck Taylor Ox", {"flipkart": FOUND, "myntra": FOUND}),
    ("B0GSRDSKYD", "Nike W Court Vision Alta", {"flipkart": FOUND, "myntra": NOT_LISTED}),
    ("B0CJ55P4M8", "Skechers W Uno Lite", {"flipkart": FOUND, "myntra": FOUND}),
    ("B0DPHV2SVJ", "Nike Revolution 8", {"flipkart": FOUND, "myntra": FOUND}),
    ("B0GFN1LBFG", "adidas W Breaknet 3.0", {"flipkart": NOT_LISTED, "myntra": FOUND}),
    ("B0D9JYRZGB", "adidas Man Utd 24/25 jersey", {"flipkart": FOUND, "myntra": FOUND}),
    ("B0B4CZWYTH", "adidas TIRO 23 jersey", {"flipkart": FOUND, "myntra": FOUND}),
    ("B09167TMLD", "Puma teamLIGA jersey", {"flipkart": FOUND, "myntra": FOUND}),
    ("B0DDTH33PL", "Puma Essential polo", {"flipkart": FOUND, "myntra": NOT_LISTED}),
    ("B07XK9H5KF", "Levi's 025 tee", {"flipkart": FOUND, "myntra": FOUND}),
]


def outcome(result: dict) -> str:
    if result["status"] in ("in_stock", "out_of_stock"):
        return FOUND
    if result["status"] == "not_listed":
        return NOT_LISTED
    # A match whose stock could not be confirmed still found the right product.
    if result.get("failure_reason") == "availability_unknown":
        return FOUND
    return "skipped"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--only", help="comma-separated Amazon ids to run")
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None

    right = wrong = skipped = 0
    with httpx.Client(timeout=120) as client:
        for asin, label, expected in CASES:
            if only and asin not in only:
                continue
            response = client.post(
                f"{args.api}/api/v1/search",
                json={"amazon_url": f"https://www.amazon.in/dp/{asin}"},
            )
            job = response.json()
            # Background mode: poll until the job finishes.
            while job.get("status") in ("pending", "processing"):
                time.sleep(1)
                job = client.get(f"{args.api}/api/v1/search/{job['search_id']}").json()

            if job.get("error"):
                print(f"{label:30} STOPPED: {job['error']}")
                wrong += max(len(expected), 1)
                continue
            parts = []
            for result in job.get("results") or []:
                platform, got = result["platform"], outcome(result)
                want = expected.get(platform)
                if got == "skipped":
                    skipped += 1
                    mark = f"skipped ({result['failure_reason']})"
                elif want is None:
                    mark = got
                elif got == want:
                    right += 1
                    mark = f"ok ({got})"
                else:
                    wrong += 1
                    reasons = (result.get("closest_listing") or {}).get("reasons") or []
                    mark = f"WRONG: got {got}, want {want} {json.dumps(reasons)[:120]}"
                parts.append(f"{platform}: {mark}")
            print(f"{label:30} " + " | ".join(parts))

    total = right + wrong
    print(f"\n{right}/{total} right, {wrong} wrong, {skipped} skipped (store could not be checked)")


if __name__ == "__main__":
    main()
