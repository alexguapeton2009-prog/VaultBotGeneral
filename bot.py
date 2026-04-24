import traceback
import sys
print("Python version:", sys.version)
sys.stdout.flush()
import discord
from discord.ext import commands
import asyncio
import yt_dlp
import secrets

import os
TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID             = 1496981659655078000
BIENVENIDA_CH_ID     = 1496982319112913086
DESPEDIDA_CH_ID      = 1496982512205828248
VERIFICACION_CH_ID   = 1496988696455413770
TICKETS_CH_ID        = 1496983520726482994
TICKETS_CATEGORY_ID  = 1496982211432415393
LOG_CH_ID            = 1496999027391332452
ROL_NO_VERIFICADO_ID = 1496987179174592712
ROL_VERIFICADO_ID    = 1496987032071700530
ROL_OWNER_ID         = 1496986693457285272
MUSIC_TEXT_CH_ID     = 1496983031632625747
MUSIC_VOICE_CH_ID    = 1497027296094326844
FOTO_BIENVENIDA      = "https://i.imgur.com/djR0tI7.png"
SEGUNDOS_BORRAR      = 5

tokens_verificacion = {}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ══════════════════════════════════════════
#                  MÚSICA
# ══════════════════════════════════════════

class MusicQueue:
    def __init__(self):
        self.queue   = []
        self.current = None
        self.vc      = None
        self.panel   = None   # mensaje del panel principal

music = MusicQueue()

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

async def get_info(query: str):
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        info = await loop.run_in_executor(
            None, lambda: ydl.extract_info(query, download=False)
        )
    if "entries" in info:
        info = info["entries"][0]
    return info["title"], info["url"]

def build_panel_embed():
    """Construye el embed del panel de música."""
    if music.current:
        titulo = "🎶  Reproduciendo ahora"
        desc   = f"**{music.current['title']}**\nPedida por **{music.current['requester']}**"
        color  = 0x9b59b6
    else:
        titulo = "🎵  Sin música"
        desc   = "No hay nada reproduciéndose ahora mismo."
        color  = 0x2c2f33

    embed = discord.Embed(title=titulo, description=desc, color=color)

    if music.queue:
        cola_lines = "\n".join(
            f"`{i}.` {s['title']} — por **{s['requester']}**"
            for i, s in enumerate(music.queue[:8], 1)
        )
        if len(music.queue) > 8:
            cola_lines += f"\n*...y {len(music.queue) - 8} más*"
        embed.add_field(name="📋 Cola", value=cola_lines, inline=False)
    else:
        embed.add_field(name="📋 Cola", value="*Vacía*", inline=False)

    embed.set_footer(text="Escribe en este canal o pulsa ➕ para añadir una canción")
    return embed

async def actualizar_panel():
    """Edita el panel existente con el estado actual."""
    if music.panel:
        try:
            await music.panel.edit(embed=build_panel_embed(), view=VistaMusicPanel())
        except Exception:
            pass

async def play_next(guild):
    if not music.queue:
        music.current = None
        if music.vc and music.vc.is_connected():
            await music.vc.disconnect()
            music.vc = None
        await actualizar_panel()
        return

    music.current = music.queue.pop(0)
    source = discord.PCMVolumeTransformer(
        discord.FFmpegPCMAudio(music.current["url"], **FFMPEG_OPTIONS),
        volume=0.5
    )

    def after_play(error):
        if error:
            print(f"❌ Error: {error}")
        asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)

    music.vc.play(source, after=after_play)
    await actualizar_panel()

async def conectar_voz(guild):
    """Conecta al canal de voz si no está conectado. Devuelve True si OK."""
    if music.vc and music.vc.is_connected():
        return True
    vc_ch = guild.get_channel(MUSIC_VOICE_CH_ID)
    if not vc_ch:
        return False
    try:
        music.vc = await vc_ch.connect()
        return True
    except Exception as e:
        print(f"❌ No pude conectarme al canal de voz: {e}")
        return False

async def añadir_cancion(query: str, requester: str, guild, feedback_ch=None):
    """Busca y añade una canción. feedback_ch es donde mandar mensajes de estado."""
    ch = feedback_ch or guild.get_channel(MUSIC_TEXT_CH_ID)

    loading = await ch.send(
        embed=discord.Embed(description=f"🔍 Buscando **{query}**...", color=0x9b59b6),
        delete_after=30
    )
    try:
        title, url = await get_info(query)
    except Exception as e:
        await loading.delete()
        await ch.send(
            embed=discord.Embed(description=f"❌ No encontré esa canción: `{e}`", color=0xe74c3c),
            delete_after=8
        )
        return
    await loading.delete()

    song = {"title": title, "url": url, "requester": requester}

    ok = await conectar_voz(guild)
    if not ok:
        await ch.send(
            embed=discord.Embed(description="❌ No pude conectarme al canal de voz.", color=0xe74c3c),
            delete_after=8
        )
        return

    if music.vc.is_playing() or music.vc.is_paused():
        music.queue.append(song)
        pos = len(music.queue)
        await ch.send(
            embed=discord.Embed(
                description=f"✅ **{title}** añadida a la cola (posición #{pos})",
                color=0x2ecc71
            ),
            delete_after=8
        )
        await actualizar_panel()
    else:
        music.queue.insert(0, song)
        await play_next(guild)

# ── Panel de música (mensaje fijo en el canal) ──

class VistaMusicPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(emoji="➕", label="Añadir canción", style=discord.ButtonStyle.success, custom_id="music_add")
    async def añadir(self, interaction, button):
        await interaction.response.send_modal(ModalCancion())

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary, custom_id="music_pause")
    async def pausar(self, interaction, button):
        vc = music.vc
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Pausado.", ephemeral=True)
        elif vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Reanudado.", ephemeral=True)
        else:
            await interaction.response.send_message("No hay nada reproduciéndose.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="music_skip")
    async def saltar(self, interaction, button):
        vc = music.vc
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭️ Saltando...", ephemeral=True)
        else:
            await interaction.response.send_message("No hay nada reproduciéndose.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="music_stop")
    async def parar(self, interaction, button):
        rol_owner = interaction.guild.get_role(ROL_OWNER_ID)
        if not (rol_owner and rol_owner in interaction.user.roles):
            await interaction.response.send_message("❌ Solo los Owners pueden parar la música.", ephemeral=True)
            return
        music.queue.clear()
        music.current = None
        if music.vc:
            music.vc.stop()
            await music.vc.disconnect()
            music.vc = None
        await actualizar_panel()
        await interaction.response.send_message("⏹️ Música parada.", ephemeral=True)

class ModalCancion(discord.ui.Modal, title="🎵 Añadir canción"):
    cancion = discord.ui.TextInput(
        label="Nombre o link de YouTube",
        placeholder="Ej: bad bunny moscow mule  /  https://youtu.be/...",
        max_length=200
    )

    async def on_submit(self, interaction):
        await interaction.response.send_message(
            embed=discord.Embed(description=f"🔍 Buscando **{self.cancion.value}**...", color=0x9b59b6),
            ephemeral=True
        )
        await añadir_cancion(
            query=self.cancion.value,
            requester=interaction.user.display_name,
            guild=interaction.guild,
            feedback_ch=None
        )

async def enviar_panel_musica():
    """Envía o renueva el panel fijo del canal de música."""
    guild = bot.get_guild(GUILD_ID)
    ch    = guild.get_channel(MUSIC_TEXT_CH_ID)
    if not ch:
        return
    async for msg in ch.history(limit=30):
        if msg.author == bot.user:
            await msg.delete()
    music.panel = await ch.send(embed=build_panel_embed(), view=VistaMusicPanel())

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == MUSIC_TEXT_CH_ID:
        query = message.content.strip()
        if query:
            await message.delete()
            await añadir_cancion(
                query=query,
                requester=message.author.display_name,
                guild=message.guild,
                feedback_ch=message.channel
            )
        return

    await bot.process_commands(message)

# ══════════════════════════════════════════
#                  ON READY
# ══════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="el servidor 👀"
    ))
    await enviar_panel_verificacion()
    await enviar_panel_tickets()
    await enviar_panel_musica()

# ══════════════════════════════════════════
#                 MIEMBROS
# ══════════════════════════════════════════

@bot.event
async def on_member_join(member):
    guild = member.guild
    rol_no_ver = guild.get_role(ROL_NO_VERIFICADO_ID)
    if rol_no_ver:
        try:
            await member.add_roles(rol_no_ver, reason="Rol automático al unirse")
        except discord.Forbidden:
            print(f"❌ Sin permisos para asignar rol a {member.name}")

    canal = guild.get_channel(BIENVENIDA_CH_ID)
    if canal:
        embed = discord.Embed(
            title="¡Bienvenido/a al servidor! 🎉",
            description=(
                f"Hey {member.mention}, nos alegra tenerte aquí.\n\n"
                f"Ve a <#{VERIFICACION_CH_ID}> y pulsa el botón para verificarte."
            ),
            color=0x2ecc71
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_image(url=FOTO_BIENVENIDA)
        embed.set_footer(text=f"Miembro #{guild.member_count}")
        await canal.send(embed=embed)

@bot.event
async def on_member_remove(member):
    canal = member.guild.get_channel(DESPEDIDA_CH_ID)
    if canal:
        embed = discord.Embed(
            title="Hasta luego 👋",
            description=f"**{member.name}** ha abandonado el servidor.",
            color=0xe74c3c
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Ahora somos {member.guild.member_count} miembros")
        await canal.send(embed=embed)

# ══════════════════════════════════════════
#              VERIFICACIÓN
# ══════════════════════════════════════════

async def enviar_panel_verificacion():
    guild = bot.get_guild(GUILD_ID)
    canal = guild.get_channel(VERIFICACION_CH_ID)
    if not canal:
        return
    async for msg in canal.history(limit=20):
        if msg.author == bot.user:
            await msg.delete()
    embed = discord.Embed(
        title="✅  Verificación",
        description=(
            "Pulsa el botón de abajo para verificarte.\n"
            "Te llegará un mensaje privado con un botón de confirmación.\n\n"
            "*(Si tienes los DMs cerrados, te verificamos automáticamente.)*"
        ),
        color=0x2ecc71
    )
    embed.set_footer(text="Solo tienes que hacerlo una vez.")
    await canal.send(embed=embed, view=VistaVerificacion())

class VistaVerificacion(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verificarme", emoji="✅", style=discord.ButtonStyle.success, custom_id="verificar_btn")
    async def verificar(self, interaction, button):
        guild  = interaction.guild
        member = interaction.user
        rol_ver = guild.get_role(ROL_VERIFICADO_ID)

        if rol_ver and rol_ver in member.roles:
            await interaction.response.send_message("✅ ¡Ya estás verificado/a!", ephemeral=True)
            return

        token = secrets.token_urlsafe(24)
        tokens_verificacion[token] = member.id

        try:
            dm_embed = discord.Embed(
                title="🔐 Verificación de cuenta",
                description=(
                    f"Hola **{member.display_name}**,\n\n"
                    f"Pulsa el botón para confirmar tu identidad en **{guild.name}**.\n\n"
                    "⏳ Expira en **5 minutos**."
                ),
                color=0x2ecc71
            )
            dm_embed.set_footer(text="Si no pediste esto, ignora este mensaje.")
            await member.send(embed=dm_embed, view=VistaDMVerificar(token, guild.id))
            await interaction.response.send_message(
                "📩 ¡Te hemos enviado un DM! Ábrelo y pulsa el botón para verificarte.",
                ephemeral=True
            )
        except discord.Forbidden:
            await verificar_usuario(member, guild)
            await interaction.response.send_message(
                "✅ ¡Verificado directamente! (Tenías los DMs cerrados.)",
                ephemeral=True
            )
            return

        async def expirar():
            await asyncio.sleep(300)
            tokens_verificacion.pop(token, None)
        asyncio.create_task(expirar())

class VistaDMVerificar(discord.ui.View):
    def __init__(self, token, guild_id):
        super().__init__(timeout=300)
        self.token    = token
        self.guild_id = guild_id

    @discord.ui.button(label="✅ Confirmar verificación", style=discord.ButtonStyle.success, custom_id="dm_verificar")
    async def confirmar(self, interaction, button):
        if self.token not in tokens_verificacion:
            await interaction.response.send_message(
                "❌ Este botón ya expiró. Vuelve al canal de verificación.",
                ephemeral=True
            )
            return
        member_id = tokens_verificacion.pop(self.token)
        guild     = bot.get_guild(self.guild_id)
        member    = guild.get_member(member_id)
        if not member:
            await interaction.response.send_message("❌ No se encontró tu cuenta.", ephemeral=True)
            return
        await verificar_usuario(member, guild)
        button.disabled = True
        button.label    = "✅ ¡Verificado!"
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ ¡Verificación completada!",
                description=f"Ya tienes acceso completo a **{guild.name}**. ¡Bienvenido/a!",
                color=0x2ecc71
            ),
            view=self
        )

async def verificar_usuario(member, guild):
    rol_ver    = guild.get_role(ROL_VERIFICADO_ID)
    rol_no_ver = guild.get_role(ROL_NO_VERIFICADO_ID)
    try:
        if rol_no_ver and rol_no_ver in member.roles:
            await member.remove_roles(rol_no_ver, reason="Verificación completada")
        if rol_ver and rol_ver not in member.roles:
            await member.add_roles(rol_ver, reason="Verificación completada")
        print(f"✅ {member.name} verificado.")
    except discord.Forbidden:
        print(f"❌ Sin permisos para verificar a {member.name}")

# ══════════════════════════════════════════
#                 TICKETS
# ══════════════════════════════════════════

tickets_abiertos = {}

async def enviar_panel_tickets():
    guild = bot.get_guild(GUILD_ID)
    canal = guild.get_channel(TICKETS_CH_ID)
    if not canal:
        return
    async for msg in canal.history(limit=20):
        if msg.author == bot.user:
            await msg.delete()
    embed = discord.Embed(
        title="🎫  Sistema de Tickets",
        description="¿Necesitas ayuda? Pulsa el botón para abrir un ticket privado.",
        color=0x3498db
    )
    embed.set_footer(text="Solo puedes tener un ticket abierto a la vez.")
    await canal.send(embed=embed, view=VistaTicket())

class VistaTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", emoji="🎫", style=discord.ButtonStyle.primary, custom_id="abrir_ticket")
    async def abrir_ticket(self, interaction, button):
        guild  = interaction.guild
        member = interaction.user
        if member.id in tickets_abiertos:
            ch = guild.get_channel(tickets_abiertos[member.id])
            await interaction.response.send_message(f"⚠️ Ya tienes un ticket: {ch.mention}", ephemeral=True)
            return
        categoria  = guild.get_channel(TICKETS_CATEGORY_ID)
        rol_owner  = guild.get_role(ROL_OWNER_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if rol_owner:
            overwrites[rol_owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        ticket_ch = await guild.create_text_channel(
            name=f"ticket-{member.name}", category=categoria, overwrites=overwrites
        )
        tickets_abiertos[member.id] = ticket_ch.id
        embed = discord.Embed(
            title=f"🎫 Ticket de {member.display_name}",
            description=(
                f"Hola {member.mention}, el equipo te atenderá en breve.\n\n"
                "Explica tu problema y un **Owner** cerrará el ticket cuando se resuelva."
            ),
            color=0x3498db
        )
        await ticket_ch.send(embed=embed, view=VistaCerrarTicket(member.id, ticket_ch.id))
        await interaction.response.send_message(f"✅ Ticket creado: {ticket_ch.mention}", ephemeral=True)
        log_ch = guild.get_channel(LOG_CH_ID)
        if log_ch:
            await log_ch.send(f"📩 Nuevo ticket de {member.mention} → {ticket_ch.mention}")

class VistaCerrarTicket(discord.ui.View):
    def __init__(self, owner_id, channel_id):
        super().__init__(timeout=None)
        self.owner_id   = owner_id
        self.channel_id = channel_id

    @discord.ui.button(label="Cerrar Ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="cerrar_ticket_base")
    async def cerrar_ticket(self, interaction, button):
        canal     = interaction.channel
        guild     = interaction.guild
        member    = interaction.user
        rol_owner = guild.get_role(ROL_OWNER_ID)

        if not (rol_owner and rol_owner in member.roles):
            await interaction.response.send_message(
                "❌ Solo los **Owners** pueden cerrar tickets.", ephemeral=True
            )
            return

        button.disabled = True
        await interaction.response.edit_message(view=self)
        await canal.send(f"🔒 Cerrando en {SEGUNDOS_BORRAR} segundos...")
        log_ch = guild.get_channel(LOG_CH_ID)
        if log_ch:
            usuario = guild.get_member(self.owner_id)
            nombre  = usuario.mention if usuario else f"<@{self.owner_id}>"
            await log_ch.send(f"🔒 Ticket cerrado — de {nombre}, cerrado por Owner {member.mention}.")
        if self.owner_id in tickets_abiertos:
            del tickets_abiertos[self.owner_id]
        await asyncio.sleep(SEGUNDOS_BORRAR)
        await canal.delete()

try:
    bot.run(TOKEN)
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
