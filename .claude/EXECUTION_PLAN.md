# 焊育智眸 国赛执行计划（决策已锁定）

> 这是「已经决策完成」的执行计划。原 UPGRADE_PROPOSAL.md 的 11 个待拍板问题已在 2026-05-19 全部答复，本文反映最终方案。  
> 与 [`docs/国赛11天升级规划与代码梳理.md`](../docs/国赛11天升级规划与代码梳理.md)（团队 11 天总规划，下文称「原规划」）配套使用：原规划定整体方向，本文档定**谁做什么、按什么顺序、什么时候 push**。

冻结日：2026-05-28（国赛）。本文最后一次修订：2026-05-19。

---

## 1. 责任分工

| 工作项 | 负责人 |
|---|---|
| 有线摄像头接入（硬件 + 联调） | **用户** |
| 原规划 P2 = 演示登录 + 学生数据归属 + 数据树 PK + 学生对比页 | **用户** |
| 3D 重构展示（原规划 P1 方向一） | **团队其他成员**（用户不负责，Claude 不负责） |
| 原规划 P0/P1 中 3D / P2 之外的所有部分 | **Claude** |
| 本提案新增的非 P2 部分（TTS / 教学严格模式 / 演示降级模式 / mock 清理 / 数据预播种 / 标准对齐文案） | **Claude**，除非用户在做 P2 时顺带完成 |
| 提案中的缺陷热图（最低优先级） | **Claude**，最后做 |

补充约定：用户在做 P2 / 有线摄像头时如果顺带把上表中 Claude 的某项完成了，就标注后从 Claude 待办里划掉。

---

## 2. 阶段排序（从现在到 05-28）

### Phase A — 深度 /simplify（先）

目的：把第一轮 /simplify 没碰的、风险中等的改动也清理掉，为后续功能开发腾出干净的代码地基。

范围（候选）：
- `front/app/page.tsx` 中的重复 fetch 逻辑抽到统一 `lib/fetcher.ts`，减少 try/catch 重复
- `front/components/lesson-plan/lesson-plan-export.tsx` 175 条 mock 文案瘦身（保留 1-2 条作为「无数据时的 placeholder」）
- `front/components/prediction/prediction-dashboard.tsx` 中 `DEFAULT_MOCK_*` 兜底数据评估：要么明确标「示例数据」UI，要么按用户决策 #7 删除
- `backend/api/predict.py` 中 `/predict/ai-radar-data` 的 mock 数据直接删（决策 #7）
- `backend/api/lesson_plan.py`、`backend/api/predict.py` 中的 `except Exception:` 收紧成具体异常
- `backend/api/teacher.py` 改造完成后，`backend/ai_analysis.py` 内部的 client 是否同样能复用单例（评估即可，不一定改）
- `front/components/data-tree/` 类型在 `front/types/` 集中
- 删除 `front/pnpm-lock.yaml` 或 `package-lock.json`（用户拍板留哪个）
- 移动 `backend/simple_test.py / test_api.py / test_types.py / check_db.py` 到 `backend/tests/`
- `backend/yolo_config.json` 与代码默认值的一致性（要先确认 zonghe 是否实际加载该 json）

**重要**：本阶段改动 commit 但 **不 push**，等用户逐项 review 后由用户授权再推。

### Phase B — 原规划 Claude 该做的部分（Phase A 通过后）

按 `docs/国赛11天升级规划与代码梳理.md` 的 P0/P1：

- 摄像头来源去硬编码（前端配置面板 + 后端环境变量），与用户有线摄像头联调对接
- ROI 可配置：把 `yolo_realtime.py` 的中心 1/3 裁剪改成 `(x, y, w, h)` 可写状态，前端加可视化检测框 + 配置 UI
- 缺陷名称兜底：所有出现「未知缺陷」的位置换成 `get_defect_name_safe()`（已建好工具函数）
- PDF 报告本地规则化：完善 `services/rules/`，剥离 AI 依赖
- AI 兜底巡查：`api/lesson_plan.py`、`api/predict.py` 中的 AI 调用都加上 timeout + fallback（参考 `teacher.py` 已做的模式）

### Phase C — 提案新增项中能顺带做的（与 Phase B 并行/穿插）

按优先级从高到低，挑选时机与 Phase B 任务结合：

1. 删 `/predict/ai-radar-data` mock 改真实数据（与 Phase B「PDF 本地规则化」批次合并做）
2. 演示数据预播种脚本 `backend/scripts/seed_demo_data.py`（与 Phase B 调试合并）
3. 教学/严格模式切换（与 Phase B「ROI 可配置」一起做 UI 设置面板）
4. 演示降级模式（必须做，安全网）
5. TTS 重要事件播报（仅 <60 分 / 严重缺陷 / 保存成功 三种场景；含手动静音开关）
6. 标准对齐文案（仅 PDF 报告页脚 + 讲稿大纲，不进 README）

### Phase D — 提案中无法顺带、留到最后

- 缺陷空间标注 / 热图（数据库加 `defect_bboxes` JSON 列；前端历史记录点击可视化）

### Phase E — 冻结

- 2026-05-27：只修 bug，不加功能；连跑 3 遍演示
- 2026-05-28：打包备份，比赛电脑 + U 盘 + 云盘

---

## 3. 决策摘要（用户 2026-05-19 答复）

| # | 议题 | 决策 |
|---|---|---|
| 1 | 3D 路线 | **不由用户负责**，跳过 Claude 这边 |
| 2 | TTS 播报 | **做**，仅重要事件（<60 分 / 严重缺陷 / 保存成功） |
| 3 | 教学模式 / 严格模式切换 | **做** |
| 4 | 演示降级模式 | **做** |
| 5 | 标准对齐叙事 GB/T 19418 + 1+X | **做**，仅 PDF 和讲稿，不进 README |
| 6 | 演示数据预播种 | **做** |
| 7 | `/predict/ai-radar-data` mock | **删** |
| 8 | 缺陷空间标注 / 热图 | 列为 P2（最后做） |
| 9 | 中英切换 | **不做** |
| 10 | 演示登录放哪里 | **新建导航** |
| 11 | 是否按 STRUCTURE_REPLAN 拆分 page.tsx / yolo_realtime.py | **同意**，逐步拆 |
| 12 | 任务流 | 先深度 /simplify → 完成原规划 → 完成提案剩余项；代码改动等用户审核后再推 |

---

## 4. 推/审流程

- **文档改动**（`.claude/*.md`、`docs/*.md`、`README.md`）：commit 后立即双推（GitHub `srtp/main` + Gitee `gitee/dev-upgrade`），零风险。
- **代码改动**：commit 后**先不 push**。在 commit message 里写清动机和影响范围，告知用户「待审」。用户审核 OK 后由 Claude 双推。
- 双推命令固定：
  ```bash
  git push srtp main
  git push gitee main:dev-upgrade
  ```

---

## 5. 完成后必做：更新 [PROJECT_MEMORY.md](./PROJECT_MEMORY.md)

每个阶段结束（Phase A/B/C/D 各一次）必须更新 PROJECT_MEMORY 第 10 节修订历史：
- 列出本阶段实际改动的文件
- 标注是否仍有未完成项需要延期
- 如有重大决策变更，回写到本文第 3 节

---

## 6. 关于 3D 部分

- Claude 不负责，用户也不负责，由团队其他成员处理。
- 但前端导航位、`front/components/modules/ThreeDModule.tsx` 占位、`front/public/3d/` 目录由 Claude 在 Phase B 留好接口（一个空模块 + 一行 README 说明），便于其他成员塞入资产。

---

## 7. 关于 P2（用户负责部分）的对接点

用户做原规划 P2（登录/数据归属/PK）时，Claude 需要预留的接口：

- `backend/api/auth.py` 路由空架子（路由前缀 `/api/v1/auth`），Claude 可以在 Phase B 末尾建好；用户填业务。
- `backend/schemas/auth.py` Pydantic 模型空架子。
- `front/contexts/AuthContext.tsx` 空 Context；`front/lib/storage.ts` 提供「当前学生身份」的统一存取。
- `WeldingRecord.student_id / student_name / batch_id` 字段已存在，无需迁移；保存检测记录时 Claude 把当前身份带上即可（与 Phase B 配合）。
- 数据树和 PK 视图属于用户工作，Claude 不在 `data-tree-viewer.tsx` 中预先加 PK 视图入口。

---

## 8. 现在的下一步

1. ✅ 本文档完成
2. ✅ [PROJECT_MEMORY.md](./PROJECT_MEMORY.md)、[STRUCTURE_REPLAN.md](./STRUCTURE_REPLAN.md) 同步修订
3. 推送本次文档改动到双远程
4. 进入 Phase A —— 跑深度 /simplify
5. Phase A 改动 commit 后等待用户审核
