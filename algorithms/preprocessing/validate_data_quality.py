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

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsFeatureSink,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
)

import processing
import os
from qgis.PyQt.QtGui import QIcon


class PreprocDataValidationAlgorithm(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    PENUTUP_LAHAN_FIX = "PENUTUP_LAHAN_FIX"
    EKOREGION_FIX = "EKOREGION_FIX"
    PENUTUP_LAHAN = "PENUTUP_LAHAN"
    EKOREGION = "EKOREGION"
    KEE = "KEE"

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PENUTUP_LAHAN,
                self.tr("Penutup Lahan"),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.EKOREGION,
                self.tr("Ekoregion"),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.KEE,
                self.tr("KEE"),
                [QgsProcessing.TypeVectorAnyGeometry],
                optional=True,
            )
        )

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.PENUTUP_LAHAN_FIX, self.tr("Penutup Lahan Fixed")
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.EKOREGION_FIX, self.tr("Ekoregion Fixed")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # DATA INPUT
        pl = parameters["PENUTUP_LAHAN"]
        ekoregion = parameters["EKOREGION"]
        # if self.KEE != None:
        #     kee = parameters["KEE"]

        # Fix Geometry PL
        fix_geom_pl_params = {
            "INPUT": pl,
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        }
        fix_geom_eko_params = {
            "INPUT": ekoregion,
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        }
        pl_fix = processing.run(
            "qgis:fixgeometries", fix_geom_pl_params
        )["OUTPUT"]
        ekoregion_fix = processing.run(
            "qgis:fixgeometries", fix_geom_eko_params
        )["OUTPUT"]

        # Here we define the output sink and its fields and
        # geometry type. The output will be a vector layer.
        sink, dest_id = self.parameterAsSink(
            parameters,
            self.PENUTUP_LAHAN_FIX,
            context,
            pl_fix.fields(),
            pl_fix.wkbType(),
            pl_fix.sourceCrs(),
        )

        sink2, dest_id2 = self.parameterAsSink(
            parameters,
            self.EKOREGION_FIX,
            context,
            ekoregion_fix.fields(),
            ekoregion_fix.wkbType(),
            ekoregion_fix.sourceCrs(),
        )

        # Compute the number of steps to display within the progress bar and
        # get features from source
        total = (
            100.0 / pl_fix.featureCount()
            if pl_fix.featureCount()
            else 0
        )
        features = pl_fix.getFeatures()

        for current, feature in enumerate(features):
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                break

            # Add a feature in the sink
            sink.addFeature(feature, QgsFeatureSink.FastInsert)

            # Update the progress bar
            feedback.setProgress(int(current * total))

        # Write features from ekoregion_fix
        for feature in ekoregion_fix.getFeatures():
            if feedback.isCanceled():
                break
            sink2.addFeature(feature, QgsFeatureSink.FastInsert)

        return {
            self.PENUTUP_LAHAN_FIX: dest_id,
            self.EKOREGION_FIX: dest_id2,
        }

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "Pengecekan Kualitas Data"

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "B. Preprocessing"

    def shortHelpString(self):
        return self.tr(
            "This module performs basic data quality validation by "
            "repairing invalid geometries in the input layers before they "
            "are used in subsequent D3TLH processing workflows.\n\n"
            "The algorithm applies the QGIS Fix Geometries tool to the "
            "Land Cover (Penutup Lahan) and Ecoregion (Ekoregion) layers "
            "and produces cleaned outputs that are ready for spatial "
            "analysis.\n\n"
            "<b>Complete explanation read here: "
            "<a href='https://yayasan-lokahita.github.io/"
            "otomatisasi_d3tlh-docs/chk_quality/'>here</a>.</b>"
        )

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(__file__), "02 Pre-processing.svg"
            )
        )

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return PreprocDataValidationAlgorithm()
