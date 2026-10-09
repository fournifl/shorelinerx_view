from pathlib import Path
import geopandas as gpd
from rasterio.mask import mask
import rasterio


def apply_mask(ls_r, roi, odir_masked):

    # output dir masked data
    odir_masked = Path(odir_masked)
    odir_masked.mkdir(exist_ok=True, parents=True)

    # read roi from the GeoPackage
    roi = gpd.read_file(roi)

    ls_r_masked = []

    # Reproject roi polygon to match raster CRS if necessary
    if roi.crs != ls_r[0].crs:
        roi = roi.to_crs(ls_r[0].crs)

    shapes = roi.geometry.values  # list of shapely geometries

    # Apply the mask
    for i, r in enumerate(ls_r):
        masked_data, masked_transform = mask(r, shapes,
            crop=True,  # crop the output extent to the polygon bounds
            nodata=-9999,  # value assigned to pixels outside the polygon
            filled=True  # fill masked pixels with nodata value
        )
        # Update metadata
        masked_meta = r.meta.copy()
        masked_meta.update({
            "height": masked_data.shape[1],
            "width": masked_data.shape[2],
            "transform": masked_transform,
            "nodata": -9999
        })

        # write masked data
        fname = odir_masked / Path(r.name).name
        with rasterio.open(fname, "w", **masked_meta) as dest:
            dest.write(masked_data)
        r.close()

        ls_r_masked.append(rasterio.open(fname, 'r+'))

    return ls_r_masked

