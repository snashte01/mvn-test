"""Simple in-memory job store — runs tasks in background threads."""
import threading
import uuid
import time

_store = {}
_lock  = threading.Lock()


def create(fn, *args, **kwargs):
    """Start fn(*args, **kwargs) in a daemon thread, return job_id immediately."""
    job_id = uuid.uuid4().hex[:8]
    with _lock:
        _store[job_id] = {'status': 'running', 'result': None, 'ts': time.time()}
    threading.Thread(target=_run, args=(job_id, fn, args, kwargs), daemon=True).start()
    return job_id


def get(job_id):
    with _lock:
        return dict(_store.get(job_id, {}))


def _run(job_id, fn, args, kwargs):
    try:
        result = fn(*args, **kwargs)
        _set(job_id, 'done', result)
    except Exception as exc:
        import traceback
        _set(job_id, 'error',
             f'<div class="alert alert-danger"><pre>{traceback.format_exc()}</pre></div>')


def _set(job_id, status, result):
    with _lock:
        if job_id in _store:
            _store[job_id]['status'] = status
            _store[job_id]['result'] = result


def cleanup(max_age_seconds=3600):
    """Drop jobs older than max_age_seconds to avoid unbounded memory growth."""
    cutoff = time.time() - max_age_seconds
    with _lock:
        old = [k for k, v in _store.items() if v['ts'] < cutoff]
        for k in old:
            del _store[k]
