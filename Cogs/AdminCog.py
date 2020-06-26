from discord.ext import commands
import discord
import datetime


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cleanup")
    @commands.has_permissions(administrator=True)
    async def cleanup(self, ctx, limit: int = 100):
        """
        Checks last <limit> messages and deletes all messages related to bots (either the author was a bot or the message was a bot command).
        May only be used by admins.
        """
        if ctx.channel is not None:
            count = 0
            async for message in ctx.channel.history(limit=limit):
                if message.author.bot or (message.content != "" and not message.content[0].isalnum()):
                    await message.delete()
                    count += 1
            embed = discord.Embed(
                color=16744587,
                timestamp=datetime.datetime.now().astimezone(),
                description="Removed " + str(count) + " messages"
            )
            embed.set_footer(text=str(ctx.author),
                             icon_url=ctx.author.avatar_url)
            await ctx.channel.send(embed=embed, delete_after=20)
        else:
            print("Oh no")
