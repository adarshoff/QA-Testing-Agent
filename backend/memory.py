import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

DEFAULT_SQLITE_URL = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'qa_agent.db')}"
DATABASE_URL = os.environ.get("DATABASE_URL") or DEFAULT_SQLITE_URL

engine_kwargs = {"poolclass": NullPool}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs = {"connect_args": {"check_same_thread": False}}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class ScanRecord(Base):
    __tablename__ = "designguard_scans_v2"

    scan_id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    url = Column(String, nullable=False, index=True)
    quality_score = Column(Integer, nullable=False, default=0)
    figma_match_score = Column(Integer, nullable=False, default=100)
    all_bugs = Column(JSON, nullable=False, default=list)
    functional_bugs = Column(JSON, nullable=False, default=list)
    dom_a11y_bugs = Column(JSON, nullable=False, default=list)
    security_bugs = Column(JSON, nullable=False, default=list)
    network_issues = Column(JSON, nullable=False, default=list)
    figma_deviations = Column(JSON, nullable=False, default=list)
    fixes = Column(JSON, nullable=False, default=list)
    new_bugs = Column(JSON, nullable=False, default=list)
    pages_visited = Column(JSON, nullable=False, default=list)
    performance_metrics = Column(JSON, nullable=False, default=dict)
    screenshots_meta = Column(JSON, nullable=False, default=list)
    healing_events = Column(JSON, nullable=False, default=list)
    design_tokens = Column(JSON, nullable=False, default=dict)
    design_inconsistencies = Column(JSON, nullable=False, default=list)
    design_consistency_score = Column(Integer, nullable=False, default=100)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ElementFingerprint(Base):
    """Remembers the last-known-good way to locate an interactive element on a given
    URL, so Functional QA can self-heal instead of re-discovering (and possibly
    missing) elements from scratch on every scan."""
    __tablename__ = "element_fingerprints"
    __table_args__ = (UniqueConstraint("url", "field_key", name="uq_fingerprint_url_field"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False, index=True)
    field_key = Column(String, nullable=False)
    descriptor = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


# Guarantee the schema exists as soon as this module is imported, instead of
# relying on callers (main.py, agent.py) to invoke init_db() first.
init_db()


def save_scan(data: Dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        record = ScanRecord(
            scan_id=data["scan_id"],
            user_id=data["user_id"],
            url=data["url"],
            quality_score=data.get("quality_score", 0),
            figma_match_score=data.get("figma_match_score", 100),
            all_bugs=data.get("all_bugs", []),
            functional_bugs=data.get("functional_bugs", []),
            dom_a11y_bugs=data.get("dom_a11y_bugs", []),
            security_bugs=data.get("security_bugs", []),
            network_issues=data.get("network_issues", []),
            figma_deviations=data.get("figma_deviations", []),
            fixes=data.get("fixes", []),
            new_bugs=data.get("new_bugs", []),
            pages_visited=data.get("pages_visited", []),
            performance_metrics=data.get("performance_metrics", {}),
            screenshots_meta=data.get("screenshots_meta", []),
            healing_events=data.get("healing_events", []),
            design_tokens=data.get("design_tokens", {}),
            design_inconsistencies=data.get("design_inconsistencies", []),
            design_consistency_score=data.get("design_consistency_score", 100),
            created_at=datetime.utcnow(),
        )
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"DB save error: {e}")
    finally:
        db.close()


def get_previous_scan(user_id: str, url: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        record = (
            db.query(ScanRecord)
            .filter(ScanRecord.user_id == user_id, ScanRecord.url == url)
            .order_by(ScanRecord.created_at.desc())
            .first()
        )
        if not record:
            return None
        return {
            "scan_id": record.scan_id,
            "all_bugs": record.all_bugs or [],
        }
    finally:
        db.close()


def get_user_history(user_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        records = (
            db.query(ScanRecord)
            .filter(ScanRecord.user_id == user_id)
            .order_by(ScanRecord.created_at.desc())
            .limit(20)
            .all()
        )
        return [
            {
                "scan_id": r.scan_id,
                "url": r.url,
                "created_at": r.created_at.isoformat(),
                "quality_score": r.quality_score,
                "figma_match_score": r.figma_match_score,
                "total_bugs": len(r.all_bugs or []),
                "critical_count": sum(1 for b in (r.all_bugs or []) if b.get("severity") == "critical"),
                "serious_count": sum(1 for b in (r.all_bugs or []) if b.get("severity") == "serious"),
                "moderate_count": sum(1 for b in (r.all_bugs or []) if b.get("severity") == "moderate"),
                "new_bugs_count": len(r.new_bugs or []),
                "pages_scanned": len(r.pages_visited or []),
                "network_issues": len(r.network_issues or []),
                "performance_metrics": r.performance_metrics or {},
            }
            for r in records
        ]
    finally:
        db.close()


def get_scan(scan_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        record = db.query(ScanRecord).filter(ScanRecord.scan_id == scan_id).first()
        if not record:
            return None
        return {
            "scan_id": record.scan_id,
            "user_id": record.user_id,
            "url": record.url,
            "quality_score": record.quality_score,
            "figma_match_score": record.figma_match_score,
            "all_bugs": record.all_bugs or [],
            "functional_bugs": record.functional_bugs or [],
            "dom_a11y_bugs": record.dom_a11y_bugs or [],
            "security_bugs": record.security_bugs or [],
            "network_issues": record.network_issues or [],
            "figma_deviations": record.figma_deviations or [],
            "fixes": record.fixes or [],
            "new_bugs": record.new_bugs or [],
            "pages_visited": record.pages_visited or [],
            "performance_metrics": record.performance_metrics or {},
            "screenshots_meta": record.screenshots_meta or [],
            "healing_events": record.healing_events or [],
            "design_tokens": record.design_tokens or {},
            "design_inconsistencies": record.design_inconsistencies or [],
            "design_consistency_score": record.design_consistency_score,
            "created_at": record.created_at.isoformat(),
        }
    finally:
        db.close()


def get_fingerprints(url: str) -> Dict[str, Dict[str, Any]]:
    """Load all remembered element locator descriptors for a given URL, keyed by field_key."""
    db = SessionLocal()
    try:
        records = db.query(ElementFingerprint).filter(ElementFingerprint.url == url).all()
        return {r.field_key: r.descriptor for r in records}
    finally:
        db.close()


def save_fingerprints(url: str, fingerprints: Dict[str, Dict[str, Any]]) -> None:
    """Upsert the current set of locator descriptors for a URL."""
    if not fingerprints:
        return
    db = SessionLocal()
    try:
        for field_key, descriptor in fingerprints.items():
            existing = (
                db.query(ElementFingerprint)
                .filter(ElementFingerprint.url == url, ElementFingerprint.field_key == field_key)
                .first()
            )
            if existing:
                existing.descriptor = descriptor
                existing.updated_at = datetime.utcnow()
            else:
                db.add(ElementFingerprint(
                    url=url,
                    field_key=field_key,
                    descriptor=descriptor,
                    updated_at=datetime.utcnow(),
                ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Fingerprint save error: {e}")
    finally:
        db.close()
