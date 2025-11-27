from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.database.db import get_db
from cor_pass.schemas import (
    Cassette as CassetteModelScheema,
    CassetteCreate,
    CassettePrinting,
    CassetteUpdateComment,
    DeleteCassetteRequest,
    DeleteCassetteResponse,
)
from cor_pass.repository.laboratory import cassette as cassette_service
from typing import List, Optional

from cor_pass.services.shared.access import doctor_access, lab_assistant_or_doctor_access

router = APIRouter(prefix="/cassettes", tags=["Cassette"])


@router.post(
    "/create",
    dependencies=[Depends(lab_assistant_or_doctor_access)],
    response_model=List[CassetteModelScheema],
)
async def create_cassette_for_sample(
    body: CassetteCreate,
    printing: bool = False,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Создаем заданное количество кассет для конкретного семпла и опционально печатаем их
    """
    created_cassettes = await cassette_service.create_cassette(
        db=db,
        sample_id=body.sample_id,
        num_cassettes=body.num_cassettes,
        printing=printing,
    )
    
    # Если нужна печать, печатаем каждую созданную кассету
    if printing and created_cassettes:
        logger.info(f"Начинаем печать {len(created_cassettes)} кассет")
        for cassette in created_cassettes:
            try:
                cassette_id = cassette['id'] if isinstance(cassette, dict) else cassette.id
                print_data = CassettePrinting(cassete_id=cassette_id, printing=True)
                print_result = await cassette_service.print_cassette_data(
                    data=print_data, db=db, request=request
                )
                if print_result and print_result.get("success"):
                    logger.debug(f"Кассета {cassette_id} успешно отправлена на печать")
                else:
                    logger.warning(f"Не удалось распечатать кассету {cassette_id}: {print_result}")
            except Exception as e:
                logger.error(f"Ошибка при печати кассеты {cassette.get('id', 'unknown')}: {e}")
    
    return created_cassettes


@router.get(
    "/{cassette_id}",
    response_model=CassetteModelScheema,
    dependencies=[Depends(lab_assistant_or_doctor_access)],
)
async def read_cassette(cassette_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получаем данные кассеты и вложеных сущностей
    """
    db_cassette = await cassette_service.get_cassette(db, cassette_id)
    if db_cassette is None:
        raise HTTPException(status_code=404, detail="Cassette not found")
    return db_cassette


@router.patch(
    "/{cassette_id}",
    response_model=CassetteModelScheema,
    dependencies=[Depends(lab_assistant_or_doctor_access)],
)
async def update_cassette_comment(
    cassette_id: str,
    comment_update: CassetteUpdateComment,
    db: AsyncSession = Depends(get_db),
):
    """Обновляет комментарий кассеты по её ID."""
    updated_cassette = await cassette_service.update_cassette_comment(
        db, cassette_id, comment_update
    )
    if not updated_cassette:
        raise HTTPException(status_code=404, detail="Cassette not found")
    return updated_cassette


@router.delete(
    "/delete",
    response_model=DeleteCassetteResponse,
    dependencies=[Depends(lab_assistant_or_doctor_access)],
    status_code=status.HTTP_200_OK,
)
async def delete_cassettes(
    request_body: DeleteCassetteRequest, db: AsyncSession = Depends(get_db)
):
    """
    Удаляет массив кассет
    """
    result = await cassette_service.delete_cassettes(
        db=db, cassettes_ids=request_body.cassette_ids
    )
    return result





@router.patch(
    "/{cassette_id}/printed",
    response_model=Optional[CassetteModelScheema],
    dependencies=[Depends(lab_assistant_or_doctor_access)],
)
async def change_glass_printing_status(
    data: CassettePrinting, request: Request, db: AsyncSession = Depends(get_db)
):
    """Меняем статус печати кассеты"""
    print_result = await cassette_service.print_cassette_data(db=db, data=data, request=request)
    # if not print_result:
    #         raise HTTPException(status_code=400, detail="Printing failed")

    if print_result and print_result.get("success"):
        updated_cassette = await cassette_service.change_printing_status(
        db=db, cassette_id=data.cassete_id, printing=data.printing
    )
        if not updated_cassette:
            raise HTTPException(status_code=404, detail="Cassette not found")
        return updated_cassette

