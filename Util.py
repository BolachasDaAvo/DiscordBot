import discord
from discord.ext import commands
import datetime
import asyncio
import traceback
import logging
from urllib.parse import urlparse


def simple_embed(author: discord.Member):
    embed = discord.Embed(
        color=16744587,
        timestamp=datetime.datetime.now().astimezone()
    )
    embed.set_footer(text=str(author), icon_url=author.avatar_url)
    return embed


def embed_with_description(author: discord.Member, description: str):
    embed = simple_embed(author)
    embed.description = description
    return embed


def embed_with_image(author: discord.Member, image: str):
    embed = simple_embed(author)
    embed.set_image(url=image)
    return embed


def embed_with_title(author: discord.Member, title: str):
    embed = simple_embed(author)
    embed.title = title
    return embed

def embed_with_title_description(author: discord.Member, title: str, description: str):
    embed = embed_with_description(author, description)
    embed.title = title
    return embed

async def paginator_task(ctx: commands.Context, embed: discord.Embed, pages: list, reactions: list, timeout=180):
    try:
        size = len(pages)
        if size == 0:
            return
        index = 0
        embed.description = pages[index] + "\n\npage {} of {}".format(index + 1, size)
        message = await ctx.send(embed=embed)
        for reaction in reactions:
            await message.add_reaction(reaction)

        def check(reaction: discord.Reaction, user: discord.Member):
            return user != ctx.me and message.id == reaction.message.id and str(reaction) in reactions

        while True:
            try:
                reaction, user = await ctx.bot.wait_for("reaction_add", check=check, timeout=timeout)
            except asyncio.TimeoutError:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                finally:
                    return
            await reaction.remove(user)

            # next page
            if str(reaction) == reactions[1]:
                if index + 1 < size:
                    index += 1
                else:
                    continue

            # previous page
            elif str(reaction) == reactions[0]:
                if index - 1 >= 0:
                    index -= 1
                else:
                    continue
            else:
                raise AssertionError("paginator_task reaction if")

            embed.description = pages[index] + "\n\npage {} of {}".format(index + 1, size)
            await message.edit(embed=embed)
    except Exception as e:
        logging.getLogger("discord").exception("Fatal error in paginator_task", exc_info=e)


def validate_url(url: str):
    result = urlparse(url)
    return result if result.scheme != "" and result.netloc != "" else None

def is_int(query: str):
    try:
        int(query)
        return True
    except ValueError:
        return False

async def notify(ctx: commands.Context, message: str):
    await ctx.send(embed=embed_with_description(ctx.author, message), delete_after=60)
