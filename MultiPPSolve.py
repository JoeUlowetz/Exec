# MultiPPSolve.py

#TODO: cannot call Log2() from here. Also can't use UTIL object (need reference to it)
#NOTE: cannot set pp MaxSolveTime less than 10 seconds;

#2019.05.05 JU: if Narrow camera, do NOT try any solutions other than 0,0

SCALE_THRESHOLD_PCT = 30  #This is a percentage (ex 30 for 30%)
import traceback
from datetime import datetime

SolveMap = {}       #SolveMap[ index into TestOffsets4 ] = count of times it solved with this offset

#2019.03.16 JU: further testing w/ Wide camera (60x40 arcmin FOV) shows that PP will solve if RA within 4 minutes
#               and Dec within 20-30 arcmin, so bracket these values. Unfortunately w/ soft ground I've seen Dec
#               off by as much as 90 arcmin.  Total: 53 attempts here, 10 seconds each max, so max time approx 9 minutes.
TestOffsets4 = [(10,60),  (5,0),   (-5,0),   (-10,0),   (10,0),   (-15,0),   (15,0),   (-20,0),   (20,0),
                (0,30),   (5,30),  (-5,30),  (-10,30),  (10,30),  (-15,30),  (15,30),  (-20,30),  (20,30),
                (0,-30),  (5,-30), (-5,-30), (-10,-30), (10,-30), (-15,-30), (15,-30), (-20,-30), (20,-30),
                (0,60),   (5,60),  (-5,60),  (-10,60),            (-15,60),  (15,60),  (-20,60),  (20,60),
                (0,-60),  (5,-60), (-5,-60), (-10,-60), (10,-60), (-15,-60), (15,-60), (-20,-60), (20,-60),
                (0,90),   (5,90),  (-5,90),  (-10,90),  (10,90),  (-15,90),  (15,90),  (-20,90),  (20,90),
                (0,-90),  (5,-90), (-5,-90), (-10,-90), (10,-90), (-15,-90), (15,-90), (-20,-90), (20,-90) ]

#-------------------------------------------------------------

#Helper functions
def AddCoordOffsets(expectedPos,deltaRA,deltaDec):
    try:
        newRADecimal = expectedPos.dRA_J2000() + (deltaRA / 60.)
        newDecDecimal = expectedPos.dDec_J2000() + (deltaDec / 60.)
        return (newRADecimal, newDecDecimal)
    except:
        print "Exception-2e"
        traceback.print_exc()
        print "ee-1"

def DisplaySolveCounts():
    if not SolveMap:
        print "SolveMap: empty"
        return
    try:
        print "***Counts for Solve offset logic:"   
        for key in SolveMap:
            if key == 0:
                print "Index: %2d, Offsets: (  0,  0), Count: %4d" % (key, SolveMap[key])
            else:
                print "Index: %2d, Offsets: (%3d,%3d), Count: %4d" % (key, TestOffsets4[key-1][0],TestOffsets4[key-1][1],SolveMap[key])
        #todo: sort by index
    except:
        print "***Exception in Solve offset count report\n"

def DisplaySolveCountStr():
    if not SolveMap:
        return "SolveMap: empty\n"
    
    try:
        msg = "***Counts for Solve offset logic:\n"   
        buf = []
        buf.append(msg)
        for key in SolveMap:
            if key == 0:
                msg = "Index: %2d, Offsets: (  0,  0), Count: %4d\n" % (key, SolveMap[key])
            else:
                msg = "Index: %2d, Offsets: (%3d,%3d), Count: %4d\n" % (key, TestOffsets4[key-1][0],TestOffsets4[key-1][1],SolveMap[key])
            buf.append(msg)
        #todo: sort by index
        return "".join(buf)
    except:
        return "***Exception in Solve offset count report\n"
    
#--------------------------------------------------------------
#Main function here:
def MultiPPSolve(pp,camera, expectedPos, vState):
  try:
    # pp = Pinpoint object created by calling function; most values already filled in before arriving here
    # camera: 0 = Narrow field, 1 = Wide field
    # expectedPos = Position() object w/ expected coord for image

    if camera == 0:
        #Imager, narrow field
        expectedScale = vState.ImagerScale  * vState.ppState[camera].binning #scale for binning
    else:
        #Guider, wide field
        expectedScale = vState.GuiderScale  #(no binning supported here)

    initialSolveTime = 20   ## vState.ppState[camera].MaxSolveTime  #use configured time for first attempt
    extraSolveTime = 10      #5 does not work; 15 works; 10 works; 9 does not work, so value must be >= 10; pp is happy w/ 300 here

    #Put expectedPos and initialSolveTime as first entry in list of values to use for solving
    TestCoordsList = [ (expectedPos.dRA_J2000(), expectedPos.dDec_J2000(), initialSolveTime,0,0),]
    #Add rest of entries to test coords; This set below is for Wide camera; maybe different for Narrow?


    #Build full list of coords to use for PP solve, after starting w/ expected position
    #2019.05.05 JU: only use additional test locations for Wide field; do NOT use for Narrow!  Narrow only uses expectedPos loaded above.
    if camera == 1:
        for item in TestOffsets4:   #USE LARGER OFFSETS
            deltaRA = item[0]
            deltaDec = item[1]
            newDecimalRA, newDecimalDec = AddCoordOffsets(expectedPos,deltaRA,deltaDec)
            TestCoordsList.append( (newDecimalRA,newDecimalDec,extraSolveTime,deltaRA,deltaDec) )

    tStart = datetime.now()
    msgList = []
    msgList.append('\n')
    for index,item in enumerate(TestCoordsList):
        pp.RightAscension = item[0]
        pp.Declination = item[1]
        #Sometimes (rarely? randomly?) PP uses these other variables when solving!
        pp.TargetRightAscension = pp.RightAscension
        pp.TargetDeclination = pp.Declination
        pp.MaxSolveTime = item[2]
        msg = "[%d] Try using: %d,%d " % (index,item[3],item[4])
        print msg
        msgList.append(msg + '\n')
        
        numCatalogStars = -1    #initialize variable just in case
        try:
            pp.FindCatalogStars()
            numCatalogStars = len(pp.CatalogStars)
            if numCatalogStars < 10:
                msg = "[%d] Warning: only found %d catalog stars" % (index,numCatalogStars)
                print msg
                msgList.append(msg + '\n')
        except Exception,e:
            msg = "[%d] Failed for FindCatalogStars" % index
            print msg
            msgList.append(msg + '\n')
            msg = "PP Exception info: " + str(e)
            msgList.append(msg + '\n')
            continue

        try:
            bSolve = pp.Solve()
        except Exception,e:
            tEnd = datetime.now()
            delta = tEnd - tStart
            msg = "[%d] [%d sec] Failed PP attempt with exception (#cat stars = %d)" % (index,delta.seconds,numCatalogStars)
            print msg
            msgList.append(msg + '\n')
            msg = "PP Exception info: " + str(e)
            msgList.append(msg + '\n')
            continue

        tEnd = datetime.now()
        delta = tEnd - tStart
        if not bSolve:
            msg = "[%d] [%d sec] Failed PP attempt (#cat stars = %d)" % (index,delta.seconds,numCatalogStars)
            print msg
            msgList.append(msg + '\n')
            continue

        diff = abs( abs(pp.ArcsecPerPixelHoriz) - expectedScale )
        if (diff/expectedScale)*100 > SCALE_THRESHOLD_PCT:
            msg = "[%d] [%d sec] Bad scale from PP attempt (#cat stars = %d)" % (index,delta.seconds,numCatalogStars)
            print msg
            msgList.append(msg + '\n')
            msg = "Expected scale = %6.3f, found = %6.3f, diff = %d%%" % (expectedScale,abs(pp.ArcsecPerPixelHoriz),int((diff/expectedScale)*100))
            print msg
            msgList.append(msg + '\n')
            continue    #added 2019.01.26 JU

        ########################
        #success at this point
        ########################
        if index in SolveMap:       #count which index values result in solves
            SolveMap[index] = SolveMap[index] + 1
        else:
            SolveMap[index] = 1
            
        msg = "[%d] [%d sec] PP SUCCESS (#cat stars = %d)" % (index,delta.seconds,numCatalogStars)
        print msg
        msgList.append(msg + '\n')
        return 1,"".join(msgList) #solution stored in pp.RightAscension, pp.Declination
    #fell out of loop without success
    msg = "Exited MultiPPSolve without success [%d sec]" % delta.seconds
    print msg
    msgList.append(msg + '\n')
    return 0,"".join(msgList)
  except Exception,e:
        print "Exception-final"
        traceback.print_exc()
        return 0,"MM EXCEPTION: " + str(e)
        