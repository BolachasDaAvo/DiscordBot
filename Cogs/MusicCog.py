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
from Util import *
import traceback

# youtubedl spams error messages
youtube_dl.utils.bug_reports_message = lambda: ''


def user_in_voice_channel_check():
    def predicate(ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CheckFailure(
                "Must be in voice channel to use this command")
        return True
    return commands.check(predicate)


def user_in_same_voice_channel_check():
    def predicate(ctx):
        if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel != ctx.voice_client.channel:
            raise commands.CheckFailure(
                "Must be in bot's voice channel to use this command")
        return True
    return commands.check(predicate)


def voice_client_check():
    def predicate(ctx):
        if not ctx.voice_client:
            raise commands.CheckFailure("Bot not in voice channel.")
        return True
    return commands.check(predicate)


def playing_check():
    def predicate(ctx):
        if not ctx.voice_client.is_playing():
            raise commands.CheckFailure("Bot not playing audio.")
        return True
    return commands.check(predicate)


def paused_check():
    def predicate(ctx):
        if not ctx.voice_client.is_paused():
            raise commands.CheckFailure("No audio paused.")
        return True
    return commands.check(predicate)


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
        try:
            processedData = cls.YTdl.extract_info(search, download=False)

            if not processedData:
                raise MusicException(
                    "Couldn't find anything that matches {}".format(search))

            if "entries" not in processedData:
                audio = processedData
            else:
                audio = None
                for entry in processedData["entries"]:
                    if entry:
                        audio = entry
                        break
                if not audio:
                    raise MusicException(
                        "Couldn't find anything that matches {}".format(search))

            return cls(discord.FFmpegPCMAudio(audio["url"], before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn"), ctx, audio)
        except youtube_dl.DownloadError as e:
            raise MusicException(str(e))
        except youtube_dl.SameFileError as e:
            raise MusicException(str(e))


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
                    async with timeout(5):
                        audio_source = await self.audio_queue.get()
                except asyncio.TimeoutError:
                    await self.channel.send(embed=embed_with_description(self.guild.me, "Leaving due to inactivity..."))
                    self.bot.loop.create_task(self.cog.cleanup(self.guild.id))
                    return

                self.voice_client.play(audio_source.source, after=self.next)
                if self.last_playing_message:
                    await self.last_playing_message.delete()
                self.last_playing_message = await audio_source.channel.send(embed=embed_with_description(audio_source.requester, "Now playing [{}]({}) | [{}]({})".format(
                    audio_source.data["title"], audio_source.data["webpage_url"], audio_source.data["uploader"], audio_source.data["uploader_url"])))
                await self.next_audio.wait()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("Caught exception of type {} in play_audio_task: {}".format(
                repr(e), str(e)))
            traceback.print_exc()

    def next(self, error=None):
        if error:
            raise MusicException(str(error))
        self.bot.loop.call_soon_threadsafe(self.next_audio.set)

    def cancel(self):
        if self.player_task:
            self.player_task.cancel()

    def clear(self):
        while not self.audio_queue.empty():
            self.audio_queue.get_nowait()

    def stop(self):
        self.clear()
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()

    def empty(self):
        return self.audio_queue.empty()

    def shuffle(self):
        random.shuffle(self.audio_queue._queue)

    async def kill(self):
        self.cancel()
        self.stop()
        await self.voice_client.disconnect()


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spotify = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials())
        self.players = {}

    async def cleanup(self, guild_id: int):
        player = self.players.pop(guild_id, None)
        if player:
            await player.kill()

    async def cog_command_error(self, ctx: commands.Context, error):
        print("ERROR in MusicCog of type {}: {}".format(repr(error), str(error)))
        if isinstance(error, commands.CheckAnyFailure):
            await ctx.send(embed=embed_with_description(ctx.author, str(error.errors[0])), delete_after=20)
        else:
            await ctx.send(embed=embed_with_description(ctx.author, str(error)), delete_after=20)

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild or not ctx.message or not ctx.channel or not ctx.author or (ctx.author.voice and not ctx.author.voice.channel):
            print("Failed cog check.")
            return False
        return True

    def cog_unload(self):
        for key in self.players.keys:
            self.players[key].cancel()
            self.players[key].stop()

    @commands.command(name="join")
    @user_in_voice_channel_check()
    async def join(self, ctx: commands.Context):
        """
        Joins user's voice channel.
        """
        destination = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(destination)
        else:
            await destination.connect()
        if not self.players.get(ctx.guild.id):
            self.players[ctx.guild.id] = AudioPlayer(self, self.bot, ctx)

    @commands.command(name="summon")
    async def summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
        """
        Summons bot to specified voice channel.
        Defaults to user's voice channel, if applicable.
        """
        if not ctx.author.voice.channel and not channel:
            raise commands.CommandError("Did not specify a voice channel.")
        destination = channel or ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(destination)
        else:
            await destination.connect()
            if not self.players.get(ctx.guild.id):
                self.players[ctx.guild.id] = AudioPlayer(
                    self, self.bot, ctx)

    @commands.command(name="leave")
    @voice_client_check()
    async def leave(self, ctx: commands.Context):
        """
        Leaves voice channel.
        """
        self.bot.loop.create_task(self.cleanup(ctx.guild.id))

    # TODO: refactor this bad boy
    @commands.command(name="play")
    @user_in_voice_channel_check()
    async def play(self, ctx: commands.Context, *, search: str):
        """
        Plays audio.
        Will search for audio in various websites if no url is provided. Also supports spotify playlists, albums and tracks.
        """
        if not ctx.voice_client:
            await self.join(ctx)
        if ctx.author.voice.channel != ctx.voice_client.channel:
            raise commands.CheckFailure(
                "Must be in bot's voice channel to use this command")
        try:
            sources = []
            if ("open.spotify.com/playlist/" in search):
                # its a spotify playlist
                results = self.spotify.playlist_tracks(search)
                for result in results["items"]:
                    sources += [await AudioSource.get_audio_source(ctx, result["track"]["name"])]
            elif ("open.spotify.com/album/" in search):
                # its a spotify album
                results = self.spotify.album_tracks(search)
                print(results)
            elif ("open.spotify.com/track/" in search):
                # its a spotify track
                results = [self.spotify.track(search)]
                print(results)
            else:
                # just search for it with youtube_dl:
                sources = [await AudioSource.get_audio_source(ctx, search)]
        except MusicException as e:
            raise commands.CommandError(str(e))
        else:
            for source in sources:
                player = self.players.get(ctx.guild.id)
                if not player:
                    player = AudioPlayer(self, self.bot, ctx)
                    self.players[ctx.guild.id] = player
                await player.audio_queue.put(source)
                embed = simple_embed(ctx.author)
                embed.description = "Enqueued [{}]({}) | [{}]({})".format(
                    source.data["title"], source.data["webpage_url"], source.data["uploader"], source.data["uploader_url"])
                await ctx.channel.send(embed=embed)

    @commands.command(name="skip")
    @user_in_same_voice_channel_check()
    @commands.check_any(playing_check(), paused_check())
    @voice_client_check()
    async def skip(self, ctx: commands.Context):
        """
        Skips current audio.    
        """
        ctx.voice_client.stop()
        await ctx.message.add_reaction("⏩")

    @commands.command(name="pause")
    @user_in_same_voice_channel_check()
    @playing_check()
    @voice_client_check()
    async def pause(self, ctx: commands.Context):
        """
        Pauses audio.
        """
        ctx.voice_client.pause()
        await ctx.message.add_reaction("⏸️")

    @commands.command(name="resume")
    @user_in_same_voice_channel_check()
    @paused_check()
    @voice_client_check()
    async def resume(self, ctx: commands.Context):
        """
        Resumes audio.
        """
        ctx.voice_client.resume()
        await ctx.message.add_reaction("▶️")

    @commands.command(name="stop")
    @user_in_same_voice_channel_check()
    @commands.check_any(playing_check(), paused_check())
    @voice_client_check()
    async def stop(self, ctx: commands.Context):
        """
        Stops playing audio and clears the queue.    
        """
        self.players[ctx.guild.id].stop()
        await ctx.message.add_reaction("⏹️")

    @commands.command(name="shuffle")
    @user_in_same_voice_channel_check()
    @voice_client_check()
    async def shuffle(self, ctx: commands.Context):
        """
        Shuffles queue.
        """
        player = self.players[ctx.guild.id]
        if player.empty():
            raise commands.CommandError("Queue is empty.")
        player.shuffle()
        await ctx.message.add_reaction("🔀")
