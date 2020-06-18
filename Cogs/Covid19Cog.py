from discord.ext import commands
import pycountry
import discord
import datetime
import requests

class Covid19Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="covid19", help="Covid19 stats for designated country")
    async def covid19(self, ctx, country: str = "PT"):
        if ctx.channel is not None:
            countryCodes = pycountry.countries.search_fuzzy(country)
            if len(countryCodes) == 0:
                await ctx.channel.send("Could not find country")
                return
            countryCode = countryCodes[0].alpha_2
            response = requests.get("https://api.thevirustracker.com/free-api?countryTotal={}".format(countryCode)).json()["countrydata"][0]
            embed = discord.Embed(
                color = 16744587,
                title = "COVID19 Stats | {}".format(countryCode),
                timestamp = datetime.datetime.now().astimezone()
            )
            embed.add_field(name = "Confirmed", value = response["total_cases"])
            embed.add_field(name = "New Confirmed", value = response["total_new_cases_today"])
            embed.add_field(name = "\u200b", value = "\u200b") #hack
            embed.add_field(name = "Deaths", value = response["total_deaths"])
            embed.add_field(name = "New Deaths", value = response["total_new_deaths_today"])
            embed.add_field(name = "\u200b", value = "\u200b") #hack
            embed.add_field(name = "Recovered", value = response["total_recovered"])
            embed.add_field(name = "Active", value = response["total_serious_cases"]) # for some reason the api has these values switched up
            embed.add_field(name = "Serious", value = response["total_active_cases"])
            embed.set_footer(text = str(ctx.author), icon_url = ctx.author.avatar_url)
            embed.set_thumbnail(url = "https://www.countryflags.io/{}/flat/64.png".format(countryCode))
            await ctx.channel.send(embed = embed)
        else:
            print("Oh no")
