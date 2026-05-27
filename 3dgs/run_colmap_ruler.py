"""One-off SfM pipeline for the ruler dataset. Adapted from scripts/run_colmap.py."""

import logging
import os
import shutil

import pycolmap

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

source_path = "D:/srtp-main/3dgs/data/ruler"
image_path = f"{source_path}/input"
distorted = f"{source_path}/distorted"

os.makedirs(f"{distorted}/sparse", exist_ok=True)

logging.info("Extracting features...")
extract_opts = pycolmap.FeatureExtractionOptions()
extract_opts.use_gpu = pycolmap.has_cuda
extract_opts.max_image_size = 2000

pycolmap.extract_features(
    database_path=f"{distorted}/database.db",
    image_path=image_path,
    camera_mode=pycolmap.CameraMode.SINGLE,
    extraction_options=extract_opts,
)

logging.info("Matching features (exhaustive)...")
match_opts = pycolmap.FeatureMatchingOptions()
match_opts.use_gpu = pycolmap.has_cuda

pycolmap.match_exhaustive(
    database_path=f"{distorted}/database.db",
    matching_options=match_opts,
)

logging.info("Running incremental mapping...")
pipeline_opts = pycolmap.IncrementalPipelineOptions()

reconstructions = pycolmap.incremental_mapping(
    database_path=f"{distorted}/database.db",
    image_path=image_path,
    output_path=f"{distorted}/sparse",
    options=pipeline_opts,
)

if len(reconstructions) == 0:
    logging.error("No reconstructions found!")
    raise SystemExit(1)

logging.info(f"Found {len(reconstructions)} reconstruction(s)")

logging.info("Undistorting images...")
pycolmap.undistort_images(
    output_path=source_path,
    input_path=f"{distorted}/sparse/0",
    image_path=image_path,
)

sparse_files = os.listdir(f"{source_path}/sparse")
os.makedirs(f"{source_path}/sparse/0", exist_ok=True)
for file in sparse_files:
    if file == "0":
        continue
    src = os.path.join(source_path, "sparse", file)
    dst = os.path.join(source_path, "sparse", "0", file)
    shutil.move(src, dst)

recon = reconstructions[0]
logging.info(f"Done! Processed {len(recon.images)} images, {len(recon.points3D)} 3D points")
