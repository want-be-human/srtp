"""Post-process raw 3DGS .ply -> viewer-ready (linear scale, sigmoid opacity)."""
import struct
import numpy as np

ply_path = "D:/srtp-main/3dgs/output/ruler/point_cloud/iteration_7000/point_cloud.ply"
out_path = "D:/srtp-main/3dgs/viewer/ruler.ply"

with open(ply_path, "rb") as f:
    header = b""
    while True:
        line = f.readline()
        header += line
        if line.strip() == b"end_header":
            break
    raw = f.read()

vertex_size = 62 * 4
count = len(raw) // vertex_size
print(f"vertices = {count}, header = {len(header)} bytes, body = {len(raw)} bytes")

arr = np.frombuffer(raw, dtype=np.float32).reshape(count, 62).copy()
arr[:, 52] = np.exp(arr[:, 52])
arr[:, 53] = np.exp(arr[:, 53])
arr[:, 54] = np.exp(arr[:, 54])
arr[:, 51] = 1.0 / (1.0 + np.exp(-arr[:, 51]))

with open(out_path, "wb") as f:
    f.write(header)
    f.write(arr.astype(np.float32).tobytes())

print(f"wrote {out_path}")
