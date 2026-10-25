"""Prend un job et appelle le handler de son type. Aucun import métier."""

from __future__ import annotations

from collections.abc import Callable

from .file import FileMemoire, Job


def executer(file: FileMemoire, worker: str, handlers: dict[str, Callable[[Job], None]]) -> bool:
    job = file.prendre(worker)
    if job is None:
        return False
    try:
        handlers[job.type](job)
    except Exception:
        file.echouer(job.id)
        return True
    file.terminer(job.id)
    return True
