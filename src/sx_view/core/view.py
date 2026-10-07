from pathlib import Path

from sx_view.core import stac, raster, waterline

def run(wl_dir: Path, f_aoi: Path, sel_rasters: list, odir: Path):

    # list of stac items
    ls = sorted(wl_dir.rglob('stac-item.json'))

    # read stac items
    items = stac.read(ls)

    # read waterlines
    waterline.read(items)

    # read and crop rasters to aoi
    raster.read(items, sel_rasters, f_aoi)

    # plot waterlines , rasters, ans ESRI tile

    return