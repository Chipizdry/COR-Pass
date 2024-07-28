from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
from cor_pass.database.models import Role


# AUTH MODELS


class UserModel(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=20)


class UserDb(BaseModel):
    id: str
    email: str
    role: Role

    class Config:
        from_attributes = True


class ResponseUser(BaseModel):
    user: UserDb
    detatil: str = "User successfully created"


class TokenModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponseModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"



class EmailSchema(BaseModel):
    email: EmailStr


class VerificationModel(BaseModel):
    email: EmailStr
    verification_code: int


class ChangePasswordModel(BaseModel):
    email: str
    password: str = Field(min_length=4, max_length=20)


# PASS-MANAGER MODELS


class TagModel(BaseModel):
    name: str = Field(max_length=25)


class TagResponse(TagModel):
    id: int
    name: str = Field(max_length=25)

    class Config:
        from_attributes = True


class CreateRecordModel(BaseModel):
    record_name: str = Field(max_length=25)
    website: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None
    tag_names: List[str] = []


class RecordResponse(BaseModel):
    record_id: int
    record_name: str
    website: str
    username: str
    password: str
    created_at: datetime
    edited_at: datetime
    notes: str
    user_id: str

    tags: List[TagModel]

    class Config:
        from_attributes = True


# PASS-GENERATOR MODELS

class PasswordGeneratorSettings(BaseModel):
    length: int = Field(12, ge=8, le=128)
    include_uppercase: bool = True
    include_lowercase: bool = True
    include_digits: bool = True
    include_special: bool = True

class WordPasswordGeneratorSettings(BaseModel):
    length: int = Field(4, ge=1, le=7)
    separator_hyphen: bool = True
    separator_underscore: bool = True
    include_uppercase: bool = True

# class RecordFieldValueModel(BaseModel):
#     string_value: Optional[str] = None
#     date_value: Optional[datetime] = None
#     number_value: Optional[float] = None


# class RecordFieldModel(BaseModel):
#     id: int
#     name: str
#     type: str

#     class Config:
#         from_attributes = True


# class TagModel(BaseModel):
#     id: int
#     name: str

#     class Config:
#         from_attributes = True

# class RecordModel(BaseModel):
#     id: int
#     user_id: str
#     record_name: str
#     website: Optional[str] = None
#     username: Optional[str] = None
#     password: Optional[str] = None
#     created_at: datetime
#     edited_at: datetime
#     attachments: Optional[str] = None
#     notes: Optional[str] = None
#     fields: List[RecordFieldValueModel] = []
#     tags: List[TagModel] = []

#     class Config:
#         from_attributes = True


# class CreateRecordModel(BaseModel):
#     record_name: str
#     website: Optional[str] = None
#     username: Optional[str] = None
#     password: Optional[str] = None
#     attachments: Optional[str] = None
#     notes: Optional[str] = None
#     fields: List[RecordFieldValueModel] = [None]
#     tags: List[TagModel] = [None]

# class ResponseRecord(BaseModel):
#     record: RecordModel
#     detail: str = "Record successfully created"
