from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterFile,
    QgsProcessingParameterFeatureSink,
    QgsVectorLayerJoinInfo,
    QgsProcessingMultiStepFeedback,
    QgsProcessingUtils,
    QgsField,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeatureSink,
    QgsVectorLayer
)
from qgis import processing

class IntegrationD3TLHAlgorithm(QgsProcessingAlgorithm):
    # Algorithm constants
    INPUT_IPRLH = 'IPRLH'
    INPUT_IKPLH = 'IKPLH'
    INPUT_CSV = 'CSV'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_IPRLH,
                "IPRLH Layer (Vector)",
                [QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorAnyGeometry]
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_IKPLH,
                "IKPLH Layer (Vector)",
                [QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorAnyGeometry]
            )
        )

        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_CSV,
                "CSV File (must have 'Provinsi' and 'IPRLH' columns)",
                extension='csv'
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Output (Union + Average)",
                QgsProcessing.TypeVectorPolygon
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        feedback = QgsProcessingMultiStepFeedback(4, feedback)

        # Step 1: Load parameters
        iprlh_layer = self.parameterAsVectorLayer(parameters, self.INPUT_IPRLH, context)
        ikplh_layer = self.parameterAsVectorLayer(parameters, self.INPUT_IKPLH, context)
        csv_file = self.parameterAsFile(parameters, self.INPUT_CSV, context)

        # Step 2: Load CSV as vector
        csv_uri = f"file:///{csv_file}?delimiter=,&xField=&yField=&crs=EPSG:4326"
        csv_layer = QgsVectorLayer(csv_uri, "csv_data", "delimitedtext")
        if not csv_layer.isValid():
            raise QgsProcessingException("Failed to load CSV file.")

        feedback.pushInfo("CSV successfully loaded.")

        # Step 3: Join CSV to IPRLH vector based on 'Provinsi'
        join_info = QgsVectorLayerJoinInfo()
        join_info.setJoinLayer(csv_layer)
        join_info.setJoinFieldName('Provinsi')
        join_info.setTargetFieldName('Provinsi')
        join_info.setJoinLayerId(csv_layer.id())
        join_info.setUsingMemoryCache(True)
        join_info.setPrefix('csv_')
        iprlh_layer.addJoin(join_info)

        feedback.pushInfo("Join completed between IPRLH and CSV.")

        # Step 4: Union IPRLH + IKPLH
        union_result = processing.run(
            "native:union",
            {
                'INPUT': iprlh_layer,
                'OVERLAY': ikplh_layer,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            },
            context=context,
            feedback=feedback
        )['OUTPUT']

        feedback.pushInfo("Union completed.")

        # Step 5: Calculate average ( (IPRLH + IKPLH) / 2 )
        calc_result = processing.run(
            "native:fieldcalculator",
            {
                'INPUT': union_result,
                'FIELD_NAME': 'AVG_INDEX',
                'FIELD_TYPE': 0,  # Float
                'FIELD_LENGTH': 10,
                'FIELD_PRECISION': 3,
                'FORMULA': '("csv_IPRLH" + "IKPLH") / 2',
                'OUTPUT': parameters[self.OUTPUT]
            },
            context=context,
            feedback=feedback
        )

        feedback.pushInfo("Average field calculated.")

        return {self.OUTPUT: calc_result['OUTPUT']}

    def name(self):
        return "d3tlhintegration"

    def displayName(self):
        return "Integrasi IKPLH dan IPRLH (D3TLH)"

    def group(self):
        return "F. Integration"

    def groupId(self):
        return "F. Integration"

    def shortHelpString(self):
        return (
            "This tool joins a CSV (by Provinsi) to the IPRLH layer, then unions it "
            "with IKPLH, and calculates the average index: (IPRLH + IKPLH)/2."
    )

    def createInstance(self):
        return IntegrationD3TLHAlgorithm()
