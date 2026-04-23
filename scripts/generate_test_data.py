"""Generate a small synthetic LAS dataset for testing.

Creates minimal LAS 1.2 files with random point clouds that simulate
a simple terrain surface. These files are valid LAS and can be used
for integration testing without requiring real LiDAR data.

Usage:
    python scripts/generate_test_data.py [--output tests/data] [--tiles 4] [--points 1000]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import laspy
import numpy as np


def generate_tile(
    output_path: Path,
    x_offset: float,
    y_offset: float,
    tile_size: float = 100.0,
    n_points: int = 1000,
    epsg: int = 26910,
) -> None:
    """Generate a single synthetic LAS tile.

    Creates a point cloud with:
    - XY positions uniformly distributed within the tile extent
    - Z values following a gentle sine-wave terrain + random noise
    - Classification: all points set to 0 (unclassified)
    """
    rng = np.random.default_rng(seed=int(x_offset * 1000 + y_offset))

    x = rng.uniform(x_offset, x_offset + tile_size, n_points)
    y = rng.uniform(y_offset, y_offset + tile_size, n_points)

    # Gentle terrain: sine wave + noise
    z = (
        50.0
        + 10.0 * np.sin(x / 30.0) * np.cos(y / 30.0)
        + rng.normal(0, 0.3, n_points)
    )

    header = laspy.LasHeader(point_format=0, version="1.2")
    header.offsets = [x_offset, y_offset, 0.0]
    header.scales = [0.01, 0.01, 0.01]

    # Add CRS as a GeoTIFF VLR (record_id 34735)
    # Minimal GeoTIFF directory for projected CRS
    from laspy import VLR

    geo_keys = np.array(
        [
            1, 1, 0, 3,  # KeyDirectoryVersion, KeyRevision, MinorRevision, NumberOfKeys
            1024, 0, 1, 1,  # GTModelTypeGeoKey = ModelTypeProjected
            2048, 0, 1, 4326,  # GeographicTypeGeoKey (base)
            3072, 0, 1, epsg,  # ProjectedCSTypeGeoKey
        ],
        dtype=np.uint16,
    )
    vlr = VLR(
        user_id="LASF_Projection",
        record_id=34735,
        description="GeoTIFF GeoKeyDirectoryTag",
        record_data=geo_keys.tobytes(),
    )
    header.vlrs.append(vlr)

    las = laspy.LasData(header)
    las.x = x
    las.y = y
    las.z = z

    output_path.parent.mkdir(parents=True, exist_ok=True)
    las.write(str(output_path))


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic LAS test data")
    parser.add_argument("--output", default="tests/data", help="Output directory")
    parser.add_argument("--tiles", type=int, default=4, help="Number of tiles (2x2 grid)")
    parser.add_argument("--points", type=int, default=1000, help="Points per tile")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    grid_size = int(np.ceil(np.sqrt(args.tiles)))
    tile_size = 100.0
    count = 0

    for row in range(grid_size):
        for col in range(grid_size):
            if count >= args.tiles:
                break
            x_off = col * tile_size + 500000  # UTM-like easting
            y_off = row * tile_size + 5400000  # UTM-like northing
            name = f"tile_{row}_{col}.las"
            path = output_dir / name
            generate_tile(path, x_off, y_off, tile_size, args.points)
            print(f"  Created {path} ({args.points} points)")
            count += 1

    print(f"\nGenerated {count} tiles in {output_dir}/")


if __name__ == "__main__":
    main()
