"""
Publish Jobs Worker

This module processes publish jobs from the database, calling external APIs
(Amazon, ML, etc.) and updating job status accordingly.
"""

import json
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import azure.functions as func
from shared.db import get_conn, exec_sp_json, DatabaseConnectionError, DatabaseExecutionError

# Configure module logger
logger = logging.getLogger(__name__)

# Configuration constants
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 300.0  # 5 minutes max delay
RETRY_BACKOFF_MULTIPLIER = 2.0
CIRCUIT_BREAKER_THRESHOLD = 5  # failures before opening circuit
CIRCUIT_BREAKER_TIMEOUT = 60  # seconds before trying again


class JobStatus(Enum):
    """Enum for job status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"


class CircuitState(Enum):
    """Enum for circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external API calls.
    
    Prevents cascading failures by stopping requests to a failing service.
    """
    
    def __init__(
        self,
        failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD,
        recovery_timeout: int = CIRCUIT_BREAKER_TIMEOUT
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = False
    
    def record_success(self):
        """Record a successful call and close the circuit if open."""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info("Circuit breaker: recovered from open state")
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success for sliding window
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker: opened after {self.failure_count} failures. "
                f"Will retry after {self.recovery_timeout} seconds."
            )
    
    def can_execute(self) -> bool:
        """Check if the circuit allows execution."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker: attempting recovery (half-open)")
                    return True
            return False
        
        # HALF_OPEN - allow single attempt
        return True
    
    def reset(self):
        """Reset the circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None


# Global circuit breaker for external API calls
circuit_breaker = CircuitBreaker()


def calculate_backoff(retry_count: int) -> float:
    """
    Calculate exponential backoff delay with jitter.
    
    Args:
        retry_count: Current retry attempt number (0-indexed).
        
    Returns:
        Delay in seconds before next retry.
    """
    base_delay = min(
        INITIAL_RETRY_DELAY * (RETRY_BACKOFF_MULTIPLIER ** retry_count),
        MAX_RETRY_DELAY
    )
    # Add random jitter (±20%)
    jitter = base_delay * 0.2 * random.uniform(-1, 1)
    return max(0, base_delay + jitter)


def validate_job_payload(job: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate job payload has required fields.
    
    Args:
        job: Job dictionary from database.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    required_fields = ["jobId", "draftId"]
    
    for field in required_fields:
        if field not in job:
            return False, f"Missing required field: {field}"
        if job[field] is None:
            return False, f"Required field is null: {field}"
    
    # Validate field types
    try:
        int(job["jobId"])
        int(job["draftId"])
    except (TypeError, ValueError):
        return False, "jobId and draftId must be convertible to integers"
    
    return True, None


def parse_payload_json(payload_json: Any) -> Optional[Dict[str, Any]]:
    """
    Safely parse JSON payload from job.
    
    Args:
        payload_json: Raw payload value (string or dict).
        
    Returns:
        Parsed dictionary or None if parsing fails.
    """
    if payload_json is None:
        return None
    
    if isinstance(payload_json, dict):
        return payload_json
    
    if isinstance(payload_json, str):
        try:
            return json.loads(payload_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse payload JSON: {str(e)}")
            return None
    
    logger.warning(f"Unexpected payload type: {type(payload_json)}")
    return None


def call_external_api(job: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Call external API to publish job.
    
    This is a placeholder for actual Amazon/ML API integration.
    
    Args:
        job: Job dictionary with payload.
        
    Returns:
        Tuple of (success, error_message).
    """
    payload = parse_payload_json(job.get("payloadJson"))
    
    if payload is None and job.get("payloadJson"):
        return False, "Failed to parse payload JSON"
    
    # Check circuit breaker
    if not circuit_breaker.can_execute():
        return False, "Circuit breaker is open - service unavailable"
    
    try:
        # TODO: Implement actual external API call here
        # Example:
        # response = requests.post(
        #     f"https://api.example.com/publish",
        #     json=payload,
        #     headers={"Authorization": f"Bearer {api_key}"},
        #     timeout=30
        # )
        # response.raise_for_status()
        
        # Simulating successful API call
        logger.info(f"Calling external API for jobId={job['jobId']}")
        time.sleep(0.1)  # Simulate network latency
        
        circuit_breaker.record_success()
        return True, None
        
    except Exception as e:
        error_msg = f"External API call failed: {str(e)}"
        logger.error(error_msg)
        circuit_breaker.record_failure()
        return False, error_msg


def update_publish_job(
    job_id: int,
    draft_id: int,
    status: str,
    next_retry_at: Optional[str] = None,
    last_error: Optional[str] = None,
    action: int = 2
) -> bool:
    """
    Update job status in database.
    
    Args:
        job_id: Job ID.
        draft_id: Draft ID.
        status: New status value.
        next_retry_at: ISO format timestamp for next retry.
        last_error: Error message if failed.
        action: Action code for stored procedure.
        
    Returns:
        True if update successful, False otherwise.
    """
    payload = {
        "publishJobs": [{
            "jobId": job_id,
            "draftId": draft_id,
            "status": status,
            "nextRetryAt": next_retry_at,
            "lastError": last_error,
            "action": str(action)
        }]
    }
    
    try:
        result = exec_sp_json("dbo.sp_publishJobs", payload)
        logger.debug(f"Updated job {job_id} with status: {status}")
        return True
    except (DatabaseConnectionError, DatabaseExecutionError) as e:
        logger.error(f"Failed to update job {job_id}: {str(e)}")
        return False


def dequeue_jobs(batch_size: int = 10) -> List[Dict[str, Any]]:
    """
    Dequeue jobs from the database for processing.
    
    Args:
        batch_size: Maximum number of jobs to dequeue.
        
    Returns:
        List of job dictionaries.
    """
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("EXEC dbo.sp_publishJobs_next ?", batch_size)
            rows = cursor.fetchall()
            cols = [c[0] for c in cursor.description] if cursor.description else []
            jobs = [dict(zip(cols, r)) for r in rows]
            conn.commit()
            
            return jobs
            
    except (DatabaseConnectionError, DatabaseExecutionError) as e:
        logger.error(f"Failed to dequeue jobs: {str(e)}")
        return []


def process_job(job: Dict[str, Any], now: datetime) -> bool:
    """
    Process a single job.
    
    Args:
        job: Job dictionary.
        now: Current timestamp for retry scheduling.
        
    Returns:
        True if job processed successfully, False otherwise.
    """
    job_id = job["jobId"]
    draft_id = job["draftId"]
    
    logger.info(f"Processing jobId={job_id}, draftId={draft_id}")
    
    # Validate job payload
    is_valid, validation_error = validate_job_payload(job)
    if not is_valid:
        logger.error(f"Job {job_id} validation failed: {validation_error}")
        update_publish_job(job_id, draft_id, JobStatus.FAILED.value, None, validation_error)
        return False
    
    # Call external API
    success, error_msg = call_external_api(job)
    
    if success:
        if update_publish_job(job_id, draft_id, JobStatus.PUBLISHED.value, None, None):
            logger.info(f"Job {job_id} published successfully")
            return True
        else:
            logger.error(f"Job {job_id} published but failed to update status")
            return False
    else:
        # Calculate next retry with exponential backoff
        retry_count = job.get("_retry_count", 0)
        next_retry_delay = calculate_backoff(retry_count)
        next_retry_at = (now + timedelta(seconds=next_retry_delay)).isoformat()
        
        if update_publish_job(job_id, draft_id, JobStatus.FAILED.value, next_retry_at, error_msg):
            logger.warning(
                f"Job {job_id} failed (attempt {retry_count + 1}): {error_msg}. "
                f"Next retry at {next_retry_at}"
            )
        else:
            logger.error(f"Job {job_id} failed but failed to update status: {error_msg}")
        
        return False


def run_publish_jobs_worker(mytimer: func.TimerRequest) -> None:
    """
    Main entry point for the publish jobs worker.
    
    Args:
        mytimer: Azure Functions timer trigger context.
    """
    start_time = datetime.utcnow()
    
    # Log timer info
    if mytimer.past_due:
        logger.warning('The timer is past due!')
    
    logger.info("Publish jobs worker started")
    
    try:
        # Dequeue jobs
        jobs = dequeue_jobs(batch_size=10)
        
        if not jobs:
            logger.info("No jobs to process")
            return
        
        logger.info(f"Dequeued {len(jobs)} jobs for processing")
        
        # Process each job (with batch error handling - continue on failure)
        success_count = 0
        failure_count = 0
        
        for job in jobs:
            try:
                # Add retry count to job for exponential backoff
            #     job["_retry_count"] = job.get("retryCount", 0)
                if process_job(job, start_time):
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                logger.error(f"Unexpected error processing job: {str(e)}")
                failure_count += 1
        
        # Log summary
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Publish jobs worker completed: "
            f"processed={len(jobs)}, success={success_count}, "
            f"failed={failure_count}, elapsed={elapsed:.2f}s"
        )
        
    except Exception as e:
        logger.error(f"Publish jobs worker failed: {str(e)}", exc_info=True)
        raise

