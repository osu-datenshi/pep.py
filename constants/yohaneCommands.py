import json
import random
import re
import threading

import requests
import time

from common import generalUtils
from common.constants import mods
from common.log import logUtils as log
from common.datenshi import rankUtils
from common.ripple import userUtils
from common.constants import gameModes
from common.constants import privileges
from common.constants import personalBestScores
from constants import exceptions, slotStatuses, matchModModes, matchTeams, matchTeamTypes, matchScoringTypes
from constants import chatChannels
from constants import serverPackets
from constants import yohaneMultiplayer as MP
from helpers import aobaHelper
from helpers import systemHelper
from objects import fokabot
from objects import glob
from helpers import chatHelper as chat
from common.web import cheesegull
from discord_webhook import DiscordWebhook, DiscordEmbed

def bloodcatMessage(beatmapID):
	beatmap = glob.db.fetch("SELECT song_name, beatmapset_id FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [beatmapID])
	if beatmap is None:
		return "Sorry, I'm not able to provide a download link for this map :("
	return "Download [https://bloodcat.com/osu/s/{} {}] from Bloodcat".format(
		beatmap["beatmapset_id"],
		beatmap["song_name"],
	)

def beatconnectMessage(beatmapID):
	beatmap = glob.db.fetch("SELECT song_name, beatmapset_id FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [beatmapID])
	if beatmap is None:
		return "Sorry, I'm not able to provide a download link for this map :("
		return "Download from beatconnect has been disabled, because the site is already shutdown"
		#beatmap["beatmapset_id"],
		#beatmap["song_name"],
	#)
	
def mirrorMessage(beatmapID):
	beatmap = glob.db.fetch("SELECT song_name, beatmapset_id FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [beatmapID])
	if beatmap is None:
		return "Sorry, I'm not able to provide a download link for this map :("
	return "Download {} from [https://bloodcat.com/osu/s/{} Bloodcat] or [osu://dl/{} osu!direct].".format(
		beatmap["song_name"],
		beatmap["beatmapset_id"],
		beatmap["beatmapset_id"],
	)
	
"""
Commands callbacks

Must have sender, channel and messages as arguments
:param fro: username of who triggered the command
:param chan: channel"(or username, if PM) where the message was sent
:param message: list containing arguments passed from the message
				[0] = first argument
				[1] = second argument
				. . .

return the message or **False** if there's no response by the bot

1) it's fucking dumb to call fro, chan ok? use normal shit like sender, channel as alternative.
   not everyone could understand this. this is what happens when you do shit with roblox word every seconds.
"""
def instantRestart(fro, chan, message):
	glob.streams.broadcast("main", serverPackets.notification("We are going to instants restart for 60sec"))
	systemHelper.scheduleShutdown(0, True, delay=60)
	return False

def faq(fro, chan, message):
	# TODO: Unhardcode this
	messages = {
		"rules": "Please make sure to check (Datenshi rules)[https://osu.troke.id/doc/rules].",
		"swearing": "Please don't abuse swearing",
		"spam": "Please don't spam",
		"offend": "Please don't offend other players",
		"discord": "(Join Datenshi Discord!)[https://link.troke.id/datenshi]",
		"ping": "NGIK NGOK NGEK PONG",
		"bruh": "BRUH",
		"changelog": "Check the (changelog)[https://osu.troke.id/changelog] !",
		"english": "Please keep this channel in english.",
		"topic": "Can you please drop the topic and talk about something else?",
		"lines": "Please try to keep your sentences on a single line to avoid getting silenced.",
		"vote": "Dont forget to vote us! (Click Here)[https://link.troke.id/vote]"
	}
	key = message[0].lower()
	if key not in messages:
		return False
	return messages[key]

def roll(fro, chan, message):
	maxPoints = 100
	if len(message) >= 1 and (message[0].isdigit() and int(message[0]) > 0):
		maxPoints = int(message[0])

	points = random.randint(1,maxPoints)
	return "{} rolls {} points!".format(fro, str(points))

#def ask(fro, chan, message):
#	return random.choice(["yes", "no", "maybe"])

def alert(fro, chan, message):
	msg = ' '.join(message[:]).strip()
	if not msg:
		return False
	glob.streams.broadcast("main", serverPackets.notification(msg))
	return False

def alertUser(fro, chan, message):
	target = message[0].lower()
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		msg = ' '.join(message[1:]).strip()
		if not msg:
			return False
		targetToken.enqueue(serverPackets.notification(msg))
		return False
	else:
		return "User offline."

def moderated(fro, chan, message):
	try:
		# Make sure we are in a channel and not PM
		if not chan.startswith("#"):
			raise exceptions.moderatedPMException

		# Get on/off
		enable = True
		if len(message) >= 1:
			if message[0] == "off":
				enable = False

		# Turn on/off moderated mode
		glob.channels.channels[chan].moderated = enable
		return "This channel is {} in moderated mode!".format("now" if enable else "no longer")
	except exceptions.moderatedPMException:
		return False

def kickAll(fro, chan, message):
	# Kick everyone but mods/admins
	toKick = []
	with glob.tokens:
		for key, value in glob.tokens.tokens.items():
			if not value.admin:
				toKick.append(key)

	# Loop though users to kick (we can't change dictionary size while iterating)
	for i in toKick:
		if i in glob.tokens.tokens:
			glob.tokens.tokens[i].kick()

	return "Everyone went to the darkness before I could... I'm jealous."

def kick(fro, chan, message):
	# Get parameters
	target = message[0].lower()
	if target == glob.BOT_NAME.lower():
		return "Nope."

	# Get target token and make sure is connected
	tokens = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True, _all=True)
	if len(tokens) == 0:
		return "{} is not online".format(target)

	# Kick users
	for i in tokens:
		i.kick()

	# Bot response
	return "{} is thrown to the Shadow Realm.".format(target)

def fokabotReconnect(fro, chan, message):
	# Check if the bot is already connected
	if glob.tokens.getTokenFromUserID(1) is not None:
		return "{} is already connected to Bancho".format(glob.BOT_NAME)

	# Bot is not connected, connect it
	fokabot.connect()
	return False

def silence(fro, chan, message):
	message = [x.lower() for x in message]
	target = message[0]
	amount = message[1]
	unit = message[2]
	reason = ' '.join(message[3:]).strip()
	if not reason:
		return "Please provide a valid reason."
	if not amount.isdigit():
		return "The amount must be a number."

	# Get target user ID
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)

	# Make sure the user exists
	if not targetUserID:
		return "{}: user not found".format(target)

	# Calculate silence seconds
	if unit == 's':
		silenceTime = int(amount)
	elif unit == 'm':
		silenceTime = int(amount) * 60
	elif unit == 'h':
		silenceTime = int(amount) * 3600
	elif unit == 'd':
		silenceTime = int(amount) * 86400
	else:
		return "Invalid time unit (s/m/h/d)."

	# Max silence time is 7 days
	if silenceTime > 604800: # DUMB. EVEN BANCHO CAN SHOT YOU MORE THAN THIS.
		return "Invalid silence time. Max silence time is 7 days."

	# Send silence packet to target if he's connected
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		# user online, silence both in db and with packet
		targetToken.silence(silenceTime, reason, userID)
	else:
		# User offline, silence user only in db
		userUtils.silence(targetUserID, silenceTime, reason, userID)

	# Log message
	msg = "{} has been silenced for the following reason: {}".format(target, reason)

        # send to discord
	webhook = DiscordWebhook(url=glob.conf.config["discord"]["reports"])
	embed = DiscordEmbed(title="New Silence!", description="**Username** : {}\n**Reason** : {}".format(target, reason), color=16711680)
	webhook.add_embed(embed)
	log.info("[REPORT] REPORT masuk ke discord bro")
	webhook.execute()

	return msg

def removeSilence(fro, chan, message):
	# Get parameters
	for i in message:
		i = i.lower()
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)

	# Send new silence end packet to user if he's online
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		# User online, remove silence both in db and with packet
		targetToken.silence(0, "", userID)
	else:
		# user offline, remove islene ofnlt from db
		userUtils.silence(targetUserID, 0, "", userID)

	return "{}'s silence reset".format(target)

def ban(fro, chan, message):
	# Get parameters
	for i in message:
		i = i.lower()
	target = message[0]
	alasan = " ".join(message[1:]).strip()
	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not alasan:
		return "provide good best reason."
	if not targetUserID:
		return "{}: user not found".format(target)
	if targetUserID in (1, 2):
		return "NO!"
	if isInPrivilegeGroup(targetUserID, 'Chat Moderators'):
		return "u wot."
	# Set allowed to 0
	userUtils.ban(targetUserID)

	# Send ban packet to the user if he's online
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		targetToken.enqueue(serverPackets.loginBanned())

	log.rap(userID, "{} has been banned, reason {}".format(target, alasan), True)
        # send to discord
	webhook = DiscordWebhook(url=glob.conf.config["discord"]["autobanned"])
	embed = DiscordEmbed(title="NEW BANNED!", description="**Username** : {}\n**Reason** : {}".format(target, alasan), color=16711680)
	webhook.add_embed(embed)
	webhook.execute()

	return "RIP {}. You will not be missed.".format(target)

def unban(fro, chan, message):
	# Get parameters
	for i in message:
		i = i.lower()
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)

	# Set allowed to 1
	userUtils.unban(targetUserID)

	log.rap(userID, "has unbanned {}".format(target), True)
	return "Welcome back {}!".format(target)

def restrict(fro, chan, message):
	# Get parameters
	target = message[0]
	alasan = " ".join(message[1:]).strip()

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target.lower())
	userID = userUtils.getID(fro)
	if not alasan:
		return "Provide best good reason"
	if not targetUserID:
		return "{}: user not found".format(target)
	if targetUserID in (1, 2, 3):
		return "NO!"
	if isInPrivilegeGroup(targetUserID, 'Chat Moderators'):
		return "u wot."

	# Put this user in restricted mode
	userUtils.restrict(targetUserID)

	# Send restricted mode packet to this user if he's online
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		targetToken.setRestricted()

	log.rap(userID, "has put {} in restricted mode because {}".format(target, alasan), True)
    # send to discord
	webhook = DiscordWebhook(url=glob.conf.config["discord"]["autobanned"])
	embed = DiscordEmbed(title="NEW RESTRICT!", description="**Username** : {}\n**Reason** : {}".format(target, alasan), color=16711680)
	webhook.add_embed(embed)
	webhook.execute()

	return "Bye bye {}. See you later, maybe.".format(target)

def unrestrict(fro, chan, message):
	# Get parameters
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target.lower())
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)

	# Set allowed to 1
	userUtils.unrestrict(targetUserID)

	log.rap(userID, "has removed restricted mode from {}".format(target), True)
	return "Welcome back {}!".format(target)

def restartShutdown(restart):
	"""Restart (if restart = True) or shutdown (if restart = False) pep.py safely"""
	msg = "The Bancho Server will going to restart!".format("restart" if restart else "shutdown")
	systemHelper.scheduleShutdown(5, restart, msg)
	return msg

def systemRestart(fro, chan, message):
	return restartShutdown(True)

def systemShutdown(fro, chan, message):
	return restartShutdown(False)

def systemReload(fro, chan, message):
	glob.banchoConf.reload()
	return "Bancho settings reloaded!"

def systemMaintenance(fro, chan, message):
	# Turn on/off bancho maintenance
	maintenance = True

	# Get on/off
	if len(message) >= 2:
		if message[1] == "off":
			maintenance = False

	# Set new maintenance value in bancho_settings table
	glob.banchoConf.setMaintenance(maintenance)

	if maintenance:
		# We have turned on maintenance mode
		# Users that will be disconnected
		who = []

		# Disconnect everyone but mod/admins
		with glob.tokens:
			for _, value in glob.tokens.tokens.items():
				if not value.admin:
					who.append(value.userID)

		glob.streams.broadcast("main", serverPackets.notification("Our bancho server is in maintenance mode. Please try to login again later."))
		glob.tokens.multipleEnqueue(serverPackets.loginError(), who)
		msg = "The server is now in maintenance mode!"
	else:
		# We have turned off maintenance mode
		# Send message if we have turned off maintenance mode
		msg = "The server is no longer in maintenance mode!"

	# Chat output
	return msg

def systemStatus(fro, chan, message):
	# Print some server info
	data = systemHelper.getSystemInfo()

	# Final message
	letsVersion = glob.redis.get("lets:version")
	if letsVersion is None:
		letsVersion = "\_(-w-)_/"
	else:
		letsVersion = letsVersion.decode("utf-8")
	msg = "pep.py bancho server v{}\n".format(glob.VERSION)
	msg += "LETS scores server v{}\n".format(letsVersion)
	msg += "---- DATENSHI SERVER ----\n"
	msg += "\n"
	msg += "=== BANCHO STATS ===\n"
	msg += "Connected users: {}\n".format(data["connectedUsers"])
	msg += "Multiplayer matches: {}\n".format(data["matches"])
	msg += "Uptime: {}\n".format(data["uptime"])
	msg += "\n"
	msg += "=== SYSTEM STATS ===\n"
	msg += "CPU: {}%\n".format(data["cpuUsage"])
	msg += "RAM: {}GB/{}GB\n".format(data["usedMemory"], data["totalMemory"])
	if data["unix"]:
		msg += "Load average: {}/{}/{}\n".format(data["loadAverage"][0], data["loadAverage"][1], data["loadAverage"][2])

	return msg


def getPPMessage(userID, just_data = False):
	try:
		# Get user token
		token = glob.tokens.getTokenFromUserID(userID)
		if token is None:
			return False

		currentMap = token.tillerino[0]
		currentMods = token.tillerino[1]
		currentAcc = token.tillerino[2]

		# Send request to LETS api
		url = "{}/v1/pp?b={}&m={}".format(glob.conf.config["server"]["letsapiurl"].rstrip("/"), currentMap, currentMods)
		resp = requests.get(url, timeout=10)
		try:
			assert resp is not None
			data = json.loads(resp.text)
		except (json.JSONDecodeError, AssertionError):
			raise exceptions.apiException()

		# Make sure status is in response data
		if "status" not in data:
			raise exceptions.apiException()

		# Make sure status is 200
		if data["status"] != 200:
			if "message" in data:
				return "Error in LETS API call ({}).".format(data["message"])
			else:
				raise exceptions.apiException()

		if just_data:
			return data

		# Return response in chat
		# Song name and mods
		msg = "{song}{plus}{mods}  ".format(song=data["song_name"], plus="+" if currentMods > 0 else "", mods=generalUtils.readableMods(currentMods))

		# PP values
		if currentAcc == -1:
			msg += "95%: {pp95}pp | 98%: {pp98}pp | 99% {pp99}pp | 100%: {pp100}pp".format(pp100=round(data["pp"][0], 2), pp99=round(data["pp"][1], 2), pp98=round(data["pp"][2], 2), pp95=round(data["pp"][3], 2))
		else:
			msg += "{acc:.2f}%: {pp}pp".format(acc=token.tillerino[2], pp=round(data["pp"][0], 2))
		
		originalAR = data["ar"]
		# calc new AR if HR/EZ is on
		if (currentMods & mods.EASY) > 0:
			data["ar"] = max(0, data["ar"] / 2)
		if (currentMods & mods.HARDROCK) > 0:
			data["ar"] = min(10, data["ar"] * 1.4)
		
		arstr = " ({})".format(originalAR) if originalAR != data["ar"] else ""
		
		# Beatmap info
		msg += " | {bpm} BPM | AR {ar}{arstr} | {stars:.2f} stars".format(bpm=data["bpm"], stars=data["stars"], ar=data["ar"], arstr=arstr)

		# Return final message
		return msg
	except requests.exceptions.RequestException:
		# RequestException
		return "API Timeout. Please try again in a few seconds."
	except exceptions.apiException:
		# API error
		return "Unknown error in LETS API call."
	#except:
		# Unknown exception
		# TODO: print exception
	#	return False

def tillerinoMods(fro, chan, message):
	try:
		# Run the command in PM only
		if chan.startswith("#"):
			return False

		# Get token and user ID
		token = glob.tokens.getTokenFromUsername(fro)
		if token is None:
			return False
		userID = token.userID

		# Make sure the user has triggered the bot with /np command
		if token.tillerino[0] == 0:
			return "Please give me a beatmap first with /np command."

		# Check passed mods and convert to enum
		modsList = [message[0][i:i+2].upper() for i in range(0, len(message[0]), 2)]
		modsEnum = 0
		for i in modsList:
			if i not in ["NO", "NF", "EZ", "HD", "HR", "DT", "HT", "NC", "FL", "SO", "RX"]:
				return "Invalid mods. Allowed mods: NO, NF, EZ, HD, HR, DT, HT, NC, FL, SO, RX. Do not use spaces for multiple mods."
			if i == "NO":
				modsEnum = 0
				break
			elif i == "NF":
				modsEnum += mods.NOFAIL
			elif i == "EZ":
				modsEnum += mods.EASY
			elif i == "HD":
				modsEnum += mods.HIDDEN
			elif i == "HR":
				modsEnum += mods.HARDROCK
			elif i == "DT":
				modsEnum += mods.DOUBLETIME
			elif i == "HT":
				modsEnum += mods.HALFTIME
			elif i == "NC":
				modsEnum += mods.NIGHTCORE
			elif i == "FL":
				modsEnum += mods.FLASHLIGHT
			elif i == "SO":
				modsEnum += mods.SPUNOUT
			elif i == "RX":
				modsEnum += mods.RELAX

		# Set mods
		token.tillerino[1] = modsEnum

		# Return tillerino message for that beatmap with mods
		return getPPMessage(userID)
	except:
		return False

def tillerinoAcc(fro, chan, message):
	try:
		# Run the command in PM only
		if chan.startswith("#"):
			return False

		# Get token and user ID
		token = glob.tokens.getTokenFromUsername(fro)
		if token is None:
			return False
		userID = token.userID

		# Make sure the user has triggered the bot with /np command
		if token.tillerino[0] == 0:
			return "Please give me a beatmap first with /np command."

		# Convert acc to float
		acc = float(message[0])

		# Set new tillerino list acc value
		token.tillerino[2] = acc

		# Return tillerino message for that beatmap with mods
		return getPPMessage(userID)
	except ValueError:
		return "Invalid acc value"
	except:
		return False

def tillerinoLast(fro, chan, message):
	try:
		# Run the command in PM only
		if chan.startswith("#"):
			return False

		data = glob.db.fetch("""SELECT beatmaps.song_name as sn, scores.*,
			beatmaps.beatmap_id as bid, beatmaps.difficulty_std, beatmaps.difficulty_taiko, beatmaps.difficulty_ctb, beatmaps.difficulty_mania, beatmaps.max_combo as fc
		FROM scores
		LEFT JOIN beatmaps ON beatmaps.beatmap_md5=scores.beatmap_md5
		LEFT JOIN users ON users.id = scores.userid
		WHERE users.username = %s
		ORDER BY scores.time DESC
		LIMIT 1""", [fro])
		if data is None:
			return False

		diffString = "difficulty_{}".format(gameModes.getGameModeForDB(data["play_mode"]))
		rank = generalUtils.getRank(data["play_mode"], data["mods"], data["accuracy"],
									data["300_count"], data["100_count"], data["50_count"], data["misses_count"])

		ifPlayer = "{0} | ".format(fro) if chan != glob.BOT_NAME else ""
		ifFc = " (FC)" if data["max_combo"] == data["fc"] else " {0}x/{1}x".format(data["max_combo"], data["fc"])
		beatmapLink = "[http://osu.ppy.sh/b/{1} {0}]".format(data["sn"], data["bid"])

		hasPP = data["play_mode"] != gameModes.CTB

		msg = ifPlayer
		msg += beatmapLink
		if data["play_mode"] != gameModes.STD:
			msg += " <{0}>".format(gameModes.getGameModeForPrinting(data["play_mode"]))

		if data["mods"]:
			msg += ' +' + generalUtils.readableMods(data["mods"])

		if not hasPP:
			msg += " | {0:,}".format(data["score"])
			msg += ifFc
			msg += " | {0:.2f}%, {1}".format(data["accuracy"], rank.upper())
			msg += " {{ {0} / {1} / {2} / {3} }}".format(data["300_count"], data["100_count"], data["50_count"], data["misses_count"])
			msg += " | {0:.2f} stars".format(data[diffString])
			return msg

		msg += " ({0:.2f}%, {1})".format(data["accuracy"], rank.upper())
		msg += ifFc
		msg += " | {0:.2f}pp".format(data["pp"])

		stars = data[diffString]
		if data["mods"]:
			token = glob.tokens.getTokenFromUsername(fro)
			if token is None:
				return False
			userID = token.userID
			token.tillerino[0] = data["bid"]
			token.tillerino[1] = data["mods"]
			token.tillerino[2] = data["accuracy"]
			oppaiData = getPPMessage(userID, just_data=True)
			if "stars" in oppaiData:
				stars = oppaiData["stars"]

		msg += " | {0:.2f} stars".format(stars)
		return msg
	except Exception as a:
		log.error(a)
		return False

def getBeatmapRequest(fro, chan, message): # Grab a random beatmap request. TODO: Add gamemode handling to this and !request
	request = glob.db.fetch("SELECT * FROM rank_requests LIMIT 1;")
	if request is not None:
		username = userUtils.getUsername(request['userid'])
		mapData = glob.db.fetch("SELECT song_name, ranked FROM beatmaps WHERE beatmap_id = {} ORDER BY difficulty_std DESC LIMIT 1;".format(request['bid']))
		glob.db.execute("DELETE FROM rank_requests WHERE id = {};".format(request['id']))
		return "[https://osu.troke.id/u/{userID} {username}] nominated beatmap: [https://osu.ppy.sh/b/{beatmapID} {songName}] for status change. {AinuBeatmapLink}The request has been deleted, so please decide it's status.".format(userID=request['userid'], username=username, beatmapID=request['bid'], songName=mapData['song_name'], AinuBeatmapLink='[https://osu.troke.id/b/{} Datenshi beatmap Link]. '.format(request['bid']))
	else:
		return "All nominations have been checked. Thank you for your hard work! :)"
	
	return "The beatmap ranking system has been reworked."

def pp(fro, chan, message):
	if chan.startswith("#"):
		return False

	gameMode = None
	if len(message) >= 1:
		gm = {
			"standard": 0,
			"std": 0,
			"taiko": 1,
			"ctb": 2,
			"mania": 3
		}
		if message[0].lower() not in gm:
			return "What's that game mode? I've never heard of it :/"
		else:
			gameMode = gm[message[0].lower()]

	token = glob.tokens.getTokenFromUsername(fro)
	if token is None:
		return False
	if gameMode is None:
		gameMode = token.gameMode
	if gameMode == gameModes.TAIKO or gameMode == gameModes.CTB:
		return "PP for your current game mode is not supported yet."
	pp = userUtils.getPP(token.userID, gameMode)
	return "You have {:,} pp".format(pp)

def updateBeatmap(fro, chan, message):
	try:
		# Run the command in PM only
		if chan.startswith("#"):
			return False

		# Get token and user ID
		token = glob.tokens.getTokenFromUsername(fro)
		if token is None:
			return False

		# Make sure the user has triggered the bot with /np command
		if token.tillerino[0] == 0:
			return "Please give me a beatmap first with /np command."

		# Send the request to cheesegull
		ok, message = cheesegull.updateBeatmap(token.tillerino[0])
		if ok:
			return "An update request for that beatmap has been queued. Check back in a few minutes and the beatmap should be updated!"
		else:
			return "Error in beatmap mirror API request: {}".format(message)
	except:
		return False

def report(fro, chan, message):
	msg = ""
	try:
		# TODO: Rate limit
		# Regex on message
		reportRegex = re.compile("^(.+) \((.+)\)\:(?: )?(.+)?$")
		result = reportRegex.search(" ".join(message))

		# Make sure the message matches the regex
		if result is None:
			raise exceptions.invalidArgumentsException()

		# Get username, report reason and report info
		target, reason, additionalInfo = result.groups()
		target = chat.fixUsernameForBancho(target)

		# Make sure the target is not foka
		if target.lower() == glob.BOT_NAME.lower():
			raise exceptions.invalidUserException()

		# Make sure the user exists
		targetID = userUtils.getID(target)
		if targetID == 0:
			raise exceptions.userNotFoundException()

		# Make sure that the user has specified additional info if report reason is 'Other'
		if reason.lower() == "other" and additionalInfo is None:
			raise exceptions.missingReportInfoException()

		# Get the token if possible
		chatlog = ""
		token = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
		if token is not None:
			chatlog = token.getMessagesBufferString()

		# Everything is fine, submit report
		glob.db.execute("INSERT INTO reports (id, from_uid, to_uid, reason, chatlog, time) VALUES (NULL, %s, %s, %s, %s, %s)", [userUtils.getID(fro), targetID, "{reason} - ingame {info}".format(reason=reason, info="({})".format(additionalInfo) if additionalInfo is not None else ""), chatlog, int(time.time())])
		msg = "You've reported {target} for {reason}{info}. A Community Manager will check your report as soon as possible. Every !report message you may see in chat wasn't sent to anyone, so nobody in chat, but admins, know about your report. Thank you for reporting!".format(target=target, reason=reason, info="" if additionalInfo is None else " (" + additionalInfo + ")")
		adminMsg = "{user} has reported {target} for {reason} ({info})".format(user=fro, target=target, reason=reason, info=additionalInfo)

		# send to discord
		webhook = DiscordWebhook(url=glob.conf.config["discord"]["reports"])
		embed = DiscordEmbed(title="NEW REPORTS!!", description="{}".format(adminMsg))
		webhook.add_embed(embed)
		log.info("[REPORT] REPORT masuk ke discord bro")
		webhook.execute()

		# Log report in #admin and on discord
		chat.sendMessage(glob.BOT_NAME, "#admin", adminMsg)
		log.warning(adminMsg, discord="cm")
	except exceptions.invalidUserException:
		msg = "Hello, {} here! You can't report me. I won't forget what you've tried to do. Watch out.".format(glob.BOT_NAME)
	except exceptions.invalidArgumentsException:
		msg = "Invalid report command syntax. To report an user, click on it and select 'Report user'."
	except exceptions.userNotFoundException:
		msg = "The user you've tried to report doesn't exist."
	except exceptions.missingReportInfoException:
		msg = "Please specify the reason of your report."
	except:
		raise
	finally:
		if msg != "":
			token = glob.tokens.getTokenFromUsername(fro)
			if token is not None:
				if token.irc:
					chat.sendMessage(glob.BOT_NAME, fro, msg)
				else:
					token.enqueue(serverPackets.notification(msg))
	return False

def getMatchIDFromChannel(chan):
	if not chan.lower().startswith(f"{chatChannels.MULTIPLAYER_PREFIX}_"):
		raise exceptions.wrongChannelException()
	parts = chan.lower().split("_")
	if len(parts) < 2 or not parts[1].isdigit():
		raise exceptions.wrongChannelException()
	matchID = int(parts[1])
	if matchID not in glob.matches.matches:
		raise exceptions.matchNotFoundException()
	return matchID

def getSpectatorHostUserIDFromChannel(chan):
	if not chan.lower().startswith(f"{chatChannels.SPECTATOR_PREFIX}_"):
		raise exceptions.wrongChannelException()
	parts = chan.lower().split("_")
	if len(parts) < 2 or not parts[1].isdigit():
		raise exceptions.wrongChannelException()
	userID = int(parts[1])
	return userID

def multiplayer(fro, chan, message):
	return MP.handler(fro, chan, message)

def switchServer(fro, chan, message):
	# Get target user ID
	target = message[0]
	newServer = message[1].strip()
	if not newServer:
		return "Invalid server IP"
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)

	# Make sure the user exists
	if not targetUserID:
		return "{}: user not found".format(target)

	# Connect the user to the end server
	userToken = glob.tokens.getTokenFromUserID(userID, ignoreIRC=True, _all=False)
	userToken.enqueue(serverPackets.switchServer(newServer))

	# Disconnect the user from the origin server
	# userToken.kick()
	return "{} has been connected to {}".format(target, newServer)

def rtx(fro, chan, message):
	target = message[0]
	message = " ".join(message[1:]).strip()
	if not message:
		return "Invalid message"
	targetUserID = userUtils.getIDSafe(target)
	if not targetUserID:
		return "{}: user not found".format(target)
	userToken = glob.tokens.getTokenFromUserID(targetUserID, ignoreIRC=True, _all=False)
	userToken.enqueue(serverPackets.rtx(message))
	return "whatever you wish"
	
def editMap(fro, chan, message): # Using Atoka's editMap with Aoba's edit
	# Put the gathered values into variables to be used later
	messages = [m.lower() for m in message]  #!map rank set [something]
	rankType = message[0]
	mapType = message[1]
	mapID = message[2]

	# Get persons userID, privileges, and token
	userID = userUtils.getID(fro)
	userPriv = userUtils.getPrivileges(userID)
	token = glob.tokens.getTokenFromUserID(userID)
	name = userUtils.getUsername(userID)

	# Only allow users to request maps in #admin channel or PMs with AC. Heavily reduced spam smh
	if (userPriv & privileges.ADMIN_MANAGE_BEATMAPS) != privileges.ADMIN_MANAGE_BEATMAPS:
		# silent ignore.
		return None
	if chan not in (chatChannels.SPECIAL_CHANNEL, glob.BOT_NAME):
		return "Map ranking is not permitted in regular channels, please do so in PMs with AC (or #admin if administrator)."
	
	isSet = False
	if 's' in mapType.lower():
		mapType = 'set'
		isSet = True
	elif 'd' in mapType.lower() or 'm' in mapType.lower():
		mapType = 'map'
	else:
		return "Please specify whether your request is a single difficulty, or a full set (map/set). Example: '!map unrank/rank/love set/map 256123 mania'."
	

	# Grab beatmapData from db
	beatmapData = glob.db.fetch("SELECT beatmapset_id, song_name, ranked FROM beatmaps WHERE {} = {} LIMIT 1".format('beatmapset_id' if isSet else 'beatmap_id', mapID))
	if beatmapData is None:
		if isSet:
			return "I can't find the beatmap set of it."
		else:
			return "I can't find the beatmap of it, you are not mistaking with set ID right?"

	# Figure out which ranked status we're requesting to
	rankTypeBase = rankType.lower()[0]
	if rankTypeBase in ('r'):
		rankType = 'rank'
		status = 'ranked'
		rankTypeID = 2
	elif rankTypeBase in ('l'):
		rankType = 'love'
		status = 'loved'
		rankTypeID = 5
	elif rankTypeBase in ('u', 'g'):
		rankType = 'unrank'
		status = 'unranked'
		rankTypeID = 0
	else:
		return "Please enter a valid ranked status (rank, love, unrank)."
	
	if beatmapData['ranked'] == rankTypeID:
		return "This map is already {}!".format(status)

	if isSet:
		rankUtils.editSet(mapID, status, userID)
	else:
		rankUtils.editMap(mapID, status, userID)

	# Announce / Log to admin panel logs when ranked status is changed
	log.rap(userID, "has {} beatmap ({}): {} ({})".format(status, mapType, beatmapData["song_name"], mapID), True)
	
	def banchoCallback(msg):
		for chan in (chatChannels.ANNOUNCE_CHANNEL, chatChannels.ANNOUNCE_RANK_CHANNEL):
			chat.sendMessage(glob.BOT_NAME, chan, re.sub(r"\!$",f" by [https://osu.troke.id/u/{userID} {name}]!",msg))
	def discordCallback(msg, idTuple):
		webhook = DiscordWebhook(url=glob.conf.config["discord"]["ranked-map"])
		embed = DiscordEmbed(description='{}\nDownload : https://osu.ppy.sh/s/{}'.format(msg, beatmapData["beatmapset_id"]), color=242424)
		embed.set_thumbnail(url='https://b.ppy.sh/thumb/{}.jpg'.format(str(beatmapData["beatmapset_id"])))
		embed.set_author(name='{}'.format(name), url='https://osu.troke.id/u/{}'.format(str(userID)), icon_url='https://a.troke.id/{}'.format(str(userID)))
		embed.set_footer(text='This map was {} from in-game'.format(status))
		webhook.add_embed(embed)
		log.info("[rankedmap] Rank status masuk ke discord bro")
		webhook.execute()
	rankUtils.announceMap(('s' if isSet else 'b', mapID), status, banchoCallback, discordCallback)
	return 'done!'

def postAnnouncement(fro, chan, message): # Post to #announce ingame
	announcement = ' '.join(message[0:])
	chat.sendMessage(glob.BOT_NAME, chatChannels.ANNOUNCE_CHANNEL, announcement)
	userID = userUtils.getID(fro)
	name = userUtils.getUsername(userID)

	# send to discord
	webhook = DiscordWebhook(url=glob.conf.config["discord"]["announcement"], content='@everyone')
	embed = DiscordEmbed(description='{}'.format(announcement), color=242424)
	embed.set_author(name='Staff : {}'.format(name), url='https://osu.troke.id/u/{}'.format(str(userID)), icon_url='https://a.troke.id/{}'.format(str(userID)))
	embed.set_footer(text='This announcement was posted from in-game')
	webhook.add_embed(embed)
	log.info("[ANNOUNCE] Announce masuk ke discord bro")
	webhook.execute()

	return "Announcement successfully sent."

def usePPBoard(fro, chan, message):
	messages = [m.lower() for m in message]
	relax = message[0]

	userID = userUtils.getID(fro)

	if 'x' in relax:
		rx = True
	else:
		rx = False

	# Set PPBoard value in user_stats table
	userUtils.setPPBoard(userID, rx)
	return "You're using PPBoard in {rx}.".format(rx='relax' if rx else 'vanilla')

def useScoreBoard(fro, chan, message):
	messages = [m.lower() for m in message]
	relax = message[0]

	userID = userUtils.getID(fro)
	
	if 'x' in relax:
		rx = True
	else:
		rx = False

	# Set PPBoard value in user_stats table
	userUtils.setScoreBoard(userID, rx)
	return "You're using Scoreboard in {rx}.".format(rx='relax' if rx else 'vanilla')

def boardVisibilityToggle(sender, channel, message):
	mode = 'normal others you none'.split()
	value = 0
	if message[0].lower() in mode:
		value = mode.index(message[0].lower())
	userID = userUtils.getID(sender)
	userUtils.setInvisibleBoard(userID, None, value)
	bits = ['you', 'others']
	if value == 0:
		return "Your score will be shown normally."
	else:
		bits_name = [(i, bits[i]) for i in range(len(bits))]
		return "Your score will be hidden from " + '/'.join(bit_data[1] for bit_data in bits_name if value & (1 << bit_data[0]))

def boardTypeToggle(sender, channel, message):
	if 'setBoardType' not in dir(userUtils):
		return "zZzZzZzZ"
	mode = personalBestScore.VALID_SCORE_TYPES
	relax = len(message) >= 2 and 'relax' == message[1].lower()
	value = 0
	if message[0].lower() in mode:
		value = mode.index(message[0].lower())
	userID = userUtils.getID(sender)
	userUtils.setBoard(userID, relax, value)
	return f"You're using {mode[value]}board in {'Relax' if relax else 'Normal'} plays."

def subscriptionSystem(sender, channel, message):
	key = 'pp'.split()
	if len(message) < 1:
		return False
	ms = message[0].lower()
	if ms not in key:
		return "Available options: " + ', '.join(key)
	keyData = {
		'pp': (userUtils.PPScoreInformation, userUtils.setPPScoreInformation)
	}
	mode = 'get set unset toggle'.split()
	userID = userUtils.getID(sender)
	subscribeValue = keyData[ms][0](userID, False)
	if len(message) < 2:
		mode_i = 0
	else:
		mode_i = -1
		if message[2].lower() in key:
			mode_i = key.index(message[2].lower())
	if mode_i == -1:
		return "!subscribe {} <{}>".format(message[0], '/'.join(mode))
	elif mode_i == 0:
		if subscribeValue:
			return "You are currently subscribing to {}.".format(ms)
		else:
			return "You are currently not subscribed to {}.".format(ms)
	elif mode_1 == 1:
		if subscribeValue:
			return "You are already subscribing to {}.".format(ms)
		else:
			keyData[ms][1](userID, False, True)
			return "You are subscribing to {}.".format(ms)
	elif mode_1 == 2:
		if subscribeValue:
			keyData[ms][1](userID, False, False)
			return "You are not subscribing to {} anymore.".format(ms)
		else:
			return "You are already not subscribing to {}.".format(ms)
	elif mode_1 == 3:
		if subscribeValue:
			keyData[ms][1](userID, False, False)
			return "You are not subscribing to {} anymore.".format(ms)
		else:
			keyData[ms][1](userID, False, True)
			return "You are subscribing to {}.".format(ms)
	else:
		pass

def whitelistUserPPLimit(fro, chan, message):
	messages = [m.lower() for m in message]
	target = message[0]
	relax = message[1]
	type = message[2] if len(message) > 2 else ''

	userID = userUtils.getID(target)

	if userID == 0:
		return "That user does not exist."

	if 'x' in relax:
		rx = True
	else:
		rx = False
	
	rt = 'single total'.split()
	if type.isdigit():
		wp = int(type) # use -1
	else:
		if type.lower() == 'all':
			wp = -1
		elif 'single' in type.lower():
			wp = 1
		elif 'total' in type.lower():
			wp = 2
		else:
			wp = 1

	userUtils.whitelistUserPPLimit(userID, rx, wp)
	rts = '+'.join(rt[i] for i in range(len(rt)) if wp & (1 << i))
	return "{user} has been whitelisted from {rts} PP Limit on {rx}.".format(user=target, rx='relax' if rx else 'vanilla', rts=rts)

def bloodcat(fro, chan, message):
	try:
		matchID = getMatchIDFromChannel(chan)
	except exceptions.wrongChannelException:
		matchID = None
	try:
		spectatorHostUserID = getSpectatorHostUserIDFromChannel(chan)
	except exceptions.wrongChannelException:
		spectatorHostUserID = None

	if matchID is not None:
		if matchID not in glob.matches.matches:
			return "This match doesn't seem to exist... Or does it...?"
		beatmapID = glob.matches.matches[matchID].beatmapID
	else:
		spectatorHostToken = glob.tokens.getTokenFromUserID(spectatorHostUserID, ignoreIRC=True)
		if spectatorHostToken is None:
			return "The spectator host is offline."
		beatmapID = spectatorHostToken.beatmapID
	return bloodcatMessage(beatmapID)

def beatconnect(fro, chan, message):
	try:
		matchID = getMatchIDFromChannel(chan)
	except exceptions.wrongChannelException:
		matchID = None
	try:
		spectatorHostUserID = getSpectatorHostUserIDFromChannel(chan)
	except exceptions.wrongChannelException:
		spectatorHostUserID = None

	if matchID is not None:
		if matchID not in glob.matches.matches:
			return "This match doesn't seem to exist... Or does it...?"
		beatmapID = glob.matches.matches[matchID].beatmapID
	else:
		spectatorHostToken = glob.tokens.getTokenFromUserID(spectatorHostUserID, ignoreIRC=True)
		if spectatorHostToken is None:
			return "The spectator host is offline."
		beatmapID = spectatorHostToken.beatmapID
	return beatconnectMessage(beatmapID)

def mirror(fro, chan, message):
	try:
		matchID = getMatchIDFromChannel(chan)
	except exceptions.wrongChannelException:
		matchID = None
	try:
		spectatorHostUserID = getSpectatorHostUserIDFromChannel(chan)
	except exceptions.wrongChannelException:
		spectatorHostUserID = None

	if matchID is not None:
		if matchID not in glob.matches.matches:
			return "This match doesn't seem to exist... Or does it...?"
		beatmapID = glob.matches.matches[matchID].beatmapID
	else:
		spectatorHostToken = glob.tokens.getTokenFromUserID(spectatorHostUserID, ignoreIRC=True)
		if spectatorHostToken is None:
			return "The spectator host is offline."
		beatmapID = spectatorHostToken.beatmapID
	return mirrorMessage(beatmapID)
	
"""
Commands list

trigger: message that triggers the command
callback: function to call when the command is triggered. Optional.
response: text to return when the command is triggered. Optional.
syntax: command syntax. Arguments must be separated by spaces (eg: <arg1> <arg2>)
privileges: privileges needed to execute the command. Optional.
"""
commands = [
	{
		"trigger": "roll",
		"callback": roll
	}, {
		"trigger": "faq",
		"syntax": "<name>",
		"callback": faq
	}, {
		"trigger": "report",
		"callback": report
	}, {
		"trigger": "help",
		"response": "Click (here)[https://osu.troke.id/index.php?p=16&id=4] for full command list"
	}, {
		"trigger": "boardshow",
		"callback": boardVisibilityToggle,
	}, {
		"trigger": "boardtype",
		"callback": boardTypeToggle,
	}, {
		"trigger": "subscribe",
		"callback": subscriptionSystem,
	}, {
		"trigger": "ppboard",
		"syntax": "<relax/vanilla>",
		"callback": usePPBoard
	}, {
		"trigger": "scoreboard",
		"syntax": "<relax/vanilla>",
		"callback": useScoreBoard
	}, {
		"trigger": "whitelist",
		"privileges": privileges.ADMIN_BAN_USERS,
		"syntax": "<target> <relax/vanilla>",
		"callback": whitelistUserPPLimit
	}, {
		"trigger": "announce",
		"syntax": "<announcement>",
		"privileges": privileges.ADMIN_SEND_ALERTS,
		"callback": postAnnouncement
	},	#{
		#"trigger": "!ask",
		#"syntax": "<question>",
		#"callback": ask
	#}, {
	{
		"trigger": "maprq",
		"privileges": privileges.ADMIN_MANAGE_BEATMAPS,
		"callback": getBeatmapRequest
	}, {
		"trigger": "map",
		"syntax": "<rank/unrank> <set/map> <ID>",
		"privileges": privileges.ADMIN_MANAGE_BEATMAPS,
		"callback": editMap
	}, {
		"trigger": "alert",
		"syntax": "<message>",
		"privileges": privileges.ADMIN_SEND_ALERTS,
		"callback": alert
	}, {
		"trigger": "alertuser",
		"syntax": "<username> <message>",
		"privileges": privileges.ADMIN_SEND_ALERTS,
		"callback": alertUser,
	}, {
		"trigger": "moderated",
		"privileges": privileges.ADMIN_CHAT_MOD,
		"callback": moderated
	}, {
		"trigger": "kickall",
		"privileges": privileges.ADMIN_MANAGE_SERVERS,
		"callback": kickAll
	}, {
		"trigger": "kick",
		"syntax": "<target>",
		"privileges": privileges.ADMIN_KICK_USERS,
		"callback": kick
	}, {
		"trigger": "bot reconnect",
		"privileges": privileges.ADMIN_MANAGE_SERVERS,
		"callback": fokabotReconnect
	}, {
		"trigger": "silence",
		"syntax": "<target> <amount> <unit(s/m/h/d)> <reason>",
		"privileges": privileges.ADMIN_SILENCE_USERS,
		"callback": silence
	}, {
		"trigger": "removesilence",
		"syntax": "<target>",
		"privileges": privileges.ADMIN_SILENCE_USERS,
		"callback": removeSilence
	}, {
		"trigger": "system restart",
		"privileges": privileges.ADMIN_MANAGE_SERVERS,
		"callback": systemRestart
	}, {
		"trigger": "system shutdown",
		"privileges": privileges.ADMIN_MANAGE_SERVERS,
		"callback": systemShutdown
	}, {
		"trigger": "system reload",
		"privileges": privileges.ADMIN_MANAGE_SETTINGS,
		"callback": systemReload
	}, {
		"trigger": "system maintenance",
		"privileges": privileges.ADMIN_MANAGE_SERVERS,
		"callback": systemMaintenance
	}, {
		"trigger": "system status",
		"privileges": privileges.ADMIN_MANAGE_SERVERS,
		"callback": systemStatus
	}, {
		"trigger": "ban",
		"syntax": "<target>",
		"privileges": privileges.ADMIN_BAN_USERS,
		"callback": ban
	}, {
		"trigger": "unban",
		"syntax": "<target>",
		"privileges": privileges.ADMIN_BAN_USERS,
		"callback": unban
	}, {
		"trigger": "restrict",
		"syntax": "<target>",
		"privileges": privileges.ADMIN_BAN_USERS,
		"callback": restrict
	}, {
		"trigger": "unrestrict",
		"syntax": "<target>",
		"privileges": privileges.ADMIN_BAN_USERS,
		"callback": unrestrict
	}, {
		"trigger": "with",
		"callback": tillerinoMods,
		"syntax": "<mods>"
	}, {
		"trigger": "last",
		"callback": tillerinoLast
	}, {
		"trigger": "ir",
		"privileges": privileges.ADMIN_MANAGE_SERVERS,
		"callback": instantRestart
	}, {
		"trigger": "pp",
		"callback": pp
	}, {
		"trigger": "update",
		"callback": updateBeatmap
	}, {
		"trigger": "mp",
		# "privileges": privileges.USER_TOURNAMENT_STAFF,
		"syntax": "<subcommand>",
		"callback": multiplayer
	}, {
		"trigger": "switchserver",
		"privileges": privileges.ADMIN_MANAGE_SERVERS,
		"syntax": "<username> <server_address>",
		"callback": switchServer
	}, {
		"trigger": "rtx",
		"privileges": privileges.ADMIN_MANAGE_USERS,
		"syntax": "<username> <message>",
		"callback": rtx
	}, {
		"trigger": "bloodcat",
		"callback": bloodcat
	}, {
		"trigger": "beatconnect",
		"callback": beatconnect
	}
	#
	#	"trigger": "!acc",
	#	"callback": tillerinoAcc,
	#	"syntax": "<accuarcy>"
	#}
]

# Commands list default values
for cmd in commands:
	cmd.setdefault("syntax", "")
	cmd.setdefault("privileges", None)
	cmd.setdefault("callback", None)
	cmd.setdefault("response", "u w0t m8?")
