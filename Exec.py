# Exec7D.py		Uses ephem for coord translation; Uses Astrometry.net for solving when PP unable to solve

#Remove calls for:
#   PrecessLocalToJ2000(dJNowRA, dJNowDec)
#   PrecessJ2000ToLocal(dJ2000RA, dJ2000Dec)

#Setting for config file:   THIS ONLY APPLIES TO WIDE FIELD, ALL NARROW FIELDS STILL USE PP
#	Set_Astrometry.net=1	#0=disable, 1=use after 2 failures of PP solve, 2=use all the time(disable all PP solves)
# line 4412:  CustomAstrometryNetSolve(...)

BASE = r"C:\Users\W510\Documents"
BASE2 = r"C:\Documents and Settings\Joe\My Documents"

Observatory_Database = "C:/fits_script/exec_db.db"
Master_Database = "C:/fits_script/Master_db.db"


#================================================================================
# COM Objects used here:
#--------------------------
#   MaxIm.CCDCamera                 Control of CCD cameras
#   ASCOM.GeminiTelescope.Telescope Control of Gemini Telescope mount
#   FocusMax.FocusControl           Control of Robofocus focuser via FocusMax
#   FocusMax.Focuser                Read Robofocus position and (air)temperature
#   MiniSAC.Catalog                 Catalog of coordinates, including CV's that I add
#   PinPoint.Plate                  PinPoint astrometric solve
#   DriverHelper.Util               Utility functions for formatting coordinates
#   NOVAS.Star                      Used to precess JNow - J2000
#   NOVAS.PositionVector            "
#   TheSky6.StarChart               Used for Planet/Minor planet lookup
#   TheSky6.RASCOMTheSky            Used to calculate Minor planet current coord
#
#
# COM Objects documentation
#--------------------------
#   MaxIm.CCDCamera                 MaxImDL5 Menu: Help / Help Topics; Contents: Scripting
#   ASCOM.GeminiTelescope.Telescope https://ascom-standards.org/Help/Developer/html/Methods_T_ASCOM_DriverAccess_Telescope.htm
#                                       Look in ASCOM.DriverAccess / TelescopeClass for Properties and Methods
#                                       Note use of CommandBlind() to directly access Gemini feature not available through ASCOM interface
#   FocusMax.FocusControl           Astronomy Documents / FocusMax Help.pdf; see section on Scripting for FocusControl and Focuser
#   FocusMax.Focuser                "
#   MiniSAC.Catalog                 Call SelectObject() with the name of the object; if it returns True the equatorial
#                                       coords are in the RightAscension and Declination properties
#   PinPoint.Plate                  Visual PinPoint, Help tab: Scripting the Engine, Plate Object
#   DriverHelper.Util               Utility functions for formatting coordinates
#   NOVAS.Star                      NOVAS_C3.1_Guide.pdf  (full path listed below)
#   NOVAS.PositionVector            "
#   TheSky6.StarChart               TheSky6 Menu: Help / Content and Index; Contents: Scripted Operation
#   TheSky6.RASCOMTheSky            "
#
#   C:\Program Files (x86)\ASCOM\Platform 6 Developer Components\Developer Documentation
#       NOVAS_C3.1_Guide.pdf
#================================================================================



#todo: add feature to set preferred Dec slew direction to target, to take up backlash before guiding

#implExp_InitialMovement:
   #Enhancement? want to move scope SOUTH to target; if target is to the North of
   # current scope position, then slew to a point even farther north, then back
   # south to final location

# 2010.06.24 JU: version for use with QSI-583 camera
# 2010.08.07 JU: only take flats I need: RGB binned 2x2, Lum and Ha binned 1x1 [later changed to just 2x2]
# 2010.10.23 JU: fixed typo that prevented execution of Narrow_Stationary_EndTime_Single
# 2010.12.03 JU: Changed FocusMax calls to Async so I can detect excessive time and raise alarm
#                (sometimes FocusMax puts up a dialog box error message and holds the program until
#                 this is dismissed.)
# 2011.08.24 JU: add "TS6" cat prefix so can look up planets;
#                park at Home instead of CWD now,
#                eliminated the 'Find' FocusMax exposure because not needed.
# 2011.09.08 JU: modified CalibrateOrRefocusForNewTarget so it checks if too soon to refocus
#                BEFORE it does a GOTO to the focus star needlessly!
# 2011.10.03 JU: populate TargetRightAscension, TargetDeclination for PP solve
#                added code to implExp_StartCondition()
#                   check sun altitude, stop if sun > -9 deg
#                   check stop time if run Until a time, before doing anything else
#                if PP finds < 20 catalog stars w/ GSC catalog, redo w/ USNO catalog (for either camera)
#2011.11.12 JU:  Automatically park scope before sounding alarm, to leave it in safer configuration.
#2011.12.12 JU:  added Crop letter to filenames; try to Halt FocusMax when it takes too long; fix bug in WaitUntil time test
#2012.02.01 JU:  expanded logic for when to automatically change PP solve catalog from GSC to USNO.
#                Added Exec_reload.txt feature to allow resuming execution from last step run.
#2012.02.12 JU: Focus logic: use slope -12 to calculate new focus position from temp change
#               if unable to get FocusMax to have reasonable result.
#2012.03.17 JU: added FixGuidingStateSetting
#2012.05.24 JU: After weather safety wait and before retry movement, reconnect the mount.
#2012.06.08 JU: Rewrote PrecessLocalToJ2000() and PrecessJ2000ToLocal() to use NOVAS PositionVector Precess cmd  [changed 2018.01.06]
#2012.06.18 JU: Changed HoursToHMS to display tenths of a second precision in RA strings from now on: HH:MI:SS.S

#2012.07.12 JU: Added ReportImageFWHM(); logs brightest 100 stars in image for now;
#               later will condense this info into one FWHM measurement of the typical
#               non-saturated star.  Note that the Camera.FWHM property is of the brightest
#               star in the image, which is typically saturated so the measurement is meaningless.
#2012.07.29 JU: changed Dark altitude limit for sun from -6 to -3, to see if QSI camera is OK with this for darks
#2012.08.01 JU: tried to fix Oscillation detection logic (it was not working)
#2012.08.29 JU: Disabled ReportImageFWHM(); don't use/need the info
#2012.11.22 JU: When setting guide star locations, need to first DISABLE the auto select flag.
#               I also realized that saving the guider find image as half-size rescales
#               the guide star location, so this may mean I start guiding on a different
#               location than the selected star. I disabled the half-size call; guiding
#               may be much improved now.
#2013.06.17 JU: added drift threshold check to see if we have drifted far from desired position;
#               this can happen if guide star lost but guiding didn't realize it.
#2013.06.28 JU: removed call to LogStatus(vState) in BIAS impl code; don't want it there.
#2013.07.15 JU: before calling FindRestrictedGuideStar, first take GF image with autosection OFF!
#2013.07.24 JU: if FindRestrictedGuideStar does not find any stars, raise weather alarm for retry later instead of ending program.
#               This can happen if it just got cloudy; the preceeding Narrow PP solve image
#               can see a few stars to solve, but then the guider find image has none.
#2014.05.30 JU: change auto focus logic so it does not use failed focus star for focus-near calc, continue using original coord for focus-near
#2014.06.11 JU: ignore PP solve of narrow image if bad plate scale and lots of stars present; probably large globular cluster and have trouble solving these; assume location is OK instead of repeatedly failing.
#2014.09.17 JU: Add delay start for Set_FocusCompensation=D so I can autofocus at start of evening, but temp comp only occurs after sun sets lower than -20 deg
#2014.10.20 JU: fixed errors in BuildFocusStarBand (some conditional tests have always been backwards!); errors could halt the prgm if looking for near focus stars within 1 hour RA east of meridian when sidereal time around 0h  (see test prgm: E_test.py)
#               Also, if one focus attempt has HFD < 6.0, then just accept it, do not do another one (to save time)
#2015.01.19 JU: add feature: Set_HaltAltitude
#2015.06.21 JU: autofocus changed so it uses whatever filter is currently in place; it no longer automatically changes to L filter;
#				in addition, the Set_Filter command will now cause filter wheel to immediately move to specified filter.
#2015.10.17 JU: fixed feature for stopping when certain altitude reached; the test was only being performed in the morning sky, so evening targets were never tested; also reset altitude
#               feature once triggered, so it won't affect the next target with an old setting
#2015.12.13 JU: add socket feature: SendToServer, use w/ prgm eserver.py for now
#2015.12.27 JU: add PrepareAdvancedFocusComp, and script command Set_FocusCompensation=A
#2016.01.02 JU: script was failing when calling RetryInitialMovementUntilClear; it called something that tried to turn on tracking when the mount was not connected, so exception thrown;
#				it seems that this logic is not integrated with newer bad weather logic; not sure why it suddenly starts being encountered because it is old code. I added fix to reconnect
#				mount before trying to turn back on tracking.
#2016.02.01 JU: disabled eserver.py feature because not using it yet
#2016.06.02 JU: redesigned logic to detect guiding problem, include test of trend of last 3 values, also added more logging when guide problem detected;
#               also added logging when FocusMax problem to show position of focuser.
#2016.06.06 JU: added mount command at startup to make sure Gemini is in "Photo" mode so guiding works
#2016.06.16 JU: added Log2Summary() feature, to write to Log2Summary_yyyymmdd.txt with abbreviated messages
#2016.08.15 JU: changed FocusCompensation() logic so adjustment relative to CURRENT focuser location, in case it was moved by MaxImDL for filter change
#2016.12.01 JU: added feature ObservingDateString() so log entries before GMT date changes get same log filename (date) as rest of session
#2017.01.07 JU: I found that I was using the wrong pixel scale for guider, specified in Set_ImageScale in CommmonConfig.txt file; it was
#				still using the Atik camera setting of 3.82", not the SBIG ST-402 setting of 4.64"
#
#2017.02.02 JU: Change version from Exec4.py to Exec5.py; add Astrometry.net support for plate solve when PP doesn't work.
#               This is because GOTO's across pier flip lately have been off by a degree, and PP can't solve when that far off.
#
#2017.02.25 JU: In park command, add logic to report as mount moves like we do for pier flip; there was a problem
#               parking the mount the other day; it did not end up in correct position; don't know why.
#2017.05.07 JU: If FocusMax attempts to run its autofocus routine spanning local midnight, it appears to lock up and will not run
#               any more (I've been using FocusMax version 3.7.0.86 for many years). Last night was apparently the first time when
#               it ever tried to autofocus spanning midnight.  Add feature that if attempting to start autofocus run within
#               5 minutes of local midnight, just pause until after midnight.
#2017.08.22 JU: an unhandled exception occurred in CustomPinpointSolve, involving formatting a string for display; I enclosed all the calls
#               to CustomPinpointSolve in exception block to catch and handle as a failed solve; otherwise program can exit without safety park
#               (this code hasn't changed for years, so this must be a very rare occurrence)
#2017.08.30 JU: removed calls to RetryInitialMovementUntilClear and replaced with raise WeatherError
#2017.09.12 JU: Revise logic for calling Pinpoint and Astrometry.net logic
#2018.01.03 JU: Changed Astrometry.net call to run in separate thread; if it ever takes longer than 10 minutes
#               to complete, the feature is disabled and the thread is abandoned so the rest of the logic can work normally.
#2018.01.06 JU: Rewrote PrecessLocalToJ2000() and PrecessJ2000ToLocal() to use PyEphem library now
#2018.01.07 JU: Initial changes to Precess...() routines fixed; should work now.
#2018.04.08 JU: Changed settings for vState.MeridianSafety and vState.MeridianPast because they were too large and mount would stop first
#2018.04.28 JU: Added focuser temperature and position setting to Summary log when reporting exposure
#2018.09.02 JU: Adding SQLite3 features; see designs on laptop W510 in C:\Users\W510\Documents\SQLite
#2018.12.31 JU: Exec6D: added display of SideOfSky to Log2Summary for PP solve and exposure

#If FocusMax does not give good answer:
#   Option 1: calc absolute:  pos = -13*temp + 9750   [this changes over time]
#                             pos = -12.1*temp + 9250  (better) (configure for now)
#       Set_Focus_Parms=-12.1,9250
#
#   Option 2: store last good focus, pos1 = -13*(temp1-temp0) + pos0
# Do NOT use prgm startup pos/temp after 1st focus; it will be off; not equalized yet

#--------------
#Pier flip logic change (2017.02.18)
#   MeridianCross   execMeridianFlip
#   implExp_LightExposures  ->  MeridianCross       waits 0
#   MeridianSafety      waits 0.2 hours
#   TestForMeridianLimit
#   SideOfSky


#Enhancement idea: set flag so that when a time-limited step is executing, it will stop
# exactly at the specified time, instead of waiting for the end of the current exposure/sequence
# for stopping.


#("SET_SUBFRAME",      setSubFrame),
#("SET_FULLFRAME",     setFullFrame),

#--> add astrometric resync when using imager on AT66 (or anytime?)

#Idea: enhance cPosition class to support J1950 ?

#Issue: after the main imaging steps end and the first Park executes, I turn off the camera cooler at some point.
#       Then, when taking flats the cooler is turned back on but doesn't reach target temp while flats taken.
#*******



#IDEA: if Internet access enabled, grab the weather page and save as image file
# periodically, such as every 15 or 30 minutes
# http://aviationweather.gov/adds/satellite/displaySat.php?region=MSP&isingle=single&itype=ir
#(or, maybe just run a separate process on desktop PC all the time to capture
# these, and I can refer to them when desired.)
#From web page contents:  <img name="content" border="0" hspace="0" vpsace="0" align="center" src="/adds/data/satellite/20100825_2045_MSP_ir.jpg" title="Color IR satellite image for MSP valid at 2045 UTC Wed 25 Aug 2010" alt="Color IR satellite image for MSP valid at 2045 UTC Wed 25 Aug 2010">
#  Note the image address (for this example):  src="/adds/data/satellite/20100825_2045_MSP_ir.jpg"

#NOTE !!! For best results, take bias frames with flats for each session and use
#   those for calibration of that session. Darks can span sessions.  Also,
#   for best results take darks 5x as long as sub-exposures, so if I use 5 minutes
#   then dark 25 minutes, or 15 minutes Ha use 75 minutes; take at least 10 of each dark.

#TODO: if guiding fails to start, right now the code stops the current step
# and goes on to the next one. If the current step was to run all night and
# the next step is Park, it does not detect bad weather or sound the alarm.
# Right now only the time it detects bad weather is if PP-wide(?) fails
# many times during focus star selection?
#   ==> want to change this (or at least make configurable) so that it
#       does NOT stop current target, that it keeps retrying until sounding
#       bad weather alarm.
# Message:
#    ********************************************************
#    ** Failed to reacquire target after Bad Guiding event **
#    ********************************************************
#2017.07.24 JU: changed so that it goes into Weather exception to retry current step (at least I hope that is what it will do)


gCamera = "QSI-583"     #Values are: "QSI-583" or "ST-402" (default)

from an_client2 import Client    #for Astrometry.net

import pythoncom            #added 2013.10.02 JU
import win32com.client      #needed to load COM objects
import os
import math
import datetime
import time
import sys
import string

import subprocess
import threading

import ephem
import random   #used for RandomSafeLocation()

import sqlite3  #added 2018.09.02 JU

import imaging_db   #my code that implements DB functions:  imaging_db.py

import MultiPPSolve #added 2019.01.01 JU

#Exec4n.py 2015.12.13    DISABLED 2018.09.02
#import socket
#from inspect import currentframe, getframeinfo
def SendToServer( frameinfo, msg):
    return	#temp disabled 2016.02.01
 #   try:
 #       clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
 #       clientsocket.connect(('localhost', 8089))
 #       if msg == "EXIT":
 #           clientsocket.send(msg)
 #           clientsocket.shutdown(socket.SHUT_RDWR)
 #           clientsocket.close()
 #           return
#
#        prefix = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime( time.time() ) )
#        outmsg = "%s [%5d] : %s" % (prefix,frameinfo.lineno,msg)
#        clientsocket.send(outmsg)
#        clientsocket.shutdown(socket.SHUT_RDWR)
#        clientsocket.close()
#    except:
#        print "[Unable to send socket message]"

#2013.09.03 JU: added so I can dump content of Guider ctrl window, to help understand why guiding does not start sometimes
from winGuiAuto import *    #give access to Windows API calls from Python

#pyfits was used for "center-of-mass" logic, which did not work

BAD_WEATHER_THRESHOLD = 10  #if this many Wide PP failures in a row; maybe bad weather; halt and raise alarm!

FORCE_REFOCUS_TEMP_DIFF = 2      #usually want 4, but for testing make it extreme
FORCE_REFOCUS_TIME_DIFF = 30*60  #1/2 hour between refocus at least, to avoid doing it too often

RELOADFILE = 'EXEC_reload.txt'
#=======================================================================
# runMode controls access to hardware
#      .MAXIM available in all modes
#      .UTIL  available in all modes
# 1 = normal use, connects to real camera,mount,focuser hardware
# 2 = simulation, assumes mount,camera,focuser configured for simulator
#     (certain features skipped that do not work w/ the simulator)
#      .FOCUSCONTROL  -NOT- available
#      .FOCUSER       -NOT- available
# 3 = skip controls: does not access hardware at all; useful for testing
#      script without changing config to simulators
#      .CAMERA        -NOT- available
#      .MOUNT         -NOT- available
#      .FOCUSCONTROL  -NOT- available
#      .FOCUSER       -NOT- available
#global runMode
runMode     = 1     #used for testing software
#=======================================================================

#global UTIL
UTIL   = win32com.client.Dispatch("DriverHelper.Util")

#global errorCount
errorCount = 0  #count number of times the Error message written so far

global sObservingDateString
sObservingDateString = "99999999"	#undefined

global excessiveFocusRetries
excessiveFocusRetries = 0  #if focus fails consistently on differents stars

SIDE_GUIDER_TRAINED = 0  #Guiding was trained: 0=looking west/OTA east;  1=looking east/OTA west

global RecentGuideX
RecentGuideX = -99

global RecentGuideY
RecentGuideY = -99

global gGuidingXSum
gGuidingXSum = 0
global gGuidingYSum
gGuidingYSum = 0
global gGuidingCount
gGuidingCount = 0

global gGuidingXMax
gGuidingXMax = 0
global gGuidingYMax
gGuidingYMax = 0

global gGuiderState
gGuiderState = 0
# 0 = guider not running
# 1 = guider startup: finding guide star, or waiting for low guide error
# 2 = guider running

global gListStaleGuideData
global gListGuideXErrors
global gListGuideYErrors
gListStaleGuideData = []
gListGuideXErrors = []
gListGuideYErrors = []

global gSurveyCommandPresent
gSurveyCommandPresent = False

#
# Settings used with StatusWindow(obsolete) --------------------------------
global gFocusOccurredAt     #the GMT time when last refocus step occurred
gFocusOccurredAt = 0        #0 = refocus has not occurred yet

global gFocusPosition       #focuser position after last refocus
gFocusPosition = 0
global gFocusTemperature    #focuser temperature when last refocus done
gFocusTemperature = 0
global gFocusLastPosChange  #change in focuser position when last focus done
gFocusLastPosChange = 0
global gFocusLastTempChange #change in focuser temp between time of last focus and prev time
gFocusLastTempChange = 0

global gbAutoUntil
gbAutoUntil = False

global gAutoUntilType   #which category the current target is chosen from
gAutoUntilType = ""	#values: 'Survey','Mosaic','Deep','Default'

global gCurrentTarget
gCurrentTarget = "Target: ?"

global gSubstep
gSubstep = ""

#-------------------------------------------------------------

simulation  = False   #True = running w/ simulator; False = real hardware
            #READ THIS: changing from True to False --> MUST reset guider image size in Guider SETUP Dialog !!!
            #           Running w/ simulator changes guider size to 256x256; should be full size!!!

if gCamera == "QSI-583":
    imageScale = 0.48
else:
    imageScale  = 0.792 # arcsec/pixel expected for main imager [CHANGE THIS IF RECONFIGURING OPTICAL SETUP]
#imageScale  = 1.51 # arcsec/pixel expected for main imager [CHANGE THIS IF RECONFIGURING OPTICAL SETUP]
guiderScale = 3.822 # arcsec/pixel expected for guider [CHANGE THIS IF RECONFIGURING GUIDE CAMERA]
                    #These values are used to determine if a Pinpoint solve is reasonable.
                    #Common Image scale values:
                    # C9.25, f/10 (OAG in place):     0.792 arcsec/pixel
                    # C9.25, f/10 (OAG NOT in place): 0.80  arcsec/pixel  <-- current configuration
                    #   "    f/5  (focal reducer):    1.50  arcsec/pixel
                    # AT66, 0.33x Meade reducer:      7.45  arcsec/pixel
                    # AT66, no reducer                3.822 arcsec/pixel  <-- current configuration


#TargetList = []          #ordered in RA starting from 0; only contains unimaged targets
#NiceTargetList = []     #initially the same as TargetList[] but no entries deleted from it
SurveyList = []     #1st priority: objects without initial survey image
MosaicList = []     #2nd priority: objects designated for a mosaic
DeepList = []       #3rd priority: objects designed for deep image
DefaultList = []    #default: anything not in above 3 lists

IgnoreList = []     #used for building survey list

MasterList = r"J-Targets3.csv"      # r"J-Targets2.csv"

RecentImaged = r"RecentImaged.dat"
gLastFocus = r"LastFocus.dat"
FocusStarFile = r"FocusStarsD.csv"

global maxRA
maxRA = 0

SCALE_THRESHOLD_PCT = 30  #This is a percentage (ex 30 for 30%)

FOV_Offsets = []       #record tuples of (RA,Dec) offset measurements of FOV offset (decimal hours, decimal degrees)
FocusStarList = []     #ordered in RA starting from 0; stars mag 4.5-6 and dec 20-70
IgnoreFocusStars = []  #names of focus stars that failed current session, to prevent re-use in this session again

MasterCoords = {}       #used to store object names/coords read from target spreadsheet, as alternate lookup source to MiniSAC

MPL_cache = {}      #used to cache MPL pos objects so use same value successive calls
#---------------------------------
#Global classes
class EnvironmentError( Exception ):
   pass

class ValidationError( Exception ):
   pass

class SoundAlarmError( Exception ):
   pass

class WeatherError( Exception ):
   pass

class HorizonError( Exception ):    #throw if current target is below western tree horizon, to stop trying to image it
   pass

class ArgumentError(Exception):
    pass    #used when parsing command arguments for one command to execute
#--------------------------------

class cState:
    def Reset(self):
        self.MeridianSafety = 0.15     #interrupt current exposure if this far past meridian
        self.MeridianPast = 0.1       #do not start new exposure if this far past meridian
        #2018.04.08 JU: changed above; was 0.3, 0.2 but even at 0.2 the mount was stopping first because of meridian limit, so need smaller values
        self.guide         = 0        #0=no, 1=yes for guiding during exposures
        self.GuidingSettleThreshold = 0.4
        self.GuidingSettleTime      = 120

        self.GuideAutoStarSelect    = True   #if false, then use next values
        self.GuideExcludeTop        = 60    #2013.07.13 JU: these were 32; changed to 60 (I suspect 40 is too small)
        self.GuideExcludeBottom     = 60
        self.GuideExcludeLeft       = 60
        self.GuideExcludeRight      = 60
        self.GuideExcludeReverse    = False  #if true, exclude middle of image and use edges

        #2012.06.15 JU: new feature: keep track of offset between center of guider and imager,
        # so that PP solve/slew of guider will center the imager.  I've seen this offset vary
        # by 15 arcsec by slewing across the sky due to flexure, but if I can get within 1 arcmin
        # of imager center using just Guider PP solves then this will save time.
        self.GuiderRAOffsetArcsec   = 0     #note that the RA value is arc-seconds, not seconds!
        self.GuiderDecOffsetArcsec  = 0

        #NOT USED
        self.AstrometricResyncNumber = 0 #0=disabled, 1=every imager image, 2=every other image, etc
        self.AstrometricResyncBackcount = 0 #0=use most recent image for PP solve, 1=penultimate image, etc

        self.guide_exp     = 4        #seconds exposure when guiding, for guide camera
        if runMode == 1:
           #normal operation
            self.sequence      = pathSeq + "_LLRGB_300sec-1.seq"  #default sequence to use
            self.sequence_time = 1512    #estimated duration of sequence (from MaxIm camera dialog)
        elif runMode == 2:
           #simulator
            self.sequence      = pathSeq + "_LLRGB_1sec-1.seq"
            self.sequence_time = 17
        else:
           #testing, no hardware or simulator
            self.sequence      = pathSeq + "_LLRGB_1sec-1.seq"
            self.sequence_time = 17
        self.path          = "C:\\fits\\"   #directory to write image files to
        self.path_dark_bias_flat    = "C:\\fits\\DBF\\"
        self.exposure      = 10       #default exposure
        self.repeat        = 1        #number of repeated EXP on one target (does NOT apply to sequences)
        self.sleep         = 15       #IGNORE, replaced w/ test looking for movement
        self.filter        = 3        #0=red,1=green,2=blue,3=luminance(clear) [field always number]
#THE ABOVE VALUE MAY NEVER BE USED
        self.min_altitude  = 0        #minimum altitude below which imaging will not occur (value should be < 60 or few targets will be available)

        self.scriptStartTime = time.time() #actual time when script started executing
        self.stepStartTime   = time.time()   #time when currently executed step started executing
        self.pinpoint_success = 0
        self.pinpoint_successive_wide_failures = 0
        self.goto_count       = 0
        self.focus_count      = 0
        self.below_horizon_count = 0
        self.focus_failed_count  = 0
        self.guide_count         = 0
        self.guide_failure_count = 0
        self.guide_shutdown_failure_count = 0
        self.exception_count     = 0
        self.excessive_slew_time_count = 0

        self.FixGuidingStateSetting = 0    #set using  Set_FixGuidingState=n

        self.WaitIfCloudy = False           #default value; set using Set_WaitIfCloudy=Y|N

        self.GuideSettleBumpEnable    = 0    #0=disable, 1=enable [ignore rest of parms below if disabled]
        self.GuideSettleBumpDirection = 0    #0=north for positive Yerr, 1=north for Negative Yerr
        self.GuideSettleBumpAmount    = 3    #arcsec to bump (usually 3)
        self.GuideSettleBumpThreshold = 1.0  #guide error pixels before trying bump
        self.GuideSettleBumpDelay     = 3    #guide cycles after attempt before trying again

        self.flush = 0
        self.flush_cnt = 1
        self.LogStatusCount = 11    #force it to log the 1st time it StatusLog is called

        self.ppState = [PP_State(),PP_State()]
        self.ppState[0].Reset(0)
        self.ppState[1].Reset(1)

##        #overall enable/slope for focusing temperature compensation
##        self.temp_comp       = 0    #DISABLE: overall enable temp comp (blind focus change)
##        self.temp_comp_slope = -3.2
##        self.temp_refocus    = 0    #control refocus based on temp change <DOESN'T WORK WELL, LEAVE DISABLED>

        self.focusEnable = True

        #During guiding, if the scope position moves by more than this amount (arcmin) from
        # the initial GOTO position, then stop the current exposure and reacquire target;
        # we have robably lost the guide star.
        self.driftThreshold = 6.0   #was 5.0   #was 4.0     Changed to 6.0 on 2019.03.05 JU
        self.gotoPosition = Position()
        self.gotoPosition.isValid = False

##        #flag whether temp comp has been enabled yet for current run (need to have focus event to enable)
##        self.TempCompPosition = 0
##        self.TempCompTemperature = 0
##        self.TempMeasureTime = time.time() - 86400  #record when these values last set; set time in the past to force initial refocus

        #if a pier limit is reached DURING an exposure:, this controls whether we
        # do a pier flip and reacquire the same target and CONTINUE on the same
        # target.
        #True: do a pier flip, re-measure imager offset (if using imager) on a bright
        #      star (and optionally refocusing at this point), and then reacquire
        #      the same target and continue imaging.
        #False: stop imaging this target and move on to the next one. If this is
        #       in survey mode, it will pick the next target at this point; if
        #       executing a list of targets, it moves on to the next step in the list.
        self.bContinueAfterPierFlip = False

        self.ImagerScale = 0.48 #default: QSI on C9.25 f/10
        self.GuiderScale = 3.82 #default: Atik on AT66 refractor

        #This can be set from command file: Set_Astrometry.net=1
        self.AstrometryNet = 0  #Set_Astrometry.net=1	#0=disable, 1=use after 2 failures of PP solve, 2=use all the time(disable all PP solves)

        self.FlatAltitudeMorning = -3.3
        self.FlatAltitudeEvening = -2   #guess value

        #Measured offset between center of guider and center of imager, in pixels for the Imager
        #These are set in CalibrateImagerOffset(), which is called each time FocusMax is run, after it is run
        self.Offset_active = False  #only use following fields if Offset_active is True
        self.X_offset = 0
        self.Y_offset = 0
        self.Offset_SideOfPier = 0  #which side of pier the offsets measured on
        self.Offset_RAused = 0.     #decimal RA JNow where offset measured
        self.Offset_DECused = 0.    #  "     DEC         "
        self.Offset_Altitude = 0.   #Altitude where offset measured
        self.Offset_Azimuth  = 0.   #Azimuth    "
        self.Offset_TimeSet = time.time()

    def ResetGuiderExclude(self):   #call this so MaxIm picks guide star automatically;
        self.GuideAutoStarSelect    = True   #if false, then use next values
        self.GuideExcludeTop        = 32
        self.GuideExcludeBottom     = 32
        self.GuideExcludeLeft       = 32
        self.GuideExcludeRight      = 32
        self.GuideExcludeReverse    = False  #if true, exclude middle of image and use edges

    def ResetImagerOffset(self):
        #This is called for steps that want the GUIDER to be exactly centered on the
        # specified target. This would be for Wide field images, and all Focus steps.
        #(I also plan to add specific command to measure offset w/o running focuser.)
        # Note that the Focus steps all result in these offsets being remeasured against
        # the focus star after FocusMax runs.
        self.Offset_active = False  #only use following fields if Offset_active is True
        self.X_offset = 0
        self.Y_offset = 0
        self.Offset_SideOfPier = 0
        self.Offset_RAused = 0.     #JNow
        self.Offset_DECused = 0.    #JNow
        self.Offset_Altitude = 0.
        self.Offset_Azimuth  = 0.
        self.Offset_TimeSet = time.time()
        Log2(0,"=========<Reset imager offset measurements>============")

    def DumpImagerOffset(self):
        lvl = 2
        if not self.Offset_active:
           Log2(lvl,"-----------------------------------------------")
           Log2(lvl,"- !!Imager offset dump called when INACTIVE!! -")
           Log2(lvl,"-----------------------------------------------")
        else:
           Log2(lvl,"----------------------------------------------------")
           Log2(lvl,"- Imager offset:  X = %+03d,  Y = %+03d                -" % (self.X_offset,self.Y_offset))
           Log2(lvl,"-   Measured at:  %s UT (%3d seconds ago)   -" % (time.strftime("%H:%M:%S ", time.gmtime()), int(time.time() - self.Offset_TimeSet) ))
           Log2(lvl,"-   Measured at:  RA=%s, Dec=%s      -" % (UTIL.HoursToHMS(self.Offset_RAused,":",":","",1),DegreesToDMS(self.Offset_DECused)))
           Log2(lvl,"-   Measured at:  altitude=%4.1f, azimuth=%5.1f     -" % (self.Offset_Altitude,self.Offset_Azimuth))
           try:
              curAlt = self.MOUNT.Altitude
              curAz  = self.MOUNT.Azimuth
              Log2(lvl,"-      Current:            %4.1f          %5.1f     -" % (curAlt,curAz))
              Log2(lvl,"-   Difference:           %+5.1f         %+6.1f     -" % (self.Offset_Altitude - curAlt, self.Offset_Azimuth - curAz))
           except:
              Log2(lvl,"-                (current alt/az not available)     -")

           if self.Offset_SideOfPier == 1:
               Log2(lvl,"- Measured SOP:  1 (OTA west, looking east)        -")
           elif self.Offset_SideOfPier == 0:
               Log2(lvl,"- Measured SOP:  0 (OTA east, looking west)        -")
           else:
               Log2(lvl,"- Measured SOP:  side of pier was unknown??        -")
           try:
               if self.MOUNT.SideOfPier == 1:
                   Log2(lvl,"-  Current Side of pier:  1 (OTA west, looking east)        -")
               else:
                   Log2(lvl,"-  Current Side of pier:  0 (OTA east, looking west)      -")
               if SideOfSky(self) == 1:
                   Log2(lvl,"-  Current Side of sky:  1 (OTA west, looking east)        -")
               else:
                   Log2(lvl,"-  Current Side of sky:  0 (OTA east, looking west)      -")

           except:
               Log2(lvl,"-  Current SOP:  cannot be determined??           -")
           Log2(lvl,"----------------------------------------------------")
        Log2(lvl," ")

#--------------------------------------------------
#Imager offset:  X = +09,  Y = -03                -
# Measured SOP:  1 (OTA west, looking east)       -
#  Current SOP:  1
#  Measured at:  06:59:59 UT (999 seconds ago)    -
#  Measured at:  RA=23:59:59, Dec=59:59:59 J2000  -
#  Measured at:  altitude=99.9, azimuth=179.9     -
#      Current:           99.9          199.9     -
#   Difference:          -99.9         -299.9     -
#--------------------------------------------------

    def __init__(self):
        self.Reset()

        #SQLite3 connection
        self.SQLITE = sqlite3.connect( Observatory_Database )   #this is only accessed by script: imaging_db.py
        self.SQMASTER = sqlite3.connect( Master_Database )
        imaging_db.SqliteStartup( self.SQMASTER, 'Exec5D-startup' )    #record start of prgm in Startup table of database

        # COM objects
        print "Connect: DriverHelper.Util"
        self.UTIL   = win32com.client.Dispatch("DriverHelper.Util")
        print "runMode = ",runMode

        #Note: MiniSAC catalog only connected when needed and then disconnected

        if runMode == 1 or runMode == 2:
           print "Connect: MaxIm.CCDCamera"
           self.CAMERA = win32com.client.Dispatch("MaxIm.CCDCamera")
           self.CAMERA.DisableAutoShutdown = True
           print "... turn on camera link"
           try:
               self.CAMERA.LinkEnabled = True
           except:
               print "... cannot connect to camera"
               print "--> Is camera hardware attached?"
               print "--> Is something else already using camera hardware?\n"
               raise EnvironmentError,'Halting program'

           #set initial cropping to full frame size
           self.CropX = 0
           self.CropY = 0
           self.CropWidth = self.CAMERA.CameraXSize
           self.CropHeight = self.CAMERA.CameraYSize

           if not self.CAMERA.LinkEnabled:
               print "... camera link DID NOT TURN ON; CANNOT CONTINUE"
               raise EnvironmentError,'Halting program'

           #make sure the cooler is on, just in case
           try:
               if not self.CAMERA.CoolerOn:
                   self.CAMERA.CoolerOn = True
           except:
               pass
        else:
            print "Bypassing camera connection, runMode =",runMode

        #verify that guider is set to correct size. Whenever it is
        # run in Simulation mode, the driver changes the size to 256x256
        # but it doesn't change back automatically. This checks whether
        # the size is wrong and stops the script if it is
        if runMode == 1:
          self.CAMERA.BinX = 1
          self.CAMERA.BinY = 1
          if self.CAMERA.CameraXSize != 3326 or self.CAMERA.CameraYSize != 2504:
            print "CameraXSize=",self.CAMERA.CameraXSize
            print "CameraYSize=",self.CAMERA.CameraYSize
            print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            print "!!! MAIN IMAGER (Camera #1) size needs to be reconfigured"
            print "!!! Go to Camera window, Expose Tab, Subframe, Camera 1 "
            print "!!!    Expand to full size and then disable subframe."
            print "!!! Should be 3326 x 2504"
            print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            raise EnvironmentError,'Halting program'
          self.CAMERA.BinX = 2  #set back to 2x2 for normal use
          self.CAMERA.BinY = 2


          self.CAMERA.GuiderBinning = 1
          if self.CAMERA.GuiderXSize < 100 or self.CAMERA.GuiderYSize < 100:
            print "GuiderXSize=",self.CAMERA.GuiderXSize
            print "GuiderYSize=",self.CAMERA.GuiderYSize
            print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            print "!!! Guider size needs to be reconfigured"
            print "!!! Go to Camera window, Expose Tab, Subframe, Camera 2"
            print "!!!    Expand to full size and then disable subframe."
            #print "!!! Should be 659 x 494"
            print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            raise EnvironmentError,'Halting program'

        print "Connect: MaxIm.Application"
        self.MAXIM    = win32com.client.Dispatch("MaxIm.Application")
        print "ConnectMaxIm to telescope mount (so it can scale guiding for Dec correctly)"
        self.MAXIM.TelescopeConnected = True
        print "...after command to connect MaxIm to telescope"

        #2012.01.06 JU: read MaxIm version number to decide certain env issues
        verNo = self.MAXIM.Version      #values 5.08, 4.62
        verNoInt = int(verNo)
        if verNoInt > 4:
            global pathSeq
            pathSeq      = "C:\\fits_seq5\\"          #stores pre-defined sequences
            print ">>> using sequence path for MaxIm version 5<<<"

        #self.MAXIMDOC = win32com.client.Dispatch("MaxIm.Document")
        #The above line may be needed if I want to open up FITS images (in MaxIm)
        # eventually and fix their header info. If I do connect to it here, this
        # is what causes an empty document to open up each time the script is run.
        # For now, disable this command.

        if runMode == 2:
            print "Connect: ScopeSim.Telescope"
            self.MOUNT  = win32com.client.Dispatch("ScopeSim.Telescope")
            print "... turn on mount link"
            self.MOUNT.Connected = True
        elif runMode == 1:
            print "Connect: Gemini.Telescope"
            try:
#                self.MOUNT  = win32com.client.Dispatch("Poth.Telescope")
                self.MOUNT  = win32com.client.Dispatch("ASCOM.GeminiTelescope.Telescope")
                print "... turn on mount link"
                self.MOUNT.Connected = True

				#2016.06.06 JU: new feature: 162 = put hand controller into "Photo" mode (or use 163 for "All Speeds" Mode)
				#NOTE: this uses a "Native" Gemini command; all the other calls to CommandBlind use the "Meade" command subset protocol.
                print "... set hand controller to Photo mode"
                self.MOUNT.CommandBlind(">162:",False)
            except:
                print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                print "--> Cannot connect to Gemini/POTH"
                print "--> Is the hardware plugged in?"
                print "--> Is some other software connected to Gemini"
                print "--> [if previously aborted script, run Task Manager and kill orphan Gemini process]"
                print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                raise EnvironmentError,'Halting program'
        else:
           print "No scope connected, runMode =",runMode

        if runMode == 1:
           print "... connect to FocusMax"
           self.FOCUSCONTROL  = win32com.client.Dispatch("FocusMax.FocusControl")
           self.FOCUSER       = win32com.client.Dispatch("FocusMax.Focuser")

        self.WesternHaltAltitude = 0    # degrees above western horizon to stop an exposure; set via Set_HaltAltitude=nn degrees

        self.FocusCompensationActive = 0    # 0 = False    #this is turned on with a config Setting
        self.AdvancedFocusState = -1
        self.AdvancedFocusStartTime = time.time()   #this variable will be reset to a new time before it is used later
        self.FocusDataAvailable = False
        self.FocusSlope = -12.1     #TODO: make this configurable?
        try:
            self.LastFocusPosition = self.FOCUSER.Position
            self.LastFocusTemperature = self.FOCUSER.Temperature
            self.FocusDataAvailable = True
            Log2(0,"Setting LastFocusPosition initial value = %d" % self.LastFocusPosition)
        except:
            Log2(0,"Exception thrown trying to read initial Focus position/temperature")
            niceLogExceptionInfo()


        ## If the above statement throws an exception, the PC may be
        ## in a bad state; try rebooting it.  Also, before running
        ## the script, make sure MaxIm is running, and camera is connected
        ## (cooler on probably) but not exposing.
        if runMode == 1 or runMode == 2:
           print "... unpark and start tracking"
           self.MOUNT.Unpark()
           self.MOUNT.Tracking = True

           if self.MOUNT.Connected:
               Log2(0,"Connected to mount")
           else:
               Log2(0,"PROBLEM: unable to connect to mount")
#=====================================================================================
class cSequenceRow:
   def __init__(self):
    self.index = 0  #may not need this
    #self.active = True #only active rows loaded here
    self.type = 0   #0=light, 1=bias, 2=dark, 3=flat
    self.filter = 0 #RGBLHa  0..4
    self.suffix = "xxx"
    self.exposure = 0.0 #seconds
    self.binning = 1
    self.repeat = 1

# ===>> check to see if MaxIm version 5 has different sequence format!!!

class cSequence:
    def __init__(self):
        self.Order = 0      #1=group by slot
        self.Delay = 0      #IGNORE delay between exposures in the sequence
        self.StartDelay = 0 #IGNORE delay before starting sequence
        self.LockRepeat = 0 #1=same repeat count for all; use RepeatAll value
        self.LockScript = 0 #IGNORE 1=same script for all; use ScriptAll value
        self.RepeatAll = 1  #count used if LockRepeat = 1
        self.ScriptAll = "" #IGNORE
        #Note: ignore delay values because we monitor the guiding
        #and won't start an exposure until it settles

        #How repeats work if Order = 0:
        # 1. Expose each slot once
        # 2. If there are any slots with repeat counts > 1,
        #    expose all of these slots
        # 3. Continue with higher count slots until all counts satisfied

        #List[cSequenceRow] #multiple entries, 1 per exposure
        self.slots = []  #store the cSequenceRow objects here
        self.slot_cnt = 0   #how many slots defined

    def ClearSequence(self):
        self.slots = []
        self.slot_cnt = 0

    def LoadSequence(self,filename):
        #todo
        pass


    #helper method to read sequence file, maybe the constructor?

#=====================================================================================
cTypeUnknown = 0     #Undetermined
cTypeCatalog = 1     #This coord was obtained from a catalog (including user provided coords); we probably want to go to this location
cTypeReported = 2    #This coord was reported by the mount (may be inaccurate)
cTypeSolved = 3      #This coord was obtained from Pinpoint solving an image
class Position:
    def __init__(self):
        #declare variables used to store position, and description of the position
        #These are ephem.angle objects; value stored in both epochs
        self.__posJ2000 = None      # this is an ephem.Angle object
        self.__posJNow = None       #  "            "
        self.posName = "n/a"        #Name of object this coord is for
        self.posType = cTypeUnknown #This is set to one of the constants above  (FEATURE NEVER REALLY USED)
        self.isValid = False
        self.orig_epoch = None      #original epoch; this may be set to ephem.J2000 or ephem.now() (which varies)

    def dump(self):  #returns long string that can be printed
       ret = "\n"
       if not self.isValid:
          ret += "[NOT VALID] "
       raJNow,decJNow   = self.getJNowString()
       raJ2000,decJ2000 = self.getJ2000String()
       ret +=  "Position dump:\n"
       ret += "Name:  %s\n" % (self.posName)
       ret += "J2000: %s  %s\n" % (raJ2000, decJ2000)
       ret += "JNow:  %s  %s\n" % (raJNow, decJNow)
       return ret

    def dump2(self):  #returns 2 string tuple that can be printed in a log
       ret = "\n"
       if not self.isValid:
          return ("THIS OBJECT IS NOT VALID!","THIS OBJECT IS NOT VALID!")
       raJNow,decJNow   = self.getJNowString()
       raJ2000,decJ2000 = self.getJ2000String()

       # Catalog Lookup    RA--JNow--Dec       RA--J2000--Dec  Name: ssssssss
       #                 00:00:00 +00:00:00  00:00:00 +00:00:00
       line0 = " Cat Lkp    RA--JNow--Dec       RA--J2000--Dec      Name:"
       line1 = "          %s %s  %s %s    %s" % (raJNow, decJNow, raJ2000, decJ2000, self.posName)
       return (line0,line1)

    def dump3(self):  #returns strings that can be printed in target log
       ret = "\n"
       if not self.isValid:
          return "THIS OBJECT IS NOT VALID!"
       raJNow,decJNow   = self.getJNowString()
       raJ2000,decJ2000 = self.getJ2000String()

       # Catalog Lookup    RA--JNow--Dec       RA--J2000--Dec    Name:     ssssssss
       #                 00:00:00 +00:00:00  00:00:00 +00:00:00
       #line0 = " RA--JNow--Dec       RA--J2000--Dec    Name:     %s" % (self.posName)
       line1 = " %s %s  %s %s    %s" % (raJNow, decJNow, raJ2000, decJ2000, self.posName)
       return line1

    def setDecimal(self,dhRA,ddDec,epoch,name=None,ptype=None):
        #Input coords are decimal hours, decimal degrees
        #Ex. 12.51234,-23.97654
        #epoch = ephem.J2000 or ephem.now()  [if not ephem.J2000 it ASSUMES ephem.now(); don't use any other epochs]
        #Future enhancement: support for 'B1900', 'B1950'
        #print "*** setDecimal called with:",dhRA,ddDec,epoch,name
        self.orig_epoch = epoch
        if epoch == ephem.J2000:
            self.__posJ2000 = ephem.Equatorial(hours2rad(dhRA),deg2rad(ddDec),epoch=ephem.J2000)
            #print "ephem J2000:   ",self.__posJ2000.ra,self.__posJ2000.dec
            self.__posJNow  = ephem.Equatorial(self.__posJ2000,epoch=ephem.now())
            #print "converted JNow:",self.__posJNow.ra,self.__posJNow.dec
        else:
            self.__posJNow = ephem.Equatorial(hours2rad(dhRA),deg2rad(ddDec),epoch=ephem.now())
            #print "ephem JNow:     ",self.__posJNow.ra,self.__posJNow.dec
            self.__posJ2000 = ephem.Equatorial(self.__posJNow,epoch=ephem.J2000)
            #print "converted J2000:",self.__posJ2000.ra,self.__posJ2000.dec
        if name == None:    self.posName = None
        else:               self.posName = name
        if ptype == None:   self.posType = cTypeUnknown
        else:               self.posType = ptype
        self.isValid = True

    def setString(self,shRA,sdDec,epoch,name=None,ptype=None):
        #Input coords are strings: RA is hours:minutes:seconds, Dec is degrees:minutes:seconds
        #Ex: '12:34:56','-89:11:22'
        #epoch = ephem.J2000 or ephem.now()  [if not ephem.J2000 it ASSUMES ephem.now(); don't use any other epochs]
        #print "***setString called with:",shRA,sdDec,epoch,name
        self.orig_epoch = epoch
        if epoch == ephem.J2000:
            self.__posJ2000 = ephem.Equatorial(shRA,sdDec,epoch=ephem.J2000)
            #print "ephem J2000:   ",self.__posJ2000.ra,self.__posJ2000.dec
            self.__posJNow  = ephem.Equatorial(self.__posJ2000,epoch=ephem.now())
            #print "converted JNow:",self.__posJNow.ra,self.__posJNow.dec
        else:
            self.__posJNow = ephem.Equatorial(shRA,sdDec,epoch=ephem.now())
            #print "ephem JNow:",self.__posJNow.ra,self.__posJNow.dec
            self.__posJ2000 = ephem.Equatorial(self.__posJNow,epoch=ephem.J2000)
            #print "converted J2000:",self.__posJ2000.ra,self.__posJ2000.dec
        if name == None:    self.posName = None
        else:               self.posName = name
        if ptype == None:   self.posType = cTypeUnknown
        else:               self.posType = ptype
        self.isValid = True

    #Input formats for coords below:
    #   Decimal hours [0.0 ... 23.999)    dhRA***       dhRAJ2000 or dhRAJNow
    #   Decimal degrees (-90.0 ... +90.0) ddDec***      ddDecJ2000 or ddDecJNow
    #   string hours (ex '12:34:56')      shRa***       shRAJ2000 or shRAJNow
    #   string degrees (ex '-89:12:34')   sdDec***      sdDecJ2000 or sdDecJNow

    def setJ2000Decimal(self,dhRAJ2000,ddDecJ2000,name=None,ptype=None): ##Decimal coords input
        self.setDecimal(dhRAJ2000,ddDecJ2000,ephem.J2000,name,ptype)

    def setJ2000String(self,shRAJ2000,sdDecJ2000,name=None,ptype=None):
        #print "setJ2000String",shRAJ2000,sdDecJ2000
        try:
            self.setString(shRAJ2000,sdDecJ2000,ephem.J2000,name,ptype)
        except Exception,e:
            print str(e)

    def setJNowDecimal(self,dhRAJNow,ddDecJNow,name=None,ptype=None):
        self.setDecimal(dhRAJNow,ddDecJNow,ephem.now(),name,ptype)

    def setJNowString(self,shRAJNow,sdDecJNow,name=None,ptype=None):
        self.setString(shRAJNow,sdDecJNow,ephem.now(),name,ptype)

    def getJ2000Decimal(self):  #returns decimal hours, decimal degrees, epoch J2000
        return(rad2hours(self.__posJ2000.ra), rad2deg(self.__posJ2000.dec))

    def getJNowDecimal(self):  #returns decimal hours, decimal degrees, epoch JNow
        return(rad2hours(self.__posJNow.ra), rad2deg(self.__posJNow.dec))

    def getJ2000String(self):   #returns strings in hh:mm:ss, dd:mm:ss format, epoch=J2000
        return(Cleanup(ephem.hours(self.__posJ2000.ra)),FixDecSign(Cleanup(ephem.degrees(self.__posJ2000.dec))))

    def getJNowString(self):   #returns strings in hh:mm:ss, dd:mm:ss format, epoch=J2000
        return(Cleanup(ephem.hours(self.__posJNow.ra)),FixDecSign(Cleanup(ephem.degrees(self.__posJNow.dec))))

    #sometimes need these values separately
    def dRA_J2000(self):
        return rad2hours(self.__posJ2000.ra)
    def dDec_J2000(self):
        return rad2deg(self.__posJ2000.dec)
    def dRA_JNow(self):
        return rad2hours(self.__posJNow.ra)
    def dDec_JNow(self):
        return rad2deg(self.__posJNow.dec)

    #also like logging feature for values

#=====================================================================================
class PP_State:
    def __init__(self):
        self.active          = 0
        self.exposure        = 30
        self.binning         = 1
        self.exp_increment   = 2
        self.retry           = 2
        self.precision       = 0       #how close in arcminutes to desired location, 0=ignore
        self.require_solve   = 0
        self.CatalogID       = 3        #3=GSC, 5=USNO_A2.0(6GB)
        self.CatMaxMag       = 16
        self.MaxSolveTime    = 60
        #self.SigmaAboveMean  = 2.0
        self.SigmaAboveMean  = 3.0       #2011.08.11 I had this 2.0, but try using default again

    def Dump_State(self):
        #print "$$$$$$$$$$ Dump_State $$$$$$$"
        print "PP_State dump:"
        print "   Active         : %d" % (self.active)
        print "   Exposure       : %5.2f" % (self.exposure)
        print "   Exp_increment  : %5.2f" % (self.exp_increment)
        print "   Retry          : %d" % (self.retry)
        print "   Precision      : %5.2f" % (self.precision)
        print "   Require_solve  : %d" % (self.require_solve)

    def Reset(self,camera):
        if camera == 1:    #Guider
           #setup guider defaults and settings
           #self.image_scale = guiderScale
           self.exposure    = 10
           self.retry   = 1
           self.active      = 1
           self.require_solve = 1
           self.CatalogID       = 3        #3=GSC, 5=USNO_A2.0(6GB)
           self.CatMaxMag       = 16
           self.MaxSolveTime    = 60
           self.SigmaAboveMean  = 3.0       #2011.08.11 I had this 2.0, but try using default again
        else:
           #setup imager values
           #self.image_scale  = imageScale
           self.retry    = 2
           self.exposure     = 30
           self.active       = 0
           self.require_solve = 0
           self.CatalogID       = 5        #3=GSC, 5=USNO_A2.0(6GB)
           self.CatMaxMag       = 18
           self.MaxSolveTime    = 90
           self.SigmaAboveMean  = 3.0

#--------------------------------
#Global variables
CatalogLookupFailures = []      #define at global scope
logFile        = r"C:\fits_script\Log2.txt"  #output for logging (gets modified to append date: ExecLogFile_yyyymmdd.txt
logAllFile     = r"C:\fits_script\Log2All.txt"  #output for all details logging (gets modified to append date: ExecLogFile_yyyymmdd.txt
logSummaryFile = r"C:\fits_script\Log2Summary.txt"  #output for all details logging (gets modified to append date: ExecLogFile_yyyymmdd.txt

CommandList    = r"C:\fits_script\Exec4.txt"            #DEFAULT input file for commands
MOVEMENT_LOG   = r"C:\fits_script\Log2Movement.txt"
PINPOINT_LOG   = r"C:\fits_script\Log2Pinpoint.txt"
PINPOINT_SOLVE = r"C:\fits_script\Log2PinpointSolve.txt"
FOCUSER_LOG    = r"C:\fits_script\Log2Focuser.txt"
PERM_FOCUSER_LOG    = r"C:\fits_script\Log2Focuser.LOG" #this is a permanent file, not daily
STATUS_LOG     = r"C:\fits_script\Log2Status.txt"
FOV_LOG        = r"C:\fits_script\FOV2Offset.txt"
TARGET_LOG     = r"C:\fits_script\Log2Targets.txt"      #reports all catalog lookups
GUIDING_LOG    = r"C:\fits_script\Log2Guiding.txt"
PERM_FWHM_LOG  = r"C:\fits_script\Log2FWHM.txt"         #this is a permanent file, not daily

#Define Paths used in the program
pathFits     = "C:\\fits\\"              #NOT USED   (not sure if I want to use this?)
pathCalib    = "Calib\\"                 #NOT USED   stores auto-calibrated images; path is appended to pathFits
pathSeq      = "C:\\fits_seq\\"          #stores pre-defined sequences
pathScript   = "C:\\fits_script\\"       #NOT USED   stores the Exec.txt execution script
pathGuider   = "C:\\fits_guider\\"       #preserve guider field location images (for diagnostics)
pathPinpoint = "C:\\fits_pinpoint\\"     #preserve images used for Pinpoint solve & sync; also for Bright Star images to get coord offset

LIVE           = True     #used for test pass through script (do not modify this; program controls it)
SkipTestForMeridianLimit = False    #set based on side of pier (do not modify this)

myLongitude = -(87 + (49.937/60.))
myLatitude  = 42 + (8.185/60.)
#----------------

#=====================================================================================
#==== SECTION  @@Log =================================================================
#=====================================================================================
def ObservingDateString():
	global sObservingDateString
	return sObservingDateString

def ObservingDateSet():
	#get current date GMT; if hours > 20 then add 4 hours to make into next date
	#then return string "_YYYYMMDD" that can be used as part of a daily log filename

	iDateTime = datetime.datetime.utcnow()
	iHours = time.gmtime().tm_hour	#easier to test this way
	if iHours > 20:
		iDateTime += datetime.timedelta(hours = 4)	#push to next date
	value = iDateTime.strftime("%Y%m%d")
	#print "ObservingDateString = %s" % value

	global sObservingDateString
	sObservingDateString = value


def StatusLog(value):
    sDateStr = ObservingDateString()	# time.strftime('_%Y%m%d.txt',iDateTime)
    statusLogName = STATUS_LOG[:-4] + "_" + sDateStr + ".txt"   #2018.01.19 JU: why did this NOT have file suffix .txt??? Added it now. Also changed base filename from Status2.txt to Log2Status.txt
    fs = open( statusLogName, "a" )
    fs.write(value + "\n")
    fs.close()
    Log2(4,value)   #put the status lines in the overall log file also

#--------------------------------
def StatusWindowSimple(value):   #common code
    pass

#--------------------------------
def StatusWindow(attribute,value,vState):   #this needs vState to exist
    pass

#--------------------------------
def LogPerm(value,filex):   #does NOT have daily log files; all entries to one master file
    prefix = time.strftime("%Y/%m/%d %H:%M:%S ", time.localtime( time.time() ) )

    if value.endswith("\n"):
        value = value[:-1]

    try:
       f = open( filex, "a" )
       f.write(prefix + value)
       f.write("\n")
       f.close()
    except:
       #print "UNABLE TO WRITE TO LOG FILE:",filex[:-4] + sDateStr, value
       niceLogExceptionInfo()
       print "LogBase: UNABLE TO WRITE TO LOG FILE:"
       print "Filename:",filex
       print "Log line:", value

    return prefix   #return prefix so it can be printed on the screen if called by Log()

#--------------------------------
def LogBase(value,filex):   #common code

    #build the date component of the filename
    iDateTime = time.gmtime()    #Change: include date as part of logfile name
    sDateStr = "_" + ObservingDateString() + ".txt"	# time.strftime('_%Y%m%d.txt',iDateTime)

    #f = open( file, "a" )
    prefix = time.strftime("%H:%M:%S ", time.localtime( time.time() ) )

    if value.endswith("\n"):
        value = value[:-1]

    #write all entries to today's log file:
    try:
       f = open( filex[:-4] + sDateStr, "a" )
       f.write(prefix + value)
       f.write("\n")
       f.close()
    except:
       #print "UNABLE TO WRITE TO LOG FILE:",filex[:-4] + sDateStr, value
       nicePrintExceptionInfo()
       print "LogBase: UNABLE TO WRITE TO LOG FILE:"
       print "Filename:",filex[:-4] + sDateStr
       print "Log line:", value


    return prefix   #return prefix so it can be printed on the screen if called by Log()

#--------------------------------

def Log2Summary(level,value):	#summary event log (as of 2016.06.15 JU)
    #level = what level of detail to output to the screen and regular log file; level values typically 0,1,2
    # each level has one (1) additional space before log text (for indenting)

    #build the filename
    iDateTime = time.gmtime()    #Change: include date as part of logfile name
#------======================================================================
#TODO: if time hours is > 20h, advance to next day to keep log files together
#------======================================================================
    sDateStr = "_" + ObservingDateString() + ".txt"	# time.strftime('_%Y%m%d.txt',iDateTime)
    #prepend spaces depending on log level
    for i in range(level):
        value = " " + value

	#build the full line including timestamp
    prefix = time.strftime("%H:%M:%S ", time.localtime( time.time() ) )
    if value.endswith("\n"):
        value = value[:-1]
    value = prefix + value

    #write string to summary log file:
    try:
       f = open( logSummaryFile[:-4] + sDateStr, "a" )
       f.write(value)
       f.write("\n")
       f.close()
    except:
       nicePrintExceptionInfo()
       print "Log2: UNABLE TO WRITE TO SUMMARY LOG FILE:"
       print "Filename:",logSummaryFile[:-4] + sDateStr
       print "Log line:", value

#--------------------------------
LOGLEVEL2SCREEN = 3     #adjust this for screen/regular log level detail
def Log2(level,value):
    #level = what level of detail to output to the screen and regular log file.
    #Note that ALL messages go to the detailed log file
    # each level has 2 additional spaces before log text (for indenting)

    #build the filename
    iDateTime = time.gmtime()    #Change: include date as part of logfile name
    sDateStr = "_" + ObservingDateString() + ".txt"	# time.strftime('_%Y%m%d.txt',iDateTime)

    #prepend spaces depending on log level
    for i in range(level):
        value = "   " + value

    #build the full screen line including timestamp
    prefix = time.strftime("%H:%M:%S ", time.localtime( time.time() ) )
    if value.endswith("\n"):
        value = value[:-1]
    value = prefix + value

    #write all entries to detailed log file:
    try:
       f = open( logAllFile[:-4] + sDateStr, "a" )
       f.write(value)
       f.write("\n")
       f.close()
    except:
       #print "UNABLE TO WRITE TO LOG FILE:",logAllFile[:-4] + sDateStr, value
       nicePrintExceptionInfo()
       print "Log2: UNABLE TO WRITE TO LOG FILE:"
       print "Filename:",logAllFile[:-4] + sDateStr
       print "Log line:", value

    #depending on level, also write to screen and common log file
    if level <= LOGLEVEL2SCREEN:
        print value
        try:
           f = open( logFile[:-4] + sDateStr, "a" )
           f.write(value)
           f.write("\n")
           f.close()
        except:
           print "UNABLE TO WRITE TO LOG FILE:",logFile[:-4] + sDateStr, value


#--------------------------------
def LogOnly(value):     #does NOT write to screen by itself
    #iDateTime = time.gmtime()    #Change: include date as part of logfile name
    #sDateStr = time.strftime('_%Y%m%d.txt',iDateTime)
    #return LogBase(value,logFile[:-4] + sDateStr)
    Log2(LOGLEVEL2SCREEN + 1,value)

#--------------------------------
def Error(value):   #same as Log() but always prints as well as logs
    global errorCount
    errorCount += 1
    Log2(0,"ERROR: " + value)
    #LogOnly("ERROR: " + str(value))
    #print "ERROR: " + str(value)

#--------------------------------
def LogHeader():    #write header into log file:
    Log2(0," ")
    Log2(0,"   ***************************************************************")
    Log2(0,"   **                                                           **")
    Log2(0,"   **                          Startup                          **")
    Log2(0,"   **                                                           **")
    Log2(0,"   ***************************************************************")
    Log2(0," ")


    gmt = time.gmtime(time.time())
    gfmt = '%a, %d %b %Y %H:%M:%S GMT'
    gstr = time.strftime(gfmt, gmt)
    ghdr = 'Date: ' + gstr
    lt = time.localtime(time.time())
    lfmt = '%a, %d %b %Y %H:%M:%S Local time'
    lstr = time.strftime(lfmt, lt)
    lhdr = 'Date: ' + lstr
    Log2(0,ghdr)
    Log2(0,lhdr)

    LogBase(" ",MOVEMENT_LOG)
    LogBase("-----------------------------------------------",MOVEMENT_LOG)
    LogBase(lhdr,MOVEMENT_LOG)

    LogBase(" ",GUIDING_LOG)
    LogBase(lhdr,GUIDING_LOG)
    LogBase("       --RMS--       --Max--   side  -------JNow--------",GUIDING_LOG)
    LogBase(" cnt   X     Y       X     Y   pier     RA        Dec",GUIDING_LOG)
    #LogBase("-----------------------------------------------",GUIDING_LOG)

    LogBase(" ", PINPOINT_LOG)
    LogBase("-----------------------------------------------",PINPOINT_LOG)
    LogBase(lhdr,PINPOINT_LOG)

    LogBase(" ", FOV_LOG)
    LogBase("-----------------------------------------------",FOV_LOG)
    LogBase(lhdr,FOV_LOG)

    LogBase(" ", PINPOINT_SOLVE)
    LogBase("-----------------------------------------------",PINPOINT_SOLVE)
    LogBase(lhdr,PINPOINT_SOLVE)
    LogBase('Time    = how long (seconds) Pinpoint worked on solving the image',PINPOINT_SOLVE)
    LogBase('#Imag #Cat Match = number of stars in: image, catalog, matched',PINPOINT_SOLVE)
    LogBase('Resdl   = Match average residual(arcsec)',PINPOINT_SOLVE)
    LogBase('"/Pixel = arcsec/pixel',PINPOINT_SOLVE)
    LogBase('FWHM    = full width half max of image stars (pixels)',PINPOINT_SOLVE)
    LogBase('pMode   = the pixel intensity that occurs most frequently in the image',PINPOINT_SOLVE)
    LogBase('pMax    = the max pixel intensity',PINPOINT_SOLVE)
    LogBase('pMin    = the min pixel intensity',PINPOINT_SOLVE)
    LogBase(" ", PINPOINT_SOLVE)
    LogBase('                                                                               Solved-J2000                             Desired-J2000         Difference',PINPOINT_SOLVE)
    LogBase('-Time- #Imag  #Cat Match Order Resdl "/Pixel -FWHM pMode  pMax  pMin PosAngle ---RA---    --Dec--- Camera Target         ---RA---  --Dec---   ---RA----    --Dec---',PINPOINT_SOLVE)

    LogBase(" ", FOCUSER_LOG)
    LogBase("-----------------------------------------------",FOCUSER_LOG)
    LogBase(lhdr,FOCUSER_LOG)
    #LogBase("Step Type:     HFD  Temp Posn   Flux     FocusStar", FOCUSER_LOG)
    LogBase("Step Type:     HFD  Temp Posn   Flux    Filter FocusStar", FOCUSER_LOG)

    LogBase(" ", TARGET_LOG)
    LogBase("-----------------------------------------------",TARGET_LOG)
    LogBase(lhdr,TARGET_LOG)
    LogBase(" RA--JNow--Dec       RA--J2000--Dec    Name:", TARGET_LOG)


#--------------------------------
def LogStatusHeaderBrief():
   StatusLog("                 Mount-JNow             Pier RevX Cam                  Aggr                  -Focuser-  -Guide_Image------------ ----Detect_guider_problems----")
   StatusLog("           ---RA----- ---Dec--- Alt- -Az-- P R   Temp Pwr  Xerr  Yerr  X  Y  FWHM Sidereal   Posn Temp    min   max   avg    std [excessive error ck]   [Stale ck]")

def LogStatusHeader():
   gmt = time.gmtime(time.time())
   gfmt = '%a, %d %b %Y %H:%M:%S GMT'
   gstr = time.strftime(gfmt, gmt)
   ghdr = 'Date: ' + gstr
   lt = time.localtime(time.time())
   lfmt = '%a, %d %b %Y %H:%M:%S Local time'
   lstr = time.strftime(lfmt, lt)
   lhdr = 'Date: ' + lstr
   StatusLog(" ")
   StatusLog("----------------------------------------------------------------------------------------")
   StatusLog(ghdr)
   StatusLog(lhdr)
   LogStatusHeaderBrief()

#--------------------------------
def LogConditions(vState):
    #log camera temperature and other info (call after each action command (overkill, but can review later for trends))
    Log2(6,"Current conditions - no longer logged:")
    return

#2014.09.23 JU: removed this logging; it adds about 4 seconds after each image, and if doing short time series this adds up.
    Log2(4,"Current conditions:")

    Log2(4,"... RA:  " + UTIL.HoursToHMS( vState.MOUNT.RightAscension,":",":","",1))
    Log2(4,"... Dec: " + DegreesToDMS( vState.MOUNT.Declination ))
    #Log2(4,"... Side of Pier: " + str(vState.MOUNT.SideOfPier))
    Log2(4,"... Side of Pier: " + str(SideOfSky(vState)))

    Log2(4,"... Altitude: " + str(round(vState.MOUNT.Altitude,2)))
    Log2(4,"... Azimuth:  " + str(round(vState.MOUNT.Azimuth,2)))
    try:
        if vState.CAMERA.CoolerOn:
            Log2(4,"... Cooler is running")
        else:
            Log2(4,"... Cooler is OFF")
    except:
        pass

    try:
        Log2(4,"... Camera name:  " + str(vState.CAMERA.CameraName))
    except:
        pass

    try:
        Log2(4,"... Camera temp:  " + str(round(vState.CAMERA.Temperature,2)))
    except:
        pass

    try:
        Log2(4,"... Set point:    " + str(vState.CAMERA.TemperatureSetPoint))
    except:
        pass

    try:
        Log2(4,"... Cooler power: " + str(vState.CAMERA.CoolerPower))
    except:
        pass

    try:
        Log2(4,"... Last image FWHM:  " + str(round(vState.CAMERA.FWHM,2)))
    except:
        pass

    try:
        Log2(4,"... Last image half flux diameter:  " + str(round(vState.CAMERA.HalfFluxDiameter,2)))
    except:
        pass

    try:
        Log2(4,"... Last image cropping settings: x=%d, y=%d, width=%d, height=%d  "
            % (vState.CAMERA.StartX,vState.CAMERA.StartY,vState.CAMERA.NumX,vState.Camera.NumY))
    except:
        pass

    try:
        Log2(4,"... Last image max pixel level: " + str(vState.CAMERA.MaxPixel) + ", location: " +
                str(vState.CAMERA.MaxPixelX) + ", " + str(vState.CAMERA.MaxPixelY))
    except:
        pass

    try:
        Log2(4,"... Robofocus position: " + str(vState.FOCUSER.Position))
    except:
        pass

    try:
        Log2(4,"... Robofocus temperature code: " + str(vState.FOCUSER.Temperature))
    except:
        pass

    try:
        doc = vState.CAMERA.Document
        Log2(4,"... Size of last exposure (pixels): %d x %d "  % (doc.XSize,doc.YSize))
    except:
        pass

#--------------------------------

#--------------------------------
def GetSign(nbr):   #return +1 if nbr >= 0, else return -1
    if nbr >= 0:
        return 1
    else:
        return -1
# Look at the last several guiding errors in X or Y. If the error is constantly
# changing sign each time, and the magnitude of the error is greater than
# the guider settling criteria, then guider is probably stuck in oscillation problem.
# Report this so that guiding can be stopped and restarted to try to clear it.
#
# Note: we require consistent sign flip and large error to call this an oscillation
# problem. If the oscillations are small, they might clear on their own. Otherwise
# I expect they will grow and eventually (soon) trigger this check.
def CheckOscillation(obj,vState):
    #obj is either gListGuideXErrors or gListGuideYErrors, both of
    #  which are global variables.
    #Return tuple: (bool,string) where true=error, string=msg for log line
   bAlternate = True
   bLarge     = True

   if len(obj) < 10:
      return (False,"s")   #don't check

   #sign = -math.copysign(1.0,obj[0])
   sign = -GetSign(obj[0])      #get the opposite sign to the 1st entry in the list, for starting the check
   i = 0
   for item in obj:
       if abs(item) < vState.GuidingSettleThreshold:
          bLarge = False        #if any of the errors is small, assume this is NOT oscillating
          break

       i += 1   #count how many we process

       if item == 0:
          return (False,"0-%d" % i)  #if any of the error measurements is exactly zero, assume no problem

       #if sign != -math.copysign(1.0,item):
       nextsign = GetSign(item)
       if sign != -nextsign:
          return (False,"s-%d" % i)  #everything OK; adjacient entries w/ same sign

       sign = nextsign  #GetSign(item)  #set up to check the next measurement

   if bAlternate and bLarge:
       #oscillation problem detected in last 10 guider measurements
       Log2(0,"Oscillation problem detected in last 10 guider measurements")
       Log2(4,"Dump of list of guide errors:")
       for item in obj:
         Log2(5,"%5.2f" % item)
       Log2(4,"End of dump")
       return (True,"Oscil")

   # Both not true, return string to show which is true, if either
   if bAlternate:
        return (False,"A-%d" % i)
   if bLarge:
        return (False,"L-%d" % i)
   return (False,"e-%d" % i)  #everything OK, reached end and no large errors and no Alternating

def TestGuidingTrend(label,guideList):
    # label = string to label message, to tell X from Y report
    # guideList = list of last several guide errors; this will be gListGuideXErrors or gListGuideYErrors
    #Return False=no problem, not enough data to check yet, or improving trend; True=trend bad so may want to halt guiding
    length = len(guideList)
    if length < 3:
        return False    #too little data to test

    last1 = guideList[length-1]     #last
    last2 = guideList[length-2]     #last-1
    last3 = guideList[length-3]     #last-2

    #if any of these are within 0.5 of zero, then something is working so do not report error
    if abs(last1) < 0.5 or abs(last2) < 0.5 or abs(last3) < 0.5:
        return False

    #look at sign of last value, and see if the 3 of them form an improving trend
    if last1 < 0:
        #value < 0, so look for increasing (approaching zero) values:
        if last1 > last2 and last2 > last3:
            return False    #values seem to be improving
    else:
        #value > 0, so look for decreasing values:
        if last1 < last2 and last2 < last3:
            return False    #values seem to be improving
    msg = "TestGuidingTrend indicates bad trend for %s (most recent last): %4.2f  %4.2f  %4.2f" % (label,last3,last2,last1)
    Log2(3,msg)
    StatusLog(msg)
    return True

def DumpGuideErrorList(label,guideList):
    msg = "Guide errors %s (most recent last)" % label
    length = len(guideList)
    for x in range(0,length):
        val = guideList[x]
        try:
            sval = " %4.2f" % val
        except:
            sval = "????"
        msg = msg + sval

    Log2(3,msg)

#Logging:
#  1234567890
#  --++-+-+--  (ex) record last 10 signs
#--------------------------------
def LogStatus( vState, sourceNum ):  #write out frequent status info to special file
    # sourceNum = number to indicate where this was called from
    #Returns True if bad guiding detected
    #Summary of flag column values:
    #   E   threw an exception when trying to read whether guider is running

   #print "<LogStatus>"
   global RecentGuideX
   global RecentGuideY

   global gGuidingXSum
   global gGuidingYSum
   global gGuidingCount
   global gGuidingXMax
   global gGuidingYMax

   #Where are we, and are we still close to the location we want?
   #TODO: IF WE ARE TAKING DARKS/BIAS/FLATS AND WE ARE PARKED WE DO NOT WANT TO DO THIS!!!
   #2018.01.06 JU: change this section so it only runs if vState.gotoPosition.isValid
   if vState.gotoPosition.isValid:
       nowPos = Position()
       try:
            nowPos.setJNowDecimal(vState.MOUNT.RightAscension,vState.MOUNT.Declination)
            #2018.08.31 JU: commented out these lines; they make logall file unreadable
            #Log2(4,"nowPos.dump:")
            #Log2(4,nowPos.dump())
            #Log2(4,"vState.gotoPosition.dump:")
            #Log2(4,vState.gotoPosition.dump())


            diffRA = vState.gotoPosition.dRA_JNow() - nowPos.dRA_JNow()
            diffDec = vState.gotoPosition.dDec_JNow() - nowPos.dDec_JNow()
            DiffRAdeg = diffRA * 15 * cosd(nowPos.dDec_JNow())   #convert RA diff into degrees, adjusted for declination
            delta = math.sqrt((DiffRAdeg * DiffRAdeg) + (diffDec * diffDec)) * 60   #arcmin
            
            #I found a formula to do this:
            #Given coord pair (ra1,dec1) and pair (ra2,dec2), then the angular distance between the coord are:
            #   cos(result) = (sin(dec1) * sin(dec2)) + cos(dec1) * cos(dec2) * sin(ra1 - ra2)
            #Where all coords are given in RADIANS (RA is not Hours, it is angle)
            #I found this: physics.stackexchange.com/questions/224950/how-can-i-convert-right-ascension-and-declination-to-distances
            

            #WHY did I think I needed this? Because sometimes guiding thinks it is working
            # but we are just looking at noise and not actually tracking the guide star.
            # When we have drifted some distance away then we may no longer be pointing at
            # the right field and should re-acquire it.
            #Note that if guiding IS actually working correctly but polar alignment is off then
            # we can get drift as well. That isn't a real problem, but since we can't tell
            # the difference between these cases we'll treat it as an error and reacquire anyway.
            #(added 2013.07.17): And if guiding is NOT working, Gemini still calculates current
            # scope position based on model, so it can detect if moved far from target coord
            # even if not guiding!!!
            if delta > vState.driftThreshold:
                #PROBLEM
                Error("Position exceeded drift threshold (%d)=======================================" % sourceNum)
                Log2(1,"delta = %5.2f, threshold = %5.2f arcmin" % (delta, vState.driftThreshold))
                Log2(2,"Where we want to be:")
                line0,line1 = vState.gotoPosition.dump2()
                Log2(3,line0)
                Log2(3,line1)
                Log2(2,"Where the mount says we currently are:")
                line0,line1 = nowPos.dump2()
                Log2(3,line0)
                Log2(3,line1)

                Log2(2,"Goto position:")
                Log2(3,vState.gotoPosition.dump())
                Log2(2,"NowPos position:")
                Log2(3,nowPos.dump())

                #To disable this feature, comment out the return True statement
#2019.03.19 JU: this problem happened again (ST LMi this time) so disable again
                #return True

       except:
           Log2(1,"Exception trying to read mount current position for threshold")
           Log2(1,"check. This can usually be ignored; it can be because mount")
           Log2(1,"has not yet moved, so no status to report yet.")
           niceLogExceptionInfo()      #removed message 2017.02.17 JU

   try:
       if not vState.CAMERA.GuiderRunning:
           LogStatusBase(vState,-99,-99," ","","","","","","","","")    #guider is off; no data
           return False
   except:
       niceLogExceptionInfo()
       Error("Threw exception trying to read whether guider is running!")
       flag = "E"
       LogStatusBase(vState,RecentGuideX,RecentGuideY,flag,"","","","","","","","") #report latest values, plus exception
       return False

   bStaleData = False

   #guider is running (and no exception checking it), so read error variables:
   try:
      if vState.CAMERA.GuiderNewMeasurement:
          #global RecentGuideX
          RecentGuideX = vState.CAMERA.GuiderXError

          #global RecentGuideY
          RecentGuideY = vState.CAMERA.GuiderYError

          vState.LogStatusCount = 0
          flag = " "

          gGuidingXSum += (RecentGuideX * RecentGuideX)
          gGuidingYSum += (RecentGuideY * RecentGuideY)
          gGuidingCount += 1

          if abs(RecentGuideX) > gGuidingXMax and RecentGuideX != -99:
              gGuidingXMax = abs(RecentGuideX)

          if abs(RecentGuideY) > gGuidingYMax and RecentGuideY != -99:
              gGuidingYMax = abs(RecentGuideY)

          imaging_db.RecordGuider(vState,True,1022)

      else:
          #new measurement not available yet; suppress logging unless we get called
          # many times in a row
          vState.LogStatusCount += 1
          if vState.LogStatusCount < 10:
            return False     #do not log

          #else log the old values
          flag = "o"
          bStaleData = True
          vState.LogStatusCount = 6 #set this so we don't do this again for ~4 seconds (6 = 10 - 4)
          imaging_db.RecordGuider(vState,False,1023)  #(Do I want to do this?)
   except:
     niceLogExceptionInfo()
     Error("Threw exception trying to read guider errors")
     flag = "e"
     bStaleData = True

   bReturn = False  #set true below if problem
   savgS = "    "
   slenAvgS = "  "
   savgX = "    "
   slenAvgX = "  "
   savgY = "    "
   slenAvgY = "  "

   xMsg = " "
   yMsg = " "
   #LogStatusBase(vState,RecentGuideX,RecentGuideY,flag)

   #Monitor recent guider activity, to detect if we lost the guide star
   # or are having really bad guiding, both of which indicate we should
   # stop the current exposure and reacquire the target.
   global gGuiderState
   if gGuiderState == 2:
       #guider should be running; calc recent trends to decide if problem
       global gListStaleGuideData
       if len(gListStaleGuideData) >= 10:
           gListStaleGuideData = gListStaleGuideData[1:]    #remove oldest entry

       if bStaleData:
           #boxcar avg of stale data; return True
           gListStaleGuideData.append(1)    #add flag that data currently stale
           prefix = time.strftime("%H:%M:%S ", time.localtime( time.time() ) )
           print prefix,"Stale guiding data:",gListStaleGuideData
           avgS = CalcListAverage(gListStaleGuideData)
           savgS = "%4.2f" % avgS
           #LogOnly("Guide monitoring: avgS = %4.2f (cnt %d)" % (avgS,len(gListStaleGuideData)))
           slenAvgS = "%2d" % len(gListStaleGuideData)
           if len(gListStaleGuideData) >= 10 and avgS > 0.5:
               #more than 50% of the last 10 measurements had stale data
               Log2(0,"************************")
               Log2(0,"** Stale guiding data **")
               Log2(0,"************************")
               bReturn = True
       else:
           #data available (not stale), calc boxcar avg of X,Y
           gListStaleGuideData.append(0)    #add flag that data is not stale
           avgS = CalcListAverage(gListStaleGuideData)
           savgS = "%4.2f" % avgS
           slenAvgS = "%2d" % len(gListStaleGuideData)

           #we can only calc the guide errors if the data is NOT stale
           global gListGuideXErrors
           if len(gListGuideXErrors) >= 10:
               gListGuideXErrors = gListGuideXErrors[1:]    #remove oldest entry
           gListGuideXErrors.append(RecentGuideX)
           avgX = CalcListAverage(gListGuideXErrors)

           global gListGuideYErrors
           if len(gListGuideYErrors) >= 10:
               gListGuideYErrors = gListGuideYErrors[1:]    #remove oldest entry
           gListGuideYErrors.append(RecentGuideY)
           avgY = CalcListAverage(gListGuideYErrors)

           savgX =  "%4.2f" % avgX
           savgY =  "%4.2f" % avgY
           slenAvgX = "%2d" % len(gListGuideXErrors)
           slenAvgY = "%2d" % len(gListGuideYErrors)
           #LogOnly("Guide monitoring: avgX = %5.2f (cnt %d)  avgY = %5.2f (cnt %d)  avgS = %4.2f (cnt %d)" % (avgX,len(gListGuideXErrors),avgY,len(gListGuideYErrors),avgS,len(gListStaleGuideData)))

           if len(gListGuideXErrors) >= 10 and avgX > (vState.GuidingSettleThreshold * 4) and TestGuidingTrend("X",gListGuideXErrors):  #1.5:
               #the average X pixel guide error over last 10 measurements is > 4*SettleThreshold
               Log2(0,"*********************")
               Log2(0,"** Bad guiding (X) **")
               Log2(0,"*********************")
               Log2(3,"Number of errors to evaluate: %d, avgx: %4.2f, threshold: %4.2f" % (len(gListGuideXErrors),avgX,(vState.GuidingSettleThreshold * 4)))
               DumpGuideErrorList("X",gListGuideXErrors)
               bReturn = True

           if len(gListGuideYErrors) >= 10 and avgY > (vState.GuidingSettleThreshold * 4) and TestGuidingTrend("Y",gListGuideYErrors):  #1.5:
               #the average Y pixel guide error over last 10 measurements is > 4*SettleThreshold
               Log2(0,"*********************")
               Log2(0,"** Bad guiding (Y) **")
               Log2(0,"*********************")
               Log2(3,"Number of errors to evaluate: %d, avgx: %4.2f, threshold: %4.2f" % (len(gListGuideYErrors),avgY,(vState.GuidingSettleThreshold * 4)))
               DumpGuideErrorList("Y",gListGuideYErrors)
               bReturn = True

           tupx = CheckOscillation(gListGuideXErrors,vState)
           xMsg = tupx[1]
           if tupx[0]:
               #report problem
               Log2(0,"*****************************")
               Log2(0,"** Guiding Oscillation (X) **")
               Log2(0,"*****************************")
               Log2(0,"msg = %s" % tupx[1])
               #if X-aggr > 3, decr X-aggr
               try:
                       xAggr = vState.CAMERA.GuiderAggressivenessX
                       yAggr = vState.CAMERA.GuiderAggressivenessY

                       if xAggr > 5:
                            xAggr = xAggr - 1
                            vState.CAMERA.GuiderAggressivenessX = xAggr
                            Log2(3,"Reducing XAggr to %f" % xAggr)
               except:
                   Log2(3,"Error, unable to adjust X aggressiveness")
               bReturn = True

           tupy = CheckOscillation(gListGuideYErrors,vState)
           yMsg = tupy[1]
           if tupy[0]:  #(this problem more common in X than in Y)
               #report problem
               Log2(0,"*****************************")
               Log2(0,"** Guiding Oscillation (Y) **")
               Log2(0,"*****************************")
               Log2(0,"msg = %s" % tupy[1])
               #if Y-aggr > 3, decr Y-aggr
               try:
                       yAggr = vState.CAMERA.GuiderAggressivenessY

                       if yAggr > 6:            #try reducing, but don't let this reduce too far
                            yAggr = yAggr - 1
                            vState.CAMERA.GuiderAggressivenessY = yAggr
                            Log2(3,"Reducing YAggr to %f" % yAggr)
               except:
                   Log2(3,"Error, unable to adjust Y aggressiveness")
               bReturn = True

       LogStatusBase(vState,RecentGuideX,RecentGuideY,flag,savgX,slenAvgX,savgY,slenAvgY,savgS,slenAvgS,xMsg,yMsg)
   return bReturn
#-----------------------------------------------------------------------------
def ResetGuiderMonitoring():
    global gListStaleGuideData
    global gListGuideXErrors
    global gListGuideYErrors

    gListStaleGuideData = []
    gListGuideXErrors = []
    gListGuideYErrors = []

    global RecentGuideX
    RecentGuideX = 0

    global RecentGuideY
    RecentGuideY = 0


def RecoverFromBadGuiding(dic,vState):    #reacquire target
   Log2(0,"*********************************************************")
   Log2(0,"** Attempt to reacquire target after Bad Guiding event **")
   Log2(0,"*********************************************************")
   Log2Summary(1,"Attempt to reacquire target after Bad Guiding event")

   #NOTE: if our current command is 'Stationary', this does not have
   # a "pos" value, so this throws an exception! (Maybe a good idea?)

   GOTO(dic["pos"],vState,dic["ID"])
   #Now precisely re-position the mount on the specified coords using PP solves.
   if PinpointEntry(dic["pos"], dic["ID"], vState, True):
       Log2(0,"********************************************************")
       Log2(0,"** Failed to reacquire target after Bad Guiding event **")
       Log2(0,"********************************************************")
       Log2Summary(1,"Failed to reacquire target after Bad Guiding event")

       #What happens next: It will try to go onto next target; make sure that
       #any explicit target list is always followed by Survey step so it won't
       #run out of targets. If it consistently fails to find a target, the
       #weather alarm will activate.
       #return True #problem
       #CHANGED 2017.07.24 JU: instead of stopping current target, pause and
       #throw weather exception so it pauses and then retries later on this target
       raise WeatherError


   if StartGuidingConfirmed(dic["ID"], vState, 5):
      Error("**Failed to start guiding even after several attempts (during RecoverFromBadGuiding)")
      ##SafetyPark(vState)
      ##raise SoundAlarmError,'Halting program'
      raise WeatherError

   return False #OK

#-----------------------------------------------------------------------------
def CalcListAverage(obj):
    sum = 0
    cnt = 0
    for item in obj:
        sum = sum + abs(item)
        cnt = cnt + 1
    if cnt > 0:
        return (sum / cnt)
    return 0
#-----------------------------------------------------------------------------
def LogStatusShort(vState):
   try:
      dRA = vState.MOUNT.RightAscension
      dDec = vState.MOUNT.Declination
      fAlt = vState.MOUNT.Altitude
      fAz  = vState.MOUNT.Azimuth
      fSidereal = vState.MOUNT.SiderealTime
   except:
      dRA = 0.
      dDec = 0.
      fAlt = 0.
      fAz  = 0.
      fSidereal = 0.

   try:
      #sideofpier = vState.MOUNT.SideOfPier
      sideofpier = SideOfSky(vState)
   except:
      sideofpier = 9

   value = "RA:%10s Dec:%9s Alt:%5s Az:%5s Pier:%d Sidereal:%10s" % (
      UTIL.HoursToHMS(dRA,":",":","",1),                      #string
      DegreesToDMS(dDec),                        #string
      str(round(fAlt,1)),                        #string
      str(round(fAz,1)),                         #string
      sideofpier,                                #number
      UTIL.HoursToHMS(fSidereal,":",":","",1)                 #string
      )
   Log2(4,"LogStatusShort: " + value)

#------------------------------------------------------------------------------
def LogStatusBase( vState, guideX, guideY, guideFlag,savgX,slenAvgX,savgY,slenAvgY,savgS,slenAvgS, msgX, msgY ):
    #write out frequent status info to special file
   if guideX == -99:
        GuideX = '??.??'
   elif guideX == -88:
        GuideX = 'ee.ee'
   else:
        GuideX = "%5.2f" % (guideX)

   if guideY == -99:
        GuideY = '??.??'
   elif guideY == -88:
        GuideY = 'ee.ee'
   else:
        GuideY = "%5.2f" % (guideY)

   #FUTURE EXPANSION:
   if guideX != -99 and guideY != -99:
       #do a boxcar analysis of recent guide errors and decide if aggressiveness should be changed
       #TODO
       pass

   try:
      #sideofpier = vState.MOUNT.SideOfPier
      sideofpier = SideOfSky(vState)
   except:
      sideofpier = 9

   try:
      coolerpower = vState.CAMERA.CoolerPower
   except:
      coolerpower = 0

   try:
      fwhm = vState.CAMERA.FWHM
   except:
      fwhm = 0

   try:
      focusPos = vState.FOCUSER.Position
   except:
      focusPos = 0

   try:
     focusTemp = str(vState.FOCUSER.Temperature)
   except:
     focusTemp = "N/A"


   try:
       doc = GetGuiderDoc(vState)
       xsize = vState.CAMERA.GuiderXSize
       ysize = vState.CAMERA.GuiderYSize
       #print xsize,ysize
       tupGuide = doc.CalcAreaInfo(0,0,xsize-1,ysize-1)
   except:
       tupGuide = (0,0,0,0.)
       #DO NOT DO THIS HERE: niceLogExceptionInfo()


   #log status (engineering) special data
   #f1 = open( r"C:\fits_script\Status.txt", "a" )
   prefix = time.strftime("%H:%M:%S ", time.localtime( time.time() ) )

#  f2.write("                                      Pier RevX Cam                  Aggr                -Focuser-\n")
#  f2.write("           ---RA--- ---Dec--- Alt- -Az-- P R   Temp  Pwr Xerr  Yerr  X  Y  FWHM Sidereal Posn Temp\n")
#            05:26:21 | 22:36:48  34:01:17 36.6 285.4 0 0  -10.2  61  0.44  0.08  7  5   0.0 03:10:52 3333  622
#            05:26:26 | 22:36:48  34:01:17 36.6 285.4 0 0  -9.79  58  0.41 -0.09  7  5   0.0 03:10:58\

   start_time = time.time()
   imaging_db.RecordMount(vState,1001)
   split1 = time.time() - start_time
   imaging_db.RecordCamera(vState,1002)
   split2 = time.time() - start_time
   imaging_db.RecordGuider(vState,False,1003)
   split3 = time.time() - start_time
   imaging_db.RecordFocuser(vState,1004)
   elapsed_time = time.time() - start_time
   imaging_db.RecordPerformance(vState,elapsed_time,split1,split2,split3) #track how much time this is taking, to make sure it isn't too much

   try:
      dRA = vState.MOUNT.RightAscension
      dDec = vState.MOUNT.Declination
      fAlt = vState.MOUNT.Altitude
      fAz  = vState.MOUNT.Azimuth
      bRevX = vState.CAMERA.GuiderReverseX
      fTemperature = vState.CAMERA.Temperature
      xAggr = vState.CAMERA.GuiderAggressivenessX
      yAggr = vState.CAMERA.GuiderAggressivenessY
      fSidereal = vState.MOUNT.SiderealTime
   except:
      dRA = 0.
      dDec = 0.
      fAlt = 0.
      fAz  = 0.
      bRevX = False
      fTemperature = 0.
      xAggr = 0
      yAggr = 0
      fSidereal = 0.

   try:
        msgGuider = vState.CAMERA.LastGuiderError
   except:
        msgGuider = "---"

   value = "| %10s %9s %4s %5s %d %d %6s %3d %5s %5s%1s%2d %2d %5s %10s %4d %3s %5d %5d %5d %6.1f %4s (%2s)   %4s (%2s)  %4s (%2s) [%s|%s]" % (
      UTIL.HoursToHMS(dRA,":",":","",1),                      #string
      DegreesToDMS(dDec),                        #string
      str(round(fAlt,1)),                        #string
      str(round(fAz,1)),                         #string
      sideofpier,                                #number
      bRevX,                                     #boolean
      str(round(fTemperature,2)),                #string
      coolerpower,                               #number
      GuideX,                                    #string
      GuideY,                                    #string
      guideFlag,                                 #1 char long string
      xAggr,                                     #number
      yAggr,                                     #number
      str(round(fwhm,2)),                        #string
      UTIL.HoursToHMS(fSidereal,":",":","",1),                #string
      focusPos,                                  #number
      focusTemp,                                  #string
      tupGuide[1],                                #number(min guider pixel)
      tupGuide[0],                              #number (max guider pixel)
      tupGuide[2],                              #number (avg guider pixel)
      tupGuide[3],                              #float (std guider pixel)
      savgX,slenAvgX,savgY,slenAvgY,savgS,slenAvgS,msgX,msgY
      )

   StatusLog(prefix + value)    #THIS IS THE IMPORTANT USE OF THIS LOG FILE

#--------------------------------
def NameWithoutPath(fullname):
    #return the last part of a path\filename
    #this is for logging to be less wordy
    ind = string.rfind(fullname,'\\')
    if ind > 0:
        return fullname[ind+1:]

    #give it one more chance with other notation
    ind = rfind(fullname,'/')
    if ind > 0:
        return fullname[ind+1:]

    return fullname  #don't know what it is

#=====================================================================================
#==== SECTION  @@Catalog =================================================================
#=====================================================================================

def catalogID_cleaner(inName):  #reformats for MiniSAC catalog: put blank between catalog indicator and number
    # ex: "M1" becomes "M 1"
    #   NGC9999  becomes NGC 9999
    #   0123456          012     (because catalog name limited to 3 char currently??)
    inName = inName.strip()
    posSpace = inName.find(' ')
    if posSpace > 0:
       return inName    #good enough for us if it already has the space in it

    posNumber = -1
    i = 0
    for c in inName:
        if (c >= '0' and c <= '9'):
            posNumber = i
            break
        i += 1

    if posNumber == -1:
        return inName   #don't know what this is; just return it

    if posSpace > 0 and posNumber == (posSpace + 1):
        return inName   #it is already in correct format; don't change it

    if posNumber > 0:
        return inName[0:posNumber] + ' ' + inName[posNumber:]

    return inName   #no idea...

#--------------------------------------------------------------------------------------------------------
def LookupObject( target):
    #Three different types of objects are supported in this lookup; the start of the name is used to determine type:
    # SAO 99999   Look in my SAO text file for this star's coords
    # MPL 99999   Use TheSky6 to look up current (JNow) coords for this asteroid
    # everything else: uses MiniSAC catalog; ex: M 1, NGC 7777, HGC 1
    #Returns a Position object

    #print "LookupObject called; target = ",target

    pos = Position()    #create the empty position object to be returned

    target = target.strip() #?? .upper()     #make sure no extra spaces around it, and upper case

    #Special case: if MPL, check for cached value. (this is NOT part of the
    # if/elif chain because I later combine checking of MPL *AND* other types
    # of objects in TheSky6, and I don't want to duplicate that code.)
##    if MPL_cache.has_key(target):
##        pos = MPL_cache(target)
##        Log2(3,"Using cached coordinates for: %s" % target)
##        Log2(3,pos.dump3())
##        return pos

    if target[:3] == "SAO":
        # Must convert input to format SAO999999 (6 digits, no space)
        posSpace = target.find(' ')

        try:
            if posSpace > 0:
                #input looks like 'SAO 123'
                temp = tuple(target.split(' '))
                nVal = int(temp[1])  #the number component
                target = "SAO%06d" % (nVal)
            else:
                #input looks like 'SAO123'
                temp = target[3:]  #skip the 'SAO' characters
                nVal = int(temp)
                target = "SAO%06d" % (nVal)
        except:
            #if the expected number is not really a number, the int() will throw an exception
            msg = "[%-9s]   SAO star format invalid; should be: SAO123456 or SAO 55555" % (target)
            Error(msg)
            CatalogLookupFailures.append(msg)
            #return (0,0)
            return pos

        #Note: SAO data is J2000

        sao = open(r'SAO Catalog.guc','r')  #the catalog has 17609 entries, but it scans in less than a second
        for line in sao:
            if target == line[:9]:
                #print "SAO line before trim"
                line = line[:-2]     #remove trailing '#\n'
                tup = tuple(line.split(','))
                #print "SAO line found:",line,tup
                sRA = tup[1]        #yes we want [1] here, [0] is the star ID field
                sDec = tup[2]
                sao.close()
                print "1-What do I have here:",sRA,sDec,line
                pos.setJ2000String(sRA,sDec,target,cTypeCatalog)
                msgs = pos.dump2()
                Log2(6,msgs[0])
                Log2(6,msgs[1])
                LogBase("   ",MOVEMENT_LOG)
                LogBase(msgs[0],MOVEMENT_LOG)
                LogBase(msgs[1],MOVEMENT_LOG)
                LogBase(pos.dump3(),TARGET_LOG)
                return pos

        #getting here means we did not find the star ID
        sao.close()
        msg = "[%-9s]   SAO catalog entry not found" % (target)
        Error(msg)   ##THIS SHOULD ONLY HAPPEN DURING VALIDATION
        CatalogLookupFailures.append(msg)
        #return (0,0)
        return pos


    elif target[:3] == "MPL" or target[:3] == "GSC" or target[:3] == "HIP" or target[:3] == "TS6" or target == "Mars" or target == "Jupiter" or target == "Saturn" or target == "Uranus" or target == "Neptune" or target == "Pluto":
    #elif target[:3] == "MPL" or target[:3] == "GSC" or target[:3] == "HIP":
        #2009.11.27 JU: added GSC and HIP star catalog lookup using TheSky6 as well.
        #2011.08.22 JU: also added prefix TS6 for "TheSky6" to look up object there, such as a planet.
        #print "Lookup:",target
        CHART  = win32com.client.Dispatch("TheSky6.StarChart")
        dLat  = CHART.DocumentProperty(0)
        dLong = CHART.DocumentProperty(1)
        nDST  = CHART.DocumentProperty(4)
        dTz   = CHART.DocumentProperty(2)
        dElev = CHART.DocumentProperty(3)
        nDST  = CHART.DocumentProperty(4)
        bUseComputerClock	= 1			#1=Yes 0=No
        szLoc = "Location from current settings"

        #convert the specified datetime(dt) into JD
        dt = time.localtime(time.time())
        #print "setChartDateTime local:",dt
        myJD = jd(dt[0], dt[1], dt[2], dt[3], dt[4], dt[5])

        #tell TheSky6 to use this datetime
        RASCOM = win32com.client.Dispatch("TheSky6.RASCOMTheSky")
        RASCOM.Connect()   #not sure if this is needed
        RASCOM.SetWhenWhere(myJD,nDST,bUseComputerClock, szLoc, dLong, dLat, dTz, dElev)

        try:
            #2009.07.21 JU: fixed this to return J2000 instead of JNow coords!
            #RASCOM.GetObjectRaDec2000( target )         #look up coords in J2000 !!!
            if target[:3] == "TS6":
                RASCOM.GetObjectRaDec2000( target[4:] )
            else:
                RASCOM.GetObjectRaDec2000( target )         #look up coords in J2000 !!!
        except:
            #print nicePrintExceptionInfo()

            if target[:3] == "TS6":
                print "TheSky6 lookup was not found==>" + target[4:] + "<"
            else:
                print "TheSky6 lookup was not found==>" + target + "<"
                print "******************************************************"
                print "** Did I run the Extended Asteroid calc in TheSky?? **"
                print "******************************************************"

##            print "TheSky6 lookup was not found==>" + target + "<"
##            print "******************************************************"
##            print "** Did I run the Extended Asteroid calc in TheSky?? **"
##            print "******************************************************"
            msg ="[%-9s]   Catalog lookup failure:  MPL did not find target" % (target)
            Error(msg)
            CatalogLookupFailures.append(msg)
            del RASCOM
            del CHART
            return pos

        dRA  = RASCOM.dObjectRa
        dDec = RASCOM.dObjectDec
        #print "Lookup worked",dRA,dDec

        if dDec < -40:
            msg ="[%-9s]   Catalog lookup failure: TARGET IS TOO FAR SOUTH: %f" % (target,dDec)
            Error(msg)
            CatalogLookupFailures.append(msg)
            del RASCOM
            del CHART
            return pos

        pos.setJ2000Decimal(dRA,dDec,target,cTypeCatalog)
        Log2(3,"Coordinates from TheSky6 (JNow pair, J2000 pair)")
        Log2(3,pos.dump3())
        del RASCOM
        del CHART

        #Note: asteroids move in a short period of time. This movement affects
        # the ability of Visual Pinpoint to group multiple images together for
        # one target. I am caching the first asteroid position and will re-use it
        # for successive calls. I hope the successive locations will still be on
        # the image FOV.  (Also note: when I initially call LookupObject to validate
        # the targets, I then clear out MPL_cache so it doesn't have the validation
        # location, and only cache the 1st position actually used to image.)
        if target[:3] == 'MPL':
            MPL_cache[target] = pos

        return pos

    else:
        print "Check MiniSAC"
        #assume can feed this to MiniSAC catalog
        #print "Connect: MiniSAC.Catalog"
        cleanTarget = catalogID_cleaner(target)  #breaks up into catalog ("M") and number ("1") with a space between them
        cat = win32com.client.Dispatch("MiniSAC.Catalog")      #deep sky catalog
        try:
            if not cat.SelectObject( cleanTarget ):
                #last resort, try spreadsheet info
                try:
                    dRA,dDec = MasterCoords[cleanTarget]
                    pos.setJ2000Decimal(dRA,dDec,target,cTypeCatalog)
                except:
                    #it really isn't here
                    msg = "[%s]   Specified catalog entry not found" % (cleanTarget)
                    Error(msg)
                    niceLogExceptionInfo()
                    CatalogLookupFailures.append(msg)
                    del cat
                    return pos  #return (0,0)

            else:
                sRA = cat.RightAscension
                sDec = cat.Declination
                print "2-What do I have here:",sRA,sDec
                pos.setJ2000Decimal(sRA,sDec,target,cTypeCatalog)

        except:
            print "DO NOT USE THIS FEATURE; IT WAS AUTOMATED TARGET SELECTION; NO LONGER POPULATED SO IT WILL NOT DO ANYTHING"
            #other last resort (if exception thrown above), try spreadsheet info
            try:
                dRA,dDec = MasterCoords[cleanTarget]
                pos.setJ2000Decimal(dRA,dDec,target,cTypeCatalog)
            except:
                #it really isn't here
                msg = "[%s]   Specified catalog entry not found (exception)" % (cleanTarget)
                Error(msg)
                CatalogLookupFailures.append(msg)
                del cat
                return pos  #return (0,0)

        del cat
        msgs = pos.dump2()
        Log2(0,msgs[0])
        Log2(0,msgs[1])
        LogBase("   ",MOVEMENT_LOG)
        LogBase("   ",MOVEMENT_LOG)
        LogBase(msgs[0],MOVEMENT_LOG)
        LogBase(msgs[1],MOVEMENT_LOG)
        LogBase(pos.dump3(),TARGET_LOG)

        return pos

    msg = "[%-9s]   Specified catalog entry not found" % (cleanTarget)
    Error(msg)
    CatalogLookupFailures.append(msg)
    return pos

#=====================================================================================
#==== SECTION  @@Guiding =================================================================
#=====================================================================================

def StartGuidingConfirmed(objectName, vState, retryCnt, bRequireSuccess=False):
    # return True if failed after all attempts to start guiding and settle; False = worked
    # bRequireSuccess = True means do NOT return until guiding works, or sun too high
        #(This feature is not used currently, and if it was it would NOT detect bad
        # weather, so it should be redesigned before use).

    if vState.guide == 0:
        return False    #guiding disabled, so report no problems here

    #we might have a passing cloud interfering with finding a guide star, so try
    # this a multiple times if necessary; the caller specifies how many retries. In
    # the case of a PP Narrow image, we don't absolutely need guiding, so it uses
    # fewer retries than the imaging steps.
    bRetrying = False

    global gGuiderState
    gGuiderState = 1    # 1 = guider startup: finding guide star, or waiting for low guide error

    retryDelay = 4      #used for pausing between attempts

	#2016.06.06 JU: removed this command; it does not work
    #FixGuidingState(vState)     #try to make sure Gemini is ready to receive guide commands
                                #(if it is in visible mode, it ignores guide commands)
                                #This is controlled with Set_FixGuidingState=<value>

    while retryCnt > 0:
        if bRetrying:
            Log2(2,"######################################")
            Log2(2,"# Repeat attempt to start guiding!!! #")
            Log2(2,"######################################")
            Log2Summary(1,"Repeat attempt to start guiding")
        if not StartGuiding(objectName,vState):
            #it worked, now settle
            if not SettleGuiding(vState):
                #this worked too, so we're done
                Log2Summary(1,"Guiding settled")

                gGuiderState = 2  #guider is running and initially settled
                ResetGuiderMonitoring()
                return False
        #try again (unless out of retries)

        Log2(2,"Guider did not start! Try stopping the guider first to see if that helps.")
        StopGuiding(vState)

        bRetrying = True
        if not bRequireSuccess:
            retryCnt -= 1
        else:
            #check sun altitude
            tup1 = time.gmtime()
            mYear  = tup1[0]
            mMonth = tup1[1]
            mDay   = tup1[2]
            utc    = float(tup1[3]) + (float(tup1[4])/60.) + (float(tup1[5])/3600.)
            alt = CalcSolarAlt(mYear,mMonth,mDay,utc,myLongitude,myLatitude)
            if alt > -6:    #pick an altitude that it is too bright to be able to get guide stars, ever
                gGuiderState = 0  #guiding not running
                return True     #too late in morning (or too early in evening, and should not have started yet!)

        #add a brief delay here
        if retryCnt > 0:
			#2016.06.06 JU: removed this command; it does not work
            #FixGuidingState(vState) #try this again to see if it helps

            Log2(2,"Pausing for %d seconds before trying again" % retryDelay)
            time.sleep(retryDelay)
            retryDelay += 4     #in case we need to do this again later

    #fell out of loop without working
    Log2(2,"######################################")
    Log2(2,"#      GUIDING NEVER STARTED !!!     #")
    Log2(2,"######################################")
    gGuiderState = 0  #guiding not running (but it should be)
    return True

#--------------------------------------------------------------------------------------------------------
# 0 = do nothing (default)
# 1 = issue "Guide Speed" cmd
# 2 = issue "Guide Speed" and then "Precision Guiding" (north) cmd for 1 arcsec
# 3 = issue "Guide Speed" and then "Movement" (north), pause 1 second, then "Quit" movement cmd

#2012.03.27 JU: this function DOES NOT HELP; IGNORE IT.......
#2016.06.06 JU: removed this function
#def FixGuidingState(vState):
#    return

#--------------------------------------------------------------------------------------------------------
def DiffXY(x1,x0,y1,y0):
    diffx = x1 - x0
    diffy = y1 - y0
    diff2 = (diffx * diffx) + (diffy * diffy)
    diff =  math.sqrt(diff2)
    return diff

#--------------------------------------------------------------------------------------------------------
def ReportImageFWHM(vState,filename=""):
  return  #disable for now
  try:
    Log2(4,"Analysis of brightest 100 image stars written to detailed log")
    pp = win32com.client.Dispatch("PinPoint.Plate") #used to find stars in image

    ImagArry = vState.CAMERA.ImageArray      #put imager array into var  (this is safearray of long, not variant)
    pp.ImageArray = ImagArry                 #give the imager array to Pinpoint

    #set value for pp use (don't need actual imager values; we just want to locate
    # stars in the image; we aren't going to plate solve it, but (apparently) these
    # values need to be set before we can find the stars.
    pp.ArcsecPerPixelHoriz = 1.0    #  using Pixels, so set arcsec per pixel = 1.0)
    pp.ArcsecPerPixelVert = 1.0
    pp.InnerAperture = 8        #may want to adjust??
    pp.OuterAperture = 24       #may want to adjust??
    pp.MinimumBrightness = 0
    pp.SigmaAboveMean = 4.0

    pp.FindImageStars()         #scan the imager image for stars

    Log2(4,"Number of stars found in imager field image: %d" % len(pp.ImageStars))

    stars = {}                  #put data into map so we can (reverse) sort by flux
    cntSaturated = 0
    for star in pp.ImageStars:
        if not star.Saturated:
            stars[star.RawFlux] = (star.Y,star.X)   #reversed because Pinpoint diff from MaxIm
        else:
            cntSaturated += 1

    Log2(4,"Number of saturated stars ignored: %d" % cntSaturated)

    #loop over stars in reverse order of flux
    #Measure the brightest 10 stars (that aren't saturated), calc average of their FWHM values.
    limit = 10    #(adjust this later)
    avgSum = 0.
    avgCnt = 0
    for key in sorted(stars.iterkeys(),reverse=True):
        limit = limit - 1
        if limit <= 0:
            break
        X = stars[key][0]
        Y = stars[key][1]
        #Log2(4,"Star: %5.2f, %5.2f,  Flux: %5.2f" % (X,Y,key))
        try:
            info = vState.CAMERA.Document.CalcInformation(X,Y)
        except:
            #this will happen if this is called during a SEQUENCE instead of single image exposure
            continue

        #info[] subscripts:
        #1=max
        #4=avg
        #8=flatness
        #9=FWHM
        #10=HFD
        #11=integrated intensity
        #12=SNR

        avgSum += info[9]
        avgCnt += 1

        Log2(4,"Flux=%7.0f X=%6.2f Y=%6.2f Max=%6.0f Avg=%6.0f Flat=%4.2f FWHM=%5.2f HFD=%5.2f Inten=%8.1f SNR=%6.2f" % (key,X,Y,info[1],info[4],info[8],info[9],info[10],info[11],info[12]))

    if avgCnt > 0:
        avg = avgSum / avgCnt
    else:
        avg = 0.
    Log2(4,"Finished with FWHM logging, average FWHM = %5.2f" % avg)

    line = "# Stars =%4d  # Saturated =%3d  avg FWHM = %5.2f    %s" % (len(pp.ImageStars), cntSaturated, avg, filename )
    LogPerm(line,PERM_FWHM_LOG)
    Log2(3,line)
    del pp
    return
  except:
    Log2(3,"Exception ignored in ReportImageFWHM()")

#--------------------------------------------------------------------------------------------------------
def FindRestrictedGuideStar(vState):
    #The guider has taken an image of the field before coming here; this code
    #is to find a star to use for guiding within the field, that isn't too
    #close to the edge, and that also is within the area specified by the
    #guider restriction settings of the current command (the GuiderExclude...
    #values in vState).
    Log2(0,"calling FindRestrictedGuideStar")

    pp = win32com.client.Dispatch("PinPoint.Plate") #used to find stars in image

    GA = vState.CAMERA.GuiderArray      #put guider array into var  (this is safearray of long, not variant)
    pp.ImageArray = GA                  #give the guider array to Pinpoint
    #(I'm not sure if I need to do this in 2 steps, but it works)

    #set value for pp use (don't need actual guider values; we want to specify
    #  using Pixels, so set arcsec per pixel = 1.0)
    pp.ArcsecPerPixelHoriz = 1.0
    pp.ArcsecPerPixelVert = 1.0
    pp.InnerAperture = 8        #may want to adjust??
    pp.OuterAperture = 24       #may want to adjust??
    pp.MinimumBrightness = 0
    pp.SigmaAboveMean = 4.0

    if SideOfSky(vState) == 0:
        #north is at top of guider field
        excludeNorth = vState.GuideExcludeTop
        excludeSouth = vState.GuideExcludeBottom
        excludeEast  = vState.GuideExcludeLeft
        excludeWest  = vState.GuideExcludeRight
    else:
        #north is at the bottom of the guider field
        excludeNorth = vState.GuideExcludeBottom
        excludeSouth = vState.GuideExcludeTop
        excludeEast  = vState.GuideExcludeRight
        excludeWest  = vState.GuideExcludeLeft

    pp.FindImageStars()         #scan the guider image for stars

    Log2(2,"Number of stars found in guider field image: %d" % len(pp.ImageStars))

    #2013.07.24 JU: if we found very few stars, it must be cloudy; throw weather error
    # (I may need to adjust this in the future if doing off-axis guiding)
    # (I have seen this have zero stars if cloudy; not sure where exactly to set this threshold)
    if len(pp.ImageStars) < 3:
        del pp
        raise WeatherError

    stars = {}                  #put data into map so we can sort by flux
    for star in pp.ImageStars:
        stars[star.RawFlux] = (star.Y,star.X)   #reversed because Pinpoint diff from MaxIm

    #loop over stars in reverse order of flux, and stop when we've found a suitable star
    bFirst = True
    last = (0.,0.)

    border = 60     #MaxIm rejects stars closer than 32 pixels to a border
                    #2013.07.13 JU: was 32, increased to 60; I have reason to suspect
                    #           that 40 is too small, while 55 seemed to work.

    sizeX = vState.CAMERA.GuiderXSize
    sizeY = vState.CAMERA.GuiderYSize
    for key in sorted(stars.iterkeys(),reverse=True):
        X = stars[key][0]
        Y = stars[key][1]
        Log2(3,"Consider star: %5.2f, %5.2f,  Flux: %5.2f" % (X,Y,key))

        #verify that this star isn't a duplicate of the last one (if not first in list)
        if not bFirst:
            diff = DiffXY(X,last[0],Y,last[1])
            #diffx = X - last[0]
            #diffy = Y - last[1]
            #diff2 = (diffx * diffx) + (diffy * diffy)
            #diff =  math.sqrt(diff2)
            if diff < 1.0:
                #don't consider this star
                Log2(5,"Star is too close to the last one (dup): %5.2f,%5.2f" % (X,Y))
                continue
            last = (X,Y)    #save for next test
        else:
            bFirst = False

        #make sure the star isn't too close to actual chip border regardless of other settings
        if X < border or X > (sizeX - border) or Y < border or Y > (sizeY - border):
            #reject this star
            Log2(3,"Rejecting guide star too close to border")
            continue

        #is the star in the area we want?
        if vState.GuideExcludeReverse:
            #exclude middle
            if X > excludeEast and X < (sizeX - excludeWest):
                Log2(3,"-- Rejecting star for X coord(center)")
                continue
            if Y > excludeNorth and Y < (sizeY - excludeSouth):
                Log2(3,"-- Rejecting star for Y coord(center)")
                continue
        else:
            #exclude edges
            if X < excludeEast:
                Log2(3,"-- Reject: X coord within %d of left edge" % excludeEast)
                continue
            if X > (sizeX - excludeWest):
                Log2(3,"-- Reject: X coord within %d of right edge, frame size %d" % (excludeWest,sizeX))
                continue
            if Y < excludeNorth:
                Log2(3,"-- Reject: Y coord within %d of top edge" % excludeNorth)
                continue
            if Y > (sizeY - excludeSouth):
                Log2(3,"-- Reject: Y coord within %d of bottom edge, frame size %d" % (excludeSouth,sizeY))
                continue

        #future enhancement: check for double star here??
        #TODO: I do want to do this to avoid problem, might even work generically?

        #Did we really find a usable star?  If we have 0,0 at this point, we did not
        if X < 32 or Y < 32:
            #bad
            Error("*********************************************")
            Error("Did not find any guide stars not excluded!!!*")
            #Error("Stopping because no simple automated        *")
            #Error("solution is possible for now.               *")
            Error("*********************************************")

            #(what about trying a longer guide exposure, or throwing weather alarm
            # in case we want to wait-out bad weather)?
            del pp

            #SafetyPark(vState)
            #raise SoundAlarmError,'Halting program'
            raise WeatherError
            #return True     #problem

        #use this star
        Log2(1,"Using star at: %5.2f,%5.2f" % (X,Y))
        vState.CAMERA.GuiderAutoSelectStar = False
        vState.CAMERA.GuiderSetStarPosition(X,Y)        #SET THIS *AFTER* SETTING AUTO SELECT TO FALSE FIRST!
#WARNING: I may need to set this false BEFORE taking the field exposure, and we
#might have come here because the regular autoselection didn't start guiding
#and we are trying this as a last resort.  (need to redesign this logic)

        #future enhancement: calculate S/N for this guide star and log it??

        del pp
        return False    #found a star!

    #if we fall out of this loop, we did not pick a star
    del pp
    #return True     #problem
    raise WeatherError

#--------------------------------------------------------------------------------------------------------
def FindGuideStar(objectName,factor,autoselect,vState):
    #Take exposure w/ guide camera and pick a star to use for guiding
    #factor: usually 1, could be larger (=2) if we seem to need longer guide exposures
    #autoselect = True to let MaxIm pick star; this usually populated by vState.GuideAutoStarSelect
    #Return: True if problem, False if it appears we found a (reasonable?) guide star to use.

    bProblem = False
    if autoselect:
        #we let MaxIm pick the guide star:  ---------------------------------
        #Step 1: enable auto select star
        #Step 2: take guider exposure
        Log2(2,"Exposure to find guide star (auto select star), exposure = %5.2f" % (factor * vState.guide_exp))
        try:
            vState.CAMERA.GuiderAutoSelectStar = True     #make sure this is set
            vState.CAMERA.GuiderExpose( factor * vState.guide_exp )
        except:
            niceLogExceptionInfo()
            Error("Exception(1) thrown by call to GuiderExpose; it may or may not recover at this point")
            bProblem = True

        count = 0
        while vState.CAMERA.GuiderRunning:
            count += 1
            time.sleep(2)    #wait until the guide exposure is done
            LogStatus(vState,9)   #do NOT test guider quality here; we are not guiding!
            imaging_db.RecordGuider(vState,False,1041)

        X = vState.CAMERA.GuiderXStarPosition
        Y = vState.CAMERA.GuiderYStarPosition

        #Preserve the guider field image we just took:
        gf_doc = GetGuiderDoc(vState)
        gf_filename = CreateGuiderFilename( objectName, vState )
        gf_doc.SaveFile( gf_filename, 3, False, 1, 0)   # 3=fits format; False=do not autostretch; 1=16-bit data; 0=no compression
        StatusLog(gf_filename)
        Log2(2,"Guider image: " + NameWithoutPath(gf_filename) + " [AUTO SELECT GUIDE STAR]")

        Log2(2,"Guider field exposure complete")
        if count == 0:
            Error("The guider exposure to find a guide star returned immediately; did it actually take an image???")

        if X < 32 or Y < 32:
            #MaxIm may have returned 0,0 because the "brightest" star was too
            # close to the edge.  Use my advanced selection function to pick
            # a star not close to the edge.
            # {{this case doesn't happen very often; it is more common for
            #   the problem to occur later on when the StartGuiding cmd is given}}
            Log2(1,"****************************************************")
            Log2(1,"Warning: automatic selection found star near edge  *")
            Log2(1,"of frame (or no stars at all).                     *")
            Log2(1,"****************************************************")
            #return FindRestrictedGuideStar(vState)
            imaging_db.RecordGuider(vState,False,1020)
            return FindGuideStar(objectName,factor,False,vState)      #recursive call (1 level!)


        Log2(2,"Auto Guide star found: x = " + str(round(vState.CAMERA.GuiderXStarPosition,1)) +
            ", y = " + str(round(vState.CAMERA.GuiderYStarPosition,1)))
        #NOTE: if we manually chose a star position (because the autoselected star
        #      was too near an edge, then the Guide star position reported here
        #      will be 0,0 but THAT IS OK, it really will use the correct location;
        #      we just can't report it this way.

    else:
        #we pick the guide star ourselves, using a subset of the guider image
        #Step 1: disable auto select star
        #Step 2: take guider exposure
        #Step 3: explicity find guide star in desired subset of guider image
        Log2(0,"*** New Guider Logic ****")
        Log2(0,"Exposure to find guide star (will use subset of guider field), exposure = %5.2f" % (factor * vState.guide_exp) )
        try:
            vState.CAMERA.GuiderAutoSelectStar = False     #make sure this is CLEARED
            vState.CAMERA.GuiderExpose( factor * vState.guide_exp )
        except:
            niceLogExceptionInfo()
            Error("Exception(2) thrown by call to GuiderExpose; it may or may not recover at this point")
            bProblem = True

        count = 0
        while vState.CAMERA.GuiderRunning:
            time.sleep(2)    #wait until the guide exposure is done
            count += 1
            LogStatus(vState,8)   #do NOT test guider quality here; we are not guiding!
            imaging_db.RecordGuider(vState,False,1042)

        Log2(2,"Guider field exposure complete(2)")
        if count == 0:
            Error("The guider exposure to find a guide star returned immediately(2); did it actually take an image???")

        #Preserve the guider field image we just took:
        gf_doc = GetGuiderDoc(vState)
        gf_filename = CreateGuiderFilename( objectName, vState )
        gf_doc.SaveFile( gf_filename, 3, False, 1, 0)   # 3=fits format; False=do not autostretch; 1=16-bit data; 0=no compression
        StatusLog(gf_filename)
        Log2(2,"Guider image: " + NameWithoutPath(gf_filename) + " [Restricted SELECT GUIDE STAR]")

        #find guide star within desired subset of guider image
        return FindRestrictedGuideStar(vState)

    return bProblem

def ReportGuiderState(vState,message):
    Log2(3,"ReportGuiderState: %s" % message)
    imaging_db.RecordGuider(vState,False,1021)
    try:    #protect just in case of problem; these actions are not critical
        Log2(4,"Guider settings:  %s" % message)
        Log2(4,"... X Aggr:     " + str(vState.CAMERA.GuiderAggressivenessX))
        Log2(4,"... Y Aggr:     " + str(vState.CAMERA.GuiderAggressivenessY))
        Log2(4,"... Angle:      " + str(round(vState.CAMERA.GuiderAngle,2)))
        Log2(4,"... AutoSelect: " + str(vState.CAMERA.GuiderAutoSelectStar))
        Log2(4,"... Binning:    " + str(vState.CAMERA.GuiderBinning))

        Log2(4,"... Cal State:  " + str(vState.CAMERA.GuiderCalState))
        Log2(4,"... Declination:" + str(vState.CAMERA.GuiderDeclination))
        Log2(4,"... Max move X: " + str(vState.CAMERA.GuiderMaxMoveX))
        Log2(4,"... Max move Y: " + str(vState.CAMERA.GuiderMaxMoveY))
        Log2(4,"... Min move X: " + str(vState.CAMERA.GuiderMinMoveX))
        Log2(4,"... Min move Y: " + str(vState.CAMERA.GuiderMinMoveY))
        Log2(4,"... Moving?:    " + str(vState.CAMERA.GuiderMoving))
        Log2(4,"... Name:       " + str(vState.CAMERA.GuiderName))

        Log2(4,"... Reverse X:  " + str(vState.CAMERA.GuiderReverseX))
        Log2(4,"... Reverse Y:  " + str(vState.CAMERA.GuiderReverseY))
        Log2(4,"... Running:    " + str(vState.CAMERA.GuiderRunning))

        Log2(4,"... X error:    " + str(vState.CAMERA.GuiderXError))
        Log2(4,"... Y error:    " + str(vState.CAMERA.GuiderYError))

        Log2(4,"... X speed:    " + str(vState.CAMERA.GuiderXSpeed))
        Log2(4,"... Y speed:    " + str(vState.CAMERA.GuiderYSpeed))

        Log2(4,"... X Position: " + str(vState.CAMERA.GuiderXStarPosition))
        Log2(4,"... Y Position: " + str(vState.CAMERA.GuiderYStarPosition))

        Log2(4,"... X Size:     " + str(vState.CAMERA.GuiderXSize))
        Log2(4,"... Y Size:     " + str(vState.CAMERA.GuiderYSize))
        #LogOnly("... Cal state: " + str(vState.CAMERA.GuiderCalState) + " (problem if not 2)")  #THIS DOESN'T SEEM TO WORK
    except:
        Error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        Error("I HAVE AN ERROR IN ReportGuiderState() ")
        Error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        niceLogExceptionInfo()
        pass

    try:
        #Dump info from the Camera Control Window!
        hSelects = findTopWindows("Camera Control")

        if len(hSelects) > 1:
            Error( "There are multiple windows open with the title string 'Camera Control'")
            Error( "You must close the other ones so that only the MaxIm camera window is open")
            return

        if len(hSelects) != 1:
            Error( "The MaxIm camera control window could not be found.")
            Error( "Make sure that MaxIm is running and that the")
            Error( "Camera control window has been opened.")
            return

        hTopWnd = hSelects[0]
        #print hex(hTopWnd)

        controls = findControls(hTopWnd, wantedClass="Edit")

        Log2(5, "Edit controls:")
        seen = []
        for ctrl in controls:
            if ctrl not in seen:
                Log2( 5,"%s -- %s" % (hex(ctrl),getEditText(ctrl)))
                seen.append(ctrl)
    except:
        Error("Unable to dump info from the Camera Control Window")

#--------------------------------------------------------------------------------------------------------
def StartGuiding(objectName, vState):
    #This should only be called by StartGuidingConfirmed() !!!
    #return True if problem, False if OK

    Log2(4,"Entry to StartGuiding()")
    ReportGuiderState(vState,"Entry to StartGuiding()")

    #Reset statistics on guiding
    Log2(4,"Resetting GuideX,Y Sum variables")
    global gGuidingXSum
    gGuidingXSum = 0
    global gGuidingYSum
    gGuidingYSum = 0
    global gGuidingCount
    gGuidingCount = 0

    global gGuidingXMax
    gGuidingXMax = 0
    global gGuidingYMax
    gGuidingYMax = 0

    vState.guide_count += 1
    if runMode == 3:
       Log2(2,"Test mode, no guiding")
       return False     #in test mode

    if vState.CAMERA.GuiderRunning:
        #This can happen if the Narrow PP solve fails but we image anyway w/o any repositioning
        Log2(2,"Guider was already running when StartGuiding command issued")
        return False
    if vState.guide == 0:
        Log2(2,"Guiding currently disabled so StartGuiding() does nothing")
        return False      #guiding disabled

    bProblem = FindGuideStar(objectName,1,vState.GuideAutoStarSelect,vState)  #take guide field exposure and pick guide star here; star image saved here

    Log2(2,"Guide star found: x = " + str(round(vState.CAMERA.GuiderXStarPosition,1)) +
        ", y = " + str(round(vState.CAMERA.GuiderYStarPosition,1)))
    if bProblem:
        Error("Warning: FindGuideStar returned PROBLEM state after first call attempt")

    # Reverse guider if pier flip;

    # Warning: cannot call SideOfPier for simulator
    if runMode == 1:
       #if vState.MOUNT.SideOfPier <> SIDE_GUIDER_TRAINED:        #1=looking east, 0=looking west/OTA east
       Log2(4,"Guider was trained on side of sky: %d" % SIDE_GUIDER_TRAINED)
       if SideOfSky(vState) <> SIDE_GUIDER_TRAINED:
          vState.CAMERA.GuiderReverseX = True
          Log2(4,"Setting camera.GuiderReverseX TRUE")
       else:
          vState.CAMERA.GuiderReverseX = False
          Log2(4,"Setting camera.GuiderReverseX false (not reversed)")

    #
    # log info about the guider
    #
    ReportGuiderState(vState,"after saving the Find guide star image")

    Log2(2,"Guider exposure = %5.2f" % vState.guide_exp)

#Note: 2012.05.17: Testing return to CAMERA.GuiderTrack may not be the
#right way to do this; documentation also says to check GuiderRunning
#to see if guider is running.

    Log2(4,"About to call GuiderTrack()")
    ReportGuiderState(vState,"about to call camera.GuiderTrack")

#2012.09.26: this can throw an exception by MaxIm if guiding doesn't start
    try:
        bStarted = vState.CAMERA.GuiderTrack( vState.guide_exp )
    except:
        Error("*** Guider threw an exception; MaxIm probably could not start guiding (could be weather issue) ***")
        niceLogExceptionInfo()
        ReportGuiderState(vState,"threw an exception calling camera.GuiderTrack")
        SafetyPark(vState)
        raise SoundAlarmError,'Halting program'

    if not bStarted:
        #2012.11.16 JU: I suspect this happens when the brightest star autoselected
        #  is too close to an edge.  Try other approach instead:
        Log2(4,"Call to GuiderTrack() returned failure this time")
        ReportGuiderState(vState,"call to camera.GuiderTrack returned failure")

        Error("Guiding was NOT successful at starting; using new logic at finding guide star")
        bProblem = FindGuideStar(objectName,1,False,vState)

        if bProblem:
            Error("Guiding was NOT successful at starting with alternate logic; try once more with longer exposure")
            ReportGuiderState(vState,"call to FindRestrictedGuideStar returned failure")

            bProblem = FindGuideStar(objectName,2,False,vState)
            Log2(2,"Guide star found: x = " + str(round(vState.CAMERA.GuiderXStarPosition,1)) +
                ", y = " + str(round(vState.CAMERA.GuiderYStarPosition,1)))
            if bProblem:
                Error("Warning: FindGuideStar returned PROBLEM state after SECOND call attempt")
                ReportGuiderState(vState,"FindGuideStar returned problem after 2nd call attempt")

#IT STOPS TRYING HERE AND CONTINUES IMAGING EVEN IF GUIDING WOULD NOT START
#ideas: verify that guide camera can still take an image here
#(is there a way I can do a screen capture, showing the MaxIm camera window
# and guider tab, so see if any messages present)
#(or, write something to pass via Windows SendMsg and get text field content?)


            try:
               Log2(0,"2nd time: Guide star found: x = " + str(round(vState.CAMERA.GuiderXStarPosition,1)) +
                  ", y = " + str(round(vState.CAMERA.GuiderYStarPosition,1)))
               if not vState.CAMERA.GuiderTrack( vState.guide_exp * 2 ):
                  Error("Guiding was NOT successful even after 2nd attempt.  PROBLEM!!!")
                  ReportGuiderState(vState,"call to camera.GuiderTrack returned failure in 2nd attempt")

                  time.sleep(1)
                  if vState.CAMERA.GuiderRunning:
                     Error("NOTE: GuiderRunning reports true although GuiderTrack startup reported false. What does this mean?")
                     imaging_db.RecordGuider(vState,False,1043)

                  else:
                     Log2(0,"Note: GuiderRunning also reports false.")
                     imaging_db.RecordGuider(vState,False,1044)

                  bProblem = True
                  ReportGuiderState(vState)
            except:
                  Error("Exception thrown during 2nd attempt to start guiding.  PROBLEM!!!")
                  ReportGuiderState(vState,"call to camera.GuiderTrack threw exception in 2nd attempt")
                  bProblem = True

    if bProblem:
        vState.guide_failure_count += 1

    #2012.01.16 JU: if guiding not running here, raise alert in all cases
    #it should be guiding at this point; check it
    time.sleep(1)   #wait a moment to make sure it should be running
    if not vState.CAMERA.GuiderRunning:
        #I saw this happen (apparently for the first time) on 2012.08.06  00:11:42 CDT
        Error("***Guider does not report running; wait a few seconds to give it one last chance:")
        ReportGuiderState(vState,"Guider does not report running")

        time.sleep(10)
        if not vState.CAMERA.GuiderRunning:
            #3rd and final attempt, try other technique
            Error("Guider still not running even after waiting; try calling FindRestrictedGuideStar function as a last resort")
            ReportGuiderState(vState,"Guider still does not report running even after waiting")
            return FindGuideStar(objectName,2,False,vState) #(this uses Restricted logic)

        Log2(0,"Guider did resume after waiting extra time.")
    Log2(4,"Verified that guider appears to be running at this point")
    ReportGuiderState(vState,"Guider appears to be running at this point -- success")

    return bProblem

#--------------------------------------------------------------------------------------------------------
def SettleGuiding(vState):
   #return False if OK, True if problem
   # wait until guiding if better than configured offset (or waited too long)

   if not vState.CAMERA.GuiderRunning:
     Log2(0,"PROBLEM: Guider not running when SettleGuiding() called!")
     return True    #2013.08.08 JU: change this so this indicates a problem

   started = time.time()
   Log2(2,"Settle Guiding better than %5.2f (max wait %d sec)" % (vState.GuidingSettleThreshold,vState.GuidingSettleTime))

   loopSleepTime = 2
   if vState.guide_exp > 1 and vState.guide_exp < 10:
       try:
           loopSleepTime = int(vState.guide_exp)
           Log2(4,"Settle loop using sleep time = " % loopSleepTime )
       except:
           pass

   bSkip = True
   while (time.time() - started) < vState.GuidingSettleTime:
      flag = "O"
      if vState.CAMERA.GuiderNewMeasurement:
         #Note: we only call LogStatusBase during guider settle when there is a NEW measurement to report
         global RecentGuideX
         imaging_db.RecordGuider(vState,True,1049)

         RecentGuideX = vState.CAMERA.GuiderXError
         global RecentGuideY
         RecentGuideY = vState.CAMERA.GuiderYError
         flag = "s"     #s=Settle wait state, also this is a new guider measurement so not stale data

#THIS SECTION...
         global gGuidingXSum
         global gGuidingYSum
         global gGuidingCount
         gGuidingXSum += (RecentGuideX * RecentGuideX)
         gGuidingYSum += (RecentGuideY * RecentGuideY)
         gGuidingCount += 1

         global gGuidingXMax
         global gGuidingYMax
         if abs(RecentGuideX) > gGuidingXMax and RecentGuideX != -99:
              gGuidingXMax = abs(RecentGuideX)

         if abs(RecentGuideY) > gGuidingYMax and RecentGuideY != -99:
              gGuidingYMax = abs(RecentGuideY)

         if abs(RecentGuideX) < vState.GuidingSettleThreshold and abs(RecentGuideY) < vState.GuidingSettleThreshold:
               #if this is first measurement; don't use it, want another small one (but must read variables to clear them)
               if bSkip:
                  bSkip = False
               else:
                  LogStatusBase(vState,RecentGuideX,RecentGuideY, flag,"","","","","","","","")
                  Log2(2,"Guider settled in %s seconds" % (str(round(time.time() - started,1))))
                  return False
#=======================
         #
         #data available (not stale), calc boxcar avg of X,Y
#WE ONLY COME HERE IF NOT STALE; DON'T NEED TO CHECK
         #global gListStaleGuideData
         #gListStaleGuideData.append(0)    #add flag that data is not stale
         avgS = 0
         savgS = "%4.2f" % avgS
         slenAvgS = "%2d" % 0

         #we can only calc the guide errors if the data is NOT stale
         global gListGuideXErrors
         if len(gListGuideXErrors) >= 10:
             gListGuideXErrors = gListGuideXErrors[1:]
         gListGuideXErrors.append(RecentGuideX)
         avgX = CalcListAverage(gListGuideXErrors)

         global gListGuideYErrors
         if len(gListGuideYErrors) >= 10:
             gListGuideYErrors = gListGuideYErrors[1:]
         gListGuideYErrors.append(RecentGuideY)
         avgY = CalcListAverage(gListGuideYErrors)

         savgX =  "%4.2f" % avgX
         savgY =  "%4.2f" % avgY
         slenAvgX = "%2d" % len(gListGuideXErrors)
         slenAvgY = "%2d" % len(gListGuideYErrors)
         #LogOnly("Guide monitoring: avgX = %5.2f (cnt %d)  avgY = %5.2f (cnt %d)  avgS = %4.2f (cnt %d)" % (avgX,len(gListGuideXErrors),avgY,len(gListGuideYErrors),avgS,len(gListStaleGuideData)))

         if len(gListGuideXErrors) >= 10 and avgX > (vState.GuidingSettleThreshold * 4) and TestGuidingTrend("X",gListGuideXErrors):  #1.5:
               #the average X pixel guide error over last 10 measurements is > 4*SettleThreshold
               Log2(0,"*****************************")
               Log2(0,"** Bad startup guiding (X) **")
               Log2(0,"*****************************")
               Log2(3,"Number of errors to evaluate: %d, avgx: %4.2f, threshold: %4.2f" % (len(gListGuideXErrors),avgX,(vState.GuidingSettleThreshold * 4)))
               DumpGuideErrorList("X",gListGuideXErrors)
               imaging_db.RecordGuider(vState,False,1045)
               bReturn = True

         if len(gListGuideYErrors) >= 10 and avgY > (vState.GuidingSettleThreshold * 4) and TestGuidingTrend("Y",gListGuideYErrors):  #1.5:
               #the average Y pixel guide error over last 10 measurements is > 4*SettleThreshold
               Log2(0,"*****************************")
               Log2(0,"** Bad startup guiding (Y) **")
               Log2(0,"*****************************")
               Log2(3,"Number of errors to evaluate: %d, avgx: %4.2f, threshold: %4.2f" % (len(gListGuideYErrors),avgY,(vState.GuidingSettleThreshold * 4)))
               DumpGuideErrorList("Y",gListGuideYErrors)
               imaging_db.RecordGuider(vState,False,1046)
               bReturn = True

         tupx = CheckOscillation(gListGuideXErrors,vState)
         xMsg = tupx[1]
         if tupx[0]:
               #report problem
               Log2(0,"*************************************")
               Log2(0,"** Guiding startup Oscillation (X) **")
               Log2(0,"*************************************")
               Log2(0,"msg = %s" % tupx[1])
               #if X-aggr > 3, decr X-aggr
               try:
                       xAggr = vState.CAMERA.GuiderAggressivenessX
                       yAggr = vState.CAMERA.GuiderAggressivenessY

                       if xAggr > 5:
                            xAggr = xAggr - 1
                            vState.CAMERA.GuiderAggressivenessX = xAggr
                            Log2(3,"Reducing XAggr to %f" % xAggr)
               except:
                   Log2(3,"Error, unable to adjust X aggressiveness")
               bReturn = True

         tupy = CheckOscillation(gListGuideYErrors,vState)
         yMsg = tupy[1]
         if tupy[0]:  #(this problem more common in X than in Y)
               #report problem
               Log2(0,"*************************************")
               Log2(0,"** Guiding startup Oscillation (Y) **")
               Log2(0,"*************************************")
               Log2(0,"msg = %s" % tupy[1])
               imaging_db.RecordGuider(vState,False,1047)
               #if Y-aggr > 3, decr Y-aggr
               try:
                       yAggr = vState.CAMERA.GuiderAggressivenessY

                       if yAggr > 6:            #try reducing, but don't let this reduce too far
                            yAggr = yAggr - 1
                            vState.CAMERA.GuiderAggressivenessY = yAggr
                            Log2(3,"Reducing YAggr to %f" % yAggr)
               except:
                   Log2(3,"Error, unable to adjust Y aggressiveness")
               bReturn = True

         LogStatusBase(vState,RecentGuideX,RecentGuideY,flag,savgX,slenAvgX,savgY,slenAvgY,savgS,slenAvgS,xMsg,yMsg)


#======================
      #LogStatusBase(vState,RecentGuideX,RecentGuideY, flag,"","","","","","","","")
      time.sleep(loopSleepTime)

   if vState.guide == 2:    #I don't think I've ever used this option:
       #Guider didn't settle; this might happen if no guide stars bright enough to be
       # used reliably. We might get better results turning off guiding in this case
       # so we don't guide on 'noise'.
       Error("ALERT! Guider did not settle during configured period; we are configured to run WITHOUT GUIDING in this case!")
       imaging_db.RecordGuider(vState,False,1048)
       StopGuiding(vState)
       return False


   Error("ALERT! Guider did not settle during configured period!!!")
   return True

#--------------------------------------------------------------------------------------------------------
def StopGuiding(vState):
    # This is called when the guider is currently tracking and we
    #  want it to stop.  While there is a method to do this, GuiderStop,
    #  that method is not callable from Python for some reason. So this
    #  function was written to work around this.

    global gGuiderState
    gGuiderState = 0

    if runMode == 3:
       Log2(2,"StopGuiding: Test mode; nothing done")
       return

    if not vState.CAMERA.GuiderRunning:
        Log2(5,"StopGuiding: guider not running so nothing done")
        return

    #Statistics
    global gGuidingXSum
    global gGuidingYSum
    global gGuidingCount
    global gGuidingXMax
    global gGuidingYMax

    if gGuidingCount == 0:
        Log2(2,"Guiding statistics: no events to calculate")
        #LogBase("  0                            %d  %9s  %9s" % (vState.MOUNT.SideOfPier,UTIL.HoursToHMS( vState.MOUNT.RightAscension),DegreesToDMS( vState.MOUNT.Declination )),GUIDING_LOG)
        LogBase("  0                            %d  %9s  %9s" % (SideOfSky(vState),UTIL.HoursToHMS( vState.MOUNT.RightAscension,":",":","",1),DegreesToDMS( vState.MOUNT.Declination )),GUIDING_LOG)

    else:
        avgX = math.sqrt(gGuidingXSum / gGuidingCount)
        avgY = math.sqrt(gGuidingYSum / gGuidingCount)
        Log2(4,"Guiding statistics (RMS): x = %5.2f  y = %5.2f  cnt = %d  Max-X = %5.2f  Max-Y = %5.2f" % (avgX,avgY,gGuidingCount,gGuidingXMax,gGuidingYMax))
#Consider logging this guider info more frequently, not just when guiding is stopped;
#maybe log every 100 guider measurements
        #LogBase("%4d %5.2f %5.2f   %5.2f %5.2f  %d  %9s  %9s" % (gGuidingCount,avgX,avgY,gGuidingXMax,gGuidingYMax,vState.MOUNT.SideOfPier,UTIL.HoursToHMS( vState.MOUNT.RightAscension),DegreesToDMS( vState.MOUNT.Declination )), GUIDING_LOG)
        LogBase("%4d %5.2f %5.2f   %5.2f %5.2f  %d  %9s  %9s" % (gGuidingCount,avgX,avgY,gGuidingXMax,gGuidingYMax,SideOfSky(vState),UTIL.HoursToHMS( vState.MOUNT.RightAscension,":",":","",1),DegreesToDMS( vState.MOUNT.Declination )), GUIDING_LOG)



    Log2(2,"StopGuiding: starting shutdown")

    # I wrote a VB script that calls the StopGuider() cmd; this seems to work!
    ret = os.system("cscript c:\\fits_script\\StopGuider.vbs")

    imaging_db.RecordGuider(vState,False,1050)

    if ret != 0:
        Error("Call to shut down guider failed")
        Error("*** EXPECT PROBLEMS TO OCCUR NOW ***")
        vState.guide_shutdown_failure_count += 1
    else:
        Log2(2,"StopGuiding: shutdown completed")
        #what if the shutdown isn't really finished yet? add extra delay
        time.sleep(2)

    #make sure any guide logging from this point does not show values (until guiding resumes)
    global RecentGuideX
    RecentGuideX = -99

    global RecentGuideY
    RecentGuideY = -99


#--------------------------------
def GetGuiderDoc(vState):
    #loop over open documents until find one with the title: "Autoguider Image"
    gdoc = vState.MAXIM.FirstDocument
    if gdoc.DisplayName == "Autoguider Image":
        return gdoc

    while 1:
         gdoc = vState.MAXIM.NextDocument
         if gdoc.DisplayName == "Autoguider Image":
             return gdoc
         #the loop will throw an exception if we don't eventually find the guider image, and that is fine
         #Log2(0, "Found document name: " + gdoc.DisplayName)

    return vState.MAXIM.FirstDocument  #return last document seen just to have something


#=====================================================================================
#==== SECTION  @@Util ================================================================
#=====================================================================================
def cosd(degrees):
    return math.cos( math.radians(degrees) )

#--------------------------------
def CalcCropSize(binning,cameraXSize,cameraYSize):
    #calculate 1/4 the frame size, return tuple (startX,startY,NumX,NumY)
    realXSize = int(cameraXSize / binning)
    realYSize = int(cameraYSize / binning)

    centerX = int(realXSize / 2)
    centerY = int(realYSize / 2)
    diffX   = int(realXSize / 4)
    diffY   = int(realYSize / 4)

    startX = centerX - diffX
    startY = centerY - diffY
    numX = centerX  # = realXSize / 2
    numY = centerY  # = realYSize / 2

    return (startX, startY, numX, numY)

def NoCroppingSize(cameraXSize,cameraYSize):
    startX = 0
    startY = 0
    numX = cameraXSize
    numY = cameraYSize
    return (startX, startY, numX, numY)


#--------------------------------
#Code for "center-of-mass" method to try to center images (did not work)

#--------------------------------
def getPPSolve(vState):
   # 0=imager, 1=guider
   if vState.ppState[0].active and vState.ppState[1].active:
      return "both"
   if vState.ppState[0].active and not vState.ppState[1].active:
      return "narrow"
   if not vState.ppState[0].active and vState.ppState[1].active:
      return "wide"
   return "none"

#--------------------------------
def filterToInt(pFilter):       #convert letter into filter code
    sFilter = str(pFilter).upper()
    #LogOnly("filterToInt: called with <%s>, converted to <%s>" % (pFilter,sFilter))

    global gCamera
    if gCamera == "QSI-583":
        #LogOnly("filterToInt: called for QSI camera")

        #print "I need to set the QSI filter wheel mapping"
        #raise "I need to set the QSI filter wheel mapping"
        #These appear to be the correct mappings.
        if sFilter == 'L':
                #LogOnly("filterToInt returns: 3 (L-qsi)")
                return 3
        if sFilter == 'R':
                #LogOnly("filterToInt returns: 0 (R-qsi)")
                return 0
        if sFilter == 'G':
                #LogOnly("filterToInt returns: 1 (G-qsi)")
                return 1
        if sFilter == 'B':
                #LogOnly("filterToInt returns: 2 (B-qsi)")
                return 2
        if sFilter == 'H' or sFilter == 'HA' or sFilter == 'H-ALPHA':
                #LogOnly("filterToInt returns: 4 (Ha-qsi)")
                return 4
        if sFilter == 'V':
                #LogOnly("filterToInt returns: 4 (V-qsi)")	#REPLACEMENT OF HA FILTER 2015.06.19
                return 4
        if sFilter == '0' or sFilter == '1' or sFilter == '2' or sFilter == '3' or sFilter == '4':
                LogOnly("filterToInt returns input number: %d (qsi)" % int(sFilter))
                return int(sFilter)

        Error("********************************************")
        Error("* Filter could not be parsed; value = %s" % sFilter)
        Error("********************************************")
        LogOnly("filterToInt could not parse value, returning 3 (qsi)" )
        return 3    #just to be safe, return luminance filter
    else:
        LogOnly("filterToInt: called for NON-QSI camera")
        if sFilter == 'L':
                LogOnly("filterToInt returns: 3 (L NON-qsi)")
                return 3
        if sFilter == 'R':
                LogOnly("filterToInt returns: 0 (R NON-qsi)")
                return 0
        if sFilter == 'G':
                LogOnly("filterToInt returns: 1 (G NON-qsi)")
                return 1
        if sFilter == 'B':
                LogOnly("filterToInt returns: 2 (B NON-qsi)")
                return 2
        if sFilter == '0' or sFilter == '1' or sFilter == '2' or sFilter == '3':
                LogOnly("filterToInt returns input number: %d (NON-qsi)" % int(sFilter))
                return int(sFilter)

        LogOnly("filterToInt could not parse value, returning 3 (NON-qsi)" )
        return 3    #just to be safe, return luminance filter

#--------------------------------
def strCamera(camera):
   if camera == 0:
      return "narrow"
   else:
      return "-WIDE-"

#--------------------------------------------------------------------------------------------------------
def isVisible(azimuth,elevation):
    #The current horizon at my telescope (custom to me and my location)
    #return true if al/el is above the horizon treeline; false means blocked.

    #New value as of August 2011 for observatory in field, including south wall DOWN:
    Horiz  = [ (10,30),  (20,1),  (30,1),  (40,1),  (50,1),  (60,1),  (70,1),  (80,1),  (90,1), (100,1),    #2013.11.18 JU: reduced eastern horizon so won't abort if above horizon at all
              (110,1), (120,1), (130,1), (140,1), (150, 8), (160, 8), (170,8), (180,10), (190,10), (200,15),
              (210,15), (220,15), (230,15), (240,13), (250,12), (260,17), (270,25), (280,25), (290,30), (300,35),
              (310,45), (320,45), (330,45), (340,44), (350,43), (360,42)]
##    Horiz  = [ (10,30),  (20,35),  (30,20),  (40,20),  (50,20),  (60,20),  (70,20),  (80,15),  (90,14), (100,13),
##              (110,15), (120,17), (130,19), (140,15), (150, 8), (160, 8), (170,10), (180,14), (190,14), (200,19),
##              (210,20), (220,20), (230,20), (240,18), (250,17), (260,22), (270,30), (280,35), (290,36), (300,40),
##              (310,45), (320,45), (330,45), (340,44), (350,43), (360,42)]

    for (az,el) in Horiz:
        if azimuth < az:
            if elevation >= el:
                return 1    #true
            else:
                Log2(2,"Target elevation %5.1f is less than expected horizon %d, at azimuth %d" % (elevation,el,azimuth))
                return 0    #false

#--------------------------------------------------------------------------------------------------------
#function usage: jd(YEAR, MONTH, DAY of MONTH, HOUR, MINUTES, SECONDS)
def jd(yy, mm, dd, hr, mn, sec):
    #LogOnly("fn: jd")
    if yy < 0:
        yy = yy + 1
    hr = hr + (float(mn) / 60) + float(sec)/3600
    ggg = 1
    if yy <= 1585:
        ggg = 0
    JD = -1 * (7 * (((mm + 9) // 12) + yy) // 4)
    s = 1
    if (mm - 9) < 0:
        s = -1
    a = abs(mm - 9)
    j1 = math.floor(yy + s * (a // 7))
    j1 = -1 * (((j1 // 100) + 1) * 3 // 4)
    JD = JD + (275 * mm // 9) + dd + (ggg * j1)
    JD = JD + 1721027 + 2 * ggg + 367 * yy - 0.5
    JD = JD + float(hr)/24
    JD = round(JD, 5)

    return JD
# I found the following code, simplier; need to check that gives same result:
# From: http://aa.usno.navy.mil/faq/docs/JD_Formula.php
#   INTEGER FUNCTION JD (YEAR,MONTH,DAY)
#C
#C---COMPUTES THE JULIAN DATE (JD) GIVEN A GREGORIAN CALENDAR
#C   DATE (YEAR,MONTH,DAY).
#C
#    INTEGER YEAR,MONTH,DAY,I,J,K
#C
#    I= YEAR
#    J= MONTH
#    K= DAY
#C
#    JD= K-32075+1461*(I+4800+(J-14)/12)/4+367*(J-2-(J-14)/12*12)/12-3*((I+4900+(J-14)/12)/100)/4
#C
#    RETURN
#    END

#--------------------------------
def GetSequenceNumber( basePath, baseName ):  #return highest used 5 digit seq number for this path and filename
    # basePath example:  C:\fits\
    # baseName example:  M57_
    #
    # This routine finds the highest sequence number in use that matches a specified base filename, assumes suffix of ".fts"
    # For example, if C:\fits\M57_00003.fts exists and is the only matching file, this will return 3

    #make sure path has terminating backslash
    if not basePath.endswith("\\"):
        basePath = basePath + "\\"

    #we'll assume the directory basePath already exists [future enhancement: create directory if necessary]

    #search pattern based on baseName (regular expression)
    Pattern = baseName + "([0-9][0-9][0-9][0-9][0-9]).*\.fts$"
    #Pattern = baseName + "([0-9][0-9][0-9][0-9][0-9]).fts$"

    #what files are in the directory
    #print "Pattern = ",Pattern
    #print "basePath = ",basePath
    col = os.listdir( basePath )

    #loop over these filenames and see if any match our pattern
    retValue = 0
    for name in col:
        #print "@ name = ",name

        #new approach: break up name:  xxxxxx00000.fts
        front = name[0:-9]
        back  = name[-9:]
        #print "front=",front
        #print "back=",back
        #if re.match(Pattern,name):
        if front == baseName:
            #match found
            #what is the sequence number found for this file?
            #     xxxxxxxx_01111.fts
            #              987654321  so want from -9 to -4
            seqString = name[-9:-4]   #get the last 5 chars of the name (should be the seq number part)
            #print "seqString = ",seqString
            try:
                seqInt = int( seqString )
                if seqInt > retValue:
                    retValue = seqInt   #track the GREATEST one seen
            except:
                #print "Exception in re.match"
                pass    #this was not a number (probably will not happen)

    #print "Highest seq number = ", retValue
    return retValue

#--------------------------------
def GetShortSequenceNumber( basePath, baseName ):  #return highest used three (3) digit seq number for this path and filename
    # basePath example:  C:\fits\
    # baseName example:  M57_
    #
    # This routine finds the highest sequence number in use that matches a specified base filename, assumes suffix of ".fts"
    # For example, if C:\fits\M57_003.fts exists and is the only matching file, this will return 3

    #make sure path has terminating backslash
    if not basePath.endswith("\\"):
        basePath = basePath + "\\"

    #we'll assume the directory basePath already exists [future enhancement: create directory if necessary]

    #search pattern based on baseName (regular expression)
    #Pattern = baseName + "([0-9][0-9][0-9]).*\.fts$"

    #what files are in the directory
    #print "Pattern = ",Pattern
    #print "basePath = ",basePath
    col = os.listdir( basePath )

    #loop over these filenames and see if any match our pattern
    retValue = 0
    for name in col:
        #print "@ name = ",name

        #new approach: break up name:  xxxxxx000.fts
        front = name[0:-7]
        back  = name[-7:]
        #print "front=",front
        #print "back=",back
        #if re.match(Pattern,name):
        if front == baseName:
            #match found
            #what is the sequence number found for this file?
            #     xxxxxxxx_011.fts
            #              7654321  so want from -7 to -4
            seqString = name[-7:-4]   #get the last 3 chars of the name (should be the seq number part)
            #print "seqString = ",seqString
            try:
                seqInt = int( seqString )
                if seqInt > retValue:
                    retValue = seqInt   #track the GREATEST one seen
            except:
                pass    #this was not a number (probably will not happen)

    #print "Highest seq number = ", retValue
    return retValue

#--------------------------------
def CreateEnhancedFilename( thepath, objectName, vState,binNumber,filterLetter,exp,crop):
    #build filename:  Objname_yyyymmdd_expFbc_sss
    #  where sss is generated sequence number (3 digit instead of 5)[this must be LAST for the seq num logic to work]
    #  and F is filter letter (could be two letters for 'Ha'
    #  and b is binning factor: nothing if binned 1x1, 'b' if 2x2, else number for higher binning
    #  and c is crop flag; not present normally, 'c' if image is cropped
    #  and exp is exposure in seconds
    LogOnly("CreateEnhancedFilename:")
    LogOnly("   thepath = %s" % thepath)
    LogOnly("   objectname = %s" % objectName)
    LogOnly("   binNumber  = %d" % binNumber)
    LogOnly("   filterLtr  = %s" % filterLetter)
    LogOnly("   exposure   = %s" % str(exp))
    root = objectName
    root.replace( ' ', '_' )    #blanks become underscores
    root.replace('\\', '_' )    #backslash becomes understore (so not interpreted as path)

    #make sure the base filename has an '_' at the end
    if not root.endswith("_"):
        root = root + "_"

	monthday = ""
    temp = ObservingDateString()
    monthday = temp[4:] + "_"
    #print "monthday = %s" % monthday
    #monthday = time.strftime("%m%d_", time.gmtime( time.time() ) )
    root = root + monthday

    if binNumber == 1:  binLetter = ""
    elif binNumber == 2:    binLetter = "b"
    else:                   binLetter = str(binNumber)[0]

    cropLetter = ""
    try:
        if crop == "yes":
            cropLetter = "c"
    except:
        pass

    iexp = int(exp)  #only use integer component
    suffix = "%d%s%s%s_" % (iexp,filterLetter,binLetter,cropLetter)
    root = root + suffix

    seq = GetShortSequenceNumber(thepath, root) + 1  #the +1 is to use next AVAILABLE number

    basename = ('%s%03d.fts') % (root,seq)
    fullname = os.path.join(thepath,basename)

    #DOES THIS FILENAME ALREADY EXIST? IT SHOULD NOT (unless I have a code error here):
    currentFiles = os.listdir(thepath)
    if basename in currentFiles:
        #I don't think this error has ever occurred
        Error("The generated filename already exists; filename: %s  path: %s" % (basename,thepath))
        Error("directory list: %s" % str(currentFiles))
        SafetyPark(vState)
        raise "ProgramError"

    return fullname

#--------------------------------
def CreateFilename( thepath, objectName, vState,isMany):
    # vState.path is path to where the filename will be created
    # objectName  name of the object being imaged; this gets cleaned up (if necessary)
    #      and turned into the basic part of the filename; the sequence number is added to it
    # Return a full path/filename with sequence number, ready to use for saving a fits image
    # Name pattern:
    #    <path>\<objectid>_MMDD_99999.fts

    root = objectName
    root.replace( ' ', '_' )    #blanks become underscores
    root.replace('\\', '_' )    #backslash becomes understore (so not interpreted as path)

    #make sure the base filename has an '_' at the end
    if not root.endswith("_"):
        root = root + "_"

    if isMany == 1:
        yearmonthday = ObservingDateString() # time.strftime("%Y%m%d", time.gmtime( time.time() ) )
        rootDate = root + yearmonthday
        fullname = ('%s%s.fts') % (thepath,rootDate)
        #does this name already exist? try opening it
        try:
            f = open(fullname,"r")
            f.close()  #it exists, so we cannot use it; continue below
        except:
            #file does NOT exist, so we do use it
            return fullname

    monthday = ""
    temp = ObservingDateString()
    monthday = temp[4:] + "_"
    #print "monthday = %s" % monthday
	#EXCEPTION THROWN ABOVE!
    #monthday = time.strftime("%m%d_", time.gmtime( time.time() ) )
    root = root + monthday

    seq = GetSequenceNumber(thepath, root) + 1  #the +1 is to use next AVAILABLE number

    fullname = ('%s%s%05d.fts') % (thepath,root,seq)
    return fullname

#--------------------------------
def CreateGuiderFilename( objectName, vState):
    # Name to use when saving a Guider image that was taken to find a guide star
    # Return a full path/filename with sequence number, ready to use for saving a fits image;
    #  the filename also includes the GMT date (month/day)
    # Name format:
    #     GF_mmdd_<objname>_99999
    #     GF_0705_IC1234_12345

    prefix = "GF_" + ObservingDateString()[4:] + "_"
    #prefix = time.strftime("GF_%m%d_", time.gmtime( time.time() ) )

    root = prefix.strip() + objectName.strip()
    root.replace( ' ', '_' )    #blanks become underscores  [DOES THIS WORK??]
    root.replace('\\', '_' )    #backslash becomes understore (so not interpreted as path)

    #make sure the base filename has an '_' at the end
    if not root.endswith("_"):
        root = root + "_"

    seq = GetSequenceNumber(pathGuider, root) + 1  #the +1 is to use next AVAILABLE number

    fullname = ('%s%s%05d.fts') % (pathGuider,root,seq)
    return fullname

#--------------------------------
def GetRecentFitsFilename(pathname,backCount):
    #returns the FITS filename from the specified directory that has the LATEST datetime stamp,
    # if backCount > 0 then the lastest less the backCount value; ie. backCount = 1 then penultimate filename based on datetime
    # if not enough files present for backCount, then use earliest one
    # if no files present at all, throw exception
    #IDEA: compare time to now, and throw exception if file is too old??

    filelist = os.listdir(pathname)

    content = {}
    for name in filelist:
        ufilename = name.upper()
        if ufilename.find(".FIT") < 0 and ufilename.find(".FTS") < 0 :
            continue

        fullname = os.path.join(pathname,name)
        content[name] = os.path.getmtime(fullname)

    if len(content) == 0:
        Error("No files found in GetRecentFitsFilename()")
        SafetyPark(vState)
        raise "problem"

    # Sort keys, based on time stamps
    items = content.keys()
    items.sort(lambda x,y: cmp(content[x],content[y]))
    items.reverse()     #want most recent first

    reportName = items[0]
    i = 0
    for item in items:
        if i == backCount:
            return(item)
        i += 1

    return( items[len(items) - 1])    #just return the last name (which will be earliest file)

#--------------------------------
def DegreesToDMS(dDec): #return string dd:mm:ss from decimal value
    #there is a problem in Python callin gthe UTIL.DegreesToDMS() function
    # because it returns a 'degree' symbol character.
    sign = ' '
    if dDec < 0:
        sign = '-'
        dDec = -dDec

    secTotal = int( round(dDec * 3600) )
    nSec = secTotal % 60
    minTotal = secTotal / 60
    nMin = minTotal % 60
    nDec = minTotal / 60

    retString = sign + str(nDec) + ':'
    if nMin < 10:
        retString += '0'
    retString += str(nMin) + ':'
    if nSec < 10:
        retString += '0'
    retString += str(nSec)

    return retString

#--------------------------------
def intToFilter(iFilter):
    if iFilter == 0:
        return 'Red'
    if iFilter == 1:
        return 'Green'
    if iFilter == 2:
        return 'Blue'
    if iFilter == 3:
        return 'Luminance'

    return '<invalid code>'

def hours2rad(hours):
    return hours / (12./math.pi)
def deg2rad(deg):
    return deg / (180./math.pi)
def rad2hours(rad):
    return rad * (12./math.pi)
def rad2deg(rad):
    return rad * (180./math.pi)

def Cleanup(astr):   #remove trailing decimal part from ephem.Angle string
    str = "%s" % astr
    pos = str.find('.')
    if pos < 0:
        return str
    return str[0:pos]
def FixDecSign(str):    #string is Dec string, if no sign then prepend '+' in front of it
    if str[0] == '-' or str[0] == '+':
        return str
    return '+' + str

#--------------------------------------------------------------------------------------------------------
def PrecessLocalToJ2000(dJNowRA, dJNowDec):
    #Newest approach: use ephem
    x = ephem.Equatorial(hours2rad(dJNowRA), deg2rad(dJNowDec),epoch=ephem.now())
    y = ephem.Equatorial(x,epoch=ephem.J2000)
    tup = (rad2hours(y.ra), rad2deg(y.dec))
    Log2(5,"Precess: Starting JNow coords:  %s  %s" % (UTIL.HoursToHMS(dJNowRA,":",":","",1)  , DegreesToDMS(dJNowDec)))
    Log2(5,"         Result J2000 coords:   %s  %s" % (UTIL.HoursToHMS(tup[0],":",":","",1) , DegreesToDMS(tup[1])))
    return tup

    #PREVIOUS APPROACH, WORKED (MOSTLY?)========================================================
    #New approach
    star = win32com.client.Dispatch("NOVAS.Star")
    star.RightAscension = dJNowRA
    star.Declination = dJNowDec

    vPos = win32com.client.Dispatch("NOVAS.PositionVector")
    vPos.SetFromStar(star)

    t = time.gmtime( time.time() )    #yyyy,mm,dd,hh,mi,sec;  Use current moment in time
    epochNow = jd( t[0], t[1], t[2], t[3], t[4], t[5])
    epoch2000 = jd( 2000, 1, 1, 12, 0, 0)

    vPos.Precess(epochNow, epoch2000)           # JNow -> J2000
    tup = (vPos.RightAscension,vPos.Declination)

    del vPos
    del star

    #Log2(5,"Precess: Starting JNow coords:  %s  %s" % (UTIL.HoursToHMS(dJNowRA,":",":","",1)  , DegreesToDMS(dJNowDec)))
    #Log2(5,"         Result J2000 coords:   %s  %s" % (UTIL.HoursToHMS(tup[0],":",":","",1) , DegreesToDMS(tup[1])))

    return tup


#--------------------------------------------------------------------------------------------------------
def PrecessJ2000ToLocal(dJ2000RA, dJ2000Dec):
    # inputs: dJ2000RA, dJ2000Dec   decimal values in J2000
    # outputs: tuple: (dLocalRA, dLocalDec)  decimal values in Local Epoch

    #Newest approach: use ephem
    x = ephem.Equatorial(hours2rad(dJ2000RA), deg2rad(dJ2000Dec),epoch=ephem.J2000)
    y = ephem.Equatorial(x,epoch=ephem.now())
    tup = (rad2hours(y.ra), rad2deg(y.dec))
    Log2(5,"Precess: Starting J2000 coords:  %s  %s" % (UTIL.HoursToHMS(dJ2000RA,":",":","",1)  , DegreesToDMS(dJ2000Dec)))
    Log2(5,"         Result JNow coords:     %s  %s" % (UTIL.HoursToHMS(tup[0],":",":","",1)  , DegreesToDMS(tup[1])))
    return tup



    #PREVIOUS APPROACH, WORKED (MOSTLY?)========================================================
    star = win32com.client.Dispatch("NOVAS.Star")
    star.RightAscension = dJ2000RA
    star.Declination = dJ2000Dec

    vPos = win32com.client.Dispatch("NOVAS.PositionVector")
    vPos.SetFromStar(star)

    t = time.gmtime( time.time() )    #yyyy,mm,dd,hh,mi,sec;  Use current moment in time
    epochNow = jd( t[0], t[1], t[2], t[3], t[4], t[5])
    epoch2000 = jd( 2000, 1, 1, 12, 0, 0)

    vPos.Precess(epoch2000, epochNow)           # J2000 -> JNow
    tup = (vPos.RightAscension,vPos.Declination)

    del vPos
    del star

    Log2(5,"Precess: Starting J2000 coords:  %s  %s" % (UTIL.HoursToHMS(dJ2000RA,":",":","",1)  , DegreesToDMS(dJ2000Dec)))
    Log2(5,"         Result JNow coords:     %s  %s" % (UTIL.HoursToHMS(tup[0],":",":","",1)  , DegreesToDMS(tup[1])))

    return tup

#==============================================================================
def AzElev2RaDec(azimuth,elevation):
    #Calculate the RA/Dec (JNow) of a spot in the sky at the specified altitude/azimuth, at the current moment
    #Input: 2 strings containing azimuth, elevation in degrees
    #Output: tuple: (ra,dec) in decimal JNow

    observer = ephem.Observer()
    observer.lon = deg2rad(-87.)
    observer.lat = deg2rad(42.)
    observer.elevation = 0
    observer.epoch = ephem.now()
    observer.date = ephem.now()

    ra,dec = observer.radec_of(azimuth, elevation)

    #print "EPHEM:   %f %f" % (rad2hours(ra),rad2deg(dec))
    return (rad2hours(ra),rad2deg(dec))

#--------------------------------------------------------------------------------------------------------
def CalcSolarAlt(targetYear,targetMonth,targetDay,UT,LONG,LAT):
    #print targetYear,targetMonth,targetDay,UT,LONG,LAT
    #return number of degrees sun is above horizon (negative for below)
    #Formula found at:
    # http://www.saao.ac.za/public-info/sun-moon-stars/sun-index/how-to-calculate-altaz/
    DEGRAD = 0.0174532925                                     #PI/180

    Y = targetYear - 1900
    ZJ_array = (-0.5, 30.5, 58.5, 89.5, 119.5, 150.5, 180.5, 211.5, 242.5,272.5, 303.5, 333.5)
    if (Y%4)==0 and (targetMonth == 1 or targetMonth == 2):
        ZJ = ZJ_array[targetMonth - 1] - 1      #leap year correction
    else:
        ZJ = ZJ_array[targetMonth - 1]
    D = int(365.25 * Y) + ZJ + targetDay + UT/24.

    T = D/36525

    Lj = 279.697 + 36000.769 * T
    mul = int(Lj/360)
    L = Lj - (mul*360)


    Mj = 358.476 + 35999.050 * T
    mul = int(Mj/360)
    M = Mj - (mul*360)
    epsilon = 23.452 - (0.013 * T)

    lamb = L + ((1.919 - (0.005 * T)) * math.sin(M*DEGRAD)) + (0.020 * math.sin(2*M*DEGRAD))

    if lamb < 90:
        Q_lamb = 1
    elif lamb < 180:
        Q_lamb = 2
    elif lamb < 270:
        Q_lamb = 3
    else:
        Q_lamb = 4

    #From reference:
    #(9) find alpha the right ascension of the sun from this formula:
    #       alpha = arctan (tan(lambda) x cos(epsilon))      in same quadrant as lambda
    alpha = math.atan( math.tan(lamb*DEGRAD) * math.cos(epsilon*DEGRAD)) / DEGRAD
    if alpha < 0:
        alpha += 360

    if alpha < 90:
        Q_alpha = 1
    elif alpha < 180:
        Q_alpha = 2
    elif alpha < 270:
        Q_alpha = 3
    else:
        Q_alpha = 4

    #try to get alpha in same quadrant as lamb [lambda, but that is a reserved keyword in Python]
    if Q_lamb != Q_alpha:
        #print "Warn: lambda and alpha in DIFFERENT quadrants; try to fix."
        if Q_lamb == 3 and Q_alpha == 1:
            alpha += 180.
        elif Q_lamb == 2 and Q_alpha == 4:
            alpha -= 180.
        elif Q_lamb == 4 and Q_alpha == 2:      #added 12/28/2008
            alpha += 180.
        elif Q_lamb == 1 and Q_alpha == 3:
            alpha -= 180.
        elif Q_lamb == 4 and Q_alpha == 1:      #added 3/22/2013
            pass    #not sure what to do?? it seems to work correctly w/ no correction here.
        else:
            Error( ">>> alpha was not corrected in Solar altitude calc, Q_lamb=%d Q_alpha=%d  alpha=%f" % (Q_lamb,Q_alpha,alpha))

    delta = math.asin( math.sin(lamb*DEGRAD) * math.sin(epsilon*DEGRAD)) / DEGRAD
    HA = L - alpha + 180 + (15 * UT) + LONG - 360

    ALT = math.asin( math.sin( LAT*DEGRAD) * math.sin(delta*DEGRAD) + math.cos(LAT*DEGRAD) * math.cos(delta*DEGRAD) * math.cos(HA*DEGRAD)) / DEGRAD
    return ALT
#--------------------------------
def CheckSunAltitude(threshold):    #return True if sun above this threshold (degrees)
    # Note: typical threshold value would be -9 for start of twilight, -6 for too bright for darks
    #check sun altitude
    fthreshold = float(threshold)
    tup1 = time.gmtime()
    mYear  = tup1[0]
    mMonth = tup1[1]
    mDay   = tup1[2]
    utc    = float(tup1[3]) + (float(tup1[4])/60.) + (float(tup1[5])/3600.)
    alt = CalcSolarAlt(mYear,mMonth,mDay,utc,myLongitude,myLatitude)
    if alt > fthreshold:    #pick an altitude that it is too bright to be able to get guide stars, ever
        Log2(3,"Sun altitude %5.2f exceeds threshold %5.2f" % (alt,fthreshold))
        Log2Summary(0,"SUN ALTITUDE > %5.2f" % fthreshold)
        return True     #too late in morning (or too early in evening, and should not have started yet!)
    return False

#--------------------------------
# **THE FOLLOWING SECTION IS WRONG; THE RESIDUAL BULK CHARGE DOES NOT WORK THIS WAY**
# Sometimes a previous image included a bright star which has left an afterimage
# on the CCD. This can be cleared by reading chip several (10) times. Make sure
# shutter is closed so another field star doesn't burn in during this!
#Warn: this requires camera to have a shutter, so it does not work for Guider
# Set with bForce=True to always clear imager regardless of global setting; this is
# for use after a Focus step, because always have a bright star there.
def ClearImager(dic,vState,bForce=False):
    return
    if vState.flush == 0 and bForce == False:
         LogOnly("Skiping FlushCCD step")
         return

    if dic["camera"].lower() == "imager":
        Log2(2,"Flushing imager CCD to clear any burn-in")
        ##StatusWindow("substep","Flushing narrow imager...",vState)
        for i in range(vState.flush_cnt):
            vState.CAMERA.BinX = 1
            vState.CAMERA.BinY = 1
            vState.CAMERA.SetFullFrame()
            vState.CAMERA.Expose( 1, 0, 3 )   # 0 = dark frame so shutter CLOSED; 3=L filter (doesn't do anything here)

            #wait for exposure to complete
            while not vState.CAMERA.ImageReady:
                time.sleep(0.25)
        ##StatusWindow("substep","Flushing complete",vState)
    else:
        #for now, do not do anything w/ current guide camera
        Log2(4,"Skipping flush of GUIDER CCD (no shutter, and takes long to download)")
        return

    Log2(4,"ClearImager step completed")

#=====================================================================================
#==== SECTION  @@Pinpoint ============================================================
#=====================================================================================

def PinpointEntry(desiredPos, targetID, vState, bImagerSolve):
    #This is called for a "pinpoint event", and handles calling for both cameras.
    # bImagerSolve = True means that we expose/solve w/ main imager; we always
    #   expose/image w/ Guider first regardless of this setting.
    #
    #This reads the mount's current location and takes images with one or both
    # cameras to find out where the mount really is. The mount is 'synced' for any
    # solution, and optionally repositioned (moved) to actually point in the sky
    # to where it thought it was, based on a precision criteria. If there is no
    # solution to images at this location, optionally the mount moves to a nearby
    # location and tries there. If it is moved, it will always be returned to its
    # original coordinates at the end.
    #
    #The parameters that control actions here are in the vState.ppState class object.
    #
    #Either or both cameras will take images and try to have them pinpoint solved,
    # the idea being that the control script will specify what it wants; it is fine
    # to want to use both cameras here, the guider to make sure in the correct area,
    # and then the imager to fine-tune (and possibly not solve, but maybe it will).
    #
    # Return True if problem, False if no problem (solved, or n/a)

    #dRA = RA_JNow_decimal     #UTIL.HMSToHours( desiredRA_string )
    #dDec = Dec_JNow_decimal   #UTIL.DMSToDegrees( desiredDec_string )

    Log2(0,"Pinpoint(Wide)")
    if PinPointSingle(1, desiredPos, targetID, vState):   #guider first (wider field)
        # guider failed to solve; is it required to?
        if  vState.ppState[1].require_solve == 1:
            #yes, it is required, so report this as error
            Log2(3,"(step may NOT proceed without WIDE solution)")
            return True
        #guider not required to solve, so act like it worked (even though it did not
        Log2(1,"Wide image did NOT solve, but continue with step anyway.")
        return False

    if bImagerSolve:
       #only do Imager PP solve step for certain events (this is skipped for Focus, or for Guider image)
       Log2(0,"Pinpoint(narrow)")
       if PinPointSingle(0, desiredPos, targetID, vState):   #imager second (narrower field)
            # imager failed to solve; is it required to?
            if  vState.ppState[0].require_solve == 1:
                #yes, it is required, so report this as error
                Log2(3,"(step may NOT proceed without Narrow solution)")
                return True
            #imager not required to solve, so act like it worked (even though it did not
            Log2(1,"Narrow image did NOT solve, but continue with step anyway.")

            #!! THIS IS WHERE I CAN USE PREVIOUSLY MEASURED FOV OFFSET AND TRY TO CORRECT LOCATION MYSELF
            FOVoffsetAdjust(vState)
            return False
    else:
       FOVoffsetAdjust(vState)

    return False
#--------------------------------
def FOVoffsetAdjust(vState):
   #we solved wide field but did not PP solve narrow (either failed or didn't try);
   # adjust the position based on a previously measured and configured offset
   # between the center of the FOV's of the two cameras, to try to get target
   # centered in narrow FOV
   return   #need to debug

#--------------------------------------------------------------------------------------------------------
def TakeNarrowImage(exposure,vState):   #used by Pinpoint solve routine
    vState.CAMERA.BinX = 1  #make sure there is no rounding when setting Full Frame
    vState.CAMERA.BinY = 1
    vState.CAMERA.SetFullFrame()
    vState.CAMERA.BinX = vState.ppState[0].binning
    vState.CAMERA.BinY = vState.ppState[0].binning
    Log2(2,"Exposure starting...")

    #2015.07.03 JU: change how Narrow PP image taken: if the filter currently selected
    # in the camera is the V filter (position 4), then take image using that filter,
    # otherwise use L filter (position 3) for any other filters since they are all parfocal and V isn't.
    if vState.CAMERA.Filter == 4:
        Log2(6,"PP--Narrow image exposing with filter 4 (V)")
        vState.CAMERA.Expose( exposure, 1, 4 )
    else:
        Log2(6,"PP--Narrow image exposing with filter 3 (Lum)")
        vState.CAMERA.Expose( exposure, 1, 3 )

    LogStatusHeaderBrief()
    while not vState.CAMERA.ImageReady:
        time.sleep(2)
        LogStatus(vState,7)

    #Log2(4,"PP---END narrow field exposure")
    doc = vState.CAMERA.Document     #point to image just taken
    return doc

#--------------------------------------------------------------------------------------------------------
def TakeWideExposure(exposure,vState):  #used by Pinpoint solve routine
  try:
    Log2(2,"Exposure (wide) starting...")
    vState.CAMERA.GuiderExpose( exposure )
    LogStatusHeaderBrief()
    while vState.CAMERA.GuiderRunning:
        time.sleep(2)    #waiting until the guide exposure is done
        LogStatus(vState,6)
    #Log2(4,"PP---END wide field exposure")
    doc = GetGuiderDoc(vState)
    return doc
  except:
        SafetyPark(vState)
        raise SoundAlarmError,'Halting program'


#--------------------------------------------------------------------------------------------------------
def PinPointSingle(camera,originalDesiredPos, targetID, vState):
    # camera = 0 for imager(narrow field), =1 for guider(wide field)
    #this is called for one particular camera
    #Note: desiredPos = Position object where we want to go
    #      currentPos = where mount thinks we are
    #      solvedPos  = result of most recent solution (exclude wide-repeat?)
    # Return: False = solved; True = problem, did not solve
    #NEW Return: 0=solved, 1=problem, 2=problem, probably looking at trees, skip this target?
    bProblem = True

    if runMode == 3:
        return True #nothing useful to do here

    #Log entry in PinpointLog.txt
    # 22:04:35 [target?][RA,Dec?] Fail:10 Fail:20 Succeed:40
    # 22:05:35 [target?][RA,Dec?] Success:10(d:8.11) Success:10(d:0.22)
    # 22:06:35 [target?][RA,Dec?] Fail:10 Fail:20 Fail:40 Repro:3/15.00 Fail:10 Success:20

    desiredPos = originalDesiredPos #may change this below

    PinpointLogLine = ""
    if camera == 0:
       sCamera = "[Imager]"
       cameraString = "imager"
    else:
       sCamera = "[GUIDER]"
       cameraString = "Guide"


    #print "PinPointSingle called for camera=",camera
    if not vState.ppState[camera].active:
        Log2(1,"PP-camera %s is DISABLED for PP solve" % (strCamera(camera)))
        return False      #this camera is NOT configured to use Pinpoint; do nothing

    tStart = time.time() #actual time when this function started

    retry = True

    # currentPos is where we think we are, as far as the mount is reporting
    currentPos = Position()
    currentPos.setJNowDecimal(vState.MOUNT.RightAscension,vState.MOUNT.Declination,targetID,cTypeReported)
    Log2(6,"PinPointSingle - currentPos:" + currentPos.dump())

    exposure = vState.ppState[camera].exposure      #initial exposure to use

    state = 0       #0=undetermined, 1=succeeded before, 2=failed before
    retries = 0     #count of how many times we've looped (applies to either all success, or all failure)
    #moves   = 0     #count how many times the mount is repositioned trying to find a better field to solve

    #Looping over retry can be for one of three reasons:
    # 1. The PP solve failed
    # 2. The solve had a plate scale too different from expected
    # 3. The distance from the solution to the desired coordinates is greater
    #    than the specified threshold; is we have a 'long' way to move to correct
    #    the position, we are not likely to be as accurate, so try again.
    while retry:
        retry = False       #do not run again unless explicitly allowed

        #********************
        # ** Expose Image  **
        #********************
        Log2(1,"Exposure (%s) start: %3.2f seconds, bin: %d" % (cameraString, exposure, vState.ppState[camera].binning))
        if camera == 0:
            #Log("PP---START NARROW FIELD exposure: %3.2f seconds, binning: %d" %(exposure, vState.ppState[camera].binning))
            # if exposure > 30 seconds, use guider during this
            if exposure > 45:
                ##StatusWindow("substep","Start Narrow PP guide",vState)
                if StartGuidingConfirmed("long PP exp - " + targetID, vState, 5):   #2013.08.08 JU: retry cnt had been one; increase for multiple attempts
                    Error("**Failed to start guiding even after several attempts")
                    ##SafetyPark(vState)
                    ##raise SoundAlarmError,'Unable to start guiding'
                    raise WeatherError

                #guiding will be stopped AFTER the Pinpoint Solve step
            ##StatusWindow("substep","Narrow PP expose",vState)
            doc = TakeNarrowImage(exposure,vState)

                                #---------------------------------------------------
            #doc.Calibrate()     #this *MAY* improve ability to PP solve narrow image
                                #---------------------------------------------------

            ##StatusWindow("substep","Narrow PP solve...",vState)
            expectedScale = vState.ImagerScale * vState.ppState[camera].binning #scale for binning
        else:
            #Log("PP---START WIDE FIELD exposure: %3.2f seconds, binning: %d" %(exposure, vState.ppState[camera].binning))
            #StatusWindow("substep","Wide PP expose",vState)
            doc = TakeWideExposure(exposure,vState)
            #StatusWindow("substep","Wide PP solve...",vState)
            expectedScale = guiderScale     #note: guider images cannot bin, so no scaling

        if camera == 1:
            #2010.04.05: PP guider images do not save w/ FITS header RA/Dec info, so add (nice to have)
            pos2 = Position()
            pos2.setJNowDecimal(vState.MOUNT.RightAscension, vState.MOUNT.Declination)
            sRA,sDec = pos2.getJ2000String()
            sRA = sRA.replace(':',' ')
            sDec = sDec.replace(':',' ')
            doc.SetFITSKey('EQUINOX',2000.0)
            doc.SetFITSKey('OBJCTRA',sRA)
            doc.SetFITSKey('OBJCTDEC',sDec)

        filename = PinpointFilename(targetID,camera,vState)
        doc.SaveFile( filename, 3, False, 1, 0)   # 3=fits format; False=do not autostretch; 1=16-bit data; 0=no compression

        Log2(2,"Exposure complete: " + NameWithoutPath(filename))
        if camera == 0:
           StatusLog(filename)   #don't bother logging when exposing w/ Guider because no guide statistics then

        #********************
        # ** Solve Image **
        #********************
        tSolveStart = time.time()

        tup = AdvancedPlateSolve(camera, desiredPos, targetID, filename, 0, vState)

        success = tup[0]
        deltaSolve = tup[3]  #arcmin difference between desired and solved position (value is 0 if not success)
        tSolveEnd =  time.time()

        #want guiding to continue during the solve step in case it runs long, so that the
        #  mount will not move far off the target (I hope).  If we reposition the mount,
        #  the GOTO command will stop the guider, so do not need to do it here.

        #SYNC mount if success
        if success:
            ##StatusWindow("substep","PP solved",vState)

            #********************
            # ** SYNC MOUNT: **
            #********************

            bProblem = False
            vState.pinpoint_success += 1
            solvedPos = Position()
            solvedPos.setJ2000Decimal(tup[1],tup[2],targetID,cTypeSolved)
            Log2(6,"PinPointSingle - solvedPos:" + solvedPos.dump())

            Log2(4,"Actual J2000 solved values: %s  %s" % (UTIL.HoursToHMS(tup[1],":",":","",1), DegreesToDMS(tup[2])))

            #how close are we really to where we think we are?
            # RESYNC            RA--JNow--Dec       RA--J2000--Dec    WIDE/narrow
            #        From     00:00:00 +00:00:00  00:00:00 +00:00:00
            #        To       00:00:00 +00:00:00  00:00:00 +00:00:00  Solved: 999 sec
            #        Diff     00:00:00 +00:00:00  00:00:00 +00:00:00
            # -----------------------------------------------------------------------------
            beforeSyncPos = Position()
            beforeSyncPos.setJNowDecimal(vState.MOUNT.RightAscension,vState.MOUNT.Declination)
            sRA_fromJ, sDec_fromJ = beforeSyncPos.getJNowString()
            sRA_from2, sDec_from2 = beforeSyncPos.getJ2000String()

            sRA_toJ, sDec_toJ = solvedPos.getJNowString()
            sRA_to2, sDec_to2 = solvedPos.getJ2000String()

            dRA_diffJ  = beforeSyncPos.dRA_JNow() - solvedPos.dRA_JNow()
            dDec_diffJ = beforeSyncPos.dDec_JNow() - solvedPos.dDec_JNow()

            dRA_diff2  = beforeSyncPos.dRA_J2000() - solvedPos.dRA_J2000()
            dDec_diff2 = beforeSyncPos.dDec_J2000() - solvedPos.dDec_J2000()

            sRA_diffJ = UTIL.HoursToHMS(dRA_diffJ,":",":","",1)
            sDec_diffJ = DegreesToDMS(dDec_diffJ)
            sRA_diff2 = UTIL.HoursToHMS(dRA_diff2,":",":","",1)
            sDec_diff2 = DegreesToDMS(dDec_diff2)

            line0 = "RESYNC            RA--JNow--Dec       RA--J2000--Dec    %s" % (sCamera)
            line1 = "       From     %s %s  %s %s " % (sRA_fromJ, sDec_fromJ, sRA_from2, sDec_from2)
            line2 = "       To       %s %s  %s %s  Solved: %5.2f  sec" % (sRA_toJ, sDec_toJ, sRA_to2, sDec_to2, tSolveEnd - tSolveStart)
            line4 = "       Diff    %9s  %8s %9s  %8s" % (sRA_diffJ,sDec_diffJ,sRA_diff2,sDec_diff2)
            Log2(4,line0)
            Log2(4,line1)
            Log2(4,line2)
            Log2(4,line4)

            LogBase(line0,MOVEMENT_LOG)
            LogBase(line1,MOVEMENT_LOG)
            LogBase(line2,MOVEMENT_LOG)
            LogBase(line4,MOVEMENT_LOG)
            LogBase("-----------------------------------------------------------------------------",MOVEMENT_LOG)

            #do the actual Sync command after logging the 'before' coords'
            #2017.02.22 JU: protect against mount being given impossible coordinates (this can happen from bad PP or Astrometry.net solve)
            try:
                vState.MOUNT.SyncToCoordinates(solvedPos.dRA_JNow(),solvedPos.dDec_JNow())
            except:
                niceLogExceptionInfo()
                Error("Exception thrown for SyncToCoordinates: mount given impossible coords to sync to!")
                SafetyPark(vState)
                raise SoundAlarmError,'Halting program'

        else:
            Log2(3,"Did not solve")
            DiffRA = 0      #just in case, but these variables should not be referenced if not solved
            DiffDec = 0
            #if the 1st attempt fails AND it appears we are below local horizon, then do NOT image this target
            # (we test horizon AFTER failing in case the horizon setting is wrong and the object really is visible)
            if not isVisible(vState.MOUNT.Azimuth,vState.MOUNT.Altitude):
                #stop trying; we are probably below the local horizon (return status??)
                Log2(0,"PP-target is probably below local horizon, stop trying")
                raise HorizonError


        #decide if we are done or need to retry
        retries += 1
        #print "success?",success,"  state?",state,"  retries?",retries
        if success:
            #Log2(3,"PP-succeeded")

            #only reposition if difference greater than some setting...
            #delta_RA = 5. * 1./3600.  #5 seconds of time
            #delta_Dec = 10 * 1./3600. #10 arcseconds
            #if abs(DiffRA) < delta_RA and abs(DiffDec) < delta_Dec:
            #    Log2(2,"Slewing not needed here (close enough already)")
            #    break

            #********************
            # ** Move mount to refine pointing based on solution/sync above **
            #********************
            ##StatusWindow("substep","PP slew correction",vState)
            GOTO(desiredPos,vState,"PP-correction adjustment [%s]" % (strCamera(camera)))   #adjust location

            #examine precision of previous goto (returned w/ CustomPinpointSolve results), to see if we should try again
            #If the precision was really 'bad', the GOTO we just did probably did
            #not get exactly where we want, so decide if we want to do it again.

            Log2(2,"%s solution result:" % (cameraString))
            #Note: deltaSolve returned from CustomPinpointSolve call above
            PinpointLogLine += " %d:Success(delta:%5.2f)" % (exposure,deltaSolve)
            if deltaSolve > vState.ppState[camera].precision and vState.ppState[camera].precision != 0:
                Log2(3,"This distance (%5.2f) is greater than threshold %5.2f arcmin" % (deltaSolve,vState.ppState[camera].precision))
                #try to do better by REPEATING another image/solve/sync/reposition cycle?
                if retries <= vState.ppState[camera].retry:
                    #this means sync to solution and GOTO desired coords again to get closer
                    # (this is NOT moving to a different field to try solving)
                    Log2(3,"Success; repeat to improve precision")
                    Log2(0,"RETRYING (%s) after success" % (strCamera(camera)))
                    retry = True
                else:
                    Log2(3,"(Diff exceeds threshold, but no retries left)")
            else:
                #this is good enough (don't need to do correction goto??)
                if vState.ppState[camera].precision == 0:
                    Log2(3,"(PP-precision not used for this step)")
                else:
                    Log2(3,"PP-precision is good enough: %5.2f arcmin" % (deltaSolve))
                break

        else:   #failure to solve or solved with bad scale
            #Log2(3,"PP-failed to solve")
            #check to see what next step should be (retry?)
            Log2(2,"%s solution result:" % (cameraString))
            Log2(3,"(failed to solve or bad scale)")
            if retries <= vState.ppState[camera].retry:
                #try again, different exposure
                retry = True
                if retries <= 2:
                    #I do NOT want to increase this too much; this limits it to at most doubling the exposure twice
                    exposure *= vState.ppState[camera].exp_increment
                    Log2(3,"(PP failed; trying again with different exposure: %5.2f)" % exposure)
                else:
                    Log2(3,"(PP failed; trying again but using SAME exposure: %5.2f)" % exposure)
                Log2(0,"RETRYING (%s) because failed to PP solve last time" % (strCamera(camera)))
            else:
                #no more exposure attempts
                Log2(3,"(No retries left)")

    tEnd   = time.time()
    timeDiff = tEnd - tStart    #overall time spend in PinPointSingle for this camera
    PinpointLogLine1 = "%-12s %s %s [%s] [%3d] " % (targetID, UTIL.HoursToHMS(desiredPos.dRA_J2000(),":",":","",1), DegreesToDMS(desiredPos.dDec_J2000()), strCamera(camera), timeDiff)

    LogBase(PinpointLogLine1 + PinpointLogLine, PINPOINT_LOG)   #log the sequence of success/failure for this attempt
    return bProblem

#--------------------------------------------------------------------------------------------------------
def PinpointFilename(targetID, camera,vState):     #removed Solved argument
    #Example syntax:
    #   PP_imager_0818_M27_solved_00007.fts
    #   PP_guider_1224_NGC7331_notsolved_00102.fts

    if camera == 1:
        root = "PP_guider_"
    else:
        root = "PP_IMAGER_"

    monthday = ""
    temp = ObservingDateString()
    monthday = temp[4:] + "_"
    #print "monthday = %s" % monthday
    #monthday = time.strftime("%m%d_", time.gmtime( time.time() ) )
    root = root + monthday

    root = root.strip() + targetID.strip() + '_'

    seq = GetSequenceNumber(pathPinpoint, root) + 1  #the +1 is to use next AVAILABLE number
    fullname = ('%s%s%05d.fts') % (pathPinpoint,root,seq)
    #
    # WARNING: the sequence number function ASSUMES the file suffix is .fts, so don't change this!!!
    #


    return fullname

#--------------------------------------------------------------------------------------------------------
def BrightStarCoordinateFilename(brightStarID,vState):
    #Example syntax:
    #   BrightStar_0818_SAO 99999_00007.fts

    root = "BrightStar_"

    monthday = ""
    temp = ObservingDateString()
    monthday = temp[4:] + "_"
    #print "monthday = %s" % monthday
    #monthday = time.strftime("%m%d_", time.gmtime( time.time() ) )
    root = root + monthday

    root = root.strip() + brightStarID.strip() + '_'

    #
    #Note use of path for Pinpont here; I don't need a separate directory for these star images
    #
    seq = GetSequenceNumber(pathPinpoint, root) + 1  #the +1 is to use next AVAILABLE number
    fullname = ('%s%s%05d.fts') % (pathPinpoint,root,seq)
    #
    # WARNING: the sequence number function ASSUMES the file suffix is .fts, so don't change this!!!
    #

    return fullname

#--------------------------------------------------------------------------------------------------------
def AdvancedPlateSolve( camera, expectedPos, targetID, filename, trace, vState ):
    #This calls the Pinpoint engine software for the specified file.
    # This is called by PinPointSingle()
    # This decides whether PinPoint or Astrometry.net is being used
    # See CustomPinpointSolve() for defn of arguments and return

    #2017.09.12 JU: change logic so always tries PP first (fast), and
    #   then only tries AN if PP fails AND image has "lots" of stars.
    #   Only want/need to use AN if scope position is far from expected
    #   location, causing PP to fail. If "few" stars and PP can't solve
    #   then the sky is probably cloudy; don't bother w/ AN attempt; instead
    #   take another image and try PP again to see if cleared up.
    #   Note: PP solve attempts give count of # image stars to use to decide
    #   if worth trying AN if PP fails.
    #
    #New logic:
    #   Take WIDE image
    #   try PP solve; if works, DONE.
    #   if star count < 100, take another WIDE image (probably cloudy) (until retry exceeded)
    #   else try AN solve; if works, DONE
    #   take another WIDE image (until retry exceeded)

    #2017.08.22 JU: enclose this in exception block because one time something went wrong in CustomPinpointSolve and it
    #   tried to log something that didn't format correctly as a string, throwing an unhandled exception (no safety park!)
    try:
        #vState.AstrometryNet #0=disable(use PP), 1=use after 2 failures of PP solve, 2=use all the time(disable all PP solves)
        #Note: Narrow camera always uses PP
        if vState.AstrometryNet == 0 or camera == 0:
            return CustomPinpointSolve( camera, expectedPos, targetID, filename, trace, vState )
        if vState.AstrometryNet == 2:
            return CustomAstrometryNetSolve( camera, expectedPos, targetID, filename, trace, vState )
        #else == 1 so use PP first
        if vState.pinpoint_successive_wide_failures < 2:    #(maybe make adjustable)
            Log2(2,"Using PinPoint for plate solve")
            return CustomPinpointSolve( camera, expectedPos, targetID, filename, trace, vState )
        else:
            Log2(2,"Using Astrometry.net for plate solve")
            return CustomAstrometryNetSolve( camera, expectedPos, targetID, filename, trace, vState )

    except:
        #catch all unhandled exceptions, treat as solve failure
        niceLogExceptionInfo()
        Error("Caught unhandled exception in AdvancedPlateSolve; treat as failed solve")
        return (False, 0., 0., 0.)


#--------------------------------------------------------------------------------------------------------
def CountImageStars( camera, expectedPos, targetID, filename, trace, vState ):
    #Use PinPoint to count number of stars in image before trying Astrometry.net; if there are no
    #or few stars in the image, probably bad weather, and don't want to try to solve it.

    #return number of field stars found; return 0 if problem performing the count

    pp = win32com.client.Dispatch("PinPoint.Plate")

    try:
       pp.AttachFITS(filename)
    except:
       #this means the file could not be opened
       Error("   Pinpoint routine could not open file: " + filename)
       Error("   The image is probably very bad")
       Log2Summary(1,"PP " + sCamera + " failed; could not open file, probably very bad (called as part of Astrometry.net)")
       try:
         del pp
       except:
         pass
       return 0

    #if the supplied RA/Dec arguments are both 0, then assume the image already has FITS header settings for these
    if not expectedPos.isValid:
       #assume the fits header already has the expected coordinates
       pp.RightAscension = UTIL.HMSToHours(pp.ReadFITSValue("OBJCTRA"))
       pp.Declination    = UTIL.DMSToDegrees(pp.ReadFITSValue("OBJCTDEC"))
    else:
       pp.RightAscension,pp.Declination  = expectedPos.getJ2000Decimal() # PrecessLocalToJ2000(expectedRA,expectedDec)


    #Sometimes (rarely? randomly?) PP uses these other variables when solving!
    pp.TargetRightAscension = pp.RightAscension
    pp.TargetDeclination = pp.Declination

    Log2(4,"RA = %s" % UTIL.HoursToHMS(pp.RightAscension,":",":","",1))
    Log2(4,"Dec = %s" % DegreesToDMS(pp.Declination))
    pp.TracePath = r"C:\temp"
    pp.TraceLevel = 1

    if camera == 0:
        #Imager, narrow field and deep (we hope)
        pp.ArcsecPerPixelHoriz     = vState.ImagerScale * vState.ppState[camera].binning #scale for binning
        pp.ArcsecPerPixelVert      = vState.ImagerScale * vState.ppState[camera].binning #scale for binning
        pp.Catalog                 = vState.ppState[camera].CatalogID # 5  #3=GSC, 5=USNO_A2.0(6GB), 8=USNO_B2.0 via Internet
        #pp.CatalogPath = r"C:\Catalog"
        pp.CatalogMaximumMagnitude = vState.ppState[camera].CatMaxMag # 18         #default=20 (data limit probably 19)
        pp.MaxSolveTime            = vState.ppState[camera].MaxSolveTime # 90   #usually solves in less than 10 seconds; I've seen it go at least 45 seconds and still solve
        pp.SigmaAboveMean          = vState.ppState[camera].SigmaAboveMean # 2.0 #default 3.0; may want to use 2.5 or 2.0 for PP narrow??
        #using PP 2.0 may need image to be calibrated first to avoid false positives!

        #maybe make this value configurable?
        pp.CatalogExpansion = 0.3  #default 0.3; legal values 0.0 - 0.8

        expectedScale = vState.ImagerScale  * vState.ppState[camera].binning #scale for binning
    else:
        #Guider, wide field, not deep
        pp.ArcsecPerPixelHoriz     = vState.GuiderScale
        pp.ArcsecPerPixelVert      = vState.GuiderScale
        pp.Catalog                 = vState.ppState[camera].CatalogID  # 3  #3=GSC, 5=USNO_A2.0(6GB), 8=USNO_B2.0 via Internet
        #pp.CatalogPath = r"C:\gsc11"
        pp.CatalogMaximumMagnitude = vState.ppState[camera].CatMaxMag # 16
        pp.MaxSolveTime            = vState.ppState[camera].MaxSolveTime # 60   #this should solve quick; if it doesn't, something is wrong
        pp.SigmaAboveMean          = vState.ppState[camera].SigmaAboveMean # 2.0 #default 3.0; may want to use 2.5 or 2.0 for PP narrow??

        #maybe make this value configurable?
        pp.CatalogExpansion = 0.3  #default 0.3; legal values 0.0 - 0.8

        expectedScale = vState.GuiderScale  #(no binning supported here)


    #Not sure if I even need catalog settings here
    pp.CatalogPath = r"C:\Catalog"

    #maybe (or maybe not):
    pp.ConvolveGaussian(1)      #arg is FWHM(arcsec) of Gaussian fn to use.
    pp.ImageModified = False    #to prevent modified image from being written out

    pp.FindImageStars()

    numImageStars = len(pp.ImageStars)
    #Log2(2,"Number of image stars: %d" % numImageStars)             #HERE IS NUMBER OF IMAGE STARS IDENTIFIED IN THIS IMAGE-----------------======================
    del pp

    return numImageStars

#--------------------------------------------------------------------------------------------------------
AstrometryResult = (False, 0., 0.,0.,"n/a",-1)   #global variable to return result if thread completes
AstrometryMaxSolveTime = 30
def CustomAstrometryNetSolve( camera, expectedPos, targetID, filename, trace, vState ):
    global AstrometryMaxSolveTime
    AstrometryMaxSolveTime = vState.ppState[camera].MaxSolveTime

    #2017.07.03: before calling Astrometry.net, first use PinPoint to COUNT the number of stars
    # present in the image. If the number is too low, don't bother trying Astrometry.net (probably bad weather)
    numImageStars = CountImageStars( camera, expectedPos, targetID, filename, trace, vState )

    Log2(2,"Number of image stars: %d" % numImageStars)             #HERE IS NUMBER OF IMAGE STARS IDENTIFIED IN THIS IMAGE-----------------======================
    if numImageStars < 10:  #ADJUST THIS
        Log2Summary(1,"AN C=" + str(camera) + " less than 10 stars in image; skip calling Astrometry.net")
        Log2(2, "vvvvvvvvvv")
        Log2(2, "> failed <             (less than 10 stars in image; skip calling Astrometry.net)" )
        Log2(2, "^^^^^^^^^^")
        return (False, 0., 0.,0.)
    #end of Pinpoint addition feature

    try:
        Log2(2,"Defining thread: CustomAstrometryNetSolve_THREAD")
        t = threading.Thread(target=CustomAstrometryNetSolve_THREAD, args=(camera, expectedPos, targetID, filename))
        Log2(2,"Starting thread")
        t.start()
        Log2(2,"Thread has been started; about to call join on thread")

        t.join(600)  #if it takes more than 10 minutes, stop and disable this feature so normal logic can run instead
        Log2(2,"Checking thread result:")
        if t.is_alive():
            Log2(0,"THREAD IS NOT DONE; ***DISABLE Astrometry.net FEATURE BECAUSE IT APPEARS TO BE HUNG***")
            vState.AstrometryNet = 0
            Log2Summary(0,"DISABLE Astrometry.net FEATURE BECAUSE IT APPEARS TO BE HUNG")
            #NOTE: we abandon the thread; we don't try to do a final join() because the thread appears to be hung
            return (False, 0., 0.,0.)
        else:
            Log2(2,"Thread completed normally")
        t.join()    #final join() to make sure fully done
        Log2(2,"Final thread join returned as expected")

        Log2(0,"Msg: " + AstrometryResult[4])
        Log2(0,"Status: %d" % AstrometryResult[5])
        vState.ppState[camera].MaxSolveTime = AstrometryMaxSolveTime
        if AstrometryResult[0] and camera == 1:
            vState.pinpoint_successive_wide_failures = 0    #reset count whenever we have a Wide success

        return (AstrometryResult[0],AstrometryResult[1],AstrometryResult[2],AstrometryResult[3])
    except:
        Error("UNHANDLED EXCEPTION WHEN TRYING TO RUN THREAD for Astrometry.net")
        niceLogExceptionInfo()
        return (False, 0., 0.,0.)

#..................................................................................
def CustomAstrometryNetSolve_THREAD(camera, expectedPos, targetID, filename ):
    #WARNING: sometimes Astrometry.net can HANG indefinitely, so call it in a thread that we can abandon if it takes too long.
    #Otherwise, the entire program is held here, including not parking the scope at all.

    #see documentation of argument list and return values in CustomPinpointSolve()
    global AstrometryResult
    global AstrometryMaxSolveTime

    start = time.time()
    if camera == 0:
        sCamera = "Narrow"	#used with Log2Summary
    else:
        sCamera = "*Wide*"	#used with Log2Summary

    try:
        #There is a chance that this might throw an exception sometimes, such as if
        #there is a problem with the internet or the remote web site
        Log2(2,"About to create Astrometry.net Client")
        client = Client()

        Log2(5,"About to log in; this is the ID string assigned to me")
        client.login('byntncnnbevtsyis')

        Log2(5,"About to upload file: %s" % filename)
        client.upload(filename)
        timeout = AstrometryMaxSolveTime    #vState.ppState[camera].MaxSolveTime
        Log2(5,"After uploading file, waiting up to %d seconds for completion" % timeout)
        client.wait_for_completion(timeout)	    #wait, timeout if too long

    except:
        Log2Summary(1,"AN " + sCamera + " EXCEPTION calling Astrometry.net")
        Log2(2, "vvvvvvvvvv")
        Log2(2, "> failed <             (EXCEPTION calling Astrometry.net)" )
        Log2(2, "^^^^^^^^^^")
        Log2(2, "Suggestion: try opening web site nova.astrometry.net to see if it is currently working." )
        Log2(2, "If web site NOT working, change cmd file to:  Set_Astrometry.net=0   to disable for now")
        #NOTE: I am not deleting the Client object here, just in case it caused this exception
        AstrometryResult = (False, 0., 0.,0.,"1008: Exception calling Astrometry.net",1008)
        return

    status = client.solved_valid
    end = time.time()
    Log2(5, "Astrometry.net took: " + str(round(end-start,2)) + " seconds.")
    if not status:
        status = client.status_code
        #   1001 = timeout(1)
        #   1002 = timeout(2)
        #   1003 = the wait function called before anything was uploaded
        #   1004 = Astrometry.net returned result of 'faiure', it could not solve the image (this can happen if image is blank)
        #   1005 = Astrometry.net returned unreasonable declination value (too far south, < -30 degrees)
        #the next error values are tested for later (or above)
        #   1006 = Astrometry.net returned coord unreasonably far from expected location
        #   1007 = ERROR: EXCEPTION CONVERTING client.solved_RA,Dec to floats after calling Astrometry.net
        #   1008 = Exception calling Astrometry.net

        msg = "N/A"
        if status == 1001:
            msg = "1001: Timeout(1) occurred"
            AstrometryMaxSolveTime += 30
            #vState.ppState[camera].MaxSolveTime += 30   #bump this by 30 seconds each time we timeout, in case Astrometry.net is having a slow night
        if status == 1002:
            msg = "1002: Timeout(2) occurred"
            AstrometryMaxSolveTime += 30
            #vState.ppState[camera].MaxSolveTime += 30   #bump this by 30 seconds each time we timeout, in case Astrometry.net is having a slow night
        if status == 1003:
            msg = "1003: Wait function called before upload"
        if status == 1004:
            msg = "1004: Astrometry.net unable to solve image (maybe blank?)"
        if status == 1005:
            msg = "1005: Astrometry.net returned unreasonable result, too far south (too few stars?)"
        #add more here in the future
        Log2(5,"Astronmetry.net Result: FAILED, status = %s" % msg)
        Log2(2, "vvvvvvvvvv")
        Log2(2, "> failed <             (using Astrometry.net)" )
        Log2(2, "^^^^^^^^^^")
        Log2Summary(1,"AN " + sCamera + " failed; status = %s" % msg)

        del client
        AstrometryResult = (False, 0., 0.,0.,"Failed, status: " + msg,status)
        return
#0. do not pass vState to thread; it has lots of COM objects embedded init
#1. return tuple: status
#2. call star count outside of thread first
#3. pass MaxSolveTime outside of vState
#4. pass pinpoint_successive_wide_failures out of vState
#5. consider whether using Log2, Log2Summary calls here could be a problem

    #It appears to have worked
    Log2(2,"Astrometry.net results returned; successful")
    try:
        solvedRA = float(client.solved_RA) / 15      #convert degrees into hours: 360/24 = 15
        solvedDec = float(client.solved_Dec)
    except:
        Log2(5,"ERROR: EXCEPTION CONVERTING client.solved_RA,Dec to floats")
        msg = "1007: ERROR: EXCEPTION CONVERTING client.solved_RA,Dec to floats after calling Astrometry.net"
        del client
        AstrometryResult = (False, 0., 0.,0.,msg,1007)
        return

    diffRA = solvedRA - expectedPos.dRA_J2000()
    diffDec = solvedDec - expectedPos.dDec_J2000()
    DiffRAdeg = diffRA * 15 * cosd(expectedPos.dDec_J2000())   #convert RA diff into degrees, adjusted for declination
    delta = math.sqrt((DiffRAdeg * DiffRAdeg) + (diffDec * diffDec)) * 60   #arcmin

    if delta > 90.:
        #There is no way this is a valid result ( >90 arcminutes); it is too far away
        msg = "1006: Astrometry.net returned unreasonable result, TOO FAR AWAY FROM EXPECTED LOCATION (too few stars?)"
        Log2(0,"Astronmetry.net Result: FAILED, status = %s" % msg)
        Log2(2, "vvvvvvvvvv")
        Log2(2, "> failed <             (using Astrometry.net)" )
        Log2(2, "^^^^^^^^^^")
        Log2Summary(1,"AN " + sCamera + " failed; status = %s" % msg)

        del client
        AstrometryResult = (False, 0., 0.,0.,msg,1006)
        return

    #delta <= 90:
    #if camera == 1:
    #    vState.pinpoint_successive_wide_failures = 0    #reset count whenever we have a Wide success
    if camera == 0:
        Log2(1,"***narrow****")
    else:
        Log2(1,"****WIDE*****")
    Log2(1,"** SOLVED! **     (%5.2f sec)  Astrometry.net" % (end-start))
    Log2(1,"*************")
    Log2(2,"Soln J2000  RA=%s Dec=%s" % (UTIL.HoursToHMS(solvedRA,":",":","",1),DegreesToDMS(solvedDec)))

    Log2(2,"Difference    %9s      %8s  = %6.2f arcmin" % (UTIL.HoursToHMS(diffRA,":",":","",1),DegreesToDMS(diffDec),delta))


    Log2Summary(1,"AN " + sCamera + " SUCCESS, Diff: %6.2f arcmin" % delta)

    #NOTE: I AM NOT WRITING THE SOLVED VALUES INTO THE IMAGES HERE

    del client

    AstrometryResult = (True, solvedRA, solvedDec, delta,"Success",0)     #success
    return

#--------------------------------------------------------------------------------------------------------
def CustomPinpointSolve( camera, expectedPos, targetID, filename, trace, vState ):
    #This calls the Pinpoint engine software for the specified file.
    # This is called by PinPointSingle()

    # returns tuple: (success, solvedRA2000, solvedDec2000, delta)
    #     delta = difference in arcmin between expected and solved positions;
    #              only available if solved and scale OK
    #     Important: if success is False, the RA/Dec coords are not valid!)
    # camera: 1=guider, 0=imager
    # filename: the entire path/filename of the saved image
    # trace:
    #   0=nothing generated
    #   1=produces:
    #       ImageStars.tab  -- tab delimited list of stars found in the image
    #       CatStars.tab    -- tab delimited list of stars used from the catalog
    #       (these can be imported into a spreadsheet and scatter graphed to examine them)
    #       TripletTrace.txt -- technical, for support only; not self-documenting
    #   2=produces the above plus:
    #       TripletDump.txt -- even more technical, for support only
    # The caller is responsible for renaming/copying these files to preserve them
    # The caller may also want to rename/copy the temp.fts file with its updated FITS header info.

    if camera == 0:
        #Imager, narrow field [SOMETIMES] and deep (we hope)
        cameraString = "imager" #"narrow"
        sCamera = "Narrow"	#used with Log2Summary
    else:
        #Guider, wide field, not deep
        cameraString = "Guid"   # "Wide"
        sCamera = "*Wide*"	#used with Log2Summary

    Log2(1,"Pinpoint (%s) start..." % (cameraString) )

    #set parameters based on which camera used
    pp = win32com.client.Dispatch("PinPoint.Plate")
    trace = 1

    try:
       pp.AttachFITS(filename)
    except:
       #this means the file could not be opened
       Error("   Pinpoint routine could not open file: " + filename)
       Error("   The image is probably very bad")
       Log2Summary(1,"PP " + sCamera + " failed; could not open file, probably very bad")
       return (False, 0., 0.,0.)

    #if the supplied RA/Dec arguments are both 0, then assume the image already has FITS header settings for these
    if not expectedPos.isValid:
       #assume the fits header already has the expected coordinates
       pp.RightAscension = UTIL.HMSToHours(pp.ReadFITSValue("OBJCTRA"))
       pp.Declination    = UTIL.DMSToDegrees(pp.ReadFITSValue("OBJCTDEC"))
    else:
       pp.RightAscension,pp.Declination  = expectedPos.getJ2000Decimal() # PrecessLocalToJ2000(expectedRA,expectedDec)

    #Sometimes (rarely? randomly?) PP uses these other variables when solving!
    pp.TargetRightAscension = pp.RightAscension
    pp.TargetDeclination = pp.Declination

    Log2(4,"J2000 RA = %s" % UTIL.HoursToHMS(pp.RightAscension,":",":","",1))
    Log2(4,"J2000 Dec = %s" % DegreesToDMS(pp.Declination))
    pp.TracePath = r"C:\temp"
    pp.TraceLevel = trace

    if camera == 0:
        #Imager, narrow field and deep (we hope)
        pp.ArcsecPerPixelHoriz     = vState.ImagerScale * vState.ppState[camera].binning #scale for binning
        pp.ArcsecPerPixelVert      = vState.ImagerScale * vState.ppState[camera].binning #scale for binning
        #Log2(1,"Using imageScale = %5.2f with bining %d" % (pp.ArcsecPerPixelHoriz,vState.ppState[camera].binning))
        pp.Catalog                 = vState.ppState[camera].CatalogID # 5  #3=GSC, 5=USNO_A2.0(6GB), 8=USNO_B2.0 via Internet
        #pp.CatalogPath = r"C:\Catalog"
        pp.CatalogMaximumMagnitude = vState.ppState[camera].CatMaxMag # 18         #default=20 (data limit probably 19)
        pp.MaxSolveTime            = vState.ppState[camera].MaxSolveTime # 90   #usually solves in less than 10 seconds; I've seen it go at least 45 seconds and still solve
        pp.SigmaAboveMean          = vState.ppState[camera].SigmaAboveMean # 2.0 #default 3.0; may want to use 2.5 or 2.0 for PP narrow??
        #using PP 2.0 may need image to be calibrated first to avoid false positives!

        #maybe make this value configurable?
        pp.CatalogExpansion = 0.3  #default 0.3; legal values 0.0 - 0.8

        expectedScale = vState.ImagerScale  * vState.ppState[camera].binning #scale for binning
    else:
        #Guider, wide field, not deep
        pp.ArcsecPerPixelHoriz     = vState.GuiderScale
        pp.ArcsecPerPixelVert      = vState.GuiderScale
        pp.Catalog                 = vState.ppState[camera].CatalogID  # 3  #3=GSC, 5=USNO_A2.0(6GB), 8=USNO_B2.0 via Internet
        #pp.CatalogPath = r"C:\gsc11"
        pp.CatalogMaximumMagnitude = vState.ppState[camera].CatMaxMag # 16
        pp.MaxSolveTime            = vState.ppState[camera].MaxSolveTime # 60   #this should solve quick; if it doesn't, something is wrong
        pp.SigmaAboveMean          = vState.ppState[camera].SigmaAboveMean # 2.0 #default 3.0; may want to use 2.5 or 2.0 for PP narrow??

        #maybe make this value configurable?
        pp.CatalogExpansion = 0.3  #default 0.3; legal values 0.0 - 0.8

        expectedScale = vState.GuiderScale  #(no binning supported here)

    if pp.Catalog == 5:
        pp.CatalogPath = r"C:\Catalog"
    elif pp.Catalog == 3:
        pp.CatalogPath = r"C:\gsc11"
    else:
        Error("Unsupported catalog value specified for PP: %d" % pp.Catalog)
        Log2Summary(1,"PP " + sCamera + " problem; unsupported catalog")
        return (False, 0., 0., 0.)

    #maybe (or maybe not):
    pp.ConvolveGaussian(1)      #arg is FWHM(arcsec) of Gaussian fn to use.
    pp.ImageModified = False    #to prevent modified image from being written out
    start = time.time()

    pp.FindImageStars()
    numImageStars = len(pp.ImageStars)
    Log2(2,"Number of image stars: %d" % numImageStars)             #HERE IS NUMBER OF IMAGE STARS IDENTIFIED IN THIS IMAGE-----------------======================

    Log2(4,"pp.ArcsecPerPixelHoriz = %f" % pp.ArcsecPerPixelHoriz)
    Log2(4,"pp.ArcsecPerPixelVert = %f" % pp.ArcsecPerPixelVert)
    Log2(4,"Using imageScale = %5.2f with bining %d" % (pp.ArcsecPerPixelHoriz,vState.ppState[camera].binning))
    Log2(4,"pp.Catalog = %s" % pp.Catalog)
    #pp.CatalogPath = r"C:\Catalog"
    Log2(4,"pp.CatalogMaximumMagnitude = %f" % pp.CatalogMaximumMagnitude)
    Log2(4,"pp.MaxSolveTime= %d" % pp.MaxSolveTime)
    try:
        Log2(4,"pp.FileName = %s" % pp.FileName)
    except:
        Log2(4,"filename did not work")
    #using PP 2.0 may need image to be calibrated first to avoid false positives!
    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    #Logic is located in file MultiPPSolve.py

    try:
        bSolve,msg = MultiPPSolve.MultiPPSolve(pp,camera, expectedPos, vState)

    except:
        bSolve = False
        msg = "Exception for MultiPPSolve"
        DumpPP(pp)

    Log2(0,msg)

    if bSolve:
       Log2(0, MultiPPSolve.DisplaySolveCountStr() )
        
    end = time.time()
    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    if not bSolve:
        if camera == 1:
            Log2(4,"Pinpoint did NOT solve.")
            vState.pinpoint_successive_wide_failures += 1
            if vState.pinpoint_successive_wide_failures > BAD_WEATHER_THRESHOLD:
                #We have had too many successive failures of the Wide field (guider)
                # for Pinpoint solve. This strongly suggests that the weather has
                # clouded up, and if that happens it might even start raining.
                # Therefore, stop the script and raise the alarm so I can close
                # up and protect the equipment.
                Log2Summary(1,"PP " + sCamera + " did not solve, and exceeded bad weather threshold; # stars = %d" % numImageStars)

                Log2(0,"%d successive Wide field Pinpoint failures; suspect bad weather; HALTING PROGRAM..." % (vState.pinpoint_successive_wide_failures))
                print "$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"
                print "$$                             $$"
                print "$$ Weather appears to be bad!  $$"
                print "$$                             $$"
                print "$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"
                ##SafetyPark(vState)
                ##raise SoundAlarmError,'BAD WEATHER SUSPECTED'
                vState.pinpoint_successive_wide_failures = 0    #reset in case we are configured to wait and try again later
                raise WeatherError

            if vState.pinpoint_successive_wide_failures > 2:
                Log2(0,"Warning: %d successive Wide field Pinpoint failures so far" % (vState.pinpoint_successive_wide_failures))

        if runMode != 1:
            Log2(2, "> test mode, bypass PP failure result <")
            Log2(2, "Pinpoint took: " + str(round(end-start,2)) + " seconds.")
            estJ2000RA, estJ2000Dec = expectedPos.getJ2000Decimal() #PrecessLocalToJ2000(expectedRA,expectedDec)
            return (True, estJ2000RA, estJ2000Dec,0.)     #success

        Log2(1,"Result: failed to solve  (%5.2f sec)" % (end-start))
        Log2Summary(1,"PP " + sCamera + " failed; SideOfSky=%d; # stars = %d" % (SideOfSky(vState),numImageStars))

        try:
            Log2(2, "vvvvvvvvvv")
            Log2(2, "> failed <             ImageStars = %d, CatalogStars = %d" % (len(pp.ImageStars),len(pp.CatalogStars)))
            Log2(2, "^^^^^^^^^^")
        except:
            Log2(2, "vvvvvvvvvv")
            Log2(2, "> failed <             (Pinpoint info not available)" )
            Log2(2, "^^^^^^^^^^")
        #Log2(2, "Pinpoint took: " + str(round(end-start,2)) + " seconds.")
        pp.WriteHistory("*** Failed to solve ***")
        catRAstring,catDecstring = expectedPos.getJ2000String()
        report_line = "%6.2f %5d %5d                           %5.3f %5d %5d %5d                             %6s %-14s%9s %9s" % (
            end-start,
            len(pp.ImageStars),
            len(pp.CatalogStars),
            pp.FullWidthHalfMax,
            pp.ImageStatisticalMode,
            pp.MaximumPixelValue,
            pp.MinimumPixelValue,
            strCamera(camera),
            targetID,
            catRAstring,catDecstring
            )
        LogBase(report_line, PINPOINT_SOLVE)

        pp.DetachFITS()
        del pp
        return (False, 0., 0., 0.)

    ## NOW: verify scale
    diff = abs( abs(pp.ArcsecPerPixelHoriz) - expectedScale )
    if (diff/expectedScale)*100 > SCALE_THRESHOLD_PCT:
        Log2(1,"Result: bad scale  (%5.2f sec)" % (end-start))
        Log2Summary(1,"PP " + sCamera + " failed;  bad scale; # stars = %d" % numImageStars)

        #Note: do not count this as a Wide failure for bad weather detection

        success = False
        Log2(2, "vvvvvvvvvvvvv")
        Log2(2, "> bad scale <             ImageStars = %d, CatalogStars = %d" % (len(pp.ImageStars),len(pp.CatalogStars)))
        Log2(2, "^^^^^^^^^^^^^")
        Log2(2,"Expected scale = %6.3f, found = %6.3f, diff = %d%%" % (expectedScale,abs(pp.ArcsecPerPixelHoriz),int((diff/expectedScale)*100)))
        Log2(2,"Plate scale varies > %d%% from expected" % (SCALE_THRESHOLD_PCT))
        #PinpointLogLine += " %d:Fail(scale:%5.2f)" % (exposure,diff)
        delta = 0.

        #2014.06.11 JU: if bad scale solution happens for Narrow image, AND there are > 200 stars[adjust this?] in the image, THEN ignore solve result and assume scope is positioned correctly
        #           (this can happen if trying to solve an image of a large globular cluster)
        if camera == 0 and len(pp.ImageStars) > 200:
            #ignore solve result
            Log2(1,"***narrow****")
            Log2(1,"*> IGNORED <*     (%5.2f sec)  Stars: Image = %d, Catalog = %d" % (end-start,len(pp.ImageStars),len(pp.CatalogStars)))
            Log2(1,"*************")
            Log2Summary(1,"PP " + sCamera + " assumed worked, but busy field and scale problem; # stars = %d" % numImageStars)

            solvedRA = expectedPos.dRA_J2000()
            solvedDec = expectedPos.dDec_J2000()
            #print count of catalog stars + matched stars
            Log2(4, "   Matched stars=" + str(len(pp.MatchedStars)))
            Log2(4, "   Match fit order=" + str(pp.MatchFitOrder) )
            Log2(4, "   Arcsec/pixel=" + str(abs(round(pp.ArcsecPerPixelHoriz,3))))
            Log2(4, "   Magnitude zero point=" + str(round(pp.MagZeroPoint,2)))
            Log2(4, "   Match average residual(arcsec)=" + str(round(pp.MatchAvgResidual,3)))
            Log2(4, "   Match RMS Residual=" + str(round(pp.MatchRMSResidual,3)))
            pp.DetachFITS()
            del pp
            return (True, solvedRA, solvedDec, 0)     #ignore solve and assume close enough
    else:
        if camera == 1:
            vState.pinpoint_successive_wide_failures = 0    #reset count whenever we have a Wide success

        success = True
        if camera == 0:
            Log2(1,"***narrow****")
        else:
            Log2(1,"****WIDE*****")
        Log2(1,"** SOLVED! **     (%5.2f sec)  Stars: Image = %d, Catalog = %d" % (end-start,len(pp.ImageStars),len(pp.CatalogStars)))
        Log2(1,"*************")
        Log2(2,"Soln J2000  RA=%s Dec=%s" % (UTIL.HoursToHMS(pp.RightAscension,":",":","",1),DegreesToDMS(pp.Declination)))

        #Note: for all the 'True' success cases, the PinpointLogLine is handled later to get precision diff
        diffRA = pp.RightAscension - expectedPos.dRA_J2000()
        diffDec = pp.Declination - expectedPos.dDec_J2000()
        DiffRAdeg = diffRA * 15 * cosd(expectedPos.dDec_J2000())   #convert RA diff into degrees, adjusted for declination
        delta = math.sqrt((DiffRAdeg * DiffRAdeg) + (diffDec * diffDec)) * 60   #arcmin
#2012.06.07 JU: sometimes there is a problem converting JNow -> J2000 and the Dec value
#               does not convert correctly.  If I calculated this delta using the JNow
#               values instead, I could avoid this

        Log2(2,"Difference    %9s      %8s  = %6.2f arcmin" % (UTIL.HoursToHMS(diffRA,":",":","",1),DegreesToDMS(diffDec),delta))
        Log2Summary(1,"PP " + sCamera + " SUCCESS, SideOfSky=%d, Diff: %6.2f arcmin; # stars = %d" % (SideOfSky(vState),delta,numImageStars))


    solvedRA = pp.RightAscension
    solvedDec = pp.Declination
    pp.WriteFITSString("SOLVERA","%s" % UTIL.HoursToHMS(pp.RightAscension,":",":","",1))
    pp.WriteFITSString("SOLVEDEC","%s" % DegreesToDMS(pp.Declination))
    pp.WriteHistory("SOLVERA,SOLVEDEC values are J2000 from Pinpoint")

    #print count of catalog stars + matched stars
    Log2(4, "   Matched stars=" + str(len(pp.MatchedStars)))
    Log2(4, "   Match fit order=" + str(pp.MatchFitOrder) )
    Log2(4, "   Arcsec/pixel=" + str(abs(round(pp.ArcsecPerPixelHoriz,3))))
    Log2(4, "   Magnitude zero point=" + str(round(pp.MagZeroPoint,2)))
    Log2(4, "   Match average residual(arcsec)=" + str(round(pp.MatchAvgResidual,3)))
    Log2(4, "   Match RMS Residual=" + str(round(pp.MatchRMSResidual,3)))
    #pp.WriteHistory("This is a test history string")
    catRAstring, catDecstring = expectedPos.getJ2000String()
    diffRA = pp.RightAscension - expectedPos.dRA_J2000()
    diffDec = pp.Declination - expectedPos.dDec_J2000()
    report_line = "%6.2f %5d %5d %5d   %d   %5.3f  %5.3f  %5.3f %5d %5d %5d %7.2f  %8s %9s %6s %-14s%9s %9s  %10s %9s" % (
            end-start,
            len(pp.ImageStars),
            len(pp.CatalogStars),
            len(pp.MatchedStars),
            pp.MatchFitOrder,
            pp.MatchAvgResidual,
            abs(pp.ArcsecPerPixelHoriz),
            pp.FullWidthHalfMax,
            pp.ImageStatisticalMode,
            pp.MaximumPixelValue,
            pp.MinimumPixelValue,
            pp.PositionAngle,
            UTIL.HoursToHMS(solvedRA,":",":","",1),
            DegreesToDMS(solvedDec),
            strCamera(camera),
            targetID,
            catRAstring, catDecstring, UTIL.HoursToHMS(diffRA,":",":","",1),DegreesToDMS(diffDec)
            )
    LogBase(report_line, PINPOINT_SOLVE)

    ##pp.UpdateFITS()
    try:
       pp.UpdateFITS()
    except:
       niceLogExceptionInfo()
       Error("Unable to update FITS file!!! (it might be in use by another program)")
       #Error("Tip: in CustomPinpointSolve, take the pp.UpdateFITS() call out side of the try/except block to see what the problem really is.")

    pp.DetachFITS()
    del pp
    return (success, solvedRA, solvedDec, delta)     #success

#--------------------------------------------------------------------------------------------------------
def DumpPP(pp):
    #return  #disabled
    Log2(4,"Dump of all PinPoint Properties:")
    Log2(4, "Airmass:")
    try:
        Log2(4, str(pp.Airmass))
    except:
        Log2(4, "n/a")

    Log2(4, "ArcsecPerPixelHoriz:")
    try:
        Log2(4, str(pp.ArcsecPerPixelHoriz))
    except:
        Log2(4, "n/a")

    Log2(4, "ArcsecPerPixelVert:")
    try:
        Log2(4, str(pp.ArcsecPerPixelVert))
    except:
        Log2(4, "n/a")

    Log2(4, "BackgroundTileSize:")
    try:
        Log2(4, str(pp.BackgroundTileSize))
    except:
        Log2(4, "n/a")

    Log2(4, "BinningHoriz:")
    try:
        Log2(4, str(pp.BinningHoriz))
    except:
        Log2(4, "n/a")

    Log2(4, "BinningVert:")
    try:
        Log2(4, str(pp.BinningVert))
    except:
        Log2(4, "n/a")

    Log2(4, "CacheImageStars:")
    try:
        Log2(4, str(pp.CacheImageStars))
    except:
        Log2(4, "n/a")

    Log2(4, "Camera:")
    try:
        Log2(4, str(pp.Camera))
    except:
        Log2(4, "n/a")

    Log2(4, "Catalog:")
    try:
        Log2(4, str(pp.Catalog))
    except:
        Log2(4, "n/a")

    Log2(4, "CatalogExpansion:")
    try:
        Log2(4, str(pp.CatalogExpansion))
    except:
        Log2(4, "n/a")

    Log2(4, "CatalogMaximumMagnitude:")
    try:
        Log2(4, str(pp.CatalogMaximumMagnitude))
    except:
        Log2(4, "n/a")

    Log2(4, "CatalogMinimumMagnitude:")
    try:
        Log2(4, str(pp.CatalogMinimumMagnitude))
    except:
        Log2(4, "n/a")

    Log2(4, "CatalogPath:")
    try:
        Log2(4, str(pp.CatalogPath))
    except:
        Log2(4, "n/a")

    Log2(4, "CatalogStars:")
    try:
        Log2(4, str(pp.CatalogStars))
    except:
        Log2(4, "n/a")

    Log2(4, "CatalogStarsReady:")
    try:
        Log2(4, str(pp.CatalogStarsReady))
    except:
        Log2(4, "n/a")

    Log2(4, "CCDTemperature:")
    try:
        Log2(4, str(pp.CCDTemperature))
    except:
        Log2(4, "n/a")

    Log2(4, "CentroidAlgorithm:")
    try:
        Log2(4, str(pp.CentroidAlgorithm))
    except:
        Log2(4, "n/a")

    Log2(4, "ColorBand:")
    try:
        Log2(4, str(pp.ColorBand))
    except:
        Log2(4, "n/a")

    Log2(4, "Columns:")
    try:
        Log2(4, str(pp.Columns))
    except:
        Log2(4, "n/a")

    Log2(4, "Declination:")
    try:
        Log2(4, str(pp.Declination))
    except:
        Log2(4, "n/a")

    Log2(4, "Email:")
    try:
        Log2(4, str(pp.Email))
    except:
        Log2(4, "n/a")

    Log2(4, "EngineVersion:")
    try:
        Log2(4, str(pp.EngineVersion))
    except:
        Log2(4, "n/a")

    Log2(4, "Equinox:")
    try:
        Log2(4, str(pp.Equinox))
    except:
        Log2(4, "n/a")

    Log2(4, "ExclusionBorder:")
    try:
        Log2(4, str(pp.ExclusionBorder))
    except:
        Log2(4, "n/a")

    Log2(4, "ExposureInterval:")
    try:
        Log2(4, str(pp.ExposureInterval))
    except:
        Log2(4, "n/a")

    Log2(4, "ExposureStartTime:")
    try:
        Log2(4, str(pp.ExposureStartTime))
    except:
        Log2(4, "n/a")

    Log2(4, "FileName:")
    try:
        Log2(4, str(pp.FileName))
    except:
        Log2(4, "n/a")

    Log2(4, "FilterName:")
    try:
        Log2(4, str(pp.FilterName))
    except:
        Log2(4, "n/a")

    Log2(4, "FitOrder:")
    try:
        Log2(4, str(pp.FitOrder))
    except:
        Log2(4, "n/a")

    Log2(4, "FullWidthHalfMax:")
    try:
        Log2(4, str(pp.FullWidthHalfMax))
    except:
        Log2(4, "n/a")

    Log2(4, "Humidity:")
    try:
        Log2(4, str(pp.Humidity))
    except:
        Log2(4, "n/a")

    Log2(4, "ImageBackgroundMean:")
    try:
        Log2(4, str(pp.ImageBackgroundMean))
    except:
        Log2(4, "n/a")

    Log2(4, "ImageBackgroundSigma:")
    try:
        Log2(4, str(pp.ImageBackgroundSigma))
    except:
        Log2(4, "n/a")

    Log2(4, "ImageModified:")
    try:
        Log2(4, str(pp.ImageModified))
    except:
        Log2(4, "n/a")

    Log2(4, "ImagePixel:")
    try:
        Log2(4, str(pp.ImagePixel))
    except:
        Log2(4, "n/a")

    Log2(4, "ImageStars:")
    try:
        Log2(4, str(pp.ImageStars))
    except:
        Log2(4, "n/a")

    Log2(4, "ImageStarsReady:")
    try:
        Log2(4, str(pp.ImageStarsReady))
    except:
        Log2(4, "n/a")

    Log2(4, "ImageStatisticalMode:")
    try:
        Log2(4, str(pp.ImageStatisticalMode))
    except:
        Log2(4, "n/a")

    Log2(4, "InnerAperture:")
    try:
        Log2(4, str(pp.InnerAperture))
    except:
        Log2(4, "n/a")

    Log2(4, "MagZeroPoint:")
    try:
        Log2(4, str(pp.MagZeroPoint))
    except:
        Log2(4, "n/a")

    Log2(4, "MatchAvgResidual:")
    try:
        Log2(4, str(pp.MatchAvgResidual))
    except:
        Log2(4, "n/a")

    Log2(4, "MatchedStars:")
    try:
        Log2(4, str(pp.MatchedStars))
    except:
        Log2(4, "n/a")

    Log2(4, "MatchedStarsReady:")
    try:
        Log2(4, str(pp.MatchedStarsReady))
    except:
        Log2(4, "n/a")

    Log2(4, "MatchFitOrder:")
    try:
        Log2(4, str(pp.MatchFitOrder))
    except:
        Log2(4, "n/a")

    Log2(4, "MatchRMSResidual:")
    try:
        Log2(4, str(pp.MatchRMSResidual))
    except:
        Log2(4, "n/a")

    Log2(4, "MaximumPixelValue:")
    try:
        Log2(4, str(pp.MaximumPixelValue))
    except:
        Log2(4, "n/a")

    Log2(4, "MaxMatchResidual:")
    try:
        Log2(4, str(pp.MaxMatchResidual))
    except:
        Log2(4, "n/a")

    Log2(4, "MaxSolveStars:")
    try:
        Log2(4, str(pp.MaxSolveStars))
    except:
        Log2(4, "n/a")

    Log2(4, "MaxSolvetime:")
    try:
        Log2(4, str(pp.MaxSolvetime))
    except:
        Log2(4, "n/a")

    Log2(4, "MinimumBrightness:")
    try:
        Log2(4, str(pp.MinimumBrightness))
    except:
        Log2(4, "n/a")

    Log2(4, "MinimumStarSize:")
    try:
        Log2(4, str(pp.MinimumStarSize))
    except:
        Log2(4, "n/a")

    Log2(4, "MinMatchStars:")
    try:
        Log2(4, str(pp.MinMatchStars))
    except:
        Log2(4, "n/a")

    Log2(4, "Observatory:")
    try:
        Log2(4, str(pp.Observatory))
    except:
        Log2(4, "n/a")

    Log2(4, "Observer:")
    try:
        Log2(4, str(pp.Observer))
    except:
        Log2(4, "n/a")

    Log2(4, "OuterAperture:")
    try:
        Log2(4, str(pp.OuterAperture))
    except:
        Log2(4, "n/a")

    Log2(4, "PositionAngle:")
    try:
        Log2(4, str(pp.PositionAngle))
    except:
        Log2(4, "n/a")

    Log2(4, "Pressure:")
    try:
        Log2(4, str(pp.Pressure))
    except:
        Log2(4, "n/a")

    Log2(4, "ProjectionType:")
    try:
        Log2(4, str(pp.ProjectionType))
    except:
        Log2(4, "n/a")

    Log2(4, "RightAscension:")
    try:
        Log2(4, str(pp.RightAscension))
    except:
        Log2(4, "n/a")

    Log2(4, "RollAngle:")
    try:
        Log2(4, str(pp.RollAngle))
    except:
        Log2(4, "n/a")

    Log2(4, "Rows:")
    try:
        Log2(4, str(pp.Rows))
    except:
        Log2(4, "n/a")

    Log2(4, "ScratchX:")
    try:
        Log2(4, str(pp.ScratchX))
    except:
        Log2(4, "n/a")

    Log2(4, "ScratchY:")
    try:
        Log2(4, str(pp.ScratchY))
    except:
        Log2(4, "n/a")

    Log2(4, "SiderealTime:")
    try:
        Log2(4, str(pp.SiderealTime))
    except:
        Log2(4, "n/a")

    Log2(4, "SigmaAboveMean:")
    try:
        Log2(4, str(pp.SigmaAboveMean))
    except:
        Log2(4, "n/a")

    Log2(4, "SiteElevation:")
    try:
        Log2(4, str(pp.SiteElevation))
    except:
        Log2(4, "n/a")

    Log2(4, "SiteLatitude:")
    try:
        Log2(4, str(pp.SiteLatitude))
    except:
        Log2(4, "n/a")

    Log2(4, "SiteLongitude:")
    try:
        Log2(4, str(pp.SiteLongitude))
    except:
        Log2(4, "n/a")

    Log2(4, "Solved:")
    try:
        Log2(4, str(pp.Solved))
    except:
        Log2(4, "n/a")

    Log2(4, "TargetDeclination:")
    try:
        Log2(4, str(pp.TargetDeclination))
    except:
        Log2(4, "n/a")

    Log2(4, "TargetName:")
    try:
        Log2(4, str(pp.TargetName))
    except:
        Log2(4, "n/a")

    Log2(4, "TargetRightAscension:")
    try:
        Log2(4, str(pp.TargetRightAscension))
    except:
        Log2(4, "n/a")

    Log2(4, "TDIMode:")
    try:
        Log2(4, str(pp.TDIMode))
    except:
        Log2(4, "n/a")

    Log2(4, "Telescope:")
    try:
        Log2(4, str(pp.Telescope))
    except:
        Log2(4, "n/a")

    Log2(4, "Temperature:")
    try:
        Log2(4, str(pp.Temperature))
    except:
        Log2(4, "n/a")

    Log2(4, "TraceLevel:")
    try:
        Log2(4, str(pp.TraceLevel))
    except:
        Log2(4, "n/a")

    Log2(4, "TracePath:")
    try:
        Log2(4, str(pp.TracePath))
    except:
        Log2(4, "n/a")

    Log2(4, "UseFaintStars:")
    try:
        Log2(4, str(pp.UseFaintStars))
    except:
        Log2(4, "n/a")

    Log2(4, "UseSExtractor:")
    try:
        Log2(4, str(pp.UseSExtractor))
    except:
        Log2(4, "n/a")

    Log2(4, "WCSValid:")
    try:
        Log2(4, str(pp.WCSValid))
    except:
        Log2(4, "n/a")

#--------------------------------------------------------------------------------------------------------
def ExposeFlat(desiredADU, rangeAllowed, hintExp, repeat, filter, binning, flatBaseName, vState):
    # Take flat frames at desired level and save files [uses C:\fits_flat directory]
    # desiredADU = the desired average ADU of the image
    # rangeAllowed = ADU above or below desiredADU; if image within this
    #   range then the image is saved as a flat; if outside then
    #   exposure re-adjusted and try again.
    # hintExp = initial exposure to try
    # repeat = the number of exposures desired at this setting
    # filter = which filter to use for the exposures (number value)
    # binning = 1,2,3
    # flatBaseName = used to create filename; suggest "Flat_L_1x1" or "Flat_R_2x2"...
    #
    # Return: exposure most recently used, or 0 if unable to complete desired flats

    Log2(1,"ExposeFlat: filter:%d  bin:%d  repeat:%d  expHint:%5.2f  ADU=%d +-%d" % (filter,binning,repeat,hintExp,desiredADU,rangeAllowed))
    #validate input!
    if desiredADU <= 1:     #using 1 here so can use it to scale and reduce exposures
        Log2(2,"Error: desiredADU too small")
        return 0
    if hintExp <= 0:
        Log2(2,"Error, hintExp must be > 0")
        return 0

    #set limits
    minExposure = 0.01  #seconds
    maxExposure = 5     #seconds
    maxRetries = 20     #limit attempts for one exposure
    #maybe limit on stdADU?

    expose = hintExp    #starting point

    while repeat > 0:
        repeat -= 1

        #loop over different exposure times until we find one that works
        retries = 0
        while True:
            retries += 1
            if retries > maxRetries:
                Log2(2,"Failed: exceeded maxRetries; unable to adjust to desired ADU")
                return 0

#StartX, StartY, NumX, NumY

            vState.CAMERA.BinX = binning
            vState.CAMERA.BinY = binning

            #set a 100x100 subframe near the middle (not the edge where there is vignetting)
            vState.CAMERA.StartX = ((vState.CAMERA.CameraXSize / binning) / 2) - 50
            vState.CAMERA.StartY = ((vState.CAMERA.CameraYSize / binning) / 2) - 50
            vState.CAMERA.NumX = 100
            vState.CAMERA.NumY = 100

            vState.CAMERA.Expose( expose, 1, filter )
            LogOnly("Begin subframe exposure")
            while not vState.CAMERA.ImageReady:
                time.sleep(0.5)
            LogOnly("End subframe exposure")
            doc = vState.CAMERA.Document     #point to image just taken so we can measure it
            LogOnly("Subframe flat size: %d x %d" % (doc.XSize,doc.YSize))
            tup = doc.CalcAreaInfo(0,0,doc.XSize-1,doc.YSize-1,0)   #look at entire frame
            maxADU = tup[0]
            minADU = tup[1]
            avgADU = tup[2]
            stdADU = tup[3]
            LogOnly("CalcAreaInfo: max:%d  min:%d  avg:%5.2f  std:%5.2f (avg used to control exposure)" % (maxADU,minADU,avgADU,stdADU))

            if avgADU >= (desiredADU - rangeAllowed) and avgADU <= (desiredADU + rangeAllowed):
                #exposure is in desired range; save it
                Log2(4,"Exposure accepted, take full frame exposure now")

                #take another exposure of same duration but full frame; don't bother testing it, just accept it
                vState.CAMERA.BinX = 1  #make sure no rounding for Full Frame
                vState.CAMERA.BinY = 1
                vState.CAMERA.SetFullFrame()
                vState.CAMERA.BinX = binning
                vState.CAMERA.BinY = binning
                vState.CAMERA.Expose( expose, 1, filter )
                LogOnly("Begin full frame exposure")
                while not vState.CAMERA.ImageReady:
                    time.sleep(0.5)
                LogOnly("End full frame exposure")
                doc = vState.CAMERA.Document     #point to image just taken
                Log2(4,"Full frame exposure completed")
                break

            #recalc sun's altitude to report it, and also include in FITS header if we save this image
            tup1 = time.gmtime()
            #print tup1
            mYear  = tup1[0]
            mMonth = tup1[1]
            mDay   = tup1[2]
            utc    = float(tup1[3]) + (float(tup1[4])/60.) + (float(tup1[5])/3600.)
            #print utc,"%f" % utc
            alt = CalcSolarAlt(mYear,mMonth,mDay,utc,myLongitude,myLatitude)

            Log2(0,"Exp: %4.2f, ADU=%6.1f, min=%d, max=%d, std=%5.2f, sun=%5.2f" % (expose,avgADU,minADU,maxADU,stdADU,alt))

            #adjust the exposure and try again
            if avgADU > desiredADU:

                #too high; try reducing exposure by fraction
                if expose < minExposure:
                    Log2(2,"Failed: sky too bright")
                    return 0    #too bright!
                lastExpose = expose
                factor = (float(avgADU) / float(desiredADU))   #this value > 1
                LogOnly("Adjustment factor to reduce flat exposure: %f" % factor)
                expose /= factor
                if expose >= lastExpose:
                    #value should have decreased; logic not working (maybe precision limit)
                    Log2(2,"Failed/error: exposure not decreasing; expose=%5.2f  avgADU=%5.2f  desiredADU=%d" % (expose,avgADU,desiredADU))
                    return 0
                Log2(3,"**ADJUST:  ADU too high, try expose=%5.2f" % expose)
                continue
            else:
                #too low; try increasing
                if expose > maxExposure:
                    Log2(2,"Failed: sky too faint")
                    return 0    #too faint
                if avgADU * 5 > desiredADU:
                    #try scaling (avgADU is at least 20% of desired value)
                    lastExpose = expose
                    factor = (float(desiredADU) / float(avgADU))  #this value > 1
                    expose *= factor
                    LogOnly("Adjustment factor to increase flat exposure: %f" % factor)
                    if expose <= lastExpose:
                        #value should have increased; logic not working
                        Log2(2,"Failed/error: exposure not increasing; expose=%5.2f  avgADU=%5.2f  desiredADU=%d" % (expose,avgADU,desiredADU))
                        return 0
                    Log2(3,"**ADJUST:  ADU too low, try expose=%5.2f" % expose)
                    continue
                else:
                    #try doubling exposure (avgADU too small to scale reliably)
                    expose *= 2
                    Log2(3,"**ADJUST:  ADU too low, double expose to=%5.2f" % expose)
                    continue

        #we have an exposure within the desired value
        flatfile = CreateFilename( vState.path_dark_bias_flat, flatBaseName, vState,0)
        if filter == 0:
           color = "RED"
        elif filter == 1:
           color = "GREEN"
        elif filter == 2:
           color = "BLUE"
        elif filter == 4:
           color = "H-alpha"
        else:
           #color = "LUMINANCE"
           color = "C"      #2014.10.06 change filter designatioun to work with Lesve Photometry
        doc.SetFITSKey("FILTER",color)
        doc.SetFITSKey("IMAGETYP","FLAT")
        #doc.SetFITSKey("XBINNING","%d" % binning)
        #doc.SetFITSKey("YBINNING","%d" % binning)
        #doc.SetFITSKey("SOLARALT","%f" % alt)
        # ??also set CCD-TEMP ??
        doc.SaveFile( flatfile, 3, False, 1, 0)   # 3=fits format; False=do not autostretch; 1=16-bit data; 0=no compression
        Log2(3,"Image saved: %s" % flatfile)

    #all done; return the most recent exposure as a possible hint if called again
    #for a different filter
    Log2(3,"Flat exposures completed")
    return expose

#--------------------------------------------------------------------------------------------------------
def ExposeWideFlat(desiredADU, rangeAllowed, hintExp, repeat, flatBaseName, vState):
    # Take flat frames with WIDE field (guide) camera at desired level and save files [uses C:\fits_flat directory]
    # desiredADU = the desired average ADU of the image
    # rangeAllowed = ADU above or below desiredADU; if image within this
    #   range then the image is saved as a flat; if outside then
    #   exposure re-adjusted and try again.
    # hintExp = initial exposure to try
    # repeat = the number of exposures desired at this setting
    # flatBaseName = used to create filename; suggest "WideFlat_L_1x1" ...
    #
    # Return: exposure most recently used, or 0 if unable to complete desired flats

    Log2(1,"ExposeWideFlat: repeat:%d  expHint:%5.2f  ADU=%d +-%d" % (repeat,hintExp,desiredADU,rangeAllowed))
    #validate input!
    if desiredADU <= 1:     #using 1 here so can use it to scale and reduce exposures
        Log2(0,"!!<WIDE Error>!!: desiredADU too small")
        return 0
    if hintExp <= 0:
        Log2(0,"!!<WIDE Error>!!, hintExp must be > 0")
        return 0

    #set limits
    minExposure = 0.01  #seconds
    maxExposure = 5     #seconds
    maxRetries = 20     #limit attempts for one exposure
    #maybe limit on stdADU?

    expose = hintExp    #starting point

    while repeat > 0:
        repeat -= 1

        #loop over different exposure times until we find one that works
        retries = 0
        while True:
            retries += 1
            if retries > maxRetries:
                Log2(0,"**STOP: WIDE Failed: exceeded maxRetries; unable to adjust to desired ADU")
                return 0

            vState.CAMERA.GuiderExpose( expose )
            while vState.CAMERA.GuiderRunning:
                time.sleep(2)    #waiting until the guide exposure is done
                LogStatus(vState,5)
            doc = GetGuiderDoc(vState)

            tup = doc.CalcAreaInfo(0,0,doc.XSize-1,doc.YSize-1,0)   #look at entire frame
            maxADU = tup[0]
            minADU = tup[1]
            avgADU = tup[2]
            stdADU = tup[3]

            #recalc sun's altitude to report it, and also include in FITS header if we save this image
            tup1 = time.gmtime()
            #print tup1
            mYear  = tup1[0]
            mMonth = tup1[1]
            mDay   = tup1[2]
            utc    = float(tup1[3]) + (float(tup1[4])/60.) + (float(tup1[5])/3600.)
            #print utc,"%f" % utc
            alt = CalcSolarAlt(mYear,mMonth,mDay,utc,myLongitude,myLatitude)

            Log2(0,"WIDE Exp: %4.2f,ADU=%6.1f,min=%d,max=%d,std=%5.2f,sun=%5.2f" % (expose,avgADU,minADU,maxADU,stdADU,alt))

            if avgADU >= (desiredADU - rangeAllowed) and avgADU <= (desiredADU + rangeAllowed):
                #exposure is in desired range; save it
                Log2(4,"WIDE Exposure accepted")
                break

            #adjust the exposure and try again
            if avgADU > desiredADU:
                #too high; try reducing exposure by fraction
                if expose < minExposure:
                    Log2(0,"**STOP: WIDE Failed: sky too bright")
                    return 0    #too bright!
                lastExpose = expose
                factor = (float(avgADU) / float(desiredADU))   #this value > 1
                expose /= factor
                if expose >= lastExpose:
                    #value should have decreased; logic not working (maybe precision limit)
                    Log2(0,"**STOP WIDE Failed/error: exposure not decreasing; expose=%5.2f  avgADU=%5.2f  desiredADU=%d" % (expose,avgADU,desiredADU))
                    return 0
                Log2(3,"**ADJUST: WIDE ADU too high, try expose=%5.2f" % expose)
                continue
            else:
                #too low; try increasing
                if expose > maxExposure:
                    Log2(0,"**STOP: WIDE Failed: sky too faint")
                    return 0    #too faint
                if avgADU * 5 > desiredADU:
                    #try scaling (avgADU is at least 20% of desired value)
                    lastExpose = expose
                    expose *= (float(desiredADU) / float(avgADU))  #this value > 1
                    if expose <= lastExpose:
                        #value should have increased; logic not working
                        Log2(0,"**STOP: WIDE Failed/error: exposure not increasing; expose=%5.2f  avgADU=%5.2f  desiredADU=%d" % (expose,avgADU,desiredADU))
                        return 0
                    Log2(3,"**ADJUST: WIDE ADU too low, try expose=%5.2f" % expose)
                    continue
                else:
                    #try doubling exposure (avgADU too small to scale reliably)
                    expose *= 2
                    Log2(3,"**ADJUST: WIDE ADU too low, double expose to=%5.2f" % expose)
                    continue

        #we have an exposure within the desired value
        flatfile = CreateFilename( vState.path_dark_bias_flat, flatBaseName, vState,0)
        #color = "LUMINANCE"
        color = "C"      #2014.10.06 change filter designation to work with Lesve Photometry
        doc.SetFITSKey("FILTER",color)
        doc.SetFITSKey("IMAGETYP","FLAT")
        #doc.SetFITSKey("XBINNING","%d" % binning)
        #doc.SetFITSKey("YBINNING","%d" % binning)
        #doc.SetFITSKey("SOLARALT","%f" % alt)
        # ??also set CCD-TEMP ??
        doc.SaveFile( flatfile, 3, False, 1, 0)   # 3=fits format; False=do not autostretch; 1=16-bit data; 0=no compression
        Log2(3,"WIDE Image saved: %s" % flatfile)

    #all done; return the most recent exposure as a possible hint if called again
    #for a different filter
    Log2(3,"WIDE Flat exposures completed")
    return expose

#=====================================================================================
#==== SECTION  @@Movement ============================================================
#=====================================================================================

##def EnableTestForMeridianLimit(vState):
##    #*-code complete-*#
##    #set global flag: if we are initially on east side of pier, there is no chance of a meridian flip
##    # during an exposure, although for targets in north the OTA can change side of pier, but this does
##    # not require a flip.
##    if runMode != 1:
##        return    #disabled for simulator or testing
##
##    if vState.MOUNT.SideOfPier == 1:    #1=looking east, 0=looking west
##      SkipTestForMeridianLimit = False    #Want to run test, so do not skip
##      LogOnly("SkipTestForMeridianLimit set to False (we WANT to test for meridian limit)")
##    else:
##      SkipTestForMeridianLimit = True     #do not want test, so skip it
##      LogOnly("SkipTestForMeridianLimit set to True (do NOT want to test))")

#--------------------------------
def MeridianCross(vState):
    #*-code complete-*#
    #called at start of a step, or in the repeat loop between exposures
    #tests against crossing the meridan
    #Return True = meridian reached; must stop current step or reposition
    return TestForMeridianLimit(vState.MeridianPast,1,vState)

#--------------------------------
def MeridianSafety(vState):
    #*-code complete-*#
    #called during exposure delay loops; will interrupt exposure/sequence
    #tests if past meridian by safety limit (approx 0.5 hours); this gives
    # current exposure/sequence a chance to complete without being interrupted.
    #Return True = meridian safety limit; must stop exposure, must stop current step or reposition
    return TestForMeridianLimit(vState.MeridianSafety,0,vState)


#--------------------------------------------------------------------------------------------------------
def TestForMeridianLimit(threshold,verbose,vState):
    #*-code complete-*#
    #This implements MeridianCross() and MeridianSafety(); other code should NOT call this.
    #return True = meridian limit reached
    #If verbose == 1, this is called by MeridianCross and is not called frequently,
    #  so output VERBOSE messages. Else no messages (called from imaging delay loop)

    if runMode != 1:
        if verbose == 1:
            #only log this if called from "MeridianCross"
            Log2(2,"MeridianCross: test disabled")
        return False    #disabled for simulator or testing

    if SkipTestForMeridianLimit:
        if verbose == 1:
            #only log this if called from "MeridianCross"
            Log2(2,"MeridianCross: OTA pointing west so skip test")
#IS THIS LOG MSG CORRECT? THERE IS NO TEST OF SIDE-OF-SKY
        return False    #we cannot have a pier flip situation during this exposure because already pointing west
                    # regardless of any changes in SideOfPier  (well, theoretically, if tracking an object
                    # underneath the pole, that would be a valid case for a pier flip, but I don't plan to
                    # do this; too low in sky.)

    # situation log:
    # RA, Dec, SideOfPier, camera temp, Guider new meas?, Guide X,Y errors, LastGuiderError, ShutterOpen

    #if vState.MOUNT.SideOfPier == 1:        #1=looking east, 0=looking west
    if SideOfSky(vState) == 1:        #1=looking east, 0=looking west
##        #2011.05.17 JU:
##        #ISSUE: if pointed to north below level of Polaris, OTA can easily pass over
##        #       the pier and trigger this code, even though it is perfectly fine
##        #       and should be left alone. Add code to test for this:
##        if vState.MOUNT.Azimuth > 270 and vState.MOUNT.Altitude < 42:
##            #we are fine even though OTA crossed meridian
##            if threshold == 0:
##                #only log this if called from "MeridianCross"
##                Log2(1,"Note: overriding meridian cross logic for NW part of sky")
##                Log2(3,"Sidereal Time: " + UTIL.HoursToHMS( vState.MOUNT.SiderealTime))
##                Log2(3,"Target RA:     " + UTIL.HoursToHMS( vState.MOUNT.RightAscension))
##                Log2(3,"Target Dec:   " + DegreesToDMS( vState.MOUNT.Declination))
##                Log2(3,"Altitude:      " + str(round(vState.MOUNT.Altitude,2)))
##                Log2(3,"Azimuth:       " + str(round(vState.MOUNT.Azimuth,2)))
##            return False
        HA = vState.MOUNT.SiderealTime - vState.MOUNT.RightAscension
        if HA < -12:  HA += 24
        if HA > 12: HA -= 24

        if HA > threshold:  #only care about positive difference; negative HA values are all safe for this side of pier
            #this will abort the current exposure to prevent hardware damage
            Log2(4,"Sidereal Time: " + UTIL.HoursToHMS( vState.MOUNT.SiderealTime,":",":","",1))
            Log2(4,"Target RA:     " + UTIL.HoursToHMS( vState.MOUNT.RightAscension,":",":","",1))
            Log2(4,"Target Dec:   " + DegreesToDMS( vState.MOUNT.Declination))
            Log2(4,"Hour angle:    " + str(UTIL.HoursToHM( HA )))
            Log2(4,"Test threshold:" + str(threshold) + ", HA is larger than this: " + str(HA))
            Log2(4,"Altitude:      " + str(round(vState.MOUNT.Altitude,2)))
            Log2(4,"Azimuth:       " + str(round(vState.MOUNT.Azimuth,2)))
            Log2(4,"Current pier side=%d/%d" % (vState.MOUNT.SideOfPier,SideOfSky(vState)))

            Error("******************************")
            Error("***   PIER FLIP REQUIRED   ***")
            Error("******************************")
            Log2Summary(0,"PIER FLIP REQUIRED, HA=" + UTIL.HoursToHMS( HA,":",":","",1))

            return True    #we have crossed the meridian!!
    if threshold == 0:
        #only log this if called from "MeridianCross"
        #Log2(2,"MeridianCross: no violation")
        pass
    return False

#--------------------------------------------------------------------------------------------------------
def EnhancedMeridianFlip(vState):       #!! Gemini specific code !!
    #Use the command Blind Gemini feature to try to slew the mount East away
    # from the meridian so it can move again, then slew to a target in the
    # western sky to get it on the correct side of the pier; if this works
    # then the calling routine can continue w/ positioning.
    #(If Gemini tracks into the meridian limit, it stops responding to most
    # movement commands. This routine is an attempt to automate recovery from
    # that situation.)

    #return False if success, True if still problem (and caller should abort program)
    #if vState.MOUNT.SideOfPier == 0:
    if SideOfSky(vState) == 0:
        #on east side looking west; this routine does not apply
        return True

    Log2(1,"***************************************")
    Log2(1,"** Attempting enhanced meridian flip **")
    Log2(1,"***************************************")
    Log2Summary(1,"Attempting enhanced meridian flip")

    #SendToServer(getframeinfo(currentframe()),"Attempting enhanced meridian flip")

    retry = 3
    while retry > 0:
        retry -= 1

        ## Get current motion from Gemini via blind cmd: :Gv#  DOES NOT WORK

        #attempt to slew the telescope east for 1 second
        # left
        Log2(2,"Current location(JNow) RA %s  Dec %s  Side=%d" % (vState.UTIL.HoursToHMS(vState.MOUNT.RightAscension,":",":","",1),DegreesToDMS(vState.MOUNT.Declination),vState.MOUNT.SideOfPier))
        Log2(2,"Slew east: start")
        vState.MOUNT.CommandBlind(":Me#",True)
        time.sleep(2)
        Log2(2,"... stop")
        vState.MOUNT.CommandBlind(":Q#",True)
        #Note: I do NOT think that I could have used AbortSlew() here; those slew commands
        #seem to depend on the current state of tracking, and when the mount is 'stuck'
        #on the meridian, tracking is off.
        time.sleep(2)
        Log2(2,"New location(JNow) RA %s  Dec %s  Side=%d" % (vState.UTIL.HoursToHMS(vState.MOUNT.RightAscension,":",":","",1),DegreesToDMS(vState.MOUNT.Declination),vState.MOUNT.SideOfPier))

        #try to turn back on tracking
        vState.MOUNT.Tracking = True
        time.sleep(1)
        if not vState.MOUNT.Tracking:
            Error("Attempt turn turn tracking back on has failed!")


        #try to GOTO a point in the western sky, causing a pier flip as part of this
        toRA = vState.MOUNT.SiderealTime - 1
        if toRA < 0:
            toRA += 24
        toDec = vState.MOUNT.Declination
        if vState.MOUNT.Declination > 70 or vState.MOUNT.Declination < 20:
            #I don't want to send it to an extreme declination, just to be safe
            toDec = 45
        Log2(2,"Attempt to slew to: RA %s  Dec %s" % (vState.UTIL.HoursToHMS(toRA,":",":","",1),DegreesToDMS(toDec)))
        vState.MOUNT.SlewToCoordinatesAsync(toRA, toDec)       # Movement occurs here <----------------

        #wait while slewing
        started = time.time()
        while vState.MOUNT.Slewing:
           time.sleep(1)    #wait until the slew is done
           LogStatusShort(vState)
           slewTime = time.time() - started
           if slewTime > 90:
                #this is wrong!
                Error("Excessive slew time detected; ABORTING SLEW")
                vState.MOUNT.AbortSlew()
                break;
        slewTime = time.time() - started
        Log2(2,"Took %d seconds to complete this slew; pier side now=%d" % (slewTime,vState.MOUNT.SideOfPier))

        #after slew, test side of pier; if on east side, success
        if vState.MOUNT.SideOfPier == 0:
            #on east side looking west, which is exactly where we want to be
            Log2(1,"***************************************")
            Log2(1,"**        !!!  SUCCESS  !!!          **")
            Log2(1,"***************************************")
            Log2Summary(1,"Pier flip completed")
            return False

    #tried a couple of times, still did not work; do not try too much, don't want
    # to slew mount east into ground!  Have to give up at this point
    return True


#--------------------------------------------------------------------------------------------------------
def execMeridianFlip(desiredPos,ID,vState,bImagerSolve):
    #Return True if problem, False if no problem
    #This flips meridian, then uses PP to precisely reposition scope
    #Note that this turns OFF guiding, so caller is responsible for turning it
    # back on if needed.

    StopGuiding(vState)

    #Send Gemini specific command for pier flip (this only does motion if
    # the mount is in a position to pier flip)

    beforeSide = vState.MOUNT.SideOfPier
    Log2(1,"Before pier flip side = %d (1=pointing east, 0=pointing west)" % (beforeSide))

    Log2(1,"Side of pier before command: " + str(vState.MOUNT.SideOfPier))
    Log2(2,"Issue pier flip command now.")
    vState.MOUNT.CommandBlind(":Mf#",True)
    Log2(1,"Waiting for pier flip to complete")
    started = time.time()

    time.sleep(2)   #give it a chance to start

    # 2009.06.15 JU:
    #Make sure motion stopped before testing side below (the Slewing
    #  value is not reliable during a pier flip).
    #Look at mount coordinates and see if it is still moving
    Log2(2,"Check to see if mount still moving after pier flip command")
    maxExtend = 90  #max we can extend this delay if we see movement
    count = 10       #initial delay to see if movement
    fromRA = vState.MOUNT.RightAscension
    fromDec = vState.MOUNT.Declination
    while count > 0:
       count -= 1
       time.sleep(1)    #wait until movement really stops
       LogStatusShort(vState)
       toRA = vState.MOUNT.RightAscension
       toDec = vState.MOUNT.Declination

       #have we moved much?
       DiffRA = abs(toRA - fromRA)
       DiffDec = abs(toDec - fromDec)
       #convert to sqrt arcmin, note if large, maybe bump count to delay end?
       DiffRAdeg = DiffRA * 15 * cosd(toDec)   #convert RA diff into degrees, adjusted for declination
       delta = math.sqrt((DiffRAdeg * DiffRAdeg) + (DiffDec * DiffDec)) * 60    #//arcminutes
       if delta > 0.05:      #threshold to detect still moving (may need to readjust this)
           Log2(2,"Mount still moving: %5.2f arcmin   (count=%d, extend=%d) pier=%d/%d" % (delta,count,maxExtend,vState.MOUNT.SideOfPier,SideOfSky(vState)))
           if maxExtend > 0:
               maxExtend -= 1
               count = 10       #reset count if seeing any motion (sometimes we don't but it is still moving)
               #Warning: even though the mount is moving, some passes through the loop here
               # do not see motion, and decrement the count.  So I reset the count all
               # the way to the beginning so that it doesn't time out too soon.
       else:
           Log2(2,"Mount is not moving   (count=%d)" % count)

       fromRA = toRA    #for next check
       fromDec = toDec

    Log2(2,"Mount should be stationary after pier flip command")
    afterSide = vState.MOUNT.SideOfPier

    if beforeSide == afterSide:
        Error("Pier flip command did not change side of mount!!!  before=%d after=%d (1=point east, 0=point west)" % (beforeSide,afterSide))
        #Do we want to continue here w/ Pinpoint steps??
        #raise "Pier flip did not occur"
        if EnhancedMeridianFlip(vState):
            Error("EnhancedMeridianFlip did not work; attempt to Park scope anyway (probably will not work)")
            SafetyPark(vState)
            raise SoundAlarmError,'Halting program' #still didn't work
        #the Enhanced flip worked; continue w/ positioning

    #We should be on the other side of the pier now, and probably very close to
    # the target.

    #Before repositioning on the target, IF WE ARE USING THE IMAGER then
    # first go to a nearby bright star, optionally refocus, and measure current
    # imager offset (probably changed after pier flip).
    if bImagerSolve and vState.focusEnable:
        bSuccess = False
        nLimit = 10     #number of retries before halting
        while not bSuccess:
            tband = BuildFocusStarBand(desiredPos,vState)  #Note: this uses pos, not repos; want star near target!
            fstar = FindNearFocusStar(vState,desiredPos, tband[0], tband[1])
            #GOTO that star, optionally refocus on it, and then calibrate imager offset
            if CalibrateOrRefocusForNewTarget(fstar,vState):
                #Problem; this might mean the chosen catalog star doesn't really exist (this can happen)
                Error("Problem with CalibrateOrRefocusForNewTarget!!")
                Error("vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv")
                Error("Possible focus star catalog entry error for: %s" % fstar.name)
                Error("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
                #problem
                nLimit -= 1
                if nLimit <= 0:
                    Error("Too many retries for CalibrateOrRefocusForNewTarget")
                    Error("Possible weather issue...")
                    ##SafetyPark(vState)
                    ##raise SoundAlarmError,'**maybe weather issue**'
                    raise WeatherError
            else:
                bSuccess = True

    Log2(1,"Now slewing back to desired target coordinates (OTA should be east now)")
    GOTO(desiredPos,vState,ID)

    #Now precisely re-position the mount on the specified coords using PP solves.
    # If the imager is being used, the PP work here will use the Imager offset
    # measured above.
    ret = PinpointEntry(desiredPos, ID, vState, bImagerSolve)
    #EnableTestForMeridianLimit(vState)   #check whether we need to watch for pier flip later during the exposure (probably not since we just flipped)
    return ret

#--------------------------------------------------------------------------------------------------------
def SideOfSky(vState):
    #return 0 = pointing west (OTA usually east); 1 = pointing east (OTA usually west)
    # Eventually the Gemini.NET driver will return the pointing state; currently it
    #  returns the side of pier (which is not the same for far NE/NW parts of sky)

    try:
        #Important: this should be the ONLY code that looks at vState.MOUNT.SideOfPier !!!
        HA = vState.MOUNT.SiderealTime - vState.MOUNT.RightAscension
        if HA < -12:  HA += 24
        if HA > 12: HA -= 24
        #negative if position east of meridian (after adjustments for wrapping)

        if HA > -6 and HA < 6:
            #position is described by side of pier
            if runMode == 1:
                return vState.MOUNT.SideOfPier
            else:
                return 0    #running in simulator mode, which doesn't have this attribute

        if HA >= 6:
            return 0    #pointing west (far to northwest, below Polaris)

        #else HA <= -6
        return 1        #pointing east (far to northeast, below Polaris)
    except:
        Error("Exception thrown in call to SideOfSky")
        return 0

#--------------------------------------------------------------------------------------------------------
def PredictSideOfPier(pos, vState):
    #predict side of pier this position is, AND whether we should do
    # a pier flip BEFORE going to this location to insure we are on
    # the 'best' side of the pier before starting imaging there
    #Returns tuple: (sideOfPier, flag)
    #  where sideOfPier = 0 for OTA east, 1 for OTA west
    #  flag = False if no problem, True if should force a flip before going to this position
    #         from our current location relative to the pier.
    dRA = pos.dRA_JNow()
    meridian = vState.MOUNT.SiderealTime
    diff = meridian - dRA   #negative if position east of meridian (after adjustments for wrapping)
    if diff < -12:
        diff += 24
    if diff > 12:
        diff -= 24

    #diff is how close to the meridian this position is; if it is very close and we
    # are currently on the opposite side right now, the mount will not flip going there,
    # and this could limit how long we can image there before being forced to flip.
    if diff < -1:
        #position safely east of meridian; want OTA west
        return (1,False)

    if diff > 1:
        #position safely west of meridian; want OTA east
        return (0,False)

    if diff < 0:
        if runMode != 1:
            return (1,True)
        if SideOfSky(vState) == 1:  #on west side of pier?  #2017.02.18 JU: changed to using SideOfSky()
            #we are already on west side of pier looking east,
            # and target position is east of meridian, so OK
            return (1,False)
        else:
            #we are east of the pier, but target is also (slightly) east
            # so we should force a pier flip first
            return (1,True)
    else:
        #if vState.MOUNT.SideOfPier == 0:    #on east side of pier?
        if SideOfSky(vState) == 0:
            #we are already on east side of pier looking west,
            # and target position is to the west, so OK
            return (0,False)
        else:
            #we are west of pier, but target is (slightly) west of meridian,
            # so force a pier flip first
            return (0, True)

#--------------------------------------------------------------------------------------------------------

def RandomSafeLocation():      #generate someplace in sky, away from meridian and horizons (values are string values of degrees)
    #return strings for (azimuth,elevation)
    return random.choice([
        ( '21','63'),( '40','54'),( '56','41'),( '47','71'),( '64','58'),( '72','43'),
        ( '89','60'),( '88','39'),('134','70'),('116','57'),('105','39'),( '87','77'),
        ('162','58'),('134','47'),('119','35'),('164','47'),('142','40'),('159','37'),
        ('342','59'),('335','69'),('312','61'),('298','50'),('320','78'),('293','64'),
        ('265','80'),('269','62'),('270','47'),('231','73'),('252','60'),('259','45'),
        ('235','57'),('250','41'),('197','60'),('222','52'),('238','41'),('194','52'),
        ('234','40'),('192','48'),('209','44'),('226','36'),('195','40'),('281','49'),
        ('213','67'),('217','48')
    ] )

def GOTO(targetScopePos,vState,name=""):
    #return false if OK, True if unable to GOTO position (below horizon?)

    for attempt in range(20):
        problem = GOTO2(targetScopePos,vState,name)
        if problem == 0:
            Log2(1,"[GOTO] Success for target GOTO on attempt = %d" % attempt)
            return False    #success
        if problem == 2:
            Log2(1,"[GOTO] Unable to GOTO target, below horizon; attempt = %d" % attempt)
            Log2Summary(1,"[GOTO] Unable to GOTO target, below horizon; attempt = %d  %s" % (attempt,name))
            return True    #failure, but in a good way

        Log2(1,"[GOTO] FAILED for target GOTO on attempt = %d" % attempt)
        Log2Summary(1,"Begin Random GOTO solution because GOTO failed, attempt = %d %s"  % (attempt,name))
        #
        #not able to move to specified location, try moving to some other location
        for subAttempt in range(5):
            az, el = RandomSafeLocation()      #generate someplace in sky, away from meridian and horizons (values are string values of degrees)
            Log2(1,"[GOTO] Attempt random sky location: azimuth: %s, elevation: %s" % (az,el))
            ra, dec = AzElev2RaDec(az,el)       #converts to JNow
            randPos = Position()
            randPos.setJNowDecimal(ra,dec,"RandPos")
            sRA,sDec = randPos.getJNowString()
            Log2(1,"[GOTO] Random sky location is JNow RA: %s  Dec: %s" % (sRA,sDec))
            problem = GOTO2(randPos,vState,"RandPos")
            if problem == 0:
                Log2(1,"[GOTO] Success for random GOTO")
                Log2Summary(1,"Random goto was successful")
                break   #Good, we were able to move someplace else
            Log2(1,"[GOTO] FAILED for random GOTO, subattempt = %d" % subAttempt)  #repeat loop a few times to try other locations instead
        if problem != 0:
            #unable to successfully move to random location after several attempts,
            # so try parking mount at this point, then let outer loop run again to see if any better
            Log2(1,"[GOTO] Attempt SafetyPark after unable to move to random locations")
            SafetyPark(vState)
    #If we fall out of the outer loop, we have tried lots of attempts and not been successful, so give up
    Error("! SLEW FAILED TO REACH DESIRED LOCATION AFTER MULTIPLE ATTEMPTS")
    Log2Summary(1,"Unable to solve GOTO problem with Random solution; perform SafetyPark")
    SafetyPark(vState)
    raise SoundAlarmError,'Slew failed to reach desired location after multiple attempts'


#--------------------------------------------------------------------------------------------------------
def GOTO2(desiredScopePos,vState,name=""):
    #This is ONLY called by GOTO(), so that GOTO() can handle multiple retry attempts if necessary
    #Return:  0 = success, 1 = problem, 2 = target below horizon

    Log2(2,"***START OF GOTO2; COORDS DESIRED ARE:***")
    line0,line1 = desiredScopePos.dump2()
    Log2(3,line0)
    Log2(3,line1)

    #record the location we intend to end at
    vState.gotoPosition = desiredScopePos
    vState.gotoPosition.isValid = False     #disable this for now so guiding during Narrow PP doesn't encounter this
    vState.gotoPosition.posName = name
    Log2(4,"vState.gotoPosition.isValid set to FALSE")

    imaging_db.RecordGuider(vState,False,1051)

    vState.goto_count += 1
    StopGuiding(vState) #make sure guider is not running (this call does nothing if guider not currently running)

    beforeScopePos = Position()     #store position of scope before movement
    if runMode == 1 or runMode == 2:
        beforeScopePos.setJNowDecimal(vState.MOUNT.RightAscension,vState.MOUNT.Declination,name,cTypeReported)
    Log2(6,"GOTO - \nBeforeScopePos:\n" + beforeScopePos.dump())

    if runMode == 3:
        return 0  #OK, nothing useful to do here

    beforeSideOfPier = SideOfSky(vState)    #vState.MOUNT.SideOfPier
    sAlt_from = str(round(vState.MOUNT.Altitude,1))		#string
    sAz_from  = str(round(vState.MOUNT.Azimuth,1))		#string

    #Are we already 'stuck' at the meridian? If tracking is off, we may be
    if not vState.MOUNT.Tracking:
        imaging_db.RecordMount(vState,1061)
        EnhancedMeridianFlip(vState)


    started = time.time()

    #******************************************************
    # *** MOVE THE MOUNT to desired location **************
    #******************************************************
    if name != desiredScopePos.posName:
        Log2(1,"Slewing to: " + name + " / " + desiredScopePos.posName)
    else:
        Log2(1,"Slewing to: " + name)
    dRA_JNow_destination, dDec_JNow_destination = desiredScopePos.getJNowDecimal()
    dRA_J2000_destination, dDec_J2000_destination = desiredScopePos.getJ2000Decimal()

    Log2(3,"J2000 RA=%s  Dec=%s" % (vState.UTIL.HoursToHMS(dRA_J2000_destination,":",":","",1), DegreesToDMS(dDec_J2000_destination)))
    Log2(3,"JNow  RA=%s  Dec=%s" % (vState.UTIL.HoursToHMS(dRA_JNow_destination, ":",":","",1), DegreesToDMS(dDec_JNow_destination) ))
    #Log2(3,"Decimal JNow RA=%6.3f  Dec=%6.3f" % (dRA_JNow_destination, dDec_JNow_destination))
    Log2(4,"desiredScopePos.dump():")
    Log2(4,desiredScopePos.dump())


#start of subroutine here----------------------------
    Log2(4,"About to issue SlewToCoordinatesAsync")
    try:
        imaging_db.RecordMount(vState,1062)
        vState.MOUNT.SlewToCoordinatesAsync(dRA_JNow_destination, dDec_JNow_destination)       # Movement occurs here <----------------
    except:
        Error("Unable to slew to specified coordinates; probably below horizon!")
        Error("Non-fatal exception, details below:")
        niceLogNonFatalExceptionInfo()
        Error("Skip this step, continue on with execution")
        return 2
    Log2(4,"After call to SlewToCoordinatesAsync")  #saw it take 11 seconds to execute the above Slew call ???

    LogStatusShort(vState)
    time.sleep(1)    #pause to make sure movement starts
    LogStatusShort(vState)
    time.sleep(1)
    fromRA = vState.MOUNT.RightAscension
    fromDec = vState.MOUNT.Declination

    #2018.01.14 JU: SOMETIMES THE MOUNT NEVER MOVES AT ALL; SEEMS TO DEPEND ON GOTO BETWEEN CERTAIN LOCATIONS;
    while vState.MOUNT.Slewing:
       LogStatusShort(vState)
       time.sleep(1)    #wait until the slew is done
       slewTime = time.time() - started
       imaging_db.RecordMount(vState,1063)
       if slewTime > 120:
          #this is wrong!
          Error("Excessive slew detected; ABORTING SLEW")
          vState.MOUNT.AbortSlew()
          break

       #log as we move
       toRA = vState.MOUNT.RightAscension
       toDec = vState.MOUNT.Declination
       DiffRA = abs(toRA - fromRA)
       DiffDec = abs(toDec - fromDec)
       #convert to sqft arcmin, note if large, maybe bump count to delay end?
       DiffRAdeg = DiffRA * 15 * cosd(toDec)   #convert RA diff into degrees, adjusted for declination
       delta = math.sqrt((DiffRAdeg * DiffRAdeg) + (DiffDec * DiffDec)) * 60    #//arcminutes
       if delta > 0.05:      #threshold to detect still moving (may need to readjust this)
           Log2(4,"%s  %s  Mount still moving: %5.2f arcmin" % (vState.UTIL.HoursToHMS(toRA,":",":","",1), DegreesToDMS(toDec), delta))
       else:
           Log2(4,"%s  %s  Mount is not moving" % (vState.UTIL.HoursToHMS(toRA,":",":","",1), DegreesToDMS(toDec)))
       fromRA = toRA    #for next check
       fromDec = toDec

    Log2(2,"***WHERE WE STOPPED MOVING, ACCORDING TO THE SLEWING FLAG***")
    Log2(3,"JNow RA:  " + UTIL.HoursToHMS( vState.MOUNT.RightAscension,":",":","",1))
    Log2(3,"JNow  Dec: " + DegreesToDMS( vState.MOUNT.Declination ))

    slewTime = time.time() - started
    HA = vState.MOUNT.SiderealTime - vState.MOUNT.RightAscension
    if HA > 12: HA -= 24
    if HA < -12: HA += 24
    Log2(2,"Took %d seconds to complete this slew; pier side now=%d/%d; Hour angle = %5.2f" % (slewTime,vState.MOUNT.SideOfPier,SideOfSky(vState),HA))
    #Log2(2,"Hour angle = %5.2f" % (HA))

    afterScopePos = Position()     #store position of scope before movement
    if runMode == 1 or runMode == 2:
        afterScopePos.setJNowDecimal(vState.MOUNT.RightAscension,vState.MOUNT.Declination,name,cTypeReported)

    #after the slew are we in a bad position relative to the meridian?
    #We do NOT test for meridian here; the caller is responsible for it

    #******************************************************
    # *** FINISHED MOVEMENT *******************************
    #******************************************************

    # GOTO:             RA--JNow--Dec       RA--J2000--Dec    Name:     ssssssss
    #        From     00:00:00 +00:00:00  00:00:00 +00:00:00  side: x  Alt: xx  Az: xxx
    #        Desired  00:00:00 +00:00:00  00:00:00 +00:00:00  Duration: sss
    #        After    00:00:00 +00:00:00  00:00:00 +00:00:00  side: x  Alt: xx  Az: xxx
    #        Diff     00:00:00 +00:00:00  00:00:00 +00:00:00

    #beforeScopePos = mount's reported RA/Dec before movement
    #desiredPos     = coords given for where we want to move to
    #afterScopePos  = mount's reported RA/Dec after movement  (should be near desiredPos)


    sRA_fromJ, sDec_fromJ = beforeScopePos.getJNowString()
    sRA_from2, sDec_from2 = beforeScopePos.getJ2000String()

    sRA_desiredJ, sDec_desiredJ = desiredScopePos.getJNowString()
    sRA_desired2, sDec_desired2 = desiredScopePos.getJ2000String()

    sRA_afterJ, sDec_afterJ = afterScopePos.getJNowString()
    sRA_after2, sDec_after2 = afterScopePos.getJ2000String()

    afterSideOfPier = SideOfSky(vState) #vState.MOUNT.SideOfPier

    dRA_diffJ  = desiredScopePos.dRA_JNow() - afterScopePos.dRA_JNow()    #dRA_JNow_destination - vState.MOUNT.RightAscension
    dDec_diffJ = desiredScopePos.dDec_JNow() - afterScopePos.dDec_JNow()  #dDec_JNow_destination - vState.MOUNT.Declination

    #SANITY CHECK: DOES OUR OBJECT REALLY HAVE SAME VALUES AS SCOPE REPORTED?
    checkRA = afterScopePos.dRA_JNow() - vState.MOUNT.RightAscension
    checkDec = afterScopePos.dDec_JNow() - vState.MOUNT.Declination
    Log2(1,"Sanity check of final position: %f, %f" % (checkRA,checkDec))
    Log2(1,"Simple diff: desired - final:   %f, %f" % (dRA_diffJ,dDec_diffJ))

    dRA_diff2  = desiredScopePos.dRA_J2000() - afterScopePos.dRA_J2000()    #dRA_JNow_destination - vState.MOUNT.RightAscension
    dDec_diff2 = desiredScopePos.dDec_J2000() - afterScopePos.dDec_J2000()  #dDec_JNow_destination - vState.MOUNT.Declination

    sRA_diffJ = UTIL.HoursToHMS(dRA_diffJ,":",":","",1)
    sDec_diffJ = DegreesToDMS(dDec_diffJ)
    sRA_diff2 = UTIL.HoursToHMS(dRA_diff2,":",":","",1)
    sDec_diff2 = DegreesToDMS(dDec_diff2)
    delta1 = math.sqrt((dRA_diffJ * dRA_diffJ) + (dDec_diffJ * dDec_diffJ)) * 60   #arcmin
    delta2 = math.sqrt((dRA_diff2 * dRA_diff2) + (dDec_diff2 * dDec_diff2)) * 60   #arcmin

    sAlt_to = str(round(vState.MOUNT.Altitude,1))		#string
    sAz_to  = str(round(vState.MOUNT.Azimuth,1))		#string
    line0 = "GOTO:             RA--JNow--Dec       RA--J2000--Dec    Name:     %s" % (name)
    line1 = "       From     %s %s  %s %s  side: %d  Alt: %4s  Az: %5s" % (sRA_fromJ, sDec_fromJ, sRA_from2, sDec_from2, beforeSideOfPier, sAlt_from, sAz_from)
    line2 = "       Desired  %s %s  %s %s  Duration: %d"                % (sRA_desiredJ, sDec_desiredJ, sRA_desired2, sDec_desired2, slewTime)
    line3 = "       To       %s %s  %s %s  side: %d  Alt: %4s  Az: %5s" % (sRA_afterJ, sDec_afterJ, sRA_after2, sDec_after2, afterSideOfPier, sAlt_to, sAz_to)
    line4 = "       Diff    %9s  %8s %9s  %8s         = %6.2f/%6.2f arcmin" % (sRA_diffJ,sDec_diffJ,sRA_diff2,sDec_diff2,delta1,delta2)
    Log2(4,line0)
    Log2(4,line1)
    Log2(4,line2)
    Log2(4,line3)
    Log2(4,line4)

    LogBase(line0,MOVEMENT_LOG)
    LogBase(line1,MOVEMENT_LOG)
    LogBase(line2,MOVEMENT_LOG)
    LogBase(line3,MOVEMENT_LOG)
    LogBase(line4,MOVEMENT_LOG)
    LogBase("-----------------------------------------------------------------------------",MOVEMENT_LOG)

    #is the final position reasonably close to the desired coordinates?
    #if not, could indicate pier limit reached and slew disabled; I've also
    # seen the mount get confused and fail to slew if CMOS problem.
    if abs(dRA_diffJ) > 1 and abs(dRA_diffJ) < 23:
        Error("! SLEW FAILED TO REACH DESIRED RA")
        return 1     #Problem!
        #SafetyPark(vState)
        #raise SoundAlarmError,'Slew failed to reach desired RA'
    if abs(dDec_diffJ) > 15:
        Error("! SLEW FAILED TO REACH DESIRED DEC")
        return 1     #Problem!
        #SafetyPark(vState)
        #raise SoundAlarmError,'Slew failed to reach desired Dec'

    Log2(2,"***we are now about to monitor location to see if still moving***")
    Log2(3,"JNow RA:  " + UTIL.HoursToHMS( vState.MOUNT.RightAscension,":",":","",1))
    Log2(3,"JNow  Dec: " + DegreesToDMS( vState.MOUNT.Declination ))

    #!! Check for excessive movement after mount says it stopped
    maxExtend = 60  #max we can extend this delay if we see movement
    count = 5       #initial delay to see if movement
    fromRA = vState.MOUNT.RightAscension
    fromDec = vState.MOUNT.Declination
    while count > 0:
       count -= 1
       time.sleep(1)    #wait until movement really stops
       toRA = vState.MOUNT.RightAscension
       toDec = vState.MOUNT.Declination
       imaging_db.RecordMount(vState,1065)

       #have we moved much?
       DiffRA = abs(toRA - fromRA)
       DiffDec = abs(toDec - fromDec)
       #convert to sqft arcmin, note if large, maybe bump count to delay end?
       DiffRAdeg = DiffRA * 15 * cosd(toDec)   #convert RA diff into degrees, adjusted for declination
       delta = math.sqrt((DiffRAdeg * DiffRAdeg) + (DiffDec * DiffDec)) * 60    #//arcminutes
       Log2(3,"Moved while stationary? %5.2f arcmin (%5.2f,%5.2f)" % (delta,DiffRAdeg,DiffDec))
       if delta > 0.05:      #threshold to detect still moving (may need to readjust this)
           Log2(0,"Excessive motion detected after slew! %5.2f arcmin" % (delta))
           if maxExtend > 0:
               maxExtend -= 1
               count += 1

       fromRA = toRA    #for next check
       fromDec = toDec

    Log2(2,"***we exited loop looking for after movement; it should be stationary***")
    Log2(3,"JNow RA:  " + UTIL.HoursToHMS( vState.MOUNT.RightAscension,":",":","",1))
    Log2(3,"JNow  Dec: " + DegreesToDMS( vState.MOUNT.Declination ))

    afterScopePos = Position()     #store position of scope before movement
    if runMode == 1 or runMode == 2:
        afterScopePos.setJNowDecimal(vState.MOUNT.RightAscension,vState.MOUNT.Declination,name,cTypeReported)
    Log2(6,"GOTO - afterScopePos:" + afterScopePos.dump())

    #(this is used to detect if we drift too far from desired location during (poor) guiding)
    vState.gotoPosition.isValid = True     #enable this position if we start guiding next
    Log2(4,"vState.gotoPosition.isValid set to TRUE")
    Log2(5,"vState.gotoPosition = " + vState.gotoPosition.dump() )

    Log2(2,"***Finished with GOTO movement; this is where we stopped***")
    line0,line1 = afterScopePos.dump2()
    Log2(3,line0)
    Log2(3,line1)
    Log2(3,"... RA:  " + UTIL.HoursToHMS( vState.MOUNT.RightAscension,":",":","",1))
    Log2(3,"... Dec: " + DegreesToDMS( vState.MOUNT.Declination ))
    print vState.MOUNT.RightAscension,vState.MOUNT.Declination

    return 0 #OK

#=====================================================================================
#Wide_Cat_Count_Single,		       <targetID>[, <repeat>, <exp-secs>]
#                                      1           2           3
#Wide_Cat_EndTime_Single,	       <targetID>,<hh:mm:ss>[, <exp-secs>]
#                                      1           2           3

#Wide_JNow_Count_Single,           <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>]
#                                   1     2       3           4           5
#Wide_JNow_EndTime_Single,         <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>]
#                                   1     2       3           4           5

#Wide_J2000_Count_Single,	       <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>]
#                                   1     2       3           4           5
#Wide_J2000_EndTime_Single,        <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>]
#                                   1     2       3           4           5

#Wide_Stationary_Count_Single,     <targetID>[, <repeat>, <exp-secs>]
#                                      1           2           3
#Wide_Stationary_EndTime_Single,   <targetID>,<hh:mm:ss>[, <exp-secs>]
#                                      1           2           3

#Narrow_Cat_Count_Sequence,	      <targetID>[, <repeat>, <seq-filename>]
#                                      1           2           3
#Narrow_Cat_Count_Single,	      <targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B>]
#                                      1           2           3       4        5
#Narrow_Cat_EndTime_Sequence,	  <targetID>,<hh:mm:ss>[, <seq-filename>]
#                                      1           2           3
#Narrow_Cat_EndTime_Single,       <targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B>]
#                                      1           2           3       4        5

#Narrow_JNow_Count_Sequence,	  <RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>]
#                                   1     2       3           4           5
#Narrow_JNow_Count_Single,	      <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B>]
#                                   1     2       3           4           5       6        7
#Narrow_JNow_EndTime_Sequence,    <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <repeat>, <seq-filename>]
#                                   1     2       3           4           5
#Narrow_JNow_EndTime_Single,      <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B>]
#                                   1     2       3           4           5       6        7

#Narrow_J2000_Count_Sequence,	  <RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>]
#                                   1     2       3           4           5
#Narrow_J2000_Count_Single,	      <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B>]
#                                   1     2       3           4           5       6        7
#Narrow_J2000_EndTime_Sequence,	  <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <seq-filename>]
#                                   1     2       3           4           5
#Narrow_J2000_EndTime_Single,     <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B>]
#                                   1     2       3           4           5       6        7

#Narrow_Stationary_Count_Sequence,  <targetID>[, <repeat>, <seq-filename>]
#                                      1           2           3
#Narrow_Stationary_Count_Single,	<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B>]
#                                      1           2           3         4        5
#Narrow_Stationary_EndTime_Sequence,<targetID>,<hh:mm:ss>[, <seq-filename>]
#                                      1           2           3
#Narrow_Stationary_EndTime_Single,  <targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B>]
#                                      1           2           3         4        5
#--CROPPED--
#Cropped_Cat_Count_Sequence,	      <targetID>[, <repeat>, <seq-filename>]
#                                      1           2           3
#Cropped_Cat_Count_Single,	      <targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B>]
#                                      1           2           3       4        5
#Cropped_Cat_EndTime_Sequence,	  <targetID>,<hh:mm:ss>[, <seq-filename>]
#                                      1           2           3
#Cropped_Cat_EndTime_Single,       <targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B>]
#                                      1           2           3       4        5

#Cropped_JNow_Count_Sequence,	  <RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>]
#                                   1     2       3           4           5
#Cropped_JNow_Count_Single,	      <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B>]
#                                   1     2       3           4           5       6        7
#Cropped_JNow_EndTime_Sequence,    <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <repeat>, <seq-filename>]
#                                   1     2       3           4           5
#Cropped_JNow_EndTime_Single,      <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B>]
#                                   1     2       3           4           5       6        7

#Cropped_J2000_Count_Sequence,	  <RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>]
#                                   1     2       3           4           5
#Cropped_J2000_Count_Single,	      <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B>]
#                                   1     2       3           4           5       6        7
#Cropped_J2000_EndTime_Sequence,	  <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <seq-filename>]
#                                   1     2       3           4           5
#Cropped_J2000_EndTime_Single,     <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B>]
#                                   1     2       3           4           5       6        7

#Cropped_Stationary_Count_Sequence,  <targetID>[, <repeat>, <seq-filename>]
#                                      1           2           3
#Cropped_Stationary_Count_Single,	<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B>]
#                                      1           2           3         4        5
#Cropped_Stationary_EndTime_Sequence,<targetID>,<hh:mm:ss>[, <seq-filename>]
#                                      1           2           3
#Cropped_Stationary_EndTime_Single,  <targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B>]
#                                      1           2           3         4        5


#=====================================================================================
#==== SECTION  @@Command ============================================================
#=====================================================================================
def LoadIncludeFile( IncludeFilename, cmdList ):
    Log2(5,"INCLUDE %s" % IncludeFilename)
    cmdFile2 = open( IncludeFilename, "r")
    for line in cmdFile2:
        i = line.find('#')
        if i == 0:
           continue         #entire line is comment

        if i > 0:
           line = line[:i]  #strip off comments

        #strip off surrounding whitespace, and convert tabs to spaces
        line = line.strip().replace(chr(9)," ")

        if len(line) == 0:
            continue        #empty line

        if line.endswith("\n"):
            line = line[:-1]    #strip off trailing <CR> (may not be necessary)

        if line[0:8] == "INCLUDE ":
            raise ValidationError, 'INCLUDE files may not be nested'

        cmdList.append( line )
        Log2(6,line)

    cmdFile2.close()
    #Log2(4,"* End of INCLUDE file                 *")
    #Log2(4,"***************************************")

def LoadList( CommandFilename, cmdList ):
    Log2(4,"***************************************")
    Log2(4,"* Command file used for this session: *")
    Log2(4,"* Filename = %-24s *" % CommandFilename)
    cmdFile = open( CommandFilename, "r")
    for line in cmdFile:
        i = line.find('#')
        if i == 0:
           continue         #entire line is comment

        if i > 0:
           line = line[:i]  #strip off comments

        #strip off surrounding whitespace, and convert tabs to spaces
        line = line.strip().replace(chr(9)," ")

        if len(line) == 0:
            continue        #empty line

        if line.endswith("\n"):
            line = line[:-1]    #strip off trailing <CR> (may not be necessary)

        #is this an INCLUDE file?
        if line[0:8] == "INCLUDE ":
            LoadIncludeFile(line[8:].strip(),cmdList)
        else:
            cmdList.append( line )
            Log2(5,line)

    cmdFile.close()
    Log2(4,"* End of command file                 *")
    Log2(4,"***************************************")

    #print "Command list loaded with:"
    #print cmdList

#--------------------------------------------------------------------------------------------------------
def ValidateList( theList ):
    Log2(0,"Validate targets against catalog:")
    for line in theList:
        if line[:9].upper() == "AUTOUNTIL":
            global gSurveyCommandPresent
            gSurveyCommandPresent = True
            Log2(0,"Survey command present, so will load TargetList later")
            continue

#        if line[:3].upper() != "CAT" and line[:10].upper() != "NARROW_CAT" and line[:8] != "WIDE_CAT":
        if line[:3].upper() != "CAT" and line[:10].upper() != "NARROW_CAT" and line[:8].upper() != "WIDE_CAT" and line[:11].upper() != "CROPPED_CAT":
            continue         #not a catalog line; do not validate

        tup = tuple(line.split(','))
        if len(tup) < 2:
            continue         #not enough fields to be a catalog line

        objectName = tup[1].strip()
        pos = LookupObject(objectName)  ##, "J2000")  #THIS CAN SET CatalogLookupFailures
        #Note: we just want to know that we could find the object
        if pos.isValid:
            Log2(0, "%-9s   OK" % (objectName))

    #after checking entire list, see if any failures found:
    if len(CatalogLookupFailures) > 0:
       Log2(0, " ")
       Log2(0, "Catalog errors vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv")
       for line in CatalogLookupFailures:
          Log2(1, line)
       Log2(0, " ")
       raise ValidationError, 'Failed to validate list'

    Log2(0, "All targets validated correctly")

    MPL_cache.clear()   #remove caching of any MPL coords from this validation step
    #we only want to cache them the first time we use one the first time.



#--------------------------------------------------------------------------------------------------------
def WriteRetryFile(copyList,index):
    #Don't write out the file if the current line is a setting (contains '=')
    #(might get file locking issues otherwise because that section runs so quickly)
    if copyList[index].find("=") >= 0:
        Log2(4,"Skipping rewrite of file because of setting line" )
        return;

    #write list contents from index thru end of list to file Exec_reload.txt
    f = open( RELOADFILE, "w")
    f.write("#Remember: changes to this file are not reflected in the original!\n\n")
    i = -1  #want first test to start at 0
    n = 0   #used to count how many lines remaining
    for line in copyList:
        i += 1

        #must retain all setting lines, so test if this line is one of them
        special = False
        if line.find("PP=") == 0:
            special = True
        if line.upper().find("SET_") == 0:
            special = True

        if i < index and not special:
            continue

        if i == index:
            f.write("# *** Current line below ***\n")
        f.write("%s\n" % line)
        if not special:
            n += 1  #just count executable lines

    f.close()
    Log2(3,"Rewrote file '%s' with %d lines remaining" % (RELOADFILE,n))

#-----------------------------------------------
def ExecuteList( theList ):
    Log2(0,"  ")
    Log2(0,"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    Log2(0,"~~~~~~~~~~ACTUAL EXECUTION BEGINS (Exec5.py)~~~")
    Log2(0,"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    Log2Summary(0,"***BEGIN SCRIPT EXECUTION HERE***")

    state = cState()     #initialize the state variable; this prints out messages of COM object setup

    #Disabled next line 2013.08.04 JU:
    #PrepareTargetList(state)            #used for survey step, or if MiniSAC catalog does not have a target

    print ">>>Path to sequence files:",pathSeq
    LIVE  = True

    #try to capture startup conditions for focuser:
    state.TempMeasureTime = time.time() - 86400 #set to past time to force initial focus event

    copyList = theList
    index = 0

    #loop over this list; empty lines already stripped out before getting here
    for line in theList:
      Log2Summary(0,"Command: " + line)
      WriteRetryFile(copyList,index)    #write out the remaining steps in case we halt and want to restart from here
      state.gotoPosition.isValid = False    #this only set True when GOTO executed as part of command, and then only for duration of that command
      Process( line, state)
      index += 1

    #delete the Restart file here; not needed any more since finished everything
    try:
        os.remove("Exec_restart.txt")
    except:
        pass    #OK if we never created it

    Log2(0,"~~~~~~~~~~Normal Execution Ends (Exec5.py)~~~")
    print "!!! DONE"

#--------------------------------------------------------------------------------------------------------
def Process( Line, vState ):
    # Line = actual command to process; comments were stripped out before calling here

    #SendToServer(getframeinfo(currentframe()),"Process: " + Line)

    #version 1 commands still supported
    action_list = [      #commands that result in actions
        # CmdName        Function for Cmd     RerunIfCloudy (eg skip 'stationary' steps)
        ("AUTOFOCUS",    execAutoFocus,             1),
        ("CATFOCUSNEAR", execCatFocusNear,          1),
        ("CATFOCUS",     execCatFocus,              1),
        ("FOCUSNEAR",    execNearAutoFocus,         0), #scope parked if cloudy so no 'near' object in parked position
        ("FOCUS",        execFocus,                 1),
        ("PARK",         execPark,                  0),
        ("DARKS",        execDarks,                 0),
        ("CropDARKS",    execCropDarks,             0),
        ("BIAS",         execBias,                  0),
        ("CropBIAS",     execCropBias,              0),
        ("FLATS",        execFlats,                 0),
        ("WAITUNTIL",    execWaitUntil,             0),
        ("CATGOTO",      execCatGoto,               0),      #Not implemented yet
        ("CoolerOff",    execCoolerOff,             0),
        ("ARCHIVE",      execArchive,               0),      #2011.07.30: runs __FinishSession.bat
        ("WAITFORDARK",        execWaitForDark,     0),      #2012.09.16 added feature
        ("DUMPSTATE",          execDumpState,       0),
        ("AUTOUNTIL",          execAutoUntil,       1),  #This is the 'survey' command!
        ("LW_MOSAIC",          execMosaicLW,        1),
        ("LN_MOSAIC",          execMosaicLN,        1),
        ("C_MOSAIC",           execMosaicC,         1),

        ("MeasureGuideScopeOffset",           exec_MeasureGuideScopeOffset,        1),


        ("Wide_Cat_Count_Single",             exec_Wide_Cat_Count_Single,          1),
        ("Wide_Cat_EndTime_Single",           exec_Wide_Cat_EndTime_Single,        1),

        ("Wide_JNow_Count_Single",            exec_Wide_JNow_Count_Single,         1),
        ("Wide_JNow_EndTime_Single",          exec_Wide_JNow_EndTime_Single,       1),

        ("Wide_J2000_Count_Single",           exec_Wide_J2000_Count_Single,        1),
        ("Wide_J2000_EndTime_Single",         exec_Wide_J2000_EndTime_Single,      1),

        ("Wide_Stationary_Count_Single",      exec_Wide_Stationary_Count_Single,   0),
        ("Wide_Stationary_EndTime_Single",    exec_Wide_Stationary_EndTime_Single, 0),

        ("Narrow_Cat_Count_Sequence",         exec_Narrow_Cat_Count_Sequence,      1),
        ("Narrow_Cat_Count_Single",           exec_Narrow_Cat_Count_Single,        1),
        ("Narrow_Cat_EndTime_Sequence",       exec_Narrow_Cat_EndTime_Sequence,    1),
        ("Narrow_Cat_EndTime_Single",         exec_Narrow_Cat_EndTime_Single,      1),

        ("Narrow_JNow_Count_Sequence",        exec_Narrow_JNow_Count_Sequence,     1),
        ("Narrow_JNow_Count_Single",          exec_Narrow_JNow_Count_Single,       1),
        ("Narrow_JNow_EndTime_Sequence",      exec_Narrow_JNow_EndTime_Sequence,   1),
        ("Narrow_JNow_EndTime_Single",        exec_Narrow_JNow_EndTime_Single,     1),

        ("Narrow_J2000_Count_Sequence",       exec_Narrow_J2000_Count_Sequence,    1),
        ("Narrow_J2000_Count_Single",         exec_Narrow_J2000_Count_Single,      1),
        ("Narrow_J2000_EndTime_Sequence",     exec_Narrow_J2000_EndTime_Sequence,  1),
        ("Narrow_J2000_EndTime_Single",       exec_Narrow_J2000_EndTime_Single,    1),

        ("Narrow_Stationary_Count_Sequence",  exec_Narrow_Stationary_Count_Sequence, 0),
        ("Narrow_Stationary_Count_Single",    exec_Narrow_Stationary_Count_Single,   0),
        ("Narrow_Stationary_EndTime_Sequence",exec_Narrow_Stationary_EndTime_Sequence, 0),
        ("Narrow_Stationary_EndTime_Single",  exec_Narrow_Stationary_EndTime_Single,  0),
#Cropped:
        ("Cropped_Cat_Count_Sequence",         exec_Cropped_Cat_Count_Sequence,      1),
        ("Cropped_Cat_Count_Single",           exec_Cropped_Cat_Count_Single,        1),
        ("Cropped_Cat_EndTime_Sequence",       exec_Cropped_Cat_EndTime_Sequence,    1),
        ("Cropped_Cat_EndTime_Single",         exec_Cropped_Cat_EndTime_Single,      1),

        ("Cropped_JNow_Count_Sequence",        exec_Cropped_JNow_Count_Sequence,     1),
        ("Cropped_JNow_Count_Single",          exec_Cropped_JNow_Count_Single,       1),
        ("Cropped_JNow_EndTime_Sequence",      exec_Cropped_JNow_EndTime_Sequence,   1),
        ("Cropped_JNow_EndTime_Single",        exec_Cropped_JNow_EndTime_Single,     1),

        ("Cropped_J2000_Count_Sequence",       exec_Cropped_J2000_Count_Sequence,    1),
        ("Cropped_J2000_Count_Single",         exec_Cropped_J2000_Count_Single,      1),
        ("Cropped_J2000_EndTime_Sequence",     exec_Cropped_J2000_EndTime_Sequence,  1),
        ("Cropped_J2000_EndTime_Single",       exec_Cropped_J2000_EndTime_Single,    1),

        ("Cropped_Stationary_Count_Sequence",  exec_Cropped_Stationary_Count_Sequence,  0),
        ("Cropped_Stationary_Count_Single",    exec_Cropped_Stationary_Count_Single,    0),
        ("Cropped_Stationary_EndTime_Sequence",exec_Cropped_Stationary_EndTime_Sequence,0),
        ("Cropped_Stationary_EndTime_Single",  exec_Cropped_Stationary_EndTime_Single,  0)


        ]

    state_list = [            #commands that set program state (line has '=' in it)
        ##("SET_TEMPREFOCUS",   setTempRefocus),
        ##("SET_TEMPCOMP",      setTempComp),
        ("SET_SETTLEGUIDING", setSettleGuiding),
        ("SET_ASTROMETRICRESYNC", setAstrometricResync),
        ("SET_GUIDE",         setGuide),
        ("SET_WAITIFCLOUDY",    setWaitIfCloudy),
        ("SET_FIXGUIDINGSTATE", setFixGuidingState),
        ("SET_GUIDESETTLEBUMP", setGuideSettleSetting),
        ("SET_SEQUENCE",      setSequence),
        ("SET_PATH",          setPath),
        ("SET_EXPOSURE",      setExposure),
        ("SET_FOCUSCOMPENSATION",setFocusCompensation),
		("SET_HALTALTITUDE",  setHaltAltitude),
        ("SET_REPEAT",        setRepeat),
        ("SET_SLEEP",         setSleep),
        ("SET_FILTER",        setFilter),
        ("SET_FLUSHCCD",      setFlushCCD),
        ("SET_ALTITUDE",      setAltitude),
        ("SET_REACQUIREAFTERPIERFLIP",  setReacquireAfterPierFlip),
        ("SET_IMAGESCALE",    setImageScale),
        ("SET_FLATALTITUDEMORNING",     setFlatAltitudeMorning),
        ("SET_FOCUSENABLE",   setFocusEnable),
        #("SET_SUBFRAME",      setSubFrame),
        #("SET_FULLFRAME",     setFullFrame),
        ("SET_DRIFTTHRESHOLD",    setDriftThreshold),
		("SET_ASTROMETRY.NET",	setAstrometryNet),		#New feature for Exec5.py
        ("PP",                setPP)
        ]

    #Reset any global state variables
    global gbAutoUntil
    gbAutoUntil = False     #set True only during survey step

    up_line = Line.upper()    #upper case version of line for string matching
    lineFields = tuple(up_line.split(','))
    cmdField = lineFields[0].strip()

    # !!!I SHOULD CLEAN UP THIS CODE !!!  TODO  <----------------------------------%%%%%%%%%%%%

    #
    # Decide if this line sets a value or executes an action
    #
    if up_line.find("=") >= 0:

        ##
        ## State command processing
        ##
        for (cmd,fn) in state_list:
            #LogOnly("Compare state command <" + cmd + "> to line: " + up_line)
            #if tup3[0] == cmd:
            if up_line.find(cmd) == 0:
                #print "Executing command ",cmd," for line: ",Line
                LogOnly("Executing command <%s> for line: %s" % (cmd,up_line))
                tup1 = tuple(Line.split('='))       #separate 1st arg from rest of line
                tup  = tuple(tup1[1].split(','))    #break up rest of line into fields
                fn(tup,vState)
                return
        Error( "Unable to parse Environment command: " + Line)
        raise ValidationError

    else:
        ##
        ## Action command processing
        ##
        for (cmd,fn,rerun) in action_list:
            upCmd = cmd.upper()
            if cmdField == upCmd:
                #we found the specified command to get its impl function to call
                Log2(0," ")
                Log2(0,"(Exec5.py)*** Command: %s" % (Line))
                Log2(1,"Filter = %d" % vState.CAMERA.Filter)

                tup = tuple(Line.split(','))
                # 2010.05.19 JU: trim whitespace from all parameter fields
                listClean = []
                for t in tup:
                    tClean = t.strip()
                    listClean.append(tClean)
                tupClean = tuple(listClean)

                while True:
                    try:
                        tret = fn(tupClean,vState)
                    except HorizonError:
                        Error("*************************************")
                        Error("*           Horizon error           *")
                        Error("*        Skipping this target       *")
                        Error("*************************************")
                        break

                    except WeatherError:
                        Error("Weather exception thrown; park mount for safety")
                        SafetyPark( vState )
                        if vState.WaitIfCloudy:
                            #if this is a 'stationary' command or other that should not be re-executed, just skip it
                            if not rerun:
                                tret = (1,)
                                break

                            #is the target too far west (HA > ~5?), then just skip it
                            #TODO

                            #is sun too high?
                            if TestSunAltitude(-6):
                                Error("Sun altitude too high for retry of this command")
                                tret = (1,)
                                break

                            #Wait half an hour
                            execUseful30MinuteDelay(vState)

                            #Turn mount back on before continuing!!!
                            if not vState.MOUNT.Connected:
                               vState.MOUNT.Connected = True
                            if vState.MOUNT.AtPark:
                               Log2(3,"Unparking mount")
                               vState.MOUNT.Unpark()
                            if not vState.MOUNT.Tracking:
                               vState.MOUNT.Tracking = True

                            #loop back to retry this same command
                            continue
                        else:
                            #retry not allowed; sound alarm because of bad weather
                            raise SoundAlarmError

                    if tret[0] == 2:
                       #Error occurred (bad argument); stop processing
                       return

                    #else no need to re-execute this step, go on to next one
                    break

                #else keep executing normally

                #show how many error messages (if any) occurred during this step
                global errorCount
                Log2(0,"Error count = %d" % errorCount)
                errorCount = 0
                return

        Error( "Unable to parse command: " + Line)      #we fell out of the above loop so did not find a match
        raise ValidationError

    return

#--------------------------------------------------------------------------------------------------------
# DumpState
def execDumpState(tup,vState):
   #dump out state class for debugging
   print " "
   print "-----------------------------------"
   print "Guiding:"
   print "   .guide   = %d" % vState.guide
   print "   .guide_exp = %d" % vState.guide_exp
   print " "
   print "Sequence:"
   print "   .sequence = %s" % vState.sequence
   print "   .sequence_time = %s" % vState.sequence_time
   print " "
   print "Path: %s" % vState.path          #= "C:\\fits\\"   #directory to write image files to
   print "Exposure: %f" % vState.exposure      #= 10       #default exposure
   print "Repeat:   %d" % vState.repeat        #= 1        #number of repeated EXP on one target (does NOT apply to sequences)
   ##print "Sleep:    %d" % vState.sleep         #= 15       #seconds to pause after slew (settle time)
   print "Filter:   %s" % vState.filter        #= 3        #0=red,1=green,2=blue,3=luminance(clear) [field always number]
   print "Min Altitude: %d" % vState.min_altitude  #= 0        #minimum altitude below which imaging will not occur (value should be < 60 or few targets will be available)
##   print "Temperature compensation:"
##   print "     .temp_comp       = %d" % vState.temp_comp  #overall enable temp comp
##   print "     .temp_comp_slope = %f" % vState.temp_comp_slope
##   print "     .TempCompPosition = %d" % vState.TempCompPosition
##   print "     .TempCompTemperature = %d" % vState.TempCompTemperature
##   print "Pinpoint success: %d" % vState.pinpoint_success
##   print "Pinpoint failure: %d" % vState.pinpoint_failure
##   print "Goto count:       %d" % vState.goto_count
##   print "Focus count:      %d" % vState.focus_count
##   print "Below Horizon:    %d" % vState.below_horizon_count
##   print "Focus failed cnt: %d" % vState.focus_failed_count
##   print "Guide count:      %d" % vState.guide_count
##   print "Guide fail cnt:   %d" % vState.guide_failure_count
##   print "Excessive slew cnt: %d" % vState.excessive_slew_time_count
   print "Flush:      %d" % vState.flush
   print "Flush cnt:  %d" % vState.flush_cnt
   print "Pinpoint setting:"
   print "    Imager:"
   vState.ppState[0].Dump_State()
   vState.ppState[1].Dump_State()
   print "-----------------------------------"
   print " "
   return (0,)

#--------------------------------
def execArchive(t,vState):
    #runs the __FinishSession.bat file

    #Important: close the databases before running script, so script can rename the daily database file
    if vState.SQMASTER is not None:
        imaging_db.SqliteStartup( vState.SQMASTER, 'Exec5D-shutdown' )
        vState.SQMASTER.close()
        vState.SQMASTER = None
    if vState.SQLITE is not None:
        vState.SQLITE.close()
        vState.SQLITE = None

    try:
        Log2(0, MultiPPSolve.DisplaySolveCountStr() )
    except:
        pass
        
    Log2(0,"About to run __FinishSession.bat")
    from subprocess import Popen
    p = Popen(r"C:\fits_script\__FinishSession.bat")
    stdout, stderr = p.communicate()

    print "stdout:", stdout
    print "stderr:",stderr
    Log2(0,"Completed running __FinishSession.bat")
    return (0,)

#--------------------------------
def execCoolerOff(t,vState):
   #turn off cooler; this would be used at end of all-night script to let camera warm up
   try:
       if vState.CAMERA.CoolerOn:
           vState.CAMERA.CoolerOn = False
           Log2(0,"Cooler turned off")
       else:
           Log2(0,"Cooler was already off when tried to execute CoolerOff script command")
   except:
       Error("Exception thrown when attempting to turn off cooler !?")
   return (0,)

##        ("FOCUS",        execFocus),    #
#  Focus,  <RA>, <Dec> [,<targetID>, <exp-secs>]
def execFocus(t,vState):
   dic = {}
   dic["crop"]     = "no"
   dic["location"] = "RA/Dec"
   dic["RA"]  = UTIL.HMSToHours(t[1])
   dic["Dec"] = UTIL.DMSToDegrees(t[2])
   dic["epoch"] = "JNow"                # <<---- JNow
   dic["type"]= "focus"


   try:
      dic["ID"]  = t[3]
   except:
      dic["ID"] = "Unspecified"

   try:
      dic["exp"] = float(t[4])
   except:
      dic["exp"] = 0.1   #default exposure for focusMax use

   return implFocus(dic,vState)



#--------------------------------
#  AutoFocus [,<exp-secs>]
def execAutoFocus(t,vState):

   #THIS IS CALLED FROM execAutoUntil SO IT IS PART OF SURVEY CODE; THIS
   #NEEDS TO BE REDESIGNED IN TERMS OF IMAGER OFFSET

   #vState.ResetImagerOffset()   #forces positioning to center in guider
   dic = {}
   dic["crop"]     = "no"
   dic["location"] = "auto"
   dic["type"]     = "focus"

   try:
      if len(t) >= 3:
        dic["exp"] = float(t[2])
      else:
        dic["exp"] = 0.1
   except:
      dic["exp"] = 0.1   #default exposure for focusMax use

   return implFocus(dic,vState)

#        ("CATFOCUS",     execCatFocus), #
#  CatFocus, <targetID> [,<exp-secs>]
def execCatFocus(t,vState):
   #vState.ResetImagerOffset()   #forces positioning to center in guider
   dic = {}
   dic["crop"]     = "no"
   dic["location"] = "cat"
   dic["ID"]       = t[1]    #this arg required for a 'cat' step; this would normally be an SAO star ID
   dic["type"]     = "focus"

   try:
      dic["exp"] = float(t[2])
   except:
      dic["exp"] = 0.1   #default exposure for focusMax use

   return implFocus(dic,vState)

#  CatFocusNear, <targetID> [,<exp-secs>]
def execCatFocusNear(t,vState):
    #vState.ResetImagerOffset()   #forces positioning to center in guider
    dic = {}
    dic["crop"]     = "no"
    dic["location"] = "near"
    dic["ID"]       = t[1]    #this arg required for a 'cat' step; this would normally be a deep sky object, it picks the star near it
    dic["type"]     = "focus"

    try:
      dic["exp"] = float(t[2])
    except:
      dic["exp"] = 0.1   #default exposure for focusMax use

    return implFocus(dic,vState)

#--------------------------------
def SafetyPark(vState):
    #call this to park the scope right before raising SoundAlarmError,
    # so that the scope is in a reasonably safe position in case I don't
    # respond to the alarm right away.

    Log2Summary(0,"SAFETY PARK")

    Log2(0,"SAFETY PARKING SCOPE..." )
    print "$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"
    print "$$                             $$"
    print "$$ Parking scope so it is safe $$"
    print "$$                             $$"
    print "$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"

    execPark((0,),vState)
    Log2(0,"Scope should be parked at this point")


##        ("PARK",         execPark),     #
#  Park
def execPark(t,vState):
    Log2(0," ")
    Log2(0,"-------------------------------------------------------------")
    StopGuiding(vState)     #make sure this is off or it will complain
    LogStatusHeaderBrief()
    LogStatus(vState,4)
    Log2(0,"*** Park mount (this can take a minute to complete)")
    if runMode == 3:
        LogOnly("Validate skipping rest of: execPark")
        return (0,)

    if vState.MOUNT.Connected:
        #vState.MOUNT.park()     ##THIS COMMAND DOES NOT SEEM TO WORK IN PYTHON
        vState.MOUNT.Tracking = True    #may need this on to slew; the Flats cmd turns it off
        #siderealTime = vState.MOUNT.SiderealTime
        #siderealTime -= 6   #move westward by 1/4 of sky (6 hours earlier in RA) so OTA will park above mount
        #if siderealTime < 0:
        #    siderealTime += 24

        #sometimes tracking is already off at this point;
        # catch exceptions here if that happens.
        try:
            prefix = ":"
            suffix = "#"
            bRaw   = True

            #vState.MOUNT.CommandBlind(prefix + "hC" + suffix,bRaw)
            vState.MOUNT.CommandBlind(prefix + "hP" + suffix,bRaw)   #park at HOME position instead of CWD
            #time.sleep(45)   #make sure it finishes

            #2017.02.20 JU: The mount did not park correctly the other day after using this command, so add
            # logging here used during a pier flip, to report on its movement.
            Log2(2,"Mount has been issued CommandBlind(park at home) command; monitor its movement now.")

            maxExtend = 90  #max we can extend this delay if we see movement
            count = 10       #initial delay to see if movement
            fromRA = vState.MOUNT.RightAscension
            fromDec = vState.MOUNT.Declination
            while count > 0:
               count -= 1
               time.sleep(1)    #wait until movement really stops
               LogStatusShort(vState)
               toRA = vState.MOUNT.RightAscension
               toDec = vState.MOUNT.Declination

               #have we moved much?
               DiffRA = abs(toRA - fromRA)
               DiffDec = abs(toDec - fromDec)
               #convert to sqrt arcmin, note if large, maybe bump count to delay end?
               DiffRAdeg = DiffRA * 15 * cosd(toDec)   #convert RA diff into degrees, adjusted for declination
               delta = math.sqrt((DiffRAdeg * DiffRAdeg) + (DiffDec * DiffDec)) * 60    #//arcminutes

               if delta > 2.00:      #(larger value because 'Park' moves relative to sky; threshold to detect still moving (may need to readjust this)
                   Log2(2,"Mount still moving: %5.2f arcmin (count=%d, extend=%d) pier=%d/%d" % (delta,count,maxExtend,vState.MOUNT.SideOfPier,SideOfSky(vState)))
                   if maxExtend > 0:
                       maxExtend -= 1
                       count = 10       #reset count if seeing any motion (sometimes we don't but it is still moving)
                       #Warning: even though the mount is moving, some passes through the loop here
                       # do not see motion, and decrement the count.  So I reset the count all
                       # the way to the beginning so that it doesn't time out too soon.
               else:
                   Log2(2,"Mount is not moving   (count=%d)" % count)

               fromRA = toRA    #for next check
               fromDec = toDec

            Log2(2,"Mount should be stationary after PARK command")

        except:
           niceLogExceptionInfo()
           Log2(0,"ERROR: The CommandBlind for PARK (or watching movement) threw an exception!!!")
           Log2(2,"Wait extra time just to make sure any mount movement is finished")
           time.sleep(45)   #make sure it finishes

        Log2(0,"Parked completed (Home)")
        vState.MOUNT.Tracking = False
        Log2(0,"Tracking turned OFF")
        vState.MOUNT.Connected = False
        Log2(0,"Mount DISCONNECTED")
    else:
        Log2(0,"Mount was NOT connected when PARK command executed; no action")

    return (0,) #OK to continue w/ next step
#--------------------------------
##        ("WAITFORDARK",        execWaitForDark),    #
#  WaitForDark, negativeSunAltitude
def execWaitForDark(t,vState):
    try:
       print "t = ",t
       desiredAlt = float(t[1])
    except:
       desiredAlt = -9.0

    if desiredAlt > 0:
        Error("Called WaitForDark() with positive altitude; must use negative altitude for sun below horizon")
	desiredAlt = -desiredAlt	#try to fix it

    Log2(0,"Wait for sun to reach below %5.2f degrees" % desiredAlt)
    while True:

       #what is sun's current altitude?
       tup = time.gmtime(time.time())
       mYear  = tup[0]
       mMonth = tup[1]
       mDay   = tup[2]
       utc    = float(tup[3]) + (float(tup[4])/60.) + (float(tup[5])/3600.)
       alt = CalcSolarAlt(mYear,mMonth,mDay,utc,myLongitude,myLatitude)

       if alt <= desiredAlt:
          Log2(0,"Sun altitude = %5.1f" % alt)
          break

       Log2(3,"Still waiting for sun to reach %5.1f, it is currently %5.1f" % (desiredAlt,alt))
       time.sleep(30)
       #this can wait a VERY LONG TIME

    Log2(0,"Sun has reached desired altitude for darkness; continue execution")
    return (0,) #OK to continue w/ next step


#--------------------------------
##        ("DARKS",        execDarks),    #
#  Darks,    <exp-secs>, <repeat> [,<bin>]
def execDarks(t,vState):
    dic = {}
    dic["crop"]     = "no"
    dic["isSeq"] = "no"
    dic["limit"] = "count"
    try:
       dic["exp"] = float(t[1])
    except:
       dic["exp"] = vState.exposure

    try:
       dic["repeat"] = int(t[2])
    except:
       dic["repeat"] = vState.repeat

    try:
       dic["bin"] = int(t[3])
    except:
       dic["bin"] = 2

    return implDarks(dic,vState)

#--------------------------------
##        ("DARKS",        execDarks),    #
#  Darks,    <exp-secs>, <repeat> [,<bin>]
def execCropDarks(t,vState):
    dic = {}
    dic["crop"]  = "yes"
    dic["isSeq"] = "no"
    dic["limit"] = "count"
    try:
       dic["exp"] = float(t[1])
    except:
       dic["exp"] = vState.exposure

    try:
       dic["repeat"] = int(t[2])
    except:
       dic["repeat"] = vState.repeat

    try:
       dic["bin"] = int(t[3])
    except:
       dic["bin"] = 2

    return implDarks(dic,vState)

def execUseful30MinuteDelay(vState):
    #called when we want a 30 minute delay, so take 30 minutes of darks.
    #Enhancement to do: do other variations of exposure/bin
    dic = {}
    dic["crop"]  = "no"
    dic["isSeq"] = "no"
    dic["limit"] = "count"
    dic["exp"] = 300
    dic["repeat"] = 6
    dic["bin"] = 2
    return implDarks(dic,vState)

#--------------------------------
##        ("BIAS",         execBias),     #
#  BIAS, <repeat> [,<bin>]
def execBias(t,vState):
    dic = {}
    dic["crop"]  = "no"
    dic["type"]  = "Bias"
    dic["limit"] = "count"

    try:
       dic["repeat"] = int(t[1])
    except:
       dic["repeat"] = vState.repeat

    try:
       dic["bin"] = int(t[2])
    except:
       dic["bin"] = 2

    return implBias(dic,vState)

#--------------------------------
##        ("BIAS",         execBias),     #
#  BIAS, <repeat> [,<bin>]
def execCropBias(t,vState):
    dic = {}
    dic["crop"]  = "yes"
    dic["type"]  = "Bias"
    dic["limit"] = "count"

    try:
       dic["repeat"] = int(t[1])
    except:
       dic["repeat"] = vState.repeat

    try:
       dic["bin"] = int(t[2])
    except:
       dic["bin"] = 2

    return implBias(dic,vState)

#--------------------------------
##        ("FLATS",        execFlats),    #
def execFlats(t,vState):
    dic = {}
    return implFlat(dic,vState)

#--------------------------------
##        ("WAITUNTIL",    execWaitUntil),#
#  WaitUntil,<hh:mm:ss>             #time in UTC
def execWaitUntil(t,vState):
   dic = {}
   dic["crop"]     = "no"
   dic["limit"]  = "time"
   dic["endTime"]  = t[1]       #fixed 2009.07.20 JU

   wantedTup = tuple(t[1].split(':'))    #end time wanted; split into components
   endTimeUtcSec = (int(wantedTup[0]) * 3600) + (int(wantedTup[1]) * 60)
   if len(wantedTup) == 3:
       endTimeUtcSec += int(wantedTup[2])
   Log2(4,"endTimeUtcSec = %d" %endTimeUtcSec)

   #if before start of UTC day AND WAIT TIME IS AFTER START OF UTC DAY, first wait for new day
   currentTup = time.gmtime(time.time())
   Log2(4, "currentTup: %s" % currentTup)
   while currentTup[3] > 18 and int(wantedTup[0]) < 18:
       Log2(2,"Waiting until start of next UTC day; current time %02d:%02d:%02d" % (currentTup[3],currentTup[4],currentTup[5]))
       time.sleep(30)
       currentTup = time.gmtime(time.time())


   #wait until we pass this time
   Log2(3,"We are in the right day, wait for time now")
   while True:
       currentTup = time.gmtime(time.time())
       nowSec = (currentTup[3] * 3600) + (currentTup[4] * 60) + currentTup[5]
       if nowSec >= endTimeUtcSec:
          Log2(3,"Reached time after waiting")
          Log2(4, "nowSec >= endTimeUtcSec")
          Log2(4,  "nowSec = %d" % nowSec)
          Log2(4,  "endTimeUtcSec = %d" % endTimeUtcSec)
          Log2(4,  "currentTup: %s" % currentTup)
          break

       Log2(1,"Still waiting; current time %02d:%02d:%02d, wait until %s" % (currentTup[3],currentTup[4],currentTup[5],t[1]))
       time.sleep(15)

   Log2(0,"End time reached; continue execution")


   return (0,)

#--------------------------------
def GetRequiredValue(t,index):
    try:
        ret = t[index]
        Log2(5,"GetRequiredValue: index=%d, value=%s" % (index,str(ret)))
        return ret
    except:
        #print "What did I get?"
        #print t
        Log2(0,"GetRequiredValue FAILED: index=%d" % (index))
        raise ArgumentError

def GetOptionalValue(t,index,default):
    try:
        ret = t[index]
        Log2(5,"GetOptionalValue: index=%d, value=%s" % (index,str(ret)))
        return ret
    except:
        Log2(5,"GetOptionalValue: index=%d, return default value=%s" % (index,str(default)))
        return default

def GetOptionalIntValue(t,index,default):
    try:
        ret = int(t[index])
        Log2(5,"GetOptionalIntValue: index=%d, value=%d" % (index,ret))
        return ret
    except:
        Log2(5,"GetOptionalIntValue: index=%d, return default value=%d" % (index,default))
        return default

def RestrictToWidePPSolve(value):
    if value == "both":
        return "wide"
    if value == "narrow":
        return "none"
    if value == "wide":
        return value
    return "none"

#-------------------------------------------------------------------------------------
def SetGuiderExclude(offset,t,vState): #if optional arguments provided, restrict region of guider field where guide star can be chosen from
    vState.ResetGuiderExclude()

    try:
        Log2(4,"Entry to SetGuiderExclude")
        top    = GetOptionalIntValue(t,offset,0)
        bottom = GetOptionalIntValue(t,offset+1,0)
        left   = GetOptionalIntValue(t,offset+2,0)
        right  = GetOptionalIntValue(t,offset+3,0)
        rflag  = GetOptionalValue(t,offset+4,"")
        Log2(5,"after getting values")

        if top == 0 and bottom == 0 and left == 0 and right == 0:
            Log2(4,"Nothing specified")
            return  #nothing specified, use MaxIm logic for guide star selection
                    #Note: 0 is not a valid value to use; too close to edge of field for guiding

        Log2(4,"top=%d, bottom=%d, left=%d, right=%d, rflag=%s" % (top,bottom,left,right,rflag))

        #something was specified, so use that value AND use 15 for any that weren't
        #(at least 1 of the values was specified or we wouldn't be here)
        if top < 32:
            top = 32
        if bottom < 32:
            bottom = 32
        if left < 32:
            left = 32
        if right < 32:
            right = 32
        Log2(5,"after fixing edges")

        vState.GuideAutoStarSelect    = False   #use next values
        vState.GuideExcludeTop        = top
        vState.GuideExcludeBottom     = bottom
        vState.GuideExcludeLeft       = left
        vState.GuideExcludeRight      = right
        Log2(5,"after storing values in vState variables")

        if len(rflag) > 0 and  rflag.upper()[0] == "R":
            vState.GuideExcludeReverse    = True  #if true, exclude middle of image and use edges
            Log2(4,"Use Reverse area")
        else:
            vState.GuideExcludeReverse    = False
            Log2(4,"Use Normal area")

    except:
        Log2(0,"*** Exception calling SetGuiderExclude; ignoring it !!!")

#-------------------------------------------------------------------------------------
#Wide_Cat_Count_Single,	   <targetID>[, <repeat>, <exp-secs>]	#like CatWide
#                              1           2           3         4
def exec_Wide_Cat_Count_Single(t,vState):
  try:
   #vState.ResetImagerOffset()   #forces positioning to center in guider
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Guider"			#Wide
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "count"			#Count
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,3))	  #different default for wide exposures
   dic["exp"]      = float(GetOptionalValue(t,3,100.))	#note shorter default for Wide images

   dic["PP-Solve"] =  RestrictToWidePPSolve(getPPSolve(vState))

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)   #error

#-------------------------------------------------------------------------------------
#Wide_Cat_EndTime_Single,	       <targetID>,<hh:mm:ss>[, <exp-secs>]	#like CatWideUntil/RunWideUntil
#                                          1           2           3
def exec_Wide_Cat_EndTime_Single(t,vState):
  try:
   #vState.ResetImagerOffset()   #forces positioning to center in guider

   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Guider"			#Wide
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["exp"]      = float(GetOptionalValue(t,3,100.))       #default for wide-field!

   dic["PP-Solve"] =  RestrictToWidePPSolve(getPPSolve(vState))

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)	#error


#-------------------------------------------------------------------------------------
#Wide_JNow_Count_Single,           <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>]
#                                   1     2       3           4           5
def exec_Wide_JNow_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Guider"			#Wide
   dic["epoch"]    = "JNow"                	#JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"			#Count
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,3))	#different default for wide exposures
   dic["exp"]      = float(GetOptionalValue(t,5,100.))

   dic["PP-Solve"] =  RestrictToWidePPSolve(getPPSolve(vState))

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)	#error

#-------------------------------------------------------------------------------------
#Wide_JNow_EndTime_Single,         <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>]
#                                   1     2       3           4           5
def exec_Wide_JNow_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Guider"			#Wide
   dic["epoch"]    = "JNow"                	#JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = int(GetRequiredValue(t,3))
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["exp"]      = float(GetOptionalValue(t,5,100.))       #default for wide-field!

   dic["PP-Solve"] =  RestrictToWidePPSolve(getPPSolve(vState))

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)	#error

#-------------------------------------------------------------------------------------
#Wide_J2000_Count_Single,	   <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>]	#like ExpWideJ2000
#                                   1     2       3           4           5
def exec_Wide_J2000_Count_Single(t,vState):
  try:
   #vState.ResetImagerOffset()   #forces positioning to center in guider
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Guider"			#Wide
   dic["epoch"]    = "J2000"                	#J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"			#Count
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,3))	#different default for wide exposures (should configure this)
   dic["exp"]      = float(GetOptionalValue(t,5,100.))

   dic["PP-Solve"] =  RestrictToWidePPSolve(getPPSolve(vState))

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)	#error

#-------------------------------------------------------------------------------------
#Wide_J2000_EndTime_Single,        <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>]
#                                   1     2       3           4           5
def exec_Wide_J2000_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Guider"			#Wide
   dic["epoch"]    = "J2000"                	#J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["exp"]      = float(GetOptionalValue(t,5,100.))

   dic["PP-Solve"] =  RestrictToWidePPSolve(getPPSolve(vState))

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)	#error

#-------------------------------------------------------------------------------------
#Wide_Stationary_Count_Single,     <targetID>[, <repeat>, <exp-secs>]
#                                      1           2           3
def exec_Wide_Stationary_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Guider"			#Wide
   dic["location"] = "stationary"		#Stationary
   dic["limit"]    = "count"			#Count
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,3))	#different default for wide exposures
   dic["exp"]      = float(GetOptionalValue(t,3,100.))

   dic["PP-Solve"] =  RestrictToWidePPSolve(getPPSolve(vState))

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)	#error

#-------------------------------------
#Wide_Stationary_EndTime_Single,   <targetID>,<hh:mm:ss>[, <exp-secs>]
#                                      1           2           3
def exec_Wide_Stationary_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Guider"			#Wide
   dic["location"] = "stationary"		#Stationary
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["exp"]      = float(GetOptionalValue(t,3,100.))

   dic["PP-Solve"] =  RestrictToWidePPSolve(getPPSolve(vState))

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)	#error

def GetOptionalSequence(t,index,defSeq):
    try:
        ret = pathSeq + t[index]
        Log2(5,"GetOptionalSequence: index=%d, value=%s" % (index,ret))
    except:
        ret = defSeq
        Log2(5,"GetOptionalSequence: index=%d, return default value=%s" % (index,ret))
    return ret

#-------------------------------------------------------------------------------------
#Narrow_Cat_Count_Sequence,	 <targetID>[, <repeat>, <seq-filename>]		#like CatSeq
#Narrow_Cat_Count_Sequence,  <targetID>[, <repeat>, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                1           2           3             4
def exec_Narrow_Cat_Count_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "yes"			#Sequence

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,vState.repeat))
   dic["seq"]      = GetOptionalSequence(t,3,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(4,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)	#error

#Cropped_Cat_Count_Sequence,<targetID>[, <repeat>, <seq-filename>]
#Cropped_Cat_Count_Sequence,<targetID>[, <repeat>, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                               1           2              3          4
def exec_Cropped_Cat_Count_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "yes"			#Sequence

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,vState.repeat))
   dic["seq"]      = GetOptionalSequence(t,3,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(4,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)	#error

#-------------------------------------------------------------------------------------
#Narrow_Cat_Count_Single,	      <targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B>]	#like CatExp
#Narrow_Cat_Count_Single,         <targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                      1           2           3       4        5           6+0     6+1        6+2      6+3       6+4
def exec_Narrow_Cat_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,vState.repeat))
   dic["exp"]      = float(GetOptionalValue(t,3,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,4,2)
   dic["filter"]   = GetOptionalValue(t,5,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_Cat_Count_Single,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Cropped_Cat_Count_Single,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                             1           2          3         4         5           6
def exec_Cropped_Cat_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,vState.repeat))
   dic["exp"]      = float(GetOptionalValue(t,3,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,4,2)
   dic["filter"]   = GetOptionalValue(t,5,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_Cat_EndTime_Sequence,   <targetID>,<hh:mm:ss>[, <seq-filename>]
#Narrow_Cat_EndTime_Sequence,   <targetID>,<hh:mm:ss>[, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                   1           2           3              4
def exec_Narrow_Cat_EndTime_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "yes"			#Sequence

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["seq"]      = GetOptionalSequence(t,3,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(4,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_Cat_EndTime_Sequence,<targetID>,<hh:mm:ss>[, <seq-filename>]
#Cropped_Cat_EndTime_Sequence,<targetID>,<hh:mm:ss>[, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                 1          2              3            4
def exec_Cropped_Cat_EndTime_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "yes"			#Sequence

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["seq"]      = GetOptionalSequence(t,3,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(4,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_Cat_EndTime_Single,       <targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B>]
#Narrow_Cat_EndTime_Single,       <targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                      1           2           3       4        5            6
def exec_Narrow_Cat_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["exp"]      = float(GetOptionalValue(t,3,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,4,2)
   dic["filter"]   = GetOptionalValue(t,5,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_Cat_EndTime_Single,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Cropped_Cat_EndTime_Single,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                              1           2            3         4         5          6
def exec_Cropped_Cat_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "cat"			#Cat
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["exp"]      = float(GetOptionalValue(t,3,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,4,2)
   dic["filter"]   = GetOptionalValue(t,5,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_JNow_Count_Sequence, <RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>]
#Narrow_JNow_Count_Sequence, <RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                             1     2       3           4           5             6
def exec_Narrow_JNow_Count_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "JNow"         #JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "yes"			#Sequence

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,vState.repeat))
   dic["seq"]      = GetOptionalSequence(t,5,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_JNow_Count_Sequence,<RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>]
#Cropped_JNow_Count_Sequence,<RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                              1    2       3            4            5           6
def exec_Cropped_JNow_Count_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "JNow"         #JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "yes"			#Sequence

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,vState.repeat))
   dic["seq"]      = GetOptionalSequence(t,5,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_JNow_Count_Single,	  <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Narrow_JNow_Count_Single,    <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                               1     2       3           4           5       6        7           8
def exec_Narrow_JNow_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "JNow"         #JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,vState.repeat))
   dic["exp"]      = float(GetOptionalValue(t,5,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,6,2)
   dic["filter"]   = GetOptionalValue(t,7,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(8,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_JNow_Count_Single,<RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Cropped_JNow_Count_Single,<RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                           1     2       3            4          5        6         7           8
def exec_Cropped_JNow_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "JNow"         #JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,vState.repeat))
   dic["exp"]      = float(GetOptionalValue(t,5,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,6,2)
   dic["filter"]   = GetOptionalValue(t,7,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(8,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_JNow_EndTime_Sequence,  <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <seq-filename>]
#Narrow_JNow_EndTime_Sequence,  <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                1     2       3           4        5                 6
def exec_Narrow_JNow_EndTime_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "JNow"         #JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "yes"			#Sequence

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["seq"]      = GetOptionalSequence(t,5,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_JNow_EndTime_Sequence,<RA>,<Dec>,<targetID>,<hh:mm:ss>[, <seq-filename>]
#Cropped_JNow_EndTime_Sequence,<RA>,<Dec>,<targetID>,<hh:mm:ss>[, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                               1     2       3           4              5           6
def exec_Cropped_JNow_EndTime_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "JNow"         #JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "yes"			#Sequence

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["seq"]      = GetOptionalSequence(t,5,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_JNow_EndTime_Single,      <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>]
#Narrow_JNow_EndTime_Single,      <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                   1     2       3           4           5       6        7            8
def exec_Narrow_JNow_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "JNow"         #JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["exp"]      = float(GetOptionalValue(t,5,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,6,2)
   dic["filter"]   = GetOptionalValue(t,7,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(8,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_JNow_EndTime_Single,<RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Cropped_JNow_EndTime_Single,<RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                              1    2       3           4            5        6         7           8
def exec_Cropped_JNow_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "JNow"         #JNow
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["exp"]      = float(GetOptionalValue(t,5,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,6,2)
   dic["filter"]   = GetOptionalValue(t,7,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(8,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_J2000_Count_Sequence,  <RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>]			#like SeqJ2000
#Narrow_J2000_Count_Sequence,  <RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                               1     2       3           4           5             6
def exec_Narrow_J2000_Count_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "J2000"        #J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "yes"			#Sequence

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,vState.repeat))
   dic["seq"]      = GetOptionalSequence(t,5,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_J2000_Count_Sequence,<RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>]
#Cropped_J2000_Count_Sequence,<RA>,<Dec>,<targetID>[, <repeat>, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                              1     2       3           4             5           6
def exec_Cropped_J2000_Count_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "J2000"        #J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "yes"			#Sequence

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,vState.repeat))
   dic["seq"]      = GetOptionalSequence(t,5,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_J2000_Count_Single,	  <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Narrow_J2000_Count_Single,   <RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                              1     2       3           4           5       6        7            8
def exec_Narrow_J2000_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "J2000"        #J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,vState.repeat))
   dic["exp"]      = float(GetOptionalValue(t,5,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,6,2)
   dic["filter"]   = GetOptionalValue(t,7,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(8,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_J2000_Count_Single,<RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Cropped_J2000_Count_Single,<RA>,<Dec>,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                            1     2       3           4           5        6         7          8
def exec_Cropped_J2000_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "J2000"        #J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["repeat"]   = int(GetOptionalValue(t,4,vState.repeat))
   dic["exp"]      = float(GetOptionalValue(t,5,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,6,2)
   dic["filter"]   = GetOptionalValue(t,7,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(8,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_J2000_EndTime_Sequence,	 <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <seq-filename>
#Narrow_J2000_EndTime_Sequence,  <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                 1     2       3           4           5              6
def exec_Narrow_J2000_EndTime_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "J2000"        #J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "yes"			#Sequence

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["seq"]      = GetOptionalSequence(t,5,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------
#Cropped_J2000_EndTime_Sequence,<RA>,<Dec>,<targetID>,<hh:mm:ss>[, <seq-filename>]
#Cropped_J2000_EndTime_Sequence,<RA>,<Dec>,<targetID>,<hh:mm:ss>,  <seq-filename>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                1     2       3          4              5           6
def exec_Cropped_J2000_EndTime_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "J2000"        #J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "yes"			#Sequence

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["seq"]      = GetOptionalSequence(t,5,vState.sequence)

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_J2000_EndTime_Single,     <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Narrow_J2000_EndTime_Single,     <RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                   1     2       3           4           5       6          7          8
def exec_Narrow_J2000_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "J2000"        #J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["exp"]      = float(GetOptionalValue(t,5,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,6,2)
   dic["filter"]   = GetOptionalValue(t,7,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(8,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_J2000_EndTime_Single,<RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Cropped_J2000_EndTime_Single,<RA>,<Dec>,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                              1     2       3          4             5        6         7          8
def exec_Cropped_J2000_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["epoch"]    = "J2000"        #J2000
   dic["location"] = "RA/Dec"
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["RA"]       = UTIL.HMSToHours(GetRequiredValue(t,1))
   dic["Dec"]      = UTIL.DMSToDegrees(GetRequiredValue(t,2))
   dic["ID"]       = GetRequiredValue(t,3)
   dic["endTime"]  = GetRequiredValue(t,4)
   dic["exp"]      = float(GetOptionalValue(t,5,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,6,2)
   dic["filter"]   = GetOptionalValue(t,7,'L')

   dic["guideExp"] = vState.guide_exp
   dic["PP-Solve"] = getPPSolve(vState)

   SetGuiderExclude(8,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_Stationary_Count_Sequence,  <targetID>[, <repeat>, <seq-filename>
#Narrow_Stationary_Count_Sequence,  <targetID>[, <repeat>, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                      1           2           3              4
def exec_Narrow_Stationary_Count_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "stationary"	#Stationary
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "yes"			#Sequence

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,vState.repeat))
   dic["seq"]      = GetOptionalSequence(t,3,vState.sequence)

   dic["guideExp"] = vState.guide_exp		#in case guider isn't running yet

   SetGuiderExclude(4,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_Stationary_Count_Sequence,<targetID>[, <repeat>, <seq-filename>]
#Cropped_Stationary_Count_Sequence,<targetID>[, <repeat>, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                      1           2             3           4
def exec_Cropped_Stationary_Count_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "stationary"	#Stationary
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "yes"			#Sequence

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,vState.repeat))
   dic["seq"]      = GetOptionalSequence(t,3,vState.sequence)

   dic["guideExp"] = vState.guide_exp		#in case guider isn't running yet

   SetGuiderExclude(4,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_Stationary_Count_Single,   <targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Narrow_Stationary_Count_Single,   <targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                      1           2           3         4        5          6
def exec_Narrow_Stationary_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "stationary"	#Stationary
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,vState.repeat))
   dic["exp"]      = float(GetOptionalValue(t,3,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,4,2)
   dic["filter"]   = GetOptionalValue(t,5,'L')

   dic["guideExp"] = vState.guide_exp		#in case guider isn't running yet

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_Stationary_Count_Single,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Cropped_Stationary_Count_Single,<targetID>[, <repeat>, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                    1            2         3         4         5          6
def exec_Cropped_Stationary_Count_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "stationary"	#Stationary
   dic["limit"]    = "count"		#Count
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["repeat"]   = int(GetOptionalValue(t,2,vState.repeat))
   dic["exp"]      = float(GetOptionalValue(t,3,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,4,2)
   dic["filter"]   = GetOptionalValue(t,5,'L')

   dic["guideExp"] = vState.guide_exp		#in case guider isn't running yet

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_Stationary_EndTime_Sequence,<targetID>,<hh:mm:ss>[, <seq-filename>]
#Narrow_Stationary_EndTime_Sequence,<targetID>,<hh:mm:ss>[, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                      1           2           3               4
#StationaryRunUntil	execStationaryRunUntil(t,vState):
def exec_Narrow_Stationary_EndTime_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "stationary"	#Stationary
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "yes"			#Sequence

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["seq"]      = GetOptionalSequence(t,3,vState.sequence)

   dic["guideExp"] = vState.guide_exp		#in case guider isn't running yet

   SetGuiderExclude(4,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_Stationary_EndTime_Sequence,<targetID>,<hh:mm:ss>[, <seq-filename>]
#Cropped_Stationary_EndTime_Sequence,<targetID>,<hh:mm:ss>[, <seq-filename>],<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                        1           2            3             4
def exec_Cropped_Stationary_EndTime_Sequence(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "stationary"	#Stationary
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "yes"			#Sequence

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["seq"]      = GetOptionalSequence(t,3,vState.sequence)

   dic["guideExp"] = vState.guide_exp		#in case guider isn't running yet

   SetGuiderExclude(4,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#-------------------------------------------------------------------------------------
#Narrow_Stationary_EndTime_Single,  <targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Narrow_Stationary_EndTime_Single,  <targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                      1           2           3         4         5           6
def exec_Narrow_Stationary_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "no"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "stationary"	#Stationary
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["exp"]      = float(GetOptionalValue(t,3,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,4,2)
   dic["filter"]   = GetOptionalValue(t,5,'L')

   dic["guideExp"] = vState.guide_exp		#in case guider isn't running yet

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)

#Cropped_Stationary_EndTime_Single,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>
#Cropped_Stationary_EndTime_Single,<targetID>,<hh:mm:ss>[, <exp-secs>, <bin>, <L/R/G/B/Ha>,<G-top>,<G-bottom>,<G-left>,<G-right>[,Reverse]]
#                                      1           2            3        4         5          6
def exec_Cropped_Stationary_EndTime_Single(t,vState):
  try:
   dic = {}
   dic["crop"]     = "yes"
   dic["type"]     = "light"
   dic["camera"]   = "Imager"		#Narrow
   dic["location"] = "stationary"	#Stationary
   dic["limit"]    = "time"			#EndTime
   dic["isSeq"]    = "no"			#Single

   dic["ID"]       = GetRequiredValue(t,1)
   dic["endTime"]  = GetRequiredValue(t,2)
   dic["exp"]      = float(GetOptionalValue(t,3,vState.exposure))
   dic["bin"]      = GetOptionalIntValue(t,4,2)
   dic["filter"]   = GetOptionalValue(t,5,'L')

   dic["guideExp"] = vState.guide_exp		#in case guider isn't running yet

   SetGuiderExclude(6,t,vState) #if optional arguments provided, restrict region of guider field where guide star can be chosen from

   return implExp(dic,vState)
  except ArgumentError:
   return (2,)


#--------------------------------------------------------------------------------------------------------
class cTarget:
    def __init__(self):
        self.name = ""
        self.listType = ""      #values:  'Survey','Mosaic','Deep','Default' (needed when a cTarget object returned as the next target, to see which list it came from)
        self.dRA = 0.

        self.bWide = False      #set from F:Size = 'W' wide
        self.bColor = False     #set from G:Type = 'C' LRGB color; this is ignored if bWide = True
        self.mosaicSize = ""    #set from H:Mosaic = 'MxN' ex '2x3' M=columns across, N=rows tall for mosaic; empty if not a mosaic target
        self.PPOvrd = ""        #set from I:PP Ovrd; 'Wide' = only PP solve wide; 'None' = no PP solve; empty = use current script setting
        self.PPRetry = -1       #set from J:PP Retry; max number of attempts to position exactly on target location to desired position; -1 = use current script setting
        self.L_exposure = 300   #set from K:L-Exp; exposure(secs) to use if Luminance-only image
        self.L_repeat = 12      #set from L:L-repeat; repeats of exposure if Luminance-only image
        self.priority = 0       #set from E:Priority, higher number is higher priority (1-9 or empty?)

    def setDetails(self,pName,pListType,pRA,pWide,pColor,pMosaicSize,pPPOvrd,pPPRetry,pExposure,pRepeat,pPriority):
        self.name = pName
        self.listType = pListType
        self.dRA = pRA
        self.bWide = pWide
        self.bColor = pColor
        self.mosaicSize = pMosaicSize     #only used if mosaic
        self.PPOvrd = pPPOvrd
        self.PPRetry = pPPRetry
        self.L_exposure = pExposure
        self.L_repeat = pRepeat
        try:
            self.priority = int(pPriority)
        except:
            self.priority = 0

    def dump(self):
        return  #disable for now
##        print "name",self.name
##        print "listType",self.listType
##        print "dRA",self.dRA
##        print "bWide",self.bWide
##        print "bColor",self.bColor
##        print "mosaicSize",self.mosaicSize
##        print "PPOvrd",self.PPOvrd
##        print "PPRetry",self.PPRetry
##        print "L_exposure",self.L_exposure
##        print "L_repeat",self.L_repeat

#--------------------------------------------------------------------------------------------------------
def CheckApproxHorizon(dTargetRA,vState):
   #compare target RA against approx horizon limits based on hour angle
   # return True if object above horizon, False if below horizon

   #Enhancement idea: use NOVAS PositionVector feature to convert a target's
   #  RA/Dec into alt/az coordinates, and then compare these directly to
   #  the local horizon map.

   #eastHoriz = -2.25     #HA increases to west, so this needs to be negative
   #westHoriz = 4.5
   eastHoriz = -6     #HA increases to west, so this needs to be negative
   westHoriz = 5

   HA = vState.MOUNT.SiderealTime - dTargetRA
   if HA > 12:
      HA -= 24
   elif HA < -12:
      HA += 24

   if HA < 0:
      #on east side of sky
      if HA < eastHoriz:
         return False #not visible
   #else on west side of the sky; compare to west horizon
   if HA > westHoriz:
         return False #not visible

   return True    #it is visible (more or less)

#--------------------------------------------------------------------------------------------------------
def PrepareTargetList(vState):
    print "PrepareTargetList"
    if not gSurveyCommandPresent:
        Log2(0,"Skip loading TargetList because no survey commands present")
        return

    Log2(0,"Entry to PrepareTargetList...")
    #read in the Ignore list first from file of RecentImaged (this only applies to Survey objects)
    try:
        #if file doesn't exist, that is fine
        g = open( RecentImaged, "r")
        for line in g:
            temp = tuple(line.split('#'))
            if( len(temp[0]) == 0 ):
                continue            #blank line
            objName = UTIL.TrimString(temp[0])
            if objName.endswith("\n"):
                objName = objName[:-1]
            #print "Loading to ignore:","'" + objName + "'"
            IgnoreList.append(objName)
        g.close()
    except:
        pass

    #print "Loading..."
    cnt = 0

    #********
    # Build 4 target lists:
    #   First priority: survey targets: objects that have not had an initial survey image taken
    #       yet; if spreadsheet column 18 (R:My Image) is empty AND this name does NOT appear
    #       in the RecentImaged list, then this object is added to the survey target list
    #   Second priority: mosaics: objects not in survey list, and which have column 21 (U:More)
    #       set to '1', and have column 7 (G:Type) start w/ letter M, then this object is
    #       added to the survey target list
    #   Third priority: deep images: objects not in survey or mosaic list, and which have
    #       column 21 (U:More) set to '1' and column 7 (G:Type) NOT start w/ letter M, then
    #       this object is added to the deep images list
    #   Default: targets of opportunity: objects not in any of the above 3 lists; this is in case
    #       there are not any objects available in any of the other lists, I don't want to waste
    #       the time, so just pick something and take a deep image of it.

    #count number of entries per hour of RA for each list
    surveyCounts = {}
    mosaicCounts = {}
    deepCounts   = {}
    defaultCounts = {}
    for i in range(24):     #init counts
        surveyCounts[i] = 0
        mosaicCounts[i] = 0
        deepCounts[i] = 0
        defaultCounts[i] = 0

    #read target file, save entries marked 'interesting'
    nice = 0
    n = open( MasterList, "r")
    first = True

    colRA =      ord('B')-ord('A')    #1  #B: 2-1=  1
    colDec =     ord('C')-ord('A')    #2  #C: 3-1=  2
    colPriority =ord('E')-ord('A')    #5  #E: 5-1=  4   Priority for deep image targets
    colWanted =  ord('F')-ord('A')    #5  #F: 6-1=  5   Wanted, float, number of hours desired for this target
    colSize =    ord('G')-ord('A')    #6  #G: 7-1=  6   Size, string, 'W'=wide field, empty=narrow field
    colType =    ord('H')-ord('A')    #7  #H: 8-1=  7   Type, string, 'L'=luminance only, 'C'=color LRGB (cannot be 'W')
    colMosaic =  ord('I')-ord('A')    #8  #I: 9-1=  8   mosaic dimensions: MxN  (M columns, N rows); empty if not mosaic
    colPPOvrd =  ord('J')-ord('A')    #9  #J:10-1=  9   Pinpoint override: 'Wide' for only wide PP solve, 'None' for no PP solve, else use current script setting
    colPPRetry = ord('K')-ord('A')    #10 #K:11-1=  10  Pinpoint retries to achieve poining precision; empty = use 2 as default retries (both cameras)
    colLExp =    ord('L')-ord('A')    #11 #L:12-1=  11  L-Exp: luminance-only override exposure
    colLRepeat = ord('M')-ord('A')    #12 #M:13-1=  12
    colTaken =   ord('N')-ord('A')    #13 #N:14-1=  13  Taken, float, number of hours exposed on this target so far
    colMyImage = ord('W')-ord('A')    #22 #W:23-1=  22  My Image, string, blank here if no survey image recorded yet; THIS CONROLS WHETHER TARGET IMAGED FOR SURVEY
    colMoreToDo= ord('Z')-ord('A')    #25 #Z:26-1=  25  int: 1=this target needs more deep exposures, 0=none
    colEND =     ord('A')-ord('A')+26 #26 #AA:27-1= 26  END marker (insures line is parsed correctly)

    for line in n:
        if first:   #skip the title line
            first = False
            continue
        temp = tuple(line.split(','))
        if( len(temp[0]) == 0 ):
            #print "skip blank line:",line
            continue            #blank line
##        if len(temp) <= 6:
##            continue            #short line
##        interesting = UTIL.TrimString(temp[6])   #I mark this column for objects that deserve deeper imaging

        if len(temp) <= colEND:     #28:
            continue            #short line
        endmark = UTIL.TrimString(temp[colEND])     # Z:End (was 21 V:End)
        if endmark[0:3] != "END":
            print "!!! this target line does not end with the word 'END'"
            print line
            print "above is the problem, len = %d" % len(temp)
            print "I think this line ends with <" + endmark + ">"
            raise ValidationError,'Halting program'

        try:
            X = 0
            try:
                cWanted = float(UTIL.TrimString(temp[colWanted]))   # E:Wanted, float, number of hours desired for this target (is this needed?)
            except:
                cWanted = 0.

            try:
                cPriority = int(UTIL.TrimString(temp[colPriority]))
            except:
                cPriority = 0

            X = 1
            try:
                cTaken = float(UTIL.TrimString(temp[colTaken]))    # M:Taken, float, number of hours exposed on this target so far (is this needed?)
            except:
                cTaken = 0.
            X = 2

            cSize  = (UTIL.TrimString(temp[colSize])).upper()           # F:Size, string, 'W'=wide field, empty=narrow field
            X = 3
            cType  = (UTIL.TrimString(temp[colType])).upper()           # G:Type, string, 'L'=luminance only, 'C'=color LRGB (cannot be 'W')
            X = 4

            cMosaic  = (UTIL.TrimString(temp[colMosaic])).upper()         # H:mosaic dimensions: MxN  (M columns, N rows); empty if not mosaic
            X = 5
            if( len(cMosaic) > 0):
                #validate the data before saving it:
                X = 6
                temp1 = cMosaic.upper()
                X = 7
                temp3 = tuple(temp1.split('X'))
                X = 8
                if len(temp3) != 2:
                    Log2(0,"Error: wrong number of components for Mosaic")
                    X = 9
                    raise
                try:
                    X = 10
                    columns = int(temp3[0])
                    X = 11
                    rows    = int(temp3[1])
                    X = 12
                except:
                    Log2(0,"Error: unable to convert mosaic sizes into numbers")
                    X = 13
                    raise
                if columns < 1 or rows < 1 or columns >= 100 or rows >= 100:
                    #upper limit is arbitrary
                    Log2(0,"Error: unreasonable value for mosaic dimension")
                    X = 14
                    raise

            X = 15
            cPPOverride = (UTIL.TrimString(temp[colPPOvrd])).upper()      # I:Pinpoint override: 'Wide' for only wide PP solve, 'None' for no PP solve, else use current script setting
            X = 16

            X = 17
            try:
                cPPRetry = int(UTIL.TrimString(temp[colPPRetry]))          # J:Pinpoint retries to achieve poining precision; empty = use 2 as default retries (both cameras)
            except:
                cPPRetry = 2

            X = 19
            try:
                cL_exposure = int(UTIL.TrimString(temp[colLExp]))    #K:L-Exp: luminance-only override exposure
                if cL_exposure <= 1:
                    cL_exposure = 1
            except:
                if cSize == 'W':
                    cL_exposure = 100
                else:
                    cL_exposure = 300       #IDEA: change this to the vState default exposure?
            X = 20
            try:
                cL_repeat = int(UTIL.TrimString(temp[colLRepeat]))
                if cL_repeat <= 1:
                    cL_repeat = 1
            except:
                cL_repeat = 12
            X = 21

            cSurvey = UTIL.TrimString(temp[colMyImage])         # V:My Image, string, blank here if no survey image recorded yet; THIS CONROLS WHETHER TARGET IMAGED FOR SURVEY

            X = 22
            # Y:More, '1'=need more detailed images of this object; THIS CONTROLS WHETHER TARGET IMAGED FOR MOSAIC OR DEEP IMAGE
            #Note: this column in spreadsheet is automatically set by comparing the 'needed' vs 'taken' numbers.
            cMore   = UTIL.TrimString(temp[colMoreToDo])

            X = 23
        except:
            print "This line has a problem reading the expected fields, trace = %d" % (X)
            print
            print line
            print
            print "^ above text is the problem ^"
            raise ValidationError,'Halting program'

##        #Any character in column 'H' indicates the field is a Widefield instead of narrow
##        widefield = len(UTIL.TrimString(temp[7]))      #column 'H', will be 'Y' for widefield

        objName = UTIL.TrimString(temp[0])
        sRA     = temp[colRA]
        dRA     = UTIL.HMSToHours(sRA)

        sDec    = temp[colDec]
        dDec    = UTIL.DMSToDegrees(sDec)

        cleanTargetName = catalogID_cleaner(objName)
        MasterCoords[cleanTargetName] = (dRA,dDec)  #keep copy of all coords from spreadsheet, in case something is not in MiniSAC catalog

        bWide = False
        if len(cSize) > 0 and (cSize[0] == 'W' or cSize[0] == 'w'):
            bWide = True

        bSurvey = False     #assume do not need survey image
        if len(cSurvey) == 0 and IgnoreList.count(objName) == 0:    #This is where I check to see if I have recently imaged this target but not recorded it yet
            bSurvey = True      #need survey image ONLY IF no image recorded AND no recent image taken

        bMosaic = False
        bDeep = False
        if cMore == '1':
            #this object will be on the Mosaic or Deep list
            if len(cMosaic) > 0:
                #validate the mosaic data before saving it and cType[0] == 'M':
                temp = cMosaic.upper()
                temp2 = tuple(temp.split('X'))
                if len(temp2) != 2:
                    raise
                try:
                    columns = int(temp2[0])
                    rows    = int(temp2[1])
                except:
                    raise
                if columns < 1 or rows < 1 or columns > 100 or rows > 100:
                    #upper limit is arbitrary
                    raise

#                temp2 = temp.tuple
                bMosaic = True
            else:
                bDeep = True

        bColor = False  #does not apply to Mosaics, which are always color if narrow, monochrome for wide
        #default value is for Luminance only image
        if len(cType) > 0 and (cType[0] == 'C' or cType[0] == 'c'):
            bColor = True       #note: this is ignored for Wide field targets

        target = cTarget()

        #(pName,pListType,pRA,pWide,pColor, pMosaicSize,pPPOvrd,pPPRetry,pExposure,pRepeat):
        if bSurvey:
            target.setDetails(objName,"Survey",dRA,bWide,bColor,cMosaic,cPPOverride,cPPRetry,cL_exposure,cL_repeat,cPriority)
            SurveyList.append(target)
            surveyCounts[int(dRA)] += 1
        elif bMosaic:
            target.setDetails(objName,"Mosaic",dRA,bWide,bColor,cMosaic,cPPOverride,cPPRetry,cL_exposure,cL_repeat,cPriority)
            target.dump()
            MosaicList.append(target)
            mosaicCounts[int(dRA)] += 1         #maybe break down to wide/narrow
        elif bDeep:
            target.setDetails(objName,"Deep",dRA,bWide,bColor,cMosaic,cPPOverride,cPPRetry,cL_exposure,cL_repeat,cPriority)
            DeepList.append(target)
            deepCounts[int(dRA)] += 1           #maybe break down to wide/color/Luminance
        else:
            target.setDetails(objName,"Default",dRA,bWide,bColor,cMosaic,cPPOverride,cPPRetry,cL_exposure,cL_repeat,cPriority)
            DefaultList.append(target)
            defaultCounts[int(dRA)] += 1

    n.close()

    #TargetListReversed = TargetList  <- this doesn't make a copy!
    Log2(1, "Total items in survey list: %d" % len(SurveyList))
    Log2(1, "Total items in mosaic list: %d" % len(MosaicList))
    Log2(1, "Total items in deep list: %d" % len(DeepList))
    Log2(1, "Total items in default list: %d" % len(DefaultList))
    Log2(1,"")
    Log2(1,"RA   Survey    Mosaic    Deep    Default   (Number of targets per hour RA)")
    #RA   Survey    Mosaic    Deep    Default
    #00    9999      9999     9999     9999
    for i in range(24):
        Log2(1,"%02d    %4d      %4d     %4d     %4d" % (i,surveyCounts[i],mosaicCounts[i],deepCounts[i],defaultCounts[i]))

#------------------------------------------------------------------------------------------------
def GetNextTargetFromList(vState,TargetList,listname):
    #From the specified list, find the next available target using the following plan:
    # 1. Pick RA 1 hour east of meridian
    # 2. Search List for next object with RA greater than this value
    #    If found, check against horizon to see if visible; if visible, return this object after removing from list
    # 3. If reached end of list without finding object, search list starting from 0h (wrapped)
    #    If found, check against horizon to see if visible; if visible, return this object after removing from list
    #return cTarget object, or None if no target found

    if len(TargetList) == 0:
        Log2(1,"Empty target list: %s" % listname)
        return None

    #Find the highest priority number in the TargetList, so we know where to start searching from
    maxPriority = 0
    for obj in TargetList:
        if obj.priority > maxPriority:
            maxPriority = obj.priority

    #loop over in order of decreasing priority, so that the highest priority CURRENTLY
    # VISIBLE in the sky is chosen, and the object with that priority that is closest
    # to the meridian is chosen.
    for desiredPriority in range(maxPriority,-1,-1):
     Log2(3,"Checking for targets of priority = %d" % desiredPriority)
     retries = 6   #try looking from initial RA of sidereal time + 1 west to Sidereal time - 4
     offset = 1    #initial RA is 1 hour east of meridian; moves westward (more negative) for additional attempts

     if listname == "MosaicList":
        retries = 3 #limit closer to meridian when choosing from Mosaic list; we want as high quality as possible

     #Loop over starting RA (move starting position farther west if current test doesn't succeed)
     while retries > 0:
       desiredRA = vState.MOUNT.SiderealTime + offset
       if desiredRA >= 24:
          desiredRA -= 24
       elif desiredRA < 0:
          desiredRA += 24
       HA = -offset
       Log2(3,"List:%s  Sid.Time = %s  HA = %d  RA = %s" % (listname,vState.UTIL.HoursToHMS(vState.MOUNT.SiderealTime,":",":","",1),HA,vState.UTIL.HoursToHMS(desiredRA,":",":","",1)))

       #look for target with RA greather than desired RA (eastward of desired RA)
       bBelowHorizon = False
       for obj in TargetList:
          if obj.priority < desiredPriority:
              continue  #only consider objects at least of desired priority
          if obj.dRA > desiredRA:
              if listname == "MosaicList":
                      Log2(3,"Mosaic ck: name:%s  RA:%5.2f" % (obj.name,obj.dRA))
              if CheckApproxHorizon(obj.dRA,vState):
                  #use this entry
                  #(ONLY REMOVE IT FROM LIST IF IT IS *NOT* A MOSAIC)
                  #(we want to keep mosaic targets in the list and repeat them
                  # as long as they are available during the night)
                  myObj = obj   #preserve it
                  if listname != "MosaicList":
                      Log2(4,"TargetList cnt before remove: %d" % len(TargetList))
                      Log2(4,"Removing item number: %d" % TargetList.index(obj))
                      Log2(4,"Removing item Name: %s  RA=%f" % (obj.name,obj.dRA))
                      TargetList.remove(obj)
                      Log2(4,"TargetList cnt AFTER remove: %d" % len(TargetList))
                      Log2(1,"**Next target: %s from list: %s; RA: %s" % (myObj.name,listname,UTIL.HoursToHMS(obj.dRA,":",":","",1)))
                  myObj.dump()
                  return myObj
              else:
                  bBelowHorizon = True
                  if listname == "MosaicList":
                          Log2(3,"Mosaic target below east horizon" )
                  break
          else:
            if listname == "MosaicList":
                Log2(0,"Mosaic target too far west: %s  RA:%5.2f" % (obj.name,obj.dRA))

       if not bBelowHorizon:
           #we reached the end of the list, and we were still above horizon;
           # wrap back to start of the list and see if the 1st object in the list
           # is above the horizon (remember: we remove items we previously used,
           # so only unused items are in the list).  If the 1st item in the list
           # THAT IS OF SUFFICIENT PRIORITY is above the horizon, use it.
           for obj in TargetList:
              if obj.priority < desiredPriority:
                  continue  #only consider objects at least of desired priority

              #obj = TargetList[0]
              if listname == "MosaicList":
               Log2(3,"Mosaic check wrap around: %s RA:%5.2f" % (obj.name,obj.dRA))
              if CheckApproxHorizon(obj.dRA,vState):
                  #use it
                  myObj = obj   #preserve it
                  Log2(4,"TargetList cnt before remove: %d" % len(TargetList))
                  Log2(4,"Removing item number: %d" % TargetList.index(obj))
                  Log2(4,"Removing item Name: %s  RA=%f" % (obj.name,obj.dRA))
                  TargetList.remove(obj)
                  Log2(4,"TargetList cnt AFTER remove: %d" % len(TargetList))
                  Log2(1,"**Next target: %s from list: %s; RA: %s" % (myObj.name,listname,UTIL.HoursToHMS(obj.dRA,":",":","",1)))
                  obj.dump()
                  return myObj
              else:
               if listname == "MosaicList":
                  Log2(0,"Mosaic target below horizon: %s  RA:%5.2f" % (obj.name,obj.dRA))
              break  #only need to check the 1st (farthest west) item in the list here

       #there are no targets in the list between current desiredRA and eastern horizon;
       #so try moving the desiredRA westward and try again
       offset -= 1   #yes, this goes below zero on purpose to go to western side of sky
       retries -= 1
       #loop back and try checking again

    #fell out of loop trying different starting positions; there is nothing in this
    # list that we can target
    Log2(1,"No targets available in list: %s" % listname)
    return None


#------------------------------------------------------------------------------------------------
def GetNextTarget(vState):
    #Pick the next available (visible) target for survey (this will be sidereal time +- )
    #return cTarget object

    global gAutoUntilType   #which category the current target is chosen from  [ONLY USED FOR STATUS WINDOW]

    #check the lists in priority order; return target from highest priority list that has something available
    obj = GetNextTargetFromList(vState,SurveyList,"SurveyList")
    if obj != None :
        gAutoUntilType = "Survey"
        return obj

    obj = GetNextTargetFromList(vState,MosaicList,"MosaicList")
    if obj != None :
        gAutoUntilType = "Mosaic"
        return obj

    obj = GetNextTargetFromList(vState,DeepList,"DeepList")
    if obj != None :
        gAutoUntilType = "Deep"
        return obj

    obj = GetNextTargetFromList(vState,DefaultList,"DefaultList")
    if obj != None :
        gAutoUntilType = "Default"
        return obj

    #the only way to get here is if the target source file J-Targets3.csv has been erased!
    raise ValidationError,'Did not find any targets in ANY list!!!'

#--------------------------------------------------------------------------------------------------------
global preservePPState
preservePPState = [PP_State(),PP_State()]

def PushAndSetPinpointControl(vState,override,retries):
    #save current PP values and possibly override for this object
    #Note:  0=imager, 1=guider
    for i in range(0,1):
        global preservePPState
        preservePPState[i] = vState.ppState[i]

##    class PP_State:
##        def __init__(self):
##            self.active          = 0
##            self.exposure        = 30
##            self.binning         = 1
##            self.exp_increment   = 2
##            self.retry           = 2
##            self.precision       = 0       #how close in arcminutes to desired location, 0=ignore
##            self.require_solve   = 0   <-- IF ACTIVE, ASSUME SOLVE IS REQUIRED FOR IT

    if( override.upper() == "NONE"):
        vState.ppState[0].active = False
        vState.ppState[1].active = False

    if override.upper() == "WIDE":
        vState.ppState[0].active = False
        vState.ppState[1].active = True
        vState.ppState[1].require_solve = True  #DO I WANT THIS?? Probably do, otherwise mosaic tiles probably will not overlap and worthless result.
        vState.ppState[1].precision = 0.5         #value usually 2 arcmin; make more precise when using wide-only PP solve

    if override.upper() == "BOTH":
        vState.ppState[0].active = True
        vState.ppState[1].active = True
        vState.ppState[0].require_solve = True
        vState.ppState[1].require_solve = True
        vState.ppState[0].precision = 0.5         #value usually 1 arcmin; make more precise when using wide-only PP solve
            #Note: do not need to increase Wide precision also since only the Narrow precision will determine final image placement.

    if retries >= 1:
        vState.ppState[0].retry = retries
        vState.ppState[1].retry = retries

def PopPinpointControl(vState):
    #restore previously saved PP values
    for i in range(0,1):
        global preservePPState
        vState.ppState[i] = preservePPState[i]

#--------------------------------------------------------------------------------------------------------
#  AutoUntil, <hh:mm:ss>
##
def execAutoUntil(t,vState):
    Log2(0, "** AutoUntil: survey of automatically selected objects")

    tup = TestSkipAhead(vState)
    if tup[0] != 0:
        return (1,)

    Log2(1,"Preparing target list...")

    global gbAutoUntil
    gbAutoUntil = True

    #calc time we want to stop (if not specified, use solar altitude)
    if len(t) > 1:
        timeStr  = t[1].strip()   #value is UT string: hh:mm or hh:mm:ss (seconds are ignored)
        tup = tuple( timeStr.split(':') )
        nHour = int( tup[0] )
        nMin  = int( tup[1] )
        minutesPast = (nHour * 60) + nMin   #this is the # of minutes past GMT midnight when we want to stop
        bUseEndTime = True
        Log2(1,"Note: this step runs until %2d:%02d UT" % (nHour,nMin))
    else:
        bUseEndTime = False
        Log2(1,"Note: this step runs until dawn twilight!")

    surveyCnt = 0  #how many get done

    #Focus is now handled as part of positioning on a new target in implExp_InitialMovement

    while True:
        #check current time against end time (if using time limit)
        gmt = time.gmtime()     #this returns current time in GMT tuple
        gHour = gmt[3]
        gMin  = gmt[4]
        gMinutesPast = (gHour * 60) + gMin  #current number of minutes past midnight GMT

        if bUseEndTime:
            if gMinutesPast >= minutesPast:
                Log2(0,"***End time reached: STOPPING. Time to stop, arg = %s, GMT now = %02d:%02d" % (t[1],gHour,gMin))
                Log2(0,"Survey targets completed: %d" % surveyCnt )
                #global gbAutoUntil
                gbAutoUntil = False
                return (0,)
            Log2(4,"End time not reached yet: not stopping.")
            Log2(4,"Time to stop = " + timeStr + ", current time = " + str(gHour) + ":" + str(gMin) + " GMT")
        else:
            Log2(4,"No stop time specified, running until dawn.")

        #check sun altitude regardless of end time (if specified)
        tup1 = time.gmtime()
        mYear  = tup1[0]
        mMonth = tup1[1]
        mDay   = tup1[2]
        utc    = float(tup1[3]) + (float(tup1[4])/60.) + (float(tup1[5])/3600.)
        alt = CalcSolarAlt(mYear,mMonth,mDay,utc,myLongitude,myLatitude)
        if utc > 6 and utc < 18:
            #exclude testing in evening sky, only check if morning
            if alt > -9:    #do not expect to get decent images if sun this high
                Log2(0,"$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
                Log2(0,"$ Stop because of high sun altitude! alt = %5.2f" % (alt))
                Log2(0,"$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
                Log2(0,"Survey targets completed: %d" % surveyCnt )
                #global gbAutoUntil
                gbAutoUntil = False
                return (0,)     #too late in morning (or too early in evening, and should not have started yet!)
        Log2(4,"Current solar altitude = %5.2f" % alt)

        #Should we refocus yet (maybe every 2 hours)
        #This is now handled as part of positioning on a new target in implExp_InitialMovement

        #find out what the next object is:
        obj = GetNextTarget(vState)

        Log2(0," " )
        if obj.listType == "Survey":        #------------------------------------------------------------
            #Settings:
            # obj.name
            # obj.dRA           not used here; only needed to pick target
            # obj.bWide
            # obj.bColor        does not apply to Survey
            # obj.mosaicSize    does not apply to Survey
            # obj.PPOvrd
            # obj.PPRetry
            # obj.L_exposure
            # obj.L_repeat      does not apply to Survey

            #   format dic entries for Imager single exposure
            dic = {}
            dic["crop"]     = "no"
            dic["location"]   = "cat"
            dic["ID"]         = obj.name
            if obj.bWide:
                Log2(0,"** Survey target (Wide): " + obj.name)
                dic["camera"] = "Guider"
            else:
                Log2(0,"** Survey target: " + obj.name)
                dic["camera"] = "Imager"
                dic["guideExp"]   = vState.guide_exp
                dic["guideStart"] = 1.0

            dic["isSeq"]      = "no"        #all survey images are simple 'L' exposure, not sequence
            PushAndSetPinpointControl(vState, obj.PPOvrd, obj.PPRetry)
            dic["PP-Solve"]   =  getPPSolve(vState) #this doesn't do anything
            dic["limit"]      = "count"
            dic["type"]       = "light"
            dic["filter"]     = 'L'
            dic["bin"]        = 2
            dic["exp"] = obj.L_exposure     #vState.exposure
            dic["repeat"] = 1   #always use 1 for survey image; do NOT use global default for survey targets
            # NOTE!!! The settings for Mosaic, L_repeat do not apply to survey images.
            implExp(dic,vState)   #take survey exposure of object
            PopPinpointControl(vState)


        elif obj.listType == "Mosaic":        #------------------------------------------------------------
            #Settings:
            # obj.name
            # obj.dRA           not used here; only needed to pick target
            # obj.bWide         T/F
            # obj.bColor        T/F
            # obj.mosaicSize    MxN
            # obj.PPOvrd
            # obj.PPRetry
            # obj.L_exposure
            # obj.L_repeat

            #bWide = True if this is wide field mosaic, else narrow field
            #NOTE: the values below are hard-coded for my cameras
            if obj.bWide:
                #42 x 31.5 arcmin  wide field camera
                height = 28
                width = 38
            else:
                #9.3 x 6.2 arcmin  narrow field camera
                height = 5      #was 6 but sometimes didn't overlap
                width = 9

            # mosaicSize = "MxN" where M is columns across, N is rows vertically
            temp = obj.mosaicSize.upper()
            temp2 = tuple(temp.split('X'))  #data was previously validated, so should not need to check here
            columns = int(temp2[0])
            rows    = int(temp2[1])

            #The call below finds the most recent tile number previously taken for this target
            # and returns coordinates for the next tile number.  When the max tile number is
            # reached (=columns*rows) it wraps around to 1. There is no limit on how often
            # this is done.
            tileRA,tileDec,tileStr = CalcMosaicCoords(obj.name,columns,rows,width,height)
            #Note: tileStr = string designating which piece of mosaic being done here, ex: "_1,2_" (row 1, column 2)

            dic = {}
            dic["crop"]     = "no"
            dic["location"] = "RA/Dec"
            dic["limit"]    = "count"
            dic["type"]     = "light"
            dic["RA"]       = tileRA
            dic["Dec"]      = tileDec
            dic["ID"]       = obj.name + tileStr      #make the name of each tile unique
            dic["epoch"]    = "J2000"
            PushAndSetPinpointControl(vState, obj.PPOvrd, obj.PPRetry)
            dic["PP-Solve"]   =  getPPSolve(vState) #this doesn't do anything

            #Lexposure,Lrepeat = ParseSpecSettings(obj.extra)    #returns 300,12 if no Spec settings to default to 1 hour of exposures

            if obj.bWide:
                Log2(0,"** Mosaic target (Wide): %s  (component %s)" % (obj.name,tileStr))
                dic["camera"] = "Guider"
                dic["isSeq"]  = "no"
                dic["filter"] = 'L'
                dic["bin"]    = 1
                dic["exp"]    = obj.L_exposure
                dic["repeat"] = obj.L_repeat
            else:
                Log2(0,"** Mosaic target: %s  (component %s)" % (obj.name,tileStr))
                dic["camera"] = "Imager"
                dic["guideExp"]   = vState.guide_exp        #only used for imager exposures
                dic["guideStart"] = 1.0
                if obj.bColor:
                    Log2(0,"** %s target (LRGB color): %s" % (obj.listType,obj.name))
                    dic["isSeq"]  = "yes"
                    dic["seq"]    = vState.sequence
                    dic["repeat"] = 2   #this makes default sequence run ~1 hour
                else:
                    Log2(0,"** %s target (L-only): %s" % (obj.listType,obj.name))
                    dic["isSeq"]  = "no"
                    dic["filter"] = 'L'
                    dic["bin"]    = 2
                    dic["exp"]    = obj.L_exposure
                    dic["repeat"] = obj.L_repeat

            Log2(1,"Mosaic coordinates: RA:%s  Dec:%s (J2000)" % (vState.UTIL.HoursToHMS(tileRA,":",":","",1),DegreesToDMS(tileDec)))
            implExp(dic,vState) #take images of one tile for mosaic of this target
            PopPinpointControl(vState)


        elif obj.listType == "Deep" or obj.listType == "Default":  #----------------------------------------
            #Settings:
            # obj.name
            # obj.dRA           not used here; only needed to pick target
            # obj.bWide         T/F
            # obj.bColor        T/F
            # obj.mosaicSize    MxN
            # obj.PPOvrd
            # obj.PPRetry
            # obj.L_exposure
            # obj.L_repeat

            dic = {}
            dic["crop"]     = "no"
            dic["location"]   = "cat"
            dic["ID"]         = obj.name
            PushAndSetPinpointControl(vState, obj.PPOvrd, obj.PPRetry)
            dic["PP-Solve"]   =  getPPSolve(vState) #this doesn't do anything
            dic["limit"]      = "count"
            dic["type"]       = "light"

            #Lexposure,Lrepeat = ParseSpecSettings(obj.extra)    #returns 300,12 if no Spec settings

            if obj.listType == "Default":       #we don't expect this to happen very often, so show when it does
                Log2(0,"----------------------------------------")
                Log2(0,"|  Resorted to using Default target!!! |")
                Log2(0,"----------------------------------------")

            if obj.bWide:
                Log2(0,"** %s target (Wide): %s" % (obj.listType,obj.name))
                dic["camera"] = "Guider"
                dic["isSeq"]  = "no"
                dic["filter"] = 'L'
                dic["bin"]    = 1
                dic["exp"]    = obj.L_exposure
                dic["repeat"] = obj.L_repeat
            else:
                dic["camera"] = "Imager"
                dic["guideExp"]   = vState.guide_exp        #only used for imager exposures
                dic["guideStart"] = 1.0
                if obj.bColor:
                    Log2(0,"** %s target (LRGB color): %s" % (obj.listType,obj.name))
                    dic["isSeq"]  = "yes"
                    dic["seq"]    = vState.sequence
                    dic["repeat"] = 2   #this makes default sequence run ~1 hour
                else:
                    Log2(0,"** %s target (L-only): %s" % (obj.listType,obj.name))
                    dic["isSeq"]  = "no"
                    dic["filter"] = 'L'
                    dic["bin"]    = 2
                    dic["exp"]    = obj.L_exposure
                    dic["repeat"] = obj.L_repeat

            implExp(dic,vState)   #take multiple exposures of this object
            PopPinpointControl(vState)


        else:                                                           #------------------------
            Log2(0,"@@ I received invalid listType = %s" % obj.listType)
            raise ValidationError,'Invalid list type returned!!!'

    #Note: loop continues until specified time, or dawn twilight

#----------------------------------------------------------------------------
#Return coords for center of "next" tile in mosaic of the target
def CalcMosaicCoords(target,columns,rows,width,height):
    # target = catalog name of base object for the mosaic
    # columns = number of tiles across (in RA) for the full mosaic
    # rows    = number of tiles vertically (in Dec) for the full mosaic
    # width = arcminute width for one tile
    # height = arcminute height for one time
    #return tuple:  (decimalRAJ2000, decimalDecJ2000, tilenamestring)

    Log2(6,"CalcMosaicCoords: target=%s columns=%d rows=%d width=%5.2f height=%5.2f" % (target,columns,rows,width,height))

    #Look in mosaic tracking file for this target, we take the tiles in order;
    # this call also increments the tile value in that tracking file for next time.
    nextTile = NextMosaicTile(target,columns*rows)

    #look up catalog coords of name
    pos = LookupObject( target )      #this returns a Position object
    if not pos.isValid:
        raise SoundAlarmError,'Unable to get position for this target'

    RABase = pos.dRA_J2000()          #(I could use JNow here instead for different return epoch)
    DecBase = pos.dDec_J2000()
    Log2(6,"baseCoords = %s" % (pos.dump3()))

    #NOTE: the width, height values should be slightly smaller than camera FOV
    #      to allow overlap for assembling the mosaic later.
    # tile = number from 1..(colums*rows) for which tile to calculate;
    #        tile numbering goes starts from lowest RA,Dec and increases
    #        first in RA, and then in Dec. For a 4x3 mosaic, the tiles
    #        would be:
    #   <- E    /\ N
    #       12 11 10  9
    #        8  7  6  5
    #        4  3  2  1

    y = ((nextTile-1) // columns) + 1     # vert coord (the row number); value will be 1..columns
    x = ((nextTile-1) % columns)+1        #hozontal coord (the column number); value will be 1..rows
    #Note that I use 'columns' for both of the above. That is correct. Since we
    #increment across first, and count rows from the first row, it doesn't really
    #matter here how high the mosaic is. (The mosaic height only is used
    #when calculating the initial offset from the center of the mosaic to tile #1.)
    Log2(6,"Tile coordinate: x=%d y=%d" % (x,y))

    #Convert tile width into Hours of RA, and height into Degrees of Dec.
    #  Important: we DIVIDE width hours by the cosine of the Dec; we want to INCREASE
    #  the time increment as we get farther north because a fixed field width of the sky
    #  spans more RA at a higher declination.
    rowInc = (width/60.)*(24./360.) / cosd(DecBase)    #width of field in HOURS, applied to RA
    colInc = height / 60.  #height of field in DEGREES, applied to Dec
    Log2(6,"Tile width=%9.6f hours   height=%9.6f degrees" % (rowInc,colInc))
    Log2(6,"Tile width=%9s hours   height=%9s degrees" % (UTIL.HoursToHMS(rowInc,":",":","",1),DegreesToDMS(colInc)))

    #Calculate offset from center of mosaic to center of tile #1
    if columns%2 == 1:
        RAOffset = -(rowInc * ((columns-1)/2))                #columns wide is odd number
    else:
        RAOffset = -(((columns/2)-1)*rowInc + (rowInc/2.))    #columns wide is even number

    if rows%2 == 1:
        DecOffset = -(colInc * ((rows-1)/2))               #rows tall is odd number
    else:
        DecOffset = -(((rows/2)-1)*colInc + (colInc/2.))   #rows tall is even number

    Log2(6,"Tile#1 offset: %9.6f hours, %5.2f degrees" % (RAOffset,DecOffset))
    Log2(6,"Tile#1 offset: %s hours, %s degrees" % (UTIL.HoursToHMS(RAOffset,":",":","",1),DegreesToDMS(DecOffset)))

    #Calculate RA/Dec center of desired tile, based on tile number used above.
    tileRA = RABase + RAOffset + (x-1)*rowInc
    tileDec = DecBase + DecOffset + (y-1)*colInc
    Log2(6,"Tile #%d coords: %s  %s" % (nextTile,UTIL.HoursToHMS(tileRA,":",":","",1),DegreesToDMS(tileDec)))

    #calculate a string for this tile that can be used to make the filename unique
    tileStr = "_%d,%d_" % (x,y)

    return (tileRA,tileDec,tileStr)

#--------------------------------
def NextMosaicTile( name, maxTileNbr ):
    #increment the count for this tile that we've chosen; rewrite the mosaic tracking file w/ this new value

    MosaicMap = {}     #I could make this global and only load the file once?

    try:
        #if file doesn't exist, that is fine
        #we load all the entries into the temp map, so that if an object
        # occurs more than once, only the latest value counts
        filerows = 0
        g = open( "MosaicTiles.dat", "r")
        for line in g:
            tup = tuple(line.split(','))
            if( len(tup) != 4 ):
                continue            #ignore it
            filerows += 1
            objName = UTIL.TrimString(tup[0])
            count = int(tup[1])
            size  = UTIL.TrimString(tup[2])
            #last part is datetime; don't need to load it

            if objName.endswith("\n"):
                objName = objName[:-1]
            #print "Loading to ignore:","'" + objName + "'"
            #IgnoreList.append(objName)
            MosaicMap[objName] = count
        g.close()
        Log2(6,"NextMosaicTile: loaded %d entries from MosaicTiles.dat, for %d entries" % (filerows,len(MosaicMap)))
    except:
        Log2(6,"NextMosaicTile: file MosaicTiles.dat does not exist yet")
        pass

    #look up the specified object name
    try:
      theCount = MosaicMap[name]
      theCount += 1
      if theCount > maxTileNbr:
        theCount = 1
    except:
      theCount = 1

    MosaicMap[name] = theCount

    value = "%s,%d,%d,%s UTC" % (name,theCount,maxTileNbr,time.asctime(time.gmtime(time.time())))
    f = open( "MosaicTiles.dat", "a" )
    f.write(value)
    f.write("\n")
    f.close()
    Log2(6,"NextMosaicTile for %s is %d" % (name,theCount))
    return( theCount )

#--------------------------------
#  CatGoto,  <targetID>    #this moves the mount but does no imaging; it leaves guider running
##        ("CATGOTO",      execCatGoto),  #
def execCatGoto(t,vState):
    Log2(0, "** CatGoto: not implemented yet")
    pass

#--------------------------------
# LN_Mosaic,<targetID>,<mosaic-size>[,<exp-secs>,<repeat>,<tiles>]
#   0            1            2          3         4        5
def execMosaicLN(t,vState):
   dic = {}
   dic["crop"]     = "no"
   dic["camera"] = "Imager"
   dic["isSeq"]  = "no"
   dic["ID"]     = t[1]
   dic["tileID"] = t[1]     #save name in both dic entries!
   dic["filter"] = "L"
   dic["bin"]    = 2
   dic["mosaic"] = t[2]	#should be string in of form MxN for M across by N vert; ex '3x2'

   try:
      dic["exp"] = int( t[3] )
   except:
      dic["exp"] = vState.exposure

   try:
      dic["repeat"] = int( t[4] )
   except:
      dic["repeat"] = 12

   try:
      dic["tiles"] = int( t[5] )
   except:
      dic["tiles"] = 1

   Log2(0,"** Luminance-Narrow Mosaic target: %s" % (dic["ID"]))
   return execMosaicCommon(dic,vState)

#--------------------------------
# LW_Mosaic,<targetID>,<mosaic-size>[,<exp-secs>,<repeat>,<tiles>]
#   0            1            2          3         4        5
def execMosaicLW(t,vState):
   #vState.ResetImagerOffset()   #forces positioning to center in guider

   dic = {}
   dic["crop"]     = "no"
   dic["camera"] = "Guider"
   dic["isSeq"]  = "no"
   dic["ID"]     = t[1]
   dic["tileID"] = t[1]     #save name in both dic entries!
   dic["filter"] = "L"
   dic["bin"]    = 1
   dic["mosaic"] = t[2]	#should be string in of form MxN for M across by N vert; ex '3x2'

   try:
      dic["exp"] = int( t[3] )
   except:
      dic["exp"] = vState.exposure

   try:
      dic["repeat"] = int( t[4] )
   except:
      dic["repeat"] = 12

   try:
      dic["tiles"] = int( t[5] )
   except:
      dic["tiles"] = 1

   Log2(0,"** Luminance-Wide Mosaic target: %s" % (dic["ID"]))
   return execMosaicCommon(dic,vState)

#--------------------------------
# C_Mosaic,<targetID>,<mosaic-size>[, <seq-filename>, <repeat>, tiles]
#   0            1            2          3               4        5
def execMosaicC(t,vState):
   dic = {}
   dic["crop"]     = "no"
   dic["camera"] = "Imager"
   dic["isSeq"]  = "yes"
   dic["ID"]     = t[1]
   dic["tileID"] = t[1]     #save name in both dic entries!
   dic["mosaic"] = t[2]	#should be string in of form MxN for M across by N vert; ex '3x2'

   dic["seq"]      = GetOptionalSequence(t,3,vState.sequence)

   dic["repeat"] = 2
   try:
      if len(t[4]) > 0:
        dic["repeat"] = int( t[4] )
   except:
      pass

   dic["tiles"] = 1
   try:
      if len(t[5]) > 0:
        dic["tiles"] = int( t[5] )
   except:
      pass

   Log2(0,"** Color Mosaic target: %s" % (dic["ID"]))
   return execMosaicCommon(dic,vState)


#--------------------------------
def execMosaicCommon(dic,vState):
   dic["location"]   = "cat"
   dic["guideExp"]   = vState.guide_exp
   dic["guideStart"] = 1.0			#not used yet
   dic["PP-Solve"]   =  getPPSolve(vState)	#not used
   dic["limit"]      = "count"
   dic["type"]       = "light"

   dic["tileID"] = dic["ID"]

   for i in range(0,dic["tiles"]):
      Log2(1,"** Mosaic tile: %d of %d" % ((i+1),dic["tiles"]))
      tup = implMosaic(dic,vState)
      if tup[0] != 0:
         return tup

   return tup

#--------------------------------

def implMosaic(dic,vState):
    #Settings:
    # dic["tileID"] obj.name
    # n/a           obj.dRA           not used here; only needed to pick target
    # dic["camera"] obj.bWide         T/F
    # dic["isSeq"]  obj.bColor        T/F
    # dic["mosaic"] obj.mosaicSize    MxN
    # n/a           obj.PPOvrd
    # n/a           obj.PPRetry
    # dic["exp"]    obj.L_exposure
    # dic["repeat"] obj.L_repeat

    #bWide = True if this is wide field mosaic, else narrow field
    #NOTE: the values below are hard-coded for my cameras
    if dic["camera"].upper() == "GUIDER":
        #42 x 31.5 arcmin  wide field camera
        height = 28
        width = 38
    else:
        #9.3 x 6.2 arcmin  narrow field camera (INCREASE OVERLAP BY DECREASING SIZE HERE:)
        height = 5.5  #   (6.2-5.5)=0.7  0.7/5.5 = 13%
        width = 8.5   #   (9.3-8.5)=0.8  0.8/8.5 = 9%

        #value used prior to 2010.04.12
        #height = 5  #   (6.2-5)=1.2  1.2/5 = ~25%
        #width = 8   #   (9.3-8)=1.3  1.3/8 = 16%  (but it actually looks more like 25% also)
        # !!THIS MAY BE TOO MUCH OVERLAP!!

    # mosaicSize = "MxN" where M is columns across, N is rows vertically
    temp = dic["mosaic"].upper()
    temp2 = tuple(temp.split('X'))  #validate this???
    columns = int(temp2[0])
    rows    = int(temp2[1])

    #The call below finds the most recent tile number previously taken for this target
    # and returns coordinates for the next tile number.  When the max tile number is
    # reached (=columns*rows) it wraps around to 1. There is no limit on how often
    # this is done.
    tileRA,tileDec,tileStr = CalcMosaicCoords(dic["tileID"],columns,rows,width,height)
    #Note: tileStr = string designating which piece of mosaic being done here, ex: "_1,2_" (row 1, column 2)

    #dic = {}
    #dic["crop"]     = "no"
    dic["location"] = "RA/Dec"      #must set this as RA/Dec to take tile images!
    #dic["limit"]    = "count"
    #dic["type"]     = "light"
    dic["RA"]       = tileRA
    dic["Dec"]      = tileDec
    dic["ID"]       = dic["tileID"] + tileStr      #make the name of each tile unique
    dic["epoch"]    = "J2000"

    Log2(1,"Mosaic coordinates: RA:%s  Dec:%s (J2000)  Tile: %s" % (vState.UTIL.HoursToHMS(tileRA,":",":","",1),DegreesToDMS(tileDec),tileStr))
    return implExp(dic,vState) 	#take images of one tile for mosaic of this target

#--------------------------------
#("SET_TEMPCOMP",     Set_TempComp=<on/off>,<slope>
##    self.temp_comp         = 0        #0=no, 1=yes, 2=future feature??
##    self.temp_comp_slope   = -5.3     #focuser position change per unit temp change
##       ("SET_TEMPCOMP",      setTempComp),
##def setTempComp(t,vState):
##    value = UTIL.TrimString(t[0])
##    if len(value) > 0:
##        if value.upper() == "ON" or value == "1":
##            vState.temp_comp = 1
##        if value.upper() == "OFF" or value == "0":
##            vState.temp_comp = 0
##    if len(t) > 1:
##       value = UTIL.TrimString(t[1])
##       if len(value) > 0:
##           vState.temp_comp_slope = float(value)
##    #Result:
##    Log2(0,"SET temp_comp;    on/off = " + str(vState.temp_comp) + ", slope = " + str(vState.temp_comp_slope))
#--------------------------------
#  Set_TempRefocus=<on/off>
##def setTempRefocus(t,vState):
##    value = UTIL.TrimString(t[0])
##    if len(value) > 0:
##        if value.upper() == "ON" or value == "1":
##            vState.temp_refocus = 1
##        if value.upper() == "OFF" or value == "0":
##            vState.temp_refocus = 0
##    Log2(0,"SET temp_refocus;    on/off = " + str(vState.temp_refocus) )

#--------------------------------
#  Set_SettleGuiding=0.4,120	#Guider on AT66: want better than 0.4 pixel guiding error within 120 seconds, or report problem
#  Set_SettleGuiding=5,60	#Guider on C9.25: want better than 5 pixel guiding error within 60 seconds, or report problem
# vState.GuidingSettleThreshold replaced SETTLE_THRESHOLD
# vState.GuidingSettleTime      replaced SETTLE_MAX_TIME
def setSettleGuiding(t,vState):
    vState.GuidingSettleThreshold = float(GetRequiredValue(t,0))
    vState.GuidingSettleTime      = int(GetRequiredValue(t,1))
    #print vState.GuidingSettleThreshold
    #print vState.GuidingSettleTime
    Log2(0,"SET SettleGuiding = %5.2f pixels, %d seconds" % (vState.GuidingSettleThreshold,vState.GuidingSettleTime))

#NOT USED:
def setAstrometricResync(t,vState):
    vState.AstrometricResyncNumber = GetRequiredValue(t,0) #0=disabled, 1=every imager image, 2=every other image, etc
    vState.AstrometricResyncBackcount = GetRequiredValue(t,1) #0=use most recent image for PP solve, 1=penultimate image, etc

    Log2(0,"SET AstrometricResync = %d number(0=disabled), %d backcount" % (vState.AstrometricResyncNumber,vState.AstrometricResyncBackcount))

def setWaitIfCloudy(t,vState):
    temp = GetRequiredValue(t,0)
    Log2,(0,"argument = %s" % temp)
    if temp == 'Y':
        Log2(0,"=================================================")
        Log2(0,"Warning:  WaitIfCloudy set to True")
        Log2(0,"This means that it keeps checking until clear")
        Log2(0,"and that there is NOT bad weather alarm!")
        Log2(0,"*** USE WITH CARE ***")
        Log2(0,"=================================================")
        vState.WaitIfCloudy = True
    elif temp == 'N':
        Log2(0,"WaitIfCloudy set to False; alarm will sound for bad weather")
        vState.WaitIfCloudy = False     #default value
    else:
        Error("Invalid setting for Set_WaitIfCloudy: " + t[0])
        raise ArgumentError

#--------------------------------
#Set_FixGuidingState=n
# 0 = do nothing (default)
# 1 = issue "Guide Speed" cmd
# 2 = issue "Guide Speed" and then "Precision Guiding" (north) cmd for 1 arcsec
# 3 = issue "Guide Speed" and then "Movement" (north), pause 1 second, then "Quit" movement cmd
def setFixGuidingState(t,vState):
    vState.FixGuidingStateSetting  = int(GetRequiredValue(t,0))
    Log2(0,"SET FixGuidingState = %d" % vState.FixGuidingStateSetting)

#Set_GuideSettleBump=<active>,<direction>[,<threshold>,<amount>,<delay>]
#When settling guider, if error exceeds +- <threshold> pixel, then move the scope <amount> pixels with/against Yerr direction; wait <delay> guide cycles before trying again
#Note:
# <threshold> may be decimal number
# <amount> must be integer value for arcsec to move
def setGuideSettleSetting(t,vState):
    vState.GuideSettleBumpEnable    = int(GetRequiredValue(t,0))    #0=disable, 1=enable
    if vState.GuideSettleBumpEnable:

        vState.GuideSettleBumpDirection = int(GetRequiredValue(t,1))    #0=north for positive Yerr, 1=north for Negative Yerr
        vState.GuideSettleBumpThreshold = float(GetOptionalValue(t,2,1))  #pixel threshold before trying bump
        vState.GuideSettleBumpAmount    = GetOptionalIntValue(t,3,3)    #arcsec to bump (usually 3)
        vState.GuideSettleBumpDelay     = GetOptionalIntValue(t,4,3)    #number of guide cycles to wait after a bump before trying again
    else:
        vState.GuideSettleBumpDirection = 0     #ignored
        vState.GuideSettleBumpThreshold = 1.0   #ignored
        vState.GuideSettleBumpAmount    = 3     #ignored
        vState.GuideSettleBumpDelay     = 3     #ignored

#--------------------------------
#  Set_Guide=<1=on/0=off/2=optional>,<exp-secs>               off,4
# 2=try to guide, but continue with exposure even if not able to start guiding
# 1=guiding must start before imaging, or error
##       ("SET_GUIDE",         setGuide),
def setGuide(t,vState):
   if t[0].upper() == "ON" or t[0] == "1":
      vState.guide = 1
   if t[0].upper() == "OFF" or t[0] == "0":
      vState.guide = 0
   if t[0] == "2":
      vState.guide = 2

   try:
      vState.guide_exp = float(t[1])
   except:
      pass

   Log2(0,"SET Guide;    active = " + str(vState.guide) + ", exp = " + str(vState.guide_exp))

#--------------------------------
#  Set_Sequence=<sequence_filename>         Default: _LLRGB_300sec-1.seq
##       ("SET_SEQUENCE",      setSequence),
def setSequence(t,vState):
   if len(str(t[0])) > 0:
      #vState.sequence = validateSequence(str(t[0]),vState)
      vState.sequence = GetOptionalSequence(t,0,vState.sequence)

   #Result:
   Log2(0,"SET Sequence: %s (should include path here, not when specified in command file)" % vState.sequence )


#--------------------------------
#  Set_Path=<path info>                   C:\fits\
##       ("SET_PATH",          setPath),
def setPath(t,vState):
    path = t[0]
    path = UTIL.TrimString( path )

    if not path.endswith("\\"):
        path += "\\"
    vState.path = path

    #Result:
    Log2(0,"SET Path:     " + str(vState.path))
#--------------------------------
#  Set_Exposure=<exp-secs>                30
##       ("SET_EXPOSURE",      setExposure),
def setExposure(t,vState):
    if len(str(t[0])) > 0:
        vState.exposure = float(t[0])

    #Result:
    Log2(0,"SET Exposure; seconds = " + str(vState.exposure))

#setFocusParms
def setFocusParms(t,vState):
    pass
    if len(t) == 2:
        pass
    #if len(str(t[0])) > 0:
    #    vState.exposure = float(t[0])

    #Result:
    #Log2(0,"SET Exposure; seconds = " + str(vState.exposure))

#------------------------------------------
#  Set_FlatAltitudeMorning=<degrees>
def setFlatAltitudeMorning(t,vState):
    if len(t) == 1:
        vState.FlatAltitudeMorning = float(t[0])

    #Result:
    Log2(0,"SET Flat Altitude: Morning = " + str(vState.FlatAltitudeMorning))
#--------------------------------
#  Set_FlatAltitudeEvening=<degrees>
def setFlatAltitudeEvening(t,vState):
    if len(t) == 1:
        vState.FlatAltitudeEvening = float(t[0])

    #Result:
    Log2(0,"SET Flat Altitude: Evening = " + str(vState.FlatAltitudeEvening))

#---------------------------------
#When specified, it will cause exposure to end when telescope reaches specified
# 	number of degrees above western horizon. This will stop a command using
#	_EndTime_ or _Count_ even if the other end condition not reached yet.
#	This functions similar to checking the sun's altitude below the horizon to
#	stop when it gets too high.
def setHaltAltitude	(t,vState):
    Log2(0,"Set_HaltAltitude setting, raw=<%s>" % str(t))
    if len(t) > 0:
		vState.WesternHaltAltitude = float(t[0])

    #Result:
    Log2(0,"SET Halt Altitude = " + str(vState.WesternHaltAltitude))

#--------------------------------
#  Set_FocusCompensation=Y/N/D   (default = N at startup; D = delay start when sun gets low enough)
def setFocusCompensation(t,vState):
    pass
    Log2(0,"Set_FocusCompensation setting, raw=<%s>" % str(t))
    if len(t) > 0:
        if t[0] in ('T','t','Y','y',1):
            vState.FocusCompensationActive = 1  # 1 = True
            Log2(1," ")
            Log2(1,"@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            Log2(1,"@ Set FocusCompensation to TRUE; automatically moves @")
            Log2(1,"@ focuser (between images) if temperature changes.   @")
            Log2(1,"@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            Log2(1," ")
        elif t[0] in ('F','f','N','n',0):
            vState.FocusCompensationActive = 0  # 0 = False
            Log2(1,"set FocusCompensation to False; does not automatically move focuser in response to temperature change")
        elif t[0] in ('A','a',3):
            vState.FocusCompensationActive = 3  # 3 = Advanced logic
            vState.AdvancedFocusState = 0       # 0 = not active yet, waiting to take benchmark focus
            vState.AdvancedFocusStartTime = time.time() #record time
            Log2(1,"set FocusCompensation to Advanced mode; this will use benchmark focus after 1.5 hours from now, and take benchmark focus itself if none done by 2 hours from now; then temp comp will be enabled")
        elif t[0] in ('D','d','2',2):
            #DISABLED
            pass
            #vState.FocusCompensationActive = 2  # 2 = delay start
            #Log2(1,"set FocusCompensation to Delay; wait until sun at least -20deg below horizon, and then start at that point")
            #Log2(1," ")
            #Log2(1,"======================================================")
            #Log2(1,"= Set FocusCompensation to DELAYED START.            =")
            ##Log2(1,"= When sun reaches -20 deg below horizon then        =")
            #Log2(1,"= temperature compensation will start.               =")
            #Log2(1,"======================================================")
            #Log2(1," ")
            ##check sun altitude
            #tup1 = time.gmtime()
            #mYear  = tup1[0]
            #mMonth = tup1[1]
            #mDay   = tup1[2]
            #utc    = float(tup1[3]) + (float(tup1[4])/60.) + (float(tup1[5])/3600.)
            #alt = CalcSolarAlt(mYear,mMonth,mDay,utc,myLongitude,myLatitude)
            #Log2(2,"Note: sun altitude currently %5.2f" % alt)
            #if alt <= -20:
            #    Log2(2," ")
            #    Log2(2,"@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            #    Log2(2,"@ TEMPERATURE COMPENSATION WILL START RIGHT AWAY @")
            #    Log2(2,"@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            #else:
            #    Log2(2,"Temperature compensation will not start yet.")


        else:
            Error("Invalid command for Set_FocusCompensation")
            Error("Parameter found = <%s>" % str(t))

# Set_Astrometry.net=1	#0=disable, 1=use after 2 failures of PP solve, 2=use all the time(disable all PP solves)
def setAstrometryNet(t,vState):
    if len(t) == 1:
        try:
            value = int(t[0])
            if value < 0 or value > 2:
                Error("INVALID ARGUMENT FOR SET_ASTROMETRY.NET; MUST BE 0-2")
                return
            vState.AstrometryNet = value
            if value == 0:
                Log2(0,"SET Astrometry.net = 0: disable Astrometry.net, use PinPoint for all plate solves")
            elif value == 1:
                Log2(0,"SET Astrometry.net = 1: if PinPoint fails to solve after 2 attempts, use Astrometry.net for all remaining attempts on that field")
            else:   # == 2
                Log2(0,"SET Astrometry.net = 2: use Astrometry.net for all plate solves; PinPoint will not be used at all")
            return

        except:
            pass
            print 5

    Error("INVALID ARGUMENT FOR SET_ASTROMETRY.NET; must be one number of value: 0, 1, or 2 !!!")
    Error("len(t) = %d" % len(t))


#  Set_ImageScale=<imager arcsec/pixel>,<guider arcsec/pixel>
def setImageScale(t,vState):
    if len(t) == 2:
        try:
            print 1
            imager = float(t[0])
            guider = float(t[1])
            print 2

            #only assign of the both of the values are OK
            if imager > 0.1 and imager < 20 and guider > 0.1 and guider < 20:
                print 3
                vState.ImagerScale = imager
                vState.GuiderScale = guider
                Log2(0,"SET image scale: Imager = %5.2f  Guider = %5.2f arcsec/pixel" % (vState.ImagerScale,vState.GuiderScale))
                return
            print 4
        except:
            pass
            print 5

    Error("INVALID ARGUMENT(S) FOR SET_IMAGESCALE !!!")
    Error("len(t) = %d" % len(t))
    Error("str(t) = %s" % str(t))

#--------------------------------
### Set_FOVoffset=<RA-arcmin>,<Dec-arcmin>
##def setFOVoffset(t,vState):
##   vState.FOV_RA = float(t[0])
##   vState.FOV_Dec = float(t[1])
##   Log2(0,"SET FOVoffset: RA: %5.2f   Dec: %5.2f" % (vState.FOV_RA,vState.FOV_Dec))

#--------------------------------
# Set_ReacquireAfterPierFlip=f    where f = T,Y,y,1 if yes;   F,N,n,0 if no
#  setReacquireAfterPierFlip
def setReacquireAfterPierFlip(t,vState):
    Log2(0,"Set_ReacquireAfterPierFlip setting, raw=<%s>" % str(t))
    if len(t) > 0:
        if t[0] in ('T','t','Y','y',1):
            vState.bContinueAfterPierFlip = True
            Log2(1,"set bContinueAfterPierFlip to TRUE")
        elif t[0] in ('F','f','N','n',0):
            vState.bContinueAfterPierFlip = False
            Log2(1,"set bContinueAfterPierFlip to False")
        else:
            Error("Invalid command for Set_ReacquireAfterPierFlip")
            Error("Parameter found = <%s>" % str(t))
#--------------------------------
# Set_FocusEnable=f    where f = T,Y,y,1 if yes;   F,N,n,0 if no
def setFocusEnable(t,vState):
    Log2(0,"Set_FocusEnable setting, raw=<%s>" % str(t))
    if len(t) > 0:
        if t[0] in ('T','t','Y','y',1):
            vState.focusEnable = True
            Log2(1,"set focusEnable to TRUE")
        elif t[0] in ('F','f','N','n',0):
            vState.focusEnable = False
            Log2(1,"set focusEnable to False; no focusing will be done, no GOTO focus stars")
        else:
            Error("Invalid command for Set_FocusEnable")
            Error("Parameter found = <%s>" % str(t))
#--------------------------------
# Set_DriftThreshold=arcmin    where arcmin = number of arcmin threshold, movement beyond that causes stop & reacquire
def setDriftThreshold(t,vState):
    Log2(0,"Set_DriftThreshold setting, raw=<%s>" % str(t))
    if len(t) > 0:
        vState.driftThreshold = float(t[0])
        Log2(1,"set driftThreshold = %5.2f" % vState.driftThreshold)
    else:
        vState.driftThreshold = 4.0
        Error("Invalid setting for Set_DriftThreshold; set to default = 5.0")


#--------------------------------
#  Set_Repeat=<cnt>                    1
##       ("SET_REPEAT",        setRepeat),
def setRepeat(t,vState):
    if len(str(t[0])) > 0:
        vState.repeat = int(t[0])

    #Result:
    Log2(0,"SET Repeat;   count = " + str(vState.repeat))
#--------------------------------
#  Set_Sleep=<secs>                    15
##       ("SET_SLEEP",         setSleep),
def setSleep(t,vState):
    ##if len(str(t[0])) > 0:
    ##    vState.sleep = int(t[0])

    #Result:
    Log2(0,"SET Sleep;  OBSOLETE; THIS COMMAND NOT USED ANY MORE " )
#--------------------------------
#  Set_Filter=<R/G/B/L/V>                   L(3)
##       ("SET_FILTER",        setFilter),
def setFilter(t,vState):
    if len(str(t[0])) == 0:
        return;
    c = UTIL.TrimString(str(t[0]))
    if  c == 'R' or c == 'r' or c == '0':
        vState.filter = 0
    elif c == 'G' or c == 'g' or c == '1':
        vState.filter = 1
    elif c == 'B' or c == 'b' or c == '2':
        vState.filter = 2
    elif c == 'L' or c == 'l' or c == '3':
        vState.filter = 3
    #elif c == 'Ha' or c == 'H' or c == 'ha' or c == 'h' or c == "HA" or c == '4':
    #    vState.filter = 4
    elif c == 'V' or c == 'v' or c == '4':	#replaced HA filter w/ V photometric 2015.06.19
        vState.filter = 4
    else:
        Error("Invalid filter setting: <" + str(t[0]) + ">")
        return
	#2015.06.21 JU: add new feature: when this command given, immediately issue Filter command to camera
    Log2(1,"@@@ Before setting filter, currently: %d" % vState.CAMERA.Filter )

    vState.CAMERA.Filter = vState.filter
    time.sleep(1)
    Log2(1,"@@@ After setting filter, currently: %d, want %d" % (vState.CAMERA.Filter,vState.filter) )

    #Result:
    Log2(0,"SET Filter = " + str(vState.filter))

#--------------------------------------------------------------------------------------------------------
#  Set_FlushCCD=<1=on,0=off>,<cnt>              1,10
##       ("SET_FLUSHCCD",      setFlushCCD),
def setFlushCCD(t,vState):
    value = UTIL.TrimString(t[0])
    if len(value) > 0:
        if value.upper() == "ON" or value == "1":
            vState.flush = 1
        if value.upper() == "OFF" or value == "0":
            vState.flush = 0
    value = UTIL.TrimString(t[1])
    try:
        if len(value) > 0 and int(value) > 0 and int(value) < 100:
            vState.flush_cnt = int(value)
    except:
        pass

    #Result:
    Log2(0,"SET FlushCCD;    active = " + str(vState.flush) + ", count = " + str(vState.flush_cnt))

#--------------------------------------------------------------------------------------------------------
#  Set_Altitude=<degrees>     #do not start images with target below this altitude (default: 0)
##       ("SET_ALTITUDE",      setAltitude),
def setAltitude(t,vState):
    if len(str(t[0])) > 0:
        vState.min_altitude = int(t[0])

    #Result:
    Log2(0,"SET Altitude;    degrees = " + str(vState.min_altitude))


#--------------------------------------------------------------------------------------------------------
#  PP=Active,1,1           #(imager,guider) 0=disable, 1=enable
#  PP=Exposure,30,10       #(imager,guider) camera exposure, seconds
#  PP=Exp_increment,2,2    #(imager,guider) factor to increase exp each time if failure
#  PP=Retry,3,2            #(imager,guider) max number of retries if failure at one location
#X  PP=Move_retry,2,0      #(imager,guider) max tries for moving to different location and try solving there
#X  PP=Move_amount,15,0    #(imager,guider) distance in arcminutes to move
#X  PP=Move_direction,1,0  #(imager,guider) direction to move: 1=N,2=S,3=E,4=W
#  PP=Precision,1,2        #(imager,guider) arcminute limit for accepting solution vs desired; else move and repeat
#X  PP=Precision_retry,1,1 #(imager,guider) max number of repositions to reach desired precision
#  PP=Require_solve,0,1	   #(imager,guider) yes/no: Must solve guider image or will not image target,
				# it will still take planned exposure w/ Imager even if PP image fails
				# to solve.
##       ("PP",                setPP)
def setPP(t,vState):
    keyword_list = [
        ("ACTIVE",        pp_Active),
        ("EXPOSURE",      pp_Exposure),
        ("BINNING",       pp_Binning),
        ("EXP_INCREMENT", pp_Exp_Increment),
        ("RETRY",         pp_Retry),
        ("PRECISION",     pp_Precision),
        ("REQUIRE_SOLVE", pp_Require_Solve),
        ("CATALOGID",     pp_CatalogID),
        ("CATMAXMAG",     pp_CatMaxMag),
        ("MAXSOLVETIME",  pp_MaxSolveTime),
        ("SIGMAABOVEMEAN",pp_SigmaAboveMean)
    ]

    if len(t) != 3:
        Error("setPP called with wrong size tuple")
        return

    ##
    ## PP State command processing
    ##
    action = t[0].upper()
    for (cmd,fn) in keyword_list:
            #Log("Compare PP state command <" + cmd + "> to line: <" + t[0] + ">")
            if action.find(cmd) == 0:
                #print "Executing command ",cmd," for line: ",t[0],t[1],t[2]
                arg1 = UTIL.TrimString(t[1])
                arg2 = UTIL.TrimString(t[2])
                fn(arg1,arg2,vState)
                return
    Error( "Unable to parse PP command: " + t[0])

#---------------------------
def pp_Active(arg1,arg2,vState):
   vState.ppState[0].active = int(arg1)
   vState.ppState[1].active = int(arg2)
   Log2(0,"PP State = %d, %d" % (int(arg1),int(arg2)))

#---------------------------
def pp_Exposure(arg1,arg2,vState):
   vState.ppState[0].exposure = float(arg1)
   vState.ppState[1].exposure = float(arg2)
   Log2(0,"PP Exposure = %d, %d" % (int(arg1),int(arg2)))

#---------------------------
def pp_Binning(arg1,arg2,vState):
   vState.ppState[0].binning = int(arg1)
   vState.ppState[1].binning = int(arg2)  #CANNOT SET BINNING FOR GUIDER; THIS SETTING DOES NOTHING
   Log2(0,"PP Binning = %d, %d" % (int(arg1),int(arg2)))

#---------------------------
def pp_Exp_Increment(arg1,arg2,vState):
   vState.ppState[0].exp_increment = float(arg1)
   vState.ppState[1].exp_increment = float(arg2)
   Log2(0,"PP Exposure Increment factor = %d, %d" % (int(arg1),int(arg2)))

#---------------------------
def pp_Retry(arg1,arg2,vState):
   vState.ppState[0].retry = int(arg1)
   vState.ppState[1].retry = int(arg2)
   Log2(0,"PP Exposure Retry limit = %d, %d" % (int(arg1),int(arg2)))

#---------------------------
def pp_Precision(arg1,arg2,vState):
   vState.ppState[0].precision = float(arg1)
   vState.ppState[1].precision = float(arg2)
   Log2(0,"PP Precision (arcminutes) = %f, %f" % (float(arg1),float(arg2)))

#---------------------------
def pp_Require_Solve(arg1,arg2,vState):
   vState.ppState[0].require_solve = int(arg1)
   vState.ppState[1].require_solve = int(arg2)
   Log2(0,"PP Require_solve = %d, %d" % (int(arg1),int(arg2)))

#---------------------------
def pp_CatalogID(arg1,arg2,vState):
#        ("CATALOGID",     pp_CatalogID),
   vState.ppState[0].CatalogID        = int(arg1)
   vState.ppState[1].CatalogID        = int(arg2)
   Log2(0,"PP CatalogID = %d, %d" % (int(arg1),int(arg2)))

#---------------------------
def pp_CatMaxMag(arg1,arg2,vState):
#        ("CATMAXMAG",     pp_CatMaxMag),
   vState.ppState[0].CatMaxMag = int(arg1)
   vState.ppState[1].CatMaxMag = int(arg2)
   Log2(0,"PP CatMaxMag = %d, %d" % (int(arg1),int(arg2)))

#---------------------------
def pp_MaxSolveTime(arg1,arg2,vState):
#        ("MAXSOLVETIME",  pp_MaxSolveTime),
   vState.ppState[0].MaxSolveTime = int(arg1)
   vState.ppState[1].MaxSolveTime = int(arg2)
   Log2(0,"PP MaxSolveTime = %d, %d" % (int(arg1),int(arg2)))

#---------------------------
def pp_SigmaAboveMean(arg1,arg2,vState):
#        ("SIGMAABOVEMEAN",pp_SigmaAboveMean)
   vState.ppState[0].SigmaAboveMean = float(arg1)
   vState.ppState[1].SigmaAboveMean = float(arg2)
   Log2(0,"PP SigmaAboveMean = %f, %f" % (float(arg1),float(arg2)))


#=====================================================================================
#==== SECTION  @@Focus ============================================================
#=====================================================================================
class cFocusStar:
    def __init__(self):
        self.name = ""
        self.dRA = 0.
        self.dDec = 0.
        self.magnitude = 0.

    def setString(self,theName, RAJ2000,DecJ2000,mag):
        global UTIL         #declare this for use below
        self.dRA = UTIL.HMSToHours(RAJ2000)
        self.dDec = UTIL.DMSToDegrees(DecJ2000)
        self.name = theName
        self.magnitude = mag

    def setStringD(self,theName, RAJ2000D,DecJ2000D,mag):
        self.dRA = RAJ2000D
        self.dDec = DecJ2000D
        self.name = theName
        self.magnitude = mag

#--------------------------------------------------------------------------------------------------------
def PrepareFocusStarList():
    Log2(4,"Preparing FocusStarList...")
    f = open( FocusStarFile, "r")
    cnt = 0

    for line in f:
        tup = tuple(line.split(','))
        if( len(tup[0]) == 0 ):
            #print "skip blank line:",line
            continue            #blank line
        cnt += 1
        dRA = float(tup[0])
        dDec = float(tup[1])
        mag  = tup[2]
        name = tup[3]
        #FYI:  tup[4] is spectral type; we don't use it currently but is available

        #2011.07.31 JU: changed from string coords to decimal coords in focus star file
        target = cFocusStar()                  #must create inside loop or only get last item repeated in list??
        target.setStringD(name,dRA,dDec,mag)
        FocusStarList.append(target)
        #print "'" + objName + "'"
    f.close()
    Log2(5, "Total stars loaded into FocusStarList: %d" % cnt)

#--------------------------------------------------------------------------------------------------------
def FindFocusStar(dRA):
    #return cFocusStar
    if dRA < 0 or dRA >= 24:
        Error("Invalid input to FindFocusStar")
        SafetyPark(vState)
        raise SoundAlarmError,'Halting program'
    for star in FocusStarList:
        if IgnoreFocusStars.count(star.name) > 0:
            continue
        if star.dRA >= dRA:
            return star
    if dRA > 23.5:
        #this might be too close to wrap around, so just pick the first star
        for star in FocusStarList:
            if IgnoreFocusStars.count(star.name) > 0:
                continue
            return star     #pick the first non-excluded star
    Error("Did not find any stars in FocusStarList")
    SafetyPark(vState)
    raise SoundAlarmError,'Halting program'

#--------------------------------------------------------------------------------------------------------
def CalcLocationDistance(ra1,ra2,dec1,dec2):
  #easy way: treat as rectangular coords
  #(correct way would be to use spherical trig)
  raDiff = abs(ra1 - ra2)
  if raDiff > 11:  raDiff = abs(24 - raDiff)  #coords wrapped
  raDeg = raDiff * 15	#convert hours to degrees

  decDiff = abs(dec1 - dec2)

  diff = math.sqrt((raDeg * raDeg) + (decDiff *decDiff))
  return diff

#-----------------------------------------------------------------------------------------------------
def AvoidMeridian(meridian, star):
	#return true if star close to meridian

 try:
	#  <--|--------|-----------+--------------|	A	star < meridian,  (meridian - star) < 12
	#     0h   meridian      star                       meridian > star (star on west side of meridian)

	#  <-----------|-------|----+-------------|	B	meridian < star,  (star - meridian) > 12
	#          meridian    0h  star                     meridian+24 > star (star on west side of meridian, wrapped)

	#  <--|-----+-------|---------------------|	C	meridian < star,  (star - meridian) < 12
	#     0h   star   meridian                   meridian < star (star on east side of meridian)

	#  <------+-----|------|------------------|	D	star < meridian,  (meridian - star) > 12
	#        star   0h  meridian                   meridian < (star+24) (star on east side of meridian, wrapped)
	THRESHOLD = 0.5

	if star < meridian:
		#this is case A or D
		diff = meridian - star
		if diff < 12:
			#this is case A
			if diff < THRESHOLD:
				#Log2(5,"AvoidMeridian: case A - too close: %5.2f %5.2f %5.2f" % (diff, meridian, star))
				return 1	#too close
			#Log2(5,"AvoidMeridian: case A - OK: %5.2f %5.2f %5.2f" % (diff, meridian, star))
			return 0		#OK
		else:
			#this is case D
			diff = (24-meridian)+star
			if diff < THRESHOLD:
				#Log2(5,"AvoidMeridian: case D - too close: %5.2f %5.2f %5.2f" % (diff, meridian, star))
				return 1	#too close
			#Log2(5,"AvoidMeridian: case D - OK: %5.2f %5.2f %5.2f" % (diff, meridian, star))
			return 0		#OK
	else:
		#this is case B or case C
		diff = star - meridian
		if diff > 12:
			#this is case B
			diff = (24-star)+meridian
			if diff < THRESHOLD:
				#Log2(5,"AvoidMeridian: case B - too close: %5.2f %5.2f %5.2f" % (diff, meridian, star))
				return 1	#too close
			#Log2(5,"AvoidMeridian: case B - OK: %5.2f %5.2f %5.2f" % (diff, meridian, star))
			return 0		#OK
		else:
			#this is case C
			if diff < THRESHOLD:
				#Log2(5,"AvoidMeridian: case C - too close: %5.2f %5.2f %5.2f" % (diff, meridian, star))
				return 1	#too close
			#Log2(5,"AvoidMeridian: case C - OK: %5.2f %5.2f %5.2f" % (diff, meridian, star))
			return 0		#OK
 except:
    #make sure I don't crash everything just in case of a minor error, so wrap in exception
	Error("Exception in AvoidMeridian")
	niceLogExceptionInfo()
 return 0

#-----------------------------------------------------------------------------------------------------
def FindNearFocusStar(vState,tpos,minRA,maxRA):
    #2014.10.19 JU: added vState to parameter list in case it needs to call SafetyPark() here; it was missing before so it threw a fatal exception and didn't park if this happened (very bad)
    #input: coords that we want the target star near,
    # and range around dRA that we want to search (already adjusted for any meridian issues)
    #Return: cFocusStar object (has RA/Dec/name)
    #Log2(2,"FindNearFocusStar:  len(FocusStarList) = %d, len(IgnoreFocusStars) = %d" % (len(FocusStarList),len(IgnoreFocusStars)))
    Log2(3,"FindNearFocusStar:  minRA = %5.2f, maxRA = %5.2f" % (minRA,maxRA))

    if len(FocusStarList) == 0:
        Error("*****************************************")
        Error("** Focus star list is empty !!!        **")
        Error("*****************************************")
        SafetyPark(vState)
        raise SoundAlarmError,'Halting program - focus star list is empty'

    minDistance = 99999
    minStar = cFocusStar()

    meridian = vState.MOUNT.SiderealTime	#added 2015.05.06 JU

    examined = 0
    ignored = 0
    considered = 0
    near_meridian = 0
    for star in FocusStarList:
        #LogOnly("examined = %d, ignored = %d, considered = %d" % (examined,ignored,considered))
        examined += 1
        #decide if the star is in the range of RA that we're interested in
        if minRA < maxRA:
            #not inverted
            if star.dRA < minRA:
                continue   #not in range yet
            if star.dRA > maxRA:
                break      #past the possible range
        else:
            #inverted range (wraps around 0h)
            if star.dRA > maxRA and star.dRA < minRA:
                continue  #excluded area

        #is this star part of the list to exclude because we had a problem w/ it earlier?
        if IgnoreFocusStars.count(star.name) > 0:
            ignored += 1
            Log2(4,"Ignoring focus star that is in right part of sky (we previously placed it in IgnoreFocusStars list): " + star.name)
            continue

        #2015.05.06 JU: new feature: if star is 'close' to meridian, exclude it because Gemini might slew to wrong
        # 			side of meridian, even though it shouldn't. This problem has happened.
        if AvoidMeridian(meridian, star.dRA):
			near_meridian += 1
			Log2(4,"Ignoring focus star too close to the meridian: " + star.name)
			continue

        #OK to check this star
        considered += 1
        #newDiff = <calculate difference, spherical trig, star.dRA, star.dDec, wantRA,wantDec>
        newDiff = CalcLocationDistance(tpos.dRA_J2000(),star.dRA,tpos.dDec_J2000(),star.dDec)
        if newDiff < minDistance:
        #new minimum found
            minStar = star
            minDistance = newDiff
            Log2(4,"New min: diff=%5.3f  Want=(%5.2f,%5.2f) Star=(%5.2f,%5.2f) %s" % (newDiff,tpos.dRA_J2000(),tpos.dDec_J2000(),star.dRA,star.dDec,star.name))

    #all stars have been checked; what did we find?
    if minDistance == 99999:
        Log2(0,"FindNearFocusStar: examined = %d, ignored = %d, considered = %d" % (examined,ignored,considered))
        Error("*****************************************")
        Error("** Did not find any 'near' focus stars **")
        Error("*****************************************")
        SafetyPark(vState)
        raise SoundAlarmError,'Halting program - did not find near focus star'

    return minStar

#--------------------------------------------------------------------------------------------------------
def BuildFocusStarBand(wantPos,vState):
   #build the basic RA band 2 hours wide centered on provided coordinate
   #returns: tuple of min,max RA values for band
   #2010.08.09 JU: rebuild logic (again) here because previous had logic failure;
   #               If target close to meridian, then the 2 hour band is uses the meridian
   #               as one side, to insure we get enough potential focus stars.
   minRA = wantPos.dRA_J2000() - 1
   if minRA < 0: minRA += 24
   maxRA = wantPos.dRA_J2000() + 1
   if maxRA >= 24: maxRA -= 24

   #is the meridian within this band?
   #2012.04.25 JU: protect in case we are restarting after waiting for clouds
   if not vState.MOUNT.Connected:
       vState.MOUNT.Connected = True
   if vState.MOUNT.AtPark:
       Log2(3,"Unparking mount")
       vState.MOUNT.Unpark()
   if not vState.MOUNT.Tracking:
       vState.MOUNT.Tracking = True

   meridian = vState.MOUNT.SiderealTime

   Log2(4,"BuildFocusStarBand: target RA: %5.2f   Meridian: %5.2f" % (wantPos.dRA_J2000(),meridian))

   if minRA < maxRA:   #did not span 0h
      #  <--|-----------+-------+--------------|
      #     0h  23h..  max     min      ...1h  0h
      if meridian < minRA or meridian > maxRA:
        #  <--|----|-------+-------+--------------|
        #     0h   M      max     min               meridian > max
        #or
        #  <--|-----------+-------+-------|-------|
        #     0h         max     min      M         meridian < min
         #simple case, meridian not included, so return values
         Log2(4,"BFSB 1a: %5.2f -> %5.2f -> %5.2f   Meridian=%5.2f" % (minRA,wantPos.dRA_JNow(),maxRA,meridian))
         return (minRA,maxRA)
      else: # spans meridian; recalc band based side of meridian that target is on
         #  <-------------+---|----+--------------|
         #               max  M   min             0h
         if wantPos.dRA_J2000() <= meridian:
             #  <----------------|-----+----+-------|
             #                   M  target              target west of meridian
             #                   max        min(=M-2)
             pass
             maxRA = meridian
             minRA = meridian - 2
             if minRA < 0:  minRA += 24     #in case new band crosses 0h
             Log2(4,"BFSB 1b: %5.2f -> %5.2f -> %5.2f   Meridian=%5.2f" % (minRA,wantPos.dRA_JNow(),maxRA,meridian))
             return (minRA,maxRA)
         else:
             #  <--------+------+-----|--------------|
             #               target   M                 target east of meridian
             #         max(=M+2)     min
             pass
             minRA = meridian
             maxRA = meridian + 2
             if maxRA >= 24: maxRA -= 24    #in case new band crosses 0h (2014.10.20 fixed test!)
             Log2(4,"BFSB 1c: %5.2f -> %5.2f -> %5.2f   Meridian=%5.2f" % (minRA,wantPos.dRA_JNow(),maxRA,meridian))
             return (minRA,maxRA)


   else: #spanning 0h
      #  <-------------+---|-----+--------------|
      #               max  0h   min
      if meridian > maxRA and meridian < minRA:
         #  <------|------+---|-----+--------------|
         #         M     max  0h   min                meridian > max
         #or
         #  <-------------+---|-----+-------|-------|
         #               max  0h   min      M         meridian < min
         #not including meridian, so just return the values
         Log2(4,"BFSB 2: %5.2f -> %5.2f -> %5.2f" % (minRA,wantPos.dRA_JNow(),maxRA))
         return (minRA,maxRA)
      else: #spans meridian (as well as 0h)
         #  <-------------+---|--|---+--------------|
         #               max  M  0h min
         #or
         #  <-------------+---|--|---+--------------|
         #               max  0h M  min

         if meridian < 12:
             #Meridian is low value, so must be east(left) of 0h
             #  <-------------+---|---|----+--------------|
             #               max  M   0h  min
             #                  A   B   C
             #Position of target relative to Meridian and 0h:
             if wantPos.dRA_J2000() > meridian and wantPos.dRA_J2000() < 12:
                 #Case 'A', target east of meridian
                 minRA = meridian
                 maxRA = meridian + 2
                 if maxRA >= 24: maxRA -= 24    #SHOULDN'T HAPPEN   (2014.10.20 fixed test!)
                 Log2(4,"BFSB 2A: %5.2f -> %5.2f -> %5.2f   Meridian=%5.2f" % (minRA,wantPos.dRA_JNow(),maxRA,meridian))
                 return (minRA,maxRA)
             elif wantPos.dRA_J2000() <= meridian and wantPos.dRA_J2000() < 12:
                 #Case 'B', target west of meridian
                 maxRA = meridian
                 minRA = meridian - 2
                 if minRA < 0:  minRA += 24
                 Log2(4,"BFSB 2B: %5.2f -> %5.2f -> %5.2f   Meridian=%5.2f" % (minRA,wantPos.dRA_JNow(),maxRA,meridian))
                 return (minRA,maxRA)
             else:
                 #Case 'C', target west of meridian
                 maxRA = meridian
                 minRA = meridian - 2
                 if minRA < 0:  minRA += 24     #SHOULDN'T BE ABLE TO HAPPEN
                 Log2(4,"BFSB 2C: %5.2f -> %5.2f -> %5.2f   Meridian=%5.2f" % (minRA,wantPos.dRA_JNow(),maxRA,meridian))
                 return (minRA,maxRA)
         else:
             #meridian is high value, so must be west(right) of 0h
             #  <-------------+---|---|----+--------------|
             #               max  0h  M   min
             #                   A  B   C
             #Position of target relative to Meridian and 0h:
             if wantPos.dRA_J2000() < meridian and wantPos.dRA_J2000() < 12:
                 #Case 'A', target east of meridian, east of 0h
                 minRA = meridian
                 maxRA = meridian + 2
                 if minRA >= 24:  minRA -= 24       #(2014.10.20 added to prevent reaching 24.0)
                 if maxRA >= 24: maxRA -= 24    #in case new band crosses 0h    (2014.10.20 fixed test!)
                 Log2(4,"BFSB 3A: %5.2f -> %5.2f -> %5.2f   Meridian=%5.2f" % (minRA,wantPos.dRA_JNow(),maxRA,meridian))
                 return (minRA,maxRA)
             elif wantPos.dRA_J2000() > meridian and wantPos.dRA_J2000() > 12:
                 #Case 'B', target east of meridian, west of 0h
                 minRA = meridian
                 maxRA = meridian + 2
                 if maxRA >= 24: maxRA -= 24    #in case new band crosses 0h    (2014.10.20 fixed test!)
                 Log2(4,"BFSB 3B: %5.2f -> %5.2f -> %5.2f   Meridian=%5.2f" % (minRA,wantPos.dRA_JNow(),maxRA,meridian))
                 return (minRA,maxRA)
             else:
                 #Case 'C', target west of meridian
                 maxRA = meridian
                 minRA = meridian - 2
                 if minRA < 0:  minRA += 24     #SHOULDN'T BE ABLE TO HAPPEN
                 if maxRA >= 24: maxRA -= 24    #in case new band crosses 0h  (added 2014.10.20)
                 Log2(4,"BFSB 3C: %5.2f -> %5.2f -> %5.2f   Meridian=%5.2f" % (minRA,wantPos.dRA_JNow(),maxRA,meridian))
                 return (minRA,maxRA)

#--------------------------------------------------------------------------------------------------------
def FocusGoodEnough():      #THIS IS NOT CALLED BY ANYTHING; CODING WAS NEVER FINISHED
    pass
    #New replacement for callFocusMax()  [NEVER FINISHED]
    #This assumes the scope is pointed at a focus star
    #Returns:
    #   success
    #   failed to focus even after several attempts

    #setup state variables
    timeoutAttempts = 7
    #TODO

    #Looping
    while timeoutAttempts > 0:
      timeoutAttempts -= 1

      try:
            imaging_db.RecordFocuser(vState,1030)
            vState.FOCUSCONTROL.FocusAsync()   #start FocusMax via async call
            started = time.time()
            limit = 10*60   #10 minutes time limit for focusing to be really generous...
            while ((time.time() - started) < limit) and (vState.FOCUSCONTROL.FocusAsyncStatus == -1):
                 time.sleep(1)
                 imaging_db.RecordFocuser(vState,1031)
      except:
            Error( "...Focus failed(exception): " + argTarget )
            niceLogExceptionInfo()
            imaging_db.RecordFocuser(vState,1230)

      #TODO...???

      imaging_db.RecordFocuser(vState,1032)

#--------------------------------------------------------------------------------------------------------
def callFocusMax(dic,vState):
	# 2015.06.21: add filter selection?	CCDCamera.Filter [= Short]
	#If I set the filter offset in MaxIm filter table, will changing the CCDCamera.Filter value immediately
	#  cause the focuser to move?
	#Does FocusMax do anything with the filter wheel? It does not appear that it does anything.
	#Adding focuser offset for V filter might be sufficient, once I measure it.

    Log2Summary(1,"FocusMax begins")
    if not vState.focusEnable:
       Log2(2,"Focusing disabled, so nothing done for focus step")
       return True  #do nothing, report success

    #return true if success, false = failed to focus
    #common code for calling FocusMax, handling errors, and in particular running FocusMax
    # at least twice in a row to make sure results are consistent. (Occasionally it gives a bad
    # result; want to protect against this.)
    #
    # init counter
    # while loop:
    #  call FocusMax
    #  Save result
    #  if 1st try, 'continue' (repeat loop)
    #  is this result "consistent" with previous value? Yes: then quit
    #  else if too many attempts: quit
    #vState.FOCUS  = win32com.client.Dispatch("FocusMax.FocusControl")
    global excessiveFocusRetries

	#REMOVED 2015.06.21 JU: plan to use Set_Filter=V or Set_Filter=L from now on before using focus cmd
    #Log2(4,"Set Filter = 3 (Luminance) for FocusMax use")  #!!!otherwise used whatever filter was in place, even Ha!!!!
    #vState.CAMERA.Filter = 3
    Log2(1,"@@@ Filter in use for FocusMax: %d, filter specified = %d" % (vState.CAMERA.Filter,vState.filter) )

    argExposure = float( dic["exp"] )
    argTarget   = dic["ID"]

    LogOnly("Exposure = " + str(argExposure))
    if argExposure > 1:
        Error("*****************************************************")
        Error("* WARNING: FOCUSMAX CALLED WITH EXPOSURE > 1 SECOND *")
        Error("*****************************************************")

    lastPosition = -1   #flag that not initially set
    retryAttempt =  5   #how many times we can try to get two results in a row
    success = False

    #2011.12.12 JU: having problem w/ FocusMax taking very long time (half an hour?) between
    # focus exposures and timing out here. Try issuing FocusMax Halt command and try again
    # when this happens.
    timeoutAttempts = 7

#Start of new section:
    while retryAttempt > 0:
        try:
           pos = str(vState.FOCUSER.Position)
        except:
           pos = '???'
        Log2(0,"FocusMax attempt starting, initial position: " + pos)
        retryAttempt -= 1

        #2017.05.07 JU: new feature: if current time is less than 5 minutes BEFORE LOCAL MIDNIGHT, sleep right now until after midnight.
        # There appears to be a bug in FocusMax where it hangs up if trying to run autofocus spanning midnight.
        now = datetime.datetime.now().time()
        if now.hour == 23 and now.minute >= 55:
            #go to sleep for 5 minutes (plus a little extra just to be sure)!
            Log2(0,"WARNING: running FocusMax over midnight can cause lockup")
            Log2(0,"Therefore, we will wait 5 minutes right not to be sure we do not start autofocus run")
            Log2(0,"until after local midnight passes.")
            Log2Summary(1,"FocusMax sleep briefly to avoid running at midnight!")
            time.sleep( (5*60) + 2)
            Log2(1,"Resuming FocusMax after waiting until past local midnight.")

#New section
        try:
            Log2(4,"Calling FocusMax FocusAsync()")
            imaging_db.RecordFocuser(vState,1033)
            vState.FOCUSCONTROL.FocusAsync()	#note: async call
            started = time.time()
            limit = 10*60   #10 minutes time limit for focusing to be really generous...
            while ((time.time() - started) < limit) and (vState.FOCUSCONTROL.FocusAsyncStatus == -1):
               time.sleep(1)
               imaging_db.RecordFocuser(vState,1034)

            imaging_db.RecordFocuser(vState,1035)
            if (vState.FOCUSCONTROL.FocusAsyncStatus == -1):		#did we exit the above loop from timeout (focus still running)?
               if timeoutAttempts > 0:
                   timeoutAttempts -= 1
                   Error("*** Timeout waiting for FocusMax calling FocusAsync(), try issuing Halt and trying again")
                   Log2Summary(1,"FocusMax timeout (2)")
                   if vState.FOCUSCONTROL.IsMoving:
                      imaging_db.RecordFocuser(vState,1236)
                      Error("*** ALERT!!! FOCUSER REPORTS THAT IT IS STILL MOVING!!!")
                   vState.FOCUSCONTROL.Halt()
                   Error("FocusMax Halt command issued.")
                   imaging_db.RecordFocuser(vState,1037)
                   vState.focus_failed_count += 1
                   line = "FocusMax     -fail/focus(TIMEOUT!!)-    %s" % argTarget
                   LogBase(line,FOCUSER_LOG)
                   LogPerm(line,PERM_FOCUSER_LOG)
                   continue

               Error("*** Timeout waiting for FocusMax FocusAsync() ***")
               imaging_db.RecordFocuser(vState,1138)
               Log2Summary(1,"FocusMax timeout (1)")
               line = "FocusMax     -fail/focus(TIMEOUTs!)-    %s" % argTarget
               LogBase(line,FOCUSER_LOG)
               LogPerm(line,PERM_FOCUSER_LOG)
               #note: I could call vState.FOCUSCONTROL.Halt() to stop the focus, but it might be better to leave this alone for debugging.
               ##SafetyPark(vState)
               ##raise SoundAlarmError
               raise WeatherError
            Log2(4,"FocusMax completed FocusAsync")
            if vState.FOCUSCONTROL.FocusAsyncStatus == 0:
               imaging_db.RecordFocuser(vState,1139)
               Error("...Unable to focus on star(3)")
               Log2Summary(1,"FocusMax unable to focus on star (error 3)")
               vState.focus_failed_count += 1
               line = "FocusMax     -fail/focus(excption3)-    %s" % argTarget
               LogBase(line,FOCUSER_LOG)
               LogPerm(line,PERM_FOCUSER_LOG)
               FocusCompensation(vState)   #move focuser to good location
               continue

        except SoundAlarmError: ##THIS NO LONGER HAPPENS, WE THROW WeatherError EXCEPTION INSTEAD
            imaging_db.RecordFocuser(vState,1370)
            Error("Caught exception in callFocusMax(), park scope then sound error")
            SafetyPark(vState)
            raise 	#re-raise this alarm; need to stop if this happens
        except:
            try:
               pos = str(vState.FOCUSER.Position)
            except:
               pos = '???'
            Error( "...Focus failed(exception): " + argTarget + ", FocusPosition: " + pos )
            niceLogExceptionInfo()
            imaging_db.RecordFocuser(vState,1271)
            line = "FocusMax     -fail/focus(exception)-    %s" % argTarget
            LogPerm(line,PERM_FOCUSER_LOG)
            vState.focus_failed_count += 1
            LogBase(line,FOCUSER_LOG)
            continue
#end of new section

        hfd = vState.FOCUSCONTROL.HalfFluxDiameter
        if hfd == 0:
            Error( "...Focus failed: " + argTarget )
            Log2Summary(1,"FocusMax failed")
            line = "FocusMax     -fail/focus-               %s" % argTarget    #failed: after focus step with Half Flux Diameter = 0
            vState.focus_failed_count += 1
            LogBase(line,FOCUSER_LOG)
            LogPerm(line,PERM_FOCUSER_LOG)
            FocusCompensation(vState)   #move focuser to good location
            continue

        if hfd > 15.0:
            #this is an unreasonably large size; it is very likely not really in focus
            Log2(0,"Unreasonably large star size; hfd = %6.2f; something may have interferred with focusing" % hfd)
            Log2Summary(1,"FocusMax unreasonable large star size: %6.2f" % 	hfd)
            #line = "BLOATED STAR?%6.2f  %3d %4d  %7d  %s  F=%d" % (
            line = "BLOATED STAR?%6.2f  %3d %4d  %7d  F=%d    %s" % (
               vState.FOCUSCONTROL.HalfFluxDiameter,
               vState.FOCUSER.Temperature,
               vState.FOCUSER.Position,
               vState.FOCUSCONTROL.TotalFlux,
               vState.CAMERA.Filter,argTarget)
            LogBase(line,FOCUSER_LOG)
            LogPerm(line,PERM_FOCUSER_LOG)
            FocusCompensation(vState)   #move focuser to good location
            imaging_db.RecordFocuser(vState,1072)
            continue

        if vState.FOCUSCONTROL.TotalFlux < 10000:
            #this is an unreasonably low value; it is very likely
            #that there is no star in this image (either clouds/trees,
            #or coord are wrong (happens)).
            Log2(0,"Unreasonably low flux during focus; probably no star here!")
            Log2Summary(1,"FocusMax low flux; probably no star here")
            #line = "MISSING STAR?%6.2f  %3d %4d  %7d  %s  F=%d" % (
            line = "MISSING STAR?%6.2f  %3d %4d  %7d  F=%d    %s" % (
               vState.FOCUSCONTROL.HalfFluxDiameter,
               vState.FOCUSER.Temperature,
               vState.FOCUSER.Position,
               vState.FOCUSCONTROL.TotalFlux,
               vState.CAMERA.Filter,argTarget)
            LogBase(line,FOCUSER_LOG)
            LogPerm(line + " **********",PERM_FOCUSER_LOG)
            FocusCompensation(vState)   #move focuser to good location
            imaging_db.RecordFocuser(vState,1073)
            return False

        currentAttempt = vState.FOCUSER.Position
        sTemp = str(vState.FOCUSER.Temperature)
        Log2(1,"Focus completed; HF dia: " + str(round(hfd,1)) + ", Temp: " + sTemp +
            ", Pos: " + str(currentAttempt) + ", F:" + str(vState.CAMERA.Filter) )
        Log2Summary(1,"FocusMax success star size: %6.2f, Position: %d" % (hfd,currentAttempt))

        #
        #2014.10.20 JU: logic change: if we have a focus result with HFD < 6.0, then just accept it, do not do another focus
        #
        fSkip = 0
        if hfd < 6.0:
            Log2(1,"New focus logic: attempt is 'good enough' so do not try another focus attempt")
            lastPosition = currentAttempt + 10  #this will cause the test below to assume success for multiple attempts, even though we didn't do that
            fSkip = 1


        if lastPosition < 0:
            lastPosition = currentAttempt    #this is the first time, need another pass before comparing.
            line = "FocusMax     %6.2f  %3d %4d  %7d  F=%d    %s" % (
               vState.FOCUSCONTROL.HalfFluxDiameter,
               vState.FOCUSER.Temperature,
               vState.FOCUSER.Position,
               vState.FOCUSCONTROL.TotalFlux,
               vState.CAMERA.Filter,argTarget)
            LogBase(line,FOCUSER_LOG)
            LogPerm(line,PERM_FOCUSER_LOG)
            continue

        diff = abs( currentAttempt - lastPosition)
        if diff < 50:    # <--- the threshold I chose for consistent results ***
            #-------------
            #- SUCCESS !!!
            #-------------
            if fSkip:
                Log2(1,"-->Completed! Single focus attempt good enough")
                Log2Summary(1,"FocusMax single focus attempt good enough")
                line = 'FocusMaxOnce %6.2f  %3d %4d  %7d  F=%d    "' % (
				   vState.FOCUSCONTROL.HalfFluxDiameter,
				   vState.FOCUSER.Temperature,
				   vState.FOCUSER.Position,
				   vState.FOCUSCONTROL.TotalFlux,
				   vState.CAMERA.Filter)
            else:
                Log2(1,"-->Completed! Two successive focus attempts consistent; diff: " + str(diff))
                Log2Summary(1,"FocusMax two successive focus attempts consistent by " + str(diff))
                line = '  "      OK  %6.2f  %3d %4d  %7d  F=%d    "' % (
				   vState.FOCUSCONTROL.HalfFluxDiameter,
				   vState.FOCUSER.Temperature,
				   vState.FOCUSER.Position,
				   vState.FOCUSCONTROL.TotalFlux,
				   vState.CAMERA.Filter)
            success = True

            LogBase(line,FOCUSER_LOG)
            LogPerm(line,PERM_FOCUSER_LOG)

            try:
                oldvalue = vState.LastFocusPosition
                vState.LastFocusPosition = vState.FOCUSER.Position
                vState.LastFocusTemperature = vState.FOCUSER.Temperature
                vState.FocusDataAvailable = True
                imaging_db.RecordFocuser(vState,1074)
                Log2(3,"Focuser results:")
                Log2(3,"  LastFocusPosition    = %d  (A) (was = %d)" % (vState.LastFocusPosition,oldvalue))
                Log2(3,"  LastFocusTemperature = %d" % vState.LastFocusTemperature)
                Log2(3,"  Filter               = %d" % vState.CAMERA.Filter)
            except:
                Log2(0,"Exception thrown trying to read initial Focus position/temperature")
                vState.FocusDataAvailable = False
                niceLogExceptionInfo()

            #write out current time and temperature to file LastFocus.dat
            global gLastFocus
            g = open( gLastFocus, "w")
            g.write("%d %d" % (time.time(), vState.FOCUSER.Temperature))
            g.close()

            global gFocusOccurredAt
            global gFocusPosition
            global gFocusTemperature

            global gFocusLastPosChange
            global gFocusLastTempChange

            gFocusOccurredAt = time.gmtime()

            if gFocusPosition == 0:
                #this is the first time, so use 0 for the change values
                gFocusLastPosChange = 0
                gFocusPosition = vState.FOCUSER.Position

                gFocusLastTempChange = 0
                gFocusTemperature = vState.FOCUSER.Temperature
            else:
                gFocusLastPosChange = vState.FOCUSER.Position - gFocusPosition
                gFocusPosition = vState.FOCUSER.Position

                gFocusLastTempChange = vState.FOCUSER.Temperature - gFocusTemperature
                gFocusTemperature = vState.FOCUSER.Temperature

            break       #this is good enough
        else:
            line = '  "     diff %6.2f  %3d %4d  %5d' % (
               vState.FOCUSCONTROL.HalfFluxDiameter,
               vState.FOCUSER.Temperature,
               vState.FOCUSER.Position,
               vState.FOCUSCONTROL.TotalFlux)
            LogBase(line,FOCUSER_LOG)
            LogPerm(line,PERM_FOCUSER_LOG)
            lastPosition = currentAttempt    #use current value for next compare


    if not success:
       Error("-->Warning: FOCUS not successful or not consistent")
       Log2Summary(1,"FocusMax not successful or not consistent")
       line = "FocusMax     -fail/exceeded retries-    %s" % argTarget
       LogBase(line,FOCUSER_LOG)
       LogPerm(line,PERM_FOCUSER_LOG)
       FocusCompensation(vState)   #move focuser to good location

       #we failed to focus on this star after several attempts;
       # has the same thing happened on the past few stars?
       excessiveFocusRetries += 1
       if excessiveFocusRetries > 3:
           #if can't focus after 3 times in a row for different stars, something is wrong
           Error("!!! STOP: unable to focus 3 times in a row with different stars; something is wrong!!!")
           Log2Summary(1,"FocusMax unable to focus after 3 attempts; assume weather problem")
           #Error("!!! Stopping program because of consistent focus failure !!!")
           ##SafetyPark(vState)
           ##raise SoundAlarmError,'Halting program'
           imaging_db.RecordFocuser(vState,1375)
           raise WeatherError
       return False
    else:
       #it worked fine; record the focus position and temperature for use with Temp Compensation
       #global excessiveFocusRetries
       excessiveFocusRetries = 0
       time.sleep(2)    #make sure to settle from focuser movement before doing imaging
       try:
          vState.TempMeasureTime = time.time()
##          vState.TempCompPosition = vState.FOCUSER.Position
##          vState.TempCompTemperature = vState.FOCUSER.Temperature
       except:
          niceLogExceptionInfo()
          Error("Hey! I threw an exception trying to turn on temp comp")

    #del vState.FOCUS

    if CalibrateImagerOffset(dic["ID"],vState):
        #the guider image does not appear to have the brightest pixel
        #within the center 100x100 pixels of its frame. But we already
        #ran FocusMax and it appeared to succeed, so there is probably
        #a bright star in the center. As long as it is the brightest star
        #within the IMAGER FOV, then we are OK. Assume it is OK, so
        #do not report an error.
        Log(0,"**Guider bright pixel not centered, but since FocusMax apparently worked we are goiung to continue as if everything is OK.")
        pass

    #Don't need flush here; imager always does flush before image now.

    return True

#--------------------------------------------------------------------------------------------------------
def BrightStarFilename(starname,vState):
    #use pathPinpoint to store these?
    monthday = ""
    temp = ObservingDateString()
    monthday = temp[4:] + "_"
    #print "monthday = %s" % monthday
    #monthday = time.strftime("%m%d_", time.gmtime( time.time() ) )
    root = "Bright_" + starname + "_" + monthday
    seq = GetSequenceNumber(pathPinpoint, root) + 1  #the +1 is to use next AVAILABLE number
    fullname = ('%s%s%05d.fts') % (pathPinpoint,root,seq)
    return fullname

def WideBrightStarFilename(starname,vState):
    #use pathPinpoint to store these?
    monthday = ""
    temp = ObservingDateString()
    monthday = temp[4:] + "_WIDE_"
    #print "monthday = %s" % monthday
    #monthday = time.strftime("%m%d_WIDE_", time.gmtime( time.time() ) )
    root = "Bright_" + starname + "_" + monthday
    seq = GetSequenceNumber(pathPinpoint, root) + 1  #the +1 is to use next AVAILABLE number
    fullname = ('%s%s%05d.fts') % (pathPinpoint,root,seq)
    return fullname

#--------------------------------------------------------------------------------------------------------
def CalibrateImagerOffset(starname,vState):
    #Log2(3,"Disabled: CalibrateImagerOffset")
    return False


def CalculateImagerRaDecOffset(desiredPos,vState):  #THIS IS NOT USED
    #for the specified position, this calculates the RA/Dec position
    #that the *GUIDER* needs to be centered at, so that the imager
    #is really centered at the desired position; this uses the previously
    #measured (current) offset between the imager and guider

    #which side of meridian will this be on? Do we need to invert offsets?
    # -->if offset measured on same side of meridian as target, don't need to consider this!
    #assume the imager is at 0 deg rotation always?
    #???
    dRA,dDec = desiredPos.getJ2000Decimal()

    #note that offsets are in pixels; convert to arcseconds by multiplying by imageScale
    #and then convert to RA time value (adjusted for declination), and Dec degrees
    RAoff = ((float(vState.X_offset) * vState.ImagerScale * 24.) / (60. * 60. * 360.)) / cosd(dDec)
    DECoff = (vState.Y_offset * vState.ImagerScale) / (60. * 60.)

    #if vState.MOUNT.SideOfPier == 1:
    if SideOfSky(vState) == 1:
        RAcorr = dRA + RAoff        #for west of Pier
        DECcorr = dDec + DECoff
    else:
        RAcorr = dRA - RAoff        #for east of Pier
        DECcorr = dDec - DECoff

    Log2(0,"Correction amounts for Imager/Guider offset:")
    Log2(0,"RAoff = %5.2f seconds, DECoff =%5.2f arcsec" % (RAoff * 3600., DECoff * 3600.))

    newPos = Position()
    newPos.setJ2000Decimal(RAcorr,DECcorr)
    return newPos

#=====================================================================================
#==== SECTION @@FOCUS ================================================================
#=====================================================================================
def execNearAutoFocus(dic,vState):
   #vState.ResetImagerOffset()   #forces positioning to center in guider

   #build dic2 object for CatFocusNear() for current location
   dic2 = {}
   dic2["type"]       = "focus"
   dic2["location"]   = "nearcurrent"
   dic2["camera"]     = "Guider"
   dic2["isSeq"]      = "no"
   dic2["PP-Solve"]   =  1
   dic2["limit"]      = "count"
   dic2["type"]       = "light"
   dic2["ID"]         = "Nearby Focus Star"
   dic2["exp"]        = 10
   dic2["repeat"]     = 1
   dic2["bin"]        = 1
   dic2["filter"]     = 'L'
   return implAutoPickFocus(dic2,vState)

def implFocus(dic,vState):
    if not vState.focusEnable:
       Log2(2,"Focusing disabled, so nothing done for focus step")
       return (0,)  #do nothing, report success

    dic["camera"] = "imager"
    return implExp(dic,vState)

def FocusCompensation(vState):
    #move focuser based on temp change from last focus, if configured to do so!
    if vState.FocusCompensationActive == 0:
        Log2(6,"Inactive FocusCompensation(); nothing to do.")
        return

    if vState.FocusCompensationActive == 3 and vState.AdvancedFocusState == 0:
        Log2(6,"Benchmark focus has not occurred yet, nothing to do for FocusCompensation")
        return

    Log2(6,"Checking FocusCompensation()")
    if not vState.FocusDataAvailable:
        Log2(0,"ERROR: FocusCompensation() called but initial focus data not available")
        return

    try:
      if not vState.FOCUSER.Absolute:
        Error("*Focuser not able to do Absolute positioning, so cannot do Temperature Compensation")
        return
    except:
      Error("*Focuser threw exception trying to access property vState.FOCUSER.Absolute !!!")
      niceLogExceptionInfo()
      return

    try:
        currentFocusTemperature = vState.FOCUSER.Temperature    #this can change suddenly, so grab fixed value for it

        Log2(6,"Last focuser position             = %d" % vState.LastFocusPosition)
        Log2(6,"Current reported focuser position = %d" % vState.FOCUSER.Position)
        Log2(6,"Last temperature                     = %d" % vState.LastFocusTemperature)
        Log2(6,"Current reported focuser temperature = %d" % currentFocusTemperature)

        tempDiff = currentFocusTemperature - vState.LastFocusTemperature

		#2015.04.29 JU: removed test for zero temp diff, and instead move focuser if it isn't where we want it to be
        #if tempDiff == 0:
        #    Log2(6,"No temperature change; nothing to do. Finished FocusCompensation()")
        #    return

        posDiff = int(tempDiff * vState.FocusSlope)

		#2016.08.15 JU: change this logic to adjust focuser based on CURRENT position, which might be different from LastFocusPosition if filter changed and MaximDL adjusted for filter focus difference
        newPos = posDiff + vState.FOCUSER.Position	##vState.LastFocusPosition

        if vState.FOCUSER.Position == newPos:
            Log2(6,"Focuser already at desired location; nothing to do. Finished FocusCompensation()")
            return

        Log2(2,"About to reposition focuser from %d to %d, based on temperature diff: %d " % (vState.FOCUSER.Position,newPos,tempDiff))
        Log2(2,"Position before movement = %d, old temperature = %d" % (vState.FOCUSER.Position,vState.LastFocusTemperature))
        vState.FOCUSER.Move( newPos )
        time.sleep(3)    #give scope a chance to settle after focuser movement
        Log2(2,"Position after movement  = %d, now temperature = %d" % (vState.FOCUSER.Position,currentFocusTemperature))

        #2010/04/09 22:08:39 Focus Comp     n/a   999 9999    n/a    n/a
        #line = "Focus Comp     n/a   %3d %4d    n/a    n/a  F:%d" % ( currentFocusTemperature, newPos,vState.CAMERA.Filter)
        line = "Focus Comp     n/a   %3d %4d    n/a    F=%d    n/a" % ( currentFocusTemperature, newPos,vState.CAMERA.Filter)

        if vState.FOCUSER.Position != newPos:
            Error("********************************************************")
            Error("*Focuser did not arrive at desired position! %d vs %d" % (vState.FOCUSER.Position,newPos))
            Error("********************************************************")
            line += "  *Focuser did not arrive at desired position! %d vs %d" % (vState.FOCUSER.Position,newPos)
        vState.LastFocusTemperature = currentFocusTemperature
        oldvalue = vState.LastFocusPosition
        vState.LastFocusPosition = vState.FOCUSER.Position		#newPos

        Log2(3,"  LastFocusPosition    = %d (C)  (was = %d)" % (vState.LastFocusPosition,oldvalue))
        Log2(3,"  LastFocusTemperature = %d" % vState.LastFocusTemperature)
        Log2(3,"  Filter               = %d" % vState.CAMERA.Filter)

        LogBase(line,FOCUSER_LOG)
        LogPerm(line,PERM_FOCUSER_LOG)
        Log2(6,line)

    except:
        Log2(0,"ERROR: exception thrown in FocusCompensation()")
        niceLogExceptionInfo()

    Log2(6,"Finished FocusCompensation()")


#=====================================================================================
#==== SECTION  @@execImpl ============================================================
#=====================================================================================
#this section expects 'valid' input parameters; no checking is done here

#--------------------------------------------------------------------------------------------------------
#dic["type"] = "Flat" take flat frames
#   add ADU limits, camera selection, exposure limit, altitude setting when I get better idea of how it works
#
# Design:
#   #set values based on running in morning or evening
#   if morning set desiredAlt = -5, initial exp = 2sec ?, desiredADU = targetADU - range, filterOrder = LBRG ?, binOrder = 1,2,2,2
#   else       set desiredAlt = -2, initial exp = 0.1 sec?, desiredADU = targetADU + range, filterOrder = GRBL ?, binOrder=2,2,2,1
#   while True:     #wait for sun to reach reasonable altitude
#       alt = get Sun Altitude
#       if (morning and alt >= desiredAlt) or (evening and alt <= desiredAlt): break
#       else sleep(1 minute)
#   while True:     #now wait for sky brightness to reach desired level
#       set filter = filterOrder[0]
#       set binning = binOrder[0]
#       expose image using initialExp time
#       if (morning and ADU <= desiredADU) or (evening and ADU >= desiredADU): break
#       else sleep(1 minute)
#   Take flat images, adjust exposure times if necessary

def implFlat(dic,vState):
    #flush camera, based on camera
    dic["camera"] = "imager"
    ClearImager(dic,vState)

    #park scope if we end up waiting here
    parked = False

    idealADU = 25000
    rangeADU =  5000
    #is this evening or morning (decides order and initial hint)
    #if time is between 6h and 18h GMT (midnight to noon local), consider it morning, else evening
    #set values based on running in morning or evening
#   if morning set desiredAlt = -5, initial exp = 2sec ?, desiredADU = targetADU - range, filterOrder = LBRG ?, binOrder = 1,2,2,2
#   else       set desiredAlt = -2, initial exp = 0.1 sec?, desiredADU = targetADU + range, filterOrder = GRBL ?, binOrder=2,2,2,1
    tup = time.gmtime()
    gmtHours = tup[3]
    if gmtHours > 6 and gmtHours < 18:  #values based on my longitude
        #morning
        evening = False
        #desiredAlt = -4     #2009.05.19: change from -5 to -4; was seeing stars in flat images
        #desiredAlt = -3.5   #2009.05.21: change again, was still seeing a couple of stars in some images
        #desiredAlt = -2.5   #2009.05.31: change again; still seeing stars
        #desiredAlt = -3.0    #2010.07.30: want more time because QSI frames download slow (very large)

        #desiredAlt = -3.3    #2010.08.16: start earlier because some exposures near short limit
        #           = -4.5    too early w/ QSI on AT66, getting stars
        desiredAlt = vState.FlatAltitudeMorning

        #desiredWideAlt = -4  # <<-- 2009.11.06: setting for WIDE field flats
        desiredWideAlt = -4.5  # <<-- 2009.11.22: change to start slightly earlier; exposures were getting so short there might be a problem if needed to be any shorter
        initialExp = 1.0
        thresholdADU = idealADU - rangeADU
        filterOrder = (3,2,0,1)     #LBRG  (check this)
        binOrder    = (1,2,2,2) #not used
    else:
        #evening  (I've never used this)
        evening = True
        #desiredAlt = -2     #adjust this??
        desiredAlt = vState.FlatAltitudeEvening
        desiredWideAlt = -4
        initialExp = 0.1    #adjust this??
        thresholdADU = idealADU + rangeADU
        filterOrder = (1,0,2,3)     #GRBL  (check this)
        binOrder    = (2,2,2,1) #not used

    #target of slew to desired location in sky
    if evening:
       azimuth = 90  #point towards east if evening
    else:
       azimuth = 270 #etc

    #--------------------------------------------
    #wait for the sun to reach the desired height
    #(if it isn't at the desired height initially, park the
    # telescope to make sure it is safe)

    bTakeWideFlat = False  ##True
    bTakeNarrowFlat = True
    while bTakeWideFlat or bTakeNarrowFlat:
       time.sleep(10)
       #this can wait a VERY LONG TIME

       #what is sun's current altitude?
       tup = time.gmtime(time.time())
       mYear  = tup[0]
       mMonth = tup[1]
       mDay   = tup[2]
       utc    = float(tup[3]) + (float(tup[4])/60.) + (float(tup[5])/3600.)
       alt = CalcSolarAlt(mYear,mMonth,mDay,utc,myLongitude,myLatitude)

       #report which type of flat will be taken first while we are waiting
       if evening:
           #narrow flat before wide
           if bTakeNarrowFlat:
               #report waiting for narrow
               bCurrentlyReportingNarrow = True
           else:
               #report waiting for wide
               bCurrentlyReportingNarrow = False
       else:
           #wide flat before narrow
           if bTakeWideFlat:
               #report waiting for wide
               bCurrentlyReportingNarrow = False
           else:
               #report waiting for narrow
               bCurrentlyReportingNarrow = True

       if bCurrentlyReportingNarrow:
           #report narrow
           Log2(2,"Solar altitude = %5.2f, desired/narrow = %5.2f" % (alt,desiredAlt))
       else:
           #report wide
           Log2(2,"Solar altitude = %5.2f, desired/Wide = %5.2f" % (alt,desiredWideAlt))

       if bTakeNarrowFlat:
          if (evening and (alt <= desiredAlt)) or (not evening and (alt >= desiredAlt)):
            bTakeNarrowFlat = False
            #-------------------------------------
            #implFlatNarrow(azimuth,dic,vState)
            #run the Narrow flat sequence right now
            if not vState.MOUNT.Connected:
               vState.MOUNT.Connected = True
            if vState.MOUNT.AtPark:
               Log2(3,"Unparking mount")
               vState.MOUNT.Unpark()
            else:
                Log2(3,"Mount currently NOT parked, ready for motion")

            vState.MOUNT.Tracking = False   #turn off tracking
            Log2(3,"Slewing mount to near zenith to take flat exposures...")
            vState.MOUNT.SlewToAltAz(azimuth,80)     #close to ideal spot in the sky for flat field
            Log2(3,"...mount positioned.")

            #ready to start flats narrow
            Log2(2,"Starting actual Flats/Narrow exposures now")

            if not evening:
               #Morning: dim initially so expose filter order: bright -> dim

               #2010.08.07 JU: restrict the flats taken to the ones I need:
               #   R,G,B    2x2
               #   Lum, Ha  1x1

               #!Adjust for QSI camera use??
               Log2(1,"    ")
               Log2(1,"Binned Flats========================================")
               Log2(1,"    ")
               hint = initialExp

               #NOTE: for QSI on AT66 f/6 refractor for wide field imaging,
               # I want LRGB & Ha all binned 2x2

               hint = ExposeFlat(idealADU, rangeADU, hint, 15, 3, 2, "Flat_L_2x2_", vState)   #3=L
               if hint == 0:
                  Log2(2,"Stoping after L b2x2 flats --morning")
                  return (0,)

               hint = ExposeFlat(idealADU, rangeADU, hint, 15, 2, 2, "Flat_B_2x2_", vState)   #2=B
               if hint == 0:
                  Log2(2,"Stoping after B b2x2 flats --morning")
                  return (0,)

               hint = ExposeFlat(idealADU, rangeADU, hint, 15, 0, 2, "Flat_R_2x2_", vState)   #0=R
               if hint == 0:
                  Log2(2,"Stoping after R b2x2 flats --morning")
                  return (0,)

               hint = ExposeFlat(idealADU, rangeADU, hint, 15, 1, 2, "Flat_G_2x2_", vState)   #1=G
               if hint == 0:
                  Log2(2,"Stoping after G b2x2 flats --morning")
                  return (0,)

               hint = hint * 2  #Ha needs longer
               hint = ExposeFlat(idealADU, rangeADU, hint, 15, 4, 2, "Flat_Ha_2x2_", vState)   #1=G
               if hint == 0:
                  Log2(2,"Stoping after Ha b2x2 flats --morning")
                  return (0,)

               Log2(1,"Note: coded to skip unbinned flats")
##               Log2(1,"    ")
##               Log2(1,"Unbinned Flats========================================")
##               Log2(1,"    ")
##               #going from Ha binned to L non-binned, so leave hint alone
##               hint = ExposeFlat(idealADU, rangeADU, hint, 15, 3, 1, "Flat_L_1x1_", vState)   #1=G
##               if hint == 0:
##                  Log2(2,"Stoping after L 1x1 flats --morning")
##                  return (0,)

##               hint = ExposeFlat(idealADU, rangeADU, hint, 5, 2, 1, "Flat_B_1x1_", vState)   #2=B
##               if hint == 0:
##                  Log2(2,"Stoping after B 1x1 flats --morning")
##                  return (0,)
##
##               hint = ExposeFlat(idealADU, rangeADU, hint, 5, 0, 1, "Flat_R_1x1_", vState)   #0=R
##               if hint == 0:
##                  Log2(2,"Stoping after R 1x1 flats --morning")
##                  return (0,)
##
##               hint = ExposeFlat(idealADU, rangeADU, hint, 5, 1, 1, "Flat_G_1x1_", vState)   #1=G
##               if hint == 0:
##                  Log2(2,"Stoping after G 1x1 flats --morning")
##                  return (0,)

##               hint = hint * 2  #Ha needs longer
##               hint = ExposeFlat(idealADU, rangeADU, hint, 15, 4, 1, "Flat_Ha_1x1_", vState)   #1=G

            else:
               #Evening: bright initially so expose filter order: dim -> bright
               # (NEVER USED)
               hint = initialExp

               hint = ExposeFlat(idealADU, rangeADU, hint, 5, 4, 2, "Flat_Ha_2x2_", vState)   #1=G
               if hint == 0:
                  Log2(2,"Stoping after Ha flats --evening")
                  return (0,)

               hint = ExposeFlat(idealADU, rangeADU, hint, 5, 1, 2, "Flat_G_2x2_", vState)   #1=G
               if hint == 0:
                  Log2(2,"Stoping after G flats --evening")
                  return (0,)

               hint = ExposeFlat(idealADU, rangeADU, hint, 5, 0, 2, "Flat_R_2x2_", vState)   #0=R
               if hint == 0:
                  Log2(2,"Stoping after R flats --evening")
                  return (0,)

               hint = ExposeFlat(idealADU, rangeADU, hint, 5, 2, 2, "Flat_B_2x2_", vState)   #2=B
               if hint == 0:
                  Log2(2,"Stoping after B flats --evening")
                  return (0,)

               hint = ExposeFlat(idealADU, rangeADU, hint, 5, 3, 2, "Flat_L_2x2_", vState)   #3=L
            #--(end of narrow flats)-----------------------------------

       #while waiting for correct sun height for main imager, also check for desired
       # height for wide field (guide) camera and run that series at some point.

       if bTakeWideFlat:
           if (evening and (alt <= desiredWideAlt)) or (not evening and (alt >= desiredWideAlt)):
               bTakeWideFlat = False    #only do this once
               if not vState.MOUNT.Connected:
                  vState.MOUNT.Connected = True
               if vState.MOUNT.AtPark:
                   vState.MOUNT.Unpark()
               vState.MOUNT.Tracking = False   #turn off tracking
               Log2(3,"Slewing mount to near zenith to take WIDE flat exposures...")
               vState.MOUNT.SlewToAltAz(azimuth,80)     #close to ideal spot in the sky for flat field
               Log2(3,"...mount positioned.")
               #parked = False
               Log2(2,"Starting actual Flats/Wide exposures now")
               ExposeWideFlat(20000, 5000, 0.5, 20, "WideFlat_L_1x1_", vState)

       if bTakeWideFlat or bTakeNarrowFlat:
           #only park the scope after we've gone through the loop the first time
           # and still have work to do, in case we it is already past the start
           # time; don't want to waste extra time parking and make us even later.
           #(After we take the first flats, don't bother reparking the scope.)
           if not parked:
              Log2(3,"Park scope while waiting...")
              execPark((0,),vState)
              parked = True

    Log2(2,"Flats completed")
    Log2(3,"Park scope after Flats...")
    execPark((0,),vState)

    return (0,)

#--------------------------------------------------------------------------------------------------------
#dic["type"] = "Bias" take bias frames (no sequence supported here); only works w/ Imager, not guider (no shutter)
#   dic["bin"] = 1,2,3; maybe more depending on camera?
#   dic["repeat"] = number of repetitions of exposure
def implBias(dic,vState):
    Log2(0," ")
    Log2(0,"-------------------------------------------------------------")
    Log2(0,"*** Bias exposure(s)    " + str(dic))

    #define variables to hold all the arguments
    argRepeat     = dic["repeat"]
    argBin        = dic["bin"]
    dic["camera"] = "imager"

    argFileName   = "Bias_%dx%d_" % (argBin,argBin)         #  base filename WITHOUT the trailing 5 seq digits.

    ClearImager(dic,vState)
    vState.CAMERA.BinX = 1  #make sure no rounding for Full Frame
    vState.CAMERA.BinY = 1
    vState.CAMERA.SetFullFrame()
    vState.CAMERA.BinX = argBin
    vState.CAMERA.BinY = argBin

    if dic["crop"] == "yes":
        tupc = CalcCropSize(dic["bin"],vState.CAMERA.cameraXSize,vState.CAMERA.cameraYSize)
        vState.CAMERA.StartX = tupc[0]
        vState.CAMERA.StartY = tupc[1]
        vState.CAMERA.NumX = tupc[2]   #NumX,NumY can be shortened if they won't fit in the available image size
        vState.CAMERA.NumY = tupc[3]
        Log2(4,"Cropping settings:")
        Log2(4,"   bin = %d" % dic["bin"])
        Log2(4,"   StartX = %d" % tupc[0])
        Log2(4,"   StartY = %d" % tupc[1])
        Log2(4,"   NumX = %d" % tupc[2])
        Log2(4,"   NumY = %d" % tupc[3])
    else:
        vState.CAMERA.BinX = argBin
        vState.CAMERA.BinY = argBin
        vState.CAMERA.SetFullFrame()

    for i in range(argRepeat):
        filename_i = CreateFilename(vState.path_dark_bias_flat, argFileName,vState,argRepeat)
        if i == 0:  #just log on console this 1st time here
            Log2(0, "Bias: Repeats: %d  Bin: %dx%d  %s" %
                 (argRepeat, argBin,argBin,filename_i))

        LogOnly("Begin exposure #" + str(i+1) )
        vState.CAMERA.Expose( 0, 0, 3 )   # 0=zero expousre, 0 = dark frame; 3=L filter (doesn't do anything here)

        #wait for exposure to complete
        LogStatusHeaderBrief()
        while not vState.CAMERA.ImageReady:
            time.sleep(1)
            #DO NOT WANT TO CALL THIS FOR BIAS:  LogStatus(vState)
        LogOnly("Bias exposure complete for: " + filename_i)

        #save the image  [do NOT save RA/Dec in FITS header for dark frame]
        vState.CAMERA.Document.SetFITSKey("IMAGETYP","BIAS")
#        vState.CAMERA.Document.SetFITSKey("XBINNING","%d" % argBin)
#        vState.CAMERA.Document.SetFITSKey("YBINNING","%d" % argBin)
        # ??also set CCD-TEMP ??
        vState.CAMERA.SaveImage(filename_i)

    return (0,)

#--------------------------------------------------------------------------------------------------------
#dic["type"] = "Dark" take dark frames (only w/ imager for now)
#   dic["camera"] = "Imager"  (required/assumed value)
#   dic["isSeq"] = "yes"
#       dic["seq"] = name of sequence file, assume Darks only! assume path C:\fits_seq unless name includes path
#   dic["isSeq"] = "no"
#       dic["bin"] = 1,2,3; maybe more depending on camera?
#       dic["exp"] = exposure time decimal seconds
#       dic["repeat"] = number of repetitions of exposure
def implDarks(dic,vState):
    Log2(0," ")
    Log2(0,"-------------------------------------------------------------")
    Log2(0,"*** Dark exposure(s)    " + str(dic))

    dic["camera"] = "imager"
    ClearImager(dic,vState)

    if runMode == 3:
       return (0,)   #skip in testing mode

    #2012.07.29 JU: changed altitude limit from -6 to -3, to see if QSI camera is OK with this for darks
    if TestSunAltitude(-3):
        return(0,)  #sun is too high to run this step

    if dic["isSeq"] == "yes":
       #
       #Take dark exposures via sequence
       #(we ASSUME the specified sequence is just for darks)
       argSequence = dic["seq"]
       LogOnly("Sequence file: %s" % argSequence)
       vState.CAMERA.StartSequence( argSequence )
       while vState.CAMERA.SequenceRunning:
            time.sleep(2)   #wait until this ends
            #decide if need to stop for skip ahead event
            if TestSunAltitude(-3): #stop darks if sun gets too high
                vState.CAMERA.AbortExposure()
                return (0,)

    else:
       #
       #Take individual dark exposures here

       #define variables to hold all the arguments
       argExposure   = dic["exp"]
       argRepeat     = dic["repeat"]
       argBin        = dic["bin"]

       #format: Dark_1x1_150sec_
       argFileName   = "Dark_%dx%d_%dsec_" % (argBin,argBin,argExposure)         #  base filename WITHOUT the trailing 5 seq digits.

       try:
            vState.CAMERA.BinX = 1    #make sure no rounding for Full Frame
            vState.CAMERA.BinY = 1
            vState.CAMERA.SetFullFrame()
            vState.CAMERA.BinX = argBin
            vState.CAMERA.BinY = argBin

            if dic["crop"] == "yes":
                tupc = CalcCropSize(dic["bin"],vState.CAMERA.cameraXSize,vState.CAMERA.cameraYSize)
                vState.CAMERA.StartX = tupc[0]
                vState.CAMERA.StartY = tupc[1]
                vState.CAMERA.NumX = tupc[2]   #NumX,NumY can be shortened if they won't fit in the available image size
                vState.CAMERA.NumY = tupc[3]
                Log2(4,"Cropping settings:")
                Log2(4,"   bin = %d" % dic["bin"])
                Log2(4,"   StartX = %d" % tupc[0])
                Log2(4,"   StartY = %d" % tupc[1])
                Log2(4,"   NumX = %d" % tupc[2])
                Log2(4,"   NumY = %d" % tupc[3])
            else:
                vState.CAMERA.BinX = argBin
                vState.CAMERA.BinY = argBin
                vState.CAMERA.SetFullFrame()


       except:
          pass

       for i in range(argRepeat):
           filename_i = CreateFilename(vState.path_dark_bias_flat, argFileName,vState,argRepeat)
           Log2(0, "Dark: %3.1f  Repeats: %d  Bin: %dx%d  %s" %
                        (argExposure, argRepeat, argBin,argBin,filename_i))

           LogOnly("Begin exposure #" + str(i+1) )
           vState.CAMERA.Expose( argExposure, 0, 3 )   # 0 = dark frame; 3=L filter (doesn't do anything here)

           #wait for exposure to complete
           LogStatusHeaderBrief()
           while not vState.CAMERA.ImageReady:
                   time.sleep(1)
                   #LogStatus(vState)
                   #I do not need to log status during Dark exposure!

                   if TestSunAltitude(-6): #stop darks if sun gets too high
                        vState.CAMERA.AbortExposure()
                        return (0,) #continue w/ next step
           LogOnly("Dark exposure complete for: " + filename_i)

               #save the image  [do NOT save RA/Dec in FITS header for dark frame]
           vState.CAMERA.Document.SetFITSKey("IMAGETYP","DARK")
#           vState.CAMERA.Document.SetFITSKey("XBINNING","%d" % argBin)
#           vState.CAMERA.Document.SetFITSKey("YBINNING","%d" % argBin)
           # ??also set CCD-TEMP ??
           vState.CAMERA.SaveImage(filename_i)
           StatusLog(filename_i)

    return (0,) #OK to continue w/ next step

#--------------------------------------------------------------------------------------------------------
#Helper function: when MaxIm saves images in a sequence, it uses an object name
# that was set through the GUI (and I can't find a way to chance this from my script),
# so instead, after the sequence is done, I'll open all the images just written by
# the sequence and update their headers here. I determine the list of image files by
# comparing the current directory contents to the list before the sequence was run,
# to find which files are new.
def FixSequenceHeaders(objName,beforeList,vState):
    LogOnly("Updating FITS headers for images just taken in sequence")
    afterList = os.listdir( vState.path )
    for afterFile in afterList:
        try:
            #Reference:  http://dev.ionous.net/2009/01/python-find-item-in-list.html
            #Use a Python 'generator expression' to search for list inclusion;
            # An exception is thrown if the afterFile name is NOT found in beforeList:
            (i for i in beforeList if i == afterFile).next()
            #getting here means the file that is in afterList was also in beforeList, so ignore it
            continue
        except:
            #getting here means the file is new so we want to process it
            try:
             if 0: #THIS DOES NOT WORK YET
                #if this isn't a FITS file, it should throw an exception to skip it
                #open the file
                pathfile = os.path.join(vState.path,afterFile)

                if not os.access(pathfile,os.F_OK): #test for now:
                    LogOnly("os.access reports that this file does NOT exist: %s" % pathfile)
                if not os.access(pathfile,os.R_OK): #test for now:
                    LogOnly("os.access reports that this file is NOT readable: %s" % pathfile)
                if not os.access(pathfile,os.W_OK): #test for now:
                    LogOnly("os.access reports that this file is NOT writable: %s" % pathfile)

                doc = vState.MAXIMDOC.OpenFile(pathfile)
                LogOnly("Opened FITS file %s" % (pathfile))
                #set the FITS object keyword
                doc.SetFITSKey("OBJECT",objName)
#the above line causes this exception:
#23:56:32 --------------------------------------------------
#23:56:32 |             General Exception                  |
#23:56:32 --------------------------------------------------
#23:56:32 Call trace (most recent call last):
#23:56:32   File "C:\fits_script\Exec3.py", line 8399, in FixSequenceHeaders
#    doc.SetFITSKey("OBJECT",objName)
#23:56:32 vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
#23:56:32 > AttributeError
#23:56:32 >
#23:56:32 > 'NoneType' object has no attribute 'SetFITSKey'
#23:56:32 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#Problem: Document.OpenFile() does NOT return a document object; it returns 'None'

                #save the change back to original image file:, 16bit, not compressed, not autostretched
                doc.SaveFile( pathfile, 3, False, 1 )
                LogOnly("Saved FITS file %s" % (pathfile))
                #close the file
                doc.Close()
                LogOnly("Updated FITS Object entry to %s for file %s" % (objName,afterFile))

#maybe the following would work?
                vState.MAXIMDOC.SetFITSKey("OBJECT",objName)
                vState.MAXIMDOC.SaveFile( pathfile, 3, False, 1 )
                vState.MAXIMDOC.Close()

            except:
                try:
                    niceLogExceptionInfo()
                except:
                    LogOnly("Unable to niceLogExceptionInfo for FITS Object keywork problem")
                LogOnly("Did not update FITS Object keyword to %s for this file: %s" % (objName,pathfile))
    LogOnly("Completed updating FITS headers")

#--------------------------------------------------------------------------------------------------------
#dic["type"] = "Light"
#   dic["camera"] = "Imager"
#       dic["isSeq"] = "yes"
#           dic["seq"] = name of sequence file; Includes path (usually C:\fits_seq); path must be specified
#       dic["isSeq"] = "no"
#           dic["bin"] = 1,2,3; maybe more depending on camera?
#           dic["filter"] = "L","R","G","B","Ha"...; default to "L" if not specified
#           dic["exp"] = exposure time decimal seconds
def implImagerExposure(index,dic,vState):
    #Take a single Imager exposure or single Imager sequence
    # Inputs:
    #   index = number of images/sequences taken of current target (may not need this here)
    #   assume scope positioned as desired, and guiding already running if desired
    # Different possible outcomes:
    #   exposure completed normally  (0,)
    #   exposure completed but meridian reached (0,)
    #   exposure completed but skip-ahead detected (1,999)
    #   exposure interrupted by meridian reached (0,)
    #   exposure interrupted by skip-ahead detected (1,999)
    #   error; stop script (2,)
    # Return tuple:  (state,skipAheadStep)
    #   where exposure: 0=exposure normal completion
    #                   1=skip ahead
    #                   2=error, stop script
    #         skipAheadStep: number = step to skip ahead to (only for state = 1)
    #
    # This code may detect a meridian limit, or a skipAhead condition
    #  and abort the exposure/sequence. A meridian limit condition is NOT
    #  explicitly returned; it is up to the caller to detect it.
    #
    #This may also detect a focuser temperature change and move the focuser
    # to compensate (no mount movement, just the focuser).

    FocusCompensation(vState)     #moves focuser if temperature has changed (and if enabled)

    #add check here that guiding has settled!
    #if doing several single exposures at bin 1x1, the download of the last image
    # can take 20 seconds, during which time the guider doesn't run. Make sure
    # the guider is back on target before proceeding here.
    #(what if guiding bad? stop current image?)

    if dic["isSeq"].lower() == "yes":
        #run sequence------------------------------------------
        Log2(0, "Sequence: %s, ID: %s" % (dic["seq"],dic["ID"]))
        if runMode == 3:
           return (0,)     #skip rest if testing

        #re-settle guiding at the start of each sequence
        if SettleGuiding(vState):
            #problem settling guiding
            vState.CAMERA.AbortExposure()
            if RecoverFromBadGuiding(dic,vState):
                return (2,)     #problem; unable to recover

        #2009.05.20 JU added back in base filename for sequence
        monthday = ""
        temp = ObservingDateString()
        monthday = "_" + temp + "_" # time.strftime("_%Y%m%d_", time.gmtime( time.time() ) )
        #print "monthday = %s" % monthday
        sequenceBaseFilename = vState.path + dic["ID"] + monthday
        vState.CAMERA.SequenceBaseFilename = sequenceBaseFilename

        #2010.05.15 JU: get list of all the files currently in the output directory
        #               (probably C:\Fits) and save this list; later we'll get a new
        #               list and do a difference to determine which files were written
        #               by this sequence call, so we can fix their FITS header entry
        #               for OBJECT.
        beforeList = os.listdir( vState.path )

        LogOnly("Sequence: %s" % dic["seq"])        #(should include path!)

        #2012.02.20 JU: having problems w/ sequence sometimes using width for bin 2x2 as
        #               being 1 pixel too small (1662 instead of 1663). Try to make sure
        #               the camera frame is in a good state before the sequence.
        vState.CAMERA.BinX = 1
        vState.CAMERA.BinY = 1
        vState.CAMERA.SetFullFrame()

        vState.CAMERA.StartSequence( dic["seq"] )
        LogStatusHeaderBrief()
        while vState.CAMERA.SequenceRunning:
            time.sleep(1)   #pause to check again for sequence end
            if LogStatus(vState,3):
                vState.CAMERA.AbortExposure()
                if RecoverFromBadGuiding(dic,vState):
                    return (2,)     #problem; unable to recover

            #decide if need to stop for skip ahead event
            tup = TestSkipAhead(vState)
            if tup[0] != 0:
                #skip ahead event found, or error
                vState.CAMERA.AbortExposure()
                #guiding will stop when scope moved, so no need to stop it here
                FixSequenceHeaders(dic["ID"],beforeList,vState)
                return tup

            if MeridianSafety(vState):
                #if we reach the meridian safety limit in the middle of an exposure,
                # abort the exposure and stop guiding because the scope has to move,
                # but let the next action after the current one decide where to move to.
                # If we are looping over single exposures, the caller will run
                # Flip_And_Reacquire_Target if there are more images to take here
                vState.CAMERA.AbortExposure()
                LogConditions(vState)
        Log2(0,"Single sequence complete")

        try:
            #2018.04.28 JU: new feature: include focuser position and temperature in summary log line for exposure
            currentPos = str(vState.FOCUSER.Position)
            currentTemp = str(vState.FOCUSER.Temperature)
        except:
            currentPos = "(exception)"
            currentTemp = "(exception)"
        Log2Summary(2,"Sequence complete  Temp:%s  Pos:%s" % (currentTemp,currentPos))

        FixSequenceHeaders(dic["ID"],beforeList,vState)
        ReportImageFWHM(vState,"Seq: " + sequenceBaseFilename)     #log info on last image taken in sequenece

    else:
        #run single exposure-------------------------------------

        #Only settle guiding between single exposures if they are long; do not settle when doing short exposures
        if dic["exp"] >= 150:
            if SettleGuiding(vState):
                #problem settling guiding
                vState.CAMERA.AbortExposure()
                if RecoverFromBadGuiding(dic,vState):
                    return (2,)     #problem; unable to recover

        filename_i = CreateEnhancedFilename(vState.path, dic["ID"],vState,dic["bin"],dic["filter"],dic["exp"],dic["crop"])
        theExposure = dic["exp"]
        Log2(2, "Expose: %3.1f  Filter: %s (%d)  Bin: %dx%d  %s" % (theExposure, dic["filter"],filterToInt(dic["filter"]),dic["bin"],dic["bin"],dic["ID"]))

        if runMode == 3:
           return (0,)     #skip for testing

        vState.CAMERA.BinX = 1  #make sure no rounding for full frame
        vState.CAMERA.BinY = 1
        vState.CAMERA.SetFullFrame()    #reset any previous cropping settings
        vState.CAMERA.BinX = dic["bin"]
        vState.CAMERA.BinY = dic["bin"]

        if dic["crop"] == "yes":
            tupc = CalcCropSize(dic["bin"],vState.CAMERA.cameraXSize,vState.CAMERA.cameraYSize)
            vState.CAMERA.StartX = tupc[0]
            vState.CAMERA.StartY = tupc[1]
            vState.CAMERA.NumX = tupc[2]   #NumX,NumY can be shortened if they won't fit in the available image size
            vState.CAMERA.NumY = tupc[3]
            #Note: the crop settings are logged once when the current step starts;
            # we reset the camera settings here for each exposure just in case,
            # but the values will all be the same.

        ##vState.CAMERA.Filter = filterToInt(dic["filter"])
        ##Log2(4,"Filter wheel reports position: %d" % vState.CAMERA.Filter)
        #2014.09.23 JU: redo above to shorten execution time
        sFilter = dic["filter"]
        iFilter = filterToInt(sFilter)
        #vState.CAMERA.Filter = iFilter     #NOT NEEDED if specified in Expose() function below; save time skipping this.
        Log2(1,"Set filter wheel to position: %s -- %d, pier side=%d/%d" % (sFilter,iFilter,vState.MOUNT.SideOfPier,SideOfSky(vState)))


        Log2(4,"@@@ Filter in use before CAMERA.Expose: %d, filter specified = %d/%s" % (vState.CAMERA.Filter,iFilter,sFilter) )
        vState.CAMERA.Expose( theExposure, 1, iFilter )   # 1 = light frame
        Log2(4,"@@@ Filter in use AFTER CAMERA.Expose: %d, filter specified = %d/%s" % (vState.CAMERA.Filter,iFilter,sFilter) )

        #wait for exposure to complete
        #Note: even for very short exposures, there are several seconds at the start
        # while MaxIm does guider settling; don't worry about it.
        LogStatusHeaderBrief()
        flag = not vState.CAMERA.ImageReady
        while flag:
            #try:
            flag = not vState.CAMERA.ImageReady
            #except:
            #    pass
            time.sleep(1)
            if LogStatus(vState,2):       #this reports if guiding problem
                vState.CAMERA.AbortExposure()
                if RecoverFromBadGuiding(dic,vState):
                    return (2,)     #problem; unable to recover

                #we recovered OK, but need to re-set binning because it was changed during PP solve during recover
                vState.CAMERA.BinX = dic["bin"]     #may not need these
                vState.CAMERA.BinY = dic["bin"]
                return (0,)     #added return after recover; THIS may have been the problem

            #decide if need to stop for skip ahead event
            tup = TestSkipAhead(vState)
            if tup[0] != 0:
                #skip ahead event found, or error
                vState.CAMERA.AbortExposure()
                return tup

            if MeridianSafety(vState):
                #if we reach the meridian safety limit in the middle of an exposure,
                # abort the exposure and stop guiding because the scope has to move,
                # but let the next action after the current one decide where to move to.
                # If we are looping over single exposures, the caller will
                # Flip And Reacquire Target if there are more images to take
                LogConditions(vState)
                vState.CAMERA.AbortExposure()
                return (0,)

        Log2(2,"Exposure complete")

        try:
            #2018.04.28 JU: new feature: include focuser position and temperature in summary log line for exposure
            currentPos = str(vState.FOCUSER.Position)
            currentTemp = str(vState.FOCUSER.Temperature)
        except:
            currentPos = "(exception)"
            currentTemp = "(exception)"
        Log2Summary(2,"Exposure complete %s  Temp:%s  Pos:%s SideOfSky=%d" % (filename_i,currentTemp,currentPos,SideOfSky(vState)))

        ReportImageFWHM(vState, filename_i)     #log info on image

        #record info into FITS header
        vState.CAMERA.SetFITSKey("OBJECT", dic["ID"])
        if vState.guide == 1:
            vState.CAMERA.SetFITSKey("GUIDED", "Guided" )
        elif vState.guide == 2:
            vState.CAMERA.SetFITSKey("GUIDED", "maybe" )
        else:
            vState.CAMERA.SetFITSKey("GUIDED", "NotGuided" )

        #save the image  [THESE COORDS WERE JNOW, NOT J2000; DOES THAT MATTER?]
        #2009.04.18 JU: yes, apparently this does matter, it reduces chance
        #                 that I can later re-solve the image in PP via MaxIm.
        pos = Position()
        pos.setJNowDecimal(vState.MOUNT.RightAscension,vState.MOUNT.Declination)
        sRA2000, sDec2000 = pos.getJ2000String()
        vState.CAMERA.Document.SetFITSKey("OBJCTRA","%s %s %s" % tuple(sRA2000.split(":")))
        vState.CAMERA.Document.SetFITSKey("OBJCTDEC","%s %s %s" % tuple(sDec2000.split(":")))
        vState.CAMERA.SaveImage(filename_i)
        LogConditions(vState)
        StatusLog(filename_i)


    RecentImaged_Add(dic["ID"])
    return (0,)

#--------------------------------------------------------------------------------------------------------
#This data is used by the automatic sched routine I'm adding,
# so that it does not pick items I imaged recently but did not
# update in the J-Targets2.csv file yet.
def RecentImaged_Add(objName):
    #write a timestamp after each name
    #ex: NGC 7777        # 2009/12/31 23:59:59
    sDateStr = time.strftime('%Y/%m/%d %H:%M:%S',time.gmtime())
    g = open( RecentImaged, "a")
    g.write("%-15s #%s\n" % (objName,sDateStr))
    g.close()

    #Add this name to the current IgnoreList !!!
    #Need to trim the name because it may come with a comment attached.
    temp = tuple(objName.split('#'))
    if( len(temp[0]) == 0 ):
        return            #???
    objName2 = UTIL.TrimString(temp[0])
    if objName2.endswith("\n"):
        objName2 = objName[:-1]
    IgnoreList.append(objName2)


#--------------------------------------------------------------------------------------------------------
#dic["type"] = "Light"
#   or ["camera"] = "Guider"
#       dic["isSeq"] = "no" (required value)
#       dic["bin"] = 1,2,3; maybe more depending on camera?
#       dic["exp"] = exposure time decimal seconds
def implGuiderExposure(index,dic,vState,bLast):
    # Return tuple:  (state,skipAheadStep)
    #   where exposure: 0=exposure normal completion
    #                   1=skip ahead
    #                   2=error, stop script
    #         skipAheadStep: number = step to skip ahead to
    #if bLast is False, PP solve guider image and sync and re-goto to re-center.
    #This depends on dic[dRA_JNow], dic[dDec_JNow] for the expected coords.

    #Note: no focus control for guider, so no TemperatureCompensation

    filename_i = CreateFilename(vState.path, dic["ID"] + "_Wide_", vState,1)
    Log2(2, "Wide exposure: %3.1f,  %s" % (dic["exp"], dic["ID"]))

    if runMode == 3:
        LogOnly("Validate skipping rest of: implGuiderExposure")
        return (0,)

    #2010.01.28 JU: limit guider exposures to 100 seconds; longer will saturate
    #2010.05.15 JU: REMOVED LIMIT, sometimes I want longer exposures w/ guider wide fields!
    #if exposure > 100:
    #    Log2(3,"Reducing guider exposure to 100 seconds")
    #    exposure = 100
    exposure = dic["exp"]
    vState.CAMERA.GuiderExpose( exposure )

    #wait for exposure to complete
    LogStatusHeaderBrief()
    while vState.CAMERA.GuiderRunning:  #--------------------
        time.sleep(2)
        LogStatus(vState,1)

        #decide if need to stop for skip ahead event
        tup = TestSkipAhead(vState)
        if tup[0] != 0:
            #skip ahead event found, or error
            #Check to make sure this really stops the Guider exposure:
            StopGuiding(vState)
            return tup

        if MeridianSafety(vState):
            #if we reach the meridian safety limit in the middle of an exposure,
            # abort the exposure and stop guiding because the scope has to move,
            # but let the next action after the current one decide where to move to.
            # If we are looping over single exposures, the caller will
            # Flip And Reacquire Target if there are more images to take
            return (0,)

    Log2(2,"Wide Exposure complete")
    doc = GetGuiderDoc(vState)

    #record info into FITS header
    doc.SetFITSKey("OBJECT", dic["ID"])
    doc.SetFITSKey("GUIDED", "NotGuided" )

    #save the image  with J2000 coords
    pos = Position()
    pos.setJNowDecimal(vState.MOUNT.RightAscension,vState.MOUNT.Declination)
    sRA2000, sDec2000 = pos.getJ2000String()
    doc.SetFITSKey("OBJCTRA","%s %s %s" % tuple(sRA2000.split(":")))
    doc.SetFITSKey("OBJCTDEC","%s %s %s" % tuple(sDec2000.split(":")))
    doc.SetFITSKey("OBJECT","%s" % dic["ID"])

    doc.SaveFile( filename_i, 3, False, 1, 0)   # 3=fits format; False=do not autostretch; 1=16-bit data; 0=no compression
    LogConditions(vState)

    #Calc center of mass of image; may use this for centering instead of PP solve?
##    xcenter, ycenter = FileCM(filename_i)
##    Log2(0,"-------TEMP-------------")
##    Log2(0,"-- Center of mass of guider image: ")
##    Log2(0,"X = %5.1f    Y = %5.1f " % (xcenter,ycenter))
##    Log2(0,"-------TEMP-------------")


    #we do not really need to solve final image
    if bLast:
        RecentImaged_Add(dic["ID"] + "    #WIDE ")
        return (0,)

    #Does dic["pos"] exist? It won't for Stationary mode
    try:

        #PP Solve the wide field (guider) image just taken, and reposition mount to keep target centered
        #tup = CustomPinpointSolve(1, dic["pos"], dic["ID"], filename_i, 0, vState)
        tup = AdvancedPlateSolve(1, dic["pos"], dic["ID"], filename_i, 0, vState)
#!!!why doesn't this write the WCS coords into the image header??? It should be able to !!!!
#-> The doc.SaveFile call below overwrites the WCS values that ARE saved in PP call above; remove it.
##    spos = Position()
##    if tup[0]:
##        spos.setJ2000Decimal(tup[1],tup[2])
##        sRA2000, sDec2000 = spos.getJ2000String()
##        doc.SetFITSKey("REAL_RA","%s %s %s" % tuple(sRA2000.split(":")))
##        doc.SetFITSKey("REAL_DEC","%s %s %s" % tuple(sDec2000.split(":")))
##        #re-save it w/ these new key values
##        doc.SaveFile( filename_i, 3, False, 1, 0)
##        Log2(6,"implGuiderExposure - solved Pos:" + spos.dump())
##    else:
##        Log2(4,"Guider image just taken could not be solved with PP")

        #SYNC mount if success
        if tup[0]:
           #PP solved; use returned coords to sync position, and then GOTO desired coords again
            vState.pinpoint_success += 1
            #Log2(2,"** SOLVED!!  Solution is:")

            #how close?  Test BEFORE syncing!!! (all these coords are JNow)
            spos = Position()
            spos.setJ2000Decimal(tup[1],tup[2])
            sRA2000, sDec2000 = spos.getJ2000String()

            DiffRA = dic["pos"].dRA_JNow() - spos.dRA_JNow()  #DIFF TO WHERE WE WANT TO BE VS WHERE PP SAYS WE ARE
            DiffDec = dic["pos"].dDec_JNow() - spos.dDec_JNow()

            Log2(2,"Diff  R%s D %s (difference before sync)" % (UTIL.HoursToHMS(DiffRA,":",":","",1), DegreesToDMS(DiffDec)))

            vState.MOUNT.SyncToCoordinates(spos.dRA_JNow(),spos.dDec_JNow())        ##Sync mount to solved coords <--

            #only reposition if difference greater than some setting...
            delta_RA = 5. * 1./3600.  #5 seconds of time
            delta_Dec = 10 * 1./3600. #10 arcseconds
            if abs(DiffRA) < delta_RA and abs(DiffDec) < delta_Dec:
                Log2(4,"No reposition after PP solve; close enough already")
            else:
                GOTO( dic["pos"], vState, "WIDE repos: " + dic["ID"] )

        else:
            #this might indicate bad weather, or below horizon, or dawn?
            Error("Unable to PP solve the WIDE field image just taken.")
            return (2,)
    except:
        #probably stationary mode, so cannot PP solve (don't have coord)
        LogOnly("Did not attempt to PP solve wide image (probably stationary mode)")
        niceLogExceptionInfo()

    RecentImaged_Add(dic["ID"] + "    #WIDE ")
    return (0,)


#=====================================================================================
#==== SECTION  @@execLogic ===========================================================
#=====================================================================================
#   the 'dic' object used to pass control info around:

# "type"
#dic["type"] = "Park"  parks mount and turns off tracking
#dic["type"] = "Goto"  goto specified location, but no camera activity (Park is an example of this)
#dic["type"] = "Dark" take dark frames
#dic["type"] = "Flat" take flat frames; sequence will be pre-programmed for now
#dic["type"] = "Bias" take bias frames (no sequence supported here); only works w/ Imager, not guider
#dic["type"] = "Focus" (focus assumes Imager for now, not guider)
#dic["type"] = "Light"

# "location"
#   dic["location"] = "RA/Dec" use RA/Dec coords to position scope
#   dic["location"] = "cat" use catalog coord lookup to position scope
#   dic["location"] = "cat+" use catalog coord w/ specified offset for better framing
#   dic["location"] = "stationary" not move scope from current location when starting this step

# "camera"
#  Imager
#  Guider
#  None? (for Goto, Park)

# "isSeq"
#  yes
#  no

# "isSeq" = "yes"
#       dic["seq"] = name of sequence file

# "isSeq" = "no"
#           dic["bin"] = 1,2,3; maybe more depending on camera?
#           dic["filter"] = "L","R","G","B","Ha"...; default to "L" if not specified
#           dic["exp"] = exposure time decimal seconds

# "limit"
#   dic["limit"] = "count"  repetition limited by repeat count
#   dic["limit"] = "time"   repetition limited by end time (UT)
#   dic["limit"] = "sunAltitude" expose as long as sun altitude is *below* horizon by at least specified value
#   dic["limit"] = "targetAltitude" expose as long as target altitude is *above* horizon by at least specified value

## dic (dictionary object) used to pass parameters to execution logic
#dic["step"] = number of step within command list (used when testing skip-ahead events)
#dic["type"] = "Park"  parks mount and turns off tracking
#dic["type"] = "Dark" take dark frames
#   dic["camera"] = "Imager"  (required value)
#   dic["isSeq"] = "yes"
#       dic["seq"] = name of sequence file, assume Darks only! Includes path (usually C:\fits_seq); path must be specified
#   dic["isSeq"] = "no"
#       dic["bin"] = 1,2,3; maybe more depending on camera?
#       dic["exp"] = exposure time decimal seconds
#       dic["repeat"] = number of repetitions of exposure
#dic["type"] = "Flat" take flat frames; sequence will be pre-programmed for now
#   later, add ADU limits, camera selection, exposure limit, altitude setting when I get better idea of how it works
#dic["type"] = "Bias" take bias frames (no sequence supported here); only works w/ Imager, not guider
#   dic["bin"] = 1,2,3; maybe more depending on camera?
#   dic["repeat"] = number of repetitions of exposure
#dic["type"] = "Focus" or "Light" (focus assumes Imager for now, not guider)
#   dic["location"] = "RA/Dec" use RA/Dec coords to position scope
#       dic["RA"] = decimal RA coord
#       dic["Dec"] = decimal Dec coord
#       dic["epoch"] = "J2000" or "JNow"
#       dic["ID"] = required string; name of object; does NOT need to conform to catalog format
#   dic["location"] = "cat" use catalog coord lookup to position scope
#       dic["ID"] = Catalog name of object, used to look up coords
#   dic["location"] = "stationary" not move scope from current location when starting this step
#dic["type"] = "Focus" (focus assumes Imager for now, not guider)
#   dic["exp"] = exposure time decimal seconds
#dic["type"] = "Light"
#   dic["camera"] = "Guider"
#       dic["isSeq"] = "no" (required value)
#       dic["bin"] = 1,2,3; maybe more depending on camera?
#       dic["exp"] = exposure time decimal seconds
#   dic["camera"] = "Imager"
#       dic["isSeq"] = "yes"
#           dic["seq"] = name of sequence file; Includes path (usually C:\fits_seq); path must be specified
#       dic["isSeq"] = "no"
#           dic["bin"] = 1,2,3; maybe more depending on camera?
#           dic["filter"] = "L","R","G","B","Ha"...; default to "L" if not specified
#           dic["exp"] = exposure time decimal seconds
#           dic["repeat"] = number of repetitions of exposure
#       dic["guideExp"] = guider exposure decimal seconds; 0=do not guide
#       dic["guideStart"] = NOT USED YET guide error must be less than this number of pixels (decimal) before image starts
#       dic["PP-Solve"] = "wide"(default), "narrow", "both", "none"
#           THIS FEATURE NOT IMPLEMENTED; solve value always read from vState variable
#   dic["limit"] = "count"  repetition limited by repeat count
#       dic["repeat"] = number of repetitions of exposure; default = 1
#   dic["limit"] = "time"   repetition limited by end time (UT)
#       dic["endTime"] = string w/ UT time, ex: "11:55"
#   dic["limit"] = "sunAltitude" expose as long as sun altitude is *below* horizon by at least specified value
#       dic["altitude"] = decimal degrees; stop if sun higher than this
#   dic["limit"] = "targetAltitude" expose as long as target altitude is *above* horizon by at least specified value
#       dic["altitude"] =  decimal degrees; stop if target lower than this altitude

#--------------------------------------------------------------------------------------------------------
#TODO: rename this to something like TestAbortCurrentStep, and change comments
def TestSkipAhead(vState):     #Are there any skip ahead events triggering now that we need to jump to?
   #Hard code this to only work with sun's altitude, assuming the next step is taking flats

   #calculate the sun's altitude
   now = time.gmtime()
   utc = now[3] + (now[4]/60) +( now[5]/3600)
   utc = float(now[3]) + (float(now[4])/60.) + (float(now[5])/3600.)

   #only do the test if sun could be in morning sky (for me)
   #2015.10.17 JU: fix logic so that we later test western halt altitude regardless of time here
   if utc > 6 and utc < 18:
   #if utc < 6 or utc > 18:
   #    return (0,)  #in evening sky, so don't test

       alt = CalcSolarAlt(now[0],now[1],now[2],utc,-87.75,42.1)

       #if sun in morning sky and higher than -10 degrees, stop current step
       #I based this value on when the sky is about to get too bright for deep
       #  sky but still dark enough that I could take some dark frames.
       #2011.10.05 JU: changed from -12 to -9 to get some additional images when possible
       if alt > -9:
           Log2(1,"--------------------------")
           Log2(1,"| Sun altitude > -9 deg |")
           Log2(1,"--------------------------")
           Log2(2,"current sun altitude = %5.2f" % (alt))
           Log2Summary(0,"SUN ALTITUDE > -9 DEG");
           return (1,)  #stop current step

   #2015.01.19 JU: add new feature: stop exposure if the target has gotten too low in the
   #western sky. Compare scope altitude to vState.setHaltAltitude

   #are we pointing to the west: azimuth between 190 and 330 degrees?
   #if we are, only then check current altitude against halt altitude
   #(only perform the test if this is set to something)
   if vState.WesternHaltAltitude > 0:
	   try:
		  curAlt = vState.MOUNT.Altitude
		  curAz  = vState.MOUNT.Azimuth

		  if curAz >= 190 and curAz <= 330:
			if curAlt < vState.WesternHaltAltitude:
				Log2(0,"******************************************************************")
				Log2(0,"** Halting current step because target altitude in west = %5.1f **" % curAlt)
				Log2(0,"******************************************************************")
				vState.WesternHaltAltitude = 0  #clear setting after being reached, so it doesn't affect next target unless that sets its own value
				return (1,)
	   except:
		  Log2(0,"Mount alt/az not available!?")
		  niceLogExceptionInfo()

   return (0,)     #continue w/ current step

#--------------------------------------------------------------------------------------------------------
def TestSunAltitude(sunLimit):     #return True if sun altitude > specified value (morning sky only)
   #the sunLimit value will usually be negative, probably between -10 and -3 degrees

   now = time.gmtime()
   utc = float(now[3]) + (float(now[4])/60.) + (float(now[5])/3600.)    #must use float here or doesn't calculate as desired!

   #only do the test if sun could be in morning sky (for me)
   if utc < 6 or utc > 18:
       return False  #in evening sky, so don't test

   alt = CalcSolarAlt(now[0],now[1],now[2],utc,-87.75,42.1)

   #if sun in morning sky and higher than -10 degrees, stop current step
   #I based this value on when the sky is about to get too bright for deep
   #  sky but still dark enough that I could take some dark frames.
   if alt > sunLimit:
       Log2(1,"--------------------------")
       Log2(1,"| Sun altitude > %2d deg |" % (sunLimit))
       Log2(1,"--------------------------")
       Log2(2,"current sun altitude = %5.2f" % (alt))
       return True  #stop current step

   return False     #continue w/ current step

#=================================================================================================
# MeasureGuideScopeOffset,<targetID>[,retries]
#   0                        1           2
def exec_MeasureGuideScopeOffset(t,vState):
    #This moves scope to targetID location (NO PP solve involved), then
    # takes both Wide and Narrow images without moving scope, and PP solves
    # both of them and calculate the difference in coords. (maybe convert solution
    # coords into JNow before measuring difference, so using same axes on sky that
    # the mount uses).  To be nice, it performs a mount Sync after the Narrow PP solve.
    dic = {}
    dic["ID"]     = t[1]
#TODO...
    return (2,) #not implemented yet


#--------------------------------------------------------------------------------------------------------
def implExp_StartCondition(dic,vState):
   #test if this step is allowed to run now, including checking
   # any skip-ahead commands.
##    tup = TestSkipAhead(vState)     #Are there any skip ahead events triggering now that we need to jump to?
##    if tup[0] == 1:
##        return tup
   #test         vState.min_altitude
   #I would like to test the target object's altitude; I can read the mounts Altitude
   #after slewing to the target; I wish I could calculate the Altitude before the slew.
   #I also may need to do this test in implExp_InitialMovement to get the coords
   #of the target.

   #Log2(0,"StartCondition: pass (not implemented yet)")
   #SendToServer(getframeinfo(currentframe()),"check start conditions")

   #calculate the sun's altitude
   now = time.gmtime()
   utc = float(now[3]) + (float(now[4])/60.) + (float(now[5])/3600.)

   #Do not run any imaging steps if sun too high IN THE MORNING!
   if utc > 5.0 and utc < 18.0:
    if CheckSunAltitude(-9):
        return(2,)

   try:
    if dic["limit"] == "time":
        #see if end time reached before starting
        if TestEndConditionReached(dic,vState):
            return (2,)
   except:
    pass    #cmd didn't have "limit", OK

   return (0,)

#--------------------------------------------------------------------------------------------------------
def CalibrateOrRefocusForNewTarget(fstar,vState):
    #NOTE: the 'Calibrate' logic has been removed; this just does a refocus unless too soon.

    #return: true = need to redo this w/ different star; false means OK to proceed
    #
    # fstar is a cFocusStar() object
    #this goto's a 'bright star' from focus star list
    #then it may refocus if temp/time sufficient
    #then regardless it calibrates imager offset from guider field
    LogOnly("**Entry to CalibrateOrRefocusForNewTarget")

    dt = FORCE_REFOCUS_TIME_DIFF - (time.time() - vState.TempMeasureTime)
    if dt > 0:
        Log2(2,"Do not attempt to refocus yet (wait another %d minutes)" % ((dt/60)))
        LogOnly("**Exit from CalibrateOrRefocusForNewTarget (nothing done)")
        return False    #OK to proceed


    #vState.ResetImagerOffset()
    pos = Position()
    pos.setJ2000Decimal(fstar.dRA,fstar.dDec)
    GOTO(pos, vState, fstar.name )
    if PinpointEntry(pos, fstar.name, vState, False): #set last arg False to prevent PP solve w/ imager at this point
       IgnoreFocusStars.append(fstar.name)
       Error("**CalbrateOrRefocusForNewTarget problem:")
       Error("**Unable to PP solve (ignore this star; maybe retry with a different one)")
       return True

    #We are now positioned on bright (focus) star; should we refocus on it?
    #tempDiff = abs(vState.TempCompTemperature - vState.FOCUSER.Temperature)
    #if tempDiff >= FORCE_REFOCUS_TEMP_DIFF:
    if True:
      #2012.02.01 JU: Always refocus regardless of temp change
      #Log2(2,"Temperature change: %d -> %d" % (vState.TempCompTemperature,vState.FOCUSER.Temperature))

      #refocus!
      Log2(2,"Refocusing...")
      dic = {}
      dic["crop"] = "no"
      dic["exp"]  = 0.5
      dic["ID"]   = fstar.name
      if not callFocusMax(dic,vState):  #this calls imager calibration here!
               IgnoreFocusStars.append(fstar.name)
               return True #try again

    LogOnly("**Exit from CalibrateOrRefocusForNewTarget")
    return False    #OK to proceed

#--------------------------------------------------------------------------------------------------------
def implExp_InitialMovement(dic,vState):
   #*-coding NOT done-*#
   #if movement needed
   #    stop guiding
   #    goto target
   #    if Meridian limit passed
   #       flip
   #       goto target (sleep after slew)
   #    sleep after slew
   #    PP procedure (image, solve, refine goto)
   #    start guiding

   #print dic
   #SendToServer(getframeinfo(currentframe()),"InitialMovement")

   #Decide if any movement
   dType = dic["type"].lower()
   if dType == "dark" or dType == "bias":
      return (0,)  #no movement for these cases

   if dType == "park" or dType == "flat":
      #these are handled elsewhere; do nothing here
      return (0,)

   #Determine how destination is specified:
   location = dic["location"].lower()
   #Log2(0,"Location = " + location)
   if location == "stationary":
      return (0,)   #nothing to do here

   Log2(0,"InitialMovement:")
   #We are moving the scope (the actual GOTO cmd will take care of stopping the guider later)

   if location == "cat+":
      Error("cat+ not implemented yet")
      return (2,)

   if location == "cat":
      pos = LookupObject( dic["ID"] )
      dic["pos"] = pos
      # target = string for deep sky (ex M1, NGC7777), asteroid (ex MPL 12345), or star (SAO 111111)
      # output is position object
      if not pos.isValid:
          #failed to find object; this should have been found earlier
          return (2,)
   if location == "auto" or location == "near" or location == "nearcurrent" or location == "reposition":
       pos = dic["pos"]

   if location == "ra/dec":    #use provided coords
      #       dic["RA"] = decimal RA coord
      #       dic["Dec"] = decimal Dec coord
      #       dic["epoch"] = "J2000" or "JNow"
      pos = Position()
      if dic["epoch"] == "J2000":
          pos.setJ2000Decimal(dic["RA"],dic["Dec"],dic["ID"],cTypeCatalog)
      else:
          pos.setJNowDecimal(dic["RA"],dic["Dec"],dic["ID"],cTypeCatalog)
          #dRA_JNow = dic["RA"]
          #dDec_JNow = dic["Dec"]
      #record the coords in the dic object, in case needed later in flip during exposures
      Log2(6,"implExp_InitialMovement - pos:" + pos.dump())
      dic["pos"] = pos


   #Verify: at this point the location type must be either cat or ra/dec; anything else is invalid
   if location != "cat" and location != "ra/dec" and location != "auto" and location != "near" and location != "nearcurrent" and location != "reposition":
       Error("implExp_InitialMovement called with invalid dic[location]")
       return (2,)
   ##Log2(1,"Target coords JNow: R%s D%s" % ( pos.getJNowString() ) )

   #we now have the coords; move the scope
   #    goto target
   #    if Meridian limit passed
   #       flip
   #       goto target (sleep after slew)
   #    PP procedure (image, solve, goto)
   #    start guiding
   ##StatusWindow("substep","Slewing...",vState)
   if runMode == 1:
	   #2016.01.02 JU: this code was causing a failure, because the mount was not connected when tracking was turned on.
	   if not vState.MOUNT.Connected:
		   vState.MOUNT.Connected = True
	   if vState.MOUNT.AtPark:
		   Log2(3,"Unparking mount")
		   vState.MOUNT.Unpark()
	   if not vState.MOUNT.Tracking:
		   vState.MOUNT.Tracking = True
       #vState.MOUNT.Tracking = True                    #just in case it was off

   #Enhancement #1: if on wrong side of pier for a target close to meridian, need to flip first
   tupflip = PredictSideOfPier(pos,vState)
   if tupflip[1]:
       #SendToServer(getframeinfo(currentframe()),"Move scope to other side of pier before GOTO")

       #need to move scope to other side of pier
       #calc some coord on desired side
       if tupflip[0] == 0:
           #OTA east, looking west, pick location 1.5 hours west of meridian
            dRA = vState.MOUNT.SiderealTime - 1.5    #1.5
       else:
            #OTA west, looking east, so pick location east of meridian
            dRA = vState.MOUNT.SiderealTime + 1.5    #1.5
       if dRA < 0:
           dRA += 24
       if dRA >= 24:
           dRA -= 24
       repos = Position()
       repos.setJNowDecimal(dRA,45) #use intermediate declination of 45 degrees for this
       #GOTO that position
       Log2(3,"Reposition OTA on other side of pier to prepare for image target after this")
       GOTO(repos, vState, "Pier reposition")
       Log2(3,"Reposition complete; now move to target")

   #Enhancement? want to move scope SOUTH to target; if target is to the North of
   # current scope position, then slew to a point even farther north, then back
   # south to final location

   #Now move to desired target for imaging (just does GOTO, the PP refinement comes after this)
   #What if target is below horizon???
   if GOTO(pos, vState, dic["ID"] ):
       return (2,) #unable to position on target; it probably is not UP!!!

   if not isVisible(vState.MOUNT.Azimuth,vState.MOUNT.Altitude):
        #this is below the tree line horizon; don't bother proceeding;
        Log2(0,"This next target is probably below the local horizon so SKIP IT!")
        raise HorizonError


   bImagerSolve = True
   if dic["camera"].lower() == "guider" or dic["type"].lower() == "focus" or location == "reposition":
       bImagerSolve = False  #only need wide field solve for these steps

   #Assume no pier flip would be needed at this point because of the new positioning logic above!

   if PinpointEntry(pos, dic["ID"], vState, bImagerSolve): #set last arg False to prevent PP solve w/ imager
        Error("**Unable to PP solve (and configured to stop if this happens); skip this step")
        return (2,)  #unable to PP solve; do not do this step

   #EnableTestForMeridianLimit(vState)   #check whether we need to watch for pier flip later during the exposure

   if bImagerSolve:
      #if we are using Imager to image, we want to guide
      if StartGuidingConfirmed(dic["ID"], vState, 5):
          Error("**Failed to start guiding even after several attempts")
          ##SafetyPark(vState)
          ##raise SoundAlarmError,'Halting program'
          raise WeatherError

          ##try a different target; maybe more success in a different part of the sky
          ##return (2,)

   #We are now precisely positioned on desired target, and guiding is running (if desired).

   return (0,)

def PrepareAdvancedFocusComp(dic,vState):
    #this is similar to execMeridianFlip() in that it is called from the loop over exposures
    # and can interrupt the imaging sequence to run a benchmark focus event if set for advanced temp comp
    #
    #This function gets called each imaging loop and it decides if it needs to run; it only needs to run once
    #so it does nothing after that point.

    if dic["camera"].lower() == "guider" or dic["type"].lower() == "focus":
        #if current activity w/ guider (wide image) or focus, do nothing here for now
        return

    if not vState.focusEnable:
        return  #focuser not enabled, so do nothing for now

    currenttime = time.time()
    if vState.FocusCompensationActive == 3 and vState.AdvancedFocusState == 0 and (currenttime - vState.AdvancedFocusStartTime) >= (2*60*60):
        #time to take benchmark focus and enable temp comp focusing
        Log2(0,"*********************************************************************")
        Log2(0,"** Prepare Advanced Focus Compensation logic: take benchmark focus **")
        Log2(0,"*********************************************************************")
        Log2Summary(0,"ADVANCED FOCUS COMPENSATION LOGIC: TAKE BENCHMARK FOCUS")

        desiredPos = dic["pos"] #target to return to when done
        ID = dic["ID"]

        bSuccess = False
        nLimit = 10     #number of retries before halting
        while not bSuccess:
            tband = BuildFocusStarBand(desiredPos,vState)  #Note: this uses pos, not repos; want star near target!
            fstar = FindNearFocusStar(vState,desiredPos, tband[0], tband[1])
            #GOTO that star, try to refocus on it
            pos = Position()
            pos.setJ2000Decimal(fstar.dRA,fstar.dDec)
            GOTO(pos, vState, fstar.name )      #GOTO the focus star
            if PinpointEntry(pos, fstar.name, vState, False): #set last arg False to prevent PP solve w/ imager at this point
                #Problem!
                IgnoreFocusStars.append(fstar.name)
                Error("**CalbrateOrRefocusForNewTarget problem:")
                Error("**Unable to PP solve (ignore this star; maybe retry with a different one)")
                #problem
                nLimit -= 1
                if nLimit <= 0:
                    Error("Too many retries for CalibrateOrRefocusForNewTarget")
                    Error("Possible weather issue...")
                    ##SafetyPark(vState)
                    ##raise SoundAlarmError,'**maybe weather issue**'
                    raise WeatherError
                continue #try again

            #refocus! (need separate dictionary object for this)
            Log2(2,"Refocusing...")
            dic2 = {}
            dic2["crop"] = "no"
            dic2["exp"]  = 0.5
            dic2["ID"]   = fstar.name
            if not callFocusMax(dic2,vState):  #this calls imager calibration here!
                IgnoreFocusStars.append(fstar.name)
                #problem
                nLimit -= 1
                if nLimit <= 0:
                    Error("Too many retries for CalibrateOrRefocusForNewTarget")
                    Error("Possible weather issue...")
                    raise WeatherError
                continue #try again
            else:
                bSuccess = True

        #Refocusing was successful at this point
        Log2(1,"PrepareAdvancedFocusComp completed and temperature comp activated.")
        vState.AdvancedFocusState = 1       #change state so we only do this activity once

        #return to original target
        Log2(1,"Now slewing back to desired target coordinates (OTA should be east now)")
        GOTO(desiredPos,vState,ID)  #Go back to previous imaging target

        #Now precisely re-position the mount on the specified coords using PP solves.
        if PinpointEntry(desiredPos, ID, vState, True):
            #there was a problem; we could not PP solve, assume weather error
            raise WeatherError

        #if we are using Imager to image, we probably want to resume guiding
        if StartGuidingConfirmed(dic["ID"], vState, 5):
          Error("**Unable to start guiding (after PrepareAdvancedFocusComp) even after several attempts")
          raise WeatherError

        Log2(1,"Scope returned to original target and ready to resume imaging")
        return

    #else nothing to do (not applicable or not time to do this)
    return

#--------------------------------------------------------------------------------------------------------
def implExp_LightExposures(dic,vState):
    #*-coding done-*#
   #Note: if this is an Imager exposure, guiding was started after moving to target
   # so do not need to do it here.

   #Loop
   #   If end condition, stop loop
   #   If Meridian crossed:
   #      flip and reacquire target IF flip enabled, else just stop imaging target
   #   take one image/sequence (either Imager or Guider)

   #pull settings from dictionary which will be needed in the loop
   dLimit = dic["limit"].lower()
   dCamera = dic["camera"].lower()

   ClearImager(dic,vState)
   if dCamera == "imager":
       Log2(0,"EXPOSURE (narrow) STARTING...")
   else:
       Log2(0,"EXPOSURE (Wide) STARTING...")

   if dLimit != "count" and dLimit != "time" and dLimit != "sunAltitude" and dLimit != "targetAltitude":
      Error( "*** Invalid dic[limit] in implExp_LightExposures")
      return (2,0)

   i = 0                       #count passes of loop even if not used for end condition
   if dLimit == "count":
      dRepeat = dic["repeat"]

   #
   #report cropping settings once (camera reset for crop each time later on if multiple exposures)
   #
   if dic["crop"] == "yes":
        tupc = CalcCropSize(dic["bin"],vState.CAMERA.cameraXSize,vState.CAMERA.cameraYSize)
        vState.CAMERA.StartX = tupc[0]
        vState.CAMERA.StartY = tupc[1]
        vState.CAMERA.NumX = tupc[2]   #NumX,NumY can be shortened if they won't fit in the available image size
        vState.CAMERA.NumY = tupc[3]
        Log2(4,"Cropping settings:")
        Log2(4,"   bin = %d" % dic["bin"])
        Log2(4,"   StartX = %d" % tupc[0])
        Log2(4,"   StartY = %d" % tupc[1])
        Log2(4,"   NumX = %d" % tupc[2])
        Log2(4,"   NumY = %d" % tupc[3])
   else:
        vState.CAMERA.BinX = 1  #make sure no rounding for full frame
        vState.CAMERA.BinY = 1
        vState.CAMERA.SetFullFrame()

   Log2Summary(1,"Start imaging: " + dic["ID"])

   while True:    #------------------------<repeat exposure/sequence loop>-------------
    #try: (catch if cloudy and want to wait/retry later)
      i = i + 1

      #
      #decide if we should continue
      #

      if dLimit == "count":
          if i > dRepeat:
              break
          else:
              Log2(1,"Exposure %d of %d" % (i,dRepeat))
      else:
          Log2(1,"Exposure %d" % (i))



      #check for skipAhead condition; also checks time/altitude if this step is limited by that
      if TestEndConditionReached(dic,vState):     #time or altitude condition check (ignored if dLimit == "count")
        #SendToServer(getframeinfo(currentframe()),"End condition reached")
        break

      if MeridianCross(vState):
          #we reached the meridian limit
          #SendToServer(getframeinfo(currentframe()),"Meridian limit reached")

          if not vState.bContinueAfterPierFlip:
              #we are configured to STOP when a meridian flip is needed, do NOT
              # flip and reacquire on this target.
              Log2(1,"Stopping imaging on this target because meridian limit reached, and configured to stop when this happens.")
              break

          #If the current step was a "Stationary" step, I do not have a dic["pos"] entry,
          #so I should NOT try to continue with same target.
          if "pos" not in dic:
              Log2(1,"Do not attempt a pier flip and reacquire because we were running a STATIONARY step, and pier flip not allowed for it")
              break

          #else reacquire exact position after doing the flip
          bImagerSolve = True
          if dic["camera"].lower() == "guider" or dic["type"].lower() == "focus":
               bImagerSolve = False  #only need wide field solve for these steps
          if execMeridianFlip(dic["pos"],dic["ID"],vState,bImagerSolve):
              Error("**Unable to find target after meridian flip; stop step")
              return (2,)
          if bImagerSolve:
              #if we are using Imager to image, we probably want to guide
              if StartGuidingConfirmed(dic["ID"], vState, 5):
#TODO: if end time reached, then just exit from this target here
                  Error("**Unable to start guiding (after meridian flip) even after several attempts")
                  ##SafetyPark(vState)
                  ##raise SoundAlarmError,'Halting program'
                  raise WeatherError

          Log2(2,"Completed meridian flip during Light Exposure loop.")

      PrepareAdvancedFocusComp(dic,vState)  #this will run benchmark focus ONCE per evening when appropriate, if enabled

      #Log("Inside exposure/sequence loop, i = %d" % (i))  #only write this message if we are going to take another exposure
      #SendToServer(getframeinfo(currentframe()),"Take exposure")

      #
      #imaging activity based on camera, sequence vs singles
      # (these have delay loops testing for skip ahead during current exposure)
      # (it is decided here whether to reposition scope or just end step)
      #
      if dCamera == "imager":
          tup = implImagerExposure(i,dic,vState)
          if tup[0] != 0:
              return tup      #stop this step and skip ahead to another one

      if dCamera == "guider":
          bLast = False  #used to decide if PP solve/sync of image; don't need for last exposure
          if dLimit == "count" and i == dRepeat:
              bLast = True
          tup = implGuiderExposure(i,dic,vState,bLast)
          if tup[0] != 0:
              return tup      #stop this step and skip ahead to another one
      Log2(4,"Bottom of LightExposures loop")

   Log2(1,"Exposure loop ended normally")
   #leave guider running in case next step at same target

   return (0,)

#--------------------------------------------------------------------------------------------------------
def RetryInitialMovementUntilClear(dic,vState):
    raise WeatherError
    #THIS CODE WAS OBSOLETE; USE WeatherError EXCEPTION INSTEAD

#--------------------------------------------------------------------------------------------------------
def implAutoPickFocus(dic,vState):
    #dic["camera"] = "imager"
    #return implExp(dic,vState)

    #2014.05.30 JU: changed logic so it does not overwrite the dic[] input object with each star it tries;
    #               this was a problem if a star in the focus list cannot be found on a subsequent iteration.

    #this is auto focus, meaning the focus star is automatically chosen;
    #if there is a problem focusing w/ a star, try again w/ another one;
    #keep trying until success; otherwise I can end up with misfocused
    #images. It is better to let this continue retrying all night than
    #to get poorly focused (and useless) images
    while 1:
       if dic["location"] == "near":
           #find near specified catalog object
           tpos = LookupObject( dic["ID"] )
           tband = BuildFocusStarBand(tpos,vState)
           fstar = FindNearFocusStar(vState,tpos, tband[0], tband[1])

       elif dic["location"] == "nearcurrent":
           #use current scope coords and find star near here
           tpos = Position()
           tpos.setJNowDecimal(vState.MOUNT.RightAscension, vState.MOUNT.Declination)
           tband = BuildFocusStarBand(tpos,vState)
           fstar = FindNearFocusStar(vState,tpos, tband[0], tband[1])

       else:
           #pick a side of sky for focus star based on current scope position
           #if vState.MOUNT.SideOfPier == 0:
           if SideOfSky(vState) == 0:
               #on east side of pier looking west; try to pick focus star to the west
               desiredRA = vState.MOUNT.SiderealTime - 1.5
               #larger offset here to try to keep to west of meridian when it
               # searches eastward for a star below
               if desiredRA < 0:
                   desiredRA += 24
           else:
               #on west side of pier looking east; pick focus star to the east
               desiredRA = vState.MOUNT.SiderealTime + 0.5
               if desiredRA >= 24:
                   desiredRA -= 24
           fstar = FindFocusStar(desiredRA)  #this searches EASTWARD from specified RA

       #use the star picked above for focusing
       dic3 = {}
       dic3["type"]       = "focus"
       dic3["location"]   = "nearcurrent"
       dic3["camera"]     = "Guider"
       dic3["isSeq"]      = "no"
       dic3["PP-Solve"]   =  1
       dic3["limit"]      = "count"
       dic3["type"]       = "light"
       #dic3["ID"]         = "Nearby Focus Star"
       #dic3["exp"]        = 10
       dic3["repeat"]     = 1
       dic3["bin"]        = 1
       dic3["filter"]     = 'L'

       pos = Position()
       pos.setJ2000Decimal(fstar.dRA,fstar.dDec,fstar.name)
       dic3["ID"] = fstar.name
       dic3["pos"] = pos
       Log2(0," " )
       Log2(0,"** AutoFocus using %s" % (fstar.name))

       tup = implExp_StartCondition(dic3,vState)
       if tup[0] != 0:
          return tup
       tup = implExp_InitialMovement(dic3,vState)
       if tup[0] != 0:
            #2017.08.30 JU: changed to raise weather exception; used to call RetryInitialMovementUntilClear (obsolete)
            raise WeatherError
            ###if RetryInitialMovementUntilClear(dic3,vState):
            ###    return tup  #unable to retry, or too late
            #else retry eventually succeeded
            ###Log2(0,"Eventual success for Initial Movement(in autofocus), continue")

       dic3["exp"] = 0.1
       if callFocusMax(dic3,vState):
          #focus completed succesfully
          return (0,)

       IgnoreFocusStars.append(fstar.name)
       #mark this as a problem star for this session (maybe behind tree or cloud?)
       #we don't want to try this one again this session, but OK to retry in the
       #future
       Log2(4,"Focus Star Failure:")
       Log2(4,"   Name:  %s" % fstar.name)
       Log2(4,"   RA:    %s" % vState.UTIL.HoursToHMS(fstar.dRA,":",":","",1))
       Log2(4,"   Dec:   %s" % DegreesToDMS(fstar.dDec))

       #2012.04.07 JU: changed to check sun altitude to decide if too late to autofocus
       now = time.gmtime()
       utc = float(now[3]) + (float(now[4])/60.) + (float(now[5])/3600.)

       #Do not run any imaging steps if sun too high IN THE MORNING!
       if utc > 5.0 and utc < 18.0:
        if CheckSunAltitude(-7):
           Log2(0,"!!AutoFocus aborted because sun too high in dawn sky (> -7)")
           return(0,)

       Log2(1,"**********************************************")
       Log2(1,"** AutoFocus repeating for a different star **")
       Log2(1,"**********************************************")


#--------------------------------------------------------------------------------------------------------
# Execute one step. This can be with either camera, and limited by several criteria,
# plus handles skip-ahead events interrupting this step.  This function also handles moving the
# telescope and finding the object, as well as starting guiding.  It assumes that the input
# values in the 'dic' object are valid! Very little validation is done here; it is assumed to
# have been done before calling here.
def implExp(dic,vState):
    #*-coding done-*#
    # dic = dictionary of commands (see documentation above for permitted combinations)
    # return:
    #   (0,) = success, go on to next step
    #   (1,index) = a "skip-ahead" event occurred, execute step[index] next
    #   (2,) = error, stop the script
    Log2(4,"implExp called with: %s" % str(dic))
    #SendToServer(getframeinfo(currentframe()),"implExp")

    global gCurrentTarget
    global gSubstep
    gSubstep = ""

    try:
        gCurrentTarget = "Target: " + dic["ID"]
    except:
        gCurrentTarget = "Target: Unspecified"

    if (dic["location"] == "auto" or dic["location"] == "near" or dic["location"] == "nearcurrent") and dic["type"] == "focus":
        gCurrentTarget = "Step: autofocus"
        return implAutoPickFocus(dic,vState)

    #
    # Is start condition met?
    #
    tup = implExp_StartCondition(dic,vState)
    if tup[0] != 0:
        return tup

    #
    # Does this step require movement of the mount? This turns on guiding after slew, if appropriate
    #  (note: this does nothing for Park/Flat; they are handled later in special cases)
    #  This uses PP solves to precisely position the mount.
    #
    tup = implExp_InitialMovement(dic,vState)
    if tup[0] != 0:
        #2017.08.30 JU: changed to raise weather exception; used to call RetryInitialMovementUntilClear (obsolete)
        raise WeatherError

        ###if RetryInitialMovementUntilClear(dic,vState):		#2016.01.02 JU: WARNING: this waits but does not take dark frames while waiting; it is apparently an old design for dealing w/ clouds; THIS SHOULD BE MERGED INTO NEW DESIGN FOR BAD WEATHER
        ###    return tup  #unable to retry, or too late
        #else retry eventually succeeded
        ###Log2(0,"Eventual success for Initial Movement, continue")

    #
    # Handle all different types of steps...
    #
    dType = dic["type"].lower()

    if dType == "light":                                # <<<--------------------------
       return implExp_LightExposures(dic,vState)        # <<<---most images taken here!
                                                        # <<<--------------------------

    #this only used for focus commands given specific target/coords.
    if dType == "focus":
       if callFocusMax(dic,vState):
           return (0,)
       #mark this as a problem star for this session (maybe behind tree or cloud?)
       #we don't want to try this one again this session, but OK to retry in the
       #future
       try:
           IgnoreFocusStars.append(dic["ID"])
           Log2(4,"Focus Star Failure:")
           Log2(4,"   Name:  %s" % dic["ID"])
           Log2(4,"   RA:    %s" % dic["RA"])
           Log2(4,"   Dec:   %s" % dic["Dec"])
       except:
           Log2(4,"Focus Star Failure, unable to log; missing dic[] entry?")

       return (0,)  #let the calling routine continue from this

    if dType == "park":
       gCurrentTarget = "Step: Park"
       return implPark(vState)

    if dType == "flat":
       gCurrentTarget = "Step: Flats"
       return implFlat(dic,vState)

    if dType == "bias":
       gCurrentTarget = "Step: Bias"
       return implBias(dic,vState)

    if dType == "goto":
       #no other action needed for this step
       return (0,)

    Error("dic[type] invalid")
    return (2,)    #error, stop processing

#--------------------------------------------------------------------------------------------------------
# This tests whether another exposure should be started (skip ahead), or whether the step's end condition
# has been reached.  One step will only have one end condition, but it could be based on time
# or target altitude or sun altitude.  This test is done *BETWEEN* exposures; this is different
# from the test done during an exposure to for skip ahead events or pier limits (not done here).
# Note that this function does NOT limit an exposure/sequence by fixed number of counts; that is
# done directly in the implExp function instead.
#   dic["limit"] = "time"   repetition limited by end time (UT)
#       dic["endTime"] = string w/ UT time, ex: "11:55"
#   dic["limit"] = "sunAltitude" expose as long as sun altitude is *below* horizon by at least specified value
#       dic["altitude"] = decimal degrees; stop if sun higher than this
#   dic["limit"] = "targetAltitude" expose as long as target altitude is *above* horizon by at least specified value
#       dic["altitude"] =  decimal degrees; stop if target lower than this altitude
def TestEndConditionReached(dic,vState):
    #return True if end condition reached, called by implExp_LightExposures()

    dLimit = dic["limit"].lower()

    if dLimit == "time":
        timeStr  = dic["endTime"].strip()   #value is UT string: hh:mm or hh:mm:ss (seconds are ignored)
        tup = tuple( timeStr.split(':') )
        nHour = int( tup[0] )
        nMin  = int( tup[1] )
        minutesPast = (nHour * 60) + nMin   #this is the # of minutes past GMT midnight when we want to stop

        gmt = time.gmtime()     #this returns current time in GMT tuple
        gHour = gmt[3]
        gMin  = gmt[4]
        gMinutesPast = (gHour * 60) + gMin  #current number of minutes past midnight GMT

        if gMinutesPast > (22 * 60):    #if current time is later then 22:00 GMT, we started before 0h so assume end time NOT reached yet
            if minutesPast > (22*60) and gMinutesPast >= minutesPast:
                Log2(0,"End time reached(2): STOPPING. Time to stop = %s, GMT now = %02d:%02d" % (dic["endTime"],gHour,gMin))
                return True             #time to stop
            Log2(1,"Assume end time not reached yet because current time > 22:00 GMT")
            #Log2(1,"Time to stop = " + timeStr + ", current time = " + str(gHour) + ":" + str(gMin) + " GMT")
            Log2(1,"Time to stop = %s, current time = %02d:%02d GMT" % (timeStr,gHour,gMin) )
            return False

        if gMinutesPast >= minutesPast:
            Log2(0,"End time reached: STOPPING. Time to stop = %s, GMT now = %02d:%02d" % (dic["endTime"],gHour,gMin))
            return True             #time to stop
        #Log2(1,"End time not reached yet: not stopping.")
        #Log2(1,"Time to stop = " + timeStr + ", current time = " + str(gHour) + ":" + str(gMin) + " GMT")
        Log2(1,"Time to stop = %s, current time = %02d:%02d GMT" % (timeStr,gHour,gMin) )
        return False

    if dLimit == "sunAltitude":
        #check sun's current altitude
        Log2(0, "sunAltitude not implemented")
        return True


    if dLimit == "targetAltitude":
        #check the target's current altitude (meaning check the scope's current alt since we should be pointing at it!)
        if vState.MOUNT.Altitude < dic["altitude"]:
            Log2(0,"***************************")
            Log2(0,"** Altitude limit reached *")
            Log2(0,"***************************")
            Log2Summary(0,"Altitude limit reached");

            Log2(1,"Current altitude = %5.2f,  Target altitude = %5.2f" % (vState.MOUNT.Altitude, dic["altitude"]))
            return True
        Log2(1,"Target altitude not reached yet: current altitude = %5.2f, target altitude = %5.2f" % (vState.MOUNT.Altitude, dic["altitude"]))
        return False

    Log2(4,"TestEndCondition: no limits reached")
    return False

#--------------------------------------------------------------------------------------------------------
import traceback
def formatExceptionInfo(maxTBlevel=10):
     cla, exc, trbk = sys.exc_info()
     try:
         excName = cla.__name__
     except:
         excName = " "

     try:
         excArgs = exc.__dict__["args"]
     except KeyError:
         excArgs = " "
     excTb = traceback.format_tb(trbk, maxTBlevel)
     return (excName, excArgs, excTb)

def nicePrintExceptionInfo(maxTBlevel=10):  #this only prints to the console; only used at end of prgm
    val = formatExceptionInfo(maxTBlevel)

    print " "
    print "--------------------------------------------------"
    print "|             General Exception                  |"
    print "--------------------------------------------------"
    print "Call trace (most recent call last):"
    for line in val[2]:
        print line

    #print out the actual error causing the exception:
    print "vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv"
    print "> ",val[0],val[1],sys.exc_value
    print "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"

def niceLogExceptionInfo():     #this writes exception to the Log
    val = formatExceptionInfo()

    Log2(0, " ")
    Log2(0,"--------------------------------------------------")
    Log2(0,"|             General Exception                  |")
    Log2(0,"--------------------------------------------------")
    Log2(0,"Call trace (most recent call last):")
    for line in val[2]:
        Log2(0,line)

    #print out the actual error causing the exception:
    print "> ",val[0],val[1],sys.exc_value
    print
    Log2(0,"vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv")
    try:
        #not sure how to format this, so catch any exception here if this is wrong
        Log2(0,"> %s" % str(val[0]))
        Log2(0,"> %s" % str(val[1]))
        Log2(0,"> %s" % str(sys.exc_value))
    except:
        Log2(0,"!!!Unable to log exception parameters, check stdout for print line!!!")
    Log2(0,"^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")

def niceLogNonFatalExceptionInfo():     #this writes exception to the Log; this is ONLY used by the function GOTO()
    val = formatExceptionInfo()

    Log2(0, " ")
    Log2(0,"--------------------------------------------------")
    Log2(0,"|            Non-fatal Exception                  |")
    Log2(0,"--------------------------------------------------")
    Log2(1,"This is for info only.")
    Log2(0,"Call trace (most recent call last):")
    for line in val[2]:
        Log2(0,line)

    #print out the actual error causing the exception:
    print "> ",val[0],val[1],sys.exc_value
    print
    Log2(0,"vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv")
    try:
        #not sure how to format this, so catch any exception here if this is wrong
        Log2(0,"> %s" % str(val[0]))
        Log2(0,"> %s" % str(val[1]))
        Log2(0,"> %s" % str(sys.exc_value))
    except:
        Log2(0,"!!!Unable to log exception parameters, check stdout for print line!!!")
    Log2(0,"^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")

#-------------------------------------------------------------------------------------
def CheckPrepareRun():
    pass
    tup = time.gmtime(time.time())
    if tup[3] > 18:
        #late in prev day, want to use next GMT date
        secTime = time.time()
        secTime = secTime + 86400.0     # advance by one day for NEXT date
        iDateTime = time.gmtime(secTime)
    else:
        iDateTime = time.gmtime()

    sDateStr = ObservingDateString()	#time.strftime('%Y%m%d',iDateTime)
    sPathDate = sDateStr[0:4] + '-' + sDateStr[4:6] + '-' + sDateStr[6:8]

    sPathRoot = BASE + r"\Astronomy Observations"
    sPath = os.path.join(sPathRoot,sDateStr[0:4],sPathDate)		#changed 2015.01.16 for new directory path including year:  [BASE]\Astronomy Observations\yyyy\yyyy-mm-dd

    if not os.path.exists(sPath):
		#Check alternate path before reporting error
        sPathRoot = BASE2 + r"\Astronomy Observations"
        sPath = os.path.join(sPathRoot,sDateStr[0:4],sPathDate)		#changed 2015.01.16 for new directory path including year:  [BASE]\Astronomy Observations\yyyy\yyyy-mm-dd
        if not os.path.exists(sPath):
			#neither path exists, so report problem
			print "Path does NOT exist:",sPath
			return False

    return True

#=====================================================================================
#==== SECTION  @@ENTRY ===========================================================
#=====================================================================================

#-#####
# The script starts here
#-######
#print "Remember: run eserver.py first if want to receive realtime updates of program state"

#SendToServer(getframeinfo(currentframe()),"========= Startup ===========")

#Make sure the log file has a break showing a new start
ObservingDateSet()
LogHeader()
print "Observing date =", ObservingDateString()

try:
    okToRun = False
    if len(sys.argv) == 1:
        #attempt to restart using 'Exec_reload.txt' file
        if not os.path.isfile(RELOADFILE):
            print " "
            print "==>  The file " + RELOADFILE + " does not exist; nothing to restart."
            print " "
        else:
            okToRun = True
            script = RELOADFILE

    elif len(sys.argv) != 2:
        print "Usage:  Exec5.py  cmdfilename.txt"
        print "  Before running this, should run Prepare Observation script (ObsPrep4.py)"
    else:
        okToRun = True
        script = sys.argv[1]

    #SendToServer(getframeinfo(currentframe()),"OK to run")

    if okToRun:
        #---everything happens here---

        #check that Prepare Observation script already run
        if not CheckPrepareRun():
                print " "
                print "**********************************************************"
                print "STOP: you have not run the Prepare Observation script yet."
                print "**********************************************************"
                print " "
                raise ValidationError

        Log2(0,"                     Command file: %s" % script)
        Log2(0," ")
        Log2(0," ")

        print "call PrepareFocusStarList..."
        PrepareFocusStarList()
        cmdList = []

        print "call LoadList..."
        LoadList( script, cmdList )     #read the specified command file into memory

        print "call ValidateList..."
        ValidateList( cmdList )              #validate that all catalog entries are valid

        print "call ExecuteList..."
        ExecuteList( cmdList )               #actually run the loaded commands

except ValidationError:
    print "Cannot run because of ValidationError"
    #SendToServer(getframeinfo(currentframe()),"Validation Error")

except EnvironmentError:
    #We already reported the error before reaching here.
    pass
    #SendToServer(getframeinfo(currentframe()),"Environment Error")

except KeyboardInterrupt:
    Log2(0,"**Exit program via KeyboardInterrupt**")

except: #catch any other exception to sound alarm and get operator's attention!
    #SendToServer(getframeinfo(currentframe()),"something happened")

    #consider adding call to SafetyPark here ?!

    import winsound
    print niceLogExceptionInfo()

    print " "
    print "--------------------------------------------------"
    print "|     Sounding alarm (press Ctrl-C to end)       |"
    print "--------------------------------------------------"
    print " (Remember: Exec_reload.txt available for restart)"
    print " "
    try:
        while(1):
            winsound.MessageBeep(winsound.MB_ICONHAND)
            time.sleep(.3)
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            time.sleep(.2)
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            time.sleep(.3)

            #IDEA: take dark/bias frames during this time?
    except:
        pass    #keyboard interrupted to end.


Log2(0,"** End of script **")
#Consider adding sound here to alert me that script ended??
#SendToServer(getframeinfo(currentframe()),"End of script reached.")
#SendToServer(getframeinfo(currentframe()),"EXIT")   #special command that tells server process to exit
