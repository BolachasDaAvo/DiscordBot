from discord.ext import commands
from Util import *


class MemeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        if not ctx.channel:
            print("Meme Cog check failed.")
            return False
        return True

    async def cog_command_error(self, ctx, error):
        await ctx.send(embed=embed_with_description(ctx.author, str(error)), delete_after=60)

    @commands.command(name="welp")
    async def welp(self, ctx):
        if ctx.channel is not None:
            await ctx.channel.send("Engrisho?")
        else:
            print("Oh no")
