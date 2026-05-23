# -*- coding: utf-8 -*-
"""
3DGS 验证用：摄像头参数手动锁定 + 多视角抓拍工具。

为什么要有这个脚本：
- 3D 高斯泼溅前置依赖 COLMAP 的 SfM。SfM 极度依赖"同一物体在不同帧颜色/亮度一致"。
- UVC 摄像头默认开自动曝光/白平衡/增益，绕焊缝拍一圈时镜头朝向/光照变化会让自动控制
  频繁调整，结果同一焊缝表面在 50 张里有 50 种亮度，SfM 特征匹配 GG。
- 必须先锁掉自动控制 + 用固定参数拍。锁掉之后才能进入 COLMAP / 3DGS 管线。

用法：
    python backend/scripts/capture_for_gsplat.py --camera 1
    # 出现预览窗口后：
    #   SPACE  → 抓一帧
    #   ENTER  → 切换连拍模式（每 0.5s 自动一帧）
    #   + / -  → 增/减曝光（手动模式）
    #   [ / ]  → 减/加增益
    #   , / .  → 减/加白平衡色温
    #   a      → 切换自动曝光（debug 用，正式拍摄前关掉）
    #   ESC    → 退出

拍完后下一步：
    colmap automatic_reconstructor --image_path <output_dir> --workspace_path <output_dir>/colmap
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

import cv2


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="抓拍 3DGS 训练用的多视角图")
    p.add_argument("--camera", type=int, default=1, help="摄像头 index（默认 1 = MF500）")
    p.add_argument("--width", type=int, default=2560, help="请求的源宽度")
    p.add_argument("--height", type=int, default=1440, help="请求的源高度")
    p.add_argument("--output", type=str, default="", help="输出目录，留空自动按时间戳生成到 captures/")
    p.add_argument("--exposure", type=int, default=-7, help="DSHOW 曝光值（log2 秒，-7 ≈ 1/128s）")
    p.add_argument("--gain", type=int, default=0, help="增益，0 = 最低")
    p.add_argument("--wb-temp", type=int, default=4500, help="白平衡色温 (K)，4500 ≈ 白色 LED 柔光")
    p.add_argument("--quality", type=int, default=95, help="JPEG 质量 (1-100)")
    p.add_argument("--burst-interval", type=float, default=0.5, help="连拍间隔（秒）")
    return p.parse_args()


def open_camera(idx: int, w: int, h: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        sys.exit(f"无法打开摄像头 index={idx}")
    # MJPG 必须在 set 分辨率之前，否则部分 UVC 相机走 YUYV 时不接受 2K
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    return cap


def lock_uvc(cap: cv2.VideoCapture, exposure: int, gain: int, wb_temp: int) -> None:
    """关掉所有自动控制并 set 一组确定的手动值。

    OpenCV DirectShow 后端的 AUTO_EXPOSURE 取值是非标的：
    0.25 = 手动, 0.75 = 自动（V4L2 上分别是 1 / 3）。两个都 set 一遍兼容。
    set 失败 OpenCV 会静默返回 False，不抛异常，正常。
    """
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)
    cap.set(cv2.CAP_PROP_WB_TEMPERATURE, wb_temp)
    cap.set(cv2.CAP_PROP_GAIN, gain)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)


def draw_hud(frame, state: dict) -> None:
    """在预览左上角叠 HUD。帧本身是 BGR，OpenCV 不支持中文，全用英文+数字。"""
    lines = [
        f"saved={state['saved']:03d}  mode={'BURST' if state['burst'] else 'single'}",
        f"exp={state['exposure']}  gain={state['gain']}  wb={state['wb']}K  AE={state['ae']}",
        "SPACE shoot | ENTER burst | +/- exp | [/] gain | ,/. wb | a auto | ESC quit",
    ]
    y = 28
    for ln in lines:
        cv2.putText(frame, ln, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, ln, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        y += 24


def main() -> None:
    args = parse_args()

    out_dir = args.output or os.path.join("captures", datetime.now().strftime("seam_%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    print(f"输出目录: {os.path.abspath(out_dir)}")

    cap = open_camera(args.camera, args.width, args.height)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"实际源分辨率: {actual_w}x{actual_h}")
    if (actual_w, actual_h) != (args.width, args.height):
        print(f"WARN: 相机不支持 {args.width}x{args.height}，被 clamp 到 {actual_w}x{actual_h}")

    lock_uvc(cap, args.exposure, args.gain, args.wb_temp)

    state = {
        "saved": 0,
        "burst": False,
        "exposure": args.exposure,
        "gain": args.gain,
        "wb": args.wb_temp,
        "ae": "manual",
    }
    last_burst_ts = 0.0
    win = "capture_for_gsplat"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 1280, 720)

    print("\n按键说明:")
    print("  SPACE  抓一帧")
    print("  ENTER  切换连拍 (每 %.2fs 一帧)" % args.burst_interval)
    print("  + / -  曝光    [ / ]  增益    , / .  白平衡    a  自动曝光    ESC  退出\n")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("read 失败，重试")
                time.sleep(0.05)
                continue

            should_save = False

            # 显示用降采样副本，原始 frame 留给保存
            preview = cv2.resize(frame, (1280, int(1280 * actual_h / actual_w)))
            draw_hud(preview, state)
            cv2.imshow(win, preview)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            elif key == 32:  # SPACE
                should_save = True
            elif key == 13:  # ENTER
                state["burst"] = not state["burst"]
                last_burst_ts = 0.0
                print(f"burst -> {state['burst']}")
            elif key in (ord('+'), ord('=')):
                state["exposure"] = min(state["exposure"] + 1, 0)
                cap.set(cv2.CAP_PROP_EXPOSURE, state["exposure"])
            elif key == ord('-'):
                state["exposure"] = max(state["exposure"] - 1, -13)
                cap.set(cv2.CAP_PROP_EXPOSURE, state["exposure"])
            elif key == ord(']'):
                state["gain"] += 4
                cap.set(cv2.CAP_PROP_GAIN, state["gain"])
            elif key == ord('['):
                state["gain"] = max(state["gain"] - 4, 0)
                cap.set(cv2.CAP_PROP_GAIN, state["gain"])
            elif key == ord('.'):
                state["wb"] = min(state["wb"] + 250, 10000)
                cap.set(cv2.CAP_PROP_WB_TEMPERATURE, state["wb"])
            elif key == ord(','):
                state["wb"] = max(state["wb"] - 250, 2000)
                cap.set(cv2.CAP_PROP_WB_TEMPERATURE, state["wb"])
            elif key == ord('a'):
                if state["ae"] == "manual":
                    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)
                    state["ae"] = "AUTO"
                else:
                    lock_uvc(cap, state["exposure"], state["gain"], state["wb"])
                    state["ae"] = "manual"
                print(f"auto-exposure -> {state['ae']}")

            if state["burst"] and time.time() - last_burst_ts >= args.burst_interval:
                should_save = True
                last_burst_ts = time.time()

            if should_save:
                path = os.path.join(out_dir, f"frame_{state['saved']:06d}.jpg")
                cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, args.quality])
                state["saved"] += 1
                print(f"[{state['saved']:03d}] saved {path}")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    print(f"\n完成：{state['saved']} 张图保存到 {os.path.abspath(out_dir)}")
    if state["saved"] >= 20:
        print("\n下一步跑 COLMAP（先 pip install pycolmap 或 装独立 COLMAP-3.x）:")
        print(f"  colmap automatic_reconstructor \\")
        print(f"    --image_path {out_dir} \\")
        print(f"    --workspace_path {out_dir}/colmap")
        print("成功标志：colmap/sparse/0/ 目录里出现 cameras.bin / images.bin / points3D.bin")
    else:
        print(f"WARN: 只拍了 {state['saved']} 张，建议 50-100 张再进 COLMAP")


if __name__ == "__main__":
    main()
