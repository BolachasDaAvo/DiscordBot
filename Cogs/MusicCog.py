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
import collections

# youtubedl spams error messages
youtube_dl.utils.bug_reports_message = lambda: ""


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
        "extractaudio": True,
        "audioformat": "mp3",
        "noplaylist": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "no_color": True
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
    async def get_audio_source(cls, ctx: commands.Context, search: str):
        try:
            processedData = cls.YTdl.extract_info(search, download=False)

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

            return cls(discord.FFmpegPCMAudio(audio["url"], before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn"), ctx, audio)
        except Exception as e:
            print("Caught exception of type {} in get_audio_source: {}".format(repr(e), str(e)))
            raise MusicException(str(e))

#TODO: fix playing message
class AudioPlayer:
    def __init__(self, cog, bot, ctx: commands.Context):
        self.bot = bot
        self.cog = cog
        self.voice_client = ctx.voice_client
        self.channel = ctx.channel
        self.guild = ctx.guild
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
                        audio_source = await self.audio_queue.get()
                except asyncio.TimeoutError:
                    try:
                        await self.channel.send(embed=embed_with_description(self.guild.me, "Leaving due to inactivity..."))
                    except discord.HTTPException:
                        pass
                    self.bot.loop.create_task(self.cog.cleanup(self.guild.id))
                    return

                self.voice_client.play(audio_source.source, after=self.next)
                try:
                    await audio_source.channel.send(
                        embed=embed_with_description(audio_source.requester, "Now playing " + str(audio_source)),
                        delete_after=audio_source.data["duration"]
                    )
                except discord.HTTPException as e:
                    print(str(e))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("Caught exception of type {} in play_audio_task: {}".format(repr(e), str(e)))
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
        self.spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())
        self.players = {}

    async def cleanup(self, guild_id: int):
        player = self.players.pop(guild_id, None)
        if player:
            await player.kill()

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CheckAnyFailure):
            print("ERROR in MusicCog of type {}: {}".format(repr(error), str(error.errors[0])))
            await self.notify(ctx, str(error.errors[0]))
        else:
            print("ERROR in MusicCog of type {}: {}".format(repr(error), str(error)))
            await self.notify(ctx, str(error))

    def cog_check(self, ctx: commands.Context):
        if (not ctx.guild or not ctx.message or not ctx.channel or not ctx.author or (ctx.author.voice and not ctx.author.voice.channel)):
            print("Music Cog check failed.")
            return False
        return True

    def cog_unload(self):
        for key in self.players.keys:
            try:
                self.players[key].cancel()
                self.players[key].stop()
            except Exception:
                pass

    async def notify(self, ctx: commands.Context, description: str):
        await ctx.send(
            embed=embed_with_description(ctx.author, description),
            delete_after=20
        )

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
            player = self.players[ctx.guild.id] = AudioPlayer(self, self.bot, ctx)
            player.voice_client = await destination.connect()
            player.next_audio.set()
            
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
            player = self.players[ctx.guild.id] = AudioPlayer(self, self.bot, ctx)
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
        Plays audio.
        Will search for audio in various websites if no url is provided. Also supports spotify playlists, albums and tracks. SoundCloud coming SoonTM.
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
                        raise commands.CommandError("Unable to queue playlist {}".format(e.msg))
                    queued_songs = 0
                    for result in results["items"]:
                        query = result["track"]["name"]
                        for artist in result["track"]["artists"]:
                            query += " " + artist["name"]
                        try:
                            await self.queue_from_youtube(ctx, query, True)
                        except MusicException as e:
                            await self.notify(ctx, "Unable to queue track {}: {}".format(result["name"], e))
                            continue
                        queued_songs += 1
                    await ctx.send(embed=embed_with_description(ctx.author, "Queued {} songs".format(queued_songs)))     
                #album
                elif parsed_url.path.startswith("/album/"):
                    try:
                        results = self.spotify.album_tracks(search)
                    except spotipy.SpotifyException as e:
                        raise commands.CommandError("Unable to queue album {}".format(e.msg))
                    queued_songs = 0
                    for result in results["items"]:
                        query = result["name"]
                        for artist in result["artists"]:
                            query += " " + artist["name"]
                        try:
                            await self.queue_from_youtube(ctx, query, True)
                        except MusicException as e:
                            await self.notify(ctx, "Unable to queue track {}: {}".format(result["name"], e))
                            continue
                        queued_songs += 1
                    await ctx.send(embed=embed_with_description(ctx.author, "Queued {} songs".format(queued_songs)))
                #track
                elif parsed_url.path.startswith("/track/"):
                    try:
                        result = self.spotify.track(search)
                    except spotipy.SpotifyException as e:
                        raise commands.CommandError("Unable to queue track {}".format(e.msg))
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
        try:
            source = await AudioSource.get_audio_source(ctx, search)
        except MusicException as e:
            raise commands.CommandError(str(e))
        await self.players.get(ctx.guild.id).audio_queue.put(source)
        if not no_print:
            await ctx.send(
                embed=embed_with_description(ctx.author, "Queued " + str(source))
            )

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
        Displays queue **at the time of invocation** (up to 10 songs per page).
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
    async def delete(self, ctx: commands.Context, *,  query: str):
        """
        Removes song from queue.
        Accepts:
            * an index
            * the name of the song (deletes every song that contain the provided name)
            * an interval (ex: !delete 1 5 -> deletes songs from index 1 to 5 inclusive)
        """
        queue = self.players[ctx.guild.id].audio_queue._queue

        #index
        if is_int(query):
            index = int(query) - 1
            if index >= len(queue) or index < 0:
                raise commands.CommandError("Index out of range")
            del queue[index]
            await ctx.message.add_reaction("🚮")
            return
        #range
        indexes = query.split(" ")
        if len(indexes) == 2 and is_int(indexes[0]) and is_int(indexes[1]):
            lower_index = int(indexes[0]) - 1 if int(indexes[0]) - 1 >= 0 else 0
            higher_index = int(indexes[1]) - 1 if int(indexes[1]) - 1 < len(queue) else len(queue) - 1
            if lower_index > higher_index:
                raise commands.CommandError("Invalid range")
            for i in range(higher_index, lower_index - 1, -1):
                del queue[i]
            await ctx.send(embed=embed_with_description(ctx.author, "Deleted {} songs".format(higher_index - lower_index + 1)))
        #string
        else:
            self.players[ctx.guild.id].audio_queue._queue = collections.deque([audio for audio in queue if query.lower() not in audio.data["title"].lower()])
            await ctx.send(embed=embed_with_description(ctx.author, "Deleted {} songs".format(len(queue) - len(self.players[ctx.guild.id].audio_queue._queue))))
