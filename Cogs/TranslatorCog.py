from discord.ext import commands
from googletrans import Translator
import discord
import datetime

class TranslatorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.translator = Translator()

    @commands.command(name = "t", help = "Translates message to target language")
    async def translate(self, ctx, target: str, *text: str):
        if ctx.channel is not None:
            embed = discord.Embed(
                color = 16744587,
                title = target,
                description = self.translator.translate(' '.join(text), dest = target).text,
                timestamp = datetime.datetime.now().astimezone()
            )
            embed.set_footer(text = str(ctx.author), icon_url = ctx.author.avatar_url)
            await ctx.channel.send(embed=embed)
        else:
            print("Oh no")

    @commands.command(name = "d", help = "Detects language of message")
    async def detect(self, ctx, *text):
        if ctx.channel is not None:
            embed = discord.Embed(
                color = 16744587,
                description = self.translator.detect(' '.join(text)).lang,
                timestamp = datetime.datetime.now().astimezone()
            )
            embed.set_footer(text = str(ctx.author), icon_url = ctx.author.avatar_url)
            await ctx.channel.send(embed=embed)
        else:
            print("Oh no")