# -*- coding: utf-8 -*-
from .plugin import SnapZenProPlugin

def classFactory(iface):
    return SnapZenProPlugin(iface)
