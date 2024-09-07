from typing import List

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from cor_pass.database.db import get_db
from cor_pass.schemas import TagModel, TagResponse
from cor_pass.repository import tags as repository_tags

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get("/", response_model=List[TagResponse])
async def read_tags(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """
    **Get a list of tags. / Получение списка всех тэгов** \n

    :param skip: The number of tags to skip (for pagination). Default is 0.
    :type skip: int
    :param limit: The maximum number of tags to retrieve. Default is 50.
    :type limit: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: A list of TagResponse objects representing the tags.
    :rtype: List[TagResponse]
    """
    tags = await repository_tags.get_tags(skip, limit, db)
    return tags


@router.get("/{tag_id}", response_model=TagResponse)
async def read_tag(tag_id: int, db: Session = Depends(get_db)):
    """
    **Get a specific tag by ID. / Получение тэга по id** \n

    :param tag_id: The ID of the tag.
    :type tag_id: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The TagResponse object representing the tag.
    :rtype: TagResponse
    :raises HTTPException 404: If the tag with the specified ID does not exist.
    """
    tag = await repository_tags.get_tag(tag_id, db)
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )
    return tag


@router.post("/", response_model=TagResponse)
async def create_tag(body: TagModel, db: Session = Depends(get_db)):
    """
    **Create a new tag. / Создание нового тэга** \n

    :param body: The request body containing the tag data.
    :type body: TagModel
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The created TagResponse object representing the new tag.
    :rtype: TagResponse
    """
    return await repository_tags.create_tag(body, db)


@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(tag_id: int, body: TagModel, db: Session = Depends(get_db)):
    """
    **Update an existing tag. / Обновление существующего тэга** \n

    :param tag_id: The ID of the tag to update.
    :type tag_id: int
    :param body: The request body containing the updated tag data.
    :type body: TagModel
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The updated TagResponse object representing the updated tag.
    :rtype: TagResponse
    :raises HTTPException 404: If the tag with the specified ID does not exist.
    """
    tag = await repository_tags.update_tag(tag_id, body, db)
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )
    return tag


@router.delete("/{tag_id}", response_model=TagResponse)
async def remove_tag(tag_id: int, db: Session = Depends(get_db)):
    """
    **Remove a tag. / Удаление тэга** \n

    :param tag_id: The ID of the tag to remove.
    :type tag_id: int
    :param db: The database session. Dependency on get_db.
    :type db: Session, optional
    :return: The removed TagResponse object representing the removed tag.
    :rtype: TagResponse
    :raises HTTPException 404: If the tag with the specified ID does not exist.
    """
    tag = await repository_tags.remove_tag(tag_id, db)
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )
    return tag
