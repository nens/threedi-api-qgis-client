from typing import Dict, List, Tuple
from qgis.core import (
    QgsProcessingFeatureSource,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsWkbTypes,
)

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterField,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
)

from threedi_models_and_simulations.processing.label_dwf import label_dwf
from threedi_models_and_simulations.processing.label_rain_zones import label_rain_zones
from threedi_models_and_simulations.settings import SettingsDialog


class MockIFace:
    """Used to replace iface when instantiating a SettingsDialog in a processing context"""
    def messageBar(message):
        pass


def get_name_wkt_pairs(
        features: QgsProcessingFeatureSource,
        source_crs: QgsCoordinateReferenceSystem,
        name_field: str,
        context
) -> List[Tuple[str, str]]:
    """
    Returns a {name: wkt} dict (wkt = geometry of the feature in Well-Known Text format)
    Transforms the input geometry to WGS84
    Converts curve geometry to linear geometry
    Converts single part to multipart
    Adds postfix to name if geometry is multipart
    """
    result = list()

    # Define CRS transformation: source to WGS84
    target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    transform = QgsCoordinateTransform(source_crs, target_crs, context.transformContext())

    # Iterate over features
    for feature in features.getFeatures():
        name = feature[name_field]
        geom = feature.geometry()

        # Convert curves to linear
        geom = geom.convertToType(QgsWkbTypes.PolygonGeometry, True)
        for i, geom_part in enumerate(geom.parts()):
            geom_part.transform(transform)
            wkt = geom_part.asWkt()
            if i > 0:
                name = name + f" {i + 1}"
            result.append((name, wkt))
    return result


class SimulateWithRainZonesAlgorithm(QgsProcessingAlgorithm):
    """
    Creates a simulation from a template, adds rain zones to the rain event(s) and add the simulation to the queue
    """

    SIMULATION_TEMPLATE_ID = "SIMULATION_TEMPLATE_ID"
    SIMULATION_NAME = "SIMULATION_NAME"
    POLYGON_LAYER = "POLYGON_LAYER"
    POLYGON_NAME_FIELD = "POLYGON_NAME_FIELD"

    def createInstance(self):
        return SimulateWithRainZonesAlgorithm()

    def name(self):
        return 'threedi_simulate_with_rain_zones'

    def displayName(self):
        return 'BETA Simulate with rain zones'

    def group(self):
        return "Simulate"

    def groupId(self):
        return "simulate"

    def shortHelpString(self):
        return  f"""
            <p>Creates a simulation from a template, adds rain zones to the rain event(s) and add the simulation to the queue</p>
            <p>Only constant rain events and time series rain events are supported. The simulation template must contain at least one such rain event.</p>
            <p>The simulation is owned by the same organisation that owns the simulation from which the template was made</p>
            <p><i>Note: in the future, this functionality will be integrated into the "New simulation" wizard.</i></p>
            <h3>Parameters</h3>
            <h4>Simulation template ID</h4>
            <p>ID of the simulation template you want to use. Use the simulation wizard to create the simulation you want to run, save it as a template, and copy the simulation template ID to use in this processing algorithm.</p>
            <h4>Simulation name</h4>
            <p>Name of the simulation</p>
            <h4>Rain zones</h4>
            <p>A layer that contains the polygons that you want to use as rain zones.</p>
            <h4>Name field</h4>
            <p>Field in the rain zones layer that contains unique names</p>
            """

    def initAlgorithm(self, config=None):
        """Define input and output parameters."""
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIMULATION_TEMPLATE_ID,
                "Simulation template ID",
                type=QgsProcessingParameterNumber.Integer
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.SIMULATION_NAME,
                "Simulation name"
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POLYGON_LAYER,
                'Rain zones',
                [QgsProcessing.TypeVectorPolygon],

            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.POLYGON_NAME_FIELD,
                "Name field",
                parentLayerParameterName=self.POLYGON_LAYER,
                type=QgsProcessingParameterField.String
            )
        )


    def processAlgorithm(self, parameters, context, feedback):
        """
        Process the algorithm.
        """
        simulation_template_id = self.parameterAsInt(parameters, self.SIMULATION_TEMPLATE_ID, context)
        simulation_name = self.parameterAsString(parameters, self.SIMULATION_NAME, context)
        polygon_feature_source = self.parameterAsSource(parameters, self.POLYGON_LAYER, context)
        polygon_feature_layer = self.parameterAsVectorLayer(parameters, self.POLYGON_LAYER, context)
        polygon_name_field = self.parameterAsString(parameters, self.POLYGON_NAME_FIELD, context)

        polygon_feature_layer.crs()

        name_wkt_dict = get_name_wkt_pairs(
            features=polygon_feature_source,
            source_crs=polygon_feature_layer.crs(),
            name_field=polygon_name_field,
            context=context
        )

        settings_dialog = SettingsDialog(MockIFace())
        api_host = settings_dialog.api_url
        _, api_key = settings_dialog.get_3di_auth()

        label_rain_zones(
            api_host,
            api_key,
            simulation_template_id=simulation_template_id,
            simulation_name=simulation_name,
            zones=name_wkt_dict,
            feedback=feedback
        )

        return {}


class SimulateWithDWFLabellingAlgorithm(QgsProcessingAlgorithm):
    """
    Creates a simulation from a template, adds rain zones to the rain event(s) and add the simulation to the queue
    """

    SIMULATION_TEMPLATE_ID = "SIMULATION_TEMPLATE_ID"
    SIMULATION_NAME = "SIMULATION_NAME"

    def createInstance(self):
        return SimulateWithDWFLabellingAlgorithm()

    def name(self):
        return 'threedi_simulate_with_dwf_labelling'

    def displayName(self):
        return 'BETA Simulate with DWF labelling'

    def group(self):
        return "Simulate"

    def groupId(self):
        return "simulate"

    def shortHelpString(self):
        return  f"""
            <p>Creates a simulation from a template, labels the dry weather flow and adds the simulation to the queue</p>
            <p>The simulation template must contain dry weather flow.</p>
            <p>The simulation is owned by the same organisation that owns the simulation from which the template was made</p>
            <p><i>Note: in the future, this functionality will be integrated into the "New simulation" wizard.</i></p>
            <h3>Parameters</h3>
            <h4>Simulation template ID</h4>
            <p>ID of the simulation template you want to use. Use the simulation wizard to create the simulation you want to run, save it as a template, and copy the simulation template ID to use in this processing algorithm.</p>
            <h4>Simulation name</h4>
            <p>Name of the simulation</p>
            """

    def initAlgorithm(self, config=None):
        """Define input and output parameters."""
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIMULATION_TEMPLATE_ID,
                "Simulation template ID",
                type=QgsProcessingParameterNumber.Integer
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.SIMULATION_NAME,
                "Simulation name"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Process the algorithm.
        """
        simulation_template_id = self.parameterAsInt(parameters, self.SIMULATION_TEMPLATE_ID, context)
        simulation_name = self.parameterAsString(parameters, self.SIMULATION_NAME, context)

        settings_dialog = SettingsDialog(MockIFace())
        api_host = settings_dialog.api_url
        _, api_key = settings_dialog.get_3di_auth()

        label_dwf(
            api_host,
            api_key,
            simulation_template_id=simulation_template_id,
            simulation_name=simulation_name,
            feedback=feedback
        )

        return {}


