import sys
import os
# 从 backend/tests/ 反推 backend/ 根，让 database / models 等顶层模块能直接 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models

db = SessionLocal()
records = db.query(models.WeldingRecord).all()
print(f'总记录数: {len(records)}')
print('\n所有记录:')
for r in records:
    print(f'ID: {r.id}, 总分: {r.total_score}, 时间: {r.timestamp}')
db.close()
