# give noop for now
class lazyEventHandler():
    __slots__ = ('fun',)
    def __init__(self, fun):
        self.fun = fun
    def handle(self, userToken, packetData):
        self.fun(userToken, packetData)

@lazyEventHandler
def event0079(userToken, packetData):
    pass

del lazyEventHandler
