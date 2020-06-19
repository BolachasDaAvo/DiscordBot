import discord
import datetime

def simple_embed(author: discord.Member):
    embed = discord.Embed(
        color = 16744587,
        timestamp = datetime.datetime.now().astimezone()
    )
    embed.set_footer(text = str(author), icon_url = author.avatar_url)
    return embed

def embed_with_description(author: discord.Member, description: str):
    embed = simple_embed(author)
    embed.description = description
    return embed

def embed_with_image(author: discord.Member, image: str):
    embed = simple_embed(author)
    embed.set_image(url=image)
    return embed
