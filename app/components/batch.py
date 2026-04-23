"""Batch job queue for running multiple pipeline configurations."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import streamlit as st

from lidar_pipeline.runner import build_command, run_pipeline


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    input_dir: str
    output_dir: str
    params: dict
    status: JobStatus = JobStatus.PENDING
    result: Optional[dict] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @property
    def label(self) -> str:
        return f"{Path(self.input_dir).name} → {Path(self.output_dir).name}"

    @property
    def elapsed(self) -> str:
        if self.started_at and self.finished_at:
            secs = self.finished_at - self.started_at
            return f"{secs / 60:.1f} min"
        if self.started_at:
            secs = time.time() - self.started_at
            return f"{secs / 60:.1f} min (running)"
        return "—"


def _get_queue() -> list[Job]:
    if "batch_queue" not in st.session_state:
        st.session_state.batch_queue = []
    return st.session_state.batch_queue


def add_job(input_dir: str, output_dir: str, params: dict) -> Job:
    """Add a job to the batch queue."""
    job = Job(
        id=uuid.uuid4().hex[:8],
        input_dir=input_dir,
        output_dir=output_dir,
        params=params,
    )
    _get_queue().append(job)
    return job


def _run_job(job: Job):
    """Execute a single job (called from thread)."""
    job.status = JobStatus.RUNNING
    job.started_at = time.time()
    try:
        Path(job.output_dir).mkdir(parents=True, exist_ok=True)
        result = run_pipeline(
            job.input_dir,
            job.output_dir,
            **job.params,
        )
        job.result = result
        job.status = JobStatus.COMPLETE if result["success"] else JobStatus.FAILED
    except Exception as exc:
        job.result = {"success": False, "exit_code": -1, "errors": [str(exc)], "warnings": []}
        job.status = JobStatus.FAILED
    finally:
        job.finished_at = time.time()


def run_batch():
    """Run all pending jobs sequentially in a background thread."""
    def _worker():
        for job in _get_queue():
            if job.status == JobStatus.PENDING:
                _run_job(job)
        st.session_state.batch_running = False

    st.session_state.batch_running = True
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def render_batch_panel(params_dict: dict):
    """Render the batch processing UI."""
    st.subheader("📋 Batch Queue")

    queue = _get_queue()
    is_running = st.session_state.get("batch_running", False)

    if queue:
        for job in queue:
            icon = {
                JobStatus.PENDING: "⏳",
                JobStatus.RUNNING: "🔄",
                JobStatus.COMPLETE: "✅",
                JobStatus.FAILED: "❌",
            }[job.status]
            st.text(f"{icon} [{job.id}] {job.label}  {job.elapsed}")

        st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("➕ Add Current Config", disabled=is_running, use_container_width=True):
            input_dir = params_dict.pop("input_dir", "")
            output_dir = params_dict.pop("output_dir", "")
            if input_dir and output_dir:
                add_job(input_dir, output_dir, params_dict)
                st.rerun()
            else:
                st.warning("Set input and output directories first.")

    with col2:
        pending = [j for j in queue if j.status == JobStatus.PENDING]
        if st.button(
            f"🚀 Run {len(pending)} Job(s)",
            disabled=is_running or not pending,
            type="primary",
            use_container_width=True,
        ):
            run_batch()
            st.rerun()

    with col3:
        if st.button("🗑️ Clear Queue", disabled=is_running, use_container_width=True):
            st.session_state.batch_queue = []
            st.rerun()

    if is_running:
        st.info("⏳ Batch is running... click Refresh to check progress.")
        if st.button("🔄 Refresh"):
            st.rerun()
