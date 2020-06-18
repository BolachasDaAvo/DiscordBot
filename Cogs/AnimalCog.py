from discord.ext import commands
import discord
import requests
from Util import simple_embed

class AnimalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dog")
    async def dog(self, ctx : commands.Context):
        '''
        Random shiba inu
        '''
        if ctx.channel is not None:
            embed = simple_embed(ctx.author)
            embed.set_image(url = requests.get("http://shibe.online/api/shibes").json()[0])
            await ctx.channel.send(embed = embed)
        else:
            print("Oh no")
    
    @commands.command(name="cat")
    async def cat(self, ctx : commands.Context):
        '''
        Random cat
        '''
        if ctx.channel is not None:
            embed = simple_embed(ctx.author)
            embed.set_image(url = requests.get("http://shibe.online/api/cats").json()[0])
            await ctx.channel.send(embed = embed)
        else:
            print("Oh no")

    @commands.command(name="bird")
    async def bird(self, ctx : commands.Context):
        '''
        Random bird
        '''
        if ctx.channel is not None:
            embed = simple_embed(ctx.author)
            embed.set_image(url = requests.get("http://shibe.online/api/birds").json()[0])
            await ctx.channel.send(embed = embed)
        else:
            print("Oh no")

    @commands.command(name="fox")
    async def fox(self, ctx : commands.Context):
        '''
        Random fox
        '''
        if ctx.channel is not None:
            embed = simple_embed(ctx.author)
            embed.set_image(url = requests.get("https://randomfox.ca/floof/").json()["image"])
            await ctx.channel.send(embed = embed)
        else:
            print("Oh no")
