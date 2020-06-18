from discord.ext import commands
import discord
import datetime
import youtube_dl
import asyncio
from async_timeout import timeout
import time
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from Util import simple_embed

#youtubedl spams error messages
youtube_dl.utils.bug_reports_message = lambda: ''

class MusicException(Exception):
    pass

class AudioSource():
    options = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'noplaylist': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
    }
    YTdl = youtube_dl.YoutubeDL(options)

    def __init__(self, source: discord.FFmpegOpusAudio, ctx: commands.Context, info: dict):
        self.source = source
        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = info

    @classmethod
    async def get_audio_source(cls, ctx: commands.Context, search: str):
        processedData = cls.YTdl.extract_info(search, download = False)

        if not processedData:
            raise MusicException("Couldn't find anything that matches {}".format(search))

        if "entries" not in processedData:
            audio = processedData
        else:
            audio = None
            for entry in processedData["entries"]:
                if entry:
                    audio = entry
                    break
            if not audio:
                raise MusicException("Couldn't find anything that matches {}".format(search))

        return cls(discord.FFmpegPCMAudio(audio["url"], before_options= "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options = "-vn"), ctx, audio)

class AudioPlayer():
    def __init__(self, cog, bot, ctx: commands.Context):
        self.bot = bot
        self.cog = cog
        self.voice_client = ctx.voice_client
        self.channel = ctx.channel
        self.guild = ctx.guild
        self.audio_queue = asyncio.Queue()
        self.next_audio = asyncio.Event()
        self.last_playing_message = None
        self.player_task = self.bot.loop.create_task(self.play_audio_task())

    async def play_audio_task(self):
        try:
            while True:
                self.next_audio.clear()
                try:
                    async with timeout(300):
                        audio_source = await self.audio_queue.get()
                except asyncio.TimeoutError:
                    embed = simple_embed(self.guild.me)
                    embed.description = "Leaving due to inactivity..."
                    await self.channel.send(embed = embed)
                    await self.voice_client.disconnect()
                    player = self.cog.players.pop(self.guild.id, None)
                    return

                self.voice_client.play(audio_source.source, after = self.next)
                embed = simple_embed(audio_source.requester)
                embed.description = "Now playing [{}]({}) | [{}]({})".format(audio_source.data["title"], audio_source.data["webpage_url"], audio_source.data["uploader"], audio_source.data["uploader_url"])
                if self.last_playing_message:
                    await self.last_playing_message.delete()
                self.last_playing_message = await audio_source.channel.send(embed = embed)
                await self.next_audio.wait()
        except Exception as e:
            print("Caught exception is play_audio_task: {}".format(str(e)))

    def next(self, error = None):
        if error:
            raise MusicException(str(error))
        self.next_audio.set()

    def cancel(self):
        self.player_task.cancel()

    def clear(self):
        while not self.audio_queue.empty():
            self.audio_queue.get_nowait()
    
    def stop(self):
        self.clear()
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()

    def shuffle(self):
        random.shuffle(self.audio_queue._queue)

    async def kill(self):
        self.cancel()
        self.stop()
        await self.voice_client.disconnect()

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spotify = spotipy.Spotify(client_credentials_manager = SpotifyClientCredentials())
        self.players = {}

    @commands.command(name = "join")
    async def join(self, ctx: commands.Context):
        """
        Joins user's voice channel.
        """
        if ctx.channel:
            if not ctx.author.voice or not ctx.author.voice.channel:
                await ctx.channel.send("Must be in voice channel to use this command")
                return True
            destination = ctx.author.voice.channel
            if ctx.voice_client:
                await ctx.voice_client.move_to(destination)
            else:
                await destination.connect()
            if not self.players.get(ctx.guild.id):
                print("Creating player")
                self.players[ctx.guild.id] = AudioPlayer(self, self.bot, ctx)
            return False
        else:
            print("Channel is None")
            return False

    @commands.command(name = "summon")
    async def summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
        """
        Summons bot to specified voice channel.
        Defaults to user's voice channel, if applicable.
        """
        if ctx.channel:
            if (not ctx.author.voice and not channel) or (ctx.author.voice and (not ctx.author.voice.channel and not channel)):
                await ctx.channel.send("Did not specify a voice channel and user is not in a voice channel")
                return
            destination = channel or ctx.author.voice.channel
            if ctx.voice_client:
                await ctx.voice_client.move_to(destination)
            else:
                await destination.connect()
                if not self.players.get(ctx.guild.id):
                    self.players[ctx.guild.id] = AudioPlayer(self, self.bot, ctx)
        else:
            print("Channel is None")
        
    @commands.command(name = "leave")
    async def leave(self, ctx: commands.Context):
        """
        Leaves voice channel.    
        """
        if ctx.channel:
            if not ctx.voice_client:
                await ctx.channel.send("Bot not connected to any voice channel.")
                return
            player = self.players.pop(ctx.guild.id, None)
            await player.kill()
        else:
            print("Channel is None")

    @commands.command(name = "play")
    async def play(self, ctx: commands.Context, *, search : str):
        """
        Plays audio.
        Will search for audio in various websites if no url is provided.
        """
        if ctx.channel:
            if not ctx.voice_client:
                if await self.join(ctx):
                    return
            try:
                sources = []
                if ("open.spotify.com/playlist/" in search):
                    #its a spotify playlist
                    results = self.spotify.playlist_tracks(search)
                    for result in results["items"]:
                        sources += [await AudioSource.get_audio_source(ctx, result["track"]["name"])]
                elif ("open.spotify.com/album/" in search):
                    #its a spotify album
                    results = self.spotify.album_tracks(search)
                    print(results)
                elif ("open.spotify.com/track/" in search):
                    #its a spotify track
                    results = [self.spotify.track(search)]
                    print(results)
                else:
                    #just search for it with youtube_dl:
                    sources = [await AudioSource.get_audio_source(ctx, search)]
            except MusicException as e:
                await ctx.channel.send("Error: {}".format(str(e)))
                return
            else:
                for source in sources:
                    player = self.players.get(ctx.guild.id)
                    if not player:
                        player = AudioPlayer(self, self.bot, ctx)
                        self.players[ctx.guild.id] = player
                    await player.audio_queue.put(source)
                    embed = simple_embed(ctx.author)
                    embed.description = "Enqueued [{}]({}) | [{}]({})".format(source.data["title"], source.data["webpage_url"], source.data["uploader"], source.data["uploader_url"])
                    await ctx.channel.send(embed = embed)
        else:
            print("Channel is None")

    @commands.command(name = "skip")
    async def skip(self, ctx: commands.Context):
        """
        Skips current audio.    
        """
        if ctx.channel:
            if ctx.voice_client and ctx.voice_client.is_playing():
                ctx.voice_client.stop()
                await ctx.message.add_reaction("⏩")
        else:
            print("Channel is None")

    @commands.command(name = "pause")
    async def pause(self, ctx: commands.Context):
        """
        Pauses audio.
        """
        if ctx.channel:
            if ctx.voice_client and ctx.voice_client.is_playing():
                ctx.voice_client.pause()
                await ctx.message.add_reaction("⏸️")
        else:
            print("Channel is None")

    @commands.command(name = "resume")
    async def resume(self, ctx: commands.Context):
        """
        Resumes audio.    
        """
        if ctx.channel:
            if ctx.voice_client and ctx.voice_client.is_paused():
                ctx.voice_client.resume()
                await ctx.message.add_reaction("▶️")
        else:
            print("Channel is None")

    @commands.command(name = "stop")
    async def stop(self, ctx: commands.Context):
        """
        Stops playing audio and clears the queue.    
        """
        if ctx.channel:
            if ctx.voice_client:
                self.players[ctx.guild.id].stop()
                await ctx.message.add_reaction("⏹️")
        else:
            print("Channel is None")

    @commands.command(name = "shuffle")
    async def shuffle(self, ctx: commands.Context):
        """
        Shuffles queue.    
        """
        if ctx.channel:
            if ctx.voice_client:
                self.players[ctx.guild.id].shuffle()
                await ctx.message.add_reaction("🔀")
        else:
            print("Channel is None")
