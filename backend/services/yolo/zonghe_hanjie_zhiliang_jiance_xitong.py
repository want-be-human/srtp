# -*- coding: utf-8 -*-
"""光滑度 + 宽度 + YOLO 缺陷三路并行的焊缝综合检测系统。"""

import cv2
import time
import numpy as np
import json
import os
import sys
from typing import Dict, List, Tuple, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_device():
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
        return "cpu"
    except ImportError:
        return "cpu"
    except Exception:
        return "cpu"


DEVICE = get_device()

try:
    from ultralytics import YOLO
    from .guanghuadu_jiance_qiqi import WeldingQualityScorer
    from .kuandu_jiance_qiqi import PreciseWeldDetector
    from .weld_roi import WeldRoiTracker

    # torch 2.6 把 weights_only 默认改成 True，加载 best.pt 会爆白名单错误。
    # best.pt 来源可信，直接把 weights_only 默认改回 False。
    try:
        import torch
        if not getattr(torch.load, "_srtp_patched", False):
            _orig_torch_load = torch.load

            def _trusted_torch_load(*args, **kwargs):
                kwargs.setdefault("weights_only", False)
                return _orig_torch_load(*args, **kwargs)

            _trusted_torch_load._srtp_patched = True
            torch.load = _trusted_torch_load
    except Exception:
        pass

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    from defect_types import (
        DEFECT_CLASSES,
        DEFECT_ID_TO_CN,
        DEFECT_EN_TO_CN,
        get_severity_level,
    )
except ImportError as e:
    print(f"模块导入失败: {e}")
    print("请确保安装了所需的依赖包")


class IntegratedWeldDetector:

    def __init__(self, config_file: str = None, pixels_per_mm: Optional[float] = None):
        # pixels_per_mm 来自摄像头标定（CameraCalibration 表）；None 时宽度走估算
        self.pixels_per_mm = pixels_per_mm
        self.config = self._load_config(config_file)
        self._init_modules()
        self.total_frames = 0
        self.detection_history = []

    def _load_config(self, config_file: str = None) -> Dict:
        default_config = {
            "yolo_model_path": "models/best.pt",
            "confidence_threshold": 0.5,
            "iou_threshold": 0.45,
            "scoring_weights": {
                "smoothness_weight": 0.3,
                "width_weight": 0.3,
                "defect_weight": 0.4,
            },
            "width_thresholds": {
                "min_width_mm": 9.0,
                "max_width_mm": 11.0,
                "optimal_width_mm": 10.0,
            },
            "display": {
                "window_width": 1280,
                "window_height": 720,
                "font_scale": 0.6,
                "line_thickness": 2,
            },
        }

        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                print(f"警告：无法加载配置文件 {config_file}，使用默认配置。错误：{e}")

        return default_config

    def _init_modules(self):
        print("正在初始化检测模块...")

        # 焊缝 ROI 跟踪器：跨帧复用上帧 bbox，给 YOLO 喂压过曝 + 背景衰减的输入
        self.roi_tracker = WeldRoiTracker()

        try:
            self.smoothness_detector = WeldingQualityScorer()
            print("[OK] 光滑度检测模块初始化完成")
        except Exception as e:
            print(f"[ERR] 光滑度检测模块初始化失败: {e}")
            self.smoothness_detector = None

        try:
            self.width_detector = PreciseWeldDetector(
                debug=False,
                pixels_per_mm=self.pixels_per_mm,
            )
            cal_note = "已标定" if self.pixels_per_mm else "未标定，走估算"
            print(f"[OK] 宽度检测模块初始化完成（{cal_note}）")
        except Exception as e:
            print(f"[ERR] 宽度检测模块初始化失败: {e}")
            self.width_detector = None

        try:
            yolo_path = self.config["yolo_model_path"]
            if not os.path.exists(yolo_path):
                yolo_path = os.path.join(os.path.dirname(__file__), yolo_path)

            if os.path.exists(yolo_path):
                self.yolo_model = YOLO(yolo_path)
                self.defect_classes = DEFECT_CLASSES
                self.defect_classes_cn = DEFECT_ID_TO_CN

                self.device = DEVICE
                self.yolo_model.to(self.device)
                print(f"[OK] YOLO 检测模块初始化完成（{len(DEFECT_CLASSES)} 类缺陷，路径 {yolo_path}）")
            else:
                print(f"[ERR] YOLO 模型文件未找到: {yolo_path}")
                print(f"  备选路径: {os.path.join(os.path.dirname(__file__), 'models/best.pt')}")
                self.yolo_model = None
                self.defect_classes = {}
                self.device = "cpu"
        except Exception as e:
            print(f"[ERR] YOLO 缺陷检测模块初始化失败: {e}")
            self.yolo_model = None
            self.defect_classes = {}
            self.device = "cpu"

    def detect_smoothness(self, frame: np.ndarray) -> Dict:
        if self.smoothness_detector is None:
            return {"score": 0, "error": "光滑度检测器未初始化"}

        try:
            detection_region = self.smoothness_detector._get_detection_region(frame)
            brightness_analysis = self.smoothness_detector._analyze_brightness(
                detection_region
            )
            score = self.smoothness_detector._calculate_score(brightness_analysis)

            return {
                "score": float(round(score, 2)),
                "brightness_analysis": {
                    "white_ratio": float(round(brightness_analysis["white_ratio"], 4)),
                    "gray_ratio": float(round(brightness_analysis["gray_ratio"], 4)),
                    "black_ratio": float(round(brightness_analysis["black_ratio"], 4)),
                },
            }
        except Exception as e:
            return {"score": 0, "error": str(e)}

    def detect_width(self, frame: np.ndarray) -> Dict:
        if self.width_detector is None:
            return {"width_mm": 0, "score": 0, "error": "宽度检测器未初始化"}

        try:
            # ROI bbox 可能落后于 detect_defects 一帧（并行线程），但只用来圈搜索带，1 帧偏差无影响
            result = self.width_detector.enhanced_weld_detection(
                cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                roi_bbox=self.roi_tracker.last_bbox,
            )

            if result["found"]:
                width_mm = result["thickness_mm"]
                width_score = self._calculate_width_score(width_mm)

                return {
                    "width_mm": float(width_mm),
                    "score": float(width_score),
                    "top_y": int(result["top_y"]),
                    "bottom_y": int(result["bottom_y"]),
                    "center_y": int(result["center_y"]),
                    "rejected_count": int(result.get("rejected_count", 0)),
                }
            else:
                return {
                    "width_mm": 0,
                    "score": 0,
                    "error": "未检测到焊缝",
                    "rejected_count": int(result.get("rejected_count", 0)),
                }
        except Exception as e:
            return {"width_mm": 0, "score": 0, "error": str(e)}

    def _apply_defect_score(self, current: int, cls: int) -> int:
        """根据 cls 严重等级调整 defect_score；按 best.pt 6 类映射。"""
        if cls == 3:  # Good Welding
            return current + 10
        if cls in (0, 1):  # 严重：Bad Welding / Crack
            return current - 35
        if cls == 4:  # 中等：Porosity
            return current - 20
        if cls in (2, 5):  # 轻微：Excess Reinforcement / Spatters
            return current - 8
        return current

    def detect_defects(self, frame: np.ndarray, use_tta: bool = False) -> Dict:
        """检测缺陷类型；use_tta=True 时走 ultralytics 内置 augment（多尺度+翻转 TTA），实时流默认关。"""
        if self.yolo_model is None:
            return {
                "detections": [],
                "score": 100,
                "error": "YOLO模型未初始化",
                "debug_info": "模型未加载",
            }

        try:
            yolo_input = self.roi_tracker.process(frame)

            # 默认 1280 而不是 ultralytics 内置 640：焊缝小缺陷（裂纹/气孔）letterbox 后
            # 输入像素多 4×；4060 单帧 < 50ms，远低于 INFERENCE_FPS=6 的 166ms 预算
            imgsz = self.config.get("optimization", {}).get("yolo_imgsz", 1280)
            results = self.yolo_model(
                yolo_input,
                conf=self.config["confidence_threshold"],
                iou=self.config["iou_threshold"],
                imgsz=imgsz,
                device=self.device,
                verbose=False,
                augment=use_tta,
            )

            detections = []
            defect_score = 100
            raw_count = 0
            dropped_outside = 0

            if results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                raw_count = len(boxes)

                for i in range(raw_count):
                    box = boxes.xyxy[i].cpu().numpy()
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls = int(boxes.cls[i].cpu().numpy())

                    if conf < self.config["confidence_threshold"]:
                        continue
                    if not self.roi_tracker.should_keep_box(box.tolist()):
                        dropped_outside += 1
                        continue

                    detections.append({
                        "box": box.tolist(),
                        "confidence": float(conf),
                        "class": int(cls),
                        "class_name": str(self.defect_classes.get(cls, f"Unknown_{cls}")),
                        "class_name_cn": str(self.defect_classes_cn.get(cls, "未知缺陷")),
                    })
                    defect_score = self._apply_defect_score(defect_score, cls)

            defect_score = max(0, min(100, defect_score))
            tag = "TTA" if use_tta else "YOLO"
            roi_active = self.roi_tracker.last_bbox is not None
            debug_info = (
                f"{tag} {raw_count} 框，ROI 内保留 {len(detections)}，剔除 {dropped_outside}"
                if roi_active else f"{tag} {raw_count} 框（ROI 未建立）"
            )

            return {
                "detections": detections,
                "score": float(defect_score),
                "debug_info": str(debug_info),
                "detection_count": int(len(detections)),
                "seam_theta": float(self.roi_tracker.last_theta),
                "roi_bbox": (
                    list(self.roi_tracker.last_bbox)
                    if self.roi_tracker.last_bbox is not None else None
                ),
                "dropped_outside": int(dropped_outside),
                "annotated_frame": results[0].plot()
                if results[0].boxes is not None
                else frame,
            }
        except Exception as e:
            return {"detections": [], "score": 0, "error": str(e)}

    def detect_defects_with_tta(self, frame: np.ndarray) -> Dict:
        """ultralytics 自带 augment=True 跑 TTA，比单次推理稳，保存按键时调。"""
        return self.detect_defects(frame, use_tta=True)

    def _calculate_width_score(self, width_mm: float) -> float:
        thresholds = self.config["width_thresholds"]
        optimal = thresholds["optimal_width_mm"]
        min_width = thresholds["min_width_mm"]
        max_width = thresholds["max_width_mm"]

        if width_mm < min_width or width_mm > max_width:
            return 20

        distance = abs(width_mm - optimal)
        max_distance = max(optimal - min_width, max_width - optimal)
        # 距离最佳宽度按线性掉分，最多扣 60；超出范围直接保底 20
        score = 100 - (distance / max_distance) * 60
        return max(20, min(100, score))

    def calculate_total_score(
        self, smoothness_result: Dict, width_result: Dict, defect_result: Dict
    ) -> Dict:
        weights = self.config["scoring_weights"]

        smoothness_score = smoothness_result.get("score", 0)
        width_score = width_result.get("score", 0)
        defect_score = defect_result.get("score", 0)

        total_score = (
            smoothness_score * weights["smoothness_weight"]
            + width_score * weights["width_weight"]
            + defect_score * weights["defect_weight"]
        )

        return {
            "total_score": float(round(total_score, 2)),
            "smoothness_score": float(round(smoothness_score, 2)),
            "width_score": float(round(width_score, 2)),
            "defect_score": float(round(defect_score, 2)),
            "weights": weights,
        }

    def draw_results(self, frame: np.ndarray, results: Dict) -> np.ndarray:
        display_frame = frame.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = self.config["display"]["font_scale"]
        thickness = self.config["display"]["line_thickness"]

        total_score = results.get("total_score", 0)
        score_color = (
            (0, 255, 0)
            if total_score >= 80
            else (0, 165, 255)
            if total_score >= 60
            else (0, 0, 255)
        )
        cv2.putText(
            display_frame,
            f"Total Score: {total_score}",
            (10, 40),
            font,
            1.0,
            score_color,
            3,
        )

        y_offset = 80
        cv2.putText(
            display_frame,
            f"Smoothness: {results.get('smoothness_score', 0)}",
            (10, y_offset),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
        )

        y_offset += 30
        width_mm = results.get("width_mm", 0)
        cv2.putText(
            display_frame,
            f"Width: {width_mm:.1f}mm ({results.get('width_score', 0)})",
            (10, y_offset),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
        )

        y_offset += 30
        defect_score = results.get("defect_score", 0)
        detection_count = results.get("detection_count", 0)
        cv2.putText(
            display_frame,
            f"Defect: {defect_score} ({detection_count} found)",
            (10, y_offset),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
        )

        y_offset += 25
        debug_info = results.get("debug_info", "")
        cv2.putText(
            display_frame,
            f"Debug: {debug_info}",
            (10, y_offset),
            font,
            font_scale * 0.8,
            (128, 128, 128),
            thickness,
        )

        if "top_y" in results and "bottom_y" in results:
            cv2.line(
                display_frame,
                (0, results["top_y"]),
                (frame.shape[1], results["top_y"]),
                (0, 0, 255),
                3,
            )
            cv2.line(
                display_frame,
                (0, results["bottom_y"]),
                (frame.shape[1], results["bottom_y"]),
                (0, 0, 255),
                3,
            )
            cv2.putText(
                display_frame,
                f"Top: {results['top_y']}",
                (10, results["top_y"] - 10),
                font,
                0.5,
                (0, 0, 255),
                2,
            )
            cv2.putText(
                display_frame,
                f"Bottom: {results['bottom_y']}",
                (10, results["bottom_y"] + 20),
                font,
                0.5,
                (0, 0, 255),
                2,
            )
        else:
            cv2.putText(
                display_frame, "No width detected", (10, 150), font, 0.6, (0, 0, 255), 2
            )

        if "detections" in results:
            for detection in results["detections"]:
                box = detection["box"]
                x1, y1, x2, y2 = map(int, box)
                class_name = detection["class_name"]
                confidence = detection["confidence"]

                color = (0, 255, 0) if "Good" in class_name else (0, 0, 255)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                label = f"{class_name}: {confidence:.2f}"
                cv2.putText(
                    display_frame,
                    label,
                    (x1, y1 - 10),
                    font,
                    font_scale,
                    color,
                    thickness,
                )

        return display_frame

    def process_frame(self, frame: np.ndarray) -> Dict:
        start_time = time.time()

        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_smoothness = executor.submit(self.detect_smoothness, frame)
            future_width = executor.submit(self.detect_width, frame)
            future_defects = executor.submit(self.detect_defects, frame)

            results["smoothness"] = future_smoothness.result()
            results["width"] = future_width.result()
            results["defects"] = future_defects.result()

        score_result = self.calculate_total_score(
            results["smoothness"], results["width"], results["defects"]
        )

        integrated_result = {
            **score_result,
            "width_mm": results["width"].get("width_mm", 0),
            "detections": results["defects"].get("detections", []),
            "detection_count": results["defects"].get("detection_count", 0),
            "debug_info": results["defects"].get("debug_info", ""),
            "seam_theta": results["defects"].get("seam_theta", 0.0),
            "roi_bbox": results["defects"].get("roi_bbox"),
            "dropped_outside": results["defects"].get("dropped_outside", 0),
            "width_rejected_count": results["width"].get("rejected_count", 0),
            "processing_time": time.time() - start_time,
        }

        if "top_y" in results["width"]:
            integrated_result["top_y"] = results["width"]["top_y"]
            integrated_result["bottom_y"] = results["width"]["bottom_y"]
            integrated_result["center_y"] = results["width"]["center_y"]

        self.total_frames += 1
        return integrated_result

    def find_camera(self) -> Optional[int]:
        print("正在搜索可用摄像头...")
        for camera_id in range(10):
            cap = cv2.VideoCapture(camera_id)
            ret, _ = cap.read()
            cap.release()
            if ret:
                print(f"找到摄像头，ID: {camera_id}")
                return camera_id
        print("未找到可用摄像头")
        return None

    def run_camera_detection(self, camera_id: Optional[int] = None):
        if camera_id is None:
            camera_id = self.find_camera()
            if camera_id is None:
                print("无法找到摄像头")
                return

        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print(f"无法打开摄像头 ID: {camera_id}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config["display"]["window_width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config["display"]["window_height"])
        cap.set(cv2.CAP_PROP_FPS, 30)

        print("开始实时检测...")
        print("按 'q' 退出程序")
        print("按 's' 保存当前画面")
        print("按 'r' 重置统计信息")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("无法读取摄像头画面")
                    break

                results = self.process_frame(frame)
                display_frame = self.draw_results(frame, results)
                cv2.imshow("焊缝质量综合检测系统", display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("s"):
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    save_path = f"detection_{timestamp}.jpg"
                    cv2.imwrite(save_path, display_frame)
                    print(f"当前画面已保存: {save_path}")
                elif key == ord("r"):
                    self.total_frames = 0
                    self.detection_history = []
                    print("统计信息已重置")

        except KeyboardInterrupt:
            print("\n程序被用户中断")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            print(f"检测完成，共处理 {self.total_frames} 帧")

    def run_video_detection(self, video_path: str):
        if not os.path.exists(video_path):
            print(f"视频文件不存在: {video_path}")
            return

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"无法打开视频文件: {video_path}")
            return

        print(f"开始检测视频: {video_path}")
        print("按 'q' 退出程序")
        print("按 's' 保存当前画面")
        print("按空格键暂停/继续")

        paused = False

        try:
            while True:
                if not paused:
                    ret, frame = cap.read()
                    if not ret:
                        print("视频处理完成")
                        break

                    results = self.process_frame(frame)
                    display_frame = self.draw_results(frame, results)
                else:
                    cv2.imshow("焊缝质量综合检测系统 - 视频检测", display_frame)

                cv2.imshow("焊缝质量综合检测系统 - 视频检测", display_frame)

                key = cv2.waitKey(30) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("s"):
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    save_path = f"video_detection_{timestamp}.jpg"
                    cv2.imwrite(save_path, display_frame)
                    print(f"当前画面已保存: {save_path}")
                elif key == ord(" "):
                    paused = not paused
                    print("已暂停" if paused else "继续播放")

        except KeyboardInterrupt:
            print("\n程序被用户中断")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            print(f"检测完成，共处理 {self.total_frames} 帧")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="焊缝质量综合检测系统")
    parser.add_argument("--camera", "-c", type=int, help="摄像头ID")
    parser.add_argument("--video", "-v", type=str, help="视频文件路径")
    parser.add_argument("--config", type=str, help="配置文件路径")

    args = parser.parse_args()

    print("焊缝质量综合检测系统")
    detector = IntegratedWeldDetector(args.config)

    if args.video:
        detector.run_video_detection(args.video)
    else:
        detector.run_camera_detection(args.camera)

    print("程序结束")


if __name__ == "__main__":
    main()
