from __future__ import annotations

import os
import sys
from datetime import date
from typing import TYPE_CHECKING

try:
    from ..algemene_functies import filtercheck, get_projectinfo, opsteller_initialen
except ModuleNotFoundError:  # pragma: no cover - executed outside QGIS runtime
    def filtercheck(*_args, **_kwargs):
        return None

    def get_projectinfo(*_args, **_kwargs):
        return {}

    def opsteller_initialen() -> str:
        return ""

try:
    from ..errorhandler import messagebox
except ModuleNotFoundError:  # pragma: no cover - executed outside QGIS runtime
    def messagebox(*_args, **_kwargs):
        return None

if TYPE_CHECKING:  # pragma: no cover - only for static type checking
    from PyQt5.QtWidgets import QTabWidget
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsLayerTree,
        QgsLayerTreeGroup,
        QgsLayerTreeLayer,
        QgsLayout,
        QgsLayoutItem,
        QgsLayoutItemLegend,
        QgsLayoutItemManualTable,
        QgsLayoutItemMap,
        QgsLayoutTable,
        QgsPrintLayout,
        QgsProject,
        QgsReadWriteContext,
        QgsVectorLayer,
        Qgis,
    )
    from ..dialogs.printomgeving_combi import printomgeving_dialog


class _ModuleAttributeProxy:
    """Proxy that resolves attributes on the :mod:`printomgeving` package.

    The unit tests patch objects on :mod:`printomgeving`.  Importing them here
    through this proxy keeps the reference in sync with the patched attribute,
    while still deferring to the real classes when executed inside QGIS.
    """

    def __init__(self, attribute: str) -> None:
        self._module_name = __package__
        self._attribute = attribute

    def _resolve(self):
        module = sys.modules.get(self._module_name)
        if module is None or not hasattr(module, self._attribute):
            raise AttributeError(
                f"Attribute '{self._attribute}' is not available on module '{self._module_name}'."
            )
        return getattr(module, self._attribute)

    def __getattr__(self, name):
        return getattr(self._resolve(), name)

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)


QApplication = _ModuleAttributeProxy("QApplication")
QDomDocument = _ModuleAttributeProxy("QDomDocument")
Qgis = _ModuleAttributeProxy("Qgis")
QgsCoordinateReferenceSystem = _ModuleAttributeProxy("QgsCoordinateReferenceSystem")
QgsLayerTree = _ModuleAttributeProxy("QgsLayerTree")
QgsLayerTreeGroup = _ModuleAttributeProxy("QgsLayerTreeGroup")
QgsLayerTreeLayer = _ModuleAttributeProxy("QgsLayerTreeLayer")
QgsLayout = _ModuleAttributeProxy("QgsLayout")
QgsLayoutItem = _ModuleAttributeProxy("QgsLayoutItem")
QgsLayoutItemLegend = _ModuleAttributeProxy("QgsLayoutItemLegend")
QgsLayoutItemManualTable = _ModuleAttributeProxy("QgsLayoutItemManualTable")
QgsLayoutItemMap = _ModuleAttributeProxy("QgsLayoutItemMap")
QgsLayoutTable = _ModuleAttributeProxy("QgsLayoutTable")
QgsPrintLayout = _ModuleAttributeProxy("QgsPrintLayout")
QgsProject = _ModuleAttributeProxy("QgsProject")
QgsReadWriteContext = _ModuleAttributeProxy("QgsReadWriteContext")
QgsVectorLayer = _ModuleAttributeProxy("QgsVectorLayer")
iface = _ModuleAttributeProxy("iface")
get_common_fields = _ModuleAttributeProxy("get_common_fields")
get_layout_path = _ModuleAttributeProxy("get_layout_path")
get_onderdeel_info = _ModuleAttributeProxy("get_onderdeel_info")
type_checks = _ModuleAttributeProxy("type_checks")
open = _ModuleAttributeProxy("open")

class Printomgeving:
    def __init__(self, plugin_dir:str, printomgeving_dialog:printomgeving_dialog):
        self.DEBUG = True
        self.plugin_dir = plugin_dir.replace('/', '\\')
        self.printomgeving_dialog = printomgeving_dialog
        self.project = QgsProject.instance()
        today = date.today()
        self.dt_string = today.strftime("%Y-%m-%d")
        self.root: QgsLayerTree | None = self.project.layerTreeRoot()
        self.qml_path = os.path.join(self.plugin_dir, 'styles')
        self.at = None
    
    def __del__(self):
        print("Printomgeving instance destroyed!")

    def run_printomgeving(self):
        """
        Functie die wordt aangeroepen vanuit dialoog printomgeving.

        Deze functie selecteert de juiste printomgeving op basis van de ingevulde gegevens en opent die. 
        Gegevens worden toegevoegd aan de printomgeving.

        Parameters
        ----------
        self : 
            om objecten makkelijk door te geven aan opvolgende functies.

        Returns
        -------
        None

        """
        QApplication.processEvents()
        lmgr = self.project.layoutManager()
        
        tab:QTabWidget = self.printomgeving_dialog.tabWidget.currentWidget()
        self.tab = tab
        
        if self.handle_open_existing_layout(tab):
            return

        if tab.objectName() == 'tab_milieu':
            path_layout = get_layout_path(tab, "", "Milieu", self.printomgeving_dialog)
            inputs = type_checks(self.printomgeving_dialog, 'Milieu')

        elif tab.objectName() == 'tab_geotechniek':
            path_layout = get_layout_path(tab, "_3", "Geotechniek", self.printomgeving_dialog)
            inputs = type_checks(self.printomgeving_dialog, 'Geotechniek')

        if not inputs:
            return

        if tab.objectName() == 'tab_geotechniek':
            if self.printomgeving_dialog.hoogveld.isChecked():
                path_layout = path_layout + '_Hoogveld'
            crs = self.project.crs()
            if crs == QgsCoordinateReferenceSystem(31370): # Belgique
                path_layout = path_layout + '_B'

        path_layout = path_layout + '.qpt'

        myTemplateFile = open(os.path.join(self.plugin_dir, path_layout),'rt')  # Location of template in pluginstructure

        myTemplateContent = myTemplateFile.read()
        myTemplateFile.close()
        myDocument = QDomDocument()
        myDocument.setContent(myTemplateContent, False)
        # lmgr = self.project.layoutManager()  # Defining layoutmanager
        self.newcomp = QgsPrintLayout(self.project)  # Defining new layout/composer

        lmgr.addLayout(self.newcomp)  # Adding new layout to layoutmanager
        self.newcomp.loadFromTemplate(myDocument, QgsReadWriteContext())  # Load template in layout newcomp

        tab_name = tab.objectName()
        dialog = self.printomgeving_dialog      

        if tab_name == 'tab_geotechniek':
            fields = get_common_fields(self.printomgeving_dialog, '_3')
            printomgeving_dialog_schaal_int = fields.get("schaal", 0)
            bijlagenr = f"{int(dialog.bijlagenr.text()):02}"
            versie = f"{dialog.versie_3.text()}" 
            bijlage_versie = f"{bijlagenr}.v{versie}" if dialog.versie_3.text() else f"{bijlagenr}"
            onderdeel, onderdeel_type = get_onderdeel_info(dialog, '_3')
            title = f"{fields['projectnummer']}.T{bijlage_versie}{'_'}{onderdeel}{'_'}{self.dt_string}"

        elif tab_name == 'tab_milieu':
            fields = get_common_fields(self.printomgeving_dialog)
            printomgeving_dialog_schaal_int = fields.get("schaal", 0)
            versie = f"{dialog.versie.text()}"
            bijlagenr = f"{'1' if dialog.topografisch.isChecked() else '7'}"
            bijlage_versie = f"{bijlagenr}.v{versie}" if dialog.versie.text() else f"{bijlagenr}"
            
            
            onderdeel, onderdeel_type = get_onderdeel_info(dialog)
            title = f"{fields['projectnummer']}.T{bijlage_versie}{'_'}{onderdeel}{'_'}{self.dt_string}"
        
        

        # Set fields on layout
        self.newcomp.itemById('Projectnr').setText(f"Projectnr         {fields['projectnummer']}")
        self.newcomp.itemById('Projectnaam').setText(f"Project            {fields['projectnaam']}")
        self.newcomp.itemById('Projectleider').setText(f"Projectleider        {fields['projectleider']}")
        self.newcomp.itemById('Onderdeel').setText(f"Onderdeel       {onderdeel_type}\n                      {fields['omschrijving']}")
        self.newcomp.itemById('Opsteller').setText(f"Getekend            {fields['opsteller']}")
        self.newcomp.itemById('Schaal').setText("Schaal ")
        self.newcomp.itemById('Bijlagenr').setText(f"Bijlagenr         T{bijlage_versie}")

        if tab_name == 'tab_geotechniek':
            self.newcomp.itemById('Locatie').setText(f"Locatie            {fields['locatie']}")
        
        if any([self.printomgeving_dialog.topografisch.isChecked()]):
            #self.handle_topografisch()
            # Haal de extent van het huidige kaartbeeld op
            # e = iface.mapCanvas().extent()
            # xmax = e.xMaximum()
            # ymax = e.yMaximum()
            # xmin = e.xMinimum()
            # ymin = e.yMinimum()

            # # Bepaal het midden van de kaart
            # xmean = int(((xmax - xmin) / 2) + xmin)
            # ymean = int(((ymax - ymin) / 2) + ymin)

            # # Zoek de X- en Y-coördinaatvelden in de lay-out en vul ze met de berekende waarden
            # X_coo = self.newcomp.itemById('X-coordinaat')
            # X_coo.setText(' ' + str('{:,}'.format(xmean).replace(',', '.')))
            # Y_coo = self.newcomp.itemById('Y-coordinaat')
            # Y_coo.setText(' ' + str('{:,}'.format(ymean).replace(',', '.')))
            self.newcomp.setName(title)

            if not self.setup_map(printomgeving_dialog_schaal_int):
                return

        elif self.newcomp:
            if not self.setup_map(printomgeving_dialog_schaal_int):
                return
            # Set title
            self.newcomp.setName(title)

            itemlegend = self.setup_legend()
            if itemlegend is None:
                return

            # set up groups
            if not self.setup_groups():
                return

            if not self.get_group_layers():
                return

            layers: list[QgsVectorLayer] = [
                self.get_layer_by_name(layer_name) for layer_name in self.l_layers_d
            ]
            #! 2 aparte loops omdat lagen anders door elkaar komen te staan in de legenda
            rapportage = self.printomgeving_dialog.rapportage.isChecked() or self.printomgeving_dialog.rapportage_3.isChecked()
            index = 0
            for layer in layers:
                index -= 1
                if layer is None:
                    continue
                self.setup_laag(layer, layer.name(), index, rapportage, self.group)

            if rapportage and self.group_r is not None:
                index = 0
                for layer in layers:
                    index -= 1
                    if layer is None:
                        continue
                    self.setup_laag(layer, layer.name(), index, True, self.group_r)

            if tab.objectName() == 'tab_geotechniek':
                print('GEO')
                group_node = self.root.findGroup("Milieu") if self.root else None
                if group_node:
                    group_node.setItemVisibilityChecked(False)
                itemlegend.setTitle('Onderzoekspunten')

            elif tab.objectName() == 'tab_milieu':
                print('MILIEU')
                group_node = self.root.findGroup("Geotechniek") if self.root else None
                if group_node:
                    group_node.setItemVisibilityChecked(False)
                self.update_legend(self.layertree)

            itemlegend.adjustBoxSize()

            if not self.setup_table():
                return

        # print(newcomp)
        iface.openLayoutDesigner(layout=self.newcomp)

        #self.printomgeving_dialog.button_Box.accepted.disconnect(self.run_printomgeving)

    def get_layer_by_name(self, layer_name):
        """
        Retrieve a layer from the group's children by its name.

        Parameters:
        self (object): The instance of the class containing the group of children.
        layer_name (str): The name of the layer to be retrieved.

        Returns:
        layer (object): The layer object if found, otherwise None.
        """
        if self.group_d is None:
            if self.DEBUG:
                print(f"Groep niet beschikbaar om laag '{layer_name}' op te halen")
            return None

        for child in self.group_d.children() or []:
            if child.name() == layer_name:
                layer = child.layer()
                return layer

        return None
    
    def get_group_layers(self) -> bool:
        """
        Bepaalt en stelt de relevante lagen(groepen) in afhankelijk van het geselecteerde tabblad.

        - Als het tabblad 'tab_geotechniek' is geselecteerd:
            * self.l_layers_d wordt ingesteld op ['Sonderingen', 'Overig', 'Boringen', 'Vast punt']
            * self.group_d en self.g_division worden ingesteld op de groepen 'Geotechniek'
        - Als het tabblad 'tab_milieu' is geselecteerd:
            * self.l_layers_d wordt ingesteld op ['Boringen']
            * self.group_d en self.g_division worden ingesteld op de groepen 'Milieu'

        Vereist:
            self.tab.objectName(): geeft de naam van het actieve tabblad terug.
            self.root.findGroup(str): zoekt een groep op naam in de root.
            self.layertree.findGroup(str): zoekt een groep op naam in de layertree.
        
        Returns:
            bool: True als de benodigde groepen gevonden konden worden, anders False.
        """
        tab_name = self.tab.objectName()
        if tab_name == 'tab_geotechniek':
            self.l_layers_d = ['Sonderingen', 'Overig', 'Boringen', 'Vast punt']
            group_name = 'Geotechniek'
        elif tab_name == 'tab_milieu':
            self.l_layers_d = ['Boringen']
            group_name = 'Milieu'
        else:
            iface.messageBar().pushMessage(
                "Fout",
                f"Tab moet milieu of geotechniek zijn, niet '{tab_name}'",
                level=Qgis.Critical
            )
            return False

        if self.root is None or self.layertree is None:
            iface.messageBar().pushMessage(
                "Fout",
                "Laagstructuur is niet beschikbaar om groepen te bepalen",
                level=Qgis.Critical
            )
            return False

        self.group_d = self.root.findGroup(group_name)
        self.g_division = self.layertree.findGroup(group_name)

        if self.group_d is None or self.g_division is None:
            iface.messageBar().pushMessage(
                "Fout",
                f"Groep '{group_name}' niet gevonden in de layertree",
                level=Qgis.Critical
            )
            return False

        return True
    
    def setup_laag(self, layer:QgsVectorLayer, layer_name:str, index:int, rflag:bool, group:QgsLayerTreeGroup):
        """
        Voegt een gekloonde laag toe aan de juiste groep in de layertree, 
        stelt de juiste symbologie in en beheert de zichtbaarheid.

        Parameters:
            layer (QgsVectorLayer): De te klonen laag die wordt toegevoegd.
            layer_name (str): Naam van de laag, gebruikt voor het ophalen van het juiste QML-stijlbestand.
            tab (str): Naam van het actieve tabblad, beïnvloedt de keuze van de symbologie.
            index (int): Indexpositie voor het invoegen van de laag in de layertree.
            rflag (bool, optioneel): Indien True, wordt de laag aan de 'rapportage'-groep toegevoegd en krijgt deze de rapportage-stijl. 
                                    Indien False, wordt de standaardgroep gebruikt.

        Werking:
            - Bepaalt aan de hand van rflag of de laag aan de rapportagegroep of standaardgroep wordt toegevoegd.
            - Kloont de opgegeven laag en voegt deze toe aan het project zonder direct zichtbaar te zijn in de layertree.
            - Haalt de juiste QML-stijlbestanden op en past deze toe op de laag.
            - Wijzigt de naam van de laag afhankelijk van rflag.
            - Zet de zichtbaarheid van de originele laag uit afhankelijk van rflag.
            - Verwijdert de laag uit de huidige divisiegroep (indien aanwezig) afhankelijk van rflag.
            - Voegt de laag toe aan de layertree op de juiste positie afhankelijk van rflag.

        Vereisten:
            - self.group, self.group_r: QgsLayerTreeGroup-objecten voor standaard en rapportage groepen.
            - self.project: QgsProject-object.
            - self.qml_path: Pad naar de map met QML-stijlbestanden.
            - self.root, self.g_division, self.layertree: QgsLayerTree-structuren.
            - self.get_legendalaag_info: Methode die QML-bestandsnamen retourneert.
        """
        if group is None:
            iface.messageBar().pushMessage(
                "Fout",
                f"Geen geldige groepsreferentie voor laag '{layer_name}'",
                level=Qgis.Critical
            )
            return

        if not hasattr(self.project, 'addMapLayer'):
            iface.messageBar().pushMessage(
                "Fout",
                "Project ondersteunt geen addMapLayer, laag kan niet worden toegevoegd",
                level=Qgis.Critical
            )
            return

        # Kloon de laag en voeg deze toe aan het project (maar niet direct zichtbaar in de layertree)
        lyr: QgsVectorLayer = layer.clone()
        self.project.addMapLayer(lyr, False)
        group.insertChildNode(index, QgsLayerTreeLayer(lyr))

        legenda_name, qml = self.get_legendalaag_info(layer_name,  group, rflag)
        qml_file = os.path.join(self.qml_path, qml + '.qml')

        print(rflag, qml_file)

        # Pas de QML-stijl toe en forceer een hertekening
        lyr.loadNamedStyle(qml_file)
        lyr.triggerRepaint()

        # Stel de naam van de laag in afhankelijk van rflag
        if rflag and group.name() == 'Rapportage':
            lyr.setName(layer.name() + ' rapportage')
            # Zet de zichtbaarheid van de originele laag uit (indien aanwezig)
            layer_node = self.root.findLayer(layer.id())
            if layer_node:
                layer_node.setItemVisibilityChecked(False)
        else:
            lyr.setName(legenda_name)

        # Verwijder de laag uit de huidige divisiegroep (indien aanwezig)
        if self.g_division is None:
            iface.messageBar().pushMessage(
                "Fout",
                "Geen divisiegroep beschikbaar om laag te verplaatsen",
                level=Qgis.Critical
            )
        else:
            self.g_division.removeLayer(layer)

        # Voeg de laag toe aan de layertree op de juiste positie
        if self.layertree is None:
            iface.messageBar().pushMessage(
                "Fout",
                "Geen layertree beschikbaar om laag toe te voegen",
                level=Qgis.Critical
            )
            return

        if group.name() == 'Rapportage':
            self.layertree.insertChildNode(-1, QgsLayerTreeLayer(lyr))
        else:
            self.layertree.insertChildNode(-1 * index, QgsLayerTreeLayer(lyr))

    def handle_topografisch(self):
        """
        Bepaalt het middelpunt van het huidige kaartbeeld (canvas) en vult 
        de X- en Y-coördinaatvelden in een lay-outcomponent met deze waarden.
        Opent vervolgens de lay-outdesigner met de bijgewerkte component.

        Werking:
            - Haalt de huidige extent (zichtbare kaartgebied) op van de QGIS map canvas.
            - #Berekent het midden van de kaart (xmean, ymean) als geheel getal.
            - Zoekt de lay-outvelden 'X-coordinaat' en 'Y-coordinaat' op in self.newcomp.
            - #Zet de tekst van deze velden naar de berekende coördinaten, 
            #geformatteerd met een punt als duizendtalseparator.
            - Opent de lay-outdesigner met de geüpdatete lay-outcomponent.

        Vereisten:
            - self.newcomp: QGIS Layout object met itemById-methode voor het ophalen van lay-outvelden.
            - iface: QGIS interface object (globaal beschikbaar in QGIS Python console).
            - iface.mapCanvas(): Geeft toegang tot het huidige kaartbeeld.
            - iface.openLayoutDesigner(layout): Opent de lay-outdesigner voor een gegeven lay-out.
        """
        # Haal de extent van het huidige kaartbeeld op
        e = iface.mapCanvas().extent()
        xmax = e.xMaximum()
        ymax = e.yMaximum()
        xmin = e.xMinimum()
        ymin = e.yMinimum()

        # Bepaal het midden van de kaart
        xmean = int(((xmax - xmin) / 2) + xmin)
        ymean = int(((ymax - ymin) / 2) + ymin)

        # Zoek de X- en Y-coördinaatvelden in de lay-out en vul ze met de berekende waarden
        X_coo = self.newcomp.itemById('X-coordinaat')
        X_coo.setText(' ' + str('{:,}'.format(xmean).replace(',', '.')))
        Y_coo = self.newcomp.itemById('Y-coordinaat')
        Y_coo.setText(' ' + str('{:,}'.format(ymean).replace(',', '.')))

        # Open de lay-outdesigner met de bijgewerkte lay-outcomponent
        iface.openLayoutDesigner(layout=self.newcomp)

    def get_legendalaag_info(self, layer_name:str, group:QgsLayerTreeGroup, rapportage=False):
        """
        Genereert de juiste legenda-naam en QML-bestandsnaam op basis van de laagnaam, tabblad en rapportage-status.

        Parameters:
            layer_name (str): Naam van de laag (bijv. 'Boringen', 'Vast punt')
            tab_object_name (str): Naam van het tabblad (bijv. 'tab_milieu', 'tab_geotechniek')
            rapportage (bool): Geeft aan of het om een rapportageversie gaat (standaard False)

        Returns:
            tuple: (legenda_name, legenda_qml) - De naam voor de legenda en de QML-bestandsnaam

        Logica:
            1. Basis QML-bestandsnaam is altijd 'Legenda ' + laagnaam
            2. Speciale gevallen:
            - Boringen krijgen '_M' of '_G' suffix afhankelijk van het tabblad
            - Vaste punten behouden hun oorspronkelijke naam
            3. Bij rapportage wordt '_rapportage' toegevoegd aan de QML-naam
        """

        # Opties
        # Voor de groep legenda:
            # Legenda plus naam: altijd
            # Legenda plus naam plus _rapportage: alleen bij boringen en sonderingen wanneer er sprake is van rapportage
        # Voor de groep rapportage:
            # Naam plus rapportage: alleen voor de groep rapportage
        
        groupname = group.name()
        if groupname == 'Rapportage':
            if layer_name == 'Boringen':
                if self.tab.objectName() == 'tab_milieu':
                    layer_name = 'Boringen_M'
                elif self.tab.objectName() == 'tab_geotechniek':
                    layer_name = 'Boringen_G'
                else:
                    raise Exception(f'Onbekend tabblad: {self.tab.objectName()}')
            return layer_name, layer_name + '_rapportage'
        
        else:
            legenda_name = ''
            legenda_qml = 'Legenda ' + layer_name
            # Specifieke logica voor Boringen per tabblad
            if layer_name == 'Boringen' and self.tab.objectName() == 'tab_milieu':
                legenda_qml = 'Legenda Boringen_M'
                legenda_name = 'Boring'

            elif layer_name == 'Boringen' and self.tab.objectName() == 'tab_geotechniek':
                legenda_qml = 'Legenda Boringen_G'
                legenda_name = 'Boring'

            # Specifieke logica voor Vast punt
            elif layer_name == 'Vast punt':
                legenda_name = 'Vast punt'

            legenda_qml = legenda_qml + '_rapportage' if rapportage else legenda_qml
            return legenda_name, legenda_qml
    
    def setup_groups(self) -> bool:
        """
        Initialiseert en beheert de benodigde layergroepen in de QGIS layer tree.

        Werking:
            1. Verwijdert eventuele bestaande 'Rapportage' en 'Legenda' groepen
            2. Maakt een nieuwe 'Legenda' groep aan
            3. Controleert of rapportage is aangevraagd via de UI:
            - Als rapportage is aangevraagd (checkbox(es) aangevinkt):
                * Maakt een 'Rapportage' groep aan vóór alle andere groepen (index 0)
                * Bewaart referenties in self.group en self.group_r

        Vereisten:
            - self.root: QgsLayerTreeGroup (hoofdgroep)
            - self.printomgeving_dialog: Dialoogvenster met UI-elementen
            - self.printomgeving_dialog.rapportage en rapportage_3: Checkbox widgets

        Returns:
            bool: True als de groepen konden worden opgebouwd, anders False.
        """
        if self.root is None:
            iface.messageBar().pushMessage(
                "Fout",
                "Kan geen groepen opzetten zonder layerTreeRoot",
                level=Qgis.Critical
            )
            self.group = None
            self.group_r = None
            return False

        # Verwijder bestaande groepen
        group = self.root.findGroup("Rapportage")
        if group:  # Voorkom None-reference errors
            self.root.removeChildNode(group)

        group = self.root.findGroup("Legenda")
        if group:
            self.root.removeChildNode(group)

        # Maak nieuwe Legenda groep
        self.group = self.root.addGroup("Legenda")

        # Controleer rapportage-status
        if any([
            self.printomgeving_dialog.rapportage.isChecked(),
            self.printomgeving_dialog.rapportage_3.isChecked()
        ]):
            # Maak Rapportage groep als eerste node (index 0)
            self.group_r = self.root.insertGroup(0, 'Rapportage')
        else:
            self.group_r = None

        return self.group is not None

    def setup_legend(self):
        """
        Configureert de legenda in een QGIS lay-out en initialiseert de layer tree referentie.

        Werking:
            1. Haalt de legenda uit de lay-out aan de hand van ID 'Legenda'
            2. Stelt het referentiepunt in (positie 8 = onderkant rechts)
            3. Controleert of de legenda bestaat:
            - Bij ontbreken: toont foutmelding en retourneert None
            4. Configureert legenda-instellingen:
            - Schakelt automatisch bijwerken uit
            - Synchroniseert met zichtbare kaartlagen
            - Reset formaataanpassing
            5. Bewaart de layer tree referentie voor latere operaties

        Returns:
            QgsLayoutItemLegend: De geconfigureerde legenda OF None bij fout

        Vereisten:
            - self.newcomp: QgsPrintLayout object met een legenda-item
            - iface: QGIS interface object voor foutmeldingen
        """
        # Haal legenda uit lay-out
        legend: QgsLayoutItemLegend = self.newcomp.itemById('Legenda')
        
        # Stel referentiepiet in (moet vóór existentie-check ivm mogelijke None-referentie)
        if legend:
            legend.setReferencePoint(8)  # 8 = QgsLayoutItem.LowerRight

        # Fouthandeling bij ontbrekende legenda
        if legend is None:
            iface.messageBar().pushMessage(
                "Fout", 
                "Openen van template mislukt: geen legenda gevonden. Neem contact op met team GIS.", 
                level=Qgis.Critical
            )
            return None

        try:
            # Configureer legenda-instellingen
            legend.setAutoUpdateModel(False)  # Schakel automatisch bijwerken uit
            legend.updateFilterByMap(True)    # Filter op zichtbare kaartlagen
            # legend.setResizeToContents(True)  # Reset formaat
            legend.setResizeToContents(False) # Sta handmatig aanpassen toe
            
            # Initialiseer layer tree referentie
            m = legend.model()
            if m is None or not hasattr(m, 'rootGroup'):
                iface.messageBar().pushMessage(
                    "Fout",
                    "Legenda model ontbreekt of ondersteunt geen rootGroup",
                    level=Qgis.Critical
                )
                return None

            root_group = m.rootGroup()
            if root_group is None:
                iface.messageBar().pushMessage(
                    "Fout",
                    "Kon rootGroup van legenda niet bepalen",
                    level=Qgis.Critical
                )
                return None

            self.layertree = root_group

            return legend
            
        except Exception as e:
            iface.messageBar().pushMessage(
                "Fout", 
                f"Onverwachte fout bij legenda-instellingen: {str(e)}", 
                level=Qgis.Critical
            )
            return None
    
    def setup_map(self, scale):
        """
        Initialiseert en configureert het kaartitem in een QGIS lay-out met foutcontrole.

        Werking:
            1. Haalt het kaartitem op uit de lay-out aan de hand van ID 'Kaart'
            2. Voert een refresh uit om de kaartweergave te synchroniseren met de huidige canvasinstellingen

        Vereisten:
            - self.newcomp: QgsPrintLayout object met een kaart-item
            - Een geldig kaart-item met ID 'Kaart' moet aanwezig zijn in de lay-out

        Returns:
            bool: True bij succes, False bij ontbrekend kaart-item
        """
        self.kaart:QgsLayoutItemMap = self.newcomp.itemById('Kaart') # (source: http://osgeo-org.1560.x6.nabble.com/QGIS-Developer-QgsLayout-returns-different-types-on-different-platforms-td5365596.html)

        if not self.kaart:
            iface.messageBar().pushMessage(
                "Fout",
                "Kaartitem met ID 'Kaart' niet gevonden in lay-out",
                level=Qgis.Warning
            )
            return False
            
        try:
            self.kaart.zoomToExtent(iface.mapCanvas().extent()) # Zoom to extent with map scale of canvas extent
            self.kaart.setScale(scale)
            return True
            
        except Exception as e:
            iface.messageBar().pushMessage(
                "Fout",
                f"Kaartrefresh mislukt: {str(e)}",
                level=Qgis.Critical
            )
            return False
    
    def setup_table(self):
        """
        Initialiseert en configureert een tabel in een QGIS lay-out op basis van het actieve tabblad.

        Werking:
            1. Maakt een handmatige tabel aan in de lay-out
            2. Configureert tabelgedrag (verberg lege tabellen)
            3. Voegt tabel toe aan de lay-out
            4. Tabblad-specifieke acties:
            - Geotechniek: Koppelt extent wijzigingen aan update-logica
            - Milieu: Voegt archieftabel toe met milieu-specifieke inhoud

        Vereisten:
            - self.newcomp: QgsPrintLayout object
            - self.tab: QTabWidget object met juiste objectName()
            - self.kaart: QgsLayoutItemMap object (voor geotechniek-tab)
            - self.extentChange: Methode voor kaartextent-afhankelijke updates
            - self.addarchieftablemilieu: Methode voor milieu-specifieke tabelinhoud

        Foutscenario's:
            - Ontbrekende kaart bij geotechniek-tab (mogelijke None-referentie)
            - Ontbrekende tabblad-identificatie
        """
        # try:
        # Basis tabel setup
        self.tbl = QgsLayoutItemManualTable.create(self.newcomp)
        self.tbl.setEmptyTableBehavior(QgsLayoutTable.EmptyTableMode.HideTable)
        self.newcomp.addMultiFrame(self.tbl)

        # Tab-specifieke logica
        tab_name = self.tab.objectName()
        
        if tab_name == 'tab_geotechniek':
            print(self.kaart)
            if not hasattr(self, 'kaart'):
                raise AttributeError("Kaartitem ontbreekt in geotechniek-configuratie")
            
            self.extentChange()
            self.kaart.extentChanged.connect(self.extentChange)
            return True
            
        elif tab_name == 'tab_milieu':
            self.addarchieftablemilieu()
            return True
            
        else:
            raise ValueError(f"Onbekend tabblad: {tab_name}")
                
        # except Exception as e:
        #     iface.messageBar().pushMessage(
        #         "Fout",
        #         f"Tabelconfiguratie mislukt: {str(e)}",
        #         level=Qgis.Critical
        #     )
        #     return False
    
    def handle_open_existing_layout(self, tab:QTabWidget):
        """
        Opent een bestaande lay-out gebaseerd op tabbladselectie en initialiseert benodigde componenten.

        Parameters:
            tab (QTabWidget): Het actieve tabblad dat bepaalt welke layout-lijst gebruikt wordt

        Returns:
            bool: True indien lay-out succesvol geopend, False bij fout of 'Geen' selectie

        Werking:
            1. Bepaalt welke layout-lijst gebruikt moet worden op basis van tabblad-ID
            2. Controleert geselecteerde lay-out
            3. Laadt de lay-out en initialiseert kaart + tabel
            4. Opent lay-out designer bij succes

        Foutscenario's:
            - Geen lay-out geselecteerd ('Geen' geselecteerd)
            - Lay-out niet gevonden in project
            - Initialisatiefouten in setup_map() of setup_table()
        """
        try:
            # Bepaal selector
            tab_name = tab.objectName()
            layout_selectors = {
                'tab_milieu': self.printomgeving_dialog.layouts,
                'tab_geotechniek': self.printomgeving_dialog.layouts_3
            }
            
            if tab_name not in layout_selectors:
                raise ValueError(f"Ongeldig tabblad: {tab_name}")
                
            # Haal selectie op
            selected_items = layout_selectors[tab_name].selectedItems()
            print(selected_items)
            if not selected_items:
                raise ValueError("Geen lay-out geselecteerd")
                
            selected = selected_items[0].text()
            print(selected)
            if selected == 'Geen':
                return False

            if not isinstance(selected, str):
                return False
                
            # Laad lay-out
            self.newcomp: QgsLayout = self.project.layoutManager().layoutByName(selected)
            if not self.newcomp:
                raise RuntimeError(f"Lay-out '{selected}' niet gevonden")
            
            scale = self.newcomp.itemById('Kaart').scale()
            self.kaart = self.newcomp.itemById('Kaart')

            # Zet de opsteller altijd op de huidige gebruiker (initialen)
            opsteller = opsteller_initialen()
            #opsteller = 'Testpersoon'
            opsteller_item = self.newcomp.itemById('Opsteller')
            if opsteller_item:
                opsteller_item.setText(f"Getekend            {opsteller}")
                
            # Initialiseer
            if not self.setup_table():
                raise RuntimeError("Component initialisatie mislukt")
                
            iface.openLayoutDesigner(layout=self.newcomp)
            return True
            
        except Exception as e:
            iface.messageBar().pushMessage(
                "Fout",
                f"Lay-out openen mislukt: {str(e)}",
                level=Qgis.Critical
            )
            return False
    
    def update_legend(self, g:QgsLayerTreeGroup):
        """
        Werkt de legenda bij door specifieke groepen en lagen te verwijderen/aan te passen.

        Parameters:
            g (QgsLayerTreeGroup): De hoofdgroep van de layer tree waarin gewerkt wordt

        Werking:
            1. Verwijder specifieke groepen ('Ondergrond (GAK)', 'QTG')
            2. Verwerk lagen met naam 'Vlak':
            - Kloon de laag, verwijder de naam en plaats bovenaan
            - Verwijder originele laag
            3. Verwijder specifieke lagen uit 'Ondergrond' groep en plaats deze bovenaan:
            - 'Topografische kaart' en 'Luchtfoto'
            - Kloon de groep en plaats bovenaan
            - Verwijder originele groep

        Foutafhandeling:
            - Logt fouten naar console indien DEBUG=True
            - Beveiligd tegen None-references en index errors
        """
        # 1. Verwijder ongewenste groepen
        groups_to_remove = ['Ondergrond (GAK)', 'QTG']
        for group_name in groups_to_remove:
            group_node = g.findGroup(group_name)
            if group_node:
                try:
                    g.removeChildNode(group_node)
                except Exception as e:
                    if self.DEBUG:
                        print(f'Fout bij verwijderen groep {group_name}: {str(e)}')

        # 2. Verwerk specifieke lagen
        layernames_to_remove = ['Vlak']
        for layername in layernames_to_remove:
            try:
                # Zoek laag in project
                layers = self.project.mapLayersByName(layername)
                if not layers:
                    continue

                # Zoek laag in legenda
                layer_node = g.findLayer(layers[0])
                if not layer_node:
                    continue

                # Kloon en pas aan
                cloned_node = layer_node.clone()
                cloned_node.setUseLayerName(False)
                cloned_node.setName('')  # Verberg naam in legenda
                
                # Plaats bovenaan en verwijder origineel
                g.insertChildNode(0, cloned_node)
                g.removeChildNode(layer_node)

            except Exception as e:
                if self.DEBUG:
                    print(f'Fout bij verwerken laag {layername}: {str(e)}')

        # 3. Verwerk ondergrond-groep
        layers_to_remove = ['Topografische kaart', 'Luchtfoto']
        try:
            ondergrond_group = g.findGroup('Ondergrond')
            if not ondergrond_group:
                return

            # Verwijder specifieke lagen uit groep
            for child in ondergrond_group.children():
                if child.name() in layers_to_remove:
                    ondergrond_group.removeChildNode(child)

            # Kloon en herplaats groep
            cloned_group = ondergrond_group.clone()
            g.insertChildNode(0, cloned_group)
            g.removeChildNode(ondergrond_group)

        except Exception as e:
            if self.DEBUG:
                print(f'Fout bij verwerken ondergrond-groep: {str(e)}')

    def extentChange(self):
        """
        Reageert op kaartextent wijzigingen door de tabel te updaten of te initialiseren.

        Werking:
            1. Verwerkt pending GUI events voor betere responsiviteit
            2. Initialiseert PrintomgevingTabel indien nog niet bestaat
            3. Koppelt layoutDesignerClosed signaal aan resetfunctie
            4. Genereert/update tabel met huidige kaartextent

        Vereisten:
            - self.tbl: QgsLayoutItemManualTable object
            - self.newcomp: QgsPrintLayout object
            - self.kaart: QgsLayoutItemMap object
            - self.printomgeving_dialog: Hoofddialoog object
            - .printomgevingtabel.PrintomgevingTabel: Tabel generator klasse
        """
        try:
            # Verwerk pending GUI events
            # QApplication.processEvents()

            # Lazy initialization van tabel generator
            if self.at is None:
                from .printomgevingtabel import PrintomgevingTabel
                self.at = PrintomgevingTabel(
                    tbl=self.tbl,
                    newcomp=self.newcomp,
                    map=self.kaart,
                    printomgeving_dialog=self.printomgeving_dialog
                )
                iface.layoutDesignerClosed.connect(self.resetprintomgeving)

            # Update tabel met huidige extent
            current_extent = self.kaart.extent()
            self.at.create_table(current_extent)

        except ImportError as e:
            iface.messageBar().pushMessage(
                "Kritieke fout",
                f"Kan tabelmodule niet importeren: {str(e)}",
                level=Qgis.Critical
            )
        except AttributeError as e:
            iface.messageBar().pushMessage(
                "Configuratiefout",
                f"Ontbrekend attribuut: {str(e)}",
                level=Qgis.Critical
            )
        except Exception as e:
            iface.messageBar().pushMessage(
                "Onverwachte fout",
                f"Updaten van data aan de hand van kaartwijziging mislukt: {str(e)}",
                level=Qgis.Critical
            )
    
    def resetprintomgeving(self):
        """
        Reset de printomgeving door:
        1. Tabelgenerator te deregisteren (self.at = None)
        2. Eventuele signaalkoppelingen te verwijderen

        Veiligheid:
        - Werkt ook als self.at niet bestaat
        - Beveiligd tegen niet-bestaan van signaalkoppeling
        - Voorkomt 'NoneType' errors
        """
        try:
            # Reset tabelgenerator
            self.at = None
            
            # Probeer signaal te deregisteren
            try:
                iface.layoutDesignerClosed.disconnect(self.resetprintomgeving)
            except (TypeError, RuntimeError) as e:
                if self.DEBUG:
                    print(f"Signaal deregistratie fout: {str(e)}")
                    
        except Exception as e:
            if self.DEBUG:
                print(f"Onverwachte reset fout: {str(e)}")
    
    def addarchieftablemilieu(self):
        """
        Initialiseert en voegt een milieu-specifieke archieftabel toe aan de lay-out 
        indien de 'Voeg archieftabel toe' checkbox is aangevinkt.

        Werking:
            1. Verwerkt GUI events voor betere responsiviteit
            2. Controleert checkbox status
            3. Initialiseert ArchiefTabelM met benodigde parameters

        Vereisten:
            - self.newcomp: QgsPrintLayout object
            - self.kaart: QgsLayoutItemMap object
            - self.printomgeving_dialog: Hoofddialoog met addArchiefcb checkbox
            - .archieftabelMilieu.ArchiefTabelM: Speciale tabel klasse voor milieu
        """
        try:
            # Zorg voor GUI-responsiviteit
            QApplication.processEvents()

            # Controleer checkbox status
            if not self.printomgeving_dialog.addArchiefcb.isChecked():
                return

            # Lazy import om circulaire imports te voorkomen
            from .archieftabelMilieu import ArchiefTabelM

            # Initialiseer en behoud referentie indien nodig
            atm = ArchiefTabelM(
                newcomp=self.newcomp,
                map=self.kaart,
                printomgeving_dialog=self.printomgeving_dialog
            )
            
            # Bewaar referentie indien nodig voor latere toegang
            # self.atm = atm  # Uncomment indien nodig

        except ImportError as e:
            iface.messageBar().pushMessage(
                "Kritieke fout", 
                f"Kan archieftabel module niet laden: {str(e)}", 
                level=Qgis.Critical
            )
        except AttributeError as e:
            iface.messageBar().pushMessage(
                "Configuratiefout",
                f"Ontbrekend UI-element: {str(e)}",
                level=Qgis.Critical
            )
        except Exception as e:
            iface.messageBar().pushMessage(
                "Onverwachte fout",
                f"Archieftabel toevoegen mislukt: {str(e)}",
                level=Qgis.Critical
            )
