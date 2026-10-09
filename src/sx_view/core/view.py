from pathlib import Path

import geopandas
import numpy as np
from bokeh.plotting import figure, output_file, save
from bokeh.models import ColumnDataSource, Slider, Div, CustomJS, RadioButtonGroup
from bokeh.layouts import column

from sx_view.core import stac
from sx_view.core.geo_utils import raster_to_rgba_mercator



def _missing(r):
    return r is None or (isinstance(r, float) and np.isnan(r))



def plot(gdf: geopandas.GeoDataFrame, odir: Path, f_out_prefix: str,
         r_ids: list[str] | None = None, cmaps: dict | None = None,
         vlims: dict | None = None, max_px: int = 800):
    """
    r_ids : names of the extra raster columns (single band)
    cmaps : optional {column: matplotlib colormap name}, default viridis
    vlims : optional {column: (vmin, vmax)}, default 2-98% stretch per image
    """
    r_ids = r_ids or []
    cmaps = cmaps or {}
    vlims = vlims or {}
    layers = ["rgb"] + [r for r in r_ids if r != "rgb"]

    if gdf.crs is None:
        raise ValueError("gdf has no CRS, cannot reproject to Web Mercator")

    gdf = gdf.sort_values("date").reset_index(drop=True)
    gdf_m = gdf.to_crs(3857)
    labels = [f"{d} - {m}" for d, m in zip(gdf["date"].astype(str), gdf["mission"])]

    # --- Lines
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

    # --- Rasters: for each layer, one RGBA image per shoreline
    minx, miny, maxx, maxy = gdf_m.total_bounds
    empty = (np.zeros((1, 1), dtype="uint32"), minx, miny, 1.0, 1.0)

    img_data = {}
    for layer in layers:
        imgs, ix, iy, idw, idh = [], [], [], [], []
        for r in gdf[layer]:
            if _missing(r):
                img, l, b, dw, dh = empty
            else:
                img, l, b, dw, dh = raster_to_rgba_mercator(
                    r,
                    mode="rgb" if layer == "rgb" else "single",
                    cmap=cmaps.get(layer, "viridis"),
                    vlim=vlims.get(layer),
                    max_px=max_px,
                )
                minx, miny = min(minx, l), min(miny, b)
                maxx, maxy = max(maxx, l + dw), max(maxy, b + dh)
            imgs.append(img); ix.append(l); iy.append(b); idw.append(dw); idh.append(dh)
        img_data.update({f"{layer}__image": imgs, f"{layer}__x": ix, f"{layer}__y": iy,
                         f"{layer}__dw": idw, f"{layer}__dh": idh})

    source_img_all = ColumnDataSource(img_data)
    l0 = layers[0]
    source_img_vis = ColumnDataSource(dict(
        image=[img_data[f"{l0}__image"][0]], x=[img_data[f"{l0}__x"][0]],
        y=[img_data[f"{l0}__y"][0]], dw=[img_data[f"{l0}__dw"][0]],
        dh=[img_data[f"{l0}__dh"][0]]))

    # --- Figure
    padx, pady = 0.05 * (maxx - minx), 0.05 * (maxy - miny)
    p = figure(
        title="shorelinerx waterlines", width=1536, height=864,
        x_axis_type="mercator", y_axis_type="mercator",
        x_range=(minx - padx, maxx + padx), y_range=(miny - pady, maxy + pady),
        match_aspect=True, tooltips=[("date - mission", "@label")],
    )
    p.add_tile("Esri.WorldImagery")
    p.grid.visible = False
    p.image_rgba("image", x="x", y="y", dw="dw", dh="dh", source=source_img_vis)
    p.multi_line("xs", "ys", source=source_vis, line_color="red", line_width=2)

    # --- Widgets
    label = Div(text=f"<b>{labels[0]} — {layers[0]}</b>", styles={"font-size": "16px"})
    slider = Slider(start=0, end=len(gdf) - 1, value=0, step=1,
                    title=None, width=600)
    layer_buttons = RadioButtonGroup(labels=layers, active=0)   # rgb by default

    callback = CustomJS(
        args=dict(source_all=source_all, source_vis=source_vis,
                  source_img_all=source_img_all, source_img_vis=source_img_vis,
                  slider=slider, buttons=layer_buttons,
                  label=label, labels=labels, layers=layers),
        code="""
        const i = slider.value;
        const layer = layers[buttons.active];

        // waterline
        const a = source_all.data;
        const xs = [], ys = [], lab = [];
        for (let k = 0; k < a.idx.length; k++) {
            if (a.idx[k] === i) { xs.push(a.xs[k]); ys.push(a.ys[k]); lab.push(a.label[k]); }
        }
        source_vis.data = {xs: xs, ys: ys, label: lab};

        // raster of the selected layer
        const b = source_img_all.data;
        source_img_vis.data = {
            image: [b[layer + "__image"][i]],
            x: [b[layer + "__x"][i]], y: [b[layer + "__y"][i]],
            dw: [b[layer + "__dw"][i]], dh: [b[layer + "__dh"][i]],
        };

        label.text = "<b>" + labels[i] + " — " + layer + "</b>";
        """,
    )
    slider.js_on_change("value", callback)
    layer_buttons.js_on_change("active", callback)

    out = odir.joinpath(f"{f_out_prefix}.html")
    output_file(out)
    print(f"\n --> {out} \n")
    save(column(layer_buttons, slider, label, p))

    return


def run(wl_dir: Path, f_aoi: Path, r_ids: list, f_out_prefix: str, odir: Path):

    # list of stac items
    ls = sorted(wl_dir.rglob('stac-item.json'))

    # read stac items
    gdf = stac.read(ls, r_ids, f_aoi, odir)

    # plot waterlines, rasters, ans ESRI tile
    plot(gdf, odir, f_out_prefix, r_ids=r_ids, cmaps={'index': 'Greys', 'mask_clouds': 'gist_gray'})

    return