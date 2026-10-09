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
        wl = gpd.read_parquet(f_wl, columns=['geometry'])

        # Reproject to Web Mercator (required for tile basemaps)
        wl = wl.to_crs(3857)

        # convert series of Linestring to a multilestring
        mls = MultiLineString(list(wl.geometry))

        # mission
        mission = item.properties['platform']

        return mls, wl.crs, mission

    except KeyError:
        print('empty waterline')
        return None, None, None



def read(items: list[pystac.item.Item], f_aoi: Path):

    date = []
    wl = []
    mission = []

    # loop through items
    for item in items:

        # date
        date.append(item.datetime)

        # waterline
        mls, crs, m = read_wl(item)
        wl.append(mls)
        mission.append(m)

    # create a geodataframe of waterline
    gdf_wl = gpd.GeoDataFrame({"date": date, "mission": mission, "geometry": wl}, crs=crs)

    return gdf_wl