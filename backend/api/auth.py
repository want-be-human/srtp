# -*- coding: utf-8 -*-
"""
学生登录接口。

学生名单由 scripts/seed_students.py 预先写入 students 表。当前演示阶段不做
token/session，前端登录后只是把学号缓存到本地；后端各业务接口仍然接受未登录
请求。后面要补 JWT 在此扩展即可。
"""

import os
import sys
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(current_dir))

from database import SessionLocal
import models


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class LoginRequest(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=200)


class PublicStudent(BaseModel):
    student_id: str
    name: str
    batch_id: Optional[str] = None

    class Config:
        from_attributes = True


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


@router.post("/auth/login", response_model=PublicStudent)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    student = (
        db.query(models.Student)
        .filter(models.Student.student_id == payload.student_id)
        .first()
    )
    if student is None or not _verify_password(payload.password, student.password_hash):
        raise HTTPException(status_code=401, detail="学号或密码错误")
    return student
