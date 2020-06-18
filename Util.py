import discord
import datetime

def simple_embed(author: discord.Member):
    embed = discord.Embed(
        color = 16744587,
        timestamp = datetime.datetime.now().astimezone()
    )
    embed.set_footer(text = str(author), icon_url = author.avatar_url)
    return embed
