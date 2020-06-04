from discord.ext import commands

class MemeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.memeBank = []

    @commands.command(name = "welp")
    async def welp(self, ctx):
        if ctx.channel is not None:
            await ctx.channel.send("Engrisho?")
        else: 
            print("Oh no")    