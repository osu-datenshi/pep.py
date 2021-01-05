# give noop for now
def wrapEvents(event):
    event.handle = event

def event0079(userToken, packetData):
    pass

event0079 = wrapEvents(event0079)
del wrapEvents
