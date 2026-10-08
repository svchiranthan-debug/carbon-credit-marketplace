#!/usr/bin/env python3
"""
READ-ONLY report on verification/credit records created before the evidence-integrity fixes.

Before those fixes the backend could (a) score NDVI from a coordinate-seeded simulation,
(b) label a random NDVI grid as "REAL SATELLITE DATA" when band files could not be read, and
(c) give a hard-coded "showcase" plot fixed scores. Such records have no ndvi_provenance.
This script lists them so you can decide what to do; it never modifies the database.

    python scripts/audit_legacy_data.py
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models.credit import Credit  # noqa: E402
from app.models.verification import Verification  # noqa: E402
from app.services.marketplace_rules import listing_check  # noqa: E402

init_db()  # additive column migration only
db = SessionLocal()
try:
    print(f"Database: {settings.DATABASE_URL}")
    scored = db.query(Verification).filter(Verification.overall_score.isnot(None)).all()
    legacy = [v for v in scored if not v.ndvi_provenance]
    print(f"Scored verifications: {len(scored)}  |  without NDVI provenance (legacy, unverifiable): {len(legacy)}")
    print("  by NDVI source label:")
    for label, n in Counter((v.satellite_source or "none")[:70] for v in legacy).most_common():
        print(f"    {n:4d}  {label}")
    print("  by decision:", dict(Counter(v.decision for v in legacy)))

    credits = db.query(Credit).all()
    reasons = Counter()
    for c in credits:
        ok, why = listing_check(c, db)
        reasons["LISTED" if ok else why] += 1
    print(f"Credits: {len(credits)}")
    for why, n in reasons.most_common():
        print(f"    {n:4d}  {why}")
finally:
    db.close()
