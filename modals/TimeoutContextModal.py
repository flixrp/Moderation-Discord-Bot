import discord

import Modules.timeouts


class TimeoutContextModal(discord.ui.Modal):
    def __init__(self, *args, member: discord.Member, bot, logging, MUTE_LOG, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.member = member
        self.bot = bot
        self.logging = logging
        self.MUTE_LOG = MUTE_LOG

        self.add_item(discord.ui.InputText(
            label="Dauer",
            max_length=30,
            placeholder="Mute dauer (3d 10h 5m 29s)",
            required=True,
            style=discord.InputTextStyle.singleline,
        ))

        self.add_item(discord.ui.InputText(
            label="Grund",
            max_length=512,
            required=True,
            style=discord.InputTextStyle.multiline,
        ))

    async def callback(self, interaction: discord.Interaction):
        try:
            duration = Modules.timeouts.TimeoutDuration(self.children[0].value)
        except Exception:
            duration = Modules.timeouts.TimeoutDuration("3d")
        reason = self.children[1].value

        if self.member.timed_out and duration.mute_timestamp_for_discord().timestamp() <= self.member.communication_disabled_until.timestamp():
            await interaction.response.send_message("Benutzer ist schon im Timeout", ephemeral=True)
            return

        try:
            await self.member.timeout(duration.mute_timestamp_for_discord(), reason=reason)
            self.logging.info("muted user " + str(self.member.id))
        except discord.HTTPException as e:
            self.logging.error("cannot mute user " + str(self.member.id), exc_info=e)
            await interaction.response.send_message(f"{self.member.mention} konnte nicht stumm geschaltet werden", ephemeral=True)
        else:
            e = discord.Embed()
            e.set_author(
                name=f"{discord.utils.escape_markdown(self.member.display_name)}#{self.member.discriminator} wurde stumm geschaltet",
                icon_url=self.member.display_avatar.url
            )
            e.description = f"Timeout für {duration.to_mute_length_str()}\n" \
                            f"Bis: {discord.utils.format_dt(duration.mute_timestamp_for_discord(), 'F')}"
            e.add_field(
                name="Grund",
                value=discord.utils.escape_markdown(reason)
            )
            e.set_footer(text=f"ID {self.member.id}")
            await interaction.response.send_message(embed=e, ephemeral=True)
            # log
            e.description += f"\nGestummt von {interaction.user.mention}"
            try:
                channel = self.bot.get_channel(self.MUTE_LOG)
                if channel:
                    await channel.send(embed=e)
                else:
                    self.logging.error("Mute-log channel not found")
            except discord.Forbidden:
                self.logging.error("Cannot send messages in Mute-log")
