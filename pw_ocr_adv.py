# -*- coding: utf-8 -*-

from PyQt5.QtCore import QCoreApplication
from qgis.utils import iface
from osgeo import gdal
import os
import sys
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterField,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterEnum,
                       QgsFeatureRequest,
                       QgsSpatialIndex,
                       QgsVectorLayer,
                       QgsPointXY,
                       QgsFeature,
                       QgsGeometry,
                       QgsProject
                       )
import processing

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract
from pytesseract import Output

'''Attention! Attention! All personel! You have to set path to your tesseract installation directory!'''
pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'


class PW_OCR_Advanced_Algorithm(QgsProcessingAlgorithm):
    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT = 'INPUT'
    RASTER_INPUT = 'RASTER INPUT'
    FIELD = 'FIELD'
    CONF_FIELD = 'CONF FIELD'
    ALL_ACTIVE_RASTERS = 'ALL ACTIVE RASTERS'
    PSM = 'PSM'
    OEM = 'OEM'
    ZERO_CONF = 'ZERO CONF'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PW_OCR_Advanced_Algorithm()

    def name(self):
        return 'pw_ocr_adv'

    def displayName(self):
        return self.tr('PW OCR ADVANCED')

    def group(self):
        return self.tr('PW')

    def groupId(self):
        return 'pw'

    def shortHelpString(self):
        help = """This algorithm recognizes text from raster images inside input polygon features and saves as attribute value of output layer.\
        <hr>
        <b>Input polygon layer</b>\
        <br>The features used to recognize text inside them.\
        <br><br><b>Text output field</b>\
        <br>The field in the input table in which the recognized text will be add.\
        <br><br><b>Confidence output field</b>\
        <br>The field in the input table in which the text recognition confidence will be add. Confidence is saved in the list; one value for each word.\
        <br><br><b>Run for all raster layers</b>\
        <br>The algorithm will recognize text from all active raster layers, if checked.\
        <br><br><b>Input raster layer</b>\
        <br>If above checkbox unchecked, the algorithm will recognize text only from this raster layer.\
        <br>In case of multiband raster images, the only first band will be used.\
        <br><br><b>Page Segmentation Mode</b>\
        <br><i>Tesseract</i> Page Segmentation Mode.\
        <br><br><b>OCR Engine Model</b>\
        <br><i>Tesseract</i> OCR Engine Model.\
        <br><br><b>Add words recognized with zero confidence</b>\
        <br>If there are some words recognized with zero confidence, they will be add too.\
        <br><br><b>Output layer</b>\
        <br>Location of the output layer with filled text attribute.\
        """
        return self.tr(help)

    def initAlgorithm(self, config=None):

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input polygon layer'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD,
                self.tr('Text output field'),
                parentLayerParameterName = self.INPUT,
                type = QgsProcessingParameterField.DataType.String
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.CONF_FIELD,
                self.tr('Confidence output field'),
                parentLayerParameterName = self.INPUT,
                type = QgsProcessingParameterField.DataType.String,
                optional = True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ALL_ACTIVE_RASTERS,
                self.tr('Run for all raster layers')
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.RASTER_INPUT,
                self.tr('Input raster layer'),
                optional = True,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PSM,
                self.tr('Page Segmentation Mode'),
                options = [
                    'Orientation and script detection (OSD) only.',
                    'Automatic page segmentation with OSD.',
                    'Automatic page segmentation, but no OSD, or OCR.',
                    'Fully automatic page segmentation, but no OSD. (Default if no config)',
                    'Assume a single column of text of variable sizes.',
                    'Assume a single uniform block of vertically aligned text.',
                    'Assume a single uniform block of text.',
                    'Treat the image as a single text line.',
                    'Treat the image as a single word.',
                    'Treat the image as a single word in a circle.',
                    'Treat the image as a single character.',
                    'Sparse text. Find as much text as possible in no particular order.',
                    'Sparse text with OSD.',
                    'Raw line. Treat the image as a single text line, bypassing hacks that are Tesseract-specific.'
                ],
                defaultValue = 3
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OEM,
                self.tr('OCR Engine Model'),
                options = [
                    'Legacy Tesseract',
                    'LSTM',
                    '2',
                    '3'
                ],
                defaultValue = 1
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ZERO_CONF,
                self.tr('Add words recognized with zero confidence'),
                True
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        self.source_layer = self.parameterAsLayer(
            parameters,
            self.INPUT,
            context
        )
        self.feature_source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )
        raster_lyr = self.parameterAsRasterLayer(
            parameters,
            self.RASTER_INPUT,
            context
        )
        all_rasters = self.parameterAsBool(
            parameters,
            self.ALL_ACTIVE_RASTERS,
            context
        )
        temp_path = self.parameterAsString(
            parameters,
            '',
            context
        )
        self.dest_field = self.parameterAsString(
            parameters,
            self.FIELD,
            context
        )
        self.conf_field = self.parameterAsString(
            parameters,
            self.CONF_FIELD,
            context
        )
        psm = self.parameterAsInt(
            parameters,
            'PSM',
            context
        )
        oem = self.parameterAsInt(
            parameters,
            'OEM',
            context
        )
        self.zero_conf = self.parameterAsBool(
            parameters,
            self.ZERO_CONF,
            context
        )
        (self.sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            self.feature_source.fields(),
            self.feature_source.wkbType(),
            self.feature_source.sourceCrs()
        )

        if self.source_layer == None:
            list = QgsProject.instance().mapLayersByName(self.feature_source.sourceName())
            for lyr in list:
                if self.feature_source.sourceCrs() == lyr.sourceCrs():
                    self.source_layer = lyr
                    
    
        if self.feature_source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        if raster_lyr is None and not all_rasters:
            feedback.pushInfo('\nNo raster layer selected!\n')
            raise QgsProcessingException(self.invalidSourceError(parameters, self.RASTER_INPUT))
        
        '''here is tesseract config string'''
        self.config = '--psm '+str(psm)+' --oem '+str(oem)
        feedback.pushInfo('TESSERACT CONFIG: ' + self.config)
        
        self.conf_treshold = 0
        if self.zero_conf:
            self.conf_treshold = -1
        else:
            self.conf_treshold = 0

        features = self.feature_source.getFeatures(QgsFeatureRequest())

        self.index = QgsSpatialIndex()
        for feat in features:
            self.index.insertFeature(feat)

        feedback.pushInfo('\nprocessing time calculating...\n')
        n=[]
        if not all_rasters and raster_lyr:
            n = self.index.intersects(raster_lyr.extent())
        else:
            for layer in iface.mapCanvas().layers():
                if layer.type() == 1 :
                    n = n + self.index.intersects(layer.extent())
        self.total = len(n)
        self.actual = 0
        if self.total>0: feedback.setProgress(self.actual/self.total*100)

                    
        if not all_rasters:
            self.OnThisRaster(feedback, raster_lyr)
        else:
            for layer in iface.mapCanvas().layers():
                if feedback.isCanceled(): break
                if layer.type() == 1 :
                    self.OnThisRaster(feedback, layer)
        
        return {self.OUTPUT: dest_id}
        
    def OnThisRaster(self, feedback, Raster_lyr):

        idsList = self.index.intersects(Raster_lyr.extent())
        if idsList and len(idsList)>0:
            feedback.pushCommandInfo('\nComputing image ' + str(Raster_lyr.name()) + '.\n')
            data = pytesseract.image_to_data(Raster_lyr.source(), lang='pol', config=self.config, output_type=Output.DICT)
            text = data['text']
            table_of_words=[]
            for i in range (0,len(text),1):
                pix_centroid_left=data['left'][i]+data['width'][i]/2
                pix_centroid_top=data['top'][i]+data['height'][i]/2
                crs_point = self.PixelCoordsToCRSPoint(feedback, Raster_lyr, pix_centroid_left, pix_centroid_top)
                element = [crs_point,data['text'][i],data['conf'][i]]
                table_of_words.append(element)
            for id in idsList:
                for feat in self.feature_source.getFeatures(QgsFeatureRequest()):
                    if feedback.isCanceled(): break
                    if int(feat.id()) == id:
                        self.OnThisFeature(feedback, feat, table_of_words)
                        break
        else:
            feedback.pushCommandInfo('\nImage ' + str(Raster_lyr.name()) + ' does not intersect any feature.\n')
        
    def OnThisFeature(self, feedback, feat, table_of_words):
        chosen_elements=[]
        for element in table_of_words:
            if feat.geometry().contains(element[0]):
                chosen_elements.append(element)
        chosen_elements.sort(key = self.sortByX)
        strings = []
        conf = []
        if chosen_elements:
            for element in chosen_elements:
                if int(element[2])>self.conf_treshold: strings.append(element[1])
                if int(element[2])>-1:conf.append(int(element[2]))
        string = ' '.join(strings)
        
        feat[self.dest_field] = string
        if self.conf_field: feat[self.conf_field] = str(conf)#.encode('utf8')#.decode('CP1250')
        
        self.actual = self.actual + 1
        feedback.setProgress(self.actual/self.total*100)
        feedback.setProgressText(str(self.actual)+'/'+str(self.total) + '       ' +'id:  ' + str(feat.id()))
        feedback.pushCommandInfo('\n'+string + '\nConfidence:'+str(conf)+'\n')
        self.sink.addFeature(feat, QgsFeatureSink.FastInsert)

    def sortByX(self,element):
        return element[0].x()
        
    def PixelCoordsToCRSPoint(self, feedback, lyr, left, top):
        rect= lyr.extent()
        x = rect.xMinimum() + lyr.rasterUnitsPerPixelY()*left
        y = rect.yMaximum() - lyr.rasterUnitsPerPixelX()*top
        point = QgsPointXY(x,y)

        return point