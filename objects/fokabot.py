"""FokaBot related functions"""
import re

from common import generalUtils
from common.constants import actions
from common.ripple import userUtils
from constants import chatChannels
from constants import yohaneCommands, yohaneReactions
from constants import serverPackets
from objects import glob

# Tillerino np regex, compiled only once to increase performance
npRegex = re.compile("^https?:\\/\\/osu\\.ppy\\.sh\\/b\\/(\\d*)")

def connect(timeOffset = 9):
	"""
	Connect FokaBot to Bancho

	:return:
	"""
	glob.BOT_NAME = userUtils.getUsername(1)
	token = glob.tokens.addToken(1)
	token.actionID = actions.IDLE
	token.actionText = "\n-- Welcome to Datenshi --"
	#token.pp = 69
	#token.accuracy = 0.9885
	#token.playcount = 26956
	#token.totalScore = 237228316533
	token.timeOffset = timeOffset
	token.timezone = 24+token.timeOffset
	token.country = 111
	glob.streams.broadcast("main", serverPackets.userPanel(1))
	#glob.streams.broadcast("main", serverPackets.userStats(999))

def disconnect():
	"""
	Disconnect FokaBot from Bancho

	:return:
	"""
	glob.tokens.deleteToken(glob.tokens.getTokenFromUserID(1))

def fokabotResponse(fro, chan, message):
	"""
	Check if a message has triggered FokaBot

	:param fro: sender username
	:param chan: channel name (or receiver username)
	:param message: chat mesage
	:return: FokaBot's response or False if no response
	"""
	msg = message.strip()
	
	for reaction in yohaneReactions.triggers:
		callIt = False
		match  = reaction.get('match','starts')
		if match == 'exact':
			callIt = reaction['trigger'] == msg
		elif match == 'partial':
			callIt = reaction['trigger'].lower() in msg.lower()
		elif match == 'word':
			callIt = reaction['trigger'].lower() in msg.lower().split()
		elif match == 'starts':
			callIt = msg.lower().startswith(reaction['trigger'].lower() + ' ')
		elif match in ('regex', 'regexp'):
			callIt = re.compile(reaction['trigger']).match(msg)
		if callIt:
			return reaction['callback'](fro, chan, message)

	# No commands triggered
	return False

def fokabotCommands(fro, chan, message):
	msg    = message.strip()
	userID = userUtils.getID(fro)
	userPr = userUtils.getPrivileges(userID)
	for command in yohaneCommands.commands:
		# Loop though all commands
		if re.compile("^{}( (.+)?)?$".format(command["trigger"])).match(msg):
			# message has triggered a command

			# Make sure the user has right permissions
			if command["privileges"] is not None:
				if userPr & command["privileges"] != command['privileges']:
					return False

			# Check argument number
			message = message.split(" ")
			if command["syntax"] != "" and len(message) <= len(command["syntax"].split(" ")):
				return "Wrong syntax: {} {}".format(command["trigger"], command["syntax"])

			# Return response or execute callback
			if command["callback"] is None:
				return command["response"]
			else:
				return command["callback"](fro, chan, message[1:])
	
	return None
