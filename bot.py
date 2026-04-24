import traceback
import sys
print("Python version:", sys.version)
sys.stdout.flush()
import discord
from discord.ext import commands, tasks
import asyncio
import yt_dlp
import secrets
import random
import re
from datetime import datetime, timedelta

TOKEN = ""

GUILD_ID             = 
BIENVENIDA_CH_ID     = 
DESPEDIDA_CH_ID      = 
VERIFICACION_CH_ID   = 
TICKETS_CH_ID        = 
TICKETS_CATEGORY_ID  = 
LOG_CH_ID            = 
ROL_NO_VERIFICADO_ID = 
ROL_VERIFICADO_ID    = 
ROL_OWNER_ID         = 
MUSIC_TEXT_CH_ID     = 
MUSIC_VOICE_CH_ID    = 
FOTO_BIENVENIDA      = ""
SEGUNDOS_BORRAR      = 5

# ── IDs de canales nuevos (RELLENA con los IDs de tus canales) ──
SORTEOS_CH_ID        =    # canal #🎁・sorteos
ENCUESTAS_CH_ID      =    # canal #📊・encuestas
SUGERENCIAS_CH_ID    =    # canal #💡・sugerencias
RANGOS_CH_ID         =    # canal #🏆・rangos (nivel/XP)
CUMPLES_CH_ID        =    # canal #🎂・cumpleaños

tokens_verificacion  = {}
tickets_abiertos     = {}
sorteos_activos      = {}   # message_id → info sorteo
xp_data              = {}   # user_id → {"xp": int, "level": int, "mensajes": int}
cumpleanos_data      = {}   # user_id → "DD/MM"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ══════════════════════════════════════════
#                  MÚSICA
# ══════════════════════════════════════════

class MusicQueue:
    def __init__(self):
        self.queue   = []
        self.current = None
        self.vc      = None
        self.panel   = None

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

    # Verificar que seguimos conectados antes de reproducir
    if not music.vc or not music.vc.is_connected():
        print("⚠️ VC desconectado, reconectando...")
        ok = await conectar_voz(guild, retry=2)
        if not ok:
            print("❌ No se pudo reconectar, cancelando")
            music.current = None
            await actualizar_panel()
            return

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

async def limpiar_vc(guild):
    vc = guild.voice_client
    if vc:
        try:
            await vc.disconnect(force=True)
        except:
            pass
    music.vc = None

async def conectar_voz(guild, retry=3):
    vc_ch = guild.get_channel(MUSIC_VOICE_CH_ID)
    if not vc_ch:
        return False

    for intento in range(retry):
        try:
            print(f"🔗 Conectando al canal de voz (intento {intento + 1}/{retry})...")

            # Si ya hay conexión, mover en vez de reconectar
            if guild.voice_client:
                if guild.voice_client.channel.id != vc_ch.id:
                    await guild.voice_client.move_to(vc_ch)
                music.vc = guild.voice_client
                return True

            # Conectar correctamente
            music.vc = await vc_ch.connect(
                timeout=15,
                reconnect=True  # 🔥 IMPORTANTE
            )

            print(f"✅ Conectado a {vc_ch.name}")
            return True

        except Exception as e:
            print(f"❌ Error conectando (intento {intento + 1}): {type(e).__name__}: {e}")
            music.vc = None
            await asyncio.sleep(2)

    print("❌ No se pudo conectar")
    return False

async def añadir_cancion(query: str, requester: str, guild, feedback_ch=None):
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
    ok = await conectar_voz(guild, retry=3)
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
            embed=discord.Embed(description=f"✅ **{title}** añadida a la cola (posición #{pos})", color=0x2ecc71),
            delete_after=8
        )
        await actualizar_panel()
    else:
        music.queue.insert(0, song)
        await play_next(guild)

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
    guild = bot.get_guild(GUILD_ID)
    ch    = guild.get_channel(MUSIC_TEXT_CH_ID)
    if not ch:
        return
    async for msg in ch.history(limit=30):
        if msg.author == bot.user:
            await msg.delete()
    music.panel = await ch.send(embed=build_panel_embed(), view=VistaMusicPanel())

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

# ══════════════════════════════════════════
#               SISTEMA XP / NIVELES
# ══════════════════════════════════════════

def get_xp_for_level(level):
    return 100 * (level ** 2)

def check_level_up(user_id):
    data = xp_data.get(user_id, {"xp": 0, "level": 1, "mensajes": 0})
    leveled_up = False
    while data["xp"] >= get_xp_for_level(data["level"]):
        data["level"] += 1
        leveled_up = True
    xp_data[user_id] = data
    return leveled_up, data["level"]

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

    # XP por mensaje
    uid = message.author.id
    if uid not in xp_data:
        xp_data[uid] = {"xp": 0, "level": 1, "mensajes": 0}
    ganado = random.randint(5, 15)
    xp_data[uid]["xp"] += ganado
    xp_data[uid]["mensajes"] += 1
    leveled, new_level = check_level_up(uid)
    if leveled:
        embed = discord.Embed(
            title="⬆️ ¡Level Up!",
            description=f"{message.author.mention} ha subido al **nivel {new_level}** 🎉",
            color=0xf1c40f
        )
        await message.channel.send(embed=embed, delete_after=10)

    await bot.process_commands(message)

# ══════════════════════════════════════════
#                   AYUDA
# ══════════════════════════════════════════

class VistaAyuda(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.pagina = "inicio"

    def embed_inicio(self):
        e = discord.Embed(
            title="📚 VaultBot — Panel de Comandos",
            description="Selecciona una categoría para ver los comandos disponibles.",
            color=0x9b59b6
        )
        e.add_field(name="🎵 Música", value="Panel visual en el canal de música", inline=True)
        e.add_field(name="🎮 Diversión", value="Dados, 8ball, moneda...", inline=True)
        e.add_field(name="🎁 Sorteos", value="Crear y gestionar sorteos", inline=True)
        e.add_field(name="📊 Encuestas", value="Crear encuestas con reacciones", inline=True)
        e.add_field(name="🏆 Niveles", value="Sistema de XP y rangos", inline=True)
        e.add_field(name="🔨 Moderación", value="Kick, ban, mute, clear...", inline=True)
        e.add_field(name="💡 Utilidades", value="Info, ping, cumpleaños...", inline=True)
        e.set_footer(text="VaultBot • Usa los botones para navegar")
        return e

    def embed_diversion(self):
        e = discord.Embed(title="🎮 Diversión", color=0xe74c3c)
        cmds = [
            ("!dado [caras]", "Lanza un dado (def. 6 caras)"),
            ("!moneda", "Cara o cruz"),
            ("!8ball <pregunta>", "La bola mágica responde"),
            ("!ruleta", "La ruleta rusa... ¡con suerte!"),
            ("!pp <usuario>", "Mide el PP de alguien 😏"),
            ("!ship <@user1> <@user2>", "Compatibilidad amorosa 💕"),
            ("!iq <usuario>", "Mide el IQ de alguien"),
            ("!rps <piedra|papel|tijera>", "Piedra, papel o tijera"),
            ("!chiste", "Un chiste aleatorio"),
            ("!meme", "Un meme random"),
        ]
        e.description = "\n".join(f"`{c}` — {d}" for c, d in cmds)
        return e

    def embed_sorteos(self):
        e = discord.Embed(title="🎁 Sorteos", color=0xf39c12)
        cmds = [
            ("!sorteo <tiempo> <premio>", "Crea un sorteo (ej: !sorteo 1h Nitro)"),
            ("!sorteo_fin <mensaje_id>", "Termina un sorteo antes de tiempo"),
            ("!reroll <mensaje_id>", "Vuelve a sortear un ganador"),
        ]
        e.description = "\n".join(f"`{c}` — {d}" for c, d in cmds)
        e.add_field(name="⏰ Formato de tiempo", value="`10s` `5m` `2h` `1d`", inline=False)
        return e

    def embed_encuestas(self):
        e = discord.Embed(title="📊 Encuestas", color=0x3498db)
        cmds = [
            ("!encuesta <pregunta>", "Encuesta de Sí/No con reacciones"),
            ("!encuesta2 <pregunta> | op1 | op2 | ...", "Encuesta con hasta 5 opciones"),
        ]
        e.description = "\n".join(f"`{c}` — {d}" for c, d in cmds)
        return e

    def embed_niveles(self):
        e = discord.Embed(title="🏆 Niveles & XP", color=0xf1c40f)
        cmds = [
            ("!nivel [@usuario]", "Ver tu nivel y XP actual"),
            ("!top", "Top 10 de miembros con más XP"),
            ("!cumple <DD/MM>", "Registra tu cumpleaños"),
        ]
        e.description = "\n".join(f"`{c}` — {d}" for c, d in cmds)
        e.add_field(name="ℹ️ Info", value="Ganas XP enviando mensajes (5-15 XP por mensaje)", inline=False)
        return e

    def embed_moderacion(self):
        e = discord.Embed(title="🔨 Moderación", color=0xe74c3c)
        e.add_field(name="⚠️ Solo para Owners", value="", inline=False)
        cmds = [
            ("!kick <@usuario> [razón]", "Expulsa a un miembro"),
            ("!ban <@usuario> [razón]", "Banea a un miembro"),
            ("!unban <ID>", "Desbanea a un usuario por ID"),
            ("!mute <@usuario> <tiempo>", "Silencia a un miembro"),
            ("!unmute <@usuario>", "Deja de silenciar"),
            ("!clear <cantidad>", "Borra mensajes (máx 100)"),
            ("!warn <@usuario> <razón>", "Advierte a un miembro"),
            ("!slowmode <segundos>", "Activa slowmode en el canal"),
        ]
        e.description = "\n".join(f"`{c}` — {d}" for c, d in cmds)
        return e

    def embed_utilidades(self):
        e = discord.Embed(title="💡 Utilidades", color=0x2ecc71)
        cmds = [
            ("!ping", "Latencia del bot"),
            ("!info @usuario", "Info de un miembro"),
            ("!servidor", "Info del servidor"),
            ("!avatar @usuario", "Avatar de un miembro"),
            ("!sugerencia <texto>", "Manda una sugerencia al staff"),
            ("!ayuda", "Este panel"),
        ]
        e.description = "\n".join(f"`{c}` — {d}" for c, d in cmds)
        return e

    @discord.ui.button(label="🎮 Diversión", style=discord.ButtonStyle.primary, custom_id="help_div")
    async def div(self, i, b):
        await i.response.edit_message(embed=self.embed_diversion(), view=self)

    @discord.ui.button(label="🎁 Sorteos", style=discord.ButtonStyle.primary, custom_id="help_sort")
    async def sort(self, i, b):
        await i.response.edit_message(embed=self.embed_sorteos(), view=self)

    @discord.ui.button(label="📊 Encuestas", style=discord.ButtonStyle.primary, custom_id="help_enc")
    async def enc(self, i, b):
        await i.response.edit_message(embed=self.embed_encuestas(), view=self)

    @discord.ui.button(label="🏆 Niveles", style=discord.ButtonStyle.primary, custom_id="help_niv")
    async def niv(self, i, b):
        await i.response.edit_message(embed=self.embed_niveles(), view=self)

    @discord.ui.button(label="🔨 Moderación", style=discord.ButtonStyle.danger, custom_id="help_mod")
    async def mod(self, i, b):
        await i.response.edit_message(embed=self.embed_moderacion(), view=self)

    @discord.ui.button(label="💡 Utilidades", style=discord.ButtonStyle.secondary, custom_id="help_util")
    async def util(self, i, b):
        await i.response.edit_message(embed=self.embed_utilidades(), view=self)

    @discord.ui.button(label="🏠 Inicio", style=discord.ButtonStyle.secondary, custom_id="help_home")
    async def home(self, i, b):
        await i.response.edit_message(embed=self.embed_inicio(), view=self)

@bot.command(name="ayuda")
async def ayuda(ctx):
    v = VistaAyuda()
    await ctx.send(embed=v.embed_inicio(), view=v)
    try:
        await ctx.message.delete()
    except:
        pass

# ══════════════════════════════════════════
#                  DIVERSIÓN
# ══════════════════════════════════════════

@bot.command(name="dado")
async def dado(ctx, caras: int = 6):
    resultado = random.randint(1, max(2, caras))
    await ctx.send(embed=discord.Embed(
        title=f"🎲 Dado de {caras} caras",
        description=f"¡Ha salido el **{resultado}**!",
        color=0x9b59b6
    ))

@bot.command(name="moneda")
async def moneda(ctx):
    resultado = random.choice(["🪙 Cara", "🪙 Cruz"])
    await ctx.send(embed=discord.Embed(description=f"**{resultado}**", color=0xf1c40f))

@bot.command(name="8ball")
async def bola(ctx, *, pregunta: str):
    respuestas = [
        "✅ Sí, definitivamente.", "✅ Sin duda.", "✅ Cuéntalo con ello.",
        "✅ Mis fuentes dicen que sí.", "🤔 No es el momento.", "🤔 Pregunta más tarde.",
        "🤔 No puedo predecirlo ahora.", "❌ Mis fuentes dicen que no.",
        "❌ No cuentes con ello.", "❌ Las perspectivas no son buenas.",
    ]
    embed = discord.Embed(title="🎱 Magic 8-Ball", color=0x2c2f33)
    embed.add_field(name="Pregunta", value=pregunta, inline=False)
    embed.add_field(name="Respuesta", value=random.choice(respuestas), inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ruleta")
async def ruleta(ctx):
    resultados = ["💀 MUERTO — la bala era tuya.", "😅 Salvado — esta vez.", "😰 Cerca... muy cerca.", "🎉 ¡Suerte de principiante!"]
    pesos = [1, 4, 1, 0]  # no usamos el 4to
    opciones = ["💀 MUERTO", "😅 Salvado", "😰 Cerca...", "😅 Salvado", "😅 Salvado", "😅 Salvado"]
    r = random.choice(opciones)
    color = 0xe74c3c if "MUERTO" in r else 0x2ecc71
    await ctx.send(embed=discord.Embed(title="🔫 Ruleta Rusa", description=f"{ctx.author.mention} {r}", color=color))

@bot.command(name="pp")
async def pp(ctx, usuario: discord.Member = None):
    usuario = usuario or ctx.author
    size = random.randint(0, 20)
    barra = "=" * size
    await ctx.send(embed=discord.Embed(
        title=f"📏 PP de {usuario.display_name}",
        description=f"8{'=' * size}D  ({size} cm)",
        color=0xe91e8c
    ))

@bot.command(name="ship")
async def ship(ctx, user1: discord.Member, user2: discord.Member = None):
    user2 = user2 or ctx.author
    compat = random.randint(0, 100)
    if compat >= 80:
        emoji = "💞"
    elif compat >= 50:
        emoji = "💕"
    elif compat >= 25:
        emoji = "💔"
    else:
        emoji = "😬"
    await ctx.send(embed=discord.Embed(
        title=f"💘 Ship: {user1.display_name} × {user2.display_name}",
        description=f"{emoji} Compatibilidad: **{compat}%**",
        color=0xe91e8c
    ))

@bot.command(name="iq")
async def iq(ctx, usuario: discord.Member = None):
    usuario = usuario or ctx.author
    iq_val = random.randint(50, 200)
    comentario = "🧠 ¡Genio!" if iq_val > 150 else "😐 Normal." if iq_val > 90 else "🥴 Preocupante..."
    await ctx.send(embed=discord.Embed(
        title=f"🧪 IQ de {usuario.display_name}",
        description=f"**{iq_val} puntos** — {comentario}",
        color=0x3498db
    ))

@bot.command(name="rps")
async def rps(ctx, eleccion: str):
    opciones = {"piedra": "🪨", "papel": "📄", "tijera": "✂️"}
    eleccion = eleccion.lower()
    if eleccion not in opciones:
        await ctx.send("❌ Elige entre: `piedra`, `papel` o `tijera`")
        return
    bot_choice = random.choice(list(opciones.keys()))
    gana = {"piedra": "tijera", "papel": "piedra", "tijera": "papel"}
    if eleccion == bot_choice:
        resultado = "😐 **¡Empate!**"
    elif gana[eleccion] == bot_choice:
        resultado = "🎉 **¡Ganaste!**"
    else:
        resultado = "😢 **¡Perdiste!**"
    embed = discord.Embed(title="✊ Piedra, Papel o Tijera", color=0x9b59b6)
    embed.add_field(name="Tú", value=f"{opciones[eleccion]} {eleccion}", inline=True)
    embed.add_field(name="Bot", value=f"{opciones[bot_choice]} {bot_choice}", inline=True)
    embed.add_field(name="Resultado", value=resultado, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="chiste")
async def chiste(ctx):
    chistes = [
        "¿Por qué el libro de matemáticas estaba triste? Porque tenía demasiados problemas.",
        "¿Qué le dijo el cero al ocho? ¡Bonito cinturón!",
        "¿Por qué los pájaros vuelan hacia el sur? Porque es demasiado lejos para ir caminando.",
        "¿Cuál es el colmo de un electricista? Que su mujer se llame Luz y no la entienda.",
        "¿Cómo se dice 'piscina' en japonés? ¡SPLASH!",
        "¿Qué hace una abeja en el gimnasio? ¡Zum-ba!",
        "¿Por qué Beethoven no terminaba nada? Porque estaba decomposing.",
    ]
    await ctx.send(embed=discord.Embed(title="😂 Chiste", description=random.choice(chistes), color=0xf1c40f))

@bot.command(name="meme")
async def meme(ctx):
    memes = [
        "https://i.imgur.com/oHMKxN2.png",
        "https://i.imgur.com/1V5KZXK.jpeg",
        "https://i.imgur.com/DFXzXah.jpeg",
    ]
    embed = discord.Embed(title="😂 Meme Random", color=0xff6b35)
    embed.set_image(url=random.choice(memes))
    await ctx.send(embed=embed)

# ══════════════════════════════════════════
#                  SORTEOS
# ══════════════════════════════════════════

def parsear_tiempo(tiempo_str: str):
    """Convierte '10s', '5m', '2h', '1d' a segundos."""
    unidades = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    match = re.match(r"(\d+)([smhd])", tiempo_str.lower())
    if not match:
        return None
    valor, unidad = int(match.group(1)), match.group(2)
    return valor * unidades[unidad]

@bot.command(name="sorteo")
async def sorteo(ctx, tiempo: str, *, premio: str):
    rol_owner = ctx.guild.get_role(ROL_OWNER_ID)
    if not (rol_owner and rol_owner in ctx.author.roles):
        await ctx.send("❌ Solo los Owners pueden crear sorteos.", delete_after=5)
        return

    segundos = parsear_tiempo(tiempo)
    if not segundos:
        await ctx.send("❌ Formato de tiempo inválido. Ej: `10s`, `5m`, `2h`, `1d`", delete_after=5)
        return

    fin = datetime.utcnow() + timedelta(seconds=segundos)
    embed = discord.Embed(
        title="🎁 ¡SORTEO!",
        description=f"**Premio:** {premio}\n\n¡Reacciona con 🎉 para participar!\n\n⏰ Termina: <t:{int(fin.timestamp())}:R>",
        color=0xf39c12
    )
    embed.set_footer(text=f"Organizado por {ctx.author.display_name}")

    canal = ctx.guild.get_channel(SORTEOS_CH_ID) if SORTEOS_CH_ID else ctx.channel
    msg = await canal.send(embed=embed)
    await msg.add_reaction("🎉")

    sorteos_activos[msg.id] = {
        "premio": premio,
        "canal_id": canal.id,
        "msg_id": msg.id,
        "organizador": ctx.author.id,
        "activo": True
    }

    try:
        await ctx.message.delete()
    except:
        pass

    await asyncio.sleep(segundos)
    await finalizar_sorteo(msg.id, canal)

async def finalizar_sorteo(msg_id: int, canal):
    if msg_id not in sorteos_activos or not sorteos_activos[msg_id]["activo"]:
        return
    sorteos_activos[msg_id]["activo"] = False
    try:
        msg = await canal.fetch_message(msg_id)
    except:
        return

    participantes = []
    for reaccion in msg.reactions:
        if str(reaccion.emoji) == "🎉":
            async for user in reaccion.users():
                if not user.bot:
                    participantes.append(user)

    if not participantes:
        embed = discord.Embed(title="🎁 Sorteo finalizado", description="No hubo participantes 😢", color=0xe74c3c)
    else:
        ganador = random.choice(participantes)
        info = sorteos_activos[msg_id]
        embed = discord.Embed(
            title="🎉 ¡GANADOR DEL SORTEO!",
            description=f"**Premio:** {info['premio']}\n\n🏆 Ganador: {ganador.mention} ¡Felicidades!",
            color=0x2ecc71
        )
    await canal.send(embed=embed)

@bot.command(name="reroll")
async def reroll(ctx, mensaje_id: int):
    rol_owner = ctx.guild.get_role(ROL_OWNER_ID)
    if not (rol_owner and rol_owner in ctx.author.roles):
        await ctx.send("❌ Solo los Owners.", delete_after=5)
        return
    try:
        msg = await ctx.channel.fetch_message(mensaje_id)
    except:
        await ctx.send("❌ No encontré ese mensaje.", delete_after=5)
        return
    participantes = []
    for reaccion in msg.reactions:
        if str(reaccion.emoji) == "🎉":
            async for user in reaccion.users():
                if not user.bot:
                    participantes.append(user)
    if not participantes:
        await ctx.send("❌ No hay participantes.")
        return
    ganador = random.choice(participantes)
    await ctx.send(embed=discord.Embed(
        title="🔁 Nuevo ganador",
        description=f"🏆 {ganador.mention} ¡Felicidades!",
        color=0x2ecc71
    ))

# ══════════════════════════════════════════
#                 ENCUESTAS
# ══════════════════════════════════════════

@bot.command(name="encuesta")
async def encuesta(ctx, *, pregunta: str):
    embed = discord.Embed(title="📊 Encuesta", description=pregunta, color=0x3498db)
    embed.set_footer(text=f"Por {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    try:
        await ctx.message.delete()
    except:
        pass

@bot.command(name="encuesta2")
async def encuesta2(ctx, *, contenido: str):
    partes = [p.strip() for p in contenido.split("|")]
    if len(partes) < 3:
        await ctx.send("❌ Uso: `!encuesta2 pregunta | opción1 | opción2 | ...`", delete_after=8)
        return
    pregunta = partes[0]
    opciones = partes[1:][:5]
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    desc = "\n".join(f"{emojis[i]} {op}" for i, op in enumerate(opciones))
    embed = discord.Embed(title=f"📊 {pregunta}", description=desc, color=0x3498db)
    embed.set_footer(text=f"Por {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    for i in range(len(opciones)):
        await msg.add_reaction(emojis[i])
    try:
        await ctx.message.delete()
    except:
        pass

# ══════════════════════════════════════════
#             NIVELES / RANKING
# ══════════════════════════════════════════

@bot.command(name="nivel")
async def nivel(ctx, usuario: discord.Member = None):
    usuario = usuario or ctx.author
    data = xp_data.get(usuario.id, {"xp": 0, "level": 1, "mensajes": 0})
    xp_actual = data["xp"]
    nivel_actual = data["level"]
    xp_siguiente = get_xp_for_level(nivel_actual)
    porcentaje = min(int((xp_actual / xp_siguiente) * 20), 20)
    barra = "█" * porcentaje + "░" * (20 - porcentaje)

    embed = discord.Embed(title=f"🏆 Nivel de {usuario.display_name}", color=0xf1c40f)
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="Nivel", value=str(nivel_actual), inline=True)
    embed.add_field(name="XP", value=f"{xp_actual}/{xp_siguiente}", inline=True)
    embed.add_field(name="Mensajes", value=str(data["mensajes"]), inline=True)
    embed.add_field(name="Progreso", value=f"`{barra}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="top")
async def top(ctx):
    if not xp_data:
        await ctx.send("No hay datos de XP todavía.")
        return
    sorted_users = sorted(xp_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]
    medallas = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = []
    for i, (uid, data) in enumerate(sorted_users):
        member = ctx.guild.get_member(uid)
        nombre = member.display_name if member else f"<@{uid}>"
        lines.append(f"{medallas[i]} **#{i+1}** {nombre} — Nv. {data['level']} ({data['xp']} XP)")
    embed = discord.Embed(title="🏆 Top 10 — Ranking XP", description="\n".join(lines), color=0xf1c40f)
    await ctx.send(embed=embed)

@bot.command(name="cumple")
async def cumple(ctx, fecha: str):
    import re
    if not re.match(r"\d{2}/\d{2}", fecha):
        await ctx.send("❌ Formato: `!cumple DD/MM`", delete_after=5)
        return
    cumpleanos_data[ctx.author.id] = fecha
    await ctx.send(embed=discord.Embed(
        description=f"🎂 Cumpleaños de {ctx.author.mention} registrado: **{fecha}** ¡Lo recordaremos!",
        color=0xe91e8c
    ))

# ══════════════════════════════════════════
#               MODERACIÓN
# ══════════════════════════════════════════

def es_owner(ctx):
    rol = ctx.guild.get_role(ROL_OWNER_ID)
    return rol and rol in ctx.author.roles

@bot.command(name="kick")
async def kick(ctx, miembro: discord.Member, *, razon: str = "Sin razón especificada"):
    if not es_owner(ctx):
        return await ctx.send("❌ Sin permisos.", delete_after=5)
    await miembro.kick(reason=razon)
    embed = discord.Embed(title="👢 Kick", description=f"{miembro.mention} expulsado.\n**Razón:** {razon}", color=0xe74c3c)
    await ctx.send(embed=embed)
    log_ch = ctx.guild.get_channel(LOG_CH_ID)
    if log_ch:
        await log_ch.send(embed=embed)

@bot.command(name="ban")
async def ban(ctx, miembro: discord.Member, *, razon: str = "Sin razón especificada"):
    if not es_owner(ctx):
        return await ctx.send("❌ Sin permisos.", delete_after=5)
    await miembro.ban(reason=razon)
    embed = discord.Embed(title="🔨 Ban", description=f"{miembro.mention} baneado.\n**Razón:** {razon}", color=0xe74c3c)
    await ctx.send(embed=embed)
    log_ch = ctx.guild.get_channel(LOG_CH_ID)
    if log_ch:
        await log_ch.send(embed=embed)

@bot.command(name="unban")
async def unban(ctx, user_id: int):
    if not es_owner(ctx):
        return await ctx.send("❌ Sin permisos.", delete_after=5)
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(embed=discord.Embed(description=f"✅ **{user}** desbaneado.", color=0x2ecc71))
    except:
        await ctx.send("❌ No encontré ese usuario.", delete_after=5)

@bot.command(name="mute")
async def mute(ctx, miembro: discord.Member, tiempo: str = "10m"):
    if not es_owner(ctx):
        return await ctx.send("❌ Sin permisos.", delete_after=5)
    segundos = parsear_tiempo(tiempo) or 600
    duracion = timedelta(seconds=segundos)
    try:
        await miembro.timeout(duracion, reason="Mute por Owner")
        await ctx.send(embed=discord.Embed(
            description=f"🔇 {miembro.mention} silenciado por **{tiempo}**.",
            color=0xe74c3c
        ))
    except Exception as e:
        await ctx.send(f"❌ Error: {e}", delete_after=5)

@bot.command(name="unmute")
async def unmute(ctx, miembro: discord.Member):
    if not es_owner(ctx):
        return await ctx.send("❌ Sin permisos.", delete_after=5)
    await miembro.timeout(None)
    await ctx.send(embed=discord.Embed(description=f"🔊 {miembro.mention} desmuteado.", color=0x2ecc71))

@bot.command(name="clear")
async def clear(ctx, cantidad: int = 10):
    if not es_owner(ctx):
        return await ctx.send("❌ Sin permisos.", delete_after=5)
    cantidad = min(cantidad, 100)
    borrados = await ctx.channel.purge(limit=cantidad + 1)
    await ctx.send(embed=discord.Embed(
        description=f"🗑️ {len(borrados) - 1} mensajes eliminados.",
        color=0xe74c3c
    ), delete_after=4)

warns_data = {}

@bot.command(name="warn")
async def warn(ctx, miembro: discord.Member, *, razon: str = "Sin razón"):
    if not es_owner(ctx):
        return await ctx.send("❌ Sin permisos.", delete_after=5)
    if miembro.id not in warns_data:
        warns_data[miembro.id] = []
    warns_data[miembro.id].append({"razon": razon, "por": ctx.author.display_name})
    total = len(warns_data[miembro.id])
    try:
        await miembro.send(embed=discord.Embed(
            title=f"⚠️ Advertencia en {ctx.guild.name}",
            description=f"**Razón:** {razon}\n**Warns totales:** {total}",
            color=0xf39c12
        ))
    except:
        pass
    embed = discord.Embed(
        title="⚠️ Warn",
        description=f"{miembro.mention} advertido.\n**Razón:** {razon}\n**Total warns:** {total}",
        color=0xf39c12
    )
    await ctx.send(embed=embed)
    log_ch = ctx.guild.get_channel(LOG_CH_ID)
    if log_ch:
        await log_ch.send(embed=embed)

@bot.command(name="slowmode")
async def slowmode(ctx, segundos: int = 0):
    if not es_owner(ctx):
        return await ctx.send("❌ Sin permisos.", delete_after=5)
    await ctx.channel.edit(slowmode_delay=segundos)
    if segundos == 0:
        await ctx.send("✅ Slowmode desactivado.")
    else:
        await ctx.send(f"🐢 Slowmode de **{segundos}s** activado.")

# ══════════════════════════════════════════
#                 UTILIDADES
# ══════════════════════════════════════════

@bot.command(name="ping")
async def ping(ctx):
    latencia = round(bot.latency * 1000)
    color = 0x2ecc71 if latencia < 100 else 0xf39c12 if latencia < 200 else 0xe74c3c
    await ctx.send(embed=discord.Embed(title="🏓 Pong!", description=f"Latencia: **{latencia}ms**", color=color))

@bot.command(name="info")
async def info(ctx, usuario: discord.Member = None):
    usuario = usuario or ctx.author
    embed = discord.Embed(title=f"ℹ️ Info de {usuario.display_name}", color=usuario.color)
    embed.set_thumbnail(url=usuario.display_avatar.url)
    embed.add_field(name="ID", value=usuario.id, inline=True)
    embed.add_field(name="Cuenta creada", value=usuario.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Se unió", value=usuario.joined_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Roles", value=" ".join(r.mention for r in usuario.roles[1:][:5]) or "Ninguno", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="servidor")
async def servidor(ctx):
    g = ctx.guild
    embed = discord.Embed(title=f"🏛️ {g.name}", color=0x3498db)
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="👑 Owner", value=g.owner.mention, inline=True)
    embed.add_field(name="👥 Miembros", value=g.member_count, inline=True)
    embed.add_field(name="📅 Creado", value=g.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="📢 Canales", value=len(g.text_channels), inline=True)
    embed.add_field(name="🎭 Roles", value=len(g.roles), inline=True)
    await ctx.send(embed=embed)

@bot.command(name="avatar")
async def avatar(ctx, usuario: discord.Member = None):
    usuario = usuario or ctx.author
    embed = discord.Embed(title=f"🖼️ Avatar de {usuario.display_name}", color=0x9b59b6)
    embed.set_image(url=usuario.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="sugerencia")
async def sugerencia(ctx, *, texto: str):
    canal = ctx.guild.get_channel(SUGERENCIAS_CH_ID) if SUGERENCIAS_CH_ID else ctx.channel
    embed = discord.Embed(
        title="💡 Nueva Sugerencia",
        description=texto,
        color=0x3498db
    )
    embed.set_footer(text=f"Por {ctx.author.display_name}")
    msg = await canal.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await ctx.send("✅ Sugerencia enviada.", delete_after=5)
    try:
        await ctx.message.delete()
    except:
        pass

# ══════════════════════════════════════════
#                  ON READY
# ══════════════════════════════════════════

ESTADOS = [
    ("watching", "!ayuda | VaultBot"),
    ("playing",  "🎮 !dado !moneda !8ball !ruleta"),
    ("playing",  "🎁 !sorteo 2h Premio"),
    ("playing",  "📊 !encuesta !encuesta2"),
    ("playing",  "🏆 !nivel !top !cumple"),
    ("playing",  "🔨 !kick !ban !mute !warn !clear"),
    ("playing",  "💡 !ping !info !avatar !servidor"),
    ("playing",  "🎵 !pp !ship !iq !rps !chiste !meme"),
    ("watching", "el servidor 👀"),
]
estado_idx = 0

@tasks.loop(seconds=15)
async def rotar_estado():
    global estado_idx
    tipo_str, texto = ESTADOS[estado_idx % len(ESTADOS)]
    estado_idx += 1
    tipo = discord.ActivityType.watching if tipo_str == "watching" else discord.ActivityType.playing
    await bot.change_presence(activity=discord.Activity(type=tipo, name=texto))

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    bot.add_view(VistaVerificacion())
    bot.add_view(VistaTicket())
    bot.add_view(VistaMusicPanel())
    bot.add_view(VistaAyuda())
    await enviar_panel_verificacion()
    await enviar_panel_tickets()
    await enviar_panel_musica()
    rotar_estado.start()
    # Limpiar cualquier sesión de voz sucia en segundo plano, sin bloquear el arranque
    guild = bot.get_guild(GUILD_ID)
    if guild:
        asyncio.create_task(limpiar_vc(guild))
    print("✅ Todos los paneles enviados.")

try:
    bot.run(TOKEN)
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
