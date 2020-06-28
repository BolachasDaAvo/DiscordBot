from discord.ext import commands
import discord
import datetime
import youtube_dl
import youtube_dl.utils
import asyncio
from async_timeout import timeout
import time
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from Util import *
import traceback
import collections
import functools
import logging
from typing import Union

# youtubedl spams bug messages
youtube_dl.utils.bug_reports_message = lambda: ''


def user_in_voice_channel_check():
    def predicate(ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CheckFailure("Must be in voice channel to use this command")
        return True

    return commands.check(predicate)


def user_in_same_voice_channel_check():
    def predicate(ctx):
        if (not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.channel != ctx.voice_client.channel):
            raise commands.CheckFailure(
                "Must be in bot's voice channel to use this command"
            )
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


class AudioSource:
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "ignoreerrors": False,
        "logtostderr": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "no_color": "True"
    }
    YTdl = youtube_dl.YoutubeDL(options)

    def __init__(self, source: discord.FFmpegOpusAudio, ctx: commands.Context, info: dict):
        self.source = source
        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = info

    def __str__(self):
        try:
            s = "[{}]({}) | [{}]({})".format(
                    self.data["title"],
                    self.data["webpage_url"],
                    self.data["uploader"],
                    self.data["uploader_url"]
                )
        except KeyError:
            s = ""
        finally:
            return s 

    @classmethod
    async def get_audio_source(cls, ctx: commands.Context, search: str, volume: float, loop: asyncio.BaseEventLoop):
        partial = functools.partial(cls.YTdl.extract_info, search, download=False)
        try:
            processedData = await loop.run_in_executor(None, partial)
        except youtube_dl.utils.YoutubeDLError as e:
            raise MusicException(str(e))
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
        return cls(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(audio["url"], before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn"), volume=volume), ctx, audio)


class MusicPlayer:
    def __init__(self, cog, bot, ctx: commands.Context):
        self.bot = bot
        self.cog = cog
        self.voice_client = ctx.voice_client
        self.channel = ctx.channel
        self.guild = ctx.guild
        self.volume = 1.0
        self.now_playing = None
        self.audio_queue = asyncio.Queue()
        self.next_audio = asyncio.Event()
        self.player_task = self.bot.loop.create_task(self.play_audio_task())

    async def play_audio_task(self):
        try:
            while True:
                await self.next_audio.wait()
                self.next_audio.clear()
                try:
                    async with timeout(300):
                        self.now_playing = await self.audio_queue.get()
                except asyncio.TimeoutError:
                    try:
                        await self.channel.send(embed=embed_with_description(self.guild.me, "Leaving due to inactivity..."), delete_after=60)
                    except discord.HTTPException:
                        pass
                    self.bot.loop.create_task(self.cog.cleanup(self.guild.id))
                    return

                self.voice_client.play(self.now_playing.source, after=self.next)
                await self.now_playing.channel.send(
                    embed=embed_with_description(self.now_playing.requester, "Now playing " + str(self.now_playing)),
                    delete_after=self.now_playing.data["duration"]
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.getLogger("discord").exception("Fatal error in pay_audio_task", exc_info=e)
            self.bot.loop.create_task(self.cog.cleanup(self.guild.id))
            await self.channel.send(embed=embed_with_description(self.guild.me, "A fatal error happened and the music player has disconnected.\n The bot owner has been informed. Sorry for the inconvenience"), delete_after=60)

    def next(self, error=None):
        if error:
            raise error
        self.bot.loop.call_soon_threadsafe(self.next_audio.set)

    def set_volume(self, volume: float):
        self.volume = volume
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.source.volume = volume

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
        self.spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())
        self.players = {}

    async def cleanup(self, guild_id: int):
        player = self.players.pop(guild_id, None)
        if player:
            await player.kill()

    def cog_check(self, ctx: commands.Context):
        if (not ctx.guild or not ctx.message or not ctx.channel or not ctx.author or (ctx.author.voice and not ctx.author.voice.channel)):
            logging.getLogger("discord").warning("Failed cog check in MusicCog ctx.guild:{} ctx.message:{} ctx.channel:{} ctx.author:{}".format(ctx.guild, ctx.message, ctx.channel, ctx.author))
            return False
        return True

    def cog_unload(self):
        for key in self.players.keys:
            try:
                self.players[key].cancel()
                self.players[key].stop()
            except Exception:
                pass

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
            player = self.players[ctx.guild.id] = MusicPlayer(self, self.bot, ctx)
            player.voice_client = await destination.connect()
            player.next_audio.set()
            
    @commands.command(name="summon")
    @user_in_voice_channel_check()
    async def summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
        """
        Summons bot to specified voice channel.
        Defaults to user's voice channel, if applicable.
        """
        destination = channel or ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(destination)
        else:
            player = self.players[ctx.guild.id] = MusicPlayer(self, self.bot, ctx)
            player.voice_client = await destination.connect()
            player.next_audio.set()

    @commands.command(name="leave")
    @user_in_same_voice_channel_check()
    @voice_client_check()
    async def leave(self, ctx: commands.Context):
        """
        Leaves voice channel.
        """
        self.bot.loop.create_task(self.cleanup(ctx.guild.id))

    @commands.command(name="play")
    @user_in_voice_channel_check()
    async def play(self, ctx: commands.Context, *, search: str):
        """
        Plays audio. (max 100 songs in queue)
        Will search for audio in various websites if no url is provided. Also supports spotify playlists, albums and tracks (playlist/album size limited to 100 songs). SoundCloud coming SoonTM.
        """
        if not ctx.voice_client:
            await self.join(ctx)
        if ctx.author.voice.channel != ctx.voice_client.channel:
            raise commands.CheckFailure("Must be in bot's voice channel to use this command")
        
        parsed_url = validate_url(search)
        
        #url
        if parsed_url:
            #spotify link
            if parsed_url.netloc == "open.spotify.com":
                #playlist
                if parsed_url.path.startswith("/playlist/"):
                    try:
                        results = self.spotify.playlist_tracks(search)
                    except spotipy.SpotifyException as e:
                        raise commands.CommandError("Unable to queue playlist {}: {}".format(search, e.msg))
                    queued_songs = 0
                    for result in results["items"]:
                        query = result["track"]["name"]
                        for artist in result["track"]["artists"]:
                            query += " " + artist["name"]
                        try:
                            await self.queue_from_youtube(ctx, query, True)
                        except MusicException as e:
                            await notify(ctx, "Unable to queue track {}: {}".format(result["name"], e))
                            continue
                        queued_songs += 1
                    await ctx.send(embed=embed_with_description(ctx.author, "Queued {} songs".format(queued_songs)))     
                #album
                elif parsed_url.path.startswith("/album/"):
                    try:
                        results = self.spotify.album_tracks(search)
                    except spotipy.SpotifyException as e:
                        raise commands.CommandError("Unable to queue album {}: {}".format(search, e.msg))
                    queued_songs = 0
                    for result in results["items"]:
                        query = result["name"]
                        for artist in result["artists"]:
                            query += " " + artist["name"]
                        try:
                            await self.queue_from_youtube(ctx, query, True)
                        except MusicException as e:
                            await notify(ctx, "Unable to queue track {}: {}".format(result["name"], e))
                            continue
                        queued_songs += 1
                    await ctx.send(embed=embed_with_description(ctx.author, "Queued {} songs".format(queued_songs)))
                #track
                elif parsed_url.path.startswith("/track/"):
                    try:
                        result = self.spotify.track(search)
                    except spotipy.SpotifyException as e:
                        raise commands.CommandError("Unable to queue track {}: {}".format(search, e.msg))
                    query = result["name"]
                    for artist in result["artists"]:
                        query += " " + artist["name"]
                    await self.queue_from_youtube(ctx, query)
                else:
                    await self.queue_from_youtube(ctx, search)
            #TODO: soundcloud
            #youtube/other
            else:
                await self.queue_from_youtube(ctx, search)
        #regular youtube search
        else:
            await self.queue_from_youtube(ctx, search)

    async def queue_from_youtube(self, ctx: commands.Context, search: str, no_print: bool = False):
        player = self.players[ctx.guild.id]
        if player.audio_queue.qsize() > 100:
            raise commands.CommandError("Unable to queue song {}: The audio queue is full".format(search))
        try:
            source = await AudioSource.get_audio_source(ctx, search, player.volume, self.bot.loop)
        except MusicException as e:
            raise commands.CommandError("Unable to queue video: {}".format(str(e)))
        await player.audio_queue.put(source)
        if not no_print:
            await ctx.send(
                embed=embed_with_description(ctx.author, "Queued " + str(source))
            )

    @commands.command(name="skip")
    @commands.check_any(playing_check(), paused_check())
    @user_in_same_voice_channel_check()
    @voice_client_check()
    async def skip(self, ctx: commands.Context):
        """
        Skips current audio.    
        """
        ctx.voice_client.stop()
        await ctx.message.add_reaction("⏩")

    @commands.command(name="pause")
    @playing_check()
    @user_in_same_voice_channel_check()
    @voice_client_check()
    async def pause(self, ctx: commands.Context):
        """
        Pauses audio.
        """
        ctx.voice_client.pause()
        await ctx.message.add_reaction("⏸️")

    @commands.command(name="resume")
    @paused_check()
    @user_in_same_voice_channel_check()
    @voice_client_check()
    async def resume(self, ctx: commands.Context):
        """
        Resumes audio.
        """
        ctx.voice_client.resume()
        await ctx.message.add_reaction("▶️")

    @commands.command(name="stop")
    @user_in_same_voice_channel_check()
    @voice_client_check()
    async def stop(self, ctx: commands.Context):
        """
        Stops playing audio and clears the queue.    
        """
        self.players[ctx.guild.id].stop()
        await ctx.message.add_reaction("⏹️")

    @commands.command(name="clear")
    @user_in_same_voice_channel_check()
    @voice_client_check()
    async def clear(self, ctx: commands.Context):
        """
        Clears the queue.
        """
        self.players[ctx.guild.id].clear()
        await ctx.message.add_reaction("🧹")

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

    @commands.command(name="queue")
    @voice_client_check()
    async def queue(self, ctx: commands.Context, entries_per_page: int = 10):
        """
        Displays queue **at the time of invocation**.
        """
        queue = self.players[ctx.guild.id].audio_queue._queue
        pages = []
        page = ""
        index = 1
        entries = entries_per_page
        for audio_source in queue:
            page += "\n{}. {}".format(index, str(audio_source))
            index += 1
            entries -= 1
            if entries <= 0:
                pages += [page]
                page = ""
                entries = entries_per_page
        if entries != entries_per_page:
            pages += [page]
        if index == 1:
            embed = embed_with_description(ctx.author, "Queue is empty")
            await ctx.send(embed=embed)
        else:
            embed = embed_with_title(ctx.author, "Current queue:")
            self.bot.loop.create_task(paginator_task(ctx, embed, pages, ["◀️", "▶️"]))

    @commands.command(name = "delete")
    @user_in_same_voice_channel_check()
    @voice_client_check()
    async def delete(self, ctx: commands.Context, *,  query: Union[int, str]):
        """
        Removes song from queue.
        Accepts:
            * an index
            * the name of the song (deletes every song that contain the provided name)
            * an interval (ex: !delete 1 5 -> deletes songs from index 1 to 5 inclusive)
        """
        queue = self.players[ctx.guild.id].audio_queue._queue
        #index
        if isinstance(query, int):
            index = int(query) - 1
            if index >= len(queue) or index < 0:
                raise commands.CommandError("Index out of range")
            del queue[index]
            await ctx.message.add_reaction("🚮")
            return
        else:
            index = query.split(" ")
            #range
            if len(index) == 2 and is_int(index[0]) and is_int(index[1]):
                index[0] = int(index[0]) - 1 if int(index[0]) - 1 >= 0 else 0
                index[1] = int(index[1]) - 1 if int(index[1]) - 1 < len(queue) else len(queue) - 1
                if index[0] > index[1]:
                    raise commands.CommandError("Invalid range")
                for i in range(index[1], index[0] - 1, -1):
                    del queue[i]
                await ctx.send(embed=embed_with_description(ctx.author, "Deleted {} songs".format(index[1] - index[0] + 1)))
            #string
            else:
                self.players[ctx.guild.id].audio_queue._queue = collections.deque([audio for audio in queue if query.lower() not in audio.data["title"].lower()])
                await ctx.send(embed=embed_with_description(ctx.author, "Deleted {} songs".format(len(queue) - len(self.players[ctx.guild.id].audio_queue._queue))))

    @commands.command(name = "volume")
    @user_in_same_voice_channel_check()
    @voice_client_check()
    async def volume(self, ctx: commands.Context, volume: float):
        """
        Sets player's volume. Argument must be a percentage from 0 to 200.
        Ex: !volume 100 -> sets the volume to 100% 
        """
        if volume < 0:
            raise commands.CommandError("Volume must be greater or equal than 0")
        elif volume > 200:
            raise commands.CommandError("Volume must be less or equal than 200")
        self.players[ctx.guild.id].set_volume(volume / 100)
        await ctx.message.add_reaction("🔊")
