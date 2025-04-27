import configparser
from typing import List

import discord
import unidecode


async def on_user_update(before, after, bot: discord.Bot, logging, config: configparser.ConfigParser):
    """Check if the user has a forbidden username, and if so, it willo be kicked"""
    if (bot.user and bot.user.id == after.id) or after.bot:
        return
    forbidden_usernames: List[str] = [val for k, val in config.items("Forbidden-Usernames")]

    try:
        decoded_name: str = unidecode.unidecode(after.name)
    except unidecode.UnidecodeError:
        logging.error("forbidden usernames: couldn't unidecode username")
        decoded_name: str = after.name

    for forbidden_name in forbidden_usernames:
        if forbidden_name.lower() in decoded_name.lower():

            guild = bot.get_guild(int(config.get("Settings", "guild_id")))
            if guild:
                member = guild.get_member(after.id)
                if not member:
                    logging.error("forbidden usernames: couldn't found guild-member by its ID")
                    return
            else:
                logging.error("forbidden usernames: couldn't found guild by its ID")
                return

            # don't do anything if it's a team member
            team_role_ids: List[int] = [int(val) for k, val in config.items("Team-Role-IDs")]
            for role in member.roles:
                if role.id in team_role_ids:
                    return

            logging.info(str(after.id) + " will be kicked due to a forbidden username")
            # log message
            embed = discord.Embed()
            embed.description = f"{after.mention} got kicked due to a forbidden username: `{forbidden_name}`!"
            embed.set_author(
                name=f"{after.name}#{after.discriminator}",
                icon_url=after.display_avatar
            )
            embed.set_thumbnail(url=after.display_avatar)
            embed.set_footer(text=f"ID {after.id}")
            embed.timestamp = discord.utils.utcnow()
            embed.colour = discord.Colour.red()
            if before.name != after.name or before.discriminator != after.discriminator:
                embed.add_field(name="Before", value=f"{before.name}#{before.discriminator}", inline=True)
                embed.add_field(name="After", value=f"{after.name}#{after.discriminator}", inline=True)
            await bot.get_channel(int(config.get("Settings", "main-log-channel-id"))).send(embed=embed)

            await member.kick(reason="Automated kick due to a forbidden username")
            return
