"""Raw-schema profiles written by the Airflow DAG ``governor_profile_raw`` (airflow-platform spec section 8).

    GET /profiles             {"profiles": [run_id, ...]}  newest first, at most 100
    GET /profiles/{run_id}    the stored profile JSON, byte for byte, or 404

Both read ``$GOVERNOR_STATE_DIR/profiles/<run_id>.json`` and need the same bearer token as every other
route. A ``run_id`` that does not match ``RUN_ID`` is a 422; no path is ever built from an unchecked string.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path as FsPath

from fastapi import APIRouter, Depends, Path
from fastapi.responses import Response
from starlette.exceptions import HTTPException

from governor.core import paths

RUN_ID = r"^[A-Za-z0-9_.+-]{1,128}$"
MAX_LISTED = 100
_RUN_ID = re.compile(RUN_ID)


def profiles_dir() -> FsPath:
    """``$GOVERNOR_STATE_DIR/profiles`` (relative paths from the repo root), read at request time."""
    raw = os.environ.get("GOVERNOR_STATE_DIR")
    return (paths.ROOT / raw if raw else paths.STATE) / "profiles"


def _stored(run_id: str) -> FsPath | None:
    """The file for a valid ``run_id`` inside the profiles folder, or None."""
    if not _RUN_ID.fullmatch(run_id):
        return None
    folder = profiles_dir().resolve()
    file = (folder / f"{run_id}.json").resolve()
    if file.parent != folder or not file.is_file():
        return None
    return file


def list_run_ids(limit: int = MAX_LISTED) -> list[str]:
    folder = profiles_dir()
    if not folder.is_dir():
        return []
    found = [(f.stat().st_mtime, f.stem) for f in folder.glob("*.json") if f.is_file() and _RUN_ID.fullmatch(f.stem)]
    found.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [stem for _, stem in found[:limit]]


def make_router(auth_dependency: Callable) -> APIRouter:
    router = APIRouter(dependencies=[Depends(auth_dependency)])

    @router.get("/profiles")
    def list_profiles() -> dict:
        return {"profiles": list_run_ids()}

    @router.get("/profiles/{run_id}")
    def get_profile(run_id: str = Path(pattern=RUN_ID)) -> Response:
        file = _stored(run_id)
        if file is None:
            raise HTTPException(404)
        return Response(content=file.read_bytes(), media_type="application/json")

    return router


__all__ = ["MAX_LISTED", "RUN_ID", "list_run_ids", "make_router", "profiles_dir"]
