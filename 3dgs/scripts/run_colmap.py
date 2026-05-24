"""SfM pipeline using pycolmap (equivalent to gaussian-splatting convert.py)."""

import logging
import shutil
import os
import pycolmap

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

source_path = "G:/3dgs/data/test"
image_path = f"{source_path}/input"
distorted = f"{source_path}/distorted"

os.makedirs(f"{distorted}/sparse", exist_ok=True)

# Step 1: Feature extraction
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

# Step 2: Feature matching (exhaustive)
logging.info("Matching features (exhaustive)...")
match_opts = pycolmap.FeatureMatchingOptions()
match_opts.use_gpu = pycolmap.has_cuda

pycolmap.match_exhaustive(
    database_path=f"{distorted}/database.db",
    matching_options=match_opts,
)

# Step 3: Incremental mapping
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
    exit(1)

logging.info(f"Found {len(reconstructions)} reconstruction(s)")

# Step 4: Undistort images
logging.info("Undistorting images...")
pycolmap.undistort_images(
    output_path=f"{source_path}",
    input_path=f"{distorted}/sparse/0",
    image_path=image_path,
)

# Step 5: Move files to expected structure
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
