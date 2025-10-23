# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QObject, Qt, QSettings
from qgis.PyQt.QtWidgets import QAction, QDockWidget
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject, QgsApplication, QgsMessageLog, Qgis
from .ui_dock import SettingsDock
from .snap_tool import SnapZenProTool
from .indexer import CentroidIndexTask, IndexBundle
import os

LOG_TAG = "SnapZen Pro"
def log_info(msg): QgsMessageLog.logMessage(str(msg), LOG_TAG, Qgis.Info)

class SnapZenProPlugin(QObject):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.action_toggle = None
        self.action_settings = None
        self.action_rebuild = None
        self.toolbar = None
        self.menu_actions = []
        self.dock = None
        self.ui = None
        self.tool = None
        self.index_bundle = IndexBundle()
        self._settings = QSettings("SnapZenPro", "SnapZenPro")

    def initGui(self):
        plugin_dir = os.path.dirname(__file__)
        icon_main = QIcon(os.path.join(plugin_dir, "icons", "snapzen_main.svg"))
        icon_settings = QIcon(os.path.join(plugin_dir, "icons", "snapzen_settings.svg"))

        # Toolbar
        self.toolbar = self.iface.addToolBar("SnapZen Pro")
        self.toolbar.setObjectName("SnapZenProToolbar")

        # Actions
        self.action_toggle = QAction(icon_main, "Activate SnapZen Pro", self.iface.mainWindow())
        self.action_toggle.setToolTip("Toggle SnapZen Pro snapping tool")
        self.action_toggle.setCheckable(True)
        self.action_toggle.toggled.connect(self._on_toggle)

        self.action_settings = QAction(icon_settings, "Settings", self.iface.mainWindow())
        self.action_settings.setToolTip("Open SnapZen Pro settings")
        self.action_settings.triggered.connect(self._show_settings)

        self.action_rebuild = QAction("Rebuild quick snap index", self.iface.mainWindow())
        self.action_rebuild.triggered.connect(self._rebuild_centroids)

        # Add to toolbar
        self.toolbar.addAction(self.action_toggle)
        self.toolbar.addAction(self.action_settings)

        # Plugins menu
        self.iface.addPluginToMenu("SnapZen Pro", self.action_toggle)
        self.iface.addPluginToMenu("SnapZen Pro", self.action_settings)
        self.iface.addPluginToMenu("SnapZen Pro", self.action_rebuild)

        # Dock (show by default)
        self.dock = QDockWidget("SnapZen Pro", self.iface.mainWindow())
        self.ui = SettingsDock(self.iface, self._settings)
        self.dock.setWidget(self.ui)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.show()

        # Signals
        self.ui.applyRequested.connect(self._apply_settings)
        self.ui.rebuildCentroidsRequested.connect(self._rebuild_centroids)

        # Layer changes
        QgsProject.instance().layersAdded.connect(lambda _: self._rebuild_centroids_if_enabled())
        QgsProject.instance().layersRemoved.connect(lambda _: self._rebuild_centroids_if_enabled())

        log_info("SnapZen Pro loaded")

    def unload(self):
        try:
            if self.tool and self.canvas.mapTool() is self.tool:
                self.canvas.unsetMapTool(self.tool)
        except Exception:
            pass
        if self.toolbar:
            try: self.iface.mainWindow().removeToolBar(self.toolbar)
            except Exception: pass
        try: self.iface.removePluginMenu("SnapZen Pro", self.action_toggle)
        except Exception: pass
        try: self.iface.removePluginMenu("SnapZen Pro", self.action_settings)
        except Exception: pass
        try: self.iface.removePluginMenu("SnapZen Pro", self.action_rebuild)
        except Exception: pass
        if self.dock:
            self.iface.removeDockWidget(self.dock)

    def _show_settings(self):
        if self.dock.isHidden(): self.dock.show()
        else: self.dock.raise_()

    def _on_toggle(self, enabled):
        if enabled:
            self._apply_settings()
        else:
            if self.canvas.mapTool() is self.tool:
                self.canvas.unsetMapTool(self.tool)
            self.tool = None

    def _apply_settings(self):
        s = self.ui.get_settings()
        self.tool = SnapZenProTool(self.iface, settings=s, index_bundle=self.index_bundle)
        self.canvas.setMapTool(self.tool)
        if self._should_build_index(s):
            self._rebuild_centroids()

    def _rebuild_centroids_if_enabled(self):
        s = self.ui.get_settings()
        if self._should_build_index(s):
            self._rebuild_centroids()

    def _should_build_index(self, settings):
        use_fallback = settings.get("use_fallback_index", settings.get("snap_centroids", False))
        build_index = settings.get("build_fallback_index", settings.get("build_centroid_index", True))
        return use_fallback and build_index

    def _rebuild_centroids(self):
        task = CentroidIndexTask(self.iface, only_visible=True)
        task.completed.connect(lambda: self._on_task_complete(task))
        QgsApplication.taskManager().addTask(task)

    def _on_task_complete(self, task):
        res = getattr(task, "result_bundle", None)
        if isinstance(res, IndexBundle):
            self.index_bundle = res
            if isinstance(self.tool, SnapZenProTool):
                self.tool.set_index_bundle(res)
