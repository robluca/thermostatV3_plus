# coding: latin-1 

### BEGIN LICENSE
# Copyright (c) 2016 Jpnos <jpnos@gmx.com>

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
### END LICENSE

##############################################################################
#                                                                            #
#       Core Imports                                                         #
#                                                                            #
##############################################################################
import threading
import math
import os, os.path, sys
import time
import datetime
import urllib2
import json
import random
import socket
import re
import locale
locale.setlocale(locale.LC_ALL, '')

##############################################################################
#                                                                            #
#       Kivy UI Imports                                                      #
#                                                                            #
##############################################################################

import kivy
kivy.require( '1.10.0' ) # replace with your current kivy version !

from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.slider import Slider
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.storage.jsonstore import JsonStore
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.garden.knob import  Knob

##############################################################################
#                                                                            #
#       Other Imports                                                        #
#                                                                            #
##############################################################################

import cherrypy
import schedule
import struct


##############################################################################
#                                                                            #
#       GPIO & Simulation Imports                                            #
#                                                                            #
##############################################################################

try:
	import RPi.GPIO as GPIO
except ImportError:
	import FakeRPi.GPIO as GPIO


##############################################################################
#                                                                            #
#       Sensor Imports                                                       #
#                                                                            #
##############################################################################

from w1thermsensor import W1ThermSensor
import Adafruit_DHT

##############################################################################
#                                                                            #
#       Utility classes                                                      #
#                                                                            #
##############################################################################

class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration
    
    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args: # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False


##############################################################################
#                                                                            #
#       MySensor.org Controller compatible translated constants              #
#                                                                            #
##############################################################################

MSG_TYPE_SET 					= "set"
MSG_TYPE_PRESENTATION 				= "presentation"

CHILD_DEVICE_NODE				= "node"
CHILD_DEVICE_UICONTROL_HEAT			= "heatControl"
CHILD_DEVICE_UICONTROL_FAN			= "fanControl"
CHILD_DEVICE_UICONTROL_HOLD			= "holdControl"
CHILD_DEVICE_UICONTROL_TPLUS			= "tempPlus"
CHILD_DEVICE_UICONTROL_SLIDER			= "tempSlider"
CHILD_DEVICE_WEATHER_FCAST_TODAY		= "weatherForecastToday"
CHILD_DEVICE_WEATHER_FCAST_TOMO			= "weatherForecastTomorrow"
CHILD_DEVICE_WEATHER_CURR			= "weatherCurrent"
CHILD_DEVICE_HEAT				= "heat"
CHILD_DEVICE_FAN				= "fan"
CHILD_DEVICE_PIR				= "motionSensor"
CHILD_DEVICE_TEMP				= "temperatureSensor"
CHILD_DEVICE_SCREEN				= "screen"
CHILD_DEVICE_SCHEDULER				= "scheduler"
CHILD_DEVICE_WEBSERVER				= "webserver"

CHILD_DEVICES						= [
	CHILD_DEVICE_NODE,
	CHILD_DEVICE_UICONTROL_HEAT,
	CHILD_DEVICE_UICONTROL_FAN,
	CHILD_DEVICE_UICONTROL_HOLD,
	CHILD_DEVICE_UICONTROL_SLIDER,
	CHILD_DEVICE_WEATHER_CURR,
	CHILD_DEVICE_WEATHER_FCAST_TODAY,
	CHILD_DEVICE_WEATHER_FCAST_TOMO,
	CHILD_DEVICE_HEAT,
	CHILD_DEVICE_FAN,
	CHILD_DEVICE_PIR,
	CHILD_DEVICE_TEMP,
	CHILD_DEVICE_SCREEN,
	CHILD_DEVICE_SCHEDULER,
	CHILD_DEVICE_WEBSERVER
]

CHILD_DEVICE_SUFFIX_UICONTROL		= "Control"

MSG_SUBTYPE_NAME			= "sketchName"
MSG_SUBTYPE_VERSION			= "sketchVersion"
MSG_SUBTYPE_BINARY_STATUS		= "binaryStatus"
MSG_SUBTYPE_TRIPPED			= "armed"
MSG_SUBTYPE_ARMED			= "tripped"
MSG_SUBTYPE_TEMPERATURE			= "temperature"
MSG_SUBTYPE_FORECAST			= "forecast"
MSG_SUBTYPE_CUSTOM			= "custom"
MSG_SUBTYPE_TEXT			= "text"


##############################################################################
#                                                                            #
#       Settings                                                             #
#                                                                            #
##############################################################################

THERMOSTAT_VERSION = "3.0.1"

# Debug settings

debug = False
useTestSchedule = False


# Threading Locks

thermostatLock = threading.RLock()
weatherLock    = threading.Lock()
scheduleLock   = threading.RLock()


# Thermostat persistent settings

settings	= JsonStore( "./setting/thermostat_settings.json" )
state		= JsonStore( "./setting/thermostat_state.json" )
actual		= JsonStore( "./setting/thermostat_actual.json")


#graphics


# Logging settings/setup

LOG_FILE_NAME = "./log/thermostat.log"

LOG_ALWAYS_TIMESTAMP = True

LOG_LEVEL_DEBUG = 1
LOG_LEVEL_INFO	= 2
LOG_LEVEL_ERROR = 3
LOG_LEVEL_STATE = 4
LOG_LEVEL_NONE  = 5

LOG_LEVELS = {
	"debug": LOG_LEVEL_DEBUG,
	"info":  LOG_LEVEL_INFO,
	"state": LOG_LEVEL_STATE,
	"error": LOG_LEVEL_ERROR
}

LOG_LEVELS_STR = { v: k for k, v in LOG_LEVELS.items() }

logFile = None


def log_dummy( level, child_device, msg_subtype, msg, msg_type=MSG_TYPE_SET, timestamp=True, single=False ):
	pass


def log_file( level, child_device, msg_subtype, msg, msg_type=MSG_TYPE_SET, timestamp=True, single=False ):
	if level >= logLevel:
		ts = datetime.datetime.now().strftime( "%Y-%m-%dT%H:%M:%S%z " ) 
		logFile.write( ts + LOG_LEVELS_STR[ level ] + "/" + child_device + "/" + msg_type + "/" + msg_subtype + ": " + msg + "\n" )


def log_print( level, child_device, msg_subtype, msg, msg_type=MSG_TYPE_SET, timestamp=True, single=False ):
	if level >= logLevel:
		ts = datetime.datetime.now().strftime( "%Y-%m-%dT%H:%M:%S%z " ) if LOG_ALWAYS_TIMESTAMP or timestamp else ""
		print( ts + LOG_LEVELS_STR[ level ] + "/" + child_device + "/" + msg_type + "/" + msg_subtype + ": " + msg )


loggingChannel = "none" if not( settings.exists( "logging" ) ) else settings.get( "logging" )[ "channel" ]
loggingLevel   = "state" if not( settings.exists( "logging" ) ) else settings.get( "logging" )[ "level" ]

for case in switch( loggingChannel ):
	if case( 'none' ):
		log = log_dummy
		break
	if case( 'file' ):
		log = log_file
		logFile = open( LOG_FILE_NAME, "a", 0 )
		break
	if case( 'print' ):
		log = log_print
		break
	if case():		# default
		log = log_dummy	

logLevel = LOG_LEVELS.get( loggingLevel, LOG_LEVEL_NONE )

# Send presentations for Node

log( LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_NAME, "Thermostat Starting Up...", msg_type=MSG_TYPE_PRESENTATION )
log( LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_VERSION, THERMOSTAT_VERSION, msg_type=MSG_TYPE_PRESENTATION )

#send presentations for all other child "sensors"

for i in range( len( CHILD_DEVICES ) ):
	child = CHILD_DEVICES[ i ]
	if child != CHILD_DEVICE_NODE:
		log( LOG_LEVEL_STATE, child, child, "", msg_type=MSG_TYPE_PRESENTATION )

# Various temperature settings:

tempScale		= settings.get( "scale" )[ "tempScale" ]
scaleUnits 	  	= u"\xb0" if tempScale == "metric" else "f"
precipUnits		= " mm" if tempScale == "metric" else '"'
precipFactor		= 1.0 if tempScale == "metric" else 0.0393701
precipRound		= 1 if tempScale == "metric" else 1
sensorUnits		= W1ThermSensor.DEGREES_C if tempScale == "metric" else W1ThermSensor.DEGREES_F
windFactor		= 3.6 if tempScale == "metric" else 1.0
windUnits		= " km/h" if tempScale == "metric" else " mph"

TEMP_TOLERANCE	= 0.1 if tempScale == "metric" else 0.18
currentTemp		= 20.0 if tempScale == "metric" else 72.0
outside_temp    = 20.0 if tempScale == "metric" else 72.0
water_temp		= 20.0 if tempScale == "metric" else 72.0
priorCorrected	= -100.0
# openDoor e openDoorcheck for stop sistem for a time set in thermostat_setting and temperature change quickly of 1 C degrees
openDoor		= 21 if not( state.exists( "thermostat" ) ) else int((state.get( "thermostat" )[ "openDoor" ]/state.get( "thermostat" )[ "tempCheckInterval" ])+1)
openDoorCheck	= 20 if not( state.exists( "thermostat" ) ) else int(state.get( "thermostat" )[ "openDoor" ]/state.get( "thermostat" )[ "tempCheckInterval" ])
measure_count = 0
setTemp			= 22.0 if not( state.exists( "state" ) ) else state.get( "state" )[ "setTemp" ]
setice			= 15.0 if not(settings.exists ( "thermostat")) else settings.get("thermostat")["tempice"]
tempHysteresis		= 0.5  if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "tempHysteresis" ]
tempCheckInterval	= 3    if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "tempCheckInterval" ]
out_temp		= 0.0
temp_vis 		= 0 

minUIEnabled		= 0    if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "minUIEnabled" ]
minUITimeout		= 20    if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "minUITimeout" ]
lightOff		= 60   if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "lightOff" ]

minUITimer		= None
csvSaver		= None
lightOffTimer = None


csvTimeout		= 300 if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "saveCsv" ] 

log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/tempScale", str( tempScale ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/scaleUnits", scaleUnits, timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/precipUnits", str( precipUnits ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/precipFactor", str( precipFactor ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/sensorUnits", str( sensorUnits ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/windFactor", str( windFactor ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/windUnits", str( windUnits ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/currentTemp", str( currentTemp ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/setTemp", str( setTemp ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/tempHysteresis", str( tempHysteresis ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/tempCheckInterval", str( tempCheckInterval ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/minUIEnabled", str( minUIEnabled ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/minUITimeout", str( minUITimeout ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/temperature/lightOff", str( lightOff ), timestamp=False )

# Temperature calibration settings:

elevation	  = 0 if not( settings.exists( "thermostat" ) ) else settings.get( "calibration" )[ "elevation" ]
boilingPoint	  = ( 100.0 - 0.003353 * elevation ) if tempScale == "metric" else ( 212.0 - 0.00184 * elevation )
freezingPoint	  = 0.01 if tempScale == "metric" else 32.018
referenceRange	  = boilingPoint - freezingPoint
correctSensor	  = 0 if not( settings.exists( "thermostat" ) ) else settings.get( "calibration" )[ "correctSensor" ]

boilingMeasured   = settings.get( "calibration" )[ "boilingMeasured" ]
freezingMeasured  = settings.get( "calibration" )[ "freezingMeasured" ]
measuredRange	  = boilingMeasured - freezingMeasured

log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/elevation", str( elevation ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/boilingPoint", str( boilingPoint ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/freezingPoint", str( freezingPoint ), timestamp=False )
log( LOG_LEVEL_DEBUG, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/referenceRange", str( referenceRange ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/boilingMeasured", str( boilingMeasured ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/freezingMeasured", str( freezingMeasured ), timestamp=False )
log( LOG_LEVEL_DEBUG, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/calibration/measuredRange", str( measuredRange ), timestamp=False )


# UI Slider settings:

minTemp			  = 15.0 if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "minTemp" ]
maxTemp			  = 30.0 if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "maxTemp" ]
tempStep		  = 0.5  if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "tempStep" ]

log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/minTemp", str( minTemp ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/maxTemp", str( maxTemp ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/UISlider/tempStep", str( tempStep ), timestamp=False )

try:
	tempSensor = W1ThermSensor()
	print("tempsensor ON")
except:
	tempSensor = None
	print("tempsensor OFF")

# PIR (Motion Sensor) setup:

pirEnabled 		= 0 if not( settings.exists( "pir" ) ) else settings.get( "pir" )[ "pirEnabled" ]
pirPin  		= 5 if not( settings.exists( "pir" ) ) else settings.get( "pir" )[ "pirPin" ]

pirCheckInterval 	= 0.5 if not( settings.exists( "pir" ) ) else settings.get( "pir" )[ "pirCheckInterval" ]

pirIgnoreFromStr	= "00:00" if not( settings.exists( "pir" ) ) else settings.get( "pir" )[ "pirIgnoreFrom" ]
pirIgnoreToStr		= "00:00" if not( settings.exists( "pir" ) ) else settings.get( "pir" )[ "pirIgnoreTo" ]

pirIgnoreFrom		= datetime.time( int( pirIgnoreFromStr.split( ":" )[ 0 ] ), int( pirIgnoreFromStr.split( ":" )[ 1 ] ) )
pirIgnoreTo		= datetime.time( int( pirIgnoreToStr.split( ":" )[ 0 ] ), int( pirIgnoreToStr.split( ":" )[ 1 ] ) )

log( LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_ARMED, str( pirEnabled ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/checkInterval", str( pirCheckInterval ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/ignoreFrom", str( pirIgnoreFromStr ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/pir/ignoreTo", str( pirIgnoreToStr ), timestamp=False )

# GPIO Pin setup and utility routines:

heatPin 			= 27 if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "heatPin" ]
fanPin  			= 25 if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "fanPin" ]
lightPin			= 24 if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "lightPin" ]
extprobePin			= 22 if not( settings.exists( "thermostat" ) ) else settings.get( "thermostat" )[ "extprobePin" ] #Rele Byp Sonda esterna IN2

GPIO.setmode( GPIO.BCM )
GPIO.setup( heatPin, GPIO.OUT )
GPIO.output( heatPin, GPIO.HIGH )
GPIO.setup( extprobePin, GPIO.OUT )
GPIO.output( extprobePin, GPIO.HIGH )
GPIO.setup( fanPin, GPIO.OUT )
GPIO.output( fanPin, GPIO.HIGH )
GPIO.setup( lightPin, GPIO.OUT )
GPIO.output( lightPin, GPIO.HIGH )

if pirEnabled:
	GPIO.setup( pirPin, GPIO.IN )

CHILD_DEVICE_HEAT					= "heat"
CHILD_DEVICE_FAN					= "fan"

log( LOG_LEVEL_INFO, CHILD_DEVICE_HEAT, MSG_SUBTYPE_BINARY_STATUS, str( heatPin ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_FAN, MSG_SUBTYPE_BINARY_STATUS, str( fanPin ), timestamp=False )
log( LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, str( pirPin ), timestamp=False )


##############################################################################
#                                                                            #
#       dht22 esp8266 external temp connect                                  #
#                                                                            #
##############################################################################
#dht ext temp setup:
dhtEnabled		= 0 if not( settings.exists( "dhtext") ) else settings.get("dhtext" )[ "dhtEnabled" ]
dhtInterval		= 2000 if not( settings.exists( "dhtext") ) else settings.get("dhtext" )[ "dhtTimeout" ]
dhtTemp			= 0 
dhtUm			= 0
dht_label		= Label( text= " ",size_hint = (None,None), font_size = '25sp', markup=True, text_size= (300,75),color=( 0.5, 0.5, 0.5, 0.2 ))
dhtTest			= 0
dhtSchedule     = 0
dhtCorrect		= 0 if not( settings.exists( "dhtext") ) else settings.get("dhtext" )[ "dhtCorrect" ]
dhtweb 			= "http://" + settings.get( "dhtext" )[ "dhtClientIP" ] + "/"



def get_dht( url ):
		return json.loads( urllib2.urlopen( url, None, 5 ).read() )

def dht_load (dt):
	global dhtTemp,dhtEnabled,dhtTest,dhtSchedule
	try	:	
		dhtUrl			= "http://"+settings.get("dhtext" )[ "dhtClientIP" ]+"/dati"
		dhtread = get_dht(dhtUrl )
		dhtTemp=dhtread["S_temperature"] 
		dhtUm=dhtread["S_humidity"]
		dht_label.text = "Dht : T: "+str(dhtTemp)+" c , Ur: "+str(dhtUm)+" %"
		#dhtEnabled 	= 1
		dhtTest		= 0
		#if dhtSchedule	== 0 :
		#	dhtSchedule = 1
		#	reloadSchedule()
	except:
		dht_label.text = ""	
		dhtTest += 1	
		dhtEnabled = 0
		dhtSchedule = 0
	if dhtTest <= 5:
		Clock.schedule_once( dht_load, dhtInterval )
		#print "normal ",dhtTest	
	elif dhtTest >=7 :
		Clock.schedule_once(dht_load,120)
		#print "blocked ", dhtTest	
	else:
		reloadSchedule()
		Clock.schedule_once(dht_load,60)
		#print "errato ", dhtTest
		
def dht_load_wired(dt):
	global dhtTemp,dhtEnabled,dhtTest,dhtSchedule
	try	:	
		getDhtSensorData()
		#dhtTemp=dhtread["S_temperature"] 
		#dhtUm=dhtread["S_humidity"]
		#dht_label.text = "Dht : T: "+str(dhtTemp)+" c , Ur: "+str(dhtUm)+" %"
		#dhtEnabled 	= 1
		#dhtTest		= 0
		#if dhtSchedule	== 0 :
		#	dhtSchedule = 1
		#	reloadSchedule()
	except:
		dht_label.text = ""	
		dhtTest += 1	
		dhtEnabled = 0
		dhtSchedule = 0
		print "Exception in dht_load_wired"
	if dhtTest <= 5:
		Clock.schedule_once( dht_load_wired, dhtInterval )
		#print "normal ",dhtTest	
	elif dhtTest >=7 :
		Clock.schedule_once(dht_load_wired,120)
		#print "blocked ", dhtTest	
	else:
		reloadSchedule()
		Clock.schedule_once(dht_load_wired, 3)
		#print "errato ", dhtTest

##############################################################################
#                                                                            #
#       dht22 esp8266 out temp 				                                 #
#                                                                            #
##############################################################################

dhtoutEnabled		= 0 if not( settings.exists( "dhtout") ) else settings.get("dhtout" )[ "dhtoutEnabled" ]
dhtoutWired		    = 0 if not( settings.exists( "dhtout") ) else settings.get("dhtout" )[ "dhtoutWired" ]
dhtoutWiredPin	    = 0 if not( settings.exists( "dhtout") ) else settings.get("dhtout" )[ "dhtoutWiredPin" ]
dhtoutweb 			= "http://" + settings.get( "dhtout" )[ "dhtoutIP" ] + "/dati"
def dhtoutRead():
	global out_temp,out_humidity,dhtoutweb
	try:
		dhtoutread = get_dht(dhtoutweb)
		out_temp=dhtoutread["S_temperature"] 
		out_humidity=dhtoutread["S_humidity"]
		print out_temp,out_humidity
	except:
		out_temp= 0
		out_humidity=0
		
def getDhtSensorData():
	global dhtTemp,dhtEnabled,dhtTest,dhtSchedule,out_temp,in_humidity,dhtUm 
	in_humidity, out_temp = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, dhtoutWiredPin)
	dhtTemp=out_temp
	dhtUm=in_humidity
	dht_label.text = "Dht : T: "+str(dhtTemp)+" c , Ur: "+str(dhtUm)+" %"
	#dhtEnabled 	= 1
	dhtTest		= 0
	#if dhtSchedule	== 0 :
	#	dhtSchedule = 1
	#	reloadSchedule()

	#out_humidity = str(out_humidity)
	#out_temp = str(out_temp)
	print out_temp,in_humidity
##############################################################################
#                                                                            #
#       UI Controls/Widgets                                                  #
#                                                                            #
##############################################################################

controlColours = {
					"normal": ( 1.0, 1.0, 1.0, 1.0 ),
					"Cool":   ( 0.0, 0.0, 1.0, 0.4 ),
					"Heat":   ( 4.0, 0.0, 0.0, 1.0 ),
					"Fan":    ( 0.0, 1.0, 0.0, 0.4 ),
					"Manuale":   ( 0.5, 1.0, 0.0, 0.4 ),					
				 }


def setControlState( control, state ):
	with thermostatLock:
		control.state = state
		if state == "normal":
			control.background_color = controlColours[ "normal" ]
		else:
			control.background_color = controlColours[ control.text.replace( "[b]", "" ).replace( "[/b]", "" ) ]
		
		controlLabel = control.text.replace( "[b]", "" ).replace( "[/b]", "" ).lower()
		log( LOG_LEVEL_STATE, controlLabel +  CHILD_DEVICE_SUFFIX_UICONTROL, MSG_SUBTYPE_BINARY_STATUS, "0" if state == "normal" else "1" )

heatControl = ToggleButton( text="[b]Heat[/b]", 
				markup=True, 
				size_hint = ( None, None )
				)

setControlState( heatControl, "normal" if not( state.exists( "state" ) ) else state.get( "state" )[ "heatControl" ] )

fanControl  = ToggleButton( text="[b]Fan[/b]", 
				markup=True, 
				size_hint = ( None, None )
				)

setControlState( fanControl, "normal" if not( state.exists( "state" ) ) else state.get( "state" )[ "fanControl" ] )

holdControl = ToggleButton( text="[b]Manuale[/b]", 
				markup=True, 
				size_hint = ( None, None )
				)
#tempPlus = Button( text="[b]+[/b]", font_size = 24, markup=True,	size_hint = ( None, None ) )

tempPlus = Button( text="", 
				markup=True, 
				size_hint = ( None, None ),
				font_size="30sp",
				border = (0,0,0,0),
				background_normal= "web/images/plus.png",
				background_down = "web/images/plus_1.png",
				color = (1,1,1,1)
				)
				
tempMinus = Button( text="", 
				markup=True, 
				size_hint = ( None, None ),
				font_size="30sp",
				border = (0,0,0,0),
				background_normal= "web/images/minus.png",
				background_down = "web/images/minus_1.png",
				color = (1,1,1,1)
				)

closeBtn = Button( text="             [b]Chiudi App[/b]", 
				markup=True, 
				size_hint = ( None, None ),
				font_size="24sp",
				border = (0,0,0,0),
				background_normal= "web/images/button_1.png",
				background_down = "web/images/button_11.png",
				color = (1,1,1,1)
				)				

rebootBtn = Button( text="            [b]Riavvia Sist[/b]", 
				markup=True, 
				size_hint = ( None, None ),
				font_size="24sp",
				border = (0,0,0,0),
				background_normal= "web/images/button_1.png",
				background_down = "web/images/button_11.png",
				color = (1,1,1,1)
				)				
meteoBtn = Button( text="                [b]Previsioni\n                       meteo[/b]", 
				markup=True, 
				size_hint = ( None, None ),
				font_size="18sp",
				border = (0,0,0,0),
				background_normal= "web/images/button_1.png",
				background_down = "web/images/button_11.png",
				color = (1,1,1,1)
				)				

backBtn = Button( text="          [b]Indietro[/b]", 
				markup=True, 
				size_hint = ( None, None ),
				font_size="30sp",
				border = (0,0,0,0),
				background_normal= "web/images/button_1.png",
				background_down = "web/images/button_11.png",
				color = (1,1,1,1)
				)				
menuBtn = Button( text="[b]Menu[/b]", 
				markup=True, 
				size_hint = ( None, None ),
				font_size="15sp",
				border = (0,0,0,0),
				background_normal= "web/images/button_round_off.png",
				background_down = "web/images/button_round_on.png",
				color = (1,1,1,1)
				)				
setControlState( holdControl, "normal" if not( state.exists( "state" ) ) else state.get( "state" )[ "holdControl" ] )



def get_status_string():
	with thermostatLock:
		temperature = 0
		if holdControl.state == "down":
			sched = "Manuale"
			temperature = setTemp
		elif useTestSchedule:
			sched = "Test"
			temperature = setTemp
		elif heatControl.state == "down":
			if dhtSchedule == 0:				
				sched = "Heat"
			else:
				sched = "Dht"
			temperature = setTemp
		else:
		    sched = "No Ice" 
		    temperature = settings.get("thermostat")["tempice"]
		    testHeat = False
		    
		if GPIO.input( heatPin ) == True:
			testHeat = False
		else:
			testHeat = True

		setLabel.color = (1,1,1,1)
		return "   [b]Ur: " +str(round(dhtUm,1))+"%[/b]\n  " + \
			   "      T Imp:    " +str(temperature)+ scaleUnits +" \n  "+\
			   "   Caldaia:      " + ( "[i][b][color=ff3333]On[/b][/i][/color]" if testHeat else "Off" ) + "\n  "+\
			   "      Sched:   " + sched


versionLabel	= Label( text="Thermostat v" + str( THERMOSTAT_VERSION ), size_hint = ( None, None ), font_size='10sp', markup=True, text_size=( 150, 20 ) )
currentLabel	= Label( text="[b]" + str( currentTemp ) + scaleUnits + "[/b]", size_hint = ( None, None ), font_size='100sp', markup=True, text_size=( 300, 200 ) )
altCurLabel	= Label( text=currentLabel.text, size_hint = ( None, None ), font_size='100sp', markup=True, text_size=( 300, 200 ), color=( 0.5, 0.5, 0.5, 0.2 ) )
waterTempLabel = Label (text="[b][i] NA [/b][/i]", font_size='20sp', markup=True, size_hint = ( None, None ), pos = ( 600, 400 ))


setLabel     = Label( text="  Set\n[b]" + str( setTemp ) + scaleUnits + "[/b]", size_hint = ( None, None ), font_size='25sp', markup=True, text_size=( 100, 100 ) )
statusLabel  = Label( text=get_status_string(), size_hint = ( None, None ),  font_size='30sp', markup=True, text_size=( 300, 230 ) )

altStatusLabel = Label( text=get_status_string(), size_hint = ( None, None),font_size='30sp', markup=True, text_size=( 300, 230 ),color=(0.5,0.5,0.5,0.2))

dateLabel	= Label( text="[b]" + time.strftime("%d %b %a, %Y") + "[/b]", size_hint = ( None, None ), font_size='25sp', markup=True, text_size=( 270, 40 ) )

timeStr		= time.strftime("%H:%M").lower()
timeInit	= time.time()

timeLabel	 = Label( text="[b]" + ( timeStr if timeStr[0:1] != "0" else timeStr[1:] ) + "[/b]", size_hint = ( None, None ), font_size='45sp', markup=True, text_size=( 180, 75 ) )
altTimeLabel = Label( text=timeLabel.text, size_hint = ( None, None ), font_size='40sp', markup=True, text_size=( 180, 75 ), color=( 0.5, 0.5, 0.5, 0.2 ) )

#tempSlider 	 = Slider( orientation='vertical', min=minTemp, max=maxTemp, step=tempStep, value=setTemp, size_hint = ( None, None ) )

tempSlider 		= Knob( knobimg_source = "web/images/round.png",marker_img = "web/images/bline.png",  markeroff_color = (0, 0, 0, 0), marker_inner_color = (0, 0, 0, 1) )

screenMgr    = None

#############################################################################
#                                                                            #
#       Weather functions/constants/widgets                                  #
#                                                                            #
##############################################################################

weatherLocation = settings.get("weather")["location"]
weatherAppKey = settings.get("weather")["appkey"]
weatherURLBase = "https://api.darksky.net/forecast/"
weatherURLTimeout = settings.get("weather")["URLtimeout"]
weatherURLCurrent = weatherURLBase + weatherAppKey + "/" + weatherLocation + "?units=si&exclude=[minutely,hourly,flags,alerts]&lang=it"


#weatherLocation 	 = settings.get( "weather" )[ "location" ]
#weatherAppKey		 = settings.get( "weather" )[ "appkey" ]
#weatherURLBase  	 = "http://api.openweathermap.org/data/2.5/"
#weatherURLForecast 	 = weatherURLBase + "forecast/daily?units=" + tempScale + "&id=" + weatherLocation + "&APPID=" + weatherAppKey + "&lang=it"
#weatherURLTimeout 	 = settings.get( "weather" )[ "URLtimeout" ]
#weatherURLCurrent 	 = weatherURLBase + "weather?units=" + tempScale + "&id=" + weatherLocation + "&APPID=" + weatherAppKey + "&lang=it"

forecastRefreshInterval  = settings.get( "weather" )[ "forecastRefreshInterval" ] * 60  
weatherExceptionInterval = settings.get( "weather" )[ "weatherExceptionInterval" ] * 60  
weatherRefreshInterval   = settings.get( "weather" )[ "weatherRefreshInterval" ] * 60

weatherSummaryLabel  = Label( text="", size_hint = ( None, None ), font_size='18sp', markup=True, text_size=( 250, 50 ), max_lines = 2 )
weatherDetailsLabel  = Label( text="", size_hint = ( None, None ), font_size='20sp', markup=True, text_size=( 300, 150 ), valign="top" )
weatherImg           = Image( source="web/images/na.png", size_hint = ( None, None ) )
weatherminSummaryLabel  = Label( text="", size_hint = ( None, None ), font_size='20sp', markup=True, text_size=( 200, 20 ), color=(0.5,0.5,0.5,0.2) )
weatherminImg           = Image( source="web/images/na.png", size_hint = ( None, None ), color=(1,1,1,0.4) )

forecastTodaySummaryLabel = Label( text="", size_hint = ( None, None ), font_size='10sp',  markup=True, text_size=( 120, 40 ), max_lines = 3 )
forecastTodayDetailsLabel = Label( text="", size_hint = ( None, None ), font_size='15sp',  markup=True, text_size=( 200, 150 ), valign="top" )
forecastTodayImg   		  = Image( source="web/images/na.png", size_hint = ( None, None ) )
forecastTomoSummaryLabel  = Label( text="", size_hint = ( None, None ), font_size='10sp', markup=True, text_size=( 120, 40 ), max_lines = 3)
forecastTomoDetailsLabel  = Label( text="", size_hint = ( None, None ), font_size='15sp', markup=True, text_size=( 200, 150 ), valign="top" )
forecastTomoImg    		  = Image( source="web/images/na.png", size_hint = ( None, None ) )

forecastDataNew = []
forecastSummaryLabelNew = []
forecastDetailsLabelNew = []
forecastImgNew = []
for c in range(0, 3):
    forecastDataNew.append(Label(text="", size_hint=(None, None), font_size='16sp', markup=True, text_size=(300, 20)))
    forecastSummaryLabelNew.append(
        Label(text="", size_hint=(None, None), font_size='16sp', markup=True, text_size=(250, 50)))
    forecastDetailsLabelNew.append(
        Label(text="", size_hint=(None, None), font_size='16sp', markup=True, text_size=(300, 150), valign="top"))
    forecastImgNew.append(Image(source="web/images/na.png", size_hint=(None, None)))
forecastSummaryNew = Label(text="", size_hint=(None, None), font_size='18sp', markup=True, text_size=(800, 50))

def get_weather( url ):
	return json.loads(urllib2.urlopen(url, None, weatherURLTimeout).read())#json.loads( urllib2.urlopen( url, None, weatherURLTimeout ).read() )

def load_weather_info(dt):
    with weatherLock:
		interval = weatherRefreshInterval
		try:
			weather = json.loads(urllib2.urlopen(weatherURLCurrent, None, weatherURLTimeout).read())
			forecastSummaryNew.text = "[b]" + weather["daily"]["summary"] + "[/b]"
			# compile data for forecast
			for c in range(0, 3):
				today = weather["daily"]["data"][c]
				forecastDataNew[c].text = "[b]" + time.strftime('%A  %d/%m ', time.localtime(today["time"])) + "[/b]"
				forecastImgNew[c].source = "web/images/" + today["icon"] + ".png"
				forecastSummaryLabelNew[c].text = "[b]" + today["summary"][:-1] + "[/b] "
				#print "range ", c ,"  forecastDataNew[c].text " ,forecastDataNew[c].text, "  forecastImgNew[c].source ",forecastImgNew[c].source,"  forecastSummaryLabelNew[c].text ",forecastSummaryLabelNew[c].text
				cloudString = " 0"
				windGustString = " 0"
				humidityString = " 0"
				if "cloudCover" in today:
					cloudString = str(today["cloudCover"] * 100)
				if "windGust" in today:
					windGustString = str(int(round(today["windGust"] * windFactor)))
				if "cloudCover" in today:
					humidityString = str( today[ "humidity" ] * 100)
				forecastTextNew = "\n".join((
					"Max: " + str(int(round(today["temperatureMax"], 0))) + "        Min: " + str(
						int(round(today["temperatureMin"], 0))),
					"Umidita:        " + humidityString + "%",

					"Nuvole:          " + cloudString + "%",

					"Pressione:     " + str(int(today["pressure"])) + "mBar",

					"Vento:            " + str(
						int(round(today["windSpeed"] * windFactor))) + " - " + windGustString + windUnits + get_cardinal_direction(
						today["windBearing"]),

				))
				#print "forecastTextNew ", forecastTextNew
				if "precipType" in today or "snow" in today:
					forecastTextNew += "\n"
					if "rain" in today["precipType"]:
						rainTime = time.strftime("%H:%M", time.localtime(int(today["precipIntensityMaxTime"])))
						forecastTextNew += "Pioggia:       " + get_precip_amount( today[ "precipIntensityMax" ] ) + precipUnits + " " + rainTime + "\nProbabilita': " + str(today[ "precipProbability" ] * 100) + "%"
						if "snow" in today["precipType"]:
							forecastTextNew += ", Neve: " + get_precip_amount( today[ "precipAccumulation" ] ) + precipUnits + "\nProbabilita': " + str(today[ "precipProbability" ] * 100) + "%"
					else:
						forecastTextNew += "Neve:           " + get_precip_amount( today[ "precipAccumulation" ] ) + precipUnits + "\nProbabilita': " + str(today[ "precipProbability" ] * 100) + "%"

				forecastDetailsLabelNew[c].text = forecastTextNew

		except:
			print "Something went wrong in load_weather_info"

			interval = weatherExceptionInterval

		Clock.schedule_once( load_weather_info, interval )


def get_cardinal_direction( heading ):
	directions = [ "N", "NE", "E", "SE", "S", "SW", "W", "NW", "N" ]
	return directions[ int( round( ( ( heading % 360 ) / 45 ) ) ) ]
	
	
def display_current_weather( dt ):
	with weatherLock:
		global out_temp,temp_vis, outside_temp, out_humidity
		interval = weatherRefreshInterval
		try:
			weather = get_weather( weatherURLCurrent )
			weatherImg.source = "web/images/" + weather["currently"]["icon"] + ".png"
			print weatherImg.source
			weatherSummaryLabel.text = "[b]" + weather["currently"]["summary"] + "[/b]"
			#weatherImg.source = "web/images/" + weather[ "weather" ][ 0 ][ "icon" ] + ".png" 
			#weatherSummaryLabel.text = "[b]" + weather[ "weather" ][ 0 ][ "description" ].title() + "[/b]"
			#weatherminImg.source = "web/images/" + weather[ "weather" ][ 0 ][ "icon" ] + ".png" 
			#weatherminSummaryLabel.text = "[b]" + weather[ "weather" ][ 0 ][ "description" ].title() + "[/b]"
			if dhtoutEnabled == 1 and dhtoutWired == 0:
				dhtoutRead()
				print "letta temperatura",out_temp
				if out_temp == 0 or out_temp == None:				
					temp_vis = str( int( round( weather["currently"]["temperature"], 1 ) ) )
					
				else:
					temp_vis = str(round(out_temp,1))
					out_humidity = str(int(round(out_humidity,0)))
					print temp_vis
			elif dhtoutEnabled == 1 and dhtoutWired == 1:
				getDhtSensorData()
				print "letta temperatura DHT Filato",out_temp
				if out_temp == 0 or out_temp == None:				
					temp_vis = str( int( round( weather["currently"]["temperature"], 1 ) ) )
				else:
					temp_vis =  str(round(out_temp,1))
					out_humidity = str(int(round(out_humidity,0)))
					print temp_vis
			else:
				temp_vis = str(round(outside_temp,1)) #outside_temp is coming from external sensor #was# str( int( round( weather[ "main" ][ "temp" ], 0 ) ) )
				out_humidity = str( weather["currently"]["humidity"]*100 )

			weatherDetailsLabel.text = "\n".join( (
				"T Out: " + temp_vis + " " +scaleUnits,
				"    Ur : " + out_humidity + "%",
				#"Vento:       " + str( int( round( weather[ "wind" ][ "speed" ] * windFactor ) ) ) + windUnits + " " + get_cardinal_direction( weather[ "wind" ][ "deg" ] ),
				#"Nuvole:     " + str( weather[ "clouds" ][ "all" ] ) + "%",
			) )

			log( LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, weather[ "currently" ][ "summary" ].title() + "; " + re.sub( '\n', "; ", re.sub( ' +', ' ', weatherDetailsLabel.text ).strip() ) )

		except:
			interval = weatherExceptionInterval
			print "debug sono qui"
			weatherImg.source = "web/images/na.png"
			weatherSummaryLabel.text = ""
			weatherDetailsLabel.text = ""

			log( LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_CURR, MSG_SUBTYPE_TEXT, "Update FAILED!" )

		Clock.schedule_once( display_current_weather, interval )

def display_forecast_weather( dt ):
	with weatherLock:
		interval = forecastRefreshInterval
		try:
			forecast = get_weather( weatherURLCurrent )
			today    = forecast["daily"]["data"][0]
			tomo     = forecast["daily"]["data"][1]
			forecastTodayImg.source = "web/images/" + today[ "icon" ] + ".png" 
			forecastTodaySummaryLabel.text = "[b]" + today[ "summary" ].title() + "[/b]"		
			cloudString = " 0"
			windGustString = " 0"
			humidityString = " 0"
			if "cloudCover" in today:
				cloudString = str(today["cloudCover"] * 100)
			if "windGust" in today:
				windGustString = str(int(round(today["windGust"] * windFactor)))
			if "cloudCover" in today:
				humidityString = str( today[ "humidity" ] * 100)
			todayText = "\n".join( (
				"Temp Max:  " + str( int( round( today[ "temperatureMax" ], 0 ) ) ) + scaleUnits + ", Min: " + str( int( round( today[ "temperatureMin" ], 0 ) ) ) + scaleUnits,
				"Umidita:       "+ humidityString + "%",
				"Vento:          " + str( int( round( today[ "windSpeed" ] * windFactor ) ) ) + " - " + windGustString + windUnits +" " + get_cardinal_direction( today[ "windBearing" ] ),
				"Nuvole:        " + cloudString + "%",
			) )
#			print "today -  forecastTodaySummaryLabel.text " ,forecastTodaySummaryLabel.text, "  forecastTodayImg ",forecastTodayImg.source,"  todayText ",todayText

			if "precipType" in today or "snow" in today:
				todayText += "\n"
				if "rain" in today["precipType"]:
					rainTime = time.strftime("%H:%M", time.localtime(int(today["precipIntensityMaxTime"])))
					todayText += "Pioggia:       " + get_precip_amount( today[ "precipIntensityMax" ] ) + precipUnits + " " + rainTime + "\nProbabilita': " + str(today[ "precipProbability" ] * 100) + "%"
					if "snow" in today["precipType"]:
						todayText += ", Neve: " + get_precip_amount( today[ "precipAccumulation" ] ) + precipUnits + "\nProbabilita': " + str(today[ "precipProbability" ] * 100) + "%"
				else:
					todayText += "Neve:           " + get_precip_amount( today[ "precipAccumulation" ] ) + precipUnits + "\nProbabilita': " + str(today[ "precipProbability" ] * 100) + "%"
			forecastTodayDetailsLabel.text = todayText;

			forecastTomoImg.source = "web/images/" + tomo["icon" ] + ".png" 

			forecastTomoSummaryLabel.text = "[b]" + tomo[ "summary" ].title() + "[/b]"		
	
			cloudString = " 0"
			windGustString = " 0"
			humidityString = " 0"
			if "cloudCover" in tomo:
				cloudString = str(tomo["cloudCover"] * 100)
			if "windGust" in tomo:
				windGustString = str(int(round(tomo["windGust"] * windFactor)))
			if "cloudCover" in tomo:
				humidityString = str( tomo[ "humidity" ] * 100)

			tomoText = "\n".join( (
				"Temp Max:  " + str( int( round( tomo[ "temperatureMax" ], 0 ) ) ) + scaleUnits + ", Min: " + str( int( round( tomo[ "temperatureMin" ], 0 ) ) ) + scaleUnits,
				"Umidita:      " + humidityString + "%",
				"Vento:         " + str( int( round( tomo[ "windSpeed" ] * windFactor ) ) ) + " - " + windGustString + windUnits + " " + get_cardinal_direction( tomo[ "windBearing" ] ),
				"Nuvole:       " + cloudString + "%",
			) )

			if "precipType" in tomo or "snow" in tomo:
				tomoText += "\n"
				if "rain" in tomo["precipType"]:
					rainTime = time.strftime("%H:%M", time.localtime(int(tomo["precipIntensityMaxTime"])))
					tomoText += "Pioggia:       " + get_precip_amount( tomo[ "precipIntensityMax" ] ) + precipUnits + " " + rainTime + "\nProbabilita': " + str(tomo[ "precipProbability" ] * 100) + "%"
					if "snow" in ["precipType"]:
						tomoText += ", Neve: " + get_precip_amount( tomo[ "precipAccumulation" ] ) + precipUnits + "\nProbabilita': " + str(tomo[ "precipProbability" ] * 100) + "%"
				else:
					tomoText += "Neve:        " + get_precip_amount( tomo[ "precipAccumulation" ] ) + precipUnits + "\nProbabilita': " + str(tomo[ "precipProbability" ] * 100) + "%"

			forecastTomoDetailsLabel.text = tomoText

			log( LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_FCAST_TODAY, MSG_SUBTYPE_TEXT, today[ "summary" ].title() + "; " + re.sub( '\n', "; ", re.sub( ' +', ' ', forecastTodayDetailsLabel.text ).strip() ) )
			log( LOG_LEVEL_INFO, CHILD_DEVICE_WEATHER_FCAST_TOMO, MSG_SUBTYPE_TEXT, tomo[ "summary" ].title() + "; " + re.sub( '\n', "; ", re.sub( ' +', ' ', forecastTomoDetailsLabel.text ).strip() ) )

		except:
			print "Something went wrong in display_forecast_weather"
			
			interval = weatherExceptionInterval

			forecastTodayImg.source = "web/images/na.png"
			forecastTodaySummaryLabel.text = ""
			forecastTodayDetailsLabel.text = ""
			forecastTomoImg.source = "web/images/na.png"
			forecastTomoSummaryLabel.text = ""
			forecastTomoDetailsLabel.text = ""

			log( LOG_LEVEL_ERROR, CHILD_DEVICE_WEATHER_FCAST_TODAY, MSG_SUBTYPE_TEXT, "Update FAILED!" )

		Clock.schedule_once( display_forecast_weather, interval )
		
		
def get_precip_amount( raw ):
	precip = round( raw * precipFactor, precipRound )

	if tempScale == "metric":
		return str( precip )
	else:
		return str( precip )


##############################################################################
#                                                                            #
#       Utility Functions                                                    #
#                                                                            #
##############################################################################

def get_ip_address():
	s = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
	s.settimeout( 10 )   # 10 seconds
	try:
		s.connect( ( "8.8.8.8", 80 ) )    # Google DNS server
		ip = s.getsockname()[0] 
		log( LOG_LEVEL_INFO, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM +"/settings/ip", ip, timestamp=False )
	except socket.error:
		ip = "127.0.0.1"
		log( LOG_LEVEL_ERROR, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/settings/ip", "FAILED to get ip address, returning " + ip, timestamp=False )

	return ip


def getVersion():
	log( LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_VERSION, THERMOSTAT_VERSION )


def reboot(dt):
	log( LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/reboot", "System Reboot...", single=True ) 
	GPIO.cleanup()

	if logFile is not None:
		logFile.flush()
		os.fsync( logFile.fileno() )
		logFile.close()
	os.system('sudo shutdown -r now')
	#os.execl( sys.executable, 'python', __file__, *sys.argv[1:] )	# This does not return!!!


def setLogLevel( msg ):
	global logLevel

	if LOG_LEVELS.get( msg.payload ):
		log( LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/loglevel", "LogLevel set to: " + msg.payload ) 

		logLevel = LOG_LEVELS.get( msg.payload, logLevel )
	else:
		log( LOG_LEVEL_ERROR, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/loglevel", "Invalid LogLevel: " + msg.payload ) 

def close_program(dt):
	log( LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/close_program", "Thermostat closing...", single=True ) 
	GPIO.cleanup()
	GPIO.setmode( GPIO.BCM )
	GPIO.setup( lightPin, GPIO.OUT )
	GPIO.output( lightPin, GPIO.HIGH )

	if logFile is not None:
		logFile.flush()
		os.fsync( logFile.fileno() )
		logFile.close()

	os.system('kill %d' % os.getpid())
	#os.execl(sys.executable, 'python', __file__, *sys.argv[1:])
	
##############################################################################
#                                                                            #
#       Thermostat Implementation                                            #
#                                                                            #
##############################################################################

# Main furnace/AC system control function:

def change_system_settings():
	with thermostatLock:
		global csvSaver
		hpin_start = str( GPIO.input( heatPin ) )
		fpin_start = str( GPIO.input( fanPin ) )
		if heatControl.state == "down":
	
			if setTemp >= currentTemp + tempHysteresis:
				GPIO.output( heatPin, GPIO.LOW )
				GPIO.output( fanPin, GPIO.LOW )	
			elif setTemp <= currentTemp:
				GPIO.output( heatPin, GPIO.HIGH )
					
		else:
#modifica per minima temp antigelo 
			    if setice >= currentTemp +tempHysteresis and holdControl != "down":
					GPIO.output(heatPin,GPIO.LOW)
			    elif setice <=currentTemp:
					GPIO.output(heatPin,GPIO.HIGH)
				
			    if holdControl.state == "down":
			    	if setTemp >= currentTemp + tempHysteresis:
			    	    GPIO.output(heatPin, GPIO.LOW)
			    	else:
				    GPIO.output( heatPin, GPIO.HIGH )


		# save the thermostat state in case of restart
		state.put( "state", setTemp=setTemp, heatControl=heatControl.state, fanControl=fanControl.state, holdControl=holdControl.state,dhtEnabled=dhtEnabled)
		
		statusLabel.text = get_status_string()
		altStatusLabel.text = get_status_string()

		if hpin_start != str( GPIO.input( heatPin ) ):
			Clock.unschedule(csvSaver)
			csvSaver = Clock.schedule_once(save_graph, 1)
			log( LOG_LEVEL_STATE, CHILD_DEVICE_HEAT, MSG_SUBTYPE_BINARY_STATUS, "1" if GPIO.input( heatPin ) else "0" )
		if fpin_start != str( GPIO.input( fanPin ) ):
			log( LOG_LEVEL_STATE, CHILD_DEVICE_FAN, MSG_SUBTYPE_BINARY_STATUS, "1" if GPIO.input( fanPin ) else "0" )


# This callback will be bound to the touch screen UI buttons:

def control_callback( control ):
	with thermostatLock:
		setControlState( control, control.state ) 	# make sure we change the background colour!

		if control is heatControl:
			if control.state == "down":
				setControlState( holdControl, "normal" )
			reloadSchedule()
		if control is holdControl:
			if control.state == "down":
				setControlState(heatControl, "normal" )
			reloadSchedule()						

# Check the current sensor temperature
def set_sensor_precision():
	global out_sensor, water_sensor, home_sensor
	with thermostatLock:
		out_sensor = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, "0516a50996ff")
		#out_sensor.set_precision(12)
		water_sensor = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, "0516a4f7beff")
		water_sensor.set_precision(11)
		home_sensor = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, "041656f614ff")
		#home_sensor.set_precision(12)

		
def check_sensor_temp( dt ):
	with thermostatLock:
		global currentTemp, priorCorrected, outside_temp, water_temp, setTemp, out_sensor, water_sensor, home_sensor
		global tempSensor,dhtTemp,openDoor,openDoorCheck,measure_count,homeTemp,out_humidity
		correctedTemp=20
		tempSlider.value = setTemp
		#sensor = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, "0516a50996ff")
		outside_temp = round(out_sensor.get_temperature(),1) #round(sensor.get_temperature(),1)
		#sensor = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, "0516a4f7beff")
		water_temp = round(water_sensor.get_temperature(),1) #round(sensor.get_temperature(),1)
		#sensor = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, "041656f614ff")
		homeTemp = home_sensor.get_temperature() #sensor.get_temperature()
		#for sensor in W1ThermSensor.get_available_sensors([W1ThermSensor.THERM_SENSOR_DS18B20]):
			#print("Sensor %s has temperature %.2f" % (sensor.id, sensor.get_temperature()))
		if dhtEnabled == 1 and dhtTemp <> 0:
			getDhtSensorData()		
			rawTemp = dhtTemp
			correctedTemp = ( ( ( rawTemp - freezingMeasured ) * referenceRange ) / measuredRange ) + freezingPoint + dhtCorrect
			log( LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/dhtTemp", str( rawTemp ) )
			log( LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/corrected", str( correctedTemp ) )
			
		else:
			if tempSensor is not None:
				#getDhtSensorData() #is it called by check_inside_dht		
				rawTemp = homeTemp
#				rawTemp = tempSensor.get_temperature( sensorUnits )
				correctedTemp = ( ( ( rawTemp - freezingMeasured ) * referenceRange ) / measuredRange ) + freezingPoint + correctSensor
				log( LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/raw", str( rawTemp ) )
				log( LOG_LEVEL_DEBUG, CHILD_DEVICE_TEMP, MSG_SUBTYPE_CUSTOM + "/corrected", str( correctedTemp ) )
				print ("rawTemp= " + str(rawTemp) + "\n")
				#Update out temp that is coming from external sensor
				weatherDetailsLabel.text = "\n".join((
					"T Out: " + str(round(outside_temp,1)) + " " +scaleUnits,
					"   Ur : " + out_humidity + "%",
					#"Vento:       " + str( int( round( weather[ "wind" ][ "speed" ] * windFactor ) ) ) + windUnits + " " + get_cardinal_direction( weather[ "wind" ][ "deg" ] ),
					#"Nuvole:     " + str( weather[ "clouds" ][ "all" ] ) + "%",
				))
#check if temp is changed and if opendoor 			
		
		if abs( priorCorrected - correctedTemp ) >= TEMP_TOLERANCE:
			log( LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, str( currentTemp ) )	
			priorCorrected = correctedTemp
			currentTemp = round( correctedTemp, 1 )	
#		else:
#			measure_count=0
#			if 	abs( priorCorrected - correctedTemp ) >= 1 and openDoor <= openDoorCheck:
#				print openDoor,openDoorCheck,priorCorrected,correctedTemp			
#				openDoor +=1			
#			else:	
#				print openDoor,openDoorCheck				
#				openDoor == 0				
#				log( LOG_LEVEL_STATE, CHILD_DEVICE_TEMP, MSG_SUBTYPE_TEMPERATURE, str( currentTemp ) )	
#				priorCorrected = correctedTemp
#				currentTemp = round( correctedTemp, 1 )	

		currentLabel.text = "[b]" + str( currentTemp ) + scaleUnits + "[/b]"
		altCurLabel.text  = currentLabel.text

		dateLabel.text      = "[b]" + time.strftime("%d %b %a, %Y") + "[/b]"

		timeStr		 = time.strftime("%H:%M").lower()

		timeLabel.text      = ( "[b]" + ( timeStr if timeStr[0:1] != "0" else timeStr[1:] ) + "[/b]" ).lower()
		altTimeLabel.text  	= timeLabel.text
		
		waterTempLabel.text = "[b]" + str( round(water_temp,1) )+" "+ scaleUnits + "[/b]"

		change_system_settings()

def check_inside_dht( dt ):
	with thermostatLock:
		getDhtSensorData()		

		change_system_settings()

# This is called when the desired temp slider is updated:
def start_inc_by_button(dt):
	temp_inc_by_button(dt)
	Clock.schedule_interval(temp_inc_by_button, 0.5)
	
def stop_inc_by_button(dt):
	Clock.unschedule(temp_inc_by_button)
	
def temp_inc_by_button(dt):
	tempSlider.value+=tempStep
	update_set_temp(tempSlider, tempSlider.value)
	
def start_dec_by_button(dt):
	temp_dec_by_button(dt)
	Clock.schedule_interval(temp_dec_by_button, 0.5)
	
def stop_dec_by_button(dt):
	Clock.unschedule(temp_dec_by_button)
	
def temp_dec_by_button(dt):
	tempSlider.value-=tempStep
	update_set_temp(tempSlider, tempSlider.value)
		
def update_set_temp( slider, value ):
	with thermostatLock:
		global setTemp
		priorTemp = setTemp
		setTemp = round( slider.value, 1 )
		setLabel.text = "  Set\n[b]" + str( setTemp ) + scaleUnits + "[/b]"
		if priorTemp != setTemp:
			log( LOG_LEVEL_STATE, CHILD_DEVICE_UICONTROL_SLIDER, MSG_SUBTYPE_TEMPERATURE, str( setTemp ) )

# Check the PIR motion sensor status

def check_pir( pin ):
	global minUITimer
	global lightOffTimer
	with thermostatLock:
		if GPIO.input( pirPin ): 
			log( LOG_LEVEL_INFO, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, "1" )

			if minUITimer != None:
				  Clock.unschedule( show_minimal_ui )
				  if lightOffTimer != None:
					Clock.unschedule( light_off )	
			minUITimer = Clock.schedule_once( show_minimal_ui, minUITimeout ) 
			lighOffTimer = Clock.schedule_once( light_off, lightOff )	
			ignore = False
			now = datetime.datetime.now().time()
			
			if pirIgnoreFrom > pirIgnoreTo:
				if now >= pirIgnoreFrom or now < pirIgnoreTo:
					ignore = True
			else:
				if now >= pirIgnoreFrom and now < pirIgnoreTo:
					ignore = True

			if screenMgr.current == "minimalUI" and not( ignore ):
				screenMgr.current = "thermostatUI"
				log( LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Full" )
	
		else:
			log( LOG_LEVEL_DEBUG, CHILD_DEVICE_PIR, MSG_SUBTYPE_TRIPPED, "0" )


#Salvo i dati per il grafico
def save_graph(dt):
# save graph
#conversione heatpin in temperatura 2=off 10=on
	global csvSaver
	global csvTimeout, water_temp, outside_temp
	Clock.unschedule(csvSaver)
	switchTemp = 10
	if GPIO.input( heatPin ) == True:
		switchTemp = 2
	else:
		switchTemp = 10	
	#scrivo il file csv con i dati 
	out_file=open (("./web/graph/" + "thermostat.csv"),"a")
	#    labels:["Date","set","Temp IN","Temp OUT","Temp Acqua","switch"],
	out_file.write (time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())+", "+str(setTemp)+", "+str(currentTemp)+ ", " + str(outside_temp) +", " + str(water_temp) + ", " + str(switchTemp) + "\n")
	out_file.close()
	timeInit=time.time()
	print "running save_graph \n"
	csvSaver = Clock.schedule_once(save_graph, csvTimeout)		
		
#premendo set label change dht enabled

def dht_change(test,data):
	global dhtEnabled,dhtSchedule
	x_pos=data.pos[0]
	y_pos=data.pos[1]	
	if (x_pos>=676 and x_pos<=753 and y_pos>=225 and  y_pos <= 276):
		if heatControl.state == "down":			
			setLabel.color=(1,0.1,0.1,1)		
			if dhtEnabled == 0 and settings.get("dhtext" )[ "dhtEnabled" ] == 1 :
				dhtEnabled = 1			
				if dhtoutWired == 0:
					Clock.schedule_once(dht_load,3)
				else:
					Clock.schedule_once(dht_load_wired,3)
				print "dht Enabled"
			else:
				dhtEnabled = 0
				dhtSchedule = 0
				dht_label.text = ""
				if dhtoutWired == 0:
					Clock.unschedule(dht_load)
				else:
					Clock.unschedule(dht_load_wired)
				reloadSchedule()
				print "dht Disabled"
	print "change dht"	,x_pos	,y_pos
	reset_light(test)
			
# Minimal UI Display functions and classes
#shell.shell(has_input=False, record_output=True, record_errors=True, strip_empty=True)

def show_minimal_ui( dt ):
	with thermostatLock:
		screenMgr.current = "minimalUI"
		log( LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Minimal" )

def show_uility_ui( dt ):
	with thermostatLock:
		screenMgr.current = "utilityUI"
		print "show_uility_ui"
		log( LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Utility" )

def show_full_ui( dt ):
	with thermostatLock:
		screenMgr.current = "thermostatUI"
		log( LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Full" )

def select_meteo(testo):
	global minUITimer
	global lightOffTimer
	if minUITimer != None:
		Clock.unschedule(show_minimal_ui)
	if lightOffTimer != None:
		Clock.unschedule(light_off)
	screenMgr.current = "meteoUI"
	Clock.schedule_once(returnScreen, 20)

def returnScreen(dt):
	global lightOffTimer
	with thermostatLock:
		lighOffTimer = Clock.schedule_once(light_off, lightOff)
		screenMgr.current = "thermostatUI"

def light_off( dt ):
	with thermostatLock:
		GPIO.output( lightPin, GPIO.LOW )
		log( LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Screen Off" )
		
def knob_init(dt):
	tempSlider.min=int(minTemp)
	tempSlider.max=int(maxTemp)
	#tempSlider.step = 0.5#int(tempStep)/10
	tempSlider.value = setTemp	

def reset_light(dt):
	global lightOffTimer
	with thermostatLock:
		Clock.unschedule( light_off )
		lighOffTimer = Clock.schedule_once( light_off, lightOff )
		GPIO.output( lightPin, GPIO.HIGH )
		log( LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "LightReset" )

class MinimalScreen( Screen ):
	def on_touch_down( self, touch ):
		if self.collide_point( *touch.pos ):
			touch.grab( self )
			return True

	def on_touch_up( self, touch ):
		global minUITimer
		global lightOffTimer
		if touch.grab_current is self:
			touch.ungrab( self )
			with thermostatLock:
				Clock.unschedule( light_off )
				if minUITimer != None:
					Clock.unschedule( show_minimal_ui )	
				minUITimer = Clock.schedule_once( show_minimal_ui, minUITimeout )
				lighOffTimer = Clock.schedule_once( light_off, lightOff )
				GPIO.output( lightPin, GPIO.HIGH )
				self.manager.current = "thermostatUI"
				log( LOG_LEVEL_DEBUG, CHILD_DEVICE_SCREEN, MSG_SUBTYPE_TEXT, "Full" )
			return True

class UtilityScreen( Screen ):
	pass

class MeteoScreen( Screen ):
	pass

class ThermoScreen( Screen ):
	pass


##############################################################################
#                                                                            #
#       Kivy Thermostat App class                                            #
#                                                                            #
##############################################################################

class ThermostatApp( App ):

	def build( self ):
		global screenMgr,csvSaver, lighOffTimer
		screenMgr = ScreenManager( transition=NoTransition())		# FadeTransition seems to have OpenGL bugs in Kivy Dev 1.9.1 and is unstable, so sticking with no transition for now

		# Set up the thermostat UI layout:
		thermostatUI = FloatLayout( size=( 800, 480 ) )

		# Make the background black:
		with thermostatUI.canvas.before:
			Color ( 0.0, 0.0, 0.0, 1 )
			self.rect = Rectangle( size=( 800, 480 ), pos=thermostatUI.pos )
			Color (0.3, 0.3,  0.4, 1.0)
			self.rect =Rectangle (size=(132,62), pos=(650,68))
			self.rect =Rectangle (size=(132,62), pos=(650,358))
			Color (0.0, 0.0,  0.0, 1)
			#self.rect =Rectangle (size=(284,244), pos=(283,213))
		# Create the rest of the UI objects ( and bind them to callbacks, if necessary ):
		
		wimg = Image( source='web/images/logo.png' )

		heatControl.bind( on_press=control_callback )	
		holdControl.bind( on_press=control_callback )
		meteoBtn.bind(on_release=select_meteo)
		closeBtn.bind(on_release=close_program)
		rebootBtn.bind(on_release=reboot)
		backBtn.bind(on_release=show_full_ui)

		tempPlus.bind(on_press=start_inc_by_button, on_release=stop_inc_by_button)
		tempMinus.bind(on_press=start_dec_by_button, on_release=stop_dec_by_button)
		menuBtn.bind(on_release=show_uility_ui)
		setLabel.bind( on_touch_down=dht_change)
		
		#tempSlider.bind( on_touch_down=update_set_temp, on_touch_move=update_set_temp )

   	# set sizing and position info
		
		wimg.size = ( 64, 64 )
		wimg.size_hint = ( None, None )
		wimg.pos = ( 5, 400 )

		heatControl.size  = ( 130, 60 )
		heatControl.pos = ( 651, 360 )
		
		tempPlus.size = ( 130, 60 )
		tempPlus.pos = ( 651, 290 )

		statusLabel.pos = ( 370, 225 )

		tempSlider.size  = (400, 400 )
		tempSlider.pos = ( 200, 50 )

		tempMinus.size = ( 130, 60 )
		tempMinus.pos = ( 651, 140 )

		holdControl.size  = ( 130, 60 )
		holdControl.pos = ( 651, 70 )

		setLabel.pos = ( 680,220 )
		

		currentLabel.pos = ( 380, 335 )

		dateLabel.pos = ( 165, 400 )
		timeLabel.pos = ( 150,370 )
		
		menuBtn.size  = ( 60, 60 )
		menuBtn.pos = ( 580, 40 )
		
		weatherImg.pos = ( 300, 70 )
		weatherSummaryLabel.pos = ( 350, 0 )
		weatherDetailsLabel.pos = ( 495,27 )
		
		versionLabel.pos = ( 710, 0 )
		
		forecastTodayHeading = Label( text="[b][i]Oggi [/i][/b]", font_size='20sp', markup=True, size_hint = ( None, None ), pos = ( 85, 320 ) )
		
		forecastTodayImg.pos = ( 0, 290 )
		forecastTodaySummaryLabel.pos = ( 115, 290 )
		forecastTodayDetailsLabel.pos = ( 80, 187 )

		forecastTomoHeading = Label( text="[b][i]Domani [/b][/i]", font_size='20sp', markup=True, size_hint = ( None, None ), pos = ( 90, 135 ) )

		forecastTomoImg.pos = ( 0, 110 )
		forecastTomoSummaryLabel.pos = ( 115, 110 )
		forecastTomoDetailsLabel.pos = ( 80, 8 )

		waterTempHeading = Label (text="[b][i]Temp. Acqua: [/b][/i]", font_size='20sp', markup=True, size_hint = ( None, None ), pos = ( 500, 400 ))
		d = 60
		for c in range(0, 3):
			forecastDataNew[c].pos = (d + 85, 360)
			forecastImgNew[c].pos = (d - 20, 290)
			forecastSummaryLabelNew[c].pos = (d + 40, 220)
			forecastDetailsLabelNew[c].pos = (d + 70, 110)
			d += 260
		forecastSummaryNew.pos = (360, 410)

		# Add the UI elements to the thermostat UI layout:
		thermostatUI.add_widget( wimg )
		thermostatUI.add_widget( heatControl )
		thermostatUI.add_widget( tempPlus )
		thermostatUI.add_widget( tempMinus )
		thermostatUI.add_widget( holdControl )
		thermostatUI.add_widget( tempSlider )
		thermostatUI.add_widget( currentLabel )
		thermostatUI.add_widget( setLabel )
		thermostatUI.add_widget( statusLabel )
		thermostatUI.add_widget( dateLabel )
		thermostatUI.add_widget( timeLabel )
		thermostatUI.add_widget( weatherImg )
		thermostatUI.add_widget( weatherSummaryLabel )
		thermostatUI.add_widget( weatherDetailsLabel )
		thermostatUI.add_widget( versionLabel )
		thermostatUI.add_widget( forecastTodayHeading )
		thermostatUI.add_widget( forecastTodayImg )
		thermostatUI.add_widget( forecastTodaySummaryLabel )
		thermostatUI.add_widget( forecastTodayDetailsLabel )
		thermostatUI.add_widget( forecastTomoHeading )
		thermostatUI.add_widget( forecastTomoImg )
		thermostatUI.add_widget( forecastTomoDetailsLabel )
		thermostatUI.add_widget( forecastTomoSummaryLabel )
		thermostatUI.add_widget( waterTempHeading )
		thermostatUI.add_widget( waterTempLabel )
		thermostatUI.add_widget( menuBtn )
		
		#layout = thermostatUI

		# Minimap UI initialization
		uiScreen 	= ThermoScreen( name="thermostatUI" )
		uiScreen.add_widget( thermostatUI )
		screenMgr.add_widget ( uiScreen )
		layout = screenMgr

		if minUIEnabled:
			#uiScreen.add_widget( thermostatUI )

			minScreen 	= MinimalScreen( name="minimalUI" )
			minUI 		= FloatLayout( size=( 800, 480 ) )
			

			with minUI.canvas.before:
				Color( 0.0, 0.0, 0.0, 1 )
				self.rect = Rectangle( size=( 800, 480 ), pos=minUI.pos )
				altCurLabel.pos = ( 390, 290 )
				altTimeLabel.pos = ( 335, 380 )
				altStatusLabel.pos = (360 , 170 )
				
			minUI.add_widget( altCurLabel )
			minUI.add_widget( altTimeLabel )
			minUI.add_widget( altStatusLabel )
			minScreen.add_widget( minUI )
			if dhtEnabled:
				dht_label.pos = ( 400, 40)
				minUI.add_widget(dht_label)
				
			#screenMgr.add_widget ( uiScreen )
			screenMgr.add_widget ( minScreen )

			#layout = screenMgr
			minUITimer = Clock.schedule_once( show_minimal_ui, minUITimeout )
			lighOffTimer = Clock.schedule_once( light_off, lightOff )
			csvSaver = Clock.schedule_once(save_graph, 3)
			if pirEnabled:
				Clock.schedule_interval( check_pir, pirCheckInterval )

#menu screen
		utilityUI 	= FloatLayout( size=( 800, 480 ) )
		

		with utilityUI.canvas.before:
			Color( 0.0, 0.0, 0.0, 1 )
			self.rect = Rectangle( size=( 800, 480 ), pos=(0, 0))
			Color(0,0,128,1)
			self.rect = Rectangle( size=( 780, 460 ), pos=(10, 10 ))
			Color( 0.0, 0.0, 0.0, 1 )
			self.rect = Rectangle( size=( 770, 450 ), pos=(15, 15 ))
			meteoBtn.pos = ( 40, 360 )
			meteoBtn.size = (220, 80)
			rebootBtn.pos = ( 540, 260 )
			rebootBtn.size = (220, 80)
			closeBtn.pos = ( 540, 160 )
			closeBtn.size = (220, 80)
			backBtn.pos = ( 540, 60 )
			backBtn.size = (220, 80)
			
		utilityUI.add_widget( meteoBtn )
		utilityUI.add_widget( rebootBtn )
		utilityUI.add_widget( closeBtn )
		utilityUI.add_widget( backBtn )
		utilityScreen 	= UtilityScreen( name="utilityUI" )
		utilityScreen.add_widget( utilityUI )
		screenMgr.add_widget ( utilityScreen )

		# creo la pagina per il meteo
		meteoScreen = MeteoScreen(name="meteoUI")
		meteoUI = FloatLayout(size=(800, 480))
		with meteoUI.canvas.before:
			Color(0.0, 0.0, 0.0, 1)
			self.rect = Rectangle(size=(800, 480), pos=meteoUI.pos)
		meteoUI.add_widget(forecastSummaryNew)

		for c in range(0, 3):
			meteoUI.add_widget(forecastDataNew[c])
			meteoUI.add_widget(forecastImgNew[c])
			meteoUI.add_widget(forecastSummaryLabelNew[c])
			meteoUI.add_widget(forecastDetailsLabelNew[c])

		meteoScreen.add_widget(meteoUI)
		screenMgr.add_widget ( meteoScreen )
		
		# Start checking the temperature
		set_sensor_precision()
		Clock.schedule_interval( check_sensor_temp, tempCheckInterval )
		Clock.schedule_interval( check_inside_dht, tempCheckInterval+(tempCheckInterval/2) )
		if dhtEnabled == 1:
			if dhtoutWired == 0:
				Clock.schedule_once(dht_load,2)
			else:
				Clock.schedule_once(dht_load_wired, 2)
		# Show the current weather  		
		Clock.schedule_once( display_current_weather, 6 )
		#initialize knob		
		Clock.schedule_once( knob_init, 4 )
		
		Clock.schedule_once( display_forecast_weather, 5 )
#		Clock.schedule_once( display_current_weather, 4 )
		Clock.schedule_once( load_weather_info, 4 )
		
		lightOffTimer = Clock.schedule_once( light_off, lightOff )
		csvSaver = Clock.schedule_once(save_graph, 20)		
		return layout


##############################################################################
#                                                                            #
#       Scheduler Implementation                                             #
#                                                                            #
##############################################################################

def startScheduler():
	log( LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_TEXT, "Started" )
	while True:
		if holdControl.state == "normal":
			with scheduleLock:
				log( LOG_LEVEL_DEBUG, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_TEXT, "Running pending" )
				schedule.run_pending()

		time.sleep( 10 )


def setScheduledTemp( temp ):
	with thermostatLock:
		global setTemp,dhtEnabled
		actual.put( "state", setTemp=round(temp,1), dhtEnabled=dhtEnabled,heatControl=heatControl.state, fanControl=fanControl.state, holdControl=holdControl.state)		
		print ("setScheduledTemp at ",temp)
		if holdControl.state == "normal":
			setTemp = round( temp, 1 )
			setLabel.text = "  Set\n[b]" + str( setTemp ) + scaleUnits + "[/b]"
			tempSlider.value = setTemp
			log( LOG_LEVEL_STATE, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_TEMPERATURE, str( setTemp ) )


def getTestSchedule():
	days = [ "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday" ]
	testSched = {}
	
	for i in range( len( days ) ):
		tempList = []
		for minute in range( 60 * 24 ):
			hrs, mins = divmod( minute, 60 )
			tempList.append( [
					str( hrs ).rjust( 2, '0' ) + ":" + str( mins ).rjust( 2, '0' ),
					float( i + 1 ) / 10.0 + ( ( 19.0 if tempScale == "metric" else 68.0 ) if minute % 2 == 1 else ( 22.0 if tempScale == "metric" else 72.0 ) )
					] )

		testSched[ days[i] ] = tempList

	return testSched


def reloadSchedule():
	global setTemp
	with scheduleLock:
		schedule.clear()

		activeSched = None
		tempToBeSet = setTemp
		with thermostatLock:
			thermoSched = JsonStore( "./setting/thermostat_schedule.json" )
			if holdControl != "down" :
				if heatControl.state == "down":
					if dhtSchedule == 0:					
						activeSched = thermoSched[ "heat" ]  
						log( LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_CUSTOM + "/load", "heat" )
					else:
						activeSched = thermoSched[ "dht" ]  
						log( LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_CUSTOM + "/load", "dht" )
			if useTestSchedule: 
				activeSched = getTestSchedule()
				log( LOG_LEVEL_INFO, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_CUSTOM + "/load", "test" )
				print "Using Test Schedule!!!"
	
		if activeSched != None:
			for day, entries in activeSched.iteritems():
				for i, entry in enumerate( entries ):
					getattr( schedule.every(), day ).at( entry[ 0 ] ).do( setScheduledTemp, entry[ 1 ] )
					log( LOG_LEVEL_DEBUG, CHILD_DEVICE_SCHEDULER, MSG_SUBTYPE_TEXT, "Set " + day + ", at: " + entry[ 0 ] + " = " + str( entry[ 1 ] ) + scaleUnits )
					now = datetime.datetime.now()
					#print now.strftime("%A") + day
					if (now.strftime("%A").lower() == day.lower()):
						timenow = now.strftime('%H:%M')
						if (timenow >= entry[0]):
							tempToBeSet = entry[1]
							#print "Analyzing schedule for " + day + " " + str(entry[0]) + " " + str(entry[1]) + " Actual time " + str(timenow)
			print "Setting temp from scheduler at " + str(tempToBeSet)
		tempSlider.value=round(tempToBeSet,1)
		update_set_temp(tempSlider, tempSlider.value)				

##############################################################################
#                                                                            #
#       Web Server Interface                                                 #
#                                                                            #
##############################################################################

##############################################################################
#      encoding: UTF-8                                                       #
# Form based authentication for CherryPy. Requires the                       #
# Session tool to be loaded.                                                 #
##############################################################################
cherrypy.server.socket_host = '0.0.0.0'


class WebInterface(object):

	@cherrypy.expose
	
	def index( self ):	
		log( LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT, "Served thermostat.html to: " + cherrypy.request.remote.ip )	
		
		
		file = open( "web/html/thermostat.html", "r" )

		html = file.read()

		file.close()

		with thermostatLock:		

			html = html.replace( "@@version@@", str( THERMOSTAT_VERSION ) )
			html = html.replace( "@@temp@@", str( setTemp ) )
			html = html.replace( "@@current@@", str( currentTemp ) )
			html = html.replace( "@@minTemp@@", str( minTemp ) )
			html = html.replace( "@@maxTemp@@", str( maxTemp ) )
			html = html.replace( "@@tempStep@@", str( tempStep ) )
			html = html.replace( "@@temp_extern@@",str( outside_temp ) )
			html = html.replace( "@@water_temp@@",str( water_temp ) )
		
			status = statusLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			status = status.replace( "[color=00ff00]", '<font color="red">' ).replace( "[/color]", '</font>' ) 
			forecastToday = forecastTodayDetailsLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			weatherSummaryLabel_web = weatherSummaryLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			html = html.replace( "@@forecastToday@@", forecastToday )
			html = html.replace( "@@status@@", status )
			html = html.replace( "@@dt@@", dateLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) + " - " + timeLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) )
			html = html.replace( "@@heatChecked@@", "checked" if heatControl.state == "down" else "" )
			html = html.replace( "@@holdChecked@@", "checked" if holdControl.state == "down" else "" )
			html = html.replace( "@@weatherSummaryLabel_web@@", weatherSummaryLabel_web )
			if dhtEnabled == 0:
				html = html.replace ("@@dhtsubmit@@", "none")
			else:
				html = html.replace ("@@dhtsubmit@@", "true")

		return html


	@cherrypy.expose
	def set( self, temp, heat="off", fan="off", hold="off" ):
		global setTemp
		global setLabel
		global heatControl
		global fanControl

		log( LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT, "Set thermostat received from: " + cherrypy.request.remote.ip )	

		tempChanged = setTemp != float( temp )

		with thermostatLock:
			setTemp = float( temp )
			setLabel.text = "  Set\n[b]" + str( setTemp ) + "c[/b]"
			tempSlider.value = setTemp

			if tempChanged:
				log( LOG_LEVEL_STATE, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEMPERATURE, str( setTemp ) )

			if heat == "on":
				setControlState( heatControl, "down" )
			else:
				setControlState( heatControl, "normal" )

			if fan == "on":
				setControlState( fanControl, "down" )
			else:
				setControlState( fanControl, "normal" )

			if hold == "on":
				setControlState( holdControl, "down" )
			else:
				setControlState( holdControl, "normal" )

			reloadSchedule()

		file = open( "web/html/thermostat_set.html", "r" )

		html = file.read()

		file.close()
		
		with thermostatLock:
			html = html.replace( "@@version@@", str( THERMOSTAT_VERSION ) )
			html = html.replace( "@@dt@@", dateLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) + ", " + timeLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) )
			html = html.replace( "@@temp@@", ( '<font color="red"><b>' if tempChanged else "" ) + str( setTemp ) + ( '</b></font>' if tempChanged else "" ) )
			html = html.replace( "@@heat@@", ( '<font color="red"><b>' if heat == "on" else "" ) + heat + ( '</b></font>' if heat == "on" else "" ) )
			html = html.replace( "@@fan@@",  ( '<font color="red"><b>' if fan == "on" else "" ) + fan + ( '</b></font>' if fan == "on" else "" ) )
			html = html.replace( "@@hold@@", ( '<font color="red"><b>' if hold == "on" else "" ) + hold + ( '</b></font>' if hold == "on" else "" ) )

		return html


	@cherrypy.expose
	def schedule( self ):	
		log( LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT, "Served thermostat_schedule.html to: " + cherrypy.request.remote.ip )			
		file = open( "web/html/thermostat_schedule.html", "r" )

		html = file.read()

		file.close()
		
		with thermostatLock:
			html = html.replace( "@@version@@", str( THERMOSTAT_VERSION ) )
			html = html.replace( "@@minTemp@@", str( minTemp ) )
			html = html.replace( "@@maxTemp@@", str( maxTemp ) )
			html = html.replace( "@@tempStep@@", str( tempStep ) )
		
			html = html.replace( "@@dt@@", dateLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) + ", " + timeLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) )
	
		return html

	@cherrypy.expose
	@cherrypy.tools.json_in()
	def save( self ):
		log( LOG_LEVEL_STATE, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT, "Set schedule received from: " + cherrypy.request.remote.ip )	
		schedule = cherrypy.request.json

		with scheduleLock:
			file = open( "./setting/thermostat_schedule.json", "w" )

			file.write( json.dumps( schedule, indent = 4 ) )
		
			file.close()

		reloadSchedule()

		file = open( "web/html/thermostat_saved.html", "r" )

		html = file.read()

		file.close()
		
		with thermostatLock:
			html = html.replace( "@@version@@", str( THERMOSTAT_VERSION ) )
			html = html.replace( "@@dt@@", dateLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) + ", " + timeLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) )
		
		return html
		
	@cherrypy.expose
	def graph( self ):	
		log( LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT, "grah.html to: " + cherrypy.request.remote.ip )			
		file = open( "web/html/graph.html", "r" )

		html = file.read()

		file.close()
		
		return html
	@cherrypy.expose
	
	def weather( self ):	
		log( LOG_LEVEL_INFO, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT, "Served weather.html to: " + cherrypy.request.remote.ip )	
		
		
		file = open( "web/html/weather.html", "r" )

		html = file.read()

		file.close()

		with thermostatLock:		

			html = html.replace( "@@version@@", str( THERMOSTAT_VERSION ) )
			html = html.replace( "@@temp@@", str( setTemp ) )
			html = html.replace( "@@current@@", str( currentTemp ) )
			html = html.replace( "@@minTemp@@", str( minTemp ) )
			html = html.replace( "@@maxTemp@@", str( maxTemp ) )
			html = html.replace( "@@tempStep@@", str( tempStep ) )
			html = html.replace( "@@temp_extern@@",str( outside_temp ) )
			html = html.replace( "@@water_temp@@",str( water_temp ) )
		
			status = statusLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			status = status.replace( "[color=00ff00]", '<font color="red">' ).replace( "[/color]", '</font>' ) 

			forecastDataNew_day1 = forecastDataNew[0].text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			forecastImgNew_day1 = forecastImgNew[0].source.replace("web/","")
			forecastSummaryLabelNew_day1 = forecastSummaryLabelNew[0].text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			forecastDetailsLabelNew_day1 = forecastDetailsLabelNew[0].text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			
			forecastDataNew_day2 = forecastDataNew[1].text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			forecastImgNew_day2 = forecastImgNew[1].source.replace("web/","")
			forecastSummaryLabelNew_day2 = forecastSummaryLabelNew[1].text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			forecastDetailsLabelNew_day2 = forecastDetailsLabelNew[1].text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			
			forecastDataNew_day3 = forecastDataNew[2].text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			forecastImgNew_day3 = forecastImgNew[2].source.replace("web/","")
			forecastSummaryLabelNew_day3 = forecastSummaryLabelNew[2].text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			forecastDetailsLabelNew_day3 = forecastDetailsLabelNew[2].text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			weatherSummaryLabel_web = weatherSummaryLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )
			forecastSummaryNew_weather = forecastSummaryNew.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )

			html = html.replace( "@@forecastDataNew_day1@@", forecastDataNew_day1 )
			html = html.replace( "@@forecastImgNew_day1@@", forecastImgNew_day1 )
			html = html.replace( "@@forecastSummaryLabelNew_day1@@", forecastSummaryLabelNew_day1 )
			html = html.replace( "@@forecastDetailsLabelNew_day1@@", forecastDetailsLabelNew_day1 )

			html = html.replace( "@@forecastDataNew_day2@@", forecastDataNew_day2 )
			html = html.replace( "@@forecastImgNew_day2@@", forecastImgNew_day2 )
			html = html.replace( "@@forecastSummaryLabelNew_day2@@", forecastSummaryLabelNew_day2 )
			html = html.replace( "@@forecastDetailsLabelNew_day2@@", forecastDetailsLabelNew_day2 )

			html = html.replace( "@@forecastDataNew_day3@@", forecastDataNew_day3 )
			html = html.replace( "@@forecastImgNew_day3@@", forecastImgNew_day3 )
			html = html.replace( "@@forecastSummaryLabelNew_day3@@", forecastSummaryLabelNew_day3 )
			html = html.replace( "@@forecastDetailsLabelNew_day3@@", forecastDetailsLabelNew_day3 )

			html = html.replace( "@@weatherSummaryLabel_web@@", weatherSummaryLabel_web )
			html = html.replace( "@@forecastSummaryNew_weather@@", forecastSummaryNew_weather )

			
			forecastToday = forecastTodayDetailsLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ).replace("[/color]","</font>").replace("[color=ff3333]","<font color=\"red\">").replace("[i]","<i>").replace("[/i]","</i>").replace( "\n", "<br>" )

			html = html.replace( "@@forecastToday@@", forecastToday )
			html = html.replace( "@@status@@", status )
			html = html.replace( "@@dt@@", dateLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) + " - " + timeLabel.text.replace( "[b]", "<b>" ).replace( "[/b]", "</b>" ) )
			html = html.replace( "@@heatChecked@@", "checked" if heatControl.state == "down" else "" )
			html = html.replace( "@@holdChecked@@", "checked" if holdControl.state == "down" else "" )
			if dhtEnabled == 0:
				html = html.replace ("@@dhtsubmit@@", "none")
			else:
				html = html.replace ("@@dhtsubmit@@", "true")

		return html

	
	@cherrypy.expose
	def redirect(self):
		global dhtweb

		#file =  open( "web/html/dhtweb.html", "r" )

		f = urllib2.urlopen(dhtweb,None,5)

		#file.close

		#html = html.replace( "@@dhtconn@@", str( dhtweb ) )

		return f

	@cherrypy.expose
	def grafico(self):
		global dhtweb

		#file =  open( "web/html/dhtweb.html", "r" )

		f = urllib2.urlopen(dhtweb+"grafico",None,5)

		#file.close

		#html = html.replace( "@@dhtconn@@", str( dhtweb ) )

		return f

	@cherrypy.expose
	
	def tabella(self):
		global dhtweb

		#file =  open( "web/html/dhtweb.html", "r" )

		f = urllib2.urlopen(dhtweb+"tabella",None,5)

		#file.close

		#html = html.replace( "@@dhtconn@@", str( dhtweb ) )

		return f

def startWebServer():	
	host = "discover" if not( settings.exists( "web" ) ) else settings.get( "web" )[ "host" ]
	#cherrypy.server.socket_host = host if host != "discover" else get_ip_address()	# use machine IP address if host = "discover"
	cherrypy.server.socket_port = 80 if not( settings.exists( "web" ) ) else settings.get( "web" )[ "port" ]

	log( LOG_LEVEL_STATE, CHILD_DEVICE_WEBSERVER, MSG_SUBTYPE_TEXT, "Starting on " + cherrypy.server.socket_host + ":" + str( cherrypy.server.socket_port ) )

	conf = {
		'/': {
			'tools.staticdir.root': os.path.abspath( os.getcwd() ),
			'tools.staticfile.root': os.path.abspath( os.getcwd() )
		},
		'/css': {
			'tools.staticdir.on': True,
			'tools.staticdir.dir': './web/css'
		},
		'/javascript': {
			'tools.staticdir.on': True,
			'tools.staticdir.dir': './web/javascript'
		},
		'/images': {
			'tools.staticdir.on': True,
			'tools.staticdir.dir': './web/images'
		},
		'/schedule.json': {
			'tools.staticfile.on': True,
			'tools.staticfile.filename': './setting/thermostat_schedule.json'
		},
		'/favicon.ico': {
			'tools.staticfile.on': True,
			'tools.staticfile.filename': './web/images/favicon.ico'
		},
		'/graph': {
			'tools.staticdir.on': True,
			'tools.staticdir.dir': './web/graph'
		}

	}

	cherrypy.config.update(
		{ 'log.screen': debug,
		  'log.access_file': "",
		  'log.error_file': "",
		  'server.thread_pool' : 10  
		}
	)

	cherrypy.quickstart ( WebInterface(), '/', conf )	


##############################################################################
#                                                                            #
#       Main                                                                 #
#                                                                            #
##############################################################################

def main():
	# Start Web Server
	webThread = threading.Thread( target=startWebServer )
	webThread.daemon = True
	webThread.start()

	# Start Scheduler
	reloadSchedule()
	schedThread = threading.Thread( target=startScheduler )
	schedThread.daemon = True
	schedThread.start()

	# Start Thermostat UI/App
	ThermostatApp().run()


if __name__ == '__main__':
	try:
		main()
	finally:
		log( LOG_LEVEL_STATE, CHILD_DEVICE_NODE, MSG_SUBTYPE_CUSTOM + "/shutdown", "Thermostat Shutting Down..." )
		GPIO.cleanup()

		if logFile is not None:
			logFile.flush()
			os.fsync( logFile.fileno() )
			logFile.close()


