import pystac
import geopandas as gpd
from pathlib import Path
from shapely import MultiLineString


def read_wl(item):

    # href item
    f_item = Path(item.get_self_href())

    # file of waterline
    try:
        f_wl = f_item.parent / item.assets['waterline_tide'].href
        assert f_wl.exists()

        # read waterline
        wl_ = gpd.read_parquet(f_wl, columns=['geometry'])
        wl = MultiLineString(list(wl_.geometry))

        return wl, wl_.crs

    except KeyError:
        print('empty waterline')
        return None, None



def read(items: list[pystac.item.Item]):

    date = []
    wl = []

    # loop through items
    for item in items:

        # date
        date.append(item.datetime)

        # waterline
        wl_, crs = read_wl(item)
        wl.append(wl_)


    df_wl = gpd.GeoDataFrame({"date": date, "geometry": wl}, crs=crs)

    return df_wl