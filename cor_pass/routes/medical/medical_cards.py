"""
Маршруты для работы с медицинскими картами
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.db import get_db
from cor_pass.database.models import User
from cor_pass.schemas import (
    MedicalCardUpdate,
    MedicalCardResponse,
    MedicalCardAccessCreate,
    MedicalCardAccessResponse,
    MedicalCardListResponse,
    MedicalCardWithAccessInfo,
)
from cor_pass.repository.medical import medical_cards as medical_cards_repo
from cor_pass.repository.user import person
from cor_pass.services.shared.access import user_access
from cor_pass.services.user.cipher import decrypt_data
from cor_pass.config.config import settings
import base64


router = APIRouter(prefix="/v1/medical-cards", tags=["Medical Cards"])


@router.get(
    "",
    response_model=MedicalCardListResponse,
    summary="Получить список медицинских карт",
    description="Получение своей медицинской карты и карт с предоставленным доступом"
)
async def get_medical_cards(
    current_user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить список медицинских карт
    
    
    Возвращает:
    - **my_card**: Собственная медицинская карта пользователя (создается автоматически при регистрации)
    - **accessible_cards**: Карты других пользователей с предоставленным доступом
    """
    # Получение собственной карты
    my_card = await medical_cards_repo.get_user_medical_card(
        user_cor_id=current_user.cor_id,
        db=db,
    )
    
    # Если display_name не установлен, заполняем из профиля
    my_card_data = None
    if my_card:
        display_name = my_card.display_name
        birth_date = None
        birth_year = None
        gender = current_user.user_sex
        
        if not display_name:
            from cor_pass.database.models import Profile
            from sqlalchemy import select as sql_select
            
            profile_query = sql_select(Profile).where(Profile.user_id == current_user.id)
            profile_result = await db.execute(profile_query)
            profile = profile_result.scalar_one_or_none()
            
            if profile and profile.encrypted_first_name:
                try:
                    decoded_key = base64.b64decode(settings.aes_key)
                    first_name = await decrypt_data(profile.encrypted_first_name, decoded_key)
                    surname = await decrypt_data(profile.encrypted_surname, decoded_key) if profile.encrypted_surname else ""
                    display_name = f"{surname} {first_name}".strip()
                except Exception as e:
                    pass  # Если не удалось расшифровать, оставляем display_name пустым
            
            # Получаем дату рождения из профиля если есть
            if profile and profile.birth_date:
                birth_date = profile.birth_date
        else:
            # Если display_name уже был, все равно получаем профиль для birth_date
            from cor_pass.database.models import Profile
            from sqlalchemy import select as sql_select
            
            profile_query = sql_select(Profile).where(Profile.user_id == current_user.id)
            profile_result = await db.execute(profile_query)
            profile = profile_result.scalar_one_or_none()
            
            if profile and profile.birth_date:
                birth_date = profile.birth_date
        
        # Если полной даты нет, используем год из User.birth
        if not birth_date and current_user.birth:
            birth_year = current_user.birth
        
        # Создаем объект ответа с обновленным display_name
        my_card_data = MedicalCardResponse(
            id=my_card.id,
            owner_cor_id=my_card.owner_cor_id,
            display_name=display_name,
            card_color=my_card.card_color,
            is_active=my_card.is_active,
            created_at=my_card.created_at,
            updated_at=my_card.updated_at,
            gender=gender,
            birth_date=birth_date,
            birth_year=birth_year,
        )
    
    # Получение доступных карт
    accessible_data = await medical_cards_repo.get_accessible_medical_cards(
        user_cor_id=current_user.cor_id,
        db=db,
    )
    
    accessible_cards = []
    for card, access, owner, profile in accessible_data:
        # Расшифровка имени из профиля если есть
        owner_name = None
        birth_date = None
        birth_year = None
        gender = owner.user_sex if owner else None
        
        if profile and profile.encrypted_first_name:
            try:
                decoded_key = base64.b64decode(settings.aes_key)
                first_name = await decrypt_data(profile.encrypted_first_name, decoded_key)
                surname = await decrypt_data(profile.encrypted_surname, decoded_key) if profile.encrypted_surname else ""
                owner_name = f"{surname} {first_name}".strip()
            except Exception as e:
                owner_name = None
        
        # Получаем дату рождения: приоритет - полная дата из профиля
        if profile and profile.birth_date:
            birth_date = profile.birth_date
        elif owner and owner.birth:
            birth_year = owner.birth
        
        accessible_cards.append(
            MedicalCardWithAccessInfo(
                **card.__dict__,
                my_access_level=access.access_level.value,
                is_owner=False,
                owner_name=owner_name or card.display_name,
                owner_birth_year=birth_year,  # Оставляем для обратной совместимости
                gender=gender,
                birth_date=birth_date,
                birth_year=birth_year,
            )
        )
    
    return MedicalCardListResponse(
        my_card=my_card_data,
        accessible_cards=accessible_cards,
        total_accessible=len(accessible_cards),
    )


@router.get(
    "/{card_id}",
    response_model=MedicalCardResponse,
    summary="Получить медицинскую карту по ID",
    description="Получение детальной информации о медицинской карте"
)
async def get_medical_card(
    card_id: str,
    current_user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить медицинскую карту по ID
    
    Доступ имеют:
    - Владелец карты
    - Пользователи с предоставленным доступом
    """
    card = await medical_cards_repo.get_medical_card_by_id(
        card_id=card_id,
        user_cor_id=current_user.cor_id,
        db=db,
    )
    
    # Получаем информацию о владельце карты
    from cor_pass.database.models import User, Profile
    from sqlalchemy import select as sql_select
    
    # Находим владельца карты
    owner_query = sql_select(User).where(User.cor_id == card.owner_cor_id)
    owner_result = await db.execute(owner_query)
    owner = owner_result.scalar_one_or_none()
    
    gender = None
    birth_date = None
    birth_year = None
    display_name = card.display_name
    
    if owner:
        gender = owner.user_sex
        
        # Получаем профиль владельца
        profile_query = sql_select(Profile).where(Profile.user_id == owner.id)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()
        
        # Если display_name не установлен, заполняем из профиля
        if not display_name and profile and profile.encrypted_first_name:
            try:
                decoded_key = base64.b64decode(settings.aes_key)
                first_name = await decrypt_data(profile.encrypted_first_name, decoded_key)
                surname = await decrypt_data(profile.encrypted_surname, decoded_key) if profile.encrypted_surname else ""
                display_name = f"{surname} {first_name}".strip()
            except Exception:
                pass
        
        # Получаем дату рождения: приоритет - полная дата из профиля
        if profile and profile.birth_date:
            birth_date = profile.birth_date
        elif owner.birth:
            birth_year = owner.birth
    
    return MedicalCardResponse(
        id=card.id,
        owner_cor_id=card.owner_cor_id,
        display_name=display_name,
        card_color=card.card_color,
        is_active=card.is_active,
        created_at=card.created_at,
        updated_at=card.updated_at,
        gender=gender,
        birth_date=birth_date,
        birth_year=birth_year,
    )


@router.patch(
    "/my-card",
    response_model=MedicalCardResponse,
    summary="Обновить свою медицинскую карту",
    description="Обновление настроек отображения своей медицинской карты"
)
async def update_my_medical_card(
    body: MedicalCardUpdate,
    current_user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить свою медицинскую карту
    
    Можно изменить только настройки отображения:
    - **display_name**: Кастомное имя карты
    - **card_color**: Цвет карты в интерфейсе
    - **is_active**: Активность карты
    
    Медицинские данные (имя, дата рождения и т.д.) берутся из User/Profile
    """
    # Получаем карту пользователя
    card = await medical_cards_repo.get_user_medical_card(
        user_cor_id=current_user.cor_id,
        db=db,
    )
    
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Медицинская карта не найдена"
        )
    
    updated_card = await medical_cards_repo.update_medical_card(
        card_id=card.id,
        body=body,
        user_cor_id=current_user.cor_id,
        db=db,
    )
    return updated_card


@router.get(
    "/{card_id}/photo",
    status_code=status.HTTP_200_OK,
    summary="Получить фото владельца медицинской карты",
    description="Возвращает фотографию профиля владельца медицинской карты"
)
async def get_medical_card_owner_photo(
    card_id: str,
    current_user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получение фотографии владельца медицинской карты.**
    
    Возвращает фотографию профиля владельца карты.
    
    Доступ имеют:
    - Владелец карты
    - Пользователи с предоставленным доступом к карте
    """
    # Проверяем доступ к карте
    card = await medical_cards_repo.get_medical_card_by_id(
        card_id=card_id,
        user_cor_id=current_user.cor_id,
        db=db,
    )
    
    # Получаем владельца карты
    from cor_pass.database.models import User as UserModel
    from sqlalchemy import select as sql_select
    
    owner_query = sql_select(UserModel).where(UserModel.cor_id == card.owner_cor_id)
    owner_result = await db.execute(owner_query)
    owner = owner_result.scalar_one_or_none()
    
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Владелец карты не найден"
        )
    
    # Получаем фото владельца
    photo_data = await person.get_profile_photo(db=db, user_id=owner.id)
    
    if not photo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Фотография профиля не найдена"
        )
    
    async def image_stream():
        yield photo_data[0]
    
    return StreamingResponse(image_stream(), media_type=photo_data[1])


@router.get(
    "/{card_id}/photo/base64",
    status_code=status.HTTP_200_OK,
    summary="Получить фото владельца карты в формате Base64",
    description="Возвращает фотографию профиля владельца в виде Base64 Data URL"
)
async def get_medical_card_owner_photo_base64(
    card_id: str,
    current_user: User = Depends(user_access),
    db: AsyncSession = Depends(get_db),
):
    """
    **Получение фотографии владельца медицинской карты в формате Base64.**
    
    Возвращает фотографию профиля владельца карты в виде Base64-строки,
    встраиваемой в Data URL.
    
    Доступ имеют:
    - Владелец карты
    - Пользователи с предоставленным доступом к карте
    """
    # Проверяем доступ к карте
    card = await medical_cards_repo.get_medical_card_by_id(
        card_id=card_id,
        user_cor_id=current_user.cor_id,
        db=db,
    )
    
    # Получаем владельца карты
    from cor_pass.database.models import User as UserModel
    from sqlalchemy import select as sql_select
    
    owner_query = sql_select(UserModel).where(UserModel.cor_id == card.owner_cor_id)
    owner_result = await db.execute(owner_query)
    owner = owner_result.scalar_one_or_none()
    
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Владелец карты не найден"
        )
    
    # Получаем фото владельца
    photo_data = await person.get_profile_photo(db=db, user_id=owner.id)
    
    if not photo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Фотография профиля не найдена"
        )
    
    encoded_photo = base64.b64encode(photo_data[0]).decode("utf-8")
    photo_data_url = f"data:{photo_data[1]};base64,{encoded_photo}"
    
    return JSONResponse(content={"photo_data_url": photo_data_url})


# @router.post(
#     "/{card_id}/share",
#     response_model=MedicalCardAccessResponse,
#     status_code=status.HTTP_201_CREATED,
#     summary="Предоставить доступ к медицинской карте",
#     description="Предоставление доступа к медицинской карте другому пользователю"
# )
# async def share_medical_card(
#     card_id: str,
#     body: MedicalCardAccessCreate,
#     current_user: User = Depends(user_access),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Предоставить доступ к медицинской карте
    
#     Доступ могут предоставлять:
#     - Владелец карты
#     - Пользователь с уровнем доступа 'share'
    
#     Уровни доступа:
#     - **view**: Может смотреть (только чтение данных)
#     - **edit**: Может редактировать (чтение и изменение данных)
#     - **share**: Может распространять (чтение, изменение и предоставление доступа другим)
    
#     Для кого предоставляется доступ (purpose):
#     - **relative**: Для родственника
#     - **doctor**: Для врача
#     - **other**: Другое (укажите в purpose_note)
    
#     Пользователь должен принять приглашение через endpoint /accept/{access_id}
#     """
#     access = await medical_cards_repo.share_medical_card(
#         card_id=card_id,
#         body=body,
#         granting_user_cor_id=current_user.cor_id,
#         db=db,
#     )
#     return access


# @router.post(
#     "/accept/{access_id}",
#     response_model=MedicalCardAccessResponse,
#     summary="Принять приглашение на доступ к медицинской карте",
#     description="Подтверждение приглашения на доступ к чужой медицинской карте"
# )
# async def accept_medical_card_access(
#     access_id: str,
#     current_user: User = Depends(user_access),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Принять приглашение на доступ к медицинской карте
    
#     После принятия приглашения карта появится в списке доступных карт.
#     """
#     access = await medical_cards_repo.accept_medical_card_access(
#         access_id=access_id,
#         user_cor_id=current_user.cor_id,
#         db=db,
#     )
#     return access


# @router.delete(
#     "/{card_id}/access/{user_cor_id}",
#     status_code=status.HTTP_204_NO_CONTENT,
#     summary="Отозвать доступ к медицинской карте",
#     description="Отзыв доступа к медицинской карте у пользователя"
# )
# async def revoke_medical_card_access(
#     card_id: str,
#     user_cor_id: str,
#     current_user: User = Depends(user_access),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Отозвать доступ к медицинской карте
    
#     Только владелец карты может отзывать доступ.
#     """
#     await medical_cards_repo.revoke_medical_card_access(
#         card_id=card_id,
#         target_user_cor_id=user_cor_id,
#         revoking_user_cor_id=current_user.cor_id,
#         db=db,
#     )


# @router.get(
#     "/invitations/pending",
#     response_model=List[MedicalCardAccessResponse],
#     summary="Получить ожидающие приглашения",
#     description="Получение списка приглашений на доступ к медицинским картам"
# )
# async def get_pending_invitations(
#     current_user: User = Depends(user_access),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Получить список ожидающих приглашений
    
#     Возвращает приглашения на доступ к медицинским картам,
#     которые требуют подтверждения.
#     """
#     invitations = await medical_cards_repo.get_pending_invitations(
#         user_cor_id=current_user.cor_id,
#         db=db,
#     )
    
#     return [access for access, _ in invitations]
