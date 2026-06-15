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
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFeatureSink,
    QgsRasterBandStats,
    QgsRasterLayer,
    QgsProcessingParameterVectorLayer,
)
import processing
import re
import os
from ..core.field_mappings import build_field_mappings_ikp
from qgis.PyQt.QtGui import QIcon


class IKPUdaraAlgorithm(QgsProcessingAlgorithm):
    IKP = "Udara"
    # Parameters
    GRID_KPKU = "GRID_KPKU"
    PM25 = "PM25"
    IPS = "IPS"  # Indeks Proyeksi Suhu

    # Output
    OUTPUT = "OUTPUT"
    OUTPUT_POLIGON = "OUTPUT_POLIGON"

    # Constant
    bakumutu_pm25 = 15  # 15µg/m^3 sesuai standar PP22/2021

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.GRID_KPKU,
                self.tr(
                    'Grid JLH Udara [Dengan Kolom "PKU_YY" dan YY adalah dua '
                    "digit terakhir dari tahun (contoh : PKU_24)]"
                ),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.IPS,
                self.tr('Indeks Proyeksi Suhu [Dengan Kolom "SKOR"]'),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.PM25,
                self.tr("Raster PM 2.5 [Dengan satuan kg m-3]"),
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_POLIGON,
                self.tr('IKP Udara Poligon [kolom "IKPUDR"]'),
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr('IKP Udara Grid [kolom "IKPUDR"]')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # Parameters
        grid_src = self.parameterAsVectorLayer(
            parameters, self.GRID_KPKU, context
        )
        pm25_raster = self.parameterAsRasterLayer(
            parameters, self.PM25, context
        )
        ips = self.parameterAsVectorLayer(parameters, self.IPS, context)
        pku = self.parameterAsVectorLayer(
            parameters, self.GRID_KPKU, context
        )
        pku_field = next(
            (
                f.name()
                for f in pku.fields()
                if re.match(r"PKU_\d+", f.name())
            ),
            None,
        )
        year = int(re.search(r"PKU_(\d+)", pku_field).group(1))
        pl_year = str(2000 + year)

        # Standarize PM25 raster
        # 1. Reclassify to Equal Interval
        # Get raster statistics
        provider = pm25_raster.dataProvider()
        stats = provider.bandStatistics(
            1, QgsRasterBandStats.All, pm25_raster.extent(), 0
        )

        min_val = stats.minimumValue
        max_val = stats.maximumValue

        # Define number of classes
        n_classes = 11
        interval = (max_val - min_val) / n_classes

        # Build reclass table: [low, high, new_value]
        reclass_table = []
        mid_table = []
        for i in range(n_classes):
            low = min_val + i * interval
            high = min_val + (i + 1) * interval
            new_value = i + 1
            mid_value = ((low + high) / 2) * 1000000000
            reclass_table.extend([low, high, new_value])
            mid_table.append({f"{new_value}": mid_value})

        # Run reclassify by table
        reclass_pm25 = processing.run(
            "qgis:reclassifybytable",
            {
                "INPUT_RASTER": pm25_raster,
                "RASTER_BAND": 1,
                "TABLE": reclass_table,
                "NO_DATA": -9999,
                "RANGE_BOUNDARIES": 0,  # 0 = min < x ≤ max
                "NODATA_FOR_MISSING": True,
                "DATA_TYPE": 5,  # Float32
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback.pushInfo(
                "Finish Reclassify PM2.5 Raster Data"
            ),
        )["OUTPUT"]

        reclass_pm25 = QgsRasterLayer(reclass_pm25, "reclass_pm25")

        # 2. Polygonize the result
        polygonize_pm25 = processing.run(
            "gdal:polygonize",
            {
                "INPUT": reclass_pm25,
                "BAND": 1,
                "FIELD": "gridcode",
                "EIGHT_CONNECTEDNESS": False,
                "EXTRA": "",
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback.pushInfo(
                "Finish Polygonize Reclassified PM2.5"
            ),
        )["OUTPUT"]

        # 3. Input mid value based on gridcode
        case_when_expr = "CASE\n"
        for item in mid_table:
            for key, val in item.items():
                case_when_expr += (
                    f'    WHEN "gridcode" = {key} THEN {val}\n'
                )
        case_when_expr += "END"
        mid_pm25 = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": polygonize_pm25,
                "FIELD_NAME": "NT_PM25",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 10,
                "NEW_FIELD": True,
                "FORMULA": case_when_expr,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback.pushInfo(
                "Get Median Value for Every Class in PM2.5 Raster"
            ),
        )["OUTPUT"]

        # 3. Menghitung IP (Konsentrasi PM2.5 / Baku mutu PM2.5)
        ip_pm25 = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": mid_pm25,
                "FIELD_NAME": "IP",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 10,
                "NEW_FIELD": True,
                "FORMULA": f'"NT_PM25"/{self.bakumutu_pm25}',
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback.pushInfo(
                "Selesai Menghitung IP untuk PM2.5"
            ),
        )["OUTPUT"]

        # 4. Menghitung Indeks PM 2.5
        indeks_pm25 = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": ip_pm25,
                "FIELD_NAME": "PM25",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 3,
                "NEW_FIELD": True,
                "FORMULA": '100-((50/0.9) * ("IP" - 0.1))',
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback.pushInfo("Selesai menghitung IKU_PM2.5"),
        )["OUTPUT"]

        idw_indeks_pm25 = processing.run(
            "gdal:gridinversedistance",
            {
                "INPUT": indeks_pm25,
                "Z_FIELD": "PM25",  # Field to interpolate
                "POWER": 2.0,  # IDW power parameter (p)
                "SMOOTHING": 0.0,  # Optional smoothing factor
                "RADIUS_1": 0.0,  # Search radius X (0 = auto)
                "RADIUS_2": 0.0,  # Search radius Y (0 = auto)
                "ANGLE": 0.0,  # Angle for anisotropy (deg)
                "MIN_POINTS": 0,  # Minimum points to use
                "MAX_POINTS": 0,  # 0 = unlimited
                "NODATA": None,  # NoData value
                "OPTIONS": "",  # Additional GDAL options
                "DATA_TYPE": 5,  # Float32
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,  # Output GeoTIFF
                "OUTPUT_EXTENT": None,  # Optional custom extent
                "OUTPUT_SIZE": 1000,  # Raster width/height in pixels
            },
        )["OUTPUT"]

        feedback.pushInfo("Selesai Interpolasi IKU_PM2.5")

        # Zonal Stat
        zon_stat_indeks_pm25 = processing.run(
            "qgis:zonalstatisticsfb",
            {
                "INPUT": grid_src,
                "INPUT_RASTER": idw_indeks_pm25,
                "RASTER_BAND": 1,
                "COLUMN_PREFIX": "idw_",
                "STATISTICS": [2],
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        zon_stat_indeks_pm25_renamed = processing.run(
            "qgis:renametablefield",
            {
                "INPUT": zon_stat_indeks_pm25,
                "FIELD": "idw_mean",
                "NEW_NAME": "PM25",
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # 5. Kategorisasi Indeks PM2.5
        kategori_pm25 = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": zon_stat_indeks_pm25_renamed,
                "FIELD_NAME": "SPM25",
                "FIELD_TYPE": 1,
                "NEW_FIELD": True,
                "FORMULA": """
                    CASE
                        WHEN "PM25" >= 95 THEN 5
                        WHEN "PM25" >= 85 AND "PM25" < 95 THEN 4
                        WHEN "PM25" >= 60 AND "PM25" < 85 THEN 3
                        WHEN "PM25" >= 30 AND "PM25" < 60 THEN 2
                        WHEN "PM25" < 30 THEN 1
                    END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # === IPS (Indeks Proyeksi Suhu) sudah ada pada layer input 'ips' ===
        # 1. Reclass Skor Standar (Kolom SKOR)
        reklas_ips = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": ips,
                "FIELD_NAME": "IPS",
                "FIELD_TYPE": 1,
                "NEW_FIELD": True,
                "FORMULA": """
                    CASE
                        WHEN "SKOR" = '< 0,9 C' THEN 0.8
                        WHEN "SKOR" = '0,9 - 1 C' THEN 1
                        WHEN "SKOR" = '1 - 1,1 C' THEN 1.1
                        WHEN "SKOR" = '1,1 - 1,2 C' THEN 1.2
                        WHEN "SKOR" = '> 1,2 C' THEN 1.5
                    END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # 2. Kategorisasi IPS
        kategori_ips = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": reklas_ips,
                "FIELD_NAME": "SIPS",
                "FIELD_TYPE": 1,
                "NEW_FIELD": True,
                "FORMULA": """
                    CASE
                        WHEN "IPS" <= 0.8 THEN 5
                        WHEN "IPS" > 0.8 AND "IPS" <= 1.1 THEN 4
                        WHEN "IPS" > 1.1 AND "IPS" <= 1.3 THEN 3
                        WHEN "IPS" > 1.3 AND "IPS" <= 1.5 THEN 2
                        WHEN "IPS" > 1.5 THEN 1
                    END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # === Klasifikasi JLH PKU ===
        # 1. Kategorisasi JLH PKU
        kelas_pku = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": pku,
                "FIELD_NAME": "SPKU",
                "FIELD_TYPE": 1,
                "NEW_FIELD": True,
                "FORMULA": f"""
                    CASE
                        WHEN "PKU_{year}" <= 1.8 THEN 1
                        WHEN "PKU_{year}" > 1.8 AND "PKU_{year}" <= 2.6 THEN 2
                        WHEN "PKU_{year}" > 2.6 AND "PKU_{year}" <= 3.4 THEN 3
                        WHEN "PKU_{year}" > 3.4 AND "PKU_{year}" <= 4.2 THEN 4
                        WHEN "PKU_{year}" > 4.2 THEN 5
                    END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Intersect Grid, IPS, dan IKU PM2.5
        intersect_pm25_ips = processing.run(
            "qgis:intersection",
            {
                "INPUT": kategori_pm25,
                "OVERLAY": kategori_ips,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        intersect_seluruh = processing.run(
            "qgis:intersection",
            {
                "INPUT": intersect_pm25_ips,
                "OVERLAY": kelas_pku,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Menghitung IKP Udara per Polygon
        IKP_udara_poly = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": intersect_seluruh,
                "FIELD_NAME": "IKPUDR",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 3,
                "NEW_FIELD": True,
                "FORMULA": '("SPKU"+"SIPS"+SPM25)/3',
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        IKP_udara_poly = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": IKP_udara_poly,
                "FIELD_NAME": "SIKPUDR",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 3,
                "NEW_FIELD": True,
                "FORMULA": """
                    CASE
                        WHEN "IKPUDR" <= 1.8 THEN 1
                        WHEN "IKPUDR" > 1.8 AND "IKPUDR" <= 2.6 THEN 2
                        WHEN "IKPUDR" > 2.6 AND "IKPUDR" <= 3.4 THEN 3
                        WHEN "IKPUDR" > 3.4 AND "IKPUDR" <= 4.2 THEN 4
                        WHEN "IKPUDR" > 4.2 THEN 5
                        ELSE 0
                    END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        IKP_udara_poly = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": IKP_udara_poly,
                "FIELD_NAME": "KIKPUDR",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 255,
                "NEW_FIELD": True,
                "FORMULA": """
                    CASE
                        WHEN "SIKPUDR" = 1 THEN 'Sangat Rendah'
                        WHEN "SIKPUDR" = 2 THEN 'Rendah'
                        WHEN "SIKPUDR" = 3 THEN 'Sedang'
                        WHEN "SIKPUDR" = 4 THEN 'Tinggi'
                        WHEN "SIKPUDR" = 5 THEN 'Sangat Tinggi'
                    END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        final_field_mappings = build_field_mappings_ikp(
            ikp_type=self.IKP,
            bentuk_output="Poligon",
            tahun=pl_year,
            layer=IKP_udara_poly,
        )

        IKP_udara_poly = processing.run(
            "qgis:refactorfields",
            {
                # your input layer (can be a QgsVectorLayer or file path)
                "INPUT": IKP_udara_poly,
                "FIELDS_MAPPING": final_field_mappings,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
        )["OUTPUT"]

        # Menghitung IKP Udara per Grid
        IKP_udara_grid = processing.run(
            "d3tlh:mcagrid",
            {
                "GRID": grid_src,
                "LAYER2": IKP_udara_poly,
                "LAYER2_FIELD": "IKPUDR",
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            feedback=feedback,
            context=context,
        )["OUTPUT"]

        # Klasifikasi nilai IKP_Udara
        IKP_udara_grid = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": IKP_udara_grid,
                "FIELD_NAME": "SIKPUDR",
                "FIELD_TYPE": 1,
                "NEW_FIELD": True,
                "FORMULA": """
                CASE
                    WHEN "IKPUDR" <= 1.8 THEN 1
                    WHEN "IKPUDR" > 1.8 AND "IKPUDR" <= 2.6 THEN 2
                    WHEN "IKPUDR" > 2.6 AND "IKPUDR" <= 3.4 THEN 3
                    WHEN "IKPUDR" > 3.4 AND "IKPUDR" <= 4.2 THEN 4
                    WHEN "IKPUDR" > 4.2 THEN 5
                    ELSE 0
                END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        IKP_udara_grid = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": IKP_udara_grid,
                "FIELD_NAME": "KIKPUDR",
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 255,
                "NEW_FIELD": True,
                "FORMULA": """
                    CASE
                        WHEN "SIKPUDR" = 1 THEN 'Sangat Rendah'
                        WHEN "SIKPUDR" = 2 THEN 'Rendah'
                        WHEN "SIKPUDR" = 3 THEN 'Sedang'
                        WHEN "SIKPUDR" = 4 THEN 'Tinggi'
                        WHEN "SIKPUDR" = 5 THEN 'Sangat Tinggi'
                    END
                """,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        final_field_mappings = build_field_mappings_ikp(
            ikp_type=self.IKP,
            bentuk_output="Grid",
            tahun=pl_year,
            layer=IKP_udara_grid,
        )

        IKP_udara_grid = processing.run(
            "qgis:refactorfields",
            {
                # your input layer (can be a QgsVectorLayer or file path)
                "INPUT": IKP_udara_grid,
                "FIELDS_MAPPING": final_field_mappings,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            feedback=feedback,
            context=context,
        )["OUTPUT"]

        # Output IKPUDR Poligon
        final = IKP_udara_poly

        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT_POLIGON,
            context,
            final.fields(),
            final.wkbType(),
            final.sourceCrs(),
        )

        for f in final.getFeatures():
            sink.addFeature(f)

        # Output IKPUDR Grid
        final2 = IKP_udara_grid

        sink2, dest_id2 = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            final2.fields(),
            final2.wkbType(),
            final2.sourceCrs(),
        )

        for f in final2.getFeatures():
            sink2.addFeature(f)

        return {
            self.OUTPUT_POLIGON: dest_id,
            self.OUTPUT: dest_id2,
        }

    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

    # Metadata
    def name(self):
        return "ikpudara"

    def displayName(self):
        return self.tr("IKP Udara")

    def groupId(self):
        return "E. Indeks Kemampuan Pemanfaatan (IKP)"

    def group(self):
        return self.tr(self.groupId())

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(__file__), "05 Carrying Capacity.svg"
            )
        )

    def shortHelpString(self):
        return self.tr(
            "This module calculates the Air Utilization Capability Index "
            "(IKP Udara), an indicator used to assess the capability of an "
            "area to absorb, assimilate, and neutralize air pollution "
            "loads while maintaining healthy air quality for humans and "
            "ecosystems.\n\n"
            "The methodology integrates air pollution concentration data "
            "and climate change indicators to evaluate the environmental "
            "capacity of an area in supporting sustainable air quality "
            "conditions.\n\n"
            "The resulting index can be used for environmental carrying "
            "capacity assessments, air quality management, climate "
            "adaptation planning, and D3TLH workflows.\n\n"
            "<b>Complete explanation read here: "
            "<a href='https://yayasan-lokahita.github.io/"
            "otomatisasi_d3tlh-docs/ikp/ikp_udara/'>here</a>.</b>"
        )

    def createInstance(self):
        return IKPUdaraAlgorithm()
