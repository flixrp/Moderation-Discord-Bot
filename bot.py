#!/usr/bin/python3
import configparser
import datetime
import logging
import os
import re
import sys
import traceback
from datetime import timedelta
from io import StringIO
from typing import List, Optional

import aiomysql
import discord
from discord.ext import commands

import Modules.factions
import Modules.forbidden_usernames
import Modules.timeouts
from Modules.factions import FactionConfig
from modals.TimeoutContextModal import TimeoutContextModal


def truncate(s: str, length: int = 1024) -> str:
    """
    Truncates a string to a maximum length. Appends '..' to the end if the string is too long.

    :param s: The string to truncate
    :param length: The number after which length the string should be cutten. Default is 1024
    :return: The truncate string
    """
    if length > 3:
        length -= 2
    return (s[:length] + '..') if len(s) > length else s


async def format_message_placeholders(msg: str, user_id: int):
    user = await bot.get_or_fetch_user(user_id)
    if user:
        msg = re.sub(r"%USERNAME%", user.name, msg, flags=re.IGNORECASE)
    else:
        msg = re.sub(r"%USERNAME%", "{user not found}", msg, flags=re.IGNORECASE)
    return re.sub(r"%USER_MENTION%", f"<@{user_id}>", msg, flags=re.IGNORECASE)


class Bot(discord.Bot):
    def __init__(self, description=None, *args, **options):
        super().__init__(description, *args, **options)
        self.pool = None

    async def close(self):
        await self.pool.close()  # close the db connection before the bot closes the async event pool
        await super().close()

    async def fetchone(self, query, args=None):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args)
                return await cur.fetchone()

    async def fetchall(self, query, args=None):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args)
                return await cur.fetchall()

    async def execute(self, query, args=None):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args)

    async def executemany(self, query, args=None):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(query, args)


bot = Bot(
    intents=discord.Intents(
        message_content=True,
        guild_messages=True,
        guild_reactions=True,
        members=True,
        guilds=True,
        voice_states=True,
    ),
    allowed_mentions=discord.AllowedMentions.none(),
)

logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'latest.log'),
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
)
logging.info("Started with python version " + sys.version)
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.ini'))
try:
    FactionConfig.parse(os.path.join(os.path.dirname(os.path.realpath(__file__)), "fraktionen-config.json"))
except Exception as e:
    logging.error("error with config", exc_info=e)
    raise e


async def init_pool():
    bot.pool = await aiomysql.create_pool(
        host=config.get("MariaDB", "host"),
        port=int(config.get("MariaDB", "port")),
        user=config.get("MariaDB", "user"),
        password=config.get("MariaDB", "password"),
        db=config.get("MariaDB", "database"),
        loop=bot.loop,
        autocommit=True)


bot.loop.run_until_complete(init_pool())

GUILD_ID = int(config.get("Settings", "guild_id"))
MUTE_LOG = int(config.get("Settings", "mute-log-channel-id"))
MAIN_LOG = int(config.get("Settings", "main-log-channel-id"))

TEAM_ROLE_IDS: List[int] = []
for k, val in config.items("Team-Role-IDs"):
    TEAM_ROLE_IDS.append(int(val))


#...


@bot.event
async def on_error(event, *args, **kwargs):
    logging.error(traceback.format_exc())


@bot.event
async def on_application_command_error(ctx, error):
    if type(error) == discord.ext.commands.CommandOnCooldown:
        await ctx.respond("Du musst noch warten bevor du diesen Befehl nochmal benutzen kannst", ephemeral=True)
    elif type(error) == discord.ext.commands.MissingAnyRole:
        await ctx.respond("Du hast dafür keine Berechtigung", ephemeral=True)
    else:
        logging.error(error)
        await ctx.respond("Ein interner Fehler ist aufgetreten. Bitte melde diesen Vorfall", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    logging.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    await Modules.factions.clear_reactions_in_faction_channel(bot)


@bot.event
async def on_connect():
    Modules.factions.on_connect()
    if bot.auto_sync_commands:
        await bot.sync_commands()


@bot.event
async def on_message(message):
    if message.author == bot.user or message.author.bot or message.author.system:
        return
    if FactionConfig.get_faction_chat_id() == message.channel.id:
        await Modules.factions.faction_message_has_send(bot, message, config, logging)
    #...


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user):
    if user.bot or user.system:
        return
    if FactionConfig.get_faction_chat_id() == reaction.message.channel.id:
        await Modules.factions.reacted_in_faction_channel(bot, reaction, user, logging)


@bot.event
async def on_member_join(member: discord.Member):
    await Modules.forbidden_usernames.on_user_update(member, member, bot, logging, config)


@bot.event
async def on_user_update(before, after):
    await Modules.forbidden_usernames.on_user_update(before, after, bot, logging, config)


#...


@bot.event
async def on_interaction(interaction):
    if interaction.user.bot:
        return
    await bot.process_application_commands(interaction)  # process the commands that have been registered to the bot


@bot.slash_command(
    guild_ids=[GUILD_ID],
    description="Bannt einen Benutzer vom Server. Speichert die Rollen für einen leichteren unban.",
)
@commands.cooldown(2, 60 * 5, commands.BucketType.user)  # 2x in 5 minuten
@commands.cooldown(5, 60 * 60, commands.BucketType.user)  # 5x in einer Stunde
@commands.cooldown(15, 60 * 60 * 6, commands.BucketType.user)  # 15x in 6 Stunden
@commands.cooldown(100, 60 * 60 * 24, commands.BucketType.guild)  # 100x an einem tag server weit
@discord.default_permissions(ban_members=True)
@commands.has_any_role(*TEAM_ROLE_IDS)
async def ban(ctx: discord.ApplicationContext,
              user: discord.Option(discord.SlashCommandOptionType.user,
                                   description="Der Benutzer oder die Benutzer-ID als Zahl den du bannen möchtest"),
              reason: discord.Option(discord.SlashCommandOptionType.string,
                                     min_length=3,
                                     max_length=255,
                                     description="Bann-Grund")):
    if not (isinstance(user, discord.User) or isinstance(user, discord.Member)):
        await ctx.respond("Benutzer nicht gefunden", ephemeral=True)
        return

    try:
        ban = await ctx.guild.fetch_ban(user)
    except discord.NotFound:
        pass  # only continue if the user not already banned
    except discord.HTTPException as ban_get_error:
        logging.error("couldn't fetch ban", exc_info=ban_get_error)
        raise ban_get_error
    else:
        assert ban.user.id == user.id
        await ctx.respond(f"{user.mention} ist bereits gebannt", ephemeral=True)
        return

    async with bot.pool.acquire() as conn:
        await conn.autocommit(False)
        await conn.begin()
        async with conn.cursor() as cursor:

            await cursor.execute(
                """
                INSERT INTO Ban (banner_fk, user_id, ban_reason) VALUES (
                    (SELECT id FROM Supporter WHERE discord_id = %s),
                    %s,
                    %s
                );
                """,
                (ctx.user.id, user.id, reason),
            )

            # attach roles
            records_to_insert: List[tuple] = []
            for role in user.roles:
                records_to_insert.append((role.id, role.name, cursor.lastrowid,))
            await cursor.executemany(
                "INSERT INTO BanUserRole (role_id, name, ban_fk) VALUES (%s, %s)",
                records_to_insert,
            )

            try:
                #await ctx.guild.ban(user, reason=reason)
                pass
            except discord.HTTPException as ban_error:
                await conn.rollback()
                logging.error(f"couldn't ban {user.id}", exc_info=ban_error)
                raise ban_error
            else:
                await conn.commit()
            finally:
                await conn.autocommit(True)

            await ctx.respond(f"{user.mention} wurde gebannt", ephemeral=True)

            # log message
            e = discord.Embed()
            e.colour = 0x47b07f
            e.set_author(
                name=f"[BAN] {user.display_name}",
                icon_url=user.display_avatar
            )
            e.add_field(name="Nutzer", value=user.mention)
            e.add_field(name="Moderator", value=ctx.user.mention)
            e.add_field(name="Bann-Grund", value=discord.utils.escape_markdown(reason))
            try:
                channel = bot.get_channel(MUTE_LOG)
                if channel:
                    await channel.send(embed=e)
                else:
                    logging.error("Mute-log channel not found")
            except discord.Forbidden as e:
                logging.error("Cannot send messages in Mute-log", exc_info=e)


@bot.slash_command(
    guild_ids=[GUILD_ID],
    name="sync-category-permissions",
    description="Synchronisiert die Berechtigungen in allen Channeln einer Kategorie mit dieser",
)
@commands.cooldown(1, 30, commands.BucketType.channel)
@discord.default_permissions(administrator=True)
async def sync_category_permissions_command(ctx: discord.ApplicationContext,
                                            category: discord.Option(discord.SlashCommandOptionType.channel,
                                                                     channel_types=[discord.ChannelType.category],
                                                                     description="Die Kategorie"),
                                            confirmation: discord.Option(discord.SlashCommandOptionType.string,
                                                                         name="bestätigung",
                                                                         description="Bestätige die synchronisierung mit \"Bestätige Sync\"!")):
    if not isinstance(category, discord.CategoryChannel):
        await ctx.respond("Der angegebene Channel ist keine Kategorie", ephemeral=True)
        return
    if not ctx.user.guild_permissions.administrator:
        await ctx.respond("Du musst Administrator sein um dies benutzen zu können", ephemeral=True)
        return
    if confirmation.lower() != "bestätige sync":
        await ctx.respond("Bestätigungs-Parameter falsch", ephemeral=True)
        return
    await ctx.defer(ephemeral=True)
    synced_channels: int = 0
    for channel in category.channels:
        try:
            await channel.edit(sync_permissions=True)
        except discord.Forbidden:
            await ctx.edit(f":x: Keine Berechtigung um {channel.mention} zu bearbeiten")
            return
        synced_channels += 1
    await ctx.edit(embed=discord.Embed(
        description=f"{synced_channels} Channel in {category.mention} wurden synchronisiert"))


@bot.slash_command(
    guild_ids=[GUILD_ID],
    name="delete-category-channels",
    description="Löscht alle Channel in einer Kategorie",
)
@commands.cooldown(1, 30, commands.BucketType.channel)
@discord.default_permissions(administrator=True)
async def sync_category_permissions_command(ctx: discord.ApplicationContext,
                                            category: discord.Option(discord.SlashCommandOptionType.channel,
                                                                     channel_types=[discord.ChannelType.category],
                                                                     description="Die Kategorie in der alle Channel gelöscht werden sollen"),
                                            confirmation: discord.Option(discord.SlashCommandOptionType.string,
                                                                         name="bestätigung",
                                                                         description="Bestätige die löschung mit \"Bestätige Löschung\"!")):
    if not isinstance(category, discord.CategoryChannel):
        await ctx.respond("Der angegebene Channel ist keine Kategorie", ephemeral=True)
        return
    if not ctx.user.guild_permissions.administrator:
        await ctx.respond("Du musst Administrator sein um dies benutzen zu können", ephemeral=True)
        return
    if confirmation.lower() != "bestätige löschung":
        await ctx.respond("Bestätigungs-Parameter falsch", ephemeral=True)
        return
    await ctx.defer(ephemeral=True)
    deleted_channels: int = 0
    for channel in category.channels:
        try:
            await channel.delete()
        except discord.Forbidden:
            continue
        deleted_channels += 1
    await ctx.edit(embed=discord.Embed(
        description=f"{deleted_channels} Channel in {category.mention} wurden gelöscht"))


async def get_faction_names(ctx: discord.AutocompleteContext):
    """for auto complete"""
    return FactionConfig.get_faction_names_member_is_og_of(ctx.interaction.user)


@bot.slash_command(
    guild_ids=[GUILD_ID],
    name="frak-list",
    description="Liste alle Mitglieder einer Fraktion auf",
)
async def fraction_list(ctx: discord.ApplicationContext,
                        faction: discord.Option(str, name="fraktion", description="Eine Fraktion bei der du OG bist", autocomplete=discord.utils.basic_autocomplete(get_faction_names))):
    faction = FactionConfig.get_faction_member_is_og_of_by_name(ctx.interaction.user, faction)
    if not faction:
        await ctx.respond(content="Du musst OG dieser Fraktion sein um diesen Befehl benutzen zu können", ephemeral=True)
        return
    g = bot.get_guild(GUILD_ID)
    frak_members = []
    og_members = []

    def go_through(mem):
        for r in mem.roles:
            if r.id in faction.og_role_ids:
                og_members.append(mem)
                return
        for r in mem.roles:
            if r.id == faction.member_role_id:
                frak_members.append(mem)
                return

    for m in g.members:
        go_through(m)

    content = "Rang,Discord ID,Anzeigename\n"
    for m in og_members:
        content += f"OG,{m.id},{m.display_name}\n"
    for m in frak_members:
        content += f",{m.id},{m.display_name}\n"
    with StringIO(content) as c:
        await ctx.respond(
            file=discord.File(c, filename="mitglieder.csv"),
            ephemeral=True,
        )


@bot.user_command(
    name="Timeout",
    guild_ids=[GUILD_ID],
)
@discord.default_permissions(administrator=True)
@commands.has_any_role(*TEAM_ROLE_IDS)
async def context_mute(ctx: discord.ApplicationContext, member: discord.Member):
    if member.bot or member.system or member.guild_permissions.administrator:
        await ctx.respond("Du kannst diesen Benutzer nicht stumm schalten", ephemeral=True)
        return
    if ctx.user.id == member.id:
        await ctx.respond("Du kannst dich nicht selbst stumm schalten", ephemeral=True)
        return
    for r in member.roles:
        if r.id in TEAM_ROLE_IDS:
            await ctx.respond("Du kannst keinen Moderator stumm schalten", ephemeral=True)
            return
    modal = TimeoutContextModal(
        title=f"Timeout für {member.display_name}",
        member=member,
        bot=bot,
        logging=logging,
        MUTE_LOG=MUTE_LOG,
    )
    await ctx.send_modal(modal)


@bot.slash_command(
    guild_ids=[GUILD_ID],
    description="Benutzer in Timeout schicken",
)
@commands.cooldown(2, 2 * 60, commands.BucketType.user)
@discord.default_permissions(administrator=True)
@commands.has_any_role(*TEAM_ROLE_IDS)
async def mute(ctx: discord.ApplicationContext,
               user: discord.Option(discord.SlashCommandOptionType.user,
                                    description="Der Benutzer oder die Benutzer-ID als Zahl"),
               duration: discord.Option(discord.SlashCommandOptionType.string,
                                        description="Mute dauer (3d 10h 5m 29s)"),
               reason: discord.Option(discord.SlashCommandOptionType.string, description="Mute-Grund")):
    if not isinstance(user, discord.Member):
        await ctx.respond("Benutzer nicht gefunden oder nicht auf dem Server", ephemeral=True)
        return
    if user.bot or user.system or user.guild_permissions.administrator:
        await ctx.respond("Du kannst diesen Benutzer nicht stumm schalten", ephemeral=True)
        return
    if user.id == ctx.interaction.user.id:
        await ctx.respond("Du kannst dich nicht selbst stumm schalten", ephemeral=True)
        return
    for r in user.roles:
        if r.id in TEAM_ROLE_IDS:
            await ctx.respond("Du kannst keinen Moderator stumm schalten", ephemeral=True)
            return
    try:
        timeout = Modules.timeouts.TimeoutDuration(duration)
    except Exception:
        e = discord.Embed()
        e.title = "Ungültige Mute-länge"
        e.description = "Gültige Zeitangaben sind zum Beispiel `1d 30m` oder `17d`.\n" \
                        "Es muss immer eine Zahl mit einem Zeitkürzel (**d**, **h**, **m** oder **s**) folgen, für " \
                        "jeweils Tage, Stunden, Minuten und Sekunden. " \
                        "Diese Zeiteinheiten sind dabei frei miteinander Kombinierbar!"
        await ctx.respond(embed=e, ephemeral=True)
        return

    # minimize seconds
    if timeout.total_seconds < 5:
        await ctx.respond("Die mute dauer muss mindestens 5 Sekunden sein", ephemeral=True)
        return

    new_mute_timestamp = timeout.mute_timestamp_for_discord()
    if user.timed_out and new_mute_timestamp.timestamp() <= user.communication_disabled_until.timestamp():
        e = discord.Embed()
        e.set_author(
            name=f"{discord.utils.escape_markdown(user.display_name)}#{user.discriminator} ist schon stumm geschaltet",
            icon_url=user.display_avatar.url
        )
        e.add_field(
            name="Ablaufdatum",
            value=discord.utils.format_dt(user.communication_disabled_until, 'R'),
            inline=True
        )
        e.set_footer(text=f"ID {user.id}")
        await ctx.respond(embed=e, ephemeral=True)
        return
    try:
        await user.timeout(new_mute_timestamp, reason=reason)
        logging.info("muted user " + str(user.id))
    except discord.HTTPException as e:
        logging.error("cannot mute user " + str(user.id), exc_info=e)
        await ctx.respond(f"{user.mention} konnte nicht stumm geschaltet werden", ephemeral=True)
    else:
        e = discord.Embed()
        e.set_author(
            name=f"{discord.utils.escape_markdown(user.display_name)}#{user.discriminator} wurde stumm geschaltet",
            icon_url=user.display_avatar.url
        )
        e.description = f"Timeout für {timeout.to_mute_length_str()}\n" \
                        f"Bis: {discord.utils.format_dt(new_mute_timestamp, 'F')}"
        e.add_field(
            name="Grund",
            value=discord.utils.escape_markdown(reason)
        )
        e.set_footer(text=f"ID {user.id}")
        await ctx.respond(embed=e, ephemeral=True)
        # log
        e.description += f"\nGestummt von {ctx.user.mention}"
        try:
            channel = bot.get_channel(MUTE_LOG)
            if channel:
                await channel.send(embed=e)
            else:
                logging.error("Mute-log channel not found")
        except discord.Forbidden:
            logging.error("Cannot send messages in Mute-log")


@bot.slash_command(
    guild_ids=[GUILD_ID],
    description="Timeout von Benutzern entfernen",
)
@commands.cooldown(1, 60, commands.BucketType.user)
@discord.default_permissions(administrator=True)
@commands.has_any_role(*TEAM_ROLE_IDS)
async def unmute(ctx: discord.ApplicationContext,
                 user: discord.Option(discord.SlashCommandOptionType.user,
                                      description="Der Benutzer oder die Benutzer-ID als Zahl"),
                 reason: discord.Option(discord.SlashCommandOptionType.string,
                                        description="Grund der entstummung") = None):
    if not isinstance(user, discord.Member):
        await ctx.respond("Benutzer nicht gefunden oder nicht auf dem Server", ephemeral=True)
        return
    if not user.timed_out:
        await ctx.respond(f"{user.mention} hat keinen Timeout", ephemeral=True)
        return
    try:
        await user.remove_timeout(reason=reason)
        logging.info("unmuted user " + str(user.id))
    except discord.HTTPException as e:
        logging.error("cannot unmute user " + str(user.id), exc_info=e)
        await ctx.respond(f"{user.mention} konnte nicht entstummt werden", ephemeral=True)
    else:
        e = discord.Embed()
        e.set_author(name=f"{discord.utils.escape_markdown(user.display_name)}#{user.discriminator} wurde entstummt",
                     icon_url=user.display_avatar.url)
        if reason:
            e.add_field(
                name="Grund",
                value=discord.utils.escape_markdown(reason)
            )
        e.set_footer(text=f"ID {user.id}")
        await ctx.respond(embed=e, ephemeral=True)
        # log
        e.description = f"Entstummt von {ctx.user.mention}"
        try:
            channel = bot.get_channel(MUTE_LOG)
            if channel:
                await channel.send(embed=e)
            else:
                logging.error("Mute-log channel not found")
        except discord.Forbidden:
            logging.error("Cannot send messages in Mute-log")


def presence_status_to_string(status) -> str:
    if status == discord.Status.online:
        return "_Online_ :green_circle:"
    elif status == discord.Status.dnd:
        return "_Nicht Stören_ :no_entry:"
    elif status == discord.Status.idle:
        return "_AFK_ :crescent_moon:"
    elif status == discord.Status.streaming:
        return "_Streamt_ :purple_circle:"
    else:
        return "_Offline_ :black_circle:"


async def raw_userinfo(ctx, user):
    is_member = False  # Whether the user is on the server
    u = bot.get_guild(ctx.guild.id).get_member(user.id)
    if isinstance(u, discord.Member):
        user = u
        is_member = True
    elif not isinstance(user, discord.User):
        await ctx.respond("Benutzer nicht gefunden", ephemeral=True)
        return

    # basic stuff
    e = discord.Embed()
    if user.banner:
        e.set_thumbnail(url=user.banner.url)
    if user.avatar:
        e.set_author(name=f"{discord.utils.escape_markdown(user.name)}#{user.discriminator}",
                     icon_url=user.avatar.url)
    else:
        e.set_author(name=f"{discord.utils.escape_markdown(user.name)}#{user.discriminator}",
                     icon_url=user.default_avatar.url)
    e.set_thumbnail(url=user.display_avatar.url)
    tags = ""
    if user.system:
        if tags:
            tags += ", "
        tags += "_`System`_"
    if user.bot:
        if tags:
            tags += ", "
        tags += "_`Bot`_"
    s = f"{user.mention}\n"
    if is_member and user.nick:
        s += f"Nickname: {discord.utils.escape_markdown(user.nick)}\n"
    s += f"ID: {user.id}\nAccount Erstellt: {discord.utils.format_dt(user.created_at)}"
    if tags:
        s += "\nTags: " + tags
    if is_member and not user.top_role.managed and not user.top_role.is_default():
        s += f"\nHöchste Rolle: {user.top_role.mention}"
    if is_member and user.premium_since:
        s += f"\nNitro: Boostet Server seid {discord.utils.format_dt(user.premium_since, 'R')}"

    # status stuff
    if is_member:
        s += f"\n\n**Aktivität / Status**\nHandy: {presence_status_to_string(user.mobile_status)}\n" \
             f"PC: {presence_status_to_string(user.desktop_status)}\n" \
             f"Web: {presence_status_to_string(user.web_status)}"

    # member stuff
    if is_member:
        s += f"\n\n:calendar: Beigetreten: {discord.utils.format_dt(user.joined_at)}"
        if user.timed_out:
            s += f"\n:mute: Timeout bis: {discord.utils.format_dt(user.communication_disabled_until, 'F')}"

    # ban stuff
    try:
        ban = await ctx.guild.fetch_ban(user)
        if ban.reason:
            s += f"\n\n:no_pedestrians: Gebannt für:\n> {discord.utils.escape_markdown(ban.reason)}"
        else:
            s += "\n\n:no_pedestrians: Gebannt ohne banngrund"
    except discord.NotFound:
        pass
    except discord.HTTPException as ban_error:
        logging.error("couldn't fetch ban", exc_info=ban_error)
        s += "\n\n:no_pedestrians: Bann-Status konnte nicht abgefragt werden!"

    # voice stuff
    if is_member and user.voice and user.voice.channel:
        e.add_field(
            name="Aktiv im Sprachkanal",
            value=f":loud_sound: #{user.voice.channel.name}",
            inline=True
        )

    s += "\n\u200b"
    e.description = s
    if not is_member:
        e.set_footer(text="Dieser Benutzer ist nicht auf diesem server")

    await ctx.respond(embed=e, ephemeral=True)


@bot.slash_command(
    guild_ids=[GUILD_ID],
    description="Details von Benutzern abfragen",
)
@discord.default_permissions(administrator=True)
@commands.has_any_role(*TEAM_ROLE_IDS)
async def userinfo(ctx: discord.ApplicationContext,
                   user: discord.Option(discord.SlashCommandOptionType.user,
                                        description="Der Benutzer oder die Benutzer-ID als Zahl")):
    await raw_userinfo(ctx, user)


@bot.user_command(
    name="Userinfo",
    guild_ids=[GUILD_ID],
)
@discord.default_permissions(administrator=True)
@commands.has_any_role(*TEAM_ROLE_IDS)
async def context_userinfo(ctx: discord.ApplicationContext, member: discord.Member):
    await raw_userinfo(ctx, member)


@bot.message_command(
    name="Nachricht löschen",
    guild_ids=[GUILD_ID],
)
@commands.cooldown(1, 1, commands.BucketType.user)
@discord.default_permissions(administrator=True)
@commands.has_any_role(*TEAM_ROLE_IDS)
async def context_delete_message(ctx: discord.ApplicationContext, message: discord.Message):
    log_channel = bot.get_channel(int(config.get("Settings", "message-deletion-log-channel-id")))
    if not log_channel:
        raise Exception("message deletion channel not found")
    if not ctx.interaction.app_permissions.manage_messages:
        await ctx.respond("Fehler: Ich habe hier keine Berechtigung Nachrichten zu löschen", ephemeral=True)
        return
    if message.pinned:  # angepinnt
        await ctx.respond("Diese Nachricht kannst du nicht löschen, da sie angepinnt ist", ephemeral=True)
        return
    if message.interaction:  # wenn eine nachricht von einer interaction (bot)
        await ctx.respond("Du kannst keine Nachrichten von Interaktionen löschen", ephemeral=True)
        return
    if message.flags.crossposted or message.flags.is_crossposted or message.flags.urgent or message.is_system():
        await ctx.respond("Du kannst diese Art von Nachricht nicht löschen", ephemeral=True)
        return
    if message.webhook_id:
        await ctx.respond("Du kannst keine Nachrichten von Webhooks löschen", ephemeral=True)
        return
    if message.author.bot or message.author.system:
        await ctx.respond("Nachrichten von Bots sind Heilig und können nicht gelöscht werden. Was denkst du?", ephemeral=True)
        return
    if message.created_at < discord.utils.utcnow() - datetime.timedelta(days=14):
        await ctx.respond("Die Nachricht ist zu alt um gelöscht zu werden", ephemeral=True)
        return
    # check for teammate
    result = await bot.fetchone(
        "SELECT TRUE, left_at IS NOT NULL FROM Supporter WHERE discord_id = %s",
        (message.author.id,),
    )
    if result:
        (is_team_mate, is_left) = result
        if is_team_mate:
            if is_left:
                await ctx.respond("Du kannst Nachrichten von ehemaligen Teammitgliedern nicht löschen", ephemeral=True)
            else:
                await ctx.respond("Du kannst Nachrichten von Teammitgliedern nicht löschen", ephemeral=True)
            return
    if isinstance(message.author, discord.Member):
        if ctx.user.top_role < message.author.top_role:
            await ctx.respond("Du kannst keine Nachrichten von Benutzern, die im Rang über dir stehen, löschen", ephemeral=True)
            return
        if message.author.guild_permissions.administrator:
            await ctx.respond("Du kannst keine Nachrichten von Administratoren löschen", ephemeral=True)
            return
        if message.author.guild_permissions.manage_messages:
            await ctx.respond("Nachrichten von diesem Benutzer kannst du nicht löschen da dieser auch Lösch-Berechtigung hat", ephemeral=True)
            return
        for r in message.author.roles:
            if r.id in TEAM_ROLE_IDS:
                await ctx.respond("Du kannst Nachrichten von Teammitgliedern nicht löschen", ephemeral=True)
                return

    await ctx.defer(ephemeral=True)

    e = discord.Embed()
    e.title = f":wastebasket: Nachricht gelöscht von {ctx.user.display_name}"
    if message.reference:
        e.description = f"↵ Antwort auf {message.reference.jump_url}"
    e.add_field(name="gesendet am", value=discord.utils.format_dt(datetime.datetime.now(), 'f'), inline=True)
    e.add_field(name="gesendet von", value=message.author.mention, inline=True)
    e.add_field(name="Kanal", value=message.channel.mention, inline=True)
    e.add_field(name="gelöscht von", value=ctx.user.mention, inline=True)
    e.timestamp = datetime.datetime.now()
    files = []
    success_files = 0
    for a in message.attachments:
        try:
            file = await a.to_file()
            files.append(file)
            success_files += 1
        except discord.HTTPException:
            pass
    e.add_field(name="Anhänge heruntergeladen", value=f"{success_files}/{len(message.attachments)}")
    if message.stickers:
        e.add_field(name=f"Sticker", value=f"{message.stickers[0].name} (1/{len(message.stickers)})\n{message.stickers[0].url}")

    log_message = await log_channel.send(content=message.content, embed=e, files=files)

    # db logging
    ref = None
    if message.reference:
        ref = message.reference.message_id
    cont = None
    if message.content:
        cont = truncate(message.content, 6000)
    await bot.execute(
        """
        INSERT INTO MessageDeletion (msg_content, msg_reference, msg_created_at, msg_author, msg_channel, msg_attachment_amount, msg_sticker_amount, msg_flags, log_message_jump_url, supporter_fk) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, (SELECT id FROM Supporter WHERE discord_id = %s)
        );
        """,
        (cont, ref, message.created_at, message.author.id, message.channel.id, len(message.attachments), len(message.stickers), message.flags.value, log_message.jump_url, ctx.user.id),
    )
    try:
        await message.delete(reason=f"deleted by {ctx.user.id} at {datetime.datetime.now()}")
    except discord.HTTPException as err:
        logging.error("couldn't delete message", exc_info=err)
        await ctx.respond("Fehler: Nachricht konnte nicht gelöscht werden")
        return
    await ctx.delete()


@bot.slash_command(
    guild_ids=[GUILD_ID],
    description="Details einer Einladung suchen",
)
@discord.default_permissions(administrator=True)
@commands.has_any_role(*TEAM_ROLE_IDS)
async def inviteinfo(ctx: discord.ApplicationContext, invite: discord.Option(discord.SlashCommandOptionType.string,
                                                                             description="Der Einladungs-Code oder URL")):
    code: str = discord.utils.resolve_invite(invite)
    try:
        inv = await bot.fetch_invite(code, with_counts=True, with_expiration=True)
    except discord.HTTPException:
        await ctx.respond(f"Keine Einladung mit dem Code **{code}** gefunden", ephemeral=True)
        return
    e = discord.Embed()
    e.title = f"Einladungs details"
    e.description = f"Einladungscode `{inv.code}`"
    if inv.inviter:
        e.add_field(
            name="Erstellt von",
            value=f"{inv.inviter.mention} "
                  f"({discord.utils.escape_markdown(inv.inviter.name)}#{inv.inviter.discriminator})",
            inline=True
        )
    if inv.expires_at:
        e.add_field(name="Läuft ab", value=discord.utils.format_dt(inv.expires_at), inline=True)
    e.add_field(
        name="Guild",
        value=f"Name: {discord.utils.escape_markdown(str(inv.guild.name))}\n"
              f"Beschreibung: {discord.utils.escape_markdown(str(inv.guild.description))}\n"
              f"Member: :green_circle: {inv.approximate_presence_count} "
              f"Online • {inv.approximate_member_count} Mitglieder\nID: {inv.guild.id}",
        inline=False
    )
    if inv.guild.icon:
        e.set_thumbnail(url=inv.guild.icon.url)
    await ctx.respond(embed=e, ephemeral=True)


bot.run(config.get("Settings", "token"))
