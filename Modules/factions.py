import asyncio
import json
from datetime import datetime
from typing import List, Optional

import discord


faction_messages: List[int] = []
"""Active faction messages that are right in the faction channel"""


class FactionContainer:
    def __init__(self, member_role_id, og_role_ids, aliases):
        self.__member_role_id = member_role_id
        self.__og_role_ids = og_role_ids
        self.__aliases = aliases

    @property
    def member_role_id(self):
        return self.__member_role_id

    @property
    def og_role_ids(self):
        return self.__og_role_ids

    @property
    def aliases(self):
        return self.__aliases

    @classmethod
    def from_json(cls, data: dict):
        try:
            member_role_id = int(data["role"])
        except KeyError:
            raise Exception("'role' in der faction-config in einem der Fraktionen nicht definiert")
        except ValueError:
            raise Exception("'role' muss eine numerische Discord ID sein!")

        try:
            og_role_ids = list(set(data["ogs"]))
        except KeyError:
            raise Exception("'ogs'-liste in der faction-config nicht definiert")
        except ValueError:
            raise Exception("'ogs'-liste muss eine json-liste aus integer sein und konnte nicht geparsed werden!")
        if not og_role_ids:
            raise Exception("'ogs'-liste in der faction-config darf nicht leer sein")

        try:
            aliases = list(set(data["aliases"]))
        except KeyError:
            raise Exception("'aliases'-liste in der faction-config nicht definiert")
        except ValueError:
            raise Exception("'aliases'-liste muss eine json-liste aus strings sein und konnte nicht geparsed werden!")
        if not aliases:
            raise Exception("'aliases'-liste in der faction-config darf nicht leer sein")

        return cls(member_role_id, og_role_ids, aliases)


class FactionConfig:
    __log_channel_id: int = 0
    __faction_chat_id: int = 0
    __factions: List[FactionContainer] = []

    @classmethod
    def get_log_channel_id(cls) -> int:
        return cls.__log_channel_id

    @classmethod
    def get_faction_chat_id(cls) -> int:
        return cls.__faction_chat_id

    # @classmethod
    # def get_factions(cls):
    #     return cls.__factions

    @classmethod
    def alias_exists(cls, alias: str) -> bool:
        for faction in cls.__factions:
            if alias in faction.aliases:
                return True
        return False

    @classmethod
    def get_faction_by_alias(cls, alias: str) -> Optional[FactionContainer]:
        for faction in cls.__factions:
            if alias in faction.aliases:
                return faction
        return None

    @staticmethod
    def is_og_of_faction(member: discord.Member, faction: FactionContainer) -> bool:
        for member_role in member.roles:
            if member_role.id in faction.og_role_ids:
                return True
        return False

    @classmethod
    def __get_factions_member_is_og_of(cls, member) -> List[FactionContainer]:
        result = []
        for fac in cls.__factions:
            for role in member.roles:
                if role.id in fac.og_role_ids:
                    result.append(fac)
        return result

    @classmethod
    def get_faction_names_member_is_og_of(cls, member) -> List[str]:
        names = []
        for f in cls.__get_factions_member_is_og_of(member):
            names.append(f.aliases[0])
        return names

    @classmethod
    def get_faction_member_is_og_of_by_name(cls, member, faction_name: str) -> Optional[FactionContainer]:
        for f in cls.__get_factions_member_is_og_of(member):
            if f.aliases[0] == faction_name:
                return f
        return None

    @classmethod
    def parse(cls, filename: str):
        """
        Reads the config file into the class data
        :param filename: Filename of the config
        :raises Exception: when the faction config is invalid formed or the file is unreadable
        """
        f = open(filename)
        try:
            data = json.load(f)
        except json.decoder.JSONDecodeError:
            raise Exception("faction-config hat einen syntaktischen fehler und kann nicht geparsed werden!")

        try:
            cls.__log_channel_id = int(data["log_channel_id"])
        except KeyError:
            raise Exception("'log_channel_id' in der faction-config nicht definiert")
        except ValueError:
            raise Exception("'log_channel_id' muss eine numerische Discord ID sein!")

        try:
            cls.__faction_chat_id = int(data["faction_chat_id"])
        except KeyError:
            raise Exception("'faction_chat_id' in der faction-config nicht definiert")
        except ValueError:
            raise Exception("'faction_chat_id' muss eine numerische Discord ID sein!")

        try:
            factions = list(data["factions"])
        except KeyError:
            raise Exception("'factions'-liste in der faction-config nicht definiert")
        except ValueError:
            raise Exception("'factions'-liste ist keine json-liste und konnte nicht geparsed werden!")
        else:
            for fn in factions:
                cls.__factions.append(FactionContainer.from_json(fn))
        # making sure the aliases are entirely unique
        used_aliases = []
        for faction in cls.__factions:
            for alias in faction.aliases:
                if alias in used_aliases:
                    raise Exception("'aliases' müssen in der ganzen json-liste einzigartig sein!")
                used_aliases.append(alias)

        f.close()


def on_connect():
    faction_messages.clear()


async def clear_reactions_in_faction_channel(bot: discord.Bot):
    """Faction System. Clears all reactions in the faction channel.
    It goes through the history of the channel and remove each reaction"""
    await bot.get_channel(FactionConfig.get_faction_chat_id()).purge()


async def reacted_in_faction_channel(bot: discord.Bot, reaction: discord.Reaction, user: discord.Member, logging):
    """Faction System. Should executed when someone reacts in the faction channel."""
    if reaction.emoji != "✅" and reaction.emoji != "❌":
        return
    if (reaction.message.author.id == user.id or user.guild_permissions.administrator) and \
            reaction.emoji == "❌":
        await reaction.message.delete()
        return
    if reaction.message.id not in faction_messages:
        return

    splitten_message = reaction.message.content.lower().split(" ")
    matches: int = 0
    faction = None
    for peace in splitten_message:
        if FactionConfig.alias_exists(peace):
            matches += 1
            if not faction:
                faction = FactionConfig.get_faction_by_alias(peace)

    if matches == 1:
        if user.guild_permissions.administrator or FactionConfig.is_og_of_faction(user, faction):
            if reaction.emoji == "✅":
                r = reaction.message.guild.get_role(faction.member_role_id)
                if r is None:
                    logging.error(f"Role {faction.member_role_id} could not found")
                    return
                await reaction.message.author.add_roles(r, reason=f"{user.id} hat ihm "
                                                                  f"die Fraktionsrolle zugewiesen")
                dt_string: str = datetime.now().strftime("%H:%M:%S")
                # noinspection PyBroadException
                try:
                    await bot.get_channel(FactionConfig.get_log_channel_id()).send(
                        f"`{dt_string}` :green_circle: {reaction.message.author.mention} hat die Rolle "
                        f"{r.mention} bekommen von {user.mention}",
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except Exception as e:
                    logging.error("could not log message in faction log channel", exc_info=e)
            await reaction.message.delete()
    else:
        await reaction.message.delete()


async def faction_message_has_send(bot: discord.Bot, message, config, logging):
    """Faction System. Should executed when someone has send a message in the faction channel."""
    # nachricht löschen wenn von einem bot gesendet
    if message.author.bot:
        await message.delete()
        return

    # nachricht löschen wenn sie einen link enthält
    if "http" in message.content.lower():
        await message.delete()
        return

    # nachricht löschen wenn sie mehr als eine mention enthält
    if len(message.mentions) > 1:
        await message.reply(
            embed=discord.Embed(description=":hot_face: Nicht so viele User auf einmal"),
            delete_after=7,
        )
        await asyncio.sleep(7)
        await message.delete()
        return

    if "@everyone" in message.system_content or "@here" in message.system_content:
        await message.reply(
            embed=discord.Embed(description=":no_entry_sign: @everyone und @here ist nicht erlaubt"),
            delete_after=7,
            allowed_mentions=discord.AllowedMentions(everyone=False),
        )
        await asyncio.sleep(7)
        await message.delete()
        return

    # nachrichten die länger als 100 zeichen lang sind, löschen
    if len(message.content) >= 100:
        await message.delete()
        return

    splitten_message = message.content.lower().split(" ")

    # lösche die nachricht wenn sie zu viele wörter hat
    if len(splitten_message) >= 10:
        await message.delete()
        return

    # suche einen rang-alias-namen in der nachricht
    matches: int = 0
    faction = None
    for peace in splitten_message:
        if FactionConfig.alias_exists(peace):
            matches += 1
            if not faction:
                faction = FactionConfig.get_faction_by_alias(peace)

    if matches == 0:
        await message.reply(
            embed=discord.Embed(description=":x: Fraktion nicht gefunden"),
            delete_after=7,
        )
        await asyncio.sleep(7)
        try:
            await message.delete()
        except discord.NotFound:
            pass
        # debugging: logs messages that wont match a faction to improve the system
        # noinspection PyBroadException
        # try:
        #     await self.get_channel(FACTION_DEBUG_LOG).send(f"```{truncate(message.content, 100)}```")
        # except Exception:
        #     pass
    elif matches == 1:
        # check if message contains 'weg' or 'entfernen' um den rang einfach direkt zu entfernen
        for word in ["weg", "entfernen"]:
            if word in splitten_message:
                target = message.author
                if len(message.mentions) > 0:
                    target = message.mentions[0]
                    if not FactionConfig.is_og_of_faction(message.author, faction) and \
                            not message.author.guild_permissions.administrator and target.id != message.author.id:
                        await message.reply(
                            embed=discord.Embed(description=f":no_entry_sign: Du kannst {target.display_name} "
                                                         f"die Rolle nicht wegnehmen"),
                            delete_after=7,
                        )
                        await asyncio.sleep(7)
                        await message.delete()
                        return

                r = message.guild.get_role(faction.member_role_id)
                if r is None:
                    logging.error(f"Role {faction.member_role_id} could not found")
                    return
                await target.remove_roles(r, reason=f"Hat die Fraktionsrolle "
                                                    f"von {message.author.id} entfernt bekommen")
                dt_string: str = datetime.now().strftime("%H:%M:%S")
                # noinspection PyBroadException
                try:
                    if target.id != message.author.id:
                        await message.reply(
                            embed=discord.Embed(description=f":white_check_mark: Du hast {target.mention} die Rolle "
                                                         f"{r.mention} entfernt"),
                            delete_after=7,
                            allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False)
                        )
                        await bot.get_channel(FactionConfig.get_log_channel_id()).send(
                            f"`{dt_string}` :red_circle: {target.mention} hat die Rolle {r.mention} "
                            f"entfernt bekommen von {message.author.mention}",
                            allowed_mentions=discord.AllowedMentions.none(),
                        )
                    else:
                        await message.reply(
                            embed=discord.Embed(description=f":white_check_mark: Du hast dir die Rolle {r.mention} "
                                                         f"entfernt"),
                            delete_after=7,
                            allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False)
                        )
                        await bot.get_channel(FactionConfig.get_log_channel_id()).send(
                            f"`{dt_string}` :red_circle: {target.mention} hat sich die Rolle {r.mention} entfernt",
                            allowed_mentions=discord.AllowedMentions.none(),
                        )
                except Exception as e:
                    logging.error("failed to complete removing faction role", exc_info=e)
                await asyncio.sleep(7)
                await message.delete()
                return
        if message.mentions and message.mentions[0].id != message.author.id:
            await message.reply(
                embed=discord.Embed(description=f":x: {message.mentions[0].display_name} muss sich "
                                             f"selbst die Rolle anfordern"),
                delete_after=7,
            )
            await asyncio.sleep(7)
            await message.delete()
            return
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        faction_messages.append(message.id)
        # delete after 10 minutes
        await asyncio.sleep(600)
        faction_messages.remove(message.id)
        try:
            await message.delete()
        except discord.NotFound:
            pass
        return
    else:
        await message.reply(
            embed=discord.Embed(description=":hot_face: Nicht so viel auf einmal. Eine Rolle nach der anderen"),
            delete_after=7,
        )
        await asyncio.sleep(7)
        await message.delete()
