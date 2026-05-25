import struct
import sys
import os
import time

def downsample_ply(input_path, output_path, target_count=150000):
    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    print(f"Reading {input_path}...")
    with open(input_path, 'rb') as f:
        raw = f.read()

    header_end_marker = b'end_header\n'
    header_end = raw.index(header_end_marker) + len(header_end_marker)
    header = raw[:header_end]

    header_str = header.decode('utf-8', errors='replace')
    for line in header_str.split('\n'):
        if line.startswith('element vertex'):
            total_vertices = int(line.split()[-1])
            break
    else:
        print("ERROR: could not find element vertex in header")
        sys.exit(1)

    print(f"  Total vertices: {total_vertices}")

    vertex_bytes = raw[header_end:]
    vertex_size = 62 * 4
    assert len(vertex_bytes) == total_vertices * vertex_size, \
        f"Size mismatch: {len(vertex_bytes)} vs {total_vertices * vertex_size}"

    target = min(target_count, total_vertices)
    print(f"  Extracting top {target} splats by opacity...")

    float_at_51 = struct.Struct('<f')
    indices = list(range(total_vertices))

    t0 = time.time()
    indices.sort(
        key=lambda i: float_at_51.unpack_from(vertex_bytes, i * vertex_size + 51 * 4)[0],
        reverse=True
    )
    elapsed = time.time() - t0
    print(f"  Sorted in {elapsed:.1f}s")

    selected = indices[:target]
    selected.sort()

    new_header = header_str.replace(
        f'element vertex {total_vertices}',
        f'element vertex {target}'
    ).encode('utf-8')

    new_data = bytearray()
    for i in selected:
        off = i * vertex_size
        new_data += vertex_bytes[off:off + vertex_size]

    with open(output_path, 'wb') as f:
        f.write(new_header)
        f.write(new_data)

    out_size = os.path.getsize(output_path)
    print(f"  Done: {target} splats -> {output_path} ({out_size / 1024 / 1024:.1f} MB)")


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    viewer_dir = os.path.join(script_dir, '..', 'viewer')
    input_ply = os.path.join(viewer_dir, 'model_fixed.ply')
    output_ply = os.path.join(viewer_dir, 'model_light.ply')

    target = int(sys.argv[1]) if len(sys.argv) > 1 else 150000
    downsample_ply(input_ply, output_ply, target)
