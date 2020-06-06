from discord.ext import commands
from pyowm.owm import OWM
import pycountry
import discord
import datetime

class WeatherCog(commands.Cog):
    def __init__(self, bot, key):
        self.bot = bot
        owm = OWM(key)
        self.weatherManager = owm.weather_manager()
        self.registry = owm.city_id_registry()

    @commands.command(name="weather", help="Forecast for designated location")
    async def weather(self, ctx, location: str, country: str):
        if ctx.channel is not None:
            countryCodes = pycountry.countries.search_fuzzy(country)
            if len(countryCodes) == 0:
                await ctx.channel.send("Could not find country")
                return
            countryCode = countryCodes[0].alpha_2
            coords = self.registry.locations_for(location, country = countryCode)
            if len(coords) == 0:
                await ctx.channel.send("Location not found")
                return
            forecasts = self.weatherManager.one_call(
                coords[0].lat, coords[0].lon).forecast_daily
            message = "```"
            message += "{:^12s}{:^10s}{:^13s}{:^13s}\n".format(
                "Day",
                "Status",
                "Min Temp(ºC)", 
                "Max Temp(ºC)"
            )
            for forecast in forecasts:
                message += "{:^12s}{:^10s}{:^13}{:^13.2f}\n".format(
                    forecast.reference_time('iso').split(' ')[0], 
                    forecast.status, 
                    forecast.temperature("celsius")["min"],
                    forecast.temperature("celsius")["max"]
                )
            message += "```"
            embed = discord.Embed(
                color = 16744587,
                title = "Forecast at {}, {}".format(location, country),
                description = message,
                timestamp = datetime.datetime.now().astimezone()
            )
            embed.set_footer(text = str(ctx.author), icon_url = ctx.author.avatar_url)
            embed.set_thumbnail(url = "https://www.countryflags.io/{}/flat/64.png".format(countryCode))
            await ctx.channel.send(embed = embed)
        else:
            print("Oh no")
