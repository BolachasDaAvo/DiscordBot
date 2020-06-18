import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
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
    
    async def on_message(self, message : discord.Message):
        if message.author == self.user:
            #ignore my messages
            return

        content = message.content
        if (content.startswith("!")):
            #its a command
            await bot.process_commands(message)
            return
        else:
            if "sporting" in message.content:
                await message.add_reaction("😂")
            return

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
