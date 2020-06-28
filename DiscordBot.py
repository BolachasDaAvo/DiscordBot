import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from Util import *
import logging
import math
from Cogs.GreetingsCog import GreetingsCog
from Cogs.MemeCog import MemeCog
from Cogs.SignCog import SignCog
from Cogs.TranslatorCog import TranslatorCog
from Cogs.WeatherCog import WeatherCog
from Cogs.AdminCog import AdminCog
from Cogs.Covid19Cog import Covid19Cog
from Cogs.MusicCog import MusicCog
from Cogs.AnimalCog import AnimalCog

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
WEATHER_KEY = os.getenv("DISCORD_WEATHER_KEY")

class MyBot(commands.Bot):
    def __init__(self, prefix):
        super().__init__(command_prefix=prefix)

    async def on_ready(self):
        print(f"{self.user} has connected to Discord!")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingRequiredArgument):
            await notify(ctx, "Missing a required argument: {}. \"!help {}\" to check required arguments".format(error.param.name, ctx.command))
        elif isinstance(error, commands.BadArgument):
            await notify(ctx, "Invalid type for one or more arguments. \"!help {}\" to check valid types".format(ctx.command))
        elif isinstance(error, commands.BadUnionArgument):
            await notify(ctx, "Invalid type for {} argument. \"!help {}\" to check valid types".format(error.param.name, ctx.command))
        elif isinstance(error, commands.ArgumentParsingError):
            await notify(ctx, str(error))
        elif isinstance(error, commands.CommandNotFound):
            await notify(ctx, "Unsupported command. \"!help\" for the list of supported commands")
        elif isinstance(error, commands.CheckAnyFailure):
            await notify(ctx, str(error.errors[0]))
        elif isinstance(error, commands.CheckFailure):
            await notify(ctx, str(error))
        elif isinstance(error, commands.DisabledCommand):
            await notify(ctx, "Command {} is disabled in this server".format(ctx.command))
        elif isinstance(error, commands.CommandOnCooldown):
            await notify(ctx, "Command {} is on cooldown. Retry in {}s".format(ctx.command, math.ceil(error.retry_after)))
        elif isinstance(error, commands.MaxConcurrency):
            await notify(ctx, "The maximum number of concurrent invocations of {} has been reached".format(error.number))
        elif isinstance(error, commands.CommandInvokeError):
            logging.getLogger("discord").exception("Caught exception in {} when invoking |{}|".format(type(ctx.cog).__name__, ctx.message.content), exc_info=error)
            await notify(ctx, "An unexpected error has ocurred. Command {} could not be executed.\n The bot owner has been informed. Sorry for the inconvenience".format(ctx.command)) 
        else:
            await notify(ctx, str(error))

    async def on_message(self, message : discord.Message):
        content = message.content
        if (content.startswith("!")):
            #its a command
            await bot.process_commands(message)
        else:
            if "sporting" in message.content.lower():
                await message.add_reaction("💩")

logger = logging.getLogger("discord")
logger.setLevel(logging.WARNING)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)

bot = MyBot("!")
bot.add_cog(GreetingsCog(bot))
bot.add_cog(MemeCog(bot))
bot.add_cog(SignCog(bot))
bot.add_cog(TranslatorCog(bot))
bot.add_cog(WeatherCog(bot, WEATHER_KEY))
bot.add_cog(AdminCog(bot))
bot.add_cog(Covid19Cog(bot))
bot.add_cog(MusicCog(bot))
bot.add_cog(AnimalCog(bot))

bot.run(TOKEN)
