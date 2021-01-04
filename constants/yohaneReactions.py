from common.constants import mods
from constants import chatChannels
from constants import yohaneTillerino
from objects import glob

def okegan(sender, chan_from, arguments):
    return "okegan"

def puritit(sender, chan_from, arguments):
    return "puritit bangsat 8("

def gaplok(sender, chan_from, arguments):
    return f"\x01ACTION gaplok {sender} balik\x01"

triggers = [
    {
        "trigger": "T3I",
        "match": "exact",
        "callback": okegan
    }, {
        "trigger": "puritit",
        "match": "word",
        "callback": puritit
    }, {
        "trigger": f"\x01ACTION gaplok Yohane\x01",
        "match": "exact",
        "callback": gaplok
    }, {
		"trigger": "\x01ACTION is listening to",
		"callback": yohaneTillerino.np
	}, {
		"trigger": "\x01ACTION is playing",
		"callback": yohaneTillerino.np
	}, {
		"trigger": "\x01ACTION is watching",
		"callback": yohaneTillerino.np
	}
]
