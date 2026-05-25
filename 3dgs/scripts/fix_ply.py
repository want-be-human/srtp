import struct
import numpy as np
from pathlib import Path


def fix_ply(ply_path: str, out_path: str) -> None:
    ply_path = Path(ply_path)
    out_path = Path(out_path)

    if not ply_path.exists():
        raise FileNotFoundError(f"Input PLY not found: {ply_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(ply_path, "rb") as f:
        header = b""
        while True:
            line = f.readline()
            if not line:
                raise RuntimeError("Invalid PLY: end_header not found")
            header += line
            if line.strip() == b"end_header":
                break

        raw = f.read()

    vertex_size = 62 * 4

    if len(raw) % vertex_size != 0:
        raise RuntimeError(
            f"Unexpected PLY binary size. raw={len(raw)}, vertex_size={vertex_size}. "
            "This script expects original 3DGS PLY format with 62 float values per vertex."
        )

    count = len(raw) // vertex_size
    new_data = bytearray()

    for i in range(count):
        off = i * vertex_size
        vals = list(struct.unpack("<62f", raw[off:off + vertex_size]))

        # opacity: logit -> linear
        vals[51] = 1.0 / (1.0 + np.exp(-vals[51]))

        # scale: log -> linear
        vals[52] = np.exp(vals[52])
        vals[53] = np.exp(vals[53])
        vals[54] = np.exp(vals[54])

        new_data += struct.pack("<62f", *vals)

    with open(out_path, "wb") as f:
        f.write(header)
        f.write(new_data)

    print(f"Done: {count} splats")
    print(f"Input : {ply_path}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    fix_ply(
        "output/ruler_test/point_cloud/iteration_7000/point_cloud.ply",
        "viewer/model_fixed.ply"
    )