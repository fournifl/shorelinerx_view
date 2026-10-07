import pystac


def read(ls: list):

    items = [pystac.Item.from_file(f) for f in ls]

    return items

