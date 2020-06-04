from discord.ext import commands

class GreetingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = member.guild.system_channel
        if channel is not None:
            await channel.send("Welcome " + str(member) + " aka " + member.display_name + "!")
        else: 
            print("Oh no")

    @commands.command(name = "hello", help = "Displays simple hello message")
    async def hello(self, ctx):
        if ctx.channel is not None:
            await ctx.channel.send("Hello " + str(ctx.author) + " aka " + ctx.author.display_name + "!")
        else: 
            print("Oh no")

    @commands.command(name = "bye", help = "Displays simple bye message")
    async def bye(self, ctx):
        if ctx.channel is not None:
            await ctx.channel.send("Please leave already...")
        else: 
            print("Oh no")       
