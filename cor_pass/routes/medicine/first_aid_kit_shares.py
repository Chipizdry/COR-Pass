from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from urllib.parse import quote
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.schemas import (
    FirstAidKitShareAcceptRequest,
    FirstAidKitShareAcceptResponse,
    FirstAidKitShareCreateRequest,
    FirstAidKitShareResponse,
    FirstAidKitShareSendToCorIdRequest,
    FirstAidKitShareSendToEmailRequest,
)
from cor_pass.repository.medicine.first_aid_kit import get_first_aid_kit_by_id
from cor_pass.repository.medicine.first_aid_kit_share import (
    accept_share,
    create_share,
    get_share_by_id,
    get_share_by_token,
    revoke_share,
)
from cor_pass.repository.user import person as repository_person
from cor_pass.services.shared.access import user_access
from cor_pass.services.user.auth import auth_service
from cor_pass.services.shared.email import send_first_aid_kit_share_email

router = APIRouter(prefix="/first_aid_kits", tags=["First Aid Kit Shares"])


@router.post(
    "/{kit_id}/share",
    response_model=FirstAidKitShareResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
    summary="Создать ссылку для шаринга аптечки",
)
async def create_first_aid_kit_share(
    kit_id: str,
    body: FirstAidKitShareCreateRequest,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kit = await get_first_aid_kit_by_id(db=db, kit_id=kit_id, user=current_user)
    if not kit:
        raise HTTPException(status_code=404, detail="Аптечка не найдена")

    share = await create_share(
        db=db,
        kit=kit,
        from_user=current_user,
        to_user_cor_id=body.to_user_cor_id,
        to_email=body.to_email,
        expires_hours=body.expires_hours or 72,
        context=body.context,
    )
    # Build mobile deep link (no email, only share token)
    encoded_token = quote(share.token)
    deep_link = f"coridapp://open?firstAidKitShareToken={encoded_token}"

    return FirstAidKitShareResponse(
        id=share.id,
        token=share.token,
        status=share.status,
        expires_at=share.expires_at,
        deep_link=deep_link,
    )


@router.post(
    "/shares/accept",
    response_model=FirstAidKitShareAcceptResponse,
    dependencies=[Depends(user_access)],
    summary="Принять шаринг аптечки по токену",
)
async def accept_first_aid_kit_share(
    body: FirstAidKitShareAcceptRequest,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    share = await get_share_by_token(db=db, token=body.token, with_kit=True)
    if not share:
        raise HTTPException(status_code=404, detail="Приглашение не найдено")

    new_kit = await accept_share(db=db, share=share, current_user=current_user)
    return FirstAidKitShareAcceptResponse(
        share_id=share.id,
        new_kit_id=new_kit.id,
        status=share.status,
        accepted_at=share.accepted_at,
    )


@router.post(
    "/shares/{share_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(user_access)],
    summary="Отозвать приглашение на шаринг аптечки",
)
async def revoke_first_aid_kit_share(
    share_id: str,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    share = await get_share_by_id(db=db, share_id=share_id)
    if not share:
        raise HTTPException(status_code=404, detail="Приглашение не найдено")

    await revoke_share(db=db, share=share, current_user=current_user)
    return None


@router.post(
    "/{kit_id}/share/send-to-corid",
    response_model=FirstAidKitShareResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
    summary="Отправить приглашение на импорт аптечки по COR-ID",
)
async def send_share_to_corid(
    kit_id: str,
    body: FirstAidKitShareSendToCorIdRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kit = await get_first_aid_kit_by_id(db=db, kit_id=kit_id, user=current_user)
    if not kit:
        raise HTTPException(status_code=404, detail="Аптечка не найдена")

    # Найдём пользователя по COR-ID
    recipient = await repository_person.get_user_by_corid(body.recipient_cor_id, db)
    if not recipient:
        raise HTTPException(status_code=404, detail="Пользователь с таким COR-ID не найден")

    # Создадим share c привязкой к to_user_cor_id
    share = await create_share(
        db=db,
        kit=kit,
        from_user=current_user,
        to_user_cor_id=recipient.cor_id,
        to_email=recipient.email,
        expires_hours=body.expires_hours or 72,
        context=body.context,
    )

    # Сгенерируем deeplink
    encoded_token = quote(share.token)
    deep_link = f"coridapp://open?firstAidKitShareToken={encoded_token}"

    # Отправим письмо получателю (используем существующий шаблон приглашения)
    background_tasks.add_task(
        send_first_aid_kit_share_email,
        recipient.email,
        deep_link,
        current_user.email,
        share.expires_at.isoformat(),
    )

    return FirstAidKitShareResponse(
        id=share.id,
        token=share.token,
        status=share.status,
        expires_at=share.expires_at,
        deep_link=deep_link,
    )


@router.post(
    "/{kit_id}/share/send-to-email",
    response_model=FirstAidKitShareResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_access)],
    summary="Отправить приглашение на импорт аптечки по email",
)
async def send_share_to_email(
    kit_id: str,
    body: FirstAidKitShareSendToEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kit = await get_first_aid_kit_by_id(db=db, kit_id=kit_id, user=current_user)
    if not kit:
        raise HTTPException(status_code=404, detail="Аптечка не найдена")

    # Создадим share без to_user_cor_id, только email
    share = await create_share(
        db=db,
        kit=kit,
        from_user=current_user,
        to_email=body.email,
        expires_hours=body.expires_hours or 72,
        context=body.context,
    )

    # Сгенерируем deeplink
    encoded_token = quote(share.token)
    deep_link = f"coridapp://open?firstAidKitShareToken={encoded_token}"

    # Отправим письмо на указанный email
    background_tasks.add_task(
        send_first_aid_kit_share_email,
        body.email,
        deep_link,
        current_user.email,
        share.expires_at.isoformat(),
    )

    return FirstAidKitShareResponse(
        id=share.id,
        token=share.token,
        status=share.status,
        expires_at=share.expires_at,
        deep_link=deep_link,
    )
