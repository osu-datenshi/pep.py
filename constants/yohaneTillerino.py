from common.constants import mods
from constants import yohaneCommands, yohaneReactions
from objects import fokabot

def np(fro, chan, message):
	try:
		# Mirror list trigger for #spect_
		if chan.startswith(f"{chatChannels.SPECTATOR_PREFIX}_"):
			spectatorHostUserID = yohaneCommands.getSpectatorHostUserIDFromChannel(chan)
			spectatorHostToken = glob.tokens.getTokenFromUserID(spectatorHostUserID, ignoreIRC=True)
			if spectatorHostToken is None:
				return False
			return yohaneCommands.mirrorMessage(spectatorHostToken.beatmapID)

		# Run the command in PM only
		if chan.startswith("#"):
			return False

		playWatch = message[1] == "playing" or message[1] == "watching"
		# Get URL from message
		if message[1] == "listening":
			beatmapURL = str(message[3][1:])
		elif playWatch:
			beatmapURL = str(message[2][1:])
		else:
			return False

		modsEnum = 0
		mapping = {
			"-Easy": mods.EASY,
			"-NoFail": mods.NOFAIL,
			"+Hidden": mods.HIDDEN,
			"+HardRock": mods.HARDROCK,
			"+Nightcore": mods.NIGHTCORE,
			"+DoubleTime": mods.DOUBLETIME,
			"-HalfTime": mods.HALFTIME,
			"+Flashlight": mods.FLASHLIGHT,
			"-SpunOut": mods.SPUNOUT
		}

		if playWatch:
			for part in message:
				part = part.replace("\x01", "")
				if part in mapping.keys():
					modsEnum += mapping[part]

		# Get beatmap id from URL
		beatmapID = fokabot.npRegex.search(beatmapURL).groups(0)[0]

		# Update latest tillerino song for current token
		token = glob.tokens.getTokenFromUsername(fro)
		if token is not None:
			token.tillerino = [int(beatmapID), modsEnum, -1.0]
		userID = token.userID

		# Return tillerino message
		return yohaneCommands.getPPMessage(userID)
	except:
		return False
