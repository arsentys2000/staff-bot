import discord
from discord.ext import commands
from discord import app_commands
import json
from datetime import datetime

# ---------- LOAD / SAVE ----------
def load(file):
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

config = load("config.json")
data = load("data.json")

# ---------- BOT ----------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- PERMISSIONS ----------
def is_moderator(member: discord.Member):
    if member.guild_permissions.administrator:
        return True
    return any(role.id in data["moderator_roles"] for role in member.roles)

# ---------- STAFF TABLE ----------
async def update_staff_table(guild: discord.Guild):
    if not config["staff_channel_id"]:
        return

    channel = guild.get_channel(config["staff_channel_id"])
    if not channel:
        return

    embed = discord.Embed(
        title="👮 Список адміністрації",
        color=discord.Color.blue()
    )

    for role_id in data["staff_roles"]:
        role = guild.get_role(role_id)
        if not role:
            continue

        if not role.members:
            embed.add_field(
                name=role.name,
                value="— **Вакантно**",
                inline=False
            )
            continue

        text = ""
        for member in role.members:
            uid = str(member.id)
            data["users"].setdefault(uid, {"warn": 0, "strike": 0})
            u = data["users"][uid]
            text += f"• {member.mention} — ⚠️ {u['warn']}/2 | 🚫 {u['strike']}/3\n"

        embed.add_field(name=role.name, value=text, inline=False)

    save("data.json", data)

    if config["staff_message_id"]:
        try:
            msg = await channel.fetch_message(config["staff_message_id"])
            await msg.edit(embed=embed, view=ControlPanel())
            return
        except:
            pass

    msg = await channel.send(embed=embed, view=ControlPanel())
    config["staff_message_id"] = msg.id
    save("config.json", config)

# ---------- LOG ----------
async def send_log(guild, text):
    if not config["log_channel_id"]:
        return
    channel = guild.get_channel(config["log_channel_id"])
    if channel:
        await channel.send(text)

# ---------- UI ----------
class ControlPanel(discord.ui.View):
    timeout = None

    @discord.ui.button(label="⚙️ Панель керування", style=discord.ButtonStyle.gray)
    async def open_panel(self, interaction: discord.Interaction, _):
        if not is_moderator(interaction.user):
            await interaction.response.send_message("❌ Немає доступу", ephemeral=True)
            return
        await interaction.response.send_message(
            "Оберіть дію:",
            view=AdminMenu(),
            ephemeral=True
        )

class AdminMenu(discord.ui.View):
    timeout = None

    @discord.ui.button(label="➕ Додати роль у таблицю", style=discord.ButtonStyle.green)
    async def add_role(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            "Напиши **ID ролі**:",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        msg = await bot.wait_for("message", check=check)
        role = interaction.guild.get_role(int(msg.content))

        if role and role.id not in data["staff_roles"]:
            data["staff_roles"].append(role.id)
            save("data.json", data)
            await update_staff_table(interaction.guild)
            await send_log(interaction.guild, f"➕ Додано роль **{role.name}** у таблицю")

    @discord.ui.button(label="👮 Додати роль модератора", style=discord.ButtonStyle.blurple)
    async def add_mod(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            "Напиши **ID ролі модератора**:",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        msg = await bot.wait_for("message", check=check)
        role = interaction.guild.get_role(int(msg.content))

        if role and role.id not in data["moderator_roles"]:
            data["moderator_roles"].append(role.id)
            save("data.json", data)
            await send_log(interaction.guild, f"👮 Роль **{role.name}** стала модераторською")

# ---------- MODERATION ----------
class ModerationMenu(discord.ui.View):
    timeout = None

    @discord.ui.button(label="⚠️ + Попередження", style=discord.ButtonStyle.red)
    async def warn(self, interaction: discord.Interaction, _):
        await interaction.response.send_message("Згадай користувача:", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.mentions

        msg = await bot.wait_for("message", check=check)
        member = msg.mentions[0]

        uid = str(member.id)
        data["users"].setdefault(uid, {"warn": 0, "strike": 0})
        data["users"][uid]["warn"] += 1
        save("data.json", data)

        await update_staff_table(interaction.guild)
        await send_log(
            interaction.guild,
            f"⚠️ {member.mention} отримав попередження від {interaction.user.mention}"
        )

# ---------- SLASH COMMANDS ----------
@bot.tree.command(name="set_staff_channel", description="Встановити канал зі списком")
async def set_staff_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Тільки адміністратор", ephemeral=True)
        return

    config["staff_channel_id"] = interaction.channel.id
    save("config.json", config)
    await update_staff_table(interaction.guild)
    await interaction.response.send_message("✅ Канал списку встановлено", ephemeral=True)

@bot.tree.command(name="set_moderation_channel", description="Встановити канал модерації")
async def set_moderation_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Тільки адміністратор", ephemeral=True)
        return

    config["moderation_channel_id"] = interaction.channel.id
    save("config.json", config)
    await interaction.channel.send(
        "🛑 **Модерація**",
        view=ModerationMenu()
    )
    await interaction.response.send_message("✅ Канал модерації встановлено", ephemeral=True)

# ---------- READY ----------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Бот запущений як {bot.user}")

bot.run(config["MTQ2MTQ1NzgyNzUzNjA0ODE1OA.G6EOTu.YKzSqPJ9xPwJxG2KWSgYSDBt8sP_ndBs945NcM"])
