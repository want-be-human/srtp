# -*- coding: utf-8 -*-
"""
焊缝质量综合检测系统
整合光滑度检测、焊缝宽度检测、YOLOv8缺陷检测三个模块
支持实时摄像头和视频文件检测
支持GPU加速和多线程处理
"""

import cv2
import time
import numpy as np
import json
import os
import sys
from typing import Dict, List, Tuple, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


# GPU检测和配置（静默模式）
def get_device():
    """自动检测并返回最佳计算设备（静默模式，不输出日志）"""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
        return "cpu"
    except ImportError:
        return "cpu"
    except Exception:
        return "cpu"


# 获取全局设备设置
DEVICE = get_device()

# 导入本地模块
try:
    from ultralytics import YOLO
    from .guanghuadu_jiance_qiqi import WeldingQualityScorer
    from .kuandu_jiance_qiqi import PreciseWeldDetector

    # 导入统一的缺陷类型定义
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
    """焊缝质量综合检测系统"""

    def __init__(self, config_file: str = None):
        """
        初始化综合检测系统

        Args:
            config_file: 配置文件路径
        """
        # 加载配置
        self.config = self._load_config(config_file)

        # 初始化各个检测模块
        self._init_modules()

        # 统计信息
        self.total_frames = 0
        self.detection_history = []

    def _load_config(self, config_file: str = None) -> Dict:
        """加载配置参数"""
        default_config = {
            "yolo_model_path": "models/best.pt",
            "confidence_threshold": 0.3,  # 降低置信度阈值，更容易检测到缺陷
            "iou_threshold": 0.45,
            "scoring_weights": {
                "smoothness_weight": 0.3,  # 光滑度权重
                "width_weight": 0.3,  # 宽度权重
                "defect_weight": 0.4,  # 缺陷权重
            },
            "width_thresholds": {
                "min_width_mm": 3.0,  # 最小宽度 3mm
                "max_width_mm": 8.0,  # 最大宽度 8mm
                "optimal_width_mm": 5.5,  # 最佳宽度 5.5mm
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
        """初始化各检测模块"""
        print("正在初始化检测模块...")

        # 1. 初始化光滑度检测器
        try:
            self.smoothness_detector = WeldingQualityScorer()
            print("✓ 光滑度检测模块初始化完成")
        except Exception as e:
            print(f"✗ 光滑度检测模块初始化失败: {e}")
            self.smoothness_detector = None

        # 2. 初始化宽度检测器
        try:
            self.width_detector = PreciseWeldDetector(debug=False, image_height_cm=15.0)
            print("✓ 宽度检测模块初始化完成")
        except Exception as e:
            print(f"✗ 宽度检测模块初始化失败: {e}")
            self.width_detector = None

        # 3. 初始化YOLO缺陷检测器（支持GPU加速）
        try:
            yolo_path = self.config["yolo_model_path"]
            if not os.path.exists(yolo_path):
                # 尝试相对路径
                yolo_path = os.path.join(os.path.dirname(__file__), yolo_path)

            if os.path.exists(yolo_path):
                self.yolo_model = YOLO(yolo_path)
                # 使用统一的缺陷类型定义
                self.defect_classes = DEFECT_CLASSES
                self.defect_classes_cn = DEFECT_ID_TO_CN

                # 设置设备（GPU优先，静默模式）
                self.device = DEVICE
                self.yolo_model.to(self.device)
                print(f"✓ YOLO缺陷检测模块初始化完成")
                print(f"✓ 模型路径: {yolo_path}")
                print(f"✓ 支持{len(DEFECT_CLASSES)}种缺陷类型识别")
            else:
                print(f"✗ YOLO模型文件未找到: {yolo_path}")
                print("请检查以下路径是否存在模型文件:")
                print(f"  - {yolo_path}")
                print(
                    f"  - {os.path.join(os.path.dirname(__file__), 'models/best.pt')}"
                )
                self.yolo_model = None
                self.defect_classes = {}
                self.device = "cpu"
        except Exception as e:
            print(f"✗ YOLO缺陷检测模块初始化失败: {e}")
            self.yolo_model = None
            self.defect_classes = {}
            self.device = "cpu"

    def detect_smoothness(self, frame: np.ndarray) -> Dict:
        """检测光滑度得分"""
        if self.smoothness_detector is None:
            return {"score": 0, "error": "光滑度检测器未初始化"}

        try:
            # 直接在内存中处理，不保存临时文件
            # 获取检测区域
            detection_region = self.smoothness_detector._get_detection_region(frame)

            # 分析明暗度
            brightness_analysis = self.smoothness_detector._analyze_brightness(
                detection_region
            )

            # 计算得分
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
        """检测焊缝宽度"""
        if self.width_detector is None:
            return {"width_mm": 0, "score": 0, "error": "宽度检测器未初始化"}

        try:
            result = self.width_detector.enhanced_weld_detection(
                cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            )

            if result["found"]:
                width_mm = result["thickness_mm"]
                # 根据宽度计算得分 (0-100)
                width_score = self._calculate_width_score(width_mm)

                return {
                    "width_mm": float(width_mm),
                    "score": float(width_score),
                    "top_y": int(result["top_y"]),
                    "bottom_y": int(result["bottom_y"]),
                    "center_y": int(result["center_y"]),
                }
            else:
                return {"width_mm": 0, "score": 0, "error": "未检测到焊缝"}
        except Exception as e:
            return {"width_mm": 0, "score": 0, "error": str(e)}

    def detect_defects(self, frame: np.ndarray) -> Dict:
        """检测缺陷类型（支持GPU加速）"""
        if self.yolo_model is None:
            return {
                "detections": [],
                "score": 100,
                "error": "YOLO模型未初始化",
                "debug_info": "模型未加载",
            }

        try:
            # 使用GPU进行推理
            results = self.yolo_model(
                frame,
                conf=self.config["confidence_threshold"],
                iou=self.config["iou_threshold"],
                device=self.device,
                verbose=False,
            )

            detections = []
            defect_score = 100  # 基础分数
            debug_info = f"检测到{len(results)}个结果"

            if results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                debug_info = f"检测到{len(boxes)}个目标"

                for i in range(len(boxes)):
                    box = boxes.xyxy[i].cpu().numpy()
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls = int(boxes.cls[i].cpu().numpy())

                    if conf >= self.config["confidence_threshold"]:
                        class_name = self.defect_classes.get(cls, f"Unknown_{cls}")
                        class_name_cn = self.defect_classes_cn.get(cls, "未知缺陷")

                        detection = {
                            "box": box.tolist(),
                            "confidence": float(conf),
                            "class": int(cls),
                            "class_name": str(class_name),
                            "class_name_cn": str(class_name_cn),  # 添加中文名称
                        }
                        detections.append(detection)

                        # 根据缺陷类型扣分（扩展17类缺陷）
                        if cls == 3:  # Good Weld
                            defect_score += 10
                        elif cls in [0, 1, 4, 6, 7, 8, 9]:  # 严重缺陷
                            # Poor Weld, Crack, Porosity, Undercut, Overlap, Incomplete Fusion, Inclusion
                            defect_score -= 35
                        elif cls in [2, 5, 10, 11, 12, 13, 14]:  # 中等缺陷
                            # Excess Rebar, Spatter, Distortion, Surface Roughness, Excess Penetration, Misalignment, Arc Strike
                            defect_score -= 20
                        elif cls in [15, 16]:  # 轻微缺陷
                            # Discoloration, Tool Mark
                            defect_score -= 8
            else:
                debug_info = "未检测到任何目标"

            defect_score = max(0, min(100, defect_score))

            return {
                "detections": detections,
                "score": float(defect_score),
                "debug_info": str(debug_info),
                "detection_count": int(len(detections)),
                "annotated_frame": results[0].plot()
                if results[0].boxes is not None
                else frame,
            }
        except Exception as e:
            return {"detections": [], "score": 0, "error": str(e)}

    def _calculate_width_score(self, width_mm: float) -> float:
        """根据宽度计算得分"""
        thresholds = self.config["width_thresholds"]
        optimal = thresholds["optimal_width_mm"]
        min_width = thresholds["min_width_mm"]
        max_width = thresholds["max_width_mm"]

        if width_mm < min_width or width_mm > max_width:
            return 20  # 超出范围，低分

        # 计算与最佳宽度的距离
        distance = abs(width_mm - optimal)
        max_distance = max(optimal - min_width, max_width - optimal)

        # 距离最佳宽度越近分数越高
        score = 100 - (distance / max_distance) * 60
        return max(20, min(100, score))

    def calculate_total_score(
        self, smoothness_result: Dict, width_result: Dict, defect_result: Dict
    ) -> Dict:
        """计算综合得分"""
        weights = self.config["scoring_weights"]

        # 获取各模块得分
        smoothness_score = smoothness_result.get("score", 0)
        width_score = width_result.get("score", 0)
        defect_score = defect_result.get("score", 0)

        # 加权计算总分
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
        """在画面上绘制检测结果"""
        display_frame = frame.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = self.config["display"]["font_scale"]
        thickness = self.config["display"]["line_thickness"]

        # 绘制总分
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

        # 绘制各模块得分
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

        # 显示调试信息
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

        # 绘制焊缝宽度标记 - 使用更明显的颜色和更粗的线条
        if "top_y" in results and "bottom_y" in results:
            # 绘制红色宽度线，更容易看到
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
            # 在线条旁边添加文字标注
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
            # 如果没有检测到宽度，显示调试信息
            cv2.putText(
                display_frame, "No width detected", (10, 150), font, 0.6, (0, 0, 255), 2
            )

        # 绘制检测框（如果有缺陷检测结果）
        if "detections" in results:
            for detection in results["detections"]:
                box = detection["box"]
                x1, y1, x2, y2 = map(int, box)
                class_name = detection["class_name"]
                confidence = detection["confidence"]

                # 选择颜色
                color = (0, 255, 0) if "Good" in class_name else (0, 0, 255)

                # 绘制框和标签
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
        """并行处理单帧图像"""
        start_time = time.time()

        # 并行执行三个检测模块
        results = {}

        with ThreadPoolExecutor(max_workers=3) as executor:
            # 提交三个任务
            future_smoothness = executor.submit(self.detect_smoothness, frame)
            future_width = executor.submit(self.detect_width, frame)
            future_defects = executor.submit(self.detect_defects, frame)

            # 收集结果
            results["smoothness"] = future_smoothness.result()
            results["width"] = future_width.result()
            results["defects"] = future_defects.result()

        # 计算综合得分
        score_result = self.calculate_total_score(
            results["smoothness"], results["width"], results["defects"]
        )

        # 整合结果
        integrated_result = {
            **score_result,
            "width_mm": results["width"].get("width_mm", 0),
            "detections": results["defects"].get("detections", []),
            "detection_count": results["defects"].get("detection_count", 0),
            "debug_info": results["defects"].get("debug_info", ""),
            "processing_time": time.time() - start_time,
        }

        # 添加宽度位置信息用于绘制
        if "top_y" in results["width"]:
            integrated_result["top_y"] = results["width"]["top_y"]
            integrated_result["bottom_y"] = results["width"]["bottom_y"]
            integrated_result["center_y"] = results["width"]["center_y"]

        self.total_frames += 1
        return integrated_result

    def find_camera(self) -> Optional[int]:
        """查找可用摄像头"""
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
        """运行摄像头实时检测"""
        if camera_id is None:
            camera_id = self.find_camera()
            if camera_id is None:
                print("无法找到摄像头")
                return

        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print(f"无法打开摄像头 ID: {camera_id}")
            return

        # 设置摄像头参数
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

                # 处理帧
                results = self.process_frame(frame)

                # 绘制结果
                display_frame = self.draw_results(frame, results)

                # 显示画面
                cv2.imshow("焊缝质量综合检测系统", display_frame)

                # 处理按键
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
        """运行视频文件检测"""
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

                    # 处理帧
                    results = self.process_frame(frame)

                    # 绘制结果
                    display_frame = self.draw_results(frame, results)
                else:
                    # 暂停时继续显示当前帧
                    cv2.imshow("焊缝质量综合检测系统 - 视频检测", display_frame)

                # 显示画面
                cv2.imshow("焊缝质量综合检测系统 - 视频检测", display_frame)

                # 处理按键
                key = cv2.waitKey(30) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("s"):
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    save_path = f"video_detection_{timestamp}.jpg"
                    cv2.imwrite(save_path, display_frame)
                    print(f"当前画面已保存: {save_path}")
                elif key == ord(" "):  # 空格键暂停/继续
                    paused = not paused
                    print("已暂停" if paused else "继续播放")

        except KeyboardInterrupt:
            print("\n程序被用户中断")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            print(f"检测完成，共处理 {self.total_frames} 帧")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="焊缝质量综合检测系统")
    parser.add_argument("--camera", "-c", type=int, help="摄像头ID")
    parser.add_argument("--video", "-v", type=str, help="视频文件路径")
    parser.add_argument("--config", type=str, help="配置文件路径")

    args = parser.parse_args()

    print("=" * 60)
    print("    焊缝质量综合检测系统")
    print("    Integrated Weld Quality Detection System")
    print("=" * 60)
    print("功能: 光滑度检测 + 宽度检测 + 缺陷检测")
    print("=" * 60)

    # 创建检测器
    detector = IntegratedWeldDetector(args.config)

    if args.video:
        # 视频文件检测
        detector.run_video_detection(args.video)
    else:
        # 摄像头检测
        detector.run_camera_detection(args.camera)

    print("程序结束")


if __name__ == "__main__":
    main()
