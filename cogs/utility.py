import discord
from discord.ext import commands
import cv2
import pyqrcode
from bs4 import BeautifulSoup
import requests
import flags
from translate import Translator
from itertools import cycle
import cse
import os
google_api_1 = os.getenv("google_api_1")
google_api_2 = os.getenv("google_api_2")
google_api_3 = os.getenv("google_api_3")
from contextlib import suppress
from menus import menus
import typing
import json
from utils import fuzzy
import zlib
import io
import re
from pyfiglet import Figlet
import ast
import decimal
import aiohttp
import humanize
from typing import Optional
from collections import Counter
from utils.format import plural
from currency_converter import CurrencyConverter
from utils.asyncstuff import asyncexe
from twemoji_parser import emoji_to_url
from PIL import Image, ImageFont
from io import BytesIO
from jishaku.paginators import PaginatorInterface, PaginatorEmbedInterface
from datetime import datetime
import base64
import unicodedata
import numpy as np
import random as rng


class googlemenu(menus.Menu):
    def __init__(self, *args, **kwargs):
        self.counter = 0
        self.safe_search = kwargs.pop("safe_search")
        self.datas = kwargs.pop("datas")
        super().__init__(*args, **kwargs)

    async def send_initial_message(self, ctx, channel):
        embed = discord.Embed(
            color=self.bot.color,
            title=self.datas[self.counter].title,
            description=
            f"{self.datas[self.counter].snippet or ''}\n{self.datas[self.counter].link}"
        )
        # if self.datas[self.counter].image != None and self.datas[self.counter].image.startswith("http"):
        #   embed.set_image(url=self.datas[self.counter].image)
        embed.set_footer(
            text=
            f"Page: {self.counter + 1}/{len(self.datas)} Safe Search: {self.safe_search}"
        )
        return await channel.send(embed=embed)

    @menus.button('\U000025c0')
    async def on_left(self, payload):
        if self.counter == 0:
            return
        self.counter -= 1
        embed = discord.Embed(
            color=self.bot.color,
            title=self.datas[self.counter].title,
            description=
            f"{self.datas[self.counter].snippet or ''}\n{self.datas[self.counter].link}"
        )
        # if self.datas[self.counter].image != None and self.datas[self.counter].image.startswith("http"):
        #   embed.set_image(url=self.datas[self.counter].image)
        embed.set_footer(
            text=
            f"Page: {self.counter + 1}/{len(self.datas)} Safe Search: {self.safe_search}"
        )
        await self.message.edit(embed=embed)

    @menus.button('\U000025b6')
    async def on_right(self, payload):
        if self.counter == len(self.datas) - 1:
            return
        self.counter += 1
        embed = discord.Embed(
            color=self.bot.color,
            title=self.datas[self.counter].title,
            description=
            f"{self.datas[self.counter].snippet or ''}\n{self.datas[self.counter].link}"
        )
        # if self.datas[self.counter].image != None and self.datas[self.counter].image.startswith("http"):             embed.set_image(url=self.datas[self.counter].image)
        embed.set_footer(
            text=
            f"Page: {self.counter + 1}/{len(self.datas)} Safe Search: {self.safe_search}"
        )
        await self.message.edit(embed=embed)

    @menus.button('\N{BLACK SQUARE FOR STOP}\ufe0f')
    async def on_stop(self, payload):
        self.stop()


class Transformer(ast.NodeTransformer):
    ALLOWED_NAMES = set(['Decimal', 'None', 'False', 'True'])
    ALLOWED_NODE_TYPES = set([
        'Expression', 'Int', 'Float', 'Call', 'UnaryOp', 'Not', 'Invert',
        'UAdd', 'USub', 'Compare', 'Eq', 'Num', 'Constant', 'BinOp', 'Add',
        'Div', 'FloorDiv', 'Sub', 'Mult', 'BitXor', 'op', 'Pow', 'Mod'
    ])

    def visit_Name(self, node):
        if node.id not in self.ALLOWED_NAMES:
            raise RuntimeError(f"Access denied for {node.id}")

        return self.generic_visit(node)

    def generic_visit(self, node):
        nodetype = type(node).__name__
        if nodetype not in self.ALLOWED_NODE_TYPES:
            raise RuntimeError(f"Access denied for {nodetype}")
        return ast.NodeTransformer.generic_visit(self, node)


transformer = Transformer()


class nogooderror(Exception):
    pass


class SphinxObjectFileReader:
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')


class utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        page_types = {
            'latest': 'https://discordpy.readthedocs.io/en/latest',
            'python': 'https://docs.python.org/3',
            'asyncpg': "https://magicstack.github.io/asyncpg/current/",
            "zaneapi": "https://docs.zaneapi.com/en/latest/",
            "aiohttp": "https://docs.aiohttp.org/en/stable/"
        }
        bot.loop.create_task(
            self.build_rtfm_lookup_table(page_types=page_types))
        bot.cse1 = cse.Search(api_key=google_api_1)
        bot.cse2 = cse.Search(api_key=google_api_2)
        bot.cse3 = cse.Search(api_key=google_api_3)
        bot.cse_lists = cycle([bot.cse1, bot.cse2, bot.cse3])

    def parse_object_inv(self, stream, url):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != '# Sphinx inventory version 2':
            raise RuntimeError('Invalid objects.inv file version.')

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        version = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if 'zlib' not in line:
            raise RuntimeError(
                'Invalid objects.inv file, not z-lib compatible.')

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(
            r'(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)')
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(':')
            if directive == 'py:module' and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == 'std:doc':
                subdirective = 'label'

            if location.endswith('$'):
                location = location[:-1] + name

            key = name if dispname == '-' else dispname
            prefix = f'{subdirective}:' if domain == 'std' else ''

            if projname == 'discord.py':
                key = key.replace('discord.ext.commands.',
                                  '').replace('discord.', '')

            result[f'{prefix}{key}'] = os.path.join(url, location)

        return result

    async def build_rtfm_lookup_table(self, page_types):
        cache = {}
        for key, page in page_types.items():
            sub = cache[key] = {}
            async with self.bot.session.get(page + '/objects.inv') as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        'Cannot build rtfm lookup table, try again later.')

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self.bot._rtfm_cache = cache

    async def uhh_rtfm_pls(self, ctx, key, obj):
        page_types = {
            'latest': 'https://discordpy.readthedocs.io/en/latest',
            'python': 'https://docs.python.org/3',
            'asyncpg': "https://magicstack.github.io/asyncpg/current/",
            "zaneapi": "https://docs.zaneapi.com/en/latest/",
            "aiohttp": "https://docs.aiohttp.org/en/stable/"
        }
        if obj is None:
            await ctx.send(page_types[key])
            return

        if not hasattr(self.bot, "_rtfm_cache"):
            await ctx.trigger_typing()
            await self.build_rtfm_lookup_table(page_types)

        obj = re.sub(r'^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)', r'\1',
                     obj)

        if key.startswith('latest'):
            # point the abc.Messageable types properly:
            q = obj.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == '_':
                    continue
                if q == name:
                    obj = f'abc.Messageable.{name}'
                    break

        cache = list(self.bot._rtfm_cache[key].items())

        def transform(tup):
            return tup[0]

        matches = fuzzy.finder(obj, cache, key=lambda t: t[0], lazy=False)[:10]

        e = discord.Embed(colour=0x00ff6a)
        if len(matches) == 0:
            return await ctx.send("Can't find anything")

        e.description = '\n'.join(f'[{key}]({url})' for key, url in matches)
        await ctx.send(embed=e, reference=ctx.replied_reference)

    @staticmethod
    def choosebstofcal(ctx, times, choices):

        if times is None:
            times = (len(choices)**2) + 1
        times = min(1000000, max(1, times))
        results = Counter(np.random.choice(choices, times))
        builder = []
        if len(results) > 30:
            builder.append('Showing the top 30 results')
        for index, (elem, count) in enumerate(results.most_common(30),
                                              start=1):
            builder.append(
                f'**{index}. {elem} ** `({plural(count):time}, {count/times:.2%})`'
            )
        return builder

    @staticmethod
    def convertcal(amount, from_, to):
        c = CurrencyConverter(decimal=True)
        try:
            final = c.convert(amount, from_.upper(), to.upper())
            return True, final
        except Exception as e:
            return False, e

    @staticmethod
    @asyncexe()
    def emojiinfo_():
        im = Image.new("RGBA", (100, 100), color=(0, 0, 0, 0))
        font = ImageFont.truetype("lexiereadable-bold.ttf", 30)
        return im, font

    async def get_incidents(self):
        lists = []
        async with self.bot.session.get(
                "https://srhpyqt94yxb.statuspage.io/api/v2/incidents.json"
        ) as resp:
            r = await resp.json()
            for i in r["incidents"]:
                name = i["name"]
                status = i["status"]
                lists.append(f"{name}: {status}")
        return lists


    async def get_status(self):
        lists = []
        async with self.bot.session.get(
                "https://srhpyqt94yxb.statuspage.io/api/v2/components.json"
        ) as resp:
            r = await resp.json()
            for i in r["components"]:
                name = i["name"]
                status = i["status"]
                lists.append(f"{name}: {status}")
        return lists

    # lists = ["assert", "class", "as", "lambda", "\\", "()", "while", "int", "float", "str", "aiohttp", "utility", "cog", "main", "py"]
    #   if "bot" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   if thing in lists:
    #     return await ctx.send("nope don't even think about it")
    #   elif len(thing) > 1000:
    #     return await ctx.send("too long")
    #   elif ".." in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "ellipsis" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "in" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "local" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "global" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "raw" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "ord" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "\'" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "\"" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "while" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "yield" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "async" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "=" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "return" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "raise" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "()" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "discord" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "__" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "foo" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "import" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "env" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "process" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "os" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "sys" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "self" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "eval" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "exec" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "await" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "print" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "ctx" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "token" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "http" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   elif "connection" in thing:
    #     return await ctx.send("nope don't even think about it")
    #   # elif "^" in thing:
    #   #   return await ctx.send("power not supported for now ")
    #   # elif "**" in thing:
    #   #   return await ctx.send("power not supported for now ")
    #   # elif "* *" in thing:
    #   #   return await ctx.send("power not supported for now ")
    #   else:
    @staticmethod
    @asyncexe()
    def translate_(from_lang, to_lang, thing):
        return Translator(from_lang=from_lang,
                          to_lang=to_lang).translate(thing)

    @commands.command()
    async def ip(self, ctx, ip):
        async with self.bot.session.get("https://api.ksoft.si/kumo/geoip", headers = {"Authorization": os.getenv("ksoft")}, params = {"ip": ip}) as resp:
            res = await resp.json()
            if res.get("message"):
                return await ctx.send(res.get("message"))
            res.get("data").pop("apis")
            await ctx.send(f"```json\n{json.dumps(res, indent=4)}\n```")
    
    @commands.command()
    async def pypi(self, ctx, name):
        async with self.bot.session.get(f"https://pypi.org/pypi/{name}/json") as resp:
            if resp.status == 404:
                return await ctx.send(f"We are unable to find that package")
            package = await resp.json()
            package = package["info"]
            Author = f"""
            **Author:** {package.get('author') or "None"}
            **Author email:** {package["author_email"] or "None"}
            """
            Package = f"""
            **Homepage:** {package.get("home_page") or "None"}
            **License:** {package.get("license") or "None"}
            **Version:** {package.get("version") or "None"}
            **Keywords:** {package.get("keywords") or "None"}
            **Documentation:** {package.get("project_urls").get("Documentation") or "None"}
            """
            embed = discord.Embed(color=self.bot.color, title=package["name"], url=package["package_url"], description=package["summary"])
            embed.set_thumbnail(url="https://i.imgur.com/8EI9rk0.png")
            embed.add_field(name="Package", value=Package, inline=False)
            embed.add_field(name="Author", value=Author, inline=False)
            await ctx.send(embed=embed)
    @commands.group(invoke_without_command=True)
    async def qrcode(self, ctx, *, thing):
        q = pyqrcode.create(thing)
        pic = BytesIO()
        q.png(pic, scale=6)
        pic.seek(0)
        await ctx.send(file=discord.File(pic, "qrcode.png"))
    @qrcode.command(name="decode")
    async def qrcode_decode(self, ctx, *, link):
        if link.startswith("https"):
            async with self.bot.session.get(link) as resp:
                byte_ = await resp.read()
                byte_ = base64.b64decode
                pic = np.frombuffer(byte_, dtype=np.uint8)
                img = cv2.imread(pic, flags=1)
                detector = cv2.QRCodeDetector()
                data, bbox, straight_qrcode = detector.detectAndDecode(img)
                await ctx.send(data)
                # qr = decode(pic)
                # await ctx.send(qr.data)
    @staticmethod
    @asyncexe()
    def txt_(thing):
        return discord.File(BytesIO(thing.encode("utf-8")), "something.txt")
    @commands.command()
    async def txt(self, ctx, *, anything:str=None):
        if anything.startswith("https://mystb.in/"):
            return await ctx.send(file=await self.txt_(str(await self.bot.mystbin.get(anything))))
        await ctx.send(file=await self.txt_(anything))

    @commands.command()
    async def mystbin(self, ctx, *, code:str=None):
        if ctx.message.reference:
            if ctx.message.reference.cached_message:
                if (
                    ctx.message.reference.cached_message.attachments
                    and ctx.message.reference.cached_message.attachments[
                        0
                    ].filename.endswith((".txt", ".py", ".json", ".html", ".csv"))
                ):
                    message = await ctx.message.reference.cached_message.attachments[0].read()
                    message = message.decode("utf-8")
                    return await ctx.send(str(await self.bot.mystbin.post(message, syntax=ctx.message.reference.cached_message.attachments[0].filename.split(".")[1])))
            else:
                message = await self.bot.get_channel(ctx.message.reference.channel_id).fetch_message(ctx.message.reference.message_id)
                if message.attachments and message.attachments.filename.endswith(
                    (".txt", ".py", ".json", ".html", ".csv")
                ):
                    message_ = await message.attachments[0].read()
                    message_ = message_.decode("utf-8")
                    return await ctx.send(str(await self.bot.mystbin.post(message_, syntax=message.attachments[0].filename.split(".")[1])))




        if code is None:
            message = ctx.message.attachments[0]
            if message:
                syntax = message.filename.split(".")[1]
                if message.filename.endswith((".txt", ".py", ".json", ".html", ".csv")):
                    message = await message.read()
                    message = message.decode("utf-8")
                    await ctx.send(str(await self.bot.mystbin.post(message, syntax=syntax)))
        else:
            if code.startswith("http"):
                async with self.bot.session.get(code) as resp:
                    message = await resp.read()
                    try:
                        message = message.decode("utf-8")
                        return await ctx.send(str(await self.bot.mystbin.post(message, syntax="html")))
                    except:

                        message = f"Unable to decode so here is the byte {message}"
                        return await ctx.send(str(await self.bot.mystbin.post(message, syntax="python")))
            await ctx.send(str(await self.bot.mystbin.post(code)))

    @staticmethod
    @asyncexe()
    def redirectcheck_(website):
        return requests.get(website).url

    @commands.command()
    async def replacespace(self, ctx, emoji, *, thing):
        await ctx.send(thing.replace(" ", emoji))

    @commands.command()
    async def redirectcheck(self, ctx, *, website):
        website = website.strip("<>")
        async with self.bot.session.get(website) as resp:
            soup = BeautifulSoup(await resp.text(), features="lxml")
            canonical = soup.find('link', {'rel': 'canonical'})
            if canonical is None:
                return await ctx.send(f"`{resp.real_url}`")
            await ctx.send(f"`{canonical['href']}`")

    @commands.command()
    async def mytime(self, ctx):
        embed = discord.Embed(color=self.bot.color,
                              timestamp=datetime.utcnow())
        await ctx.send(embed=embed)

    @commands.command()
    async def translate(self, ctx, from_lang, to_lang, *, thing):
        """
        put " " between your word if you are translating only one word
    Translate text languages are in ISO 639-1 you may google to find the right language code or find them here https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes
    """
        await ctx.send(await self.translate_(from_lang, to_lang, thing))

    @staticmethod
    async def google_(self, thing, ctx):
        return await next(self.bot.cse_lists
                          ).search(thing,
                                   safe_search=not ctx.channel.is_nsfw())

    @commands.command()
    async def google(self, ctx, *, thing: str):
        results = await self.google_(self, thing, ctx)
        m = googlemenu(datas=results, safe_search=not ctx.channel.is_nsfw())
        await m.start(ctx)
        # paginator = commands.Paginator(prefix="", suffix="", max_size=500)
        # embed=discord.Embed(color=self.bot.color)
        # for i in results:
        #   paginator.add_line(i)
        # interface = PaginatorEmbedInterface(ctx.bot, paginator, owner=ctx.author, embed=embed)
        # await interface.send_to(ctx)

    @commands.command()
    async def make_embed(self, ctx, *, thing: json.loads):
        """
    Make a embed from json. Link to make it https://leovoel.github.io/embed-visualizer/
    """
        try:
            await ctx.send(embed=discord.Embed().from_dict(thing))
        except Exception as e:
            raise commands.CommandError(e)

    @commands.group(invoke_without_command=True,
                    aliases=[
                        "read_the_fucking_manual", "rtfd",
                        "read_the_fucking_doc", "read_tfm", "read_tfd"
                    ])
    async def rtfm(self, ctx, *, thing: str = None):
        """
    Get the link to the discord.py's manual or python's manual
    """
        await self.uhh_rtfm_pls(ctx, "latest", thing)

    @rtfm.command(name="py", aliases=["python"])
    async def rtfm_py(self, ctx, *, thing: str = None):
        await self.uhh_rtfm_pls(ctx, "python", thing)

    @rtfm.command(name="asyncpg", aliases=["apg"])
    async def rtfm_asyncpg(self, ctx, *, thing: str = None):
        await self.uhh_rtfm_pls(ctx, "asyncpg", thing)

    @rtfm.command(name="zaneapi")
    async def rtfm_zaneapi(self, ctx, *, thing: str = None):
        await self.uhh_rtfm_pls(ctx, "zaneapi", thing)

    @rtfm.command(name="aiohttp")
    async def rtfm_aiohttp(self, ctx, *, thing: str = None):
        await self.uhh_rtfm_pls(ctx, "aiohttp", thing)

    @commands.command(aliases=["fm"])
    async def firstmsg(self, ctx, *, channel: discord.TextChannel = None):
        """
    The first message send in that channel
    """
        if channel is None:
            channel = ctx.channel
        msg = await channel.history(around=channel.created_at,
                                    oldest_first=True,
                                    limit=10).flatten()
        msg = msg[0]
        embed = discord.Embed(color=self.bot.color, timestamp=msg.created_at)
        embed.set_author(name=msg.author, icon_url=str(msg.author.avatar_url))
        embed.set_footer(text=f"id: {msg.id} Created at: ")
        if msg.embeds != []:
            content = "Embed"
        elif msg.attachments != []:
            content = "Attachment"
        else:
            content = msg.content
        embed.add_field(name="Content", value=content, inline=False)
        embed.add_field(name="Jump link",
                        value=f"[url]({msg.jump_url})",
                        inline=False)
        await ctx.send(embed=embed)
        if msg.attachments != []:
            await ctx.send(msg.attachments[0].url)
        if msg.embeds != []:
            await ctx.send(embed=msg.embeds[0])

    @commands.command()
    async def art(self, ctx, *, thing: str):
        """
    transform your text into ascii art
    """
        f = Figlet(font='standard')
        await ctx.send(f"```css\n{f.renderText(thing)}\n```")

    @staticmethod
    def calc(thing):
        try:
            tree = ast.parse(thing, mode='eval')
            transformer.visit(tree)
            clause = compile(tree, '<AST>', 'eval')
            return eval(clause, dict(Decimal=decimal.Decimal))
        except OverflowError as e:
            raise e
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise e

    @commands.command()
    async def math(self, ctx, *, thing: str):
        """
      Calculate some math
      """
        thing = thing.replace(" ", "").replace("^", "**")
        lists = ["\"", "\'", "()", ".."]
        if any(i in thing for i in lists):
            return await ctx.send("nope don't even think about it")
        if "*" in thing and "/" in thing:
            return await ctx.send("nope don't even think about it")
        if "**" in thing:
            return await ctx.send("Power not supported")
        result = str(await
                     self.bot.loop.run_in_executor(None, self.calc, thing))
        if "None" in result:
            raise RuntimeError("Access denied")
        if "Ellipsis" in result:
            raise RuntimeError("Access denied")
        if len(result) > 1068:
            await ctx.send(str(await self.bot.mystbin.post(result)))
        else:
            await ctx.send(result)

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def auditlog(self, ctx, limit=100, *, datatype=None):
        """
    Shows you the audit logs actions
    The max limit of it is 5000
    Avaible datatype: guild_update, channel_create, channel_update, channel_delete, etc. There are a tons of datatype is hmm hard to list them all here. List of datatypes: https://discordpy.readthedocs.io/en/latest/api.html#discord.AuditLogAction
    """
        limit = min(limit, 5000)
        if datatype is None:
            entries = await ctx.guild.audit_logs(limit=limit).flatten()
        else:
            entries = await ctx.guild.audit_logs(limit=limit,
                                                 action=getattr(
                                                     discord.AuditLogAction,
                                                     datatype)).flatten()
        paginator = commands.Paginator(max_size=1000)
        lists = [
            f"Action: {i.action}\nExtra info: {i.extra}\nBefore: {i.before}\nAfter: {i.after}\nDone by: {i.user}\nTime: {i.created_at}\nReason: {i.reason}\nTarget: {i.target}\n"
            for i in entries
        ]

        for i in lists:
            paginator.add_line(i)
        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        await interface.send_to(ctx)

    @commands.command()
    async def discordincidents(self, ctx):
        """
    Shows discord's incidents
    """
        paginator = commands.Paginator(max_size=500,
                                       prefix='```yaml',
                                       suffix='```')
        for i in await self.get_incidents():
            paginator.add_line(f"{i}\n")
        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        await interface.send_to(ctx)

    @commands.command()
    async def discordstatus(self, ctx):
        """
    Shows discord's status
    """
        paginator = commands.Paginator(max_size=500,
                                       prefix='```yaml',
                                       suffix='```')
        for i in await self.get_status():
            paginator.add_line(i)
        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        await interface.send_to(ctx)

    @commands.command()
    async def emojiinfo(self, ctx, *, emoji):
        """
    Shows emoji info
    """
        emoji = emoji.replace("\U0000fe0f", "")
        emoji = emoji.replace("\\", "")
        # im, font = await self.emojiinfo_()
        # parser = TwemojiParser(im, parse_discord_emoji=True)
        # await parser.draw_text((0, 0), emoji, font=font, fill=(0, 0, 0))
        # await parser.close()
        # obj = BytesIO()
        # im.save(obj, "PNG")
        # obj.seek(0)
        # file = discord.File(fp=obj, filename="emoji.png")
        # await ctx.send(file=file)
        try:
            partialemoji = await commands.PartialEmojiConverter().convert(ctx, emoji)
            if partialemoji.is_custom_emoji() == True:
                asset = partialemoji.url
                link = str(asset)
                embed = discord.Embed(color=self.bot.color,
                                      title=partialemoji.name, description=f"`{str(partialemoji)}`\nCustom Emoji")
                embed.set_image(url=link)
            else:
                emoji_link = await emoji_to_url(emoji)
                embed = discord.Embed(color=self.bot.color,
                                      title=unicodedata.name(
                                          emoji, "Can not find emoji\'s name"), description="Unicode emoji/Discord Emoji")
                embed.set_image(url=emoji_link)
            await ctx.send(embed=embed)
        except:
            emoji_link = await emoji_to_url(emoji)
            embed = discord.Embed(color=self.bot.color,
                                  title=unicodedata.name(
                                      emoji, "Can not find emoji\'s name"), description="Unicode emoji/Discord Emoji")
            embed.set_image(url=emoji_link)
            await ctx.send(embed=embed)

    @commands.command()
    async def parsetoken(self, ctx, token: str):
        """
    Parse a discord token
    """
        counter = token.count(".")
        if counter != 2:
            return await ctx.reply("Enter a valid token")
        TOKEN = token.split(".")
        id_ = base64.b64decode(TOKEN[0]).decode("utf-8")
        bytes_int = base64.standard_b64decode(TOKEN[1] + "==")
        unix = int.from_bytes(bytes_int, "big")
        timestamp = datetime.utcfromtimestamp(unix + 1293840000)
        name = await self.bot.get_user(id_)
        await ctx.reply(f"Bot: {name}\nToken created at: {timestamp}")

    # @commands.command()
    # async def wordcloud(self, ctx):
    #   f = open("channeltext.txt", "a")
    #   async for message in ctx.channel.history(limit=10), open("channeltext.txt", "a") as file:
    #     file.write(f" {message.content}")
    #   text = open("channeltext.txt", "r").read()
    #   wordcloud_ = WordCloud.generate(self=self, text=text)
    #   image = wordcloud_.to_image()
    #   buffer = BytesIO()
    #   image.save(buffer, "png")
    #   await ctx.send(file=discord.File(fp=buffer, filename="wordcloud.png"))

    @commands.command()
    async def convert(self, ctx, amount: float, from_: lambda x: str(x).upper(), to: lambda x: str(x).upper()):
        """
    Convert from one currency to another. Currency code are listed here https://en.wikipedia.org/wiki/ISO_4217#Active_codes
    """
        async with self.bot.session.get("https://api.ksoft.si/kumo/currency", headers = {"Authorization": os.getenv("ksoft")}, params = {"from": from_, "to": to, "value": amount}) as resp:
            res = await resp.json()
            if res.get("message"):
                return await ctx.send(res.get("message"))
            await ctx.send(f"{amount} {from_.upper()} is equal to {res.get('pretty')}")
    @commands.command()
    async def charinfo(self, ctx, *, characters: str):
        """Shows you information about a number of characters.
        No more then 25 characters at a time.
        """
        def to_string(c):
            digit = f'{ord(c):x}'
            name = unicodedata.name(c, 'Can not find')
            return f'`\\U{digit:>08}`= {name}'

        # msg = '\n'.join(map(to_string, characters))
        msg = map(to_string, characters)
        paginator = commands.Paginator(max_size=500)
        for i in msg:
            i = str(i)
            paginator.add_line(i)
        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        await interface.send_to(ctx)

    @commands.command(aliases=["guildinfo", "gi", "si"])
    async def serverinfo(self, ctx, guild=None):
        """
      Shows you the guild's informations.
    """
        guild1 = guild
        if guild1 is None:
            guild1 = ctx.message.guild
        else:
            if self.bot.get_guild(guild) is None:
                return await ctx.send(
                    "Bot do not have permission to view that guild")
            else:
                guild1 = self.bot.get_guild(guild)
        categories = len(guild1.categories)
        channels = len(guild1.channels)
        created_at = humanize.naturaldate(guild1.created_at)
        default_role = guild1.default_role.name
        features = "\n".join(
            list(
                map(lambda f: f.title(),
                    [feature.replace("_", " ")
                     for feature in guild1.features])))
        description = guild1.description
        emoji_limit = guild1.emoji_limit
        emojis_count = len(guild1.emojis)
        guild_id = guild1.id
        guild_name = guild1.name
        guild_owner = guild1.owner
        guild_owner_id = guild1.owner_id
        member_count = guild1.member_count

        embed = discord.Embed(color=self.bot.color)
        embed.set_thumbnail(url=str(guild1.icon_url_as(static_format="png")))
        embed.set_author(name=guild_name)
        embed.add_field(
            name="Infos",
            value=
            f"**Categories Count**: {categories}\n**Channels Count**: {channels}\n**Created_at**: {created_at}\n**Default Role**: {default_role}\n**Emoji Count:** {emojis_count}\n**Features:** \n{features}\n**Description**: {description}\n**Emoji Limit**: {emoji_limit}\n**Guild Id**: {guild_id}\n**Guild Owner**: {guild_owner}\n**Guild Owner UserId**: {guild_owner_id}\n**Member Count**: {member_count}"
        )
        await ctx.reply(embed=embed)

    @commands.command(aliases=["cbo"])
    async def choosebestof(self, ctx, times: Optional[str],
                           *choices: commands.clean_content):
        """Chooses between multiple choices x times. to choose multiple stuff you shouse use double quote
        """
        await ctx.channel.trigger_typing()
        if len(choices) < 2:
            return await ctx.send("Give me more choice to choose from")
        if times == "max":
            times = 1000000
        times = int(times)
        embed = discord.Embed(color=self.bot.color,
                              description="<a:loading:747680523459231834>")
        message = await ctx.reply(embed=embed)

        builder = await self.bot.loop.run_in_executor(None,
                                                      self.choosebstofcal, ctx,
                                                      times, choices)
        embed = discord.Embed(color=self.bot.color,
                              description="\n".join(builder))
        await message.edit(embed=embed)

    @commands.command(aliases=["ui", "userinformation", "userinformations"])
    async def userinfo(self,
                       ctx,
                       member: typing.Union[discord.Member,
                                            discord.User] = None):
        """
    Shows you the user's informations.
    """
        member1 = member
        if member1 is None:
            member1 = ctx.guild.get_member(ctx.author.id)
        if isinstance(member1, discord.Member):
            embed = discord.Embed(color=self.bot.color)
            embed.set_author(name=member1)
            if member1.bot == True:
                bot = "<:greenTick:596576670815879169>"
            else:
                bot = "<:redTick:596576672149667840>"
            created_at = humanize.naturaldate(member1.created_at)
            nickname = member1.display_name
            id = member1.id
            joined_at = humanize.naturaldate(member1.joined_at)
            if member1.premium_since:
                premium_since = humanize.naturaldate(member1.premium_since)
            else:
                premium_since = "Member not boosting server"
            if member1.public_flags.staff == True:
                staff = "<:greenTick:596576670815879169>"
            else:
                staff = "<:redTick:596576672149667840>"
            if member1.public_flags.partner == True:
                partner = "<:greenTick:596576670815879169>"
            else:
                partner = "<:redTick:596576672149667840>"
            if member1.public_flags.hypesquad == False:
                hypesquad = "<:redTick:596576672149667840>"
            if member1.public_flags.bug_hunter == True:
                bug_hunter = "<:greenTick:596576670815879169>"
            else:
                bug_hunter = "<:redTick:596576672149667840>"
            if member1.public_flags.hypesquad_bravery == True:
                hypesquad = "Hypesquad Bravery"
            if member1.public_flags.hypesquad_brilliance == True:
                hypesquad = "Hypesquad Brilliance"
            if member1.public_flags.hypesquad_balance == True:
                hypesquad = "Hypesquad Balance"
            if member1.public_flags.early_supporter == True:
                early_supporter = "<:greenTick:596576670815879169>"
            else:
                early_supporter = "<:redTick:596576672149667840>"
            if member1.public_flags.bug_hunter_level_2 == True:
                bug_hunter = "<:greenTick:596576670815879169> Bug hunter level 2"
            if member1.public_flags.verified_bot == True:
                verified_bot = "<:greenTick:596576670815879169>"
            else:
                verified_bot = "<:redTick:596576672149667840>"
            if member1.public_flags.verified_bot_developer == True:
                verified_bot_developer = "<:greenTick:596576670815879169>"
            else:
                verified_bot_developer = "<:redTick:596576672149667840>"
            toprole = member1.top_role.name
            if member1.is_avatar_animated() == True:
                avatar_animated = "<:greenTick:596576670815879169>"
            else:
                avatar_animated = "<:redTick:596576672149667840>"
            embed.set_thumbnail(url=member1.avatar_url_as(static_format="png"))
            embed.add_field(
                name="User",
                value=
                f"**Bot:** {bot}\n**Account Created at:** {created_at}\n**Nickname:** {nickname}\n**UserId:** {id}\n**Joined Server at:** {joined_at}\n**Boosted Server since since:** {premium_since}\n**Discord Staff:** {staff}\n**Discord Partner:** {partner}\n**Hypesquad:** {hypesquad}\n**Bug Hunter:** {bug_hunter}\n**Early Supporter:** {early_supporter}\n**Verified Bot:** {verified_bot}\n**Early Verified Bot Developer:** {verified_bot_developer}\n**Avatar Animated:** {avatar_animated}\n**Top Role:** {toprole}"
            )
        else:
            embed = discord.Embed(color=self.bot.color)
            embed.set_author(name=member1)
            if member1.bot == True:
                bot = "<:greenTick:596576670815879169>"
            else:
                bot = "<:redTick:596576672149667840>"
            created_at = humanize.naturaldate(member1.created_at)
            id = member1.id
            if member1.public_flags.staff == True:
                staff = "<:greenTick:596576670815879169>"
            else:
                staff = "<:redTick:596576672149667840>"
            if member1.public_flags.partner == True:
                partner = "<:greenTick:596576670815879169>"
            else:
                partner = "<:redTick:596576672149667840>"
            if member1.public_flags.hypesquad == False:
                hypesquad = "<:redTick:596576672149667840>"
            if member1.public_flags.bug_hunter == True:
                bug_hunter = "<:greenTick:596576670815879169>"
            else:
                bug_hunter = "<:redTick:596576672149667840>"
            if member1.public_flags.hypesquad_bravery == True:
                hypesquad = "Hypesquad Bravery"
            if member1.public_flags.hypesquad_brilliance == True:
                hypesquad = "Hypesquad Brilliance"
            if member1.public_flags.hypesquad_balance == True:
                hypesquad = "Hypesquad Balance"
            if member1.public_flags.early_supporter == True:
                early_supporter = "<:greenTick:596576670815879169>"
            else:
                early_supporter = "<:redTick:596576672149667840>"
            if member1.public_flags.bug_hunter_level_2 == True:
                bug_hunter = "<:greenTick:596576670815879169> Bug hunter level 2"
            if member1.public_flags.verified_bot == True:
                verified_bot = "<:greenTick:596576670815879169>"
            else:
                verified_bot = "<:redTick:596576672149667840>"
            if member1.public_flags.verified_bot_developer == True:
                verified_bot_developer = "<:greenTick:596576670815879169>"
            else:
                verified_bot_developer = "<:redTick:596576672149667840>"
            if member1.is_avatar_animated() == True:
                avatar_animated = "<:greenTick:596576670815879169>"
            else:
                avatar_animated = "<:redTick:596576672149667840>"
            embed.set_thumbnail(url=member1.avatar_url_as(static_format="png"))
            embed.add_field(
                name="User",
                value=
                f"**Bot:** {bot}\n**Account Created at:** {created_at}\n**UserId:** {id}\n**Discord Staff:** {staff}\n**Discord Partner:** {partner}\n**Hypesquad:** {hypesquad}\n**Bug Hunter:** {bug_hunter}\n**Early Supporter:** {early_supporter}\n**Verified Bot:** {verified_bot}\n**Early Verified Bot Developer:** {verified_bot_developer}\n**Avatar Animated:** {avatar_animated}"
            )

        embed.set_footer(
            text=
            f"requested by {ctx.author} response time : {round(self.bot.latency * 1000)} ms",
            icon_url=ctx.author.avatar_url)
        await ctx.reply(embed=embed)

    @commands.command()
    async def avatar(self, ctx, member: discord.User = None):
        """
    shows a members's avatar

    """
        member1 = member
        if member1 is None:
            member1 = ctx.author
        embed = discord.Embed(color=self.bot.color)
        embed.set_image(url=str(member1.avatar_url_as(static_format="png")))
        embed.set_footer(
            text=
            f"requested by {ctx.author} response time : {round(self.bot.latency * 1000)} ms",
            icon_url=ctx.author.avatar_url)
        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(utility(bot))
