# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from lxml import etree


def _float_to_string(val):
    if isinstance(val, float):
        return format(val, ".2f")
    return str(val)


def _etree_subelement(tag, values):
    elem = etree.Element(tag)
    for key, val in values.items():
        if val:
            elem.attrib[key] = _float_to_string(val)
        if key == "tax" and val == 0.0:
            elem.attrib[key] = _float_to_string(val)
    return elem
