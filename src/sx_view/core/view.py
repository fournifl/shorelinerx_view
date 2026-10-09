from pathlib import Path

import geopandas
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from bokeh.plotting import figure, output_file, save
from bokeh.models import ColumnDataSource, Slider, Div, CustomJS
from bokeh.layouts import column

from sx_view.core import stac


def raster_to_rgba_mercator(src, max_px=1000, low=2, high=98):

    DST_CRS = "EPSG:3857"

    """Reproject a 3-band raster to EPSG:3857 and return (rgba_uint32, left, bottom, width, height)."""
    if isinstance(src, (str, Path)):
        with rasterio.open(src) as ds:
            return raster_to_rgba_mercator(ds, max_px, low, high)

    transform, w, h = calculate_default_transform(
        src.crs, DST_CRS, src.width, src.height, *src.bounds)

    # Downsample to keep the HTML light
    f = max(w, h) / max_px
    if f > 1:
        transform, w, h = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds,
            dst_width=int(round(w / f)), dst_height=int(round(h / f)))

    dst = np.full((3, h, w), np.nan, dtype="float32")
    for b in range(3):
        reproject(
            source=rasterio.band(src, b + 1),
            destination=dst[b],
            src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
            dst_transform=transform, dst_crs=DST_CRS, dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

    valid = np.isfinite(dst).all(axis=0) & (np.nan_to_num(dst).sum(axis=0) > 0)

    if src.dtypes[0] == "uint8":
        rgb8 = np.nan_to_num(dst).astype("uint8")
    else:  # float / uint16: percentile stretch per band
        rgb8 = np.zeros_like(dst, dtype="uint8")
        for b in range(3):
            if valid.any():
                lo, hi = np.nanpercentile(dst[b][valid], (low, high))
                rgb8[b] = (np.clip((np.nan_to_num(dst[b]) - lo) / max(hi - lo, 1e-9), 0, 1) * 255)

    rgba = np.dstack([rgb8[0], rgb8[1], rgb8[2], (valid * 255).astype("uint8")])
    rgba = np.ascontiguousarray(np.flipud(rgba))      # bokeh origin = bottom-left
    img = rgba.view("uint32").reshape(h, w)

    left, top = transform.c, transform.f
    right, bottom = left + w * transform.a, top + h * transform.e
    return img, left, bottom, right - left, top - bottom


def plot(gdf: geopandas.GeoDataFrame, odir: Path, f_out_prefix: str):

    if gdf.crs is None:
        raise ValueError("gdf has no CRS, cannot reproject to Web Mercator")

    gdf = gdf.sort_values("date").reset_index(drop=True)
    gdf_m = gdf.set_geometry(gdf.geometry).to_crs(3857)

    labels = [f"{d} - {m}" for d, m in zip(gdf["date"].astype(str), gdf["mission"])]

    # --- Lines: one entry per line, tagged with the shoreline index
    xs, ys, idx, label_col = [], [], [], []
    for i, geom in enumerate(gdf_m.geometry):
        if geom is None or geom.is_empty:
            continue
        lines = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
        for line in lines:
            x, y = line.xy
            xs.append(list(x)); ys.append(list(y))
            idx.append(i); label_col.append(labels[i])

    source_all = ColumnDataSource(dict(xs=xs, ys=ys, idx=idx, label=label_col))
    first = [k for k, i in enumerate(idx) if i == 0]
    source_vis = ColumnDataSource(dict(
        xs=[xs[k] for k in first], ys=[ys[k] for k in first],
        label=[label_col[k] for k in first]))

    # --- Rasters: one RGBA image per shoreline (transparent placeholder if missing)
    minx, miny, maxx, maxy = gdf_m.total_bounds
    empty = (np.zeros((1, 1), dtype="uint32"), minx, miny, 1.0, 1.0)

    imgs, ix, iy, idw, idh = [], [], [], [], []
    for r in gdf["rgb"]:
        img, l, b, dw, dh = empty if r is None else raster_to_rgba_mercator(r)
        imgs.append(img); ix.append(l); iy.append(b); idw.append(dw); idh.append(dh)
        if r is not None:
            minx, miny = min(minx, l), min(miny, b)
            maxx, maxy = max(maxx, l + dw), max(maxy, b + dh)

    source_img_all = ColumnDataSource(dict(image=imgs, x=ix, y=iy, dw=idw, dh=idh))
    source_img_vis = ColumnDataSource(dict(
        image=[imgs[0]], x=[ix[0]], y=[iy[0]], dw=[idw[0]], dh=[idh[0]]))

    # --- Figure (fixed extent covering lines and rasters)
    padx, pady = 0.05 * (maxx - minx), 0.05 * (maxy - miny)
    p = figure(
        title="shorelinerx waterlines", width=1536, height=864,
        x_axis_type="mercator", y_axis_type="mercator",
        x_range=(minx - padx, maxx + padx), y_range=(miny - pady, maxy + pady),
        match_aspect=True, tooltips=[("date - mission", "@label")],
    )
    p.add_tile("Esri.WorldImagery")
    p.grid.visible = False

    # Raster first (below), then the waterline on top
    p.image_rgba("image", x="x", y="y", dw="dw", dh="dh", source=source_img_vis)
    p.multi_line("xs", "ys", source=source_vis, line_color="red", line_width=2)

    # --- Slider
    label = Div(text=f"<b>{labels[0]}</b>", styles={"font-size": "16px"})
    slider = Slider(start=0, end=len(gdf) - 1, value=0, step=1,
                    title=None, width=600)

    slider.js_on_change("value", CustomJS(
        args=dict(source_all=source_all, source_vis=source_vis,
                  source_img_all=source_img_all, source_img_vis=source_img_vis,
                  label=label, labels=labels),
        code="""
        const i = cb_obj.value;

        // lines
        const a = source_all.data;
        const xs = [], ys = [], lab = [];
        for (let k = 0; k < a.idx.length; k++) {
            if (a.idx[k] === i) { xs.push(a.xs[k]); ys.push(a.ys[k]); lab.push(a.label[k]); }
        }
        source_vis.data = {xs: xs, ys: ys, label: lab};

        // raster
        const b = source_img_all.data;
        source_img_vis.data = {
            image: [b.image[i]], x: [b.x[i]], y: [b.y[i]],
            dw: [b.dw[i]], dh: [b.dh[i]],
        };

        label.text = "<b>" + labels[i] + "</b>";
        """,
    ))

    out = odir.joinpath(f"{f_out_prefix}.html")
    output_file(out)
    print(f"\n --> {out} \n")
    save(column(slider, label, p))

    return


def run(wl_dir: Path, f_aoi: Path, r_ids: list, f_out_prefix: str, odir: Path):

    # list of stac items
    ls = sorted(wl_dir.rglob('stac-item.json'))

    # read stac items
    gdf = stac.read(ls, r_ids, f_aoi, odir)

    # plot waterlines, rasters, ans ESRI tile
    plot(gdf, odir, f_out_prefix)

    return