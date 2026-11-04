from __future__ import annotations

from types import SimpleNamespace

from docuflow.jobs.broker import InlineBroker, RQBroker


class RecordingRunner:
    def __init__(self) -> None:
        self.ids: list[str] = []

    def process(self, job_id: str) -> None:
        self.ids.append(job_id)


def test_inline_broker_dedupes_inflight_jobs() -> None:
    runner = RecordingRunner()
    broker = InlineBroker(runner, workers=1)  # type: ignore[arg-type]
    broker._inflight.add("job-1")
    broker.enqueue("job-1")
    assert runner.ids == []


def test_rq_broker_falls_back_inline_without_workers(monkeypatch) -> None:
    runner = RecordingRunner()
    broker = RQBroker.__new__(RQBroker)
    broker.queue = SimpleNamespace(enqueue=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("rq")))
    broker.inline = InlineBroker(runner, workers=1)  # type: ignore[arg-type]
    monkeypatch.setattr(broker, "active_worker_count", lambda: 0)
    broker.enqueue("job-42")
    broker.inline.pool.shutdown(wait=True)
    assert runner.ids == ["job-42"]


def test_rq_broker_uses_redis_when_workers_exist(monkeypatch) -> None:
    queued: list[str] = []
    runner = RecordingRunner()
    broker = RQBroker.__new__(RQBroker)
    broker.queue = SimpleNamespace(enqueue=lambda *args, **kwargs: queued.append(str(kwargs.get("job_id") or args[-1])))
    broker.inline = InlineBroker(runner, workers=1)  # type: ignore[arg-type]
    monkeypatch.setattr(broker, "active_worker_count", lambda: 2)
    broker.enqueue("job-9")
    assert queued == ["docuflow-job-9"]
    assert runner.ids == []
