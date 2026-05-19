# -*- coding: utf-8 -*-
"""
学生登录 API（C1）

国赛演示阶段使用预播种的班级名单：学校管理员通过 backend/scripts/seed_students.py
把学生学号、姓名、初始密码（bcrypt 哈希）写入 students 表，学生用学号 + 密码登录。
将来对接学校官网时只需在另一处刷新这张表，本接口保持不变。

接口刻意没有 token / session / refresh —— 演示场景够用，且不打算把鉴权强制
推到其它端点。前端 gate 是软的：未登录会被跳到 /login，但后端不会单独拒绝
未登录用户调 detection 等接口。后续需要真鉴权时，可在本文件下补 JWT 与
依赖注入，不破坏对外契约。
"""

import sys
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import bcrypt

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
    """对外暴露的学生信息（不含 password_hash）。"""
    student_id: str
    name: str
    batch_id: Optional[str] = None

    class Config:
        from_attributes = True


def _verify_password(plain: str, hashed: str) -> bool:
    """安全校验密码：异常输入（hash 损坏 / 编码问题）一律返回 False。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


@router.post("/auth/login", response_model=PublicStudent)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """学号 + 密码登录。错误信息统一为「学号或密码错误」，不区分两种情况。"""
    student = (
        db.query(models.Student)
        .filter(models.Student.student_id == payload.student_id)
        .first()
    )
    if student is None or not _verify_password(payload.password, student.password_hash):
        raise HTTPException(status_code=401, detail="学号或密码错误")
    return student
