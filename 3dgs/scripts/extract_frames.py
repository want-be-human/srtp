import argparse
import os
import cv2


def extract_frames(video_path: str, output_dir: str, target_fps: float) -> None:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    source_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if source_fps <= 0:
        source_fps = 30.0

    step = max(1, round(source_fps / target_fps))

    print(f"Video: {video_path}")
    print(f"Source FPS: {source_fps}")
    print(f"Total frames: {total_frames}")
    print(f"Target FPS: {target_fps}")
    print(f"Frame step: {step}")
    print(f"Output dir: {output_dir}")

    saved = 0
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_idx % step == 0:
            saved += 1
            out_name = f"frame_{saved:04d}.jpg"
            out_path = os.path.join(output_dir, out_name)
            cv2.imwrite(out_path, frame)

        frame_idx += 1

    cap.release()
    print(f"Done. Saved {saved} frames.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Path to input video")
    parser.add_argument("output", help="Output image folder")
    parser.add_argument("--fps", type=float, default=5.0, help="Target FPS for extraction")
    args = parser.parse_args()

    extract_frames(args.video, args.output, args.fps)