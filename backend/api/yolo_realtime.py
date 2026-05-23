# -*- coding: utf-8 -*-
"""
YOLO实时检测API
功能：
1. 在后端运行YOLO检测
2. 通过API提供实时检测数据（不是视频流，前端用摄像头）
3. 用户按键时保存分数
"""

import asyncio
import sys
import os
import threading
import time
from collections import deque
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import cv2
import numpy as np
import base64

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

# 导入数据库相关模块
from database import SessionLocal
import models

from config import YOLO_CONFIG_FILE  # 配置文件路径，置信度阈值等

# 导入统一的缺陷类型定义
try:
    from defect_types import DEFECT_EN_TO_CN, TRUE_DEFECT_TYPES, NON_DEFECT_LABELS
except ImportError:
    NON_DEFECT_LABELS = frozenset({"Good Weld", "良好焊缝", "无缺陷", "无", "未知", ""})
    DEFECT_EN_TO_CN = {
        'Poor Weld': '焊接不良', 'Crack': '裂纹', 'Excess Rebar': '钢筋过剩',
        'Good Weld': '良好焊缝', 'Porosity': '气孔', 'Spatter': '飞溅',
        'Undercut': '咬边', 'Overlap': '焊瘤', 'Incomplete Fusion': '未熔合',
        'Inclusion': '夹渣', 'Distortion': '变形', 'Surface Roughness': '表面粗糙',
        'Excess Penetration': '焊穿', 'Misalignment': '错边', 'Arc Strike': '电弧擦伤',
        'Discoloration': '变色', 'Tool Mark': '工具痕迹'
    }

# 导入YOLO检测服务（从backend/services/yolo/）
try:
    from services.yolo import IntegratedWeldDetector
    YOLO_AVAILABLE = True
except ImportError as e:
    print(f"警告：无法导入YOLO模块: {e}")
    IntegratedWeldDetector = None
    YOLO_AVAILABLE = False

router = APIRouter()

# 全局变量
capture_thread = None
inference_thread = None
is_detecting = False
current_detection_data = None
detector = None
camera_cap = None
data_lock = threading.Lock()
latest_frame = None
frame_lock = threading.Lock()
detector_lock = threading.Lock()

# ====== 可配置的默认参数（可通过 /video-stream 查询参数覆盖） ======
# 目标摄像头抓帧FPS：下游 STREAM 30、INFERENCE 6，抓 60 一半帧会被覆盖浪费
TARGET_CAMERA_FPS = 30
# MJPEG 推流默认FPS
STREAM_DEFAULT_FPS = 30
# JPEG 编码默认质量（10-95，越低压缩越狠、带宽越小）
JPEG_DEFAULT_QUALITY = 85
# 请求相机源分辨率：2K 相机走 2K，YOLO 拿到 2K 原图后内部 letterbox 到 imgsz=1280
CAPTURE_REQ_WIDTH = 2560
CAPTURE_REQ_HEIGHT = 1440
# video_stream 默认推流分辨率：1080p 而不是 2K。
# 2K JPEG 单线程编码 ~75ms/帧，单线程跑不到 30fps；1080p 编码 ~30ms 能稳 30fps。
# 想看 2K 流前端在 URL 加 ?width=2560&height=1440 即可（接受 12fps）
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
# 推理目标频率（每秒几次YOLO）
INFERENCE_FPS = 6

# 检测时序融合参数
# 5 帧滑动窗口；同类缺陷需要在窗口内被关联到 ≥3 次才算"确认"，瞬时单帧噪声丢掉
STABILIZER_WINDOW = 5
STABILIZER_CONFIRM = 3
# 前后帧检测框 IoU 超过这个值才视为同一目标
STABILIZER_IOU = 0.3
# 一条 track 持续没匹配上多少帧就回收
STABILIZER_TRACK_TTL = 5
# 分数指数滑动平均权重：smoothed = ALPHA * new + (1 - ALPHA) * smoothed
STABILIZER_EMA_ALPHA = 0.4


class FpsMeter:
    """每 window_s 秒打一行实测 fps + 单帧 work_label 平均耗时。

    capture_loop 和 generate_video_stream 都要测自己的 fps + 内部某一段耗时，
    单独写两份很容易在 divide-by-zero 守卫上漂移，统一到这里。
    """

    def __init__(self, label: str, work_label: str = "work", window_s: float = 5.0):
        self.label = label
        self.work_label = work_label
        self.window_s = window_s
        self.count = 0
        self.work_total = 0.0
        self.window_start = time.perf_counter()

    def tick(self, work_seconds: float, *, suffix: str = "") -> None:
        """记一帧（含本帧 work_seconds 耗时），到窗口边界就打日志并复位。"""
        self.count += 1
        self.work_total += work_seconds
        now = time.perf_counter()
        elapsed = now - self.window_start
        if elapsed < self.window_s:
            return
        fps = self.count / elapsed
        avg_ms = self.work_total / max(1, self.count) * 1000
        tail = f"，{suffix}" if suffix else ""
        print(f"[{self.label}] 实测 {fps:.1f} fps，{self.work_label} 平均 {avg_ms:.1f} ms/帧{tail}")
        self.count = 0
        self.work_total = 0.0
        self.window_start = now


def _box_iou(a, b):
    """两个 [x1, y1, x2, y2] 框的 IoU，无重叠或退化框返回 0。"""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


class DetectionStabilizer:
    """跨帧关联 + 多帧确认 + 分数 EMA 平滑。

    - 用 IoU 把当前帧的 detection 关联到已有 track；同类且 IoU 超阈值即认为是同一目标。
    - 一条 track 在最近 STABILIZER_WINDOW 帧里出现 ≥ STABILIZER_CONFIRM 次才算"确认"，
      前端拿到的就是稳定的检测，不再被单帧误检带飞。
    - track 的输出 confidence 取窗口内中位数，对异常高/低值天然鲁棒。
    - 四项分数走 EMA，前端折线不再跳。
    """

    def __init__(self):
        self.frame_idx = 0
        self.tracks = []
        # None 表示尚未收过任何一帧
        self.smoothed = None

    def update(self, raw_detections, raw_scores):
        """送入一帧的检测和分数，返回 (confirmed_detections, smoothed_scores)。"""
        self.frame_idx += 1

        parsed = []
        for d in raw_detections or []:
            box = d.get("box")
            if not box or len(box) != 4:
                continue
            try:
                parsed.append({
                    "raw": d,
                    "box": [float(x) for x in box],
                    "cls": d.get("class_name", ""),
                    "conf": float(d.get("confidence", 0.0)),
                })
            except (TypeError, ValueError):
                continue

        # 贪心 IoU 匹配：每条 track 找未占用的最佳 detection
        matched = set()
        for trk in self.tracks:
            best_iou, best_j = STABILIZER_IOU, -1
            for j, p in enumerate(parsed):
                if j in matched or p["cls"] != trk["class"]:
                    continue
                iou = _box_iou(trk["box"], p["box"])
                if iou >= best_iou:
                    best_iou, best_j = iou, j
            if best_j >= 0:
                p = parsed[best_j]
                matched.add(best_j)
                trk["box"] = p["box"]
                trk["last_seen"] = self.frame_idx
                trk["frames"].append((self.frame_idx, p["conf"], p["box"], p["raw"]))

        for j, p in enumerate(parsed):
            if j in matched:
                continue
            new_trk = {
                "class": p["cls"],
                "box": p["box"],
                "last_seen": self.frame_idx,
                "frames": deque(maxlen=STABILIZER_WINDOW),
            }
            new_trk["frames"].append((self.frame_idx, p["conf"], p["box"], p["raw"]))
            self.tracks.append(new_trk)

        ttl_cut = self.frame_idx - STABILIZER_TRACK_TTL
        self.tracks = [t for t in self.tracks if t["last_seen"] > ttl_cut]

        # 多帧确认：窗口内累计 ≥ confirm 次的 track 才输出
        confirmed = []
        window_cut = self.frame_idx - STABILIZER_WINDOW + 1
        for t in self.tracks:
            recent = [f for f in t["frames"] if f[0] >= window_cut]
            if len(recent) < STABILIZER_CONFIRM:
                continue
            confs = sorted(f[1] for f in recent)
            median_conf = confs[len(confs) // 2]
            latest_raw = recent[-1][3]
            out = dict(latest_raw)
            out["confidence"] = float(median_conf)
            out["box"] = list(t["box"])
            confirmed.append(out)

        if self.smoothed is None:
            self.smoothed = {}
            for k, v in raw_scores.items():
                try:
                    self.smoothed[k] = float(v)
                except (TypeError, ValueError):
                    self.smoothed[k] = v
        else:
            a = STABILIZER_EMA_ALPHA
            for k, v in raw_scores.items():
                try:
                    self.smoothed[k] = a * float(v) + (1 - a) * float(self.smoothed.get(k, v))
                except (TypeError, ValueError):
                    self.smoothed[k] = v

        # state 保留全精度，对外只暴露两位小数避免前端长尾
        out_scores = {
            k: round(v, 2) if isinstance(v, (int, float)) else v
            for k, v in self.smoothed.items()
        }
        return confirmed, out_scores


class StartDetectionRequest(BaseModel):
    camera_id: Optional[int] = None
    camera_url: Optional[str] = None  # IP摄像头URL，如 http://192.168.141.81:8081/


def _normalize_bboxes(detections, img_w: int, img_h: int) -> List[dict]:
    """xyxy 像素坐标 → cx/cy/w/h 归一化到 [0,1]，并丢掉良品框。"""
    if img_w <= 0 or img_h <= 0:
        return []
    out = []
    for d in detections or []:
        box = d.get("box")
        if not box or len(box) != 4:
            continue
        label_cn = str(d.get("class_name_cn") or "")
        label_en = str(d.get("class_name") or "")
        if label_cn in NON_DEFECT_LABELS or label_en in NON_DEFECT_LABELS:
            continue
        try:
            x1, y1, x2, y2 = (float(v) for v in box)
        except (TypeError, ValueError):
            continue
        # 越界 / 退化框直接丢，否则 clamp 后会堆到 (0,0) 或 (1,1) 污染热图
        if x1 < 0 or y1 < 0 or x2 > img_w or y2 > img_h or x2 - x1 < 1 or y2 - y1 < 1:
            continue
        cx = (x1 + x2) * 0.5 / img_w
        cy = (y1 + y2) * 0.5 / img_h
        w = (x2 - x1) / img_w
        h = (y2 - y1) / img_h
        out.append({
            "label": label_en or "unknown",
            "label_cn": label_cn or label_en or "未知",
            "cx": round(cx, 4),
            "cy": round(cy, 4),
            "w": round(w, 4),
            "h": round(h, 4),
            "conf": round(float(d.get("confidence", 0.0)), 3),
        })
    return out


class ScoreData(BaseModel):
    """用户按键时保存的分数数据"""
    total_score: float
    smoothness_score: float
    width_score: float
    defect_score: float
    width_mm: float
    defect_type_name: str
    timestamp: str
    # 学生标识字段
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    batch_id: Optional[str] = None
    notes: Optional[str] = None


# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def capture_loop(camera_source):
    """摄像头抓帧循环（后台线程）：读取相机帧并更新 latest_frame。

    camera_source 是整数（USB 设备 index）或字符串（IP 摄像头 URL）。
    """
    global is_detecting, camera_cap, latest_frame

    try:
        # 注意：抓帧线程不初始化YOLO，YOLO在推理线程初始化

        # 打开摄像头：USB 设备优先 MSMF。DSHOW 在 Windows 上 set FOURCC 经常 silently
        # fail —— 相机回退未压缩 YUYV，2K 单帧 7.4MB 在 USB 2.0 上传不动 → fps 跌到 2-3。
        # MSMF 协商更可靠（启动慢 1-2s），打不开时再退 DSHOW。URL 走 FFMPEG，沿用 CAP_ANY
        if isinstance(camera_source, int):
            camera_cap = cv2.VideoCapture(camera_source, cv2.CAP_MSMF)
            if not camera_cap.isOpened():
                print("MSMF 打开失败，回退到 DSHOW")
                camera_cap = cv2.VideoCapture(camera_source, cv2.CAP_DSHOW)
        else:
            camera_cap = cv2.VideoCapture(camera_source)
        if not camera_cap.isOpened():
            print(f"✗ 无法打开摄像头 {camera_source}")
            is_detecting = False
            return

        # MJPG fourcc 必须在 set 分辨率之前，否则部分相机在 YUYV 下不接受 1080p
        try:
            fourcc_fn = getattr(cv2, 'VideoWriter_fourcc', None)
            if fourcc_fn is not None:
                fourcc = fourcc_fn(*'MJPG')
                camera_cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        except Exception:
            pass
        camera_cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_REQ_WIDTH)
        camera_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_REQ_HEIGHT)
        camera_cap.set(cv2.CAP_PROP_FPS, TARGET_CAMERA_FPS)
        try:
            camera_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        actual_w = int(camera_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(camera_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = camera_cap.get(cv2.CAP_PROP_FPS)
        # fourcc 的 int 编码解回 ASCII 看相机实际跑哪种格式；不是 MJPG 几乎一定带宽爆
        fourcc_int = int(camera_cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = bytes([(fourcc_int >> (8 * i)) & 0xff for i in range(4)]).decode('ascii', errors='replace')
        print(f"✓ 摄像头 {camera_source} 已打开，源 {actual_w}x{actual_h}，输出 {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
        print(f"  fourcc='{fourcc_str}' (空字符串=MSMF 不暴露此值，看下方 capture fps 反推)，驱动报告 fps={actual_fps:.1f} (请求 {TARGET_CAMERA_FPS})")
        if fourcc_str and fourcc_str != 'MJPG':
            print("  WARN: 不是 MJPG，相机跑未压缩格式，USB 2.0 带宽不够，fps 会暴跌到个位数")

        # 基于高精度计时的节流，减少抖动
        next_frame_time = time.perf_counter()
        # 实测 fps + 每帧 read+解码 耗时，定位"请求 30 实际只跑到几"
        fps_meter = FpsMeter("capture", "相机 read+解码")

        while is_detecting:
            t_read = time.perf_counter()
            ret, frame = camera_cap.read()
            read_dt = time.perf_counter() - t_read
            if not ret:
                print("✗ 无法读取摄像头帧")
                time.sleep(0.01)
                continue

            # 更新最新帧（用于视频流 & 推理）
            with frame_lock:
                latest_frame = frame.copy()

            fps_meter.tick(read_dt, suffix=f"请求 {TARGET_CAMERA_FPS}")

            # 控制抓帧节奏，趋近 TARGET_CAMERA_FPS
            next_frame_time += 1.0 / max(1, TARGET_CAMERA_FPS)
            sleep_dt = next_frame_time - time.perf_counter()
            if sleep_dt > 0:
                time.sleep(sleep_dt)

    except Exception as e:
        print(f"抓帧循环异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理资源
        if camera_cap:
            camera_cap.release()
            camera_cap = None
        print("抓帧循环已停止")


def inference_loop():
    """YOLO推理循环（后台线程）：周期性读取 latest_frame 做推理，更新 current_detection_data"""
    global is_detecting, detector, latest_frame, current_detection_data

    try:
        # 初始化YOLO检测器
        if YOLO_AVAILABLE and IntegratedWeldDetector:
            # 摄像头标定值（如有），让 PreciseWeldDetector 把宽度像素换算成真实 mm
            try:
                from api.calibration import load_calibration_pixels_per_mm
                pixels_per_mm = load_calibration_pixels_per_mm()
            except Exception:
                pixels_per_mm = None
            with detector_lock:
                detector = IntegratedWeldDetector(
                    config_file=YOLO_CONFIG_FILE,
                    pixels_per_mm=pixels_per_mm,
                )
            cal_msg = f"标定 {pixels_per_mm:.3f} px/mm" if pixels_per_mm else "未标定"
            print(f"✓ YOLO检测器初始化成功（推理线程，{cal_msg}）")
        else:
            print("⚠ YOLO不可用（推理线程使用模拟数据）")
            detector = None

        # 每个推理会话独立 stabilizer
        stabilizer = DetectionStabilizer()

        # 推理频率控制
        interval = 1.0 / max(1, INFERENCE_FPS)
        next_t = time.perf_counter()

        while is_detecting:
            frame = None
            with frame_lock:
                if latest_frame is not None:
                    frame = latest_frame.copy()

            if frame is None:
                time.sleep(0.01)
            else:
                try:
                    if detector:
                        # 使用真实YOLO检测
                        with detector_lock:
                            results = detector.process_frame(frame)

                        raw_scores = {
                            "smoothness": results.get("smoothness_score", 0),
                            "width": results.get("width_score", 0),
                            "defect_type": results.get("defect_score", 0),
                            "total_score": results.get("total_score", 0),
                        }
                        raw_detections = results.get("detections", [])
                        confirmed, smoothed_scores = stabilizer.update(raw_detections, raw_scores)

                        detection_count = len(confirmed)
                        if detection_count == 0:
                            defect_name = "无缺陷"
                        else:
                            # 优先使用中文名称，如果没有则将英文转换为中文
                            defect_name = confirmed[0].get("class_name_cn", "未知")
                            if defect_name == "未知":
                                en_name = confirmed[0].get("class_name", "未知")
                                defect_name = DEFECT_EN_TO_CN.get(en_name, en_name)

                        detection_data = {
                            "smoothness": smoothed_scores.get("smoothness", 0),
                            "width": smoothed_scores.get("width", 0),
                            "defect_type": smoothed_scores.get("defect_type", 0),
                            "total_score": smoothed_scores.get("total_score", 0),
                            "timestamp": time.time(),
                            "actual_width": results.get("width_mm", 0),
                            "defect_type_name": defect_name,
                            "detected_defects": confirmed,
                            "top_y": results.get("top_y"),
                            "bottom_y": results.get("bottom_y"),
                            "detection_count": detection_count,
                            "debug_info": results.get("debug_info", "")
                        }
                    else:
                        # 使用模拟数据
                        import random
                        smoothness = random.randint(70, 95)
                        width = random.randint(70, 95)
                        defect = random.randint(70, 95)
                        detection_data = {
                            "smoothness": smoothness,
                            "width": width,
                            "defect_type": defect,
                            "total_score": round(smoothness * 0.3 + width * 0.3 + defect * 0.4, 2),
                            "timestamp": time.time(),
                            "actual_width": round(random.uniform(4.0, 7.0), 2),
                            "defect_type_name": random.choice(["无缺陷", "气孔", "裂纹", "夹渣", "咬边", "未熔合", "焊瘤", "飞溅"]),
                            "detected_defects": []
                        }

                    # 更新当前检测数据
                    with data_lock:
                        current_detection_data = detection_data

                except Exception as e:
                    print(f"推理出错: {e}")
                    import traceback
                    traceback.print_exc()

            # 节流推理频率
            next_t += interval
            dt = next_t - time.perf_counter()
            if dt > 0:
                time.sleep(dt)

    except Exception as e:
        print(f"推理循环异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 释放YOLO资源
        with detector_lock:
            detector = None
        print("推理循环已停止")


def _probe_cameras(max_index: int = 5, max_consecutive_miss: int = 2) -> List[dict]:
    """没有 pygrabber 时的退路：硬开 0..N-1，能打开就当存在。

    显式走 CAP_DSHOW 而不是 CAP_ANY —— CAP_ANY 会轮询 MSMF / DSHOW /
    Orbbec(深度相机) 等多个后端，没接深度相机时 Orbbec 会刷 obsensor
    `Camera index out of range` 错日志且每个 index 卡几百 ms。
    连续 max_consecutive_miss 个 index 失败就 break，避免空跑到 max_index。
    """
    found: List[dict] = []
    miss = 0
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        try:
            if cap.isOpened():
                found.append({"index": i, "name": f"摄像头 {i}"})
                miss = 0
            else:
                miss += 1
                if miss >= max_consecutive_miss:
                    break
        finally:
            # isOpened() 为 False 时 DirectShow 仍可能持着句柄，无脑释放
            cap.release()
    return found


@router.get("/list-cameras")
async def list_cameras():
    """枚举本机可用摄像头（Windows 走 DirectShow 拿友好名）。

    返回的 index 就是 cv2.VideoCapture(i) 用的设备序号；用户在前端选好哪个是平面
    检测摄像头后，启动检测时回传 camera_id 即可。
    """
    try:
        from pygrabber.dshow_graph import FilterGraph
        names = FilterGraph().get_input_devices()
        cameras = [{"index": i, "name": n} for i, n in enumerate(names)]
    except ImportError:
        cameras = _probe_cameras()
    except Exception as e:
        # pygrabber 在某些 OBS / 虚拟相机配置下会抛 COM 错，退回探测
        print(f"pygrabber 枚举失败，回退暴力探测: {e}")
        cameras = _probe_cameras()

    return {"status": "success", "cameras": cameras, "count": len(cameras)}


@router.post("/start-yolo")
async def start_yolo_detection(request: StartDetectionRequest):
    """启动YOLO检测（后台运行）"""
    global is_detecting

    try:
        if is_detecting:
            return {
                "status": "already_running",
                "message": "YOLO检测已在运行中"
            }

        # 启动抓帧与推理线程
        is_detecting = True
        
        # 确定摄像头来源（优先使用 URL）
        camera_source = request.camera_url if request.camera_url else (request.camera_id if request.camera_id is not None else 0)
        
        # 抓帧线程
        cap_t = threading.Thread(
            target=capture_loop,
            args=(camera_source,),
            daemon=True
        )
        cap_t.start()
        # 推理线程
        inf_t = threading.Thread(
            target=inference_loop,
            daemon=True
        )
        inf_t.start()

        # 保存线程句柄
        global capture_thread, inference_thread
        capture_thread = cap_t
        inference_thread = inf_t

        # 等待一下让检测器初始化
        time.sleep(1)

        return {
            "status": "success",
            "message": "YOLO检测已启动",
            "camera_source": camera_source
        }

    except Exception as e:
        is_detecting = False
        raise HTTPException(
            status_code=500,
            detail=f"启动YOLO检测失败: {str(e)}"
        )


@router.post("/stop-yolo")
async def stop_yolo_detection():
    """停止YOLO检测"""
    global is_detecting, current_detection_data

    try:
        if not is_detecting:
            return {
                "status": "not_running",
                "message": "YOLO检测未在运行"
            }

        # 停止检测
        is_detecting = False

        # 等待线程结束
        global capture_thread, inference_thread
        if inference_thread:
            inference_thread.join(timeout=3)
        if capture_thread:
            capture_thread.join(timeout=3)

        with data_lock:
            current_detection_data = None

        return {
            "status": "success",
            "message": "YOLO检测已停止"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"停止YOLO检测失败: {str(e)}"
        )


@router.get("/yolo-data")
async def get_yolo_data():
    """获取最新的YOLO检测数据"""
    global current_detection_data, is_detecting

    try:
        if not is_detecting:
            return {
                "status": "not_running",
                "data": None
            }

        with data_lock:
            if current_detection_data:
                return {
                    "status": "success",
                    "data": current_detection_data
                }
            else:
                return {
                    "status": "no_data",
                    "data": None,
                    "message": "暂无检测数据"
                }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取YOLO数据失败: {str(e)}"
        )


@router.post("/save-score")
async def save_score(data: ScoreData, db: SessionLocal = Depends(get_db)):
    """
    保存单次检测分数到数据库
    当用户按下按键时，前端调用此接口保存那一刻的分数
    """
    try:
        # 解析时间戳
        try:
            timestamp = datetime.fromisoformat(data.timestamp.replace('Z', '+00:00'))
        except:
            timestamp = datetime.now()

        def _clamp_score(value: float) -> float:
            try:
                return max(0.0, min(100.0, float(value)))
            except (TypeError, ValueError):
                return 0.0

        # TTA 出来的缺陷框入库时记一份归一化坐标，给热图用
        defect_bboxes_payload: Optional[List[dict]] = None

        # 保存前用 TTA 重新算一次，入库分数比实时显示更稳。
        # 关键：roi_tracker.process 没有内部锁，必须拿 detector_lock 不让 inference_loop
        # 同时跑同一个 tracker。整段 detector 调用一起进线程池，事件循环不阻塞。
        if detector is not None and latest_frame is not None and is_detecting:
            try:
                with frame_lock:
                    snap = latest_frame.copy()

                def _run_under_detector_lock():
                    with detector_lock:
                        tta = detector.detect_defects_with_tta(snap)
                        sm = detector.detect_smoothness(snap)
                        wd = detector.detect_width(snap)
                    return detector.calculate_total_score(sm, wd, tta), tta, wd

                composite, tta_def, wd = await asyncio.to_thread(_run_under_detector_lock)
                data.smoothness_score = composite["smoothness_score"]
                data.width_score = composite["width_score"]
                data.defect_score = composite["defect_score"]
                data.total_score = composite["total_score"]
                if wd.get("width_mm"):
                    data.width_mm = float(wd["width_mm"])
                if tta_def.get("detections"):
                    data.defect_type_name = (
                        tta_def["detections"][0].get("class_name_cn")
                        or data.defect_type_name
                    )
                    defect_bboxes_payload = _normalize_bboxes(
                        tta_def["detections"], snap.shape[1], snap.shape[0]
                    )
                print(f"save-score 用 TTA 重算: {tta_def.get('debug_info', '')}")
            except Exception as exc:
                # TTA 失败不阻断保存，沿用前端传来的瞬时分数
                print(f"save-score TTA 失败，沿用前端分数: {exc}")

        # 创建数据库记录
        db_record = models.WeldingRecord(
            timestamp=timestamp,
            student_id=data.student_id,
            student_name=data.student_name,
            batch_id=data.batch_id,
            # 分数夹到 [0,100]
            smoothness_score=_clamp_score(data.smoothness_score),
            spacing_score=_clamp_score(data.width_score),
            defect_type_score=_clamp_score(data.defect_score),
            total_score=_clamp_score(data.total_score),
            actual_width=data.width_mm,
            defect_type_name=data.defect_type_name,
            notes=data.notes,
            defect_bboxes=defect_bboxes_payload,
        )

        db.add(db_record)
        db.commit()
        db.refresh(db_record)

        print(f"✓ 分数已保存到数据库: ID={db_record.id}, 学生={data.student_id or '未知'}, 总分={data.total_score}")

        return {
            "status": "success",
            "message": "分数已保存到数据库",
            "database_id": db_record.id,
            "data": data.dict()
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"保存分数失败: {str(e)}"
        )


@router.get("/recent-scores")
async def get_recent_scores(
    limit: int = 10,
    student_id: Optional[str] = None,
    db: SessionLocal = Depends(get_db),
):
    """获取最近的检测分数记录，可选按学号过滤。"""
    try:
        query = db.query(models.WeldingRecord)
        if student_id:
            query = query.filter(models.WeldingRecord.student_id == student_id)
        records = query.order_by(
            models.WeldingRecord.timestamp.desc()
        ).limit(limit).all()

        scores = []
        for r in records:
            scores.append({
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "student_id": r.student_id,
                "student_name": r.student_name,
                "batch_id": r.batch_id,
                "total_score": r.total_score,
                "smoothness_score": r.smoothness_score,
                "width_score": r.spacing_score,  # 映射回 width_score
                "defect_score": r.defect_type_score,
                "actual_width": r.actual_width,
                "defect_type_name": r.defect_type_name
            })

        return {
            "status": "success",
            "scores": scores,
            "count": len(scores)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取分数记录失败: {str(e)}"
        )


@router.get("/detection-heatmap")
async def get_detection_heatmap(
    student_id: str = Query(..., description="学号"),
    limit: int = Query(200, ge=1, le=2000, description="拉最近多少条按键记录的 bbox"),
    db: SessionLocal = Depends(get_db),
):
    """汇总学生历史按键记录里的归一化缺陷框，给前端画 KDE 热图用。"""
    try:
        rows = (
            db.query(models.WeldingRecord.defect_bboxes)
            .filter(
                models.WeldingRecord.student_id == student_id,
                models.WeldingRecord.defect_bboxes.isnot(None),
            )
            .order_by(models.WeldingRecord.timestamp.desc())
            .limit(limit)
            .all()
        )

        points: List[dict] = []
        by_label: dict = {}
        for (boxes,) in rows:
            if not isinstance(boxes, list):
                continue
            for b in boxes:
                if not isinstance(b, dict):
                    continue
                try:
                    cx, cy = float(b["cx"]), float(b["cy"])
                except (KeyError, TypeError, ValueError):
                    continue
                label = str(b.get("label_cn") or b.get("label") or "未知")
                points.append({
                    "cx": cx,
                    "cy": cy,
                    "w": float(b.get("w", 0.0)),
                    "h": float(b.get("h", 0.0)),
                    "label": label,
                    "conf": float(b.get("conf", 0.0)),
                })
                by_label[label] = by_label.get(label, 0) + 1

        return {
            "status": "success",
            "student_id": student_id,
            "record_count": len(rows),
            "point_count": len(points),
            "points": points,
            "by_label": by_label,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取热图数据失败: {str(e)}")


@router.get("/student-comparison")
async def get_student_comparison(
    batch_id: Optional[str] = None,
    db: SessionLocal = Depends(get_db)
):
    """
    获取学生批次比较数据
    用于PDF报告生成：按学生ID分组，比较不同学生的焊接质量
    """
    try:
        from sqlalchemy import func as sql_func

        # 构建查询
        query = db.query(
            models.WeldingRecord.student_id,
            models.WeldingRecord.student_name,
            models.WeldingRecord.batch_id,
            sql_func.count(models.WeldingRecord.id).label('detection_count'),
            sql_func.avg(models.WeldingRecord.total_score).label('avg_total_score'),
            sql_func.avg(models.WeldingRecord.smoothness_score).label('avg_smoothness'),
            sql_func.avg(models.WeldingRecord.spacing_score).label('avg_width'),
            sql_func.avg(models.WeldingRecord.defect_type_score).label('avg_defect'),
            sql_func.max(models.WeldingRecord.total_score).label('max_score'),
            sql_func.min(models.WeldingRecord.total_score).label('min_score')
        ).filter(
            models.WeldingRecord.student_id.isnot(None)
        )

        if batch_id:
            query = query.filter(models.WeldingRecord.batch_id == batch_id)

        query = query.group_by(
            models.WeldingRecord.student_id,
            models.WeldingRecord.student_name,
            models.WeldingRecord.batch_id
        ).order_by(sql_func.avg(models.WeldingRecord.total_score).desc())

        results = query.all()

        comparison_data = []
        for r in results:
            comparison_data.append({
                "student_id": r.student_id,
                "student_name": r.student_name or "未知学生",
                "batch_id": r.batch_id,
                "detection_count": r.detection_count,
                "avg_total_score": round(r.avg_total_score, 1) if r.avg_total_score else 0,
                "avg_smoothness": round(r.avg_smoothness, 1) if r.avg_smoothness else 0,
                "avg_width": round(r.avg_width, 1) if r.avg_width else 0,
                "avg_defect": round(r.avg_defect, 1) if r.avg_defect else 0,
                "max_score": round(r.max_score, 1) if r.max_score else 0,
                "min_score": round(r.min_score, 1) if r.min_score else 0
            })

        return {
            "status": "success",
            "batch_id": batch_id,
            "comparison_data": comparison_data,
            "total_students": len(comparison_data)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取学生比较数据失败: {str(e)}"
        )


@router.get("/batch-list")
async def get_batch_list(db: SessionLocal = Depends(get_db)):
    """获取所有批次ID列表"""
    try:
        from sqlalchemy import distinct

        batches = db.query(distinct(models.WeldingRecord.batch_id)).filter(
            models.WeldingRecord.batch_id.isnot(None)
        ).all()

        batch_list = [b[0] for b in batches if b[0]]

        return {
            "status": "success",
            "batches": batch_list,
            "count": len(batch_list)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取批次列表失败: {str(e)}"
        )


class FrameDetectionRequest(BaseModel):
    """前端发送的帧数据"""
    frame_data: str  # base64编码的图像


def generate_video_stream(fps: int, quality: int, width: int, height: int):
    """生成MJPEG视频流 - 使用 capture_loop 捕获的帧

    参数：
      - fps: 目标推流帧率
      - quality: JPEG编码质量（10-95）
      - width, height: 编码前缩放到此分辨率
    """
    global latest_frame, current_detection_data, is_detecting

    # 预设下一帧发送时间，确保稳定帧间隔
    frame_interval = 1.0 / max(1, fps)
    next_send_time = time.perf_counter()

    # 待机黑屏帧只构造一次：2K 时 zeros((1440,2560,3)) 是 ~10MB，每帧重分配很贵
    idle_frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(idle_frame, "Camera not started", (150, 240),
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    fps_meter = FpsMeter("stream", "JPEG 编码")

    while True:
        if not is_detecting or latest_frame is None:
            ret, buffer = cv2.imencode('.jpg', idle_frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            # 维持节奏
            next_send_time += frame_interval
            sleep_dt = next_send_time - time.perf_counter()
            if sleep_dt > 0:
                time.sleep(sleep_dt)
            continue

        # 获取最新帧的副本
        with frame_lock:
            display_frame = latest_frame.copy()

        # 按需缩放，降低编码负载
        if display_frame.shape[1] != width or display_frame.shape[0] != height:
            try:
                display_frame = cv2.resize(display_frame, (width, height), interpolation=cv2.INTER_AREA)
            except Exception:
                pass

        # 在帧上绘制检测结果 - 自定义绘制（解决top_y为None和中文显示问题）
        with data_lock:
            if current_detection_data:
                font = cv2.FONT_HERSHEY_SIMPLEX

                # 1. 绘制总分
                total_score = current_detection_data.get('total_score', 0)
                score_color = (0, 255, 0) if total_score >= 80 else (0, 165, 255) if total_score >= 60 else (0, 0, 255)
                cv2.putText(display_frame, f'Total Score: {total_score:.1f}',
                          (10, 40), font, 1.0, score_color, 3)

                # 2. 绘制各模块得分
                smoothness = current_detection_data.get("smoothness", 0)
                cv2.putText(display_frame, f'Smoothness: {smoothness:.1f}',
                          (10, 80), font, 0.6, (255, 255, 255), 2)

                width_mm = current_detection_data.get("actual_width", 0)
                width_score = current_detection_data.get("width", 0)
                cv2.putText(display_frame, f'Width: {width_mm:.1f}mm ({width_score:.1f})',
                          (10, 110), font, 0.6, (255, 255, 255), 2)

                defect_score = current_detection_data.get("defect_type", 0)
                detection_count = current_detection_data.get("detection_count", 0)
                cv2.putText(display_frame, f'Defect: {defect_score:.1f} ({detection_count} found)',
                          (10, 140), font, 0.6, (255, 255, 255), 2)

                # 3. 绘制焊缝宽度标记线（如果有）
                top_y = current_detection_data.get("top_y")
                bottom_y = current_detection_data.get("bottom_y")
                if top_y is not None and bottom_y is not None:
                    cv2.line(display_frame, (0, top_y), (display_frame.shape[1], top_y), (0, 0, 255), 3)
                    cv2.line(display_frame, (0, bottom_y), (display_frame.shape[1], bottom_y), (0, 0, 255), 3)
                    cv2.putText(display_frame, f'Top: {top_y}', (10, top_y-10 if top_y > 20 else top_y+20),
                              font, 0.5, (0, 0, 255), 2)
                    cv2.putText(display_frame, f'Bottom: {bottom_y}', (10, bottom_y+20),
                              font, 0.5, (0, 0, 255), 2)

                # 4. 绘制缺陷检测框
                detections = current_detection_data.get("detected_defects", [])
                for detection in detections:
                    box = detection.get("box", [])
                    if len(box) == 4:
                        x1, y1, x2, y2 = map(int, box)
                        class_name = detection.get("class_name", "Unknown")
                        confidence = detection.get("confidence", 0)

                        # 选择颜色
                        color = (0, 255, 0) if "Good" in class_name else (0, 0, 255)

                        # 绘制框和标签
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                        label = f'{class_name}: {confidence:.2f}'
                        cv2.putText(display_frame, label, (x1, y1-10 if y1 > 20 else y1+20),
                                  font, 0.6, color, 2)

        # 编码为JPEG
        t_enc = time.perf_counter()
        ret, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        encode_dt = time.perf_counter() - t_enc
        if not ret:
            continue

        fps_meter.tick(encode_dt, suffix=f"请求 {fps}，{width}x{height} q={quality}")

        frame_bytes = buffer.tobytes()

        # 返回MJPEG格式
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        # 维持推流帧率
        next_send_time += frame_interval
        sleep_dt = next_send_time - time.perf_counter()
        if sleep_dt > 0:
            time.sleep(sleep_dt)


@router.get("/video-stream")
async def video_stream(
    fps: int = Query(STREAM_DEFAULT_FPS, ge=1, le=120, description="目标推流FPS"),
    quality: int = Query(JPEG_DEFAULT_QUALITY, ge=10, le=95, description="JPEG质量(10-95)"),
    width: int = Query(DEFAULT_WIDTH, ge=160, le=2560, description="编码宽度"),
    height: int = Query(DEFAULT_HEIGHT, ge=120, le=1440, description="编码高度"),
):
    """MJPEG视频流接口（支持通过查询参数调整FPS/质量/分辨率）"""
    return StreamingResponse(
        generate_video_stream(fps=fps, quality=quality, width=width, height=height),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/snapshot")
async def get_snapshot():
    """返回当前 latest_frame 的 JPEG base64，供前端标定面板抓静态画面。"""
    global latest_frame, is_detecting
    if not is_detecting:
        raise HTTPException(status_code=409, detail="检测未启动，请先开启实时检测再抓画面")
    with frame_lock:
        if latest_frame is None:
            raise HTTPException(status_code=503, detail="暂无可用画面，请稍后重试")
        frame = latest_frame.copy()
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise HTTPException(status_code=500, detail="画面编码失败")
    return {
        "image_base64": base64.b64encode(buf.tobytes()).decode("ascii"),
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
    }


@router.post("/detect-frame")
async def detect_frame(request: FrameDetectionRequest):
    """
    接收前端发送的摄像头帧，进行YOLO检测
    前端通过canvas捕获video帧，转为base64发送
    """
    global detector

    try:
        # 初始化检测器（如果还没初始化）
        if detector is None and YOLO_AVAILABLE and IntegratedWeldDetector:
            detector = IntegratedWeldDetector(config_file=YOLO_CONFIG_FILE)
            print("✓ YOLO检测器初始化成功")

        # 解码base64图像
        try:
            # 移除data:image前缀（如果有）
            image_data = request.frame_data
            if ',' in image_data:
                image_data = image_data.split(',')[1]

            # 解码base64
            image_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                raise ValueError("无法解码图像")

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"图像解码失败: {str(e)}"
            )

        # 进行YOLO检测
        if detector:
            try:
                results = detector.detect_frame(frame)

                detection_data = {
                    "smoothness": results.get("smoothness_score", 0),
                    "width": results.get("width_score", 0),
                    "defect_type": results.get("defect_score", 0),
                    "total_score": results.get("total_score", 0),
                    "timestamp": time.time(),
                    "actual_width": results.get("width_mm", 0),
                    "defect_type_name": results.get("defect_type", "未知"),
                    "detected_defects": results.get("detections", [])
                }

                return {
                    "status": "success",
                    "data": detection_data
                }

            except Exception as e:
                print(f"YOLO检测失败: {e}")
                import traceback
                traceback.print_exc()
                # 如果YOLO检测失败，返回模拟数据
                raise HTTPException(
                    status_code=500,
                    detail=f"YOLO检测失败: {str(e)}"
                )
        else:
            # YOLO不可用，返回模拟数据
            import random
            smoothness = random.randint(70, 95)
            width = random.randint(70, 95)
            defect = random.randint(70, 95)

            detection_data = {
                "smoothness": smoothness,
                "width": width,
                "defect_type": defect,
                "total_score": round(smoothness * 0.3 + width * 0.3 + defect * 0.4, 2),
                "timestamp": time.time(),
                "actual_width": round(random.uniform(4.0, 7.0), 2),
                "defect_type_name": random.choice(["无缺陷", "气孔", "裂纹"]),
                "detected_defects": []
            }

            return {
                "status": "success",
                "data": detection_data,
                "note": "YOLO不可用，使用模拟数据"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"检测失败: {str(e)}"
        )


class ImageDetectionRequest(BaseModel):
    """前端发送的图片数据"""
    image_data: str  # base64编码的图像


@router.post("/detect-image")
async def detect_image(request: ImageDetectionRequest):
    """
    接收前端上传的图片，进行YOLO检测
    用于上传图片检测功能
    """
    global detector

    try:
        # 初始化检测器（如果还没初始化）
        if detector is None and YOLO_AVAILABLE and IntegratedWeldDetector:
            detector = IntegratedWeldDetector(config_file=YOLO_CONFIG_FILE)
            print("✓ YOLO检测器初始化成功（图片检测）")

        # 解码base64图像
        try:
            # 移除data:image前缀（如果有）
            image_data = request.image_data
            if ',' in image_data:
                image_data = image_data.split(',')[1]

            # 解码base64
            image_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                raise ValueError("无法解码图像")

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"图像解码失败: {str(e)}"
            )

        # 进行YOLO检测
        if detector:
            try:
                results = detector.process_frame(frame)

                detection_data = {
                    "smoothness": results.get("smoothness_score", 0),
                    "width": results.get("width_score", 0),
                    "defect_type": results.get("defect_score", 0),
                    "total_score": results.get("total_score", 0),
                    "timestamp": time.time(),
                    "actual_width": results.get("width_mm", 0),
                    "defect_type_name": results.get("defect_type", "未知"),
                    "detected_defects": results.get("detections", []),
                    "detection_count": results.get("detection_count", 0)
                }

                return {
                    "status": "success",
                    "data": detection_data
                }

            except Exception as e:
                print(f"YOLO检测失败: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"YOLO检测失败: {str(e)}"
                )
        else:
            # YOLO不可用，返回模拟数据
            import random
            smoothness = random.randint(70, 95)
            width = random.randint(70, 95)
            defect = random.randint(70, 95)

            detection_data = {
                "smoothness": smoothness,
                "width": width,
                "defect_type": defect,
                "total_score": round(smoothness * 0.3 + width * 0.3 + defect * 0.4, 2),
                "timestamp": time.time(),
                "actual_width": round(random.uniform(4.0, 7.0), 2),
                "defect_type_name": random.choice(["无缺陷", "气孔", "裂纹"]),
                "detected_defects": []
            }

            return {
                "status": "success",
                "data": detection_data,
                "note": "YOLO不可用，使用模拟数据"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"检测失败: {str(e)}"
        )


# 清理资源的回调
@router.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    global is_detecting, camera_cap
    is_detecting = False
    if camera_cap:
        camera_cap.release()