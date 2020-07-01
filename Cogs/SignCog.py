from discord.ext import commands
import random
import datetime

class SignCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lastDate = datetime.date.min
        self.lastMessage = ""

    @commands.command(name = "palavradodia", help = "Perguntar à Karina")
    async def DailyWord(self, ctx):
        if ctx.channel is not None:
            #hardcoded trash
            if self.lastDate is None or self.lastDate < datetime.date.today():
                self.lastDate = datetime.date.today()
                f = open("Resources/DailyWords.txt", "r")
                words = f.readlines()
                f.close()
                f = open("Resources/Signs.txt", "r")
                signs = f.readlines()
                f.close()
                count = 0
                choices = []
                while count < len(signs):
                    choice = random.choice(words)
                    if (choice not in choices):
                        choices += [choice]
                        count += 1
                message = "Palavra do dia:\n"
                for i in range(0, len(signs)):
                    message += "\n" + signs[i][:-1] + ": " + choices[i][:-1]
                self.lastMessage = message
                await ctx.channel.send(self.lastMessage)
            else:
                await ctx.channel.send(self.lastMessage)
        else:
            print("Oh no")