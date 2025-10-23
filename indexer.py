# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsTask, QgsProject, QgsWkbTypes, QgsSpatialIndex, QgsFeature, QgsGeometry, QgsPointXY

class IndexBundle:
    def __init__(self):
        self.centroid_index = None
        self.id_to_point = {}

class CentroidIndexTask(QgsTask):
    completed = pyqtSignal()

    def __init__(self, iface, only_visible=True):
        super().__init__("SnapZenPro: Build centroid index", QgsTask.CanCancel)
        self.iface = iface
        self.only_visible = only_visible
        self.result_bundle = None

    def run(self):
        canvas = self.iface.mapCanvas()
        vis_ids = {l.id() for l in canvas.layers()} if self.only_visible else None

        id_to_point = {}
        idx = QgsSpatialIndex()

        for lyr in QgsProject.instance().mapLayers().values():
            if self.only_visible and lyr.id() not in vis_ids:
                continue
            try:
                if hasattr(lyr, "geometryType") and lyr.geometryType() == QgsWkbTypes.PolygonGeometry:
                    for f in lyr.getFeatures():
                        if self.isCanceled(): return False
                        g = f.geometry()
                        if not g: continue
                        c = g.centroid().asPoint()
                        pt = QgsPointXY(c)
                        id_to_point[f.id()] = pt
                        tmp = QgsFeature()
                        tmp.setGeometry(QgsGeometry.fromPointXY(pt))
                        idx.insertFeature(tmp)
            except Exception:
                continue

        bundle = IndexBundle()
        bundle.centroid_index = idx if len(id_to_point)>0 else None
        bundle.id_to_point = id_to_point
        self.result_bundle = bundle
        return True

    def finished(self, ok):
        self.completed.emit()
