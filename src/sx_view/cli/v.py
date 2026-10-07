from sx_view.core import view


def viewer(conf):
    view.run(
        conf.wl_dir,
        conf.f_aoi,
        conf.odir
    )