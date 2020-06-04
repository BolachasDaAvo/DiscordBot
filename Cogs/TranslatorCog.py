from discord.ext import commands
from googletrans import Translator
import random
import datetime

class TranslatorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.translator = Translator()

    @commands.command(name = "t", help = "Translates message to target language")
    async def translate(self, ctx, target: str, *text):
        if ctx.channel is not None:
            message = self.translator.translate(' '.join(text), dest = target).text
            await ctx.channel.send(message)
        else:
            print("Oh no")