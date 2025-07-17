from cor_pass.database.models import LabAssistant, User
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.schemas import LabAssistantCreate


async def create_lab_assistant(
    lab_assistant_data: LabAssistantCreate,
    db: AsyncSession,
    user: User,
) -> LabAssistant:
    """
    Асинхронная сервисная функция по созданию лаборанта.
    """
    lab_assistant = LabAssistant(
        lab_assistant_cor_id=user.cor_id,
        first_name=lab_assistant_data.first_name,
        surname=lab_assistant_data.last_name,
        middle_name=lab_assistant_data.middle_name,
    )

    db.add(lab_assistant)

    await db.commit()
    await db.refresh(lab_assistant)

    return lab_assistant
