# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import (
    QgsTask,
    QgsProject,
    QgsWkbTypes,
    QgsSpatialIndex,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsFeatureRequest,
    QgsVectorLayer,
    QgsCoordinateTransform,
)

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
        seen_coords = set()

        def add_point(pt_xy):
            nonlocal running_id
            if pt_xy is None:
                return
            key = (round(pt_xy.x(), 6), round(pt_xy.y(), 6))
            if key in seen_coords:
                return
            seen_coords.add(key)
            id_to_point[running_id] = pt_xy
            feature = QgsFeature()
            feature.setId(running_id)
            feature.setGeometry(QgsGeometry.fromPointXY(pt_xy))
            idx.insertFeature(feature)
            running_id += 1

        for layer in QgsProject.instance().mapLayers().values():
            if self.only_visible and layer.id() not in vis_ids:
                continue

            if not isinstance(layer, QgsVectorLayer):
                continue

            if not layer.isValid():
                continue

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
                for feature in layer.getFeatures(request):
                    if self.isCanceled():
                        return False

                    geom = feature.geometry()
                    if not geom or geom.isEmpty():
                        continue

                    def maybe_transform(pt):
                        if transformer is None:
                            return pt
                        try:
                            return transformer.transform(pt)
                        except Exception:
                            return None

                    try:
                        for vertex in geom.vertices():
                            pt_xy = QgsPointXY(vertex)
                            add_point(maybe_transform(pt_xy))
                    except Exception:
                        # Fall back to single-point conversion if iteration fails
                        try:
                            pt_xy = QgsPointXY(geom.asPoint())
                            add_point(maybe_transform(pt_xy))
                        except Exception:
                            continue

                    if QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.PolygonGeometry:
                        try:
                            centroid_geom = geom.centroid()
                            if centroid_geom and not centroid_geom.isEmpty():
                                pt_xy = QgsPointXY(centroid_geom.asPoint())
                                add_point(maybe_transform(pt_xy))
                        except Exception:
                            continue
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
