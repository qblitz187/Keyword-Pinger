import os
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands

# -----------------------------------------------------
# TOKEN MUST COME FROM ENV
# -----------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise SystemExit("ERROR: DISCORD_TOKEN env var is missing.")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------------------------------
# DATABASE SETUP
# -----------------------------------------------------
VOLUME_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", ".")
DB_PATH = os.path.join(VOLUME_PATH, "keywords.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS keywords (
    user_id INTEGER,
    keyword TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS excluded_channels (
    user_id    INTEGER,
    channel_id INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS watched_channels (
    user_id    INTEGER,
    channel_id INTEGER
)
""")

conn.commit()

# -----------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------
def add_keyword(user_id: int, keyword: str):
    keyword = keyword.lower().strip()
    cur.execute("INSERT INTO keywords (user_id, keyword) VALUES (?, ?)", (user_id, keyword))
    conn.commit()

def remove_keyword(user_id: int, keyword: str):
    keyword = keyword.lower().strip()
    cur.execute("DELETE FROM keywords WHERE user_id = ? AND keyword = ?", (user_id, keyword))
    conn.commit()

def get_keywords(user_id: int):
    cur.execute("SELECT keyword FROM keywords WHERE user_id = ?", (user_id,))
    return [row[0] for row in cur.fetchall()]

def get_all_keywords():
    cur.execute("SELECT user_id, keyword FROM keywords")
    return cur.fetchall()

def add_excluded_channel(user_id: int, channel_id: int):
    cur.execute("INSERT INTO excluded_channels (user_id, channel_id) VALUES (?, ?)", (user_id, channel_id))
    conn.commit()

def remove_excluded_channel(user_id: int, channel_id: int):
    cur.execute("DELETE FROM excluded_channels WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
    conn.commit()

def get_excluded_channels(user_id: int):
    cur.execute("SELECT channel_id FROM excluded_channels WHERE user_id = ?", (user_id,))
    return [row[0] for row in cur.fetchall()]

def is_channel_excluded_for_user(user_id: int, channel_id: int):
    cur.execute(
        "SELECT 1 FROM excluded_channels WHERE user_id = ? AND channel_id = ? LIMIT 1",
        (user_id, channel_id)
    )
    return cur.fetchone() is not None

def add_watched_channel(user_id: int, channel_id: int):
    cur.execute(
        "SELECT 1 FROM watched_channels WHERE user_id = ? AND channel_id = ? LIMIT 1",
        (user_id, channel_id)
    )
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO watched_channels (user_id, channel_id) VALUES (?, ?)",
            (user_id, channel_id)
        )
        conn.commit()

def remove_watched_channel(user_id: int, channel_id: int):
    cur.execute(
        "DELETE FROM watched_channels WHERE user_id = ? AND channel_id = ?",
        (user_id, channel_id)
    )
    conn.commit()

def get_watched_channels(user_id: int):
    cur.execute("SELECT channel_id FROM watched_channels WHERE user_id = ?", (user_id,))
    return [row[0] for row in cur.fetchall()]

def get_channel_watchers(channel_id: int):
    cur.execute("SELECT user_id FROM watched_channels WHERE channel_id = ?", (channel_id,))
    return [row[0] for row in cur.fetchall()]

# -----------------------------------------------------
# /kw COMMAND GROUP
# -----------------------------------------------------
class KeywordGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="kw", description="Keyword alert tools")

    @app_commands.command(name="add", description="Add a keyword to be notified about")
    async def add(self, interaction: discord.Interaction, keyword: str):
        add_keyword(interaction.user.id, keyword)
        await interaction.response.send_message(f"Added keyword: **{keyword}**", ephemeral=True)

    @app_commands.command(name="remove", description="Remove one of your keywords")
    async def remove(self, interaction: discord.Interaction, keyword: str):
        remove_keyword(interaction.user.id, keyword)
        await interaction.response.send_message(f"Removed keyword: **{keyword}**", ephemeral=True)

    @app_commands.command(name="list", description="See all keywords you are tracking")
    async def list(self, interaction: discord.Interaction):
        kws = get_keywords(interaction.user.id)
        if not kws:
            await interaction.response.send_message("You don't have any keywords yet.", ephemeral=True)
            return

        await interaction.response.send_message(
            "**Your keywords:**\n" + "\n".join(f"- `{k}`" for k in kws),
            ephemeral=True
        )

    @app_commands.command(name="exclude", description="Stop alerts in a specific channel")
    async def exclude(self, interaction: discord.Interaction, channel: discord.TextChannel):
        add_excluded_channel(interaction.user.id, channel.id)
        await interaction.response.send_message(
            f"I'll ignore keyword alerts for you in {channel.mention}.",
            ephemeral=True
        )

    @app_commands.command(name="unexclude", description="Resume alerts in a channel you excluded")
    async def unexclude(self, interaction: discord.Interaction, channel: discord.TextChannel):
        remove_excluded_channel(interaction.user.id, channel.id)
        await interaction.response.send_message(
            f"I'll resume alerts for you in {channel.mention}.",
            ephemeral=True
        )

    @app_commands.command(name="exclusions", description="List all channels you excluded")
    async def exclusions(self, interaction: discord.Interaction):
        chans = get_excluded_channels(interaction.user.id)
        if not chans:
            await interaction.response.send_message("You have no excluded channels.", ephemeral=True)
            return

        out = []
        for cid in chans:
            ch = interaction.guild.get_channel(cid)
            out.append(ch.mention if ch else f"<#{cid}>")

        await interaction.response.send_message(
            "**Your excluded channels:**\n" + "\n".join(out),
            ephemeral=True
        )

    @app_commands.command(name="watch", description="Get a DM for every new post in a channel")
    async def watch(self, interaction: discord.Interaction, channel: discord.TextChannel):
        add_watched_channel(interaction.user.id, channel.id)
        await interaction.response.send_message(
            f"I'll DM you whenever a new message is posted in {channel.mention}.",
            ephemeral=True
        )

    @app_commands.command(name="unwatch", description="Stop DMs for every new post in a channel")
    async def unwatch(self, interaction: discord.Interaction, channel: discord.TextChannel):
        remove_watched_channel(interaction.user.id, channel.id)
        await interaction.response.send_message(
            f"I'll stop sending every-post alerts for {channel.mention}.",
            ephemeral=True
        )

    @app_commands.command(name="watches", description="List channels where every new post DMs you")
    async def watches(self, interaction: discord.Interaction):
        chans = get_watched_channels(interaction.user.id)
        if not chans:
            await interaction.response.send_message("You aren't watching any channels.", ephemeral=True)
            return

        out = []
        for cid in chans:
            ch = interaction.guild.get_channel(cid)
            out.append(ch.mention if ch else f"<#{cid}>")

        await interaction.response.send_message(
            "**Channels you're watching:**\n" + "\n".join(out),
            ephemeral=True
        )

bot.tree.add_command(KeywordGroup())

# -----------------------------------------------------
# EVENTS
# -----------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id={bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print("Sync failed:", e)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    text = message.content.lower().strip()

    notified_users = set()

    for user_id in get_channel_watchers(message.channel.id):
        user = message.guild.get_member(user_id)
        if not user:
            continue

        try:
            await user.send(
                f"**Watched channel post**\n"
                f"Server: **{message.guild.name}**\n"
                f"Channel: {message.channel.mention}\n"
                f"Author: **{message.author.display_name}**\n"
                f"Jump: {message.jump_url}"
            )
            notified_users.add(user_id)
        except:
            pass

    if not text:
        return

    for user_id, keyword in get_all_keywords():
        if user_id in notified_users:
            continue

        if keyword in text:
            if is_channel_excluded_for_user(user_id, message.channel.id):
                continue

            user = message.guild.get_member(user_id)
            if not user:
                continue

            try:
                await user.send(
                    f"🔔 **Keyword hit:** `{keyword}`\n"
                    f"Server: **{message.guild.name}**\n"
                    f"Channel: {message.channel.mention}\n"
                    f"Jump: {message.jump_url}"
                )
            except:
                pass

# -----------------------------------------------------
# RUN
# -----------------------------------------------------
bot.run(TOKEN)
