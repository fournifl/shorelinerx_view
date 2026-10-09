from pathlib import Path

import geopandas as gpd
import numpy as np
from rasterio.mask import mask
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from matplotlib import colormaps


def apply_mask(ls_r, roi, nodata, odir_masked):

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
            nodata=nodata,  # value assigned to pixels outside the polygon
            filled=True  # fill masked pixels with nodata value
        )
        # Update metadata
        masked_meta = r.meta.copy()
        masked_meta.update({
            "height": masked_data.shape[1],
            "width": masked_data.shape[2],
            "transform": masked_transform,
            "nodata": nodata
        })

        # write masked data
        fname = odir_masked / Path(r.name).name
        with rasterio.open(fname, "w", **masked_meta) as dest:
            dest.write(masked_data)
        r.close()

        ls_r_masked.append(rasterio.open(fname, 'r+'))

    return ls_r_masked


def raster_to_rgba_mercator(src, mode="rgb", cmap="viridis", vlim=None,
                            max_px=1000, low=2, high=98):
    """Reproject a raster to EPSG:3857 -> (rgba_uint32, left, bottom, width, height).
    mode="rgb": bands 1-3 as true color. mode="single": band 1 through a colormap."""

    DST_CRS = "EPSG:3857"

    transform, w, h = calculate_default_transform(
        src.crs, DST_CRS, src.width, src.height, *src.bounds)
    f = max(w, h) / max_px
    if f > 1:  # downsample to keep the HTML light
        transform, w, h = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds,
            dst_width=int(round(w / f)), dst_height=int(round(h / f)))

    nb = 3 if mode == "rgb" else 1
    dst = np.full((nb, h, w), np.nan, dtype="float32")
    for b in range(nb):
        reproject(
            source=rasterio.band(src, b + 1), destination=dst[b],
            src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
            dst_transform=transform, dst_crs=DST_CRS, dst_nodata=np.nan,
            resampling=Resampling.bilinear if mode == "rgb" else Resampling.nearest,
        )

    valid = np.isfinite(dst).all(axis=0)

    if mode == "rgb":
        valid &= np.nan_to_num(dst).sum(axis=0) > 0
        if src.dtypes[0] == "uint8":
            rgb8 = np.nan_to_num(dst).astype("uint8")
        else:  # float / uint16: percentile stretch per band
            rgb8 = np.zeros(dst.shape, dtype="uint8")
            for b in range(3):
                if valid.any():
                    lo, hi = np.nanpercentile(dst[b][valid], (low, high))
                    rgb8[b] = np.clip((np.nan_to_num(dst[b]) - lo) / max(hi - lo, 1e-9), 0, 1) * 255
        rgba = np.dstack([rgb8[0], rgb8[1], rgb8[2], (valid * 255).astype("uint8")])
    else:
        band = dst[0]
        if vlim is None:
            lo, hi = np.nanpercentile(band[valid], (low, high)) if valid.any() else (0, 1)
        else:
            lo, hi = vlim
        norm = np.clip((np.nan_to_num(band) - lo) / max(hi - lo, 1e-9), 0, 1)
        rgba = (colormaps[cmap](norm) * 255).astype("uint8")   # (h, w, 4)
        rgba[..., 3] = (valid * 255).astype("uint8")

    rgba = np.ascontiguousarray(np.flipud(rgba))               # bokeh origin = bottom-left
    img = rgba.view("uint32").reshape(h, w)

    left, top = transform.c, transform.f
    right, bottom = left + w * transform.a, top + h * transform.e
    return img, left, bottom, right - left, top - bottom

