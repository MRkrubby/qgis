# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsTask, QgsProject, QgsWkbTypes, QgsSpatialIndex, QgsFeature, QgsGeometry, QgsPointXY

class IndexBundle:
    def __init__(self):
        self.point_index = None
        self.id_to_point = {}

    @property
    def centroid_index(self):  # backwards compatibility for existing tool logic
        return self.point_index

    @centroid_index.setter
    def centroid_index(self, value):
        self.point_index = value

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
        map_settings = canvas.mapSettings()
        target_extent = map_settings.extent() if map_settings else None
        target_crs = map_settings.destinationCrs() if map_settings else None

        id_to_point = {}
        idx = QgsSpatialIndex()
        running_id = 0

            if layer.wkbType() == QgsWkbTypes.NoGeometry:
                continue

            transformer = None
            to_layer_transform = None
            try:
                if target_crs is not None and target_crs.isValid() and layer.crs() != target_crs:
                    transformer = QgsCoordinateTransform(layer.crs(), target_crs, QgsProject.instance())
                    to_layer_transform = QgsCoordinateTransform(target_crs, layer.crs(), QgsProject.instance())
            except Exception:
                transformer = None
                to_layer_transform = None

            request = QgsFeatureRequest()
            if target_extent is not None and not target_extent.isNull():
                try:
                    layer_extent = target_extent
                    if to_layer_transform:
                        layer_extent = to_layer_transform.transformBoundingBox(target_extent)
                    request.setFilterRect(layer_extent)
                except Exception:
                    pass

            try:
                if hasattr(lyr, "geometryType") and lyr.geometryType() == QgsWkbTypes.PolygonGeometry:
                    for f in lyr.getFeatures():
                        if self.isCanceled(): return False
                        g = f.geometry()
                        if not g or g.isEmpty():
                            continue
                        centroid_geom = g.centroid()
                        if centroid_geom.isEmpty():
                            continue
                        try:
                            pt = QgsPointXY(centroid_geom.asPoint())
                        except Exception:
                            continue
                        id_to_point[running_id] = pt
                        tmp = QgsFeature()
                        tmp.setId(running_id)
                        tmp.setGeometry(QgsGeometry.fromPointXY(pt))
                        idx.insertFeature(tmp)
                        running_id += 1
            except Exception:
                continue

        bundle = IndexBundle()
        if id_to_point:
            bundle.point_index = idx
            bundle.id_to_point = id_to_point
        else:
            bundle.point_index = None
            bundle.id_to_point = {}
        self.result_bundle = bundle
        return True

    def finished(self, ok):
        self.completed.emit()
