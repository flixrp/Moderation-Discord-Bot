import datetime
import re

import discord


class TimeoutDuration:
    def __init__(self, duration: str, maximise_to_discord_limit: bool = True):
        """
        Create a new timeout duration instance from a duration string
        :param duration: duration string e.g. 3d 10h 5m 29s
        :param maximise_to_discord_limit whether to limit the timeout duration to discord's 28 days limit. Default True
        :raises Exception: when the duration could not be parsed
        """
        result = re.match(r"^(?:([0-9]{1,6})[d]\s*?|([0-9]{1,6})[h]\s*?|([0-9]{1,6})[m]\s*?|([0-9]{1,6})[s]\s*?){1,4}$",
                          duration, re.IGNORECASE)
        if not result:
            raise Exception("couldn't parse timeout duration")
        # calc mute duration
        days = hours = minutes = seconds = 0
        if result.group(1):
            days = int(result.group(1))
        if result.group(2):
            hours = int(result.group(2))
        if result.group(3):
            minutes = int(result.group(3))
        if result.group(4):
            seconds = int(result.group(4))
        while seconds >= 60:
            seconds -= 60
            minutes += 1
        while minutes >= 60:
            minutes -= 60
            hours += 1
        while hours >= 24:
            hours -= 24
            days += 1
        self.__total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds

        # maximize mute length to 28 days due discord (4000 seconds tolerance) (possible time difference)
        if maximise_to_discord_limit and self.__total_seconds > 28 * 86400 - 4000:
            self.__total_seconds = 28 * 86400 - 4000
            hours = minutes = seconds = 0
            days = 28

        self.__days = days
        self.__hours = hours
        self.__minutes = minutes
        self.__seconds = seconds

    @property
    def total_seconds(self) -> int:
        return self.__total_seconds

    def mute_timestamp_for_discord(self) -> datetime.datetime:
        return discord.utils.utcnow() + datetime.timedelta(seconds=self.__total_seconds)

    def to_mute_length_str(self) -> str:
        result = ""
        if self.__days == 1:
            result += f"{self.__days} Tag "
        elif self.__days > 1:
            result += f"{self.__days} Tage "
        if self.__hours == 1:
            result += f"{self.__hours} Stunde "
        elif self.__hours > 1:
            result += f"{self.__hours} Stunden "
        if self.__minutes == 1:
            result += f"{self.__minutes} Minute "
        elif self.__minutes > 1:
            result += f"{self.__minutes} Minuten "
        if self.__seconds == 1:
            result += f"{self.__seconds} Sekunde "
        elif self.__seconds > 1:
            result += f"{self.__seconds} Sekunden "
        return result.rstrip()
