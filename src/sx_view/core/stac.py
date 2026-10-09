import pystac
from pathlib import Path
from sx_view.core import raster, waterline


def read(ls: list, r_ids, f_aoi, odir: Path):
    '''
    read list of stac items
    '''

    # create list of pystac objects
    items = [pystac.Item.from_file(f) for f in ls]

    # read waterlines
    gdf = waterline.read(items, r_ids)

    # read rasters
    rs = raster.read(items, r_ids, f_aoi, odir)

    # add rasters to gdf
    for r_id in r_ids:
        gdf[r_id] = rs[r_id]

    # drop lines of the geodataframe corresponding to empty waterline
    gdf = gdf.dropna(subset=["geometry"])

    return gdf