#-------------------------------------------------------------------------------
# Name:        imaging_db.py
# Purpose:     Database funcitonality used by Exec5D.py program; this module
#               is imported into there for use. This module can also be run
#               stand-alone for testing
#
# This has 4 main entry points plus one startup function
#
# Author:      Joe Ulowetz
#
# Created:     02/09/2018
# Copyright:   (c) W510 2018
# Licence:     <your licence>
#
#Trace values: 1001-1099 normal activity
#	      1100-1199 minor problem/delay/waiting
#	      1200-1299 problem/concern
#	      1300-1399 SERIOUS PROBLEM
#
#
#TODO: protect against this:
#    Traceback (most recent call last):
#  File "C:\fits_script\imaging_db.py", line 638, in <module>
#    main()
#  File "C:\fits_script\imaging_db.py", line 626, in main
#    cstate = cTestState()
#  File "C:\fits_script\imaging_db.py", line 605, in __init__
#    SqliteStartup( self.SQLITE, 'Self-test' )    #record start of prgm in Startup table of database
#  File "C:\fits_script\imaging_db.py", line 34, in SqliteStartup
#    {'Julian':sJulian,'Process':processName})
#OperationalError: database is locked
#-------------------------------------------------------------------------------

import win32com.client      #needed to load COM objects

import sqlite3
Imaging_Database = "C:/fits_script/exec_db.db"

#
#--- Main entry points called from Exec5D.py
#
def SqliteStartup(conn,processName):
    cur = conn.cursor()
    sJulian = GetJulianDate(cur)
    cur.execute("INSERT INTO Startup (Julian,Process) VALUES (:Julian,:Process)",
        {'Julian':sJulian,'Process':processName})
    conn.commit()

  
#-------------------------------------------------------------------------------
def RecordMount(vState,trace):
    conn = vState.SQLITE
    cur = conn.cursor()
    #Source of data:
	#strftime('%J','now')
	#vState.MOUNT.RightAscension
	#vState.MOUNT.Declination
	#vState.MOUNT.Altitude
	#vState.MOUNT.Azimuth
	#vState.MOUNT.SiderealTime
	#calc( SiderealTime - RightAscension )
	#vState.MOUNT.Tracking
	#vState.MOUNT.Slewing
	#vState.MOUNT.SideOfPier
	#vState.MOUNT.AtPark
	#vState.MOUNT.AtHome
    julian = GetJulianDate(cur)

    fields = 0
    bad = 0

    try:
        fields += 1
        RA = vState.MOUNT.RightAscension
    except:
        RA = 99
        bad += 1

    try:
        fields += 1
        Dec =  vState.MOUNT.Declination
    except:
        Dec = 99
        bad += 1

    try:
        fields += 1
        alt = vState.MOUNT.Altitude
    except:
        alt = 0
        bad += 1

    try:
        fields += 1
        az = vState.MOUNT.Azimuth
    except:
        az = 0
        bad += 1

    try:
        fields += 1
        ST = vState.MOUNT.SiderealTime
    except:
        ST = 99
        bad += 1

    if RA == 99 or ST == 99:
        #one (or both) of these are invalid, so cannot calc HA
        HA = 99
    else:
        HA = ST - RA
        if HA > 12:
            HA -= 24
        elif HA < -12:
            HA += 24

    try:
        fields += 1
        track = vState.MOUNT.Tracking
    except:
        track = 99
        bad += 1

    try:
        fields += 1
        slew = vState.MOUNT.Slewing
    except:
        slew = 99
        bad += 1

    try:
        fields += 1
        side = vState.MOUNT.SideOfPier
    except:
        side = 9
        bad += 1

    try:
        fields += 1
        park = vState.MOUNT.AtPark
    except:
        park = 9
        bad += 1

    try:
        fields += 1
        home = vState.MOUNT.AtHome
    except:
        home = 9
        bad += 1

    #print "[RecordMount]: %d fields, %d bad" % (fields,bad)
    cur.execute("""
        INSERT INTO Mount (
            Julian,
            RA,
            Dec,
            Alt,
            Az,
            Sidereal,
            HA,
            Tracking,
            Slewing,
            SideOfPier,
            AtPark,
            AtHome,
            Trace,
            bad)
        VALUES (
            :Julian,
            :RA,
            :Dec,
            :Alt,
            :Az,
            :Sidereal,
            :HA,
            :Tracking,
            :Slewing,
            :SideOfPier,
            :AtPark,
            :AtHome,
            :Trace,
            :bad)""",
        {'Julian':julian,
        'RA':RA,
        'Dec':Dec,
        'Alt':alt,
        'Az':az ,
        'Sidereal':ST,
        'HA':HA,
        'Tracking':track,
        'Slewing':slew,
        'SideOfPier':side,
        'AtPark':park,
        'AtHome':home,
        'Trace':trace,
        'bad':bad})

    conn.commit()
    return bad

#-------------------------------------------------------------------------------
def RecordCamera(vState,trace):     #SEE:  LogConditions(vState)
    conn = vState.SQLITE
    cur = conn.cursor()
    #Source of data:
	#strftime('%J','now')
	#vState.CAMERA.Temperature
	#vState.CAMERA.CoolerPower
	#vState.CAMERA.CameraStatus
	#vState.CAMERA.FWHM
	#vState.CAMERA.HalfFluxDiameter
	#vState.CAMERA.Filter
    julian = GetJulianDate(cur)
    fields = 0
    bad = 0

    try:
        fields += 1
        temperature = vState.CAMERA.Temperature
    except:
        temperature = 99
        bad += 1

    try:
        fields += 1
        cooler = vState.CAMERA.CoolerPower
    except:
        cooler = 0
        bad += 1

    try:
        fields += 1
        status = vState.CAMERA.CameraStatus
    except:
        status = 99
        bad += 1

    try:
        fields += 1
        fwhm =  vState.CAMERA.FWHM
    except:
        fwhm = 0
        bad += 1

    try:
        fields += 1
        hfd = vState.CAMERA.HalfFluxDiameter
    except:
        hfd = 0
        bad += 1

    try:
        fields += 1
        filter = vState.CAMERA.Filter
    except:
        filter = 9
        bad += 1

    #print "[RecordCamera]: %d fields, %d bad" % (fields,bad)
    cur.execute("""
        INSERT INTO Camera (
            Julian,
            TempC,
            Power,
            CamStat,
            FWHM,
            HFD,
            Filter,
            Trace,
            bad)
        VALUES (
            :Julian,
            :TempC,
            :Power,
            :CamStat,
            :FWHM,
            :HFD,
            :Filter,
            :Trace,
            :bad)""",
        {'Julian':julian,
        'TempC':temperature,
        'Power':cooler,
        'CamStat':status,
        'FWHM':fwhm,
        'HFD':hfd,
        'Filter':filter,
        'Trace':trace,
        'bad':bad})
    conn.commit()
    return bad

#-------------------------------------------------------------------------------
def RecordGuider(vState,bNewMeasurement,trace):
    conn = vState.SQLITE
    cur = conn.cursor()
    #Source of data:
	#strftime('%J','now')
    #vState.CAMERA.GuiderXError
    #vState.CAMERA.GuiderYError
    #vState.CAMERA.GuiderAggressivenessX
    #vState.CAMERA.GuiderAggressivenessY
    #vState.CAMERA.GuiderReverseX
    #vState.CAMERA.GuiderTemperature
    #vState.CAMERA.GuiderCoolerPower
    #vState.CAMERA.GuiderMoving
    #####vState.CAMERA.GuiderNewMeasurement     WARNING: reading this field resets the flag, so only the main script logic should read it
    #vState.CAMERA.GuiderRunning
    #vState.CAMERA.GuiderXStarPosition
    #vState.CAMERA.GuiderYStarPosition
    #vState.CAMERA.LastGuiderError
    julian = GetJulianDate(cur)
    fields = 0
    bad = 0

    try:
        fields += 1
        guideX = vState.CAMERA.GuiderXError
    except:
        guideX = 0
        bad += 1

    try:
        fields += 1
        guideY = vState.CAMERA.GuiderYError
    except:
        guideY = 0
        bad += 1

    try:
        fields += 1
        aggrX = vState.CAMERA.GuiderAggressivenessX
    except:
        aggrX = 0
        bad += 1

    try:
        fields += 1
        aggrY = vState.CAMERA.GuiderAggressivenessY
    except:
        aggrY = 0
        bad += 1

    try:
        fields += 1
        reverseX = vState.CAMERA.GuiderReverseX
    except:
        reverseX = 9
        bad += 1

    try:
        fields += 1
        temperature = vState.CAMERA.GuiderTemperature
    except:
        temperature = 0
        bad += 1

    try:
        fields += 1
        cooler = vState.CAMERA.GuiderCoolerPower
    except:
        cooler = 0
        bad += 1

    try:
        fields += 1
        moving = vState.CAMERA.GuiderMoving
    except:
        moving = 9
        bad += 1

    try:
        fields += 1
        running = vState.CAMERA.GuiderRunning
    except:
        running = 9
        bad += 1

    try:
        fields += 1
        starX = vState.CAMERA.GuiderXStarPosition
    except:
        starX = 0
        bad += 1

    try:
        fields += 1
        starY = vState.CAMERA.GuiderYStarPosition
    except:
        starY = 0
        bad += 1

    try:
        fields += 1
        lastErr = vState.CAMERA.LastGuiderError
    except:
        vState.CAMERA.LastGuiderError = 9
        bad += 1

    #print "[RecordGuider]: %d fields, %d bad" % (fields,bad)
    cur.execute("""
        INSERT INTO Guider (
            Julian,
            GuiderXError,
            GuiderYError,
            GuiderXAggr,
            GuiderYAggr,
            GuiderReverseX,
            TempC,
            Power,
            Moving,
            NewData,
            Running,
            StarX,
            StarY,
            LastErr,
            Trace,
            bad)
        VALUES (
            :Julian,
            :GuiderXError,
            :GuiderYError,
            :GuiderXAggr,
            :GuiderYAggr,
            :GuiderReverseX,
            :TempC,
            :Power,
            :Moving,
            :NewData,
            :Running,
            :StarX,
            :StarY,
            :LastErr,
            :Trace,
            :bad) """,
        {'Julian':julian,
        'GuiderXError':guideX,
        'GuiderYError':guideY,
        'GuiderXAggr':aggrX,
        'GuiderYAggr':aggrY,
        'GuiderReverseX':reverseX,
        'TempC':temperature,
        'Power':cooler,
        'Moving':moving,
        'NewData':bNewMeasurement,      #Note: provided by caller
        'Running':running,
        'StarX':starX,
        'StarY':starY,
        'LastErr':lastErr,
        'Trace':trace,
        'bad':bad})

    conn.commit()
    return bad

#Maybe add additional calls for Guider if problem such as Oscillation?

#-------------------------------------------------------------------------------
def RecordFocuser(vState,trace):
    conn = vState.SQLITE
    cur = conn.cursor()
    #Source of data:
	#strftime('%J','now')
    #vState.FOCUSCONTROL.Position
    #vState.FOCUSCONTROL.Temperature
    #vState.FOCUSCONTROL.IsMoving
    #vState.FOCUSCONTROL.IsBusy
    #vState.FOCUSCONTROL.FocusAsyncStatus
    #vState.FOCUSCONTROL.HalfFluxDiameter
    #vState.FOCUSCONTROL.TotalFlux
    #vState.FOCUSCONTROL.StarXCenter
    #vState.FOCUSCONTROL.StarYCenter
    #vState.FOCUSCONTROL.SingleExposeAsyncStatus
    julian = GetJulianDate(cur)
    fields = 0
    bad = 0
    try:
        fields += 1
        position = vState.FOCUSCONTROL.Position
    except:
        position = 0
        bad += 1

    try:
        fields += 1
        temperature = vState.FOCUSCONTROL.Temperature
    except:
        temperature = 0
        bad += 1

    try:
        fields += 1
        ismoving = vState.FOCUSCONTROL.IsMoving
    except:
        ismoving = 9
        bad += 1

    try:
        fields += 1
        isbusy = vState.FOCUSCONTROL.IsBusy
    except:
        isbusy = 9
        bad += 1

    try:
        fields += 1
        status = vState.FOCUSCONTROL.FocusAsyncStatus
    except:
        status = 99
        bad += 1

    try:
        fields += 1
        hfd = vState.FOCUSCONTROL.HalfFluxDiameter
    except:
        hfd = 0
        bad += 1

    try:
        fields += 1
        flux = vState.FOCUSCONTROL.TotalFlux
    except:
        flux = 0
        bad += 1

    try:
        fields += 1
        starX = vState.FOCUSCONTROL.StarXCenter
    except:
        starX = 0
        bad += 1

    try:
        fields += 1
        starY = vState.FOCUSCONTROL.StarYCenter
    except:
        starY = 0
        bad += 1

    try:
        fields += 1
        se_status = vState.FOCUSCONTROL.SingleExposeAsyncStatus
    except:
        se_status = 99
        bad += 1

    #print "[RecordFocuser]: %d fields, %d bad" % (fields,bad)
    cur.execute("""
        INSERT INTO Focuser (
            Julian,
            Position,
            Temperature,
            IsMoving,
            IsBusy,
            FocusStatus,
            HFD,
            TotalFlux,
            StarXCenter,
            StarYCenter,
            ExposeStatus,
            Trace,
            bad)
        VALUES (
            :Julian,
            :Position,
            :Temperature,
            :IsMoving,
            :IsBusy,
            :FocusStatus,
            :HFD,
            :TotalFlux,
            :StarXCenter,
            :StarYCenter,
            :ExposeStatus,
            :Trace,
            :bad)""",
        {'Julian':julian,
        'Position':position,
        'Temperature':temperature,
        'IsMoving':ismoving,
        'IsBusy':isbusy,
        'FocusStatus':status,
        'HFD':hfd,
        'TotalFlux':flux,
        'StarXCenter':starX,
        'StarYCenter':starY,
        'ExposeStatus':se_status,
        'Trace':trace,
        'bad':bad})
    conn.commit()
    return bad

#-------------------------------------------------------------------------------
def RecordPerformance(vState,elapsed,split1,split2,split3):
    # elapsed is time in decimal seconds for how long DB activity took,
    # not counting this call
    conn = vState.SQLITE
    cur = conn.cursor()
    sJulian = GetJulianDate(cur)
    cur.execute("INSERT INTO Performance (Julian,elapsed,split1,split2,split3) VALUES (:Julian,:Elapsed,:Split1,:Split2,:Split3)",
        {'Julian':sJulian,'Elapsed':elapsed,'Split1':split1,'Split2':split2,'Split3':split3})
    conn.commit()

#
#--- Helper Functions --------------------------------------
#
def GetJulianDate(cur):     #cur = cursor into database
    cur.execute("SELECT strftime('%J','now')") #this returns Julian date
    x = cur.fetchone()
    return x[0]


#Test Code only below this point -------------------------------------------
class cTestState:   #only used for stand-alone testing
    def __init__(self):
        self.SQLITE = sqlite3.connect( Imaging_Database )
        SqliteStartup( self.SQLITE, 'Self-test' )    #record start of prgm in Startup table of database

        # COM objects
        #print "Connect: DriverHelper.Util"
        #self.UTIL   = win32com.client.Dispatch("DriverHelper.Util")    #NOT NEEDED
        print "Connect: MaxIm.CCDCamera"
        self.CAMERA = win32com.client.Dispatch("MaxIm.CCDCamera")
        self.CAMERA.DisableAutoShutdown = True
        self.CAMERA.LinkEnabled = True

        print "Connect: ASCOM.GeminiTelescope.Telescope"
        self.MOUNT  = win32com.client.Dispatch("ASCOM.GeminiTelescope.Telescope")
        self.MOUNT.Connected = True

        print "Connect: FocusMax.FocusControl"
        self.FOCUSCONTROL  = win32com.client.Dispatch("FocusMax.FocusControl")

        print "cState init completed"


def main():     #only used for stand-alone testing
   cstate = cTestState()
   print "Before RecordMount"
   RecordMount(cstate,0)
   RecordCamera(cstate,0)
   RecordGuider(cstate,False,0)
   RecordFocuser(cstate,0)

   print "After RecordMonth"

   pass

if __name__ == '__main__':
    main()
    print "Running stand-alone"
