import logging

from constants import exceptions
from constants import chatChannels
from objects import glob

class channel:
	def __init__(self, name, description, publicRead, publicWrite, temp, hidden):
		"""
		Create a new chat channel object

		:param name: channel name
		:param description: channel description
		:param publicRead: if True, this channel can be read by everyone. If False, it can be read only by mods/admins
		:param publicWrite: same as public read, but regards writing permissions
		:param temp: if True, this channel will be deleted when there's no one in this channel
		:param hidden: if True, thic channel won't be shown in channels list
		"""
		self.name = name
		self.description = description
		self.publicRead = publicRead
		self.publicWrite = publicWrite
		self.moderated = False
		self.temp = temp
		self.hidden = hidden

		# Make Foka join the channel
		fokaToken = glob.tokens.getTokenFromUserID(1)
		if fokaToken is not None:
			try:
				fokaToken.joinChannel(self)
			except exceptions.userAlreadyInChannelException:
				logging.warning("Bot has already joined channel {}".format(self.name))

	@property
	def isSpecial(self):
		return any(self.name.startswith(x) for x in (f"{chatChannels.SPECTATOR_PREFIX}_", f"{chatChannels.MULTIPLAYER_PREFIX}_"))

	@property
	def clientName(self):
		if self.name.startswith(f"{chatChannels.SPECTATOR_PREFIX}_"):
			return chatChannels.SPECTATOR_MASK
		elif self.name.startswith(f"{chatChannels.MULTIPLAYER_PREFIX}_"):
			return chatChannels.MULTIPLAYER_MASK
		return self.name
