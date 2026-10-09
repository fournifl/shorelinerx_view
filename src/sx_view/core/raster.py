import pystac
import rasterio
import geopandas as gpd
from pathlib import Path

from sx_view.core.geo_utils import apply_mask


def read_aoi(f_aoi: Path, crs: rasterio.crs.CRS):

    # read aoi
    aoi = gpd.read_file(f_aoi)

    # convert aoi crs to rasters' crs
    aoi = aoi.to_crs(crs)

    return aoi



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
        ls_r = apply_mask(ls_r, f_aoi, r.nodata, odir_masked)
        rs[r_id] = ls_r

    return rs

