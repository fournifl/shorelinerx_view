from sx_view.core import view


def viewer(conf):

    view.run(
        conf.wl_dir,
        conf.f_aoi,
        conf.rasters.ids,
        conf.f_out_prefix,
        conf.odir
    )