from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    is_active: bool | None = None


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshRequest(BaseModel):
    refresh_token: str
