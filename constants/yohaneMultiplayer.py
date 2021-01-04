from collections import namedtuple
import random
import threading
import re

import requests
import time

from common import generalUtils
from common.constants import mods
from common.log import logUtils as log
from common.ripple import userUtils
from constants import exceptions, slotStatuses, matchModModes, matchTeams, matchTeamTypes, matchScoringTypes
from constants import chatChannels
from constants import yohaneCommands, yohaneReactions
from helpers import chatHelper as chat
from objects import glob

def _wrapper_():
    perm_level = 'basic player referee host creator'.split()
    def getMPPermission(match, userID):
        if userID == match.ownerUserID:
            return perm_level[4]
        elif userID == match.hostUserID:
            return perm_level[3]
        elif userID in match.referees:
            return perm_level[2]
        elif userID in [glob.tokens.tokens[slot.user].userID for slot in match.slots]:
            return perm_level[1]
        else:
            return perm_level[0]
    def getMPPermissionLevel(match,userID):
        return perm_level.index(getMPPermission(match,userID))
    
    def getCurrentMatchID(channel):
        return yohaneCommands.getMatchIDFromChannel(channel)
    def getCurrentMatch(channel):
        return glob.matches.matches[getCurrentMatchID(channel)]
    def lookupUserID(user):
        iter = []
        iter.append(userUtils.getID(user))
        iter.append(userUtils.getIDSafe(user))
        iter.append(userUtils.getIDSafe(user.lower()))
        iter.append(userUtils.getIDSafe(chat.fixUsernameForIRC(user).lower()))
        for result in iter:
            if result:
                return result
    def lookupUser(userStr):
        match = re.match(r'^#([1-9][0-9]*)$', userStr)
        if match:
            log.info(f"Special case {match.group(1)}")
            userID = int(match.group(1))
        else:
            userID = lookupUserID(userStr)
        if userID is None:
            raise exceptions.userNotFoundException('No such user.')
        if userID < 2:
            raise exceptions.invalidArgumentsException("\x01ACTION gaplok")
        return userID
    
    def checkPerms(sender, channel, message):
        userID  = userUtils.getID(sender)
        match   = getCurrentMatch(channel)
        return f"{sender} permission level is {getMPPermission(match,userID)}"
        
    def listReferee(sender, channel, message):
        _match = getCurrentMatch(channel)
        return str(_match.referees)

    def addReferee(sender, channel, message):
        if len(message) < 1:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp addref <user>")
        _match = getCurrentMatch(channel)
        username = message[0].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        userID = lookupUser(username)
        _match.addRefer(userID)
        return "Added {} to referees".format(username)

    def removeReferee(sender, channel, message):
        if len(message) < 1:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp rmref <user>")
        _match = getCurrentMatch(channel)
        username = message[0].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        userID = lookupUser(username)
        _match.removeRefer(userID)
        return "Removed {} from referee".format(username)

    def make(sender, channel, message):
        if len(message) < 1:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp make <name>")
        matchName = " ".join(message[0:]).strip()
        if not matchName:
            raise exceptions.invalidArgumentsException("Match name must not be empty!")
        userID = userUtils.getID(sender)
        matchID = glob.matches.createMatch(matchName, generalUtils.stringMd5(generalUtils.randomString(32)), 0, "Tournament", "", 0, -1, creatorUserID=userID, isTourney=True)
        glob.matches.matches[matchID].sendUpdates()
        return "Tourney match #{} created!".format(matchID)

    def join(sender, channel, message):
        # FIXME: what the fuck? mp join? isn't this bypass??
        if len(message) < 1 or not message[0].isdigit():
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp join <id>")
        matchID = int(message[1])
        userToken = glob.tokens.getTokenFromUsername(fro, ignoreIRC=True)
        if userToken is None:
            raise exceptions.invalidArgumentsException(
                "No game clients found for {}, can't join the match. "
                "If you're a referee and you want to join the chat "
                "channel from IRC, use /join #multi_{} instead.".format(fro, matchID)
            )
        userToken.joinMatch(matchID)
        return "Attempting to join match #{}!".format(matchID)

    def close(sender, channel, message):
        matchID = getCurrentMatchID(channel)
        glob.matches.disposeMatch(matchID)
        return "Multiplayer match #{} disposed successfully".format(matchID)

    def lock(sender, channel, message):
        matchID = getCurrentMatchID(channel)
        glob.matches.matches[matchID].isLocked = True
        return "This match has been locked"

    def unlock(sender, channel, message):
        matchID = getCurrentMatchID(channel)
        glob.matches.matches[matchID].isLocked = False
        return "This match has been unlocked"

    def size(sender, channel, message):
        if len(message) < 1 or not message[0].isdigit() or int(message[1]) < 2 or int(message[1]) > 16:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp size <slots(2-16)>")
        matchSize = int(message[0])
        _match = getCurrentMatch(channel)
        _match.forceSize(matchSize)
        return "Match size changed to {}".format(matchSize)

    def move(sender, channel, message):
        log.info(message[0] + ' to ' + message[1])
        if len(message) < 2 or not message[1].isdigit() or int(message[1]) not in range(1,17):
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp move <username> <slot>")
        username = message[0].strip()
        newSlotID = int(message[1])
        userID = lookupUser(username)
        _match = getCurrentMatch(channel)
        success = _match.userChangeSlot(userID, newSlotID - 1)
        if success:
            result = "Player {} moved to slot {}".format(username, newSlotID)
        else:
            result = "You can't use that slot: it's either already occupied by someone else or locked"
        return result

    def host(sender, channel, message):
        if len(message) < 1:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp host <username>")
        username = message[0].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        userID = lookupUser(username)
        _match = getCurrentMatch(channel)
        success = _match.setHost(userID)
        return "{} is now the host".format(username) if success else "Couldn't give host to {}".format(username)

    def clearHost(sender, channel, message):
        matchID = getCurrentMatchID(channel)
        glob.matches.matches[matchID].removeHost()
        return "Host has been removed from this match"
    
    class countdown:
        def __init__(self, count, level, onTick=None, onAction=None, onAbort=None):
            self.count  = count
            self.perm   = level
            self.state  = 0
            self.onTick   = onTick   if callable(onTick)   else None
            self.onAction = onAction if callable(onAction) else None
            self.onAbort  = onAbort  if callable(onAbort)  else None
        def tick(self):
            if self.state != 1:
                return
            if self.count > 0:
                callTick = False
                callTick = callTick or (self.count >  60 and not (self.count % 60))
                callTick = callTick or (self.count <= 60 and not (self.count % 10))
                callTick = callTick or (self.count <=  5 and not (self.count %  1))
                if callTick:
                    self.onTick(self.count)
                self.count -= 1
                threading.Timer(1.00, self.tick, []).start()
            elif self.count == 0:
                self.onAction()
                self.state = 2
            else:
                pass
        def start(self):
            self.state = 1
            self.tick()
        def abort(self):
            self.state = 3
            self.onAbort()
        @property
        def level(self):
            return self.perm
    
    timerList = {}
    
    def _mainTimer(matchID, newTimer=None):
        if newTimer is None:
            if matchID not in timerList:
                timerList[matchID] = None
        else:
            if timerList.get(matchID,None):
                timerList[matchID].abort()
            timerList[matchID] = newTimer
        return timerList[matchID]
        
    def timer(sender, channel, message):
        count   = 30
        if message[0].isdigit() and int(message[0],10) > 0:
            count = int(message[0],10)
        userID  = userUtils.getID(sender)
        matchID = getCurrentMatchID(channel)
        match   = getCurrentMatch(channel)
        level   = getMPPermissionLevel(match,userID)
        def onTick(tick):
            fmt = ""
            if tick >= 60:
                fmt = f"{tick // 60} minute{'s' if (tick // 60) > 1 else ''}"
            else:
                fmt = f"{tick} second{'s' if (tick) > 1 else ''}"
            chat.sendMessage(glob.BOT_NAME, channel, f"Countdown ends in {fmt}")
        def onAction():
            chat.sendMessage(glob.BOT_NAME, channel, "Countdown finished")
        def onAbort():
            chat.sendMessage(glob.BOT_NAME, channel, "Countdown aborted")
        timer  = countdown(count, level, onTick, onAction, onAbort)
        ptimer = _mainTimer(matchID)
        if ptimer is not None and timer.level < ptimer.level:
            return f"Ask the room {perm_level[ptimer.level]} to abort it!"
        _mainTimer(matchID, timer)
        timer.start()
        return f"Countdown starts for {count} second(s)."
    
    def start(sender, channel, message):
        count   = 0
        if len(message) > 0 and message[0].isdigit() and int(message[0],10) >= 0:
            count = int(message[0],10)
        userID  = userUtils.getID(sender)
        matchID = getCurrentMatchID(channel)
        match   = getCurrentMatch(channel)
        if match.inProgress:
            return "what the fuck are you doing, son?"
        level   = getMPPermissionLevel(match,userID)
        def forceReady():
            someoneNotReady = False
            for i, slot in enumerate(match.slots):
                if slot.status != slotStatuses.READY and slot.user is not None:
                    someoneNotReady = True
                    match.toggleSlotReady(i)
        def triggerStart():
            success = match.start()
            if not success:
                chat.sendMessage(glob.BOT_NAME, channel, "Couldn't start match. Make sure there are enough players and "
                                                  "teams are valid. The match has been unlocked.")
            else:
                chat.sendMessage(glob.BOT_NAME, channel, "Match have started.")
        def onTick(tick):
            fmt = ""
            if tick >= 60:
                fmt = f"{tick // 60} minute{'s' if (tick // 60) > 1 else ''}"
            elif tick >= 3:
                fmt = f"{tick} second{'s' if (tick) > 1 else ''}"
            elif tick == 2:
                chat.sendMessage(glob.BOT_NAME, channel, "glhf!")
                return
            else:
                return
            chat.sendMessage(glob.BOT_NAME, channel, f"Match starts in {fmt}")
        def onAction():
            triggerStart()
        def onAbort():
            chat.sendMessage(glob.BOT_NAME, channel, "Countdown aborted")
        match.isStarting = count > 0
        timer = countdown(count, level, onTick, onAction, onAbort)
        ptimer = _mainTimer(matchID)
        if ptimer is not None and timer.level < ptimer.level:
            return f"Ask the room {perm_level[ptimer.level]} to abort it!"
        if count > 0:
            _mainTimer(matchID, timer)
            forceReady()
            timer.start()
            return f"Match will start in {count} second(s)..."
        else:
            forceReady()
            triggerStart()
            return "Match will begin soon! Good luck!"
    
    def abortTimer(sender, channel, message):
        userID  = userUtils.getID(sender)
        matchID = getCurrentMatchID(channel)
        match   = getCurrentMatch(channel)
        level   = getMPPermissionLevel(match,userID)
        ptimer  = _mainTimer(matchID)
        if ptimer is None or ptimer.state != 1:
            return "Nothing happened."
        elif level < ptimer.level:
            return "Ask the room {perm_level[ptimer.level]} to abort it!"
        else:
            ptimer.abort()
            return None

    def invite(sender, channel, message):
        if len(message) < 1:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp invite <username>")
        username = message[0].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        userID = lookupUser(username)
        token = glob.tokens.getTokenFromUserID(userID, ignoreIRC=True)
        if token is None:
            raise exceptions.invalidUserException("That user is not connected to bancho right now.")
        _match = getCurrentMatch(channel)
        _match.invite(1, userID)
        token.enqueue(serverPackets.notification("Please accept the invite you've just received from {} to "
                                                 "enter your tourney match.".format(glob.BOT_NAME)))
        return "An invite to this match has been sent to {}".format(username)

    def map(sender, channel, message):
        if len(message) < 1 or not message[0].isdigit() or (len(message) == 2 and not message[1].isdigit()):
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp map <beatmapid> [<gamemode>]")
        beatmapID = int(message[0])
        gameMode = int(message[1]) if len(message) == 2 else 0
        if gameMode not in (0,1,2,3):
            raise exceptions.invalidArgumentsException("Gamemode must be 0, 1, 2 or 3")
        beatmapData = glob.db.fetch("SELECT beatmap_md5, song_name, mode FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [beatmapID])
        if beatmapData is None:
            raise exceptions.invalidArgumentsException("The beatmap you've selected couldn't be found in the database."
                                                       "If the beatmap id is valid, please load the scoreboard first in "
                                                       "order to cache it, then try again.")
        _match = getCurrentMatch(channel)
        _match.beatmapID = beatmapID
        _match.beatmapName = beatmapData["song_name"]
        _match.beatmapMD5 = beatmapData["beatmap_md5"]
        _match.gameMode = gameMode if beatmapData['mode'] == 0 else beatmapData['mode']
        _match.resetReady()
        _match.sendUpdates()
        return "Match map has been updated"

    def modeSet(sender, channel, message):
        if len(message) < 1 or not message[0].isdigit() or \
                (len(message) >= 2 and not message[1].isdigit()) or \
                (len(message) >= 3 and not message[2].isdigit()):
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp set <teammode> [<scoremode>] [<size>]")
        _match = getCurrentMatch(channel)
        matchTeamType = int(message[0])
        matchScoringType = int(message[1]) if len(message) >= 2 else _match.matchScoringType
        if not 0 <= matchTeamType <= 3:
            raise exceptions.invalidArgumentsException("Match team type must be between 0 and 3")
        if not 0 <= matchScoringType <= 3:
            raise exceptions.invalidArgumentsException("Match scoring type must be between 0 and 3")
        oldMatchTeamType = _match.matchTeamType
        _match.matchTeamType = matchTeamType
        _match.matchScoringType = matchScoringType
        if len(message) >= 3:
            _match.forceSize(int(message[2]))
        if _match.matchTeamType != oldMatchTeamType:
            _match.initializeTeams()
        if _match.matchTeamType == matchTeamTypes.TAG_COOP or _match.matchTeamType == matchTeamTypes.TAG_TEAM_VS:
            _match.matchModMode = matchModModes.NORMAL

        _match.sendUpdates()
        return "Match settings have been updated!"

    def abort(sender, channel, message):
        match = getCurrentMatch(channel)
        if not match.inProgress:
            return "Match is not in progress..."
        match.abort()
        return "Match aborted!"

    def kick(sender, channel, message):
        if len(message) < 1:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp kick <username>")
        username = message[0].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        userID = lookupUser(username)
        _match = getCurrentMatch(channel)
        slotID = _match.getUserSlotID(userID)
        if slotID is None:
            raise exceptions.userNotFoundException("The specified user is not in this match")
        for i in range(0, 2):
            _match.toggleSlotLocked(slotID)
        return "{} has been kicked from the match.".format(username)

    def password(sender, channel, message):
        password = "" if len(message) < 2 or not message[0].strip() else message[0]
        _match = getCurrentMatch(channel)
        _match.changePassword(password)
        return "Match password has been changed!"

    def randomPassword(sender, channel, message):
        password = generalUtils.stringMd5(generalUtils.randomString(32))
        _match = getCurrentMatch(channel)
        _match.changePassword(password)
        return "Match password has been changed to a random one"

    def mods(sender, channel, message):
        if len(message) < 1:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp mods <mod1> [<mod2>] ...")
        _match = getCurrentMatch(channel)
        newMods = 0
        freeMod = False
        for _mod in message[0:]:
            if _mod.lower().strip() == "hd":
                newMods |= mods.HIDDEN
            elif _mod.lower().strip() == "hr":
                newMods |= mods.HARDROCK
            elif _mod.lower().strip() == "dt":
                newMods |= mods.DOUBLETIME
            elif _mod.lower().strip() == "fl":
                newMods |= mods.FLASHLIGHT
            elif _mod.lower().strip() in "fi sud".split():
                newMods |= mods.FADEIN
            elif _mod.lower().strip() in "em ez".split():
                newMods |= mods.EASY
            #if _mod.lower().strip() == "none":
            #    newMods = 0
            #    break
            if _mod.lower().strip() == "freemod":
                newMods = 0
                freeMod = True
                break

        _match.matchModMode = matchModModes.FREE_MOD if freeMod else matchModModes.NORMAL
        _match.resetReady()
        if _match.matchModMode == matchModModes.FREE_MOD:
            _match.resetMods()
        _match.changeMods(newMods)
        return "Match mods have been updated!"

    def team(sender, channel, message):
        if len(message) < 2:
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp team <username> <colour>")
        username = message[0].strip()
        if not username:
            raise exceptions.invalidArgumentsException("Please provide a username")
        colour = message[1].lower().strip()
        if colour not in ["red", "blue"]:
            raise exceptions.invalidArgumentsException("Team colour must be red or blue")
        userID = lookupUser(username)
        _match = getCurrentMatch(channel)
        _match.changeTeam(userID, matchTeams.BLUE if colour == "blue" else matchTeams.RED)
        return "{} is now in {} team".format(username, colour)

    def settings(sender, channel, message):
        _match = getCurrentMatch(channel)
        single = False if len(message) < 2 else message[0].strip().lower() == "single"
        msg = "PLAYERS IN THIS MATCH "
        if not single:
            msg += "(use !mp settings single for a single-line version):"
            msg += "\n"
        else:
            msg += ": "
        empty = True
        for slot in _match.slots:
            if slot.user is None:
                continue
            readableStatuses = {
                slotStatuses.READY: "ready",
                slotStatuses.NOT_READY: "not ready",
                slotStatuses.NO_MAP: "no map",
                slotStatuses.PLAYING: "playing",
            }
            if slot.status not in readableStatuses:
                readableStatus = "???"
            else:
                readableStatus = readableStatuses[slot.status]
            empty = False
            msg += "* [{team}] <{status}> ~ {username}{mods}{nl}".format(
                team="red" if slot.team == matchTeams.RED else "blue" if slot.team == matchTeams.BLUE else "!! no team !!",
                status=readableStatus,
                username=glob.tokens.tokens[slot.user].username,
                mods=" (+ {})".format(generalUtils.readableMods(slot.mods)) if slot.mods > 0 else "",
                nl=" | " if single else "\n"
            )
        if empty:
            msg += "Nobody.\n"
        msg = msg.rstrip(" | " if single else "\n")
        return msg

    def scoreVersion(sender, channel, message):
        if len(message) < 1 or message[0] not in ("1", "2"):
            raise exceptions.invalidArgumentsException("Wrong syntax: !mp scorev <1|2>")
        _match = getCurrentMatch(channel)
        _match.matchScoringType = matchScoringTypes.SCORE_V2 if message[0] == "2" else matchScoringTypes.SCORE
        _match.sendUpdates()
        return "Match scoring type set to scorev{}".format(message[0])

    command_t = namedtuple('command_t', ('fun', 'mpOnly', 'syntax', 'description', 'perm'))
    commands = {
        "checkperm": command_t(checkPerms, True, '', '', 'basic'),
        "listref": command_t(listReferee, True, '', 'list current match referees', 'basic'),
        "addref": command_t(addReferee, True, '<username>', 'add user to match referees', 'creator'),
        "rmref": command_t(removeReferee, True, '<username>', 'remove user from match referees', 'creator'),
        "make": command_t(make, False, '<name>', 'create a room', 'basic'),
        "close": command_t(close, True, '<name>', 'close room', 'creator'),
        # "join": join,
        "lock": command_t(lock, True, '', '', 'host'),
        "unlock": command_t(unlock, True, '', '', 'host'),
        "size": command_t(size, True, '<2-16>', '', 'referee'),
        "move": command_t(move, True, '<username> <slot#>', '', 'referee'),
        "host": command_t(host, True, '<username>', '', 'creator'),
        "clearhost": command_t(clearHost, True, '', '', 'creator'),
        "timer": command_t(timer, True, '[timer]', '', 'basic'),
        "start": command_t(start, True, '[timer]', '', 'referee'),
        "aborttimer": command_t(abortTimer, True, '', '', 'basic'),
        "invite": command_t(invite, True, '<username>', '', 'referee'),
        "map": command_t(map, True, '<mapID> [mode]', '', 'referee'),
        "set": command_t(modeSet, True, '<vsmode> [<scoremode> [<size>]]', '', 'referee'),
        "abort": command_t(abort, True, '', '', 'player'),
        "kick": command_t(kick, True, '<username>', '', 'referee'),
        "password": command_t(password, True, '<pass>', '', 'host'),
        "randompassword": command_t(randomPassword, True, '', '', 'host'),
        "mods": command_t(mods, True, '<mod combination>', '', 'referee'),
        "team": command_t(team, True, '<username> <color>', '', 'referee'),
        "settings": command_t(settings, True, '', '', 'referee'),
        "scorev": command_t(scoreVersion, True, '<version>', '', 'referee'),
    }
    def help(sender, channel, message):
        userID = userUtils.getID(sender)
        for command, command_data in commands.items():
            chat.sendMessage(glob.BOT_NAME, sender, f"!mp {command} {command_data.syntax} {('(requires %s or higher)' % (command_data.perm,) if command_data.perm != 'basic' else '') if command_data.mpOnly else '*can be used outside mp room*'}".strip())
        chat.sendMessage(glob.BOT_NAME, sender, "This command still underwent heavy rewriting, those ugly terms and such will go soon(TM).")
        chat.sendMessage(glob.BOT_NAME, sender, "Let (us) me know about the bancho mimicking that I need to do, I'll do my best!")
        gloryID = 3 # oi.
        if userID == gloryID:
            chat.sendMessage(glob.BOT_NAME, sender, "-- a note that you left behind.")
        else:
            gloryName = userUtils.getUsername(gloryID)
            chat.sendMessage(glob.BOT_NAME, sender, f"-- {gloryName}.")
        pass
    commands['help'] = command_t(help, False, '', '', 'basic')
    def handler(sender, channel, message):
        action, args = message[0].lower().strip(), message[1:]
        if action not in commands:
            return None
        command_data  = commands[action]
        userID        = userUtils.getID(sender)
        if command_data.mpOnly:
            if not channel.startswith(f"{chatChannels.MULTIPLAYER_PREFIX}"):
                return None
            match         = getCurrentMatch(channel)
            userMPPower   = getMPPermissionLevel(match, userID)
            targetMPPower = perm_level.index(command_data.perm)
            if userMPPower < targetMPPower:
                return None
        try:
            return command_data.fun(sender, channel, args)
        except (exceptions.invalidArgumentsException, exceptions.userNotFoundException) as e:
            return str(e)
        except:
            raise
    
    return handler
handler = _wrapper_()
del _wrapper_
