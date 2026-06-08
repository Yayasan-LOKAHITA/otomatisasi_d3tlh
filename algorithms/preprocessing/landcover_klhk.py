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

import os
import csv
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterBoolean,
    QgsProcessingException,
    QgsProcessingAlgorithm,
)
from qgis.PyQt.QtGui import QIcon


class PreprocLandCoverKLHKAlgorithm(QgsProcessingAlgorithm):
    """
    Klasifikasikan layer menjadi Penutup Lahan (PL) atau Kawasan Hutan
    (kwshutan)
    memakai lookup CSV yang DIBUNDEL (tanpa input CSV dari user).
    Fitur:
      - Autodeteksi delimiter (; , \t |)
      - Header case-insensitive
      - Pencocokan ID numerik fleksibel (leading zero)
    """

    # ----- keys -----
    INPUT = "INPUT"
    CLASS_TYPE = "CLASS_TYPE"  # 0=PL, 1=Kawasan Hutan
    INPUT_ID_FIELD = "INPUT_ID_FIELD"
    FORCE_ID_TEXT = "FORCE_ID_TEXT"
    FLEX_NUMERIC_ID = "FLEX_NUMERIC_ID"
    OUTPUT = "OUTPUT"

    # ----- constants -----
    CLASS_OPTIONS = ["Penutup Lahan (PL)", "Kawasan Hutan (kwshutan)"]
    OUT_FIELD_PL = "PL"
    OUT_FIELD_KWS = "kwshutan"

    # nama file lookup default relatif ke file algoritma ini
    LOOKUP_PL_FILES = "lookup_pl.csv"
    LOOKUP_KWS_FILES = "lookup_kws.csv"

    # ----- boilerplate -----
    def tr(self, s):
        return QCoreApplication.translate("Processing", s)

    def createInstance(self):
        return PreprocLandCoverKLHKAlgorithm()

    def name(self):
        return "klasifikasituplah"

    def displayName(self):
        return self.tr(
            "Klasifikasi Penutupan Lahan & Kawasan Hutan (KLHK RI)"
        )

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return "B. Preprocessing"

    def icon(self):
        return QIcon(
            os.path.join(
                os.path.dirname(__file__), "02 Pre-processing.svg"
            )
        )

    def shortHelpString(self) -> str:
        return self.tr("""\
🇮🇩 ID:
Klasifikasikan fitur menjadi Penutup Lahan (PL) atau Kawasan Hutan (kwshutan)
via lookup CSV YANG DIBUNDEL.
• PL CSV (dibundel): header = CODE;PL
• Kawasan Hutan CSV (dibundel): header = fungsikws;kwshutan
CSV dicari otomatis di folder algoritma ini atau subfolder 'data/'. Tidak
perlu memilih file CSV.

🌍 EN:
Classify features as Land Cover (PL) or Forest Area (kwshutan) using BUNDLED
CSV lookups.
• PL headers: CODE;PL
• Forest headers: fungsikws;kwshutan
CSV files are resolved automatically beside this script or in 'data/'.
No CSV parameters.
""")

    # ----- parameters -----
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input layer"),
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CLASS_TYPE,
                self.tr(
                    "Classification type / Jenis klasifikasi"
                    "[PL / Kawasan Hutan]"
                ),
                options=self.CLASS_OPTIONS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.INPUT_ID_FIELD,
                self.tr(
                    "Select ID field on input "
                    "(e.g., PL2024_ID / fungsikws / CODE)"
                ),
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.Any,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FORCE_ID_TEXT,
                self.tr("Treat ID as text (preserve leading zeros)"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FLEX_NUMERIC_ID,
                self.tr(
                    "Match numeric IDs with or without leading zeros"
                ),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("Output Layer")
            )
        )

    # ----- utilities -----
    def _read_csv_lookup(self, csv_path, key_col, val_col):
        """
        Baca CSV jadi dict:
        - Autodeteksi delimiter (; , \\t |) via csv.Sniffer, fallback ';'
        - Header case-insensitive
        - Validasi duplikat kunci
        """
        mapping = {}
        dup_keys = set()

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(8192)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(
                    sample, delimiters=";,\t|"
                )
                reader = csv.DictReader(f, dialect=dialect)
            except csv.Error:
                reader = csv.DictReader(f, delimiter=";")

            raw_headers = reader.fieldnames or []
            norm_map = {
                (h or "").strip().lower(): (h or "").strip()
                for h in raw_headers
            }

            k_norm, v_norm = key_col.lower(), val_col.lower()
            if k_norm not in norm_map or v_norm not in norm_map:
                raise QgsProcessingException(
                    self.tr(
                        f"Header CSV tidak cocok.\n"
                        f"Ditemukan: {raw_headers}\n"
                        f"Perlu: '{key_col}' dan '{val_col}'"
                        "(case-insensitive)."
                    )
                )

            k_name, v_name = norm_map[k_norm], norm_map[v_norm]
            for row in reader:
                k_raw = row.get(k_name)
                k = "" if k_raw is None else str(k_raw).strip()
                if k in mapping:
                    dup_keys.add(k)
                mapping[k] = row.get(v_name)

        if dup_keys:
            raise QgsProcessingException(
                self.tr(
                    f"Ditemukan {len(dup_keys)} kunci duplikat pada "
                    f"'{os.path.basename(csv_path)}', "
                    f"contoh: {list(dup_keys)[:5]}"
                )
            )
        return mapping

    def _build_numeric_variants(self, key, max_len_hint):
        variants = {key}
        if key.isdigit():
            variants.add(key.lstrip("0"))
            if max_len_hint and max_len_hint > 0:
                variants.add(key.zfill(max_len_hint))
        return [v for v in variants if v != ""]

    # ----- main -----
    def processAlgorithm(self, parameters, context, feedback):
        src = self.parameterAsSource(parameters, self.INPUT, context)
        if src is None:
            raise QgsProcessingException(
                self.tr("Layer input tidak valid.")
            )

        class_type = self.parameterAsInt(
            parameters, self.CLASS_TYPE, context
        )
        id_field = self.parameterAsString(
            parameters, self.INPUT_ID_FIELD, context
        )
        force_text = self.parameterAsBool(
            parameters, self.FORCE_ID_TEXT, context
        )
        flex_numeric = self.parameterAsBool(
            parameters, self.FLEX_NUMERIC_ID, context
        )

        def load_csv_path(name: str):
            this_file = os.path.abspath(__file__)
            plugin_root = os.path.dirname(
                os.path.dirname(os.path.dirname(this_file))
            )
            data_root = os.path.join(plugin_root, "data", name)
            if data_root and os.path.isfile(data_root):
                feedback.pushInfo(
                    self.tr(f"Memuat CSV dari: {data_root}")
                )
                return data_root
            else:
                raise QgsProcessingException(
                    f"File CSV {name} tidak ditemukan: {data_root}"
                )

        # Tentukan CSV & skema
        if class_type == 0:
            out_field = self.OUT_FIELD_PL
            key_col, val_col = "CODE", "PL"
            lookup_path = load_csv_path(self.LOOKUP_PL_FILES)
            missing_msg = (
                "Lookup PL tidak ditemukan. Taruh 'lookup_pl.csv' "
                "di folder algoritma ini atau subfolder 'data/'."
            )
        else:
            out_field = self.OUT_FIELD_KWS
            key_col, val_col = "fungsikws", "kwshutan"
            lookup_path = load_csv_path(self.LOOKUP_KWS_FILES)
            missing_msg = (
                "Lookup Kawasan Hutan tidak ditemukan. Taruh 'lookup_kws.csv' "
                "di folder algoritma ini atau subfolder 'data/'."
            )

        if not lookup_path:
            raise QgsProcessingException(self.tr(missing_msg))

        lut = self._read_csv_lookup(lookup_path, key_col, val_col)
        max_key_len = max(
            (len(k) for k in lut.keys() if isinstance(k, str)),
            default=0,
        )

        # Validasi ID field
        in_fields: QgsFields = src.fields()
        if id_field not in in_fields.names():
            raise QgsProcessingException(
                self.tr(
                    f"Kolom ID '{id_field}' tidak ditemukan di layer input."
                )
            )

        # Siapkan schema output
        out_fields = QgsFields(in_fields)
        if out_fields.indexFromName(out_field) == -1:
            f = QgsField(out_field, QVariant.String)
            try:
                f.setLength(254)
            except Exception:
                pass
            out_fields.append(f)

        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            src.wkbType(),
            src.sourceCrs(),
        )
        out_idx = out_fields.indexFromName(out_field)

        # Proses fitur
        n_all = n_match = n_null = 0
        null_samples = []
        total = max(1, src.featureCount())

        for i, feat in enumerate(src.getFeatures()):
            if feedback.isCanceled():
                break

            n_all += 1
            attrs = feat.attributes()
            if len(attrs) < out_fields.count():
                attrs += [None] * (out_fields.count() - len(attrs))

            key_val = feat[id_field]
            key_norm = "" if key_val is None else str(key_val)
            if force_text:
                pass
            key_norm = key_norm.strip()

            label = lut.get(key_norm)
            if label is None and flex_numeric and key_norm:
                for v in self._build_numeric_variants(
                    key_norm, max_key_len
                ):
                    label = lut.get(v)
                    if label is not None:
                        break

            if label is None:
                n_null += 1
                if len(null_samples) < 5:
                    null_samples.append(key_norm)
            else:
                n_match += 1

            attrs[out_idx] = label

            new_f = QgsFeature(out_fields)
            new_f.setGeometry(feat.geometry())
            new_f.setAttributes(attrs)
            sink.addFeature(new_f, QgsFeatureSink.FastInsert)

            feedback.setProgress(int((i + 1) * (100.0 / total)))

        # Ringkasan
        feedback.pushInfo(self.tr("=== Klasifikasi selesai ==="))
        feedback.pushInfo(self.tr(f"Fitur diproses : {n_all}"))
        feedback.pushInfo(self.tr(f"Match          : {n_match}"))
        feedback.pushInfo(self.tr(f"Tidak match    : {n_null}"))
        if n_null:
            feedback.pushInfo(
                self.tr(
                    f"Contoh ID tidak match (maks 5): {null_samples}"
                )
            )
            feedback.pushInfo(self.tr(f"Lookup: {lookup_path}"))
            feedback.pushInfo(
                self.tr(
                    "Periksa kembali nilai ID input dan kunci pada lookup CSV."
                )
            )

        return {self.OUTPUT: dest_id}
