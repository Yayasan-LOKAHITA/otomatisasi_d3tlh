# -*- coding: utf-8 -*-

"""
/***************************************************************************
 Otomatisasi D3TLH
                                 A QGIS plugin
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

"""
/***************************************************************************
Module Name : Efisiensi Potensi Sumber Daya Alam
Description :
    Menghitung Efisiensi Potensi Sumber Daya Alam (EF) berdasarkan rasio
    kontribusi Jasa Lingkungan Hidup (JLH) terhadap kapasitas maksimum
    JLH pada suatu jenis area (Kawasan Hutan atau Pola Ruang).

    Steps:
    1. Siapkan (reproject -> World Mercator EPSG:3395, fix geometry, drop
       Z/M, convert ke MultiPolygon) kedua layer input (JLH & Area).
    2. Intersect layer JLH dengan layer Area menggunakan native:intersection.
    3. Hitung luas potongan dalam meter persegi (poly_area_m2).
    4. Hitung JLH_Max (nilai maksimum JLH) per kategori area (statistics by
       categories, MAX).
    5. Hitung total luas area murni per kategori area (area_m2) via field
       calculator + statistics by categories (SUM).
    6. Join JLH_Max dan area_m2 ke hasil intersect berdasarkan field area.
    7. Hitung EF = (poly_area_m2 * JLH) / (JLH_Max * area_m2), dengan guard
       pembagian nol.
    8. Summarize (SUM) EF per kategori area.
    9. Join hasil summarize ke layer Area asli berdasarkan field area.
Inputs:
    - Layer JLH (polygon): memiliki field JLH numerik.
    - Layer Area (polygon): Kawasan Hutan atau Pola Ruang, memiliki field
      yang mendefinisikan jenis area.
Outputs:
    - Layer Area (polygon) ber-attach field ef_<kode_jlh> hasil rekapitulasi.
Dependencies:
    - QGIS Processing Framework (native:*, qgis:*).
    - Konvensi penulisan mengikuti mine-ops-qgis-plugin.

Created by: Fadillah Azhar D.K. | Yayasan LOKAHITA
Date: 2026-08-28
***************************************************************************/
"""

import os

import processing

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingParameterFeatureSink,
    QgsFeatureSink,
    QgsCoordinateReferenceSystem,
)

# Target CRS: World Mercator
TARGET_CRS = QgsCoordinateReferenceSystem("EPSG:3395")

# Kode JLH untuk penamaan output (ef_<kode>) dan pushInfo saja
JLH_TYPE_OPTIONS = ["PHK", "PKU", "PGA", "PYA", "PGN", "PPK"]
AREA_TYPE_OPTIONS = ["Kawasan Hutan", "Pola Ruang"]


def prepare_layer(layer, target_crs, feedback=None, context=None):
    """
    Reprojects, fixes geometries, drops Z/M, and converts geometry type
    to MultiPolygon (TYPE=4).
    """
    # 1. Fix invalid geometries
    init_fix = processing.run(
        "native:fixgeometries",
        {"INPUT": layer, "OUTPUT": "memory:"},
        feedback=feedback,
        context=context,
    )["OUTPUT"]

    # 2. Reproject ke target CRS
    reprojected = processing.run(
        "native:reprojectlayer",
        {
            "INPUT": init_fix,
            "TARGET_CRS": target_crs.toWkt(),
            "OUTPUT": "memory:",
        },
        feedback=feedback,
        context=context,
    )["OUTPUT"]

    # 3. Drop Z/M values
    drop_zm = processing.run(
        "native:dropmzvalues",
        {
            "INPUT": reprojected,
            "DROP_Z_VALUES": True,
            "DROP_M_VALUES": True,
            "OUTPUT": "memory:",
        },
        feedback=feedback,
        context=context,
    )["OUTPUT"]

    # 4. Convert geometry type (TYPE=4 -> MultiPolygon)
    converted = processing.run(
        "native:convertgeometrytype",
        {"INPUT": drop_zm, "TYPE": 4, "OUTPUT": "memory:"},
        feedback=feedback,
        context=context,
    )["OUTPUT"]

    # 5. Fix invalid geometries (final)
    fixed = processing.run(
        "native:fixgeometries",
        {"INPUT": converted, "OUTPUT": "memory:"},
        feedback=feedback,
        context=context,
    )["OUTPUT"]

    if feedback:
        feedback.pushInfo(
            f"Prepared layer: {layer.name()} - reprojected to "
            f"{target_crs.authid()}, dropped Z/M, converted to MultiPolygon, "
            "and fixed geometries."
        )

    return fixed


class EfisiensiPotensiSdaAlgorithm(QgsProcessingAlgorithm):
    INPUT_JLH = "INPUT_JLH"
    INPUT_AREA = "INPUT_AREA"
    JLH_TYPE = "JLH_TYPE"
    JLH_FIELD = "JLH_FIELD"
    AREA_TYPE = "AREA_TYPE"
    AREA_FIELD = "AREA_FIELD"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_JLH,
                self.tr("Layer JLH (polygon)"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_AREA,
                self.tr("Layer Area (Kawasan Hutan / Pola Ruang, polygon)"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.JLH_TYPE,
                self.tr("Tipe JLH (untuk penamaan output)"),
                options=JLH_TYPE_OPTIONS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.JLH_FIELD,
                self.tr("Field JLH yang dihitung"),
                parentLayerParameterName=self.INPUT_JLH,
                type=QgsProcessingParameterField.Numeric,
                allowMultiple=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.AREA_TYPE,
                self.tr("Tipe Layer Area (untuk info)"),
                options=AREA_TYPE_OPTIONS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.AREA_FIELD,
                self.tr("Field yang mendefinisikan jenis area"),
                parentLayerParameterName=self.INPUT_AREA,
                type=QgsProcessingParameterField.Any,
                allowMultiple=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("Layer Area dengan EF")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # -----------------------------
        # Ambil parameter
        # -----------------------------
        jlh_type_idx = self.parameterAsEnum(
            parameters, self.JLH_TYPE, context
        )
        area_type_idx = self.parameterAsEnum(
            parameters, self.AREA_TYPE, context
        )
        jlh_code = JLH_TYPE_OPTIONS[jlh_type_idx]
        area_type_label = AREA_TYPE_OPTIONS[area_type_idx]

        jlh_layer = self.parameterAsVectorLayer(
            parameters, self.INPUT_JLH, context
        )
        area_layer = self.parameterAsVectorLayer(
            parameters, self.INPUT_AREA, context
        )
        jlh_field = self.parameterAsString(
            parameters, self.JLH_FIELD, context
        )
        area_field = self.parameterAsString(
            parameters, self.AREA_FIELD, context
        )

        # Field output dinamis: ef_<kode>
        ef_field = f"ef_{jlh_code.lower()}"

        feedback.pushInfo(
            f"Tipe JLH dipilih: {jlh_code} (output field: {ef_field})"
        )
        feedback.pushInfo(f"Tipe Layer Area: {area_type_label}")

        # -----------------------------
        # Step 1: Prepare layers
        # -----------------------------
        jlh_prep = prepare_layer(jlh_layer, TARGET_CRS, feedback, context)
        area_prep = prepare_layer(area_layer, TARGET_CRS, feedback, context)

        # -----------------------------
        # Step 2: Intersect (native:intersection)
        #   native:intersection membawa semua field dari kedua layer,
        #   sehingga tidak perlu retainfields terpisah.
        # -----------------------------
        intersect_result = processing.run(
            "native:intersection",
            {
                "INPUT": jlh_prep,
                "OVERLAY": area_prep,
                "INPUT_FIELDS": [],
                "OVERLAY_FIELDS": [],
                "OVERLAY_FIELDS_PREFIX": "",
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )
        intersect_layer = intersect_result["OUTPUT"]

        # -----------------------------
        # Step 3: Luas potongan (m2)
        # -----------------------------
        poly_area_layer = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": intersect_layer,
                "FIELD_NAME": "poly_area_m2",
                "FIELD_TYPE": 0,  # Decimal number
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "FORMULA": "area($geometry)",
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # -----------------------------
        # Step 4: JLH_Max per kategori area (statistics by categories, MAX)
        # -----------------------------
        jlh_max_layer = processing.run(
            "qgis:statisticsbycategories",
            {
                "INPUT": poly_area_layer,
                "CATEGORIES_FIELD_NAME": [area_field],
                "VALUES_FIELD_NAME": jlh_field,
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Field hasil statistics by categories bernama "max"
        jlh_max_field = "max"

        # -----------------------------
        # Step 5: Total luas area murni per kategori (m2)
        # -----------------------------
        area_m2_layer = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": area_prep,
                "FIELD_NAME": "area_m2",
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "FORMULA": "area($geometry)",
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        area_sum_layer = processing.run(
            "qgis:statisticsbycategories",
            {
                "INPUT": area_m2_layer,
                "CATEGORIES_FIELD_NAME": [area_field],
                "VALUES_FIELD_NAME": "area_m2",
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        area_sum_field = "sum"

        # -----------------------------
        # Step 6: Join JLH_Max & area_m2 ke hasil intersect
        # -----------------------------
        joined = processing.run(
            "native:joinattributestable",
            {
                "INPUT": poly_area_layer,
                "FIELD": area_field,
                "INPUT_2": jlh_max_layer,
                "FIELD_2": area_field,
                "FIELDS_TO_COPY": [jlh_max_field],
                "METHOD": 1,  # first matching feature
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        joined = processing.run(
            "native:joinattributestable",
            {
                "INPUT": joined,
                "FIELD": area_field,
                "INPUT_2": area_sum_layer,
                "FIELD_2": area_field,
                "FIELDS_TO_COPY": [area_sum_field],
                "METHOD": 1,
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # -----------------------------
        # Step 7: Hitung EF dengan guard pembagian nol
        # -----------------------------
        ef_layer = processing.run(
            "qgis:fieldcalculator",
            {
                "INPUT": joined,
                "FIELD_NAME": ef_field,
                "FIELD_TYPE": 0,
                "FIELD_LENGTH": 20,
                "FIELD_PRECISION": 6,
                "FORMULA": (
                    f'CASE WHEN ("{jlh_max_field}" * "{area_sum_field}") = 0 '
                    f"THEN 0 "
                    f'ELSE ("poly_area_m2" * "{jlh_field}") '
                    f'/ ("{jlh_max_field}" * "{area_sum_field}") '
                    f"END"
                ),
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # -----------------------------
        # Step 8: Summarize (SUM) EF per kategori area
        # -----------------------------
        ef_summary_layer = processing.run(
            "qgis:statisticsbycategories",
            {
                "INPUT": ef_layer,
                "CATEGORIES_FIELD_NAME": [area_field],
                "VALUES_FIELD_NAME": ef_field,
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        ef_sum_field = "sum"  # field hasil summary

        # -----------------------------
        # Step 9: Join summary EF ke layer Area asli (area_layer)
        #   Sink menyalin seluruh fitur + field dari layer area,
        #   lalu kita join agar field ef_<kode> tersimpan di output.
        # -----------------------------
        final_layer = processing.run(
            "native:joinattributestable",
            {
                "INPUT": area_layer,
                "FIELD": area_field,
                "INPUT_2": ef_summary_layer,
                "FIELD_2": area_field,
                "FIELDS_TO_COPY": [ef_sum_field],
                "METHOD": 1,
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Rename field hasil join menjadi ef_<kode> (pertahankan field lain)
        final_layer = processing.run(
            "native:refactorfields",
            {
                "INPUT": final_layer,
                "FIELDS_MAPPING": _build_rename_mapping(
                    final_layer, ef_sum_field, ef_field
                ),
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # -----------------------------
        # Step 10: Sink output
        # -----------------------------
        source = final_layer
        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs(),
        )

        total = 100.0 / source.featureCount() if source.featureCount() else 0
        for current, feature in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            sink.addFeature(feature, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))

        feedback.pushInfo(
            f"Selesai. Field output: {ef_field} (EF {jlh_code})."
        )

        return {self.OUTPUT: dest_id}

    def name(self):
        return "efisiensipotensisda"

    def displayName(self):
        return self.tr("Efisiensi Potensi Sumber Daya Alam")

    def group(self):
        return self.tr("D3TLH Integration")

    def groupId(self):
        return "d3tlhintegration"

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def icon(self):
        folder_path = os.path.dirname(__file__)
        icon_path = os.path.join(folder_path, "efisiensi_sda.svg")
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    def createInstance(self):
        return EfisiensiPotensiSdaAlgorithm()

    def shortHelpString(self):
        return self.tr("""
            <div class="plugin-help">
                <p><strong>Efisiensi Potensi Sumber Daya Alam (EF)</strong></p>

                <p>
                    Alat ini menghitung efisiensi potensi SDA berdasarkan rasio
                    kontribusi Jasa Lingkungan Hidup (JLH) terhadap kapasitas
                    maksimum JLH pada setiap jenis area (Kawasan Hutan atau
                    Pola Ruang).
                </p>

                <p><strong>Rumus:</strong></p>
                <ul>
                    <li>EF = (poly_area_m2 &times; JLH) / (JLH_Max &times; area_m2)</li>
                    <li>Hasil direkapitulasi (SUM) per jenis area, lalu di-join
                        ke layer area.</li>
                </ul>

                <p><strong>Proses utama:</strong></p>
                <ul>
                    <li>Reproject ke World Mercator (EPSG:3395) & validasi geometri.</li>
                    <li>Intersect layer JLH dengan layer area (native:intersection).</li>
                    <li>Hitung luas potongan (m2) dan JLH_Max per jenis area.</li>
                    <li>Hitung total luas area (area_m2) per jenis area.</li>
                    <li>Hitung EF dengan guard pembagian nol.</li>
                    <li>Summarize EF dan join ke layer area.</li>
                </ul>

                <p><strong>Input:</strong></p>
                <ul>
                    <li>Layer JLH (polygon) dengan field JLH numerik.</li>
                    <li>Layer Area (polygon) dengan field jenis area.</li>
                </ul>

                <p><strong>Output:</strong></p>
                <ul>
                    <li>Layer area ber-attach field ef_&lt;kode_jlh&gt;.</li>
                </ul>

                <p class="plugin-footer">
                    <em>Developed by Fadillah Azhar D.K.<br/>
                    Yayasan LOKAHITA</em>
                </p>
            </div>
            """)


def _build_rename_mapping(layer, old_field, new_field):
    """Build a refactorfields mapping that renames old_field -> new_field
    while preserving all other fields untouched."""
    mapping = []
    for fld in layer.fields():
        name = fld.name()
        entry = {
            "expression": f'"{name}"',
            "length": fld.length(),
            "name": name,
            "precision": fld.precision(),
            "sub_type": 0,
            "type": fld.type(),
            "type_name": fld.typeName(),
            "alias": "",
            "comment": "",
        }
        if name == old_field:
            entry["name"] = new_field
        mapping.append(entry)
    return mapping
