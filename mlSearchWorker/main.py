# mlSearchWorker/main.py
"""
ML Search Worker
- Dequeue jobs from dbo.ml_jobs using sp_ml_jobs action=4
- If 403 PolicyAgent: mark retry w/ not_before backoff
- If success: create search_run and insert results with sp_ml_search_runs
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import azure.functions as func

from shared.db import exec_sp_json
from shared.ml_api import ml_search

logger = logging.getLogger(__name__)

# -----------------------------
# Constants
# -----------------------------
DEFAULT_LOCK_SECONDS = 120
MAX_ATTEMPTS_DEFAULT = 6


# -----------------------------
# Helpers
# -----------------------------
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


# -----------------------------
# DB helpers
# -----------------------------
def dequeue_one(job_type: str, locked_by: str, lock_seconds: int):
    """
    Dequeue ONE job using sp_ml_jobs action=4
    """

    payload = {
        "jobs": [{
            "action": 4,
            "job_type": job_type,
            "locked_by": locked_by,
            "lock_seconds": lock_seconds
        }]
    }

    sp = exec_sp_json("dbo.sp_ml_jobs", payload)

    logger.info(
        "dequeue_one => job_type=%s locked_by=%s lock_seconds=%s sp_type=%s",
        job_type, locked_by, lock_seconds, type(sp)
    )

    # Normalize SP response
    if sp is None:
        res = []
    elif isinstance(sp, dict):
        res = sp.get("result") or []
    elif isinstance(sp, list):
        res = sp
    else:
        res = []

    row0 = res[0] if res else None
    if not row0:
        return None

    # value == "1" means job dequeued
    if str(row0.get("value", "")) != "1":
        return None

    return row0


def update_job(
    job_id: int,
    status: str,
    unlock: int = 1,
    payload_patch: Optional[Dict[str, Any]] = None,
    last_error: Optional[Dict[str, Any]] = None
) -> None:
    payload = {
        "jobs": [{
            "action": 2,
            "job_id": job_id,
            "status": status,
            "unlock": unlock,
            "payload_patch": payload_patch,
            "last_error": last_error
        }]
    }
    exec_sp_json("dbo.sp_ml_jobs", payload)


def create_search_run(
    site_id: str,
    query_text: str,
    domain_id: Optional[str],
    status: str,
    http_status: Optional[int] = None,
    error_json: Optional[Dict[str, Any]] = None,
    results: Optional[list] = None
) -> None:
    sr = {
        "action": 1,
        "site_id": site_id,
        "query_text": query_text,
        "domain_id": domain_id,
        "status": status,
        "http_status": http_status,
        "error_json": error_json
    }

    if results is not None:
        sr["results"] = results

    payload = {"search_runs": [sr]}
    exec_sp_json("dbo.sp_ml_search_runs", payload)


# -----------------------------
# ML API via Backend Proxy
# -----------------------------
def try_ml_public_search(
    payload: Dict[str, Any]
) -> Tuple[bool, Optional[int], Optional[Dict[str, Any]], Optional[list]]:
    """
    Call ML search via backend proxy.
    
    Routes through smartloansbackend.azurewebsites.net/ml/search
    The backend handles ML authentication and browser headers.
    
    Return:
      (ok, http_status, error_json, results)
    """
    query_text = payload.get("query_text", "")
    category = payload.get("category")
    seller_id = payload.get("seller_id")
    offset = payload.get("offset", 0)
    limit = payload.get("limit", 50)
    
    try:
        results = ml_search(
            q=query_text,
            category=category,
            seller_id=seller_id,
            offset=offset,
            limit=limit
        )
        logger.info(f"ML search returned {len(results.get('results', []))} results")
        return (True, 200, None, results)
    except requests.exceptions.HTTPError as e:
        error_json = None
        if e.response is not None:
            try:
                error_json = e.response.json()
            except Exception:
                error_json = {"msg": e.response.text, "status": e.response.status_code}
        logger.error(f"ML search HTTP error: {e.response.status_code if e.response else 'unknown'}")
        return (False, e.response.status_code if e.response else 500, error_json, None)
    except Exception as e:
        logger.exception(f"ML search exception: {e}")
        error_json = {"type": "exception", "msg": str(e)}
        return (False, 500, error_json, None)


def backoff_not_before(attempts: int) -> str:
    # exponential backoff, capped at 60 minutes
    minutes = min(2 ** max(0, attempts - 1), 60)
    return _iso(_utc_now() + timedelta(minutes=minutes))


# -----------------------------
# Azure Function entrypoint
# -----------------------------
def run_ml_search_worker(mytimer: func.TimerRequest) -> None:
    """
    Entry point called by function_app.py (timer trigger)
    """
    logger.info("mlSearchWorker fired")

    locked_by = os.getenv("WORKER_ID", "ml_worker_01")
    job_type = os.getenv("ML_JOB_TYPE", "search")
    lock_seconds = int(os.getenv("ML_LOCK_SECONDS", str(DEFAULT_LOCK_SECONDS)))

    job = dequeue_one(
        job_type=job_type,
        locked_by=locked_by,
        lock_seconds=lock_seconds
    )

    if not job:
        logger.info("mlSearchWorker: no jobs")
        return

    job_id = int(job["job_id"])
    payload = job.get("payload_json") or {}

    site_id = payload.get("site_id", "MLM")
    query_text = payload.get("query_text")
    domain_id = payload.get("domain_id")
    max_attempts = int(payload.get("max_attempts", MAX_ATTEMPTS_DEFAULT))

    if not query_text:
        logger.error("Job missing query_text. Marking dead.")
        update_job(
            job_id,
            status="dead",
            unlock=1,
            last_error={"msg": "missing query_text"}
        )
        return

    logger.info(
        "Processing job_id=%s query='%s' domain='%s'",
        job_id, query_text, domain_id
    )

    ok, http_status, err, results = try_ml_public_search(payload)

    # -----------------------------
    # Failure path
    # -----------------------------
    if not ok:
        create_search_run(
            site_id=site_id,
            query_text=query_text,
            domain_id=domain_id,
            status="failed",
            http_status=http_status,
            error_json=err,
            results=None
        )

        attempts = 0
        try:
            attempts = int((job.get("job_json") or {}).get("attempts") or 0)
        except Exception:
            attempts = 0

        if attempts >= max_attempts:
            logger.warning(
                "job_id=%s reached max_attempts=%s. Marking dead.",
                job_id, max_attempts
            )
            update_job(
                job_id,
                status="dead",
                unlock=1,
                last_error=err
            )
            return

        nb = backoff_not_before(attempts)
        logger.warning(
            "job_id=%s failed http=%s. Retrying at %s",
            job_id, http_status, nb
        )

        update_job(
            job_id,
            status="retry",
            unlock=1,
            payload_patch={"not_before": nb},
            last_error=err
        )
        return

    # -----------------------------
    # Success path
    # -----------------------------
    create_search_run(
        site_id=site_id,
        query_text=query_text,
        domain_id=domain_id,
        status="completed",
        http_status=http_status,
        error_json=None,
        results=results or []
    )

    update_job(job_id, status="done", unlock=1)
    logger.info("job_id=%s completed", job_id)

