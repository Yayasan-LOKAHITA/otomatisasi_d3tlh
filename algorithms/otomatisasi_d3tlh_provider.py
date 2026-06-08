# -*- coding: utf-8 -*-

"""
/***************************************************************************
 OtomatisasiD3TLH
 Plugin yang membantu pengolahan D3TLH secara otomatis
                              -------------------
        begin                : 2025-08-15
        copyright            : (C) 2025 by Direktorat PDLKWS -
                               Deputi TLSDAB - Kementerian Lingkungan
                               Hidup/BPLH Republik Indonesia
        supported by         : Yayasan Lokus Bijak Hijau Lestari (LOKAHITA)
        email                : tech@yayasanlokahita.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = (
    "Fadillah Azhar Deaudin Kurniawan, "
    "Sitarani Safitri, Dini Aprilia Norvyani, "
    "Suchi Rahmadani, Fariz Rizaldy Wibowo"
)
__date__ = "2025-08-15"
__copyright__ = (
    "(C) 2025 by Direktorat PDLKWS - Deputi TLSDAB - "
    "Kementerian Lingkungan Hidup/BPLH Republik Indonesia"
)

# This will get replaced with a git SHA1 when you do a git archive
__revision__ = "$Format:%H$"

from qgis.core import QgsProcessingProvider
import os
from qgis.PyQt.QtGui import QIcon

# Algoritma lainnya
from .utils.mca_dominant_grid import UtilsMCADominantAlgorithm
from .utils.grid_sgsri import UtilsGridSGSRIAlgorithm

# Algoritma Pre-Processing
# from .preprocessing.validate_data_quality import PreprocDataValidationAlgorithm
# from .preprocessing.add_island_attribute import PreprocAddIslandAttributeAlgorithm
# from .preprocessing.schema_standardization import PreprocSchemaStandardizationAlgorithm
# from .preprocessing.road_class_standard import PreprocRoadClassStandardAlgorithm
# from .preprocessing.landcover_klhk import PreprocLandCoverKLHKAlgorithm

# Algoritma IJLH
# from .jlh.jlh_pengatur_kualitas_udara import JLHAirQualityRegulationAlgorithm
# from .jlh.jlh_penyedia_air import JLHWaterSupplyAlgorithm
# from .jlh.jlh_penyedia_pangan import JLHFoodSupplyAlgorithm
# from .jlh.jlh_penyerapan_dan_penyimpanan_karbon import JLHCarbonStorageAlgorithm
# from .jlh.jlh_pendukung_habibat_dan_kehati import JLHHabitatKehatiAlgorithm
# from .jlh.jlh_pengaturan_air import JLHWaterRegulationAlgorithm

# Model
# from .socio_ecologial.population_distribution import SocioEcoPopulationDistAlgorithm
# from .socio_ecologial.ecological_footprint import SocioEcoEcologicalFootprintAlgorithm

# Algoritma IKP
# from .ikp.ikp_lahan import IKPLahanAlgorithm
# from .ikp.ikp_kehati import IKPKehatiAlgorithm
# from .ikp.ikp_udara import IKPUdaraAlgorithm
# from .ikp.ikp_air import IKPAirAlgorithm

# Algoritma Integrasi
# from .integration.ikp_integration import IntegrationIKPAlgorithm

# Algoritma Simbologi
# from .styling.simbology import ApplyStandardStylesAlgorithm


class OtomatisasiD3TLHProvider(QgsProcessingProvider):

    def __init__(self):
        QgsProcessingProvider.__init__(self)

    def unload(self):
        pass

    def loadAlgorithms(self):
        # Algoritma lainnya
        self.addAlgorithm(UtilsMCADominantAlgorithm())
        self.addAlgorithm(UtilsGridSGSRIAlgorithm())
        # self.addAlgorithm(PreprocLandCoverKLHKAlgorithm())
        # self.addAlgorithm(PreprocRoadClassStandardAlgorithm())

        # Algoritma Pre-Processing
        # self.addAlgorithm(PreprocAddIslandAttributeAlgorithm())
        # self.addAlgorithm(PreprocDataValidationAlgorithm())
        # self.addAlgorithm(PreprocSchemaStandardizationAlgorithm())

        # Algoritma IJLH
        # self.addAlgorithm(JLHAirQualityRegulationAlgorithm())
        # self.addAlgorithm(JLHFoodSupplyAlgorithm())
        # self.addAlgorithm(JLHCarbonStorageAlgorithm())
        # self.addAlgorithm(JLHHabitatKehatiAlgorithm())
        # self.addAlgorithm(JLHWaterSupplyAlgorithm())
        # self.addAlgorithm(JLHWaterRegulationAlgorithm())

        # Model-Model Pendukung
        # self.addAlgorithm(SocioEcoEcologicalFootprintAlgorithm())
        # self.addAlgorithm(SocioEcoPopulationDistAlgorithm())

        # Algoritma IKP
        # self.addAlgorithm(IKPAirAlgorithm())
        # self.addAlgorithm(IKPKehatiAlgorithm())
        # self.addAlgorithm(IKPUdaraAlgorithm())
        # self.addAlgorithm(IKPLahanAlgorithm())

        # Algoritma Integrasi
        # self.addAlgorithm(IntegrationIKPAlgorithm())

        # Algoritma Simbology
        # self.addAlgorithm(ApplyStandardStylesAlgorithm())

    def id(self):
        """
        Returns the unique provider id, used for identifying the provider. This
        string should be a unique, short, character only string, eg "qgis" or
        "gdal". This string should not be localised.
        """
        return "d3tlh"

    def name(self):
        """
        Returns the provider name, which is used to describe the provider
        within the GUI.

        This string should be short (e.g. "Lastools") and localised.
        """
        return self.tr("Otomatisasi D3TLH")

    def icon(self):
        icon_path = os.path.join(
            os.path.dirname(__file__), "00 Main Logo.svg"
        )
        print(f"[OtomatisasiD3TLHProvider] Loading icon from: {icon_path}")
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        else:
            print("[OtomatisasiD3TLHProvider] Icon not found!")
            return super().icon()

    def longName(self):
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Lastools LIDAR tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()
