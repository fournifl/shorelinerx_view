import pystac
import rasterio
import geopandas as gpd
from pathlib import Path
import numpy as np

from sx_view.core.geo_utils import apply_mask


def read_aoi(f_aoi: Path, crs: rasterio.crs.CRS):

    # read aoi
    aoi = gpd.read_file(f_aoi)

    # convert aoi crs to rasters' crs
    aoi = aoi.to_crs(crs)

    return aoi


def process_rgb(ls_rgb: np.array, mission: list[str], nodata: int):

    rgb_out = []
    for i, rgb in enumerate(ls_rgb):
        print(mission)
        if 'Landsat' in mission[i]:
            rgb_p = process_rgb_landsat(rgb, nodata)
        rgb_out.append(rgb_p)

    return rgb_out


def process_rgb_landsat(rgb: np.array, nodata: float):

    rgb = rgb.transpose(1, 2, 0)
    rgb = rgb * 0.0000275 - 0.2
    rgb = rgb.clip(0, 1)
    rgb_display = rgb / 0.3
    rgb_display = (rgb_display.clip(0, 1) * 255).astype(np.uint8)

    return rgb_display


def read(items: list[pystac.item.Item], r_ids: list[str], f_aoi: Path, odir: Path):
    '''
    read rasters (only the ones present in the selection of rasters)
    '''

    # raster dict output
    rs = {}

    for r_id in r_ids:

        # list of rasterio rasters
        ls_r = []

        # list of missions
        mission = []

        # initialize list of rasters
        rs[r_id] = []

        # loop through rasters
        for item in items:

            # mission
            mission.append(item.properties['platform'])

            # href item
            f_item = Path(item.get_self_href())

            # raster filename
            f_r = f_item.parent / item.assets[r_id].href

            # read raster
            r = rasterio.open(f_r, 'r')
            ls_r.append(r)

        # apply aoi mask to rasters
        odir_masked = odir / 'rasters_masked'
        odir_masked.mkdir(parents=True, exist_ok=True)
        ls_r = apply_mask(ls_r, f_aoi, odir_masked)
        rs[r_id] = ls_r

    return rs

