"""Admin page: server-rendered forms for cleaning up contributed data.

Mounted at `/admin` (not under `/api`). Every route requires a signed-in user whose role
is `Admin`; everyone else gets a 404, so the page does not advertise itself. Actions are
plain form POSTs that redirect back with a message. The session cookie is SameSite=Lax,
so another site cannot submit these forms on an admin's behalf.
"""

from typing import Any
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.constants import Roles
from app.db.session import get_db
from app.models import User
from app.services import openopus
from app.services.admin_service import AdminError, AdminService

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(include_in_schema=False)


async def require_admin(
    current_user: User | None = Depends(deps.get_current_user_optional),
) -> User:
    if current_user is None or current_user.role != Roles.ADMIN:
        raise HTTPException(status_code=404, detail="Not Found")
    return current_user


async def _form(request: Request) -> dict[str, str]:
    """Fields of a urlencoded form post (first value of each)."""
    body = (await request.body()).decode("utf-8", errors="replace")
    return {key: values[0] for key, values in parse_qs(body, keep_blank_values=True).items()}


def _int(form: dict[str, str], key: str) -> int:
    try:
        return int(form.get(key, ""))
    except ValueError:
        raise AdminError("Falta elegir un elemento.") from None


def _back(path: str, *, msg: str = "", error: str = "") -> RedirectResponse:
    query = f"?msg={quote(msg)}" if msg else f"?error={quote(error)}" if error else ""
    return RedirectResponse(url=f"{path}{query}", status_code=303)


async def _run(db: AsyncSession, action: Any, *, ok: str, back: str = "/admin") -> Response:
    """Run an admin action and redirect with its outcome. `action` is an awaitable
    factory so that argument errors are reported the same way as failures."""
    try:
        result = await action()
    except AdminError as e:
        await db.rollback()
        return _back(back, error=str(e))
    except IntegrityError:
        await db.rollback()
        return _back(
            back, error="La operación choca con otro dato existente; no se ha cambiado nada."
        )
    return _back(back, msg=ok.format(result=result))


@router.get("", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    msg: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> HTMLResponse:
    context = await AdminService.get_overview(db)
    context.update({"user": admin, "msg": msg, "error": error})
    return templates.TemplateResponse(request, "admin.html", context)


@router.post("/reports/{report_id}/clear-flag")
async def clear_flag(
    report_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> Response:
    return await _run(db, lambda: AdminService.clear_flag(db, report_id), ok="Marca retirada.")


@router.post("/reports/{report_id}/delete")
async def delete_report(
    report_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> Response:
    return await _run(
        db, lambda: AdminService.delete_report(db, report_id), ok="Reporte eliminado."
    )


@router.post("/events/delete-empty")
async def delete_empty_events(
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> Response:
    return await _run(
        db,
        lambda: AdminService.delete_empty_events(db),
        ok="Convocatorias vacías eliminadas: {result}.",
    )


@router.post("/works/merge")
async def merge_works(
    request: Request, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> Response:
    form = await _form(request)

    async def action() -> None:
        await AdminService.merge_works(db, _int(form, "source_id"), _int(form, "target_id"))

    return await _run(db, action, ok="Obras fusionadas.")


@router.get("/works/{work_id}", response_class=HTMLResponse)
async def work_page(
    request: Request,
    work_id: int,
    q: str = "",
    msg: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> HTMLResponse:
    try:
        work = await AdminService.get_work(db, work_id)
    except AdminError as e:
        raise HTTPException(status_code=404, detail="Not Found") from e
    try:
        candidates = await AdminService.catalogue_candidates(db, work_id, q)
    except AdminError as e:
        candidates, error = [], str(e)
    return templates.TemplateResponse(
        request,
        "admin_work.html",
        {
            "user": admin,
            "work": work,
            "q": q,
            "candidates": candidates,
            "msg": msg,
            "error": error,
        },
    )


@router.post("/works/{work_id}")
async def update_work(
    request: Request,
    work_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    form = await _form(request)
    return await _run(
        db,
        lambda: AdminService.update_work(
            db, work_id, form.get("title", ""), form.get("nickname"), form.get("imslp_url")
        ),
        ok="Obra guardada.",
        back=f"/admin/works/{work_id}",
    )


@router.post("/works/{work_id}/link")
async def link_work(
    request: Request,
    work_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    form = await _form(request)
    # After a link the work may have been merged away, so go back to the main page.
    return await _run(
        db,
        lambda: AdminService.link_work_to_catalogue(db, work_id, form.get("openopus_id", "")),
        ok="Obra vinculada al catálogo.",
    )


@router.post("/works/{work_id}/delete")
async def delete_work(
    work_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> Response:
    return await _run(db, lambda: AdminService.delete_work(db, work_id), ok="Obra eliminada.")


@router.post("/composers/merge")
async def merge_composers(
    request: Request, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> Response:
    form = await _form(request)

    async def action() -> None:
        await AdminService.merge_composers(db, _int(form, "source_id"), _int(form, "target_id"))

    return await _run(db, action, ok="Compositores fusionados.")


@router.post("/composers/rename")
async def rename_composer(
    request: Request, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
) -> Response:
    form = await _form(request)

    async def action() -> None:
        await AdminService.rename_composer(db, _int(form, "composer_id"), form.get("name", ""))

    return await _run(db, action, ok="Nombre cambiado.")


@router.get("/composers/{composer_id}", response_class=HTMLResponse)
async def composer_page(
    request: Request,
    composer_id: int,
    q: str = "",
    msg: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> HTMLResponse:
    try:
        composer = await AdminService.get_composer(db, composer_id)
    except AdminError as e:
        raise HTTPException(status_code=404, detail="Not Found") from e
    try:
        candidates = await AdminService.composer_candidates(q)
    except AdminError as e:
        candidates, error = [], str(e)
    return templates.TemplateResponse(
        request,
        "admin_composer.html",
        {
            "user": admin,
            "composer": composer,
            "q": q,
            # OpenOpus rejects short words, so "Fernando Sor" is searched as "fernando".
            "suggested_q": next(iter(openopus.name_search_terms(str(composer.name))), ""),
            "candidates": candidates,
            "msg": msg,
            "error": error,
        },
    )


@router.post("/composers/{composer_id}/link")
async def link_composer(
    request: Request,
    composer_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    form = await _form(request)
    # After a link the composer may have been merged away, so go back to the main page.
    return await _run(
        db,
        lambda: AdminService.link_composer_to_catalogue(
            db, composer_id, form.get("openopus_id", ""), form.get("q", "")
        ),
        ok="Compositor vinculado a OpenOpus. Ya puedes vincular sus obras al catálogo.",
    )
