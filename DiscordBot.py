import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from Cogs.GreetingsCog import GreetingsCog
from Cogs.MemeCog import MemeCog
from Cogs.SignCog import SignCog

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

class MyBot(commands.Bot):
    def __init__(self, prefix):
        super().__init__(command_prefix=prefix)

    async def on_ready(self):
        print(f"{self.user} has connected to Discord!")
    
    async def on_message(self, message):
        if message.author == self.user:
            #ignore my messages
            return

        content = message.content
        if (content.startswith("!")):
            #its a command
            await bot.process_commands(message)
            return
        else:
            return

bot = MyBot("!")
bot.add_cog(GreetingsCog(bot))
bot.add_cog(MemeCog(bot))
bot.add_cog(SignCog(bot))

bot.run(TOKEN)
