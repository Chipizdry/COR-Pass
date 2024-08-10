from typing import List

from fastapi import Depends, HTTPException, status

from cor_pass.database.models import User
from cor_pass.services.auth import auth_service


class UserAccess:
    def __init__(self, active_user):
        self.active_user = active_user

    async def __call__(self, user: User = Depends(auth_service.get_current_user)):
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden operation"
            )


user_access = UserAccess([User.is_active])
