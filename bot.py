import discord
from discord.ext import commands
import asyncio

# ─────────────────────────────────────────
#  CONFIGURACIÓN  —  edita solo esta sección
# ─────────────────────────────────────────
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

FOTO_BIENVENIDA = ""

EMOJI_VERIFICAR  = "✅"
SEGUNDOS_BORRAR  = 5
# ─────────────────────────────────────────

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

verificacion_msg_id = None

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="el servidor 👀"
    ))
    await enviar_panel_verificacion()
    await enviar_panel_tickets()


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    rol_no_ver = guild.get_role(ROL_NO_VERIFICADO_ID)
    if rol_no_ver:
        try:
            await member.add_roles(rol_no_ver, reason="Nuevo miembro — pendiente de verificación")
        except discord.Forbidden:
            print(f"⚠️ Sin permisos para asignar rol a {member.name}. Sube el rol del bot en la jerarquía de roles.")

    canal = guild.get_channel(BIENVENIDA_CH_ID)
    if canal:
        embed = discord.Embed(
            title="¡Bienvenido/a al servidor! 🎉",
            description=(
                f"Hey {member.mention}, nos alegra tenerte aquí.\n\n"
                f"📋 Dirígete a <#{VERIFICACION_CH_ID}> y reacciona con {EMOJI_VERIFICAR} "
                f"para verificarte y acceder al servidor completo."
            ),
            color=0x2ecc71
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_image(url=FOTO_BIENVENIDA)
        embed.set_footer(text=f"Miembro #{guild.member_count}")
        await canal.send(embed=embed)


@bot.event
async def on_member_remove(member: discord.Member):
    canal = member.guild.get_channel(DESPEDIDA_CH_ID)
    if canal:
        embed = discord.Embed(
            title="Hasta luego 👋",
            description=f"**{member.name}** ha abandonado el servidor.\nEsperamos verte de nuevo pronto.",
            color=0xe74c3c
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Ahora somos {member.guild.member_count} miembros")
        await canal.send(embed=embed)


async def enviar_panel_verificacion():
    global verificacion_msg_id
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
            "Para acceder al servidor completo debes verificarte.\n\n"
            f"**Reacciona con {EMOJI_VERIFICAR} a este mensaje** y recibirás "
            "el rol de Miembro Verificado automáticamente."
        ),
        color=0x2ecc71
    )
    embed.set_footer(text="Solo tienes que reaccionar una vez.")
    mensaje = await canal.send(embed=embed)
    await mensaje.add_reaction(EMOJI_VERIFICAR)
    verificacion_msg_id = mensaje.id


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    global verificacion_msg_id
    if payload.user_id == bot.user.id:
        return
    if payload.message_id != verificacion_msg_id:
        return
    if str(payload.emoji) != EMOJI_VERIFICAR:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member:
        return

    rol_ver    = guild.get_role(ROL_VERIFICADO_ID)
    rol_no_ver = guild.get_role(ROL_NO_VERIFICADO_ID)

    try:
        if rol_no_ver and rol_no_ver in member.roles:
            await member.remove_roles(rol_no_ver, reason="Verificado")
        if rol_ver and rol_ver not in member.roles:
            await member.add_roles(rol_ver, reason="Verificado mediante reacción")
            try:
                await member.send(f"✅ ¡Ya estás verificado/a en **{guild.name}**! Bienvenido/a 🎉")
            except discord.Forbidden:
                pass
    except discord.Forbidden:
        print(f"⚠️ Sin permisos para cambiar roles de {member.name}. Sube el rol del bot en la jerarquía.")


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
        description=(
            "¿Necesitas ayuda o tienes algún problema?\n\n"
            "Haz clic en el botón de abajo para abrir un ticket privado "
            "con el equipo de administración."
        ),
        color=0x3498db
    )
    embed.set_footer(text="Solo puedes tener un ticket abierto a la vez.")
    vista = VistaTicket()
    await canal.send(embed=embed, view=vista)


class VistaTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", emoji="🎫", style=discord.ButtonStyle.primary, custom_id="abrir_ticket")
    async def abrir_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        if member.id in tickets_abiertos:
            ch = guild.get_channel(tickets_abiertos[member.id])
            await interaction.response.send_message(
                f"⚠️ Ya tienes un ticket abierto: {ch.mention}", ephemeral=True
            )
            return

        categoria = guild.get_channel(TICKETS_CATEGORY_ID)
        rol_owner = guild.get_role(ROL_OWNER_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if rol_owner:
            overwrites[rol_owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_ch = await guild.create_text_channel(
            name=f"ticket-{member.name}",
            category=categoria,
            overwrites=overwrites,
            reason=f"Ticket de {member.name}"
        )
        tickets_abiertos[member.id] = ticket_ch.id

        embed = discord.Embed(
            title=f"🎫  Ticket de {member.display_name}",
            description=(
                f"Hola {member.mention}, el equipo te atenderá en breve.\n\n"
                "Explica tu problema con detalle.\n\n"
                "Cuando termines, pulsa **Cerrar Ticket** para cerrarlo."
            ),
            color=0x3498db
        )
        vista_cerrar = VistaCerrarTicket(member.id, ticket_ch.id)
        await ticket_ch.send(embed=embed, view=vista_cerrar)
        await interaction.response.send_message(
            f"✅ Ticket creado: {ticket_ch.mention}", ephemeral=True
        )

        log_ch = guild.get_channel(LOG_CH_ID)
        if log_ch:
            await log_ch.send(f"📩 **Nuevo ticket** abierto por {member.mention} → {ticket_ch.mention}")


class VistaCerrarTicket(discord.ui.View):
    def __init__(self, owner_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.channel_id = channel_id

    @discord.ui.button(label="Cerrar Ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="cerrar_ticket_base")
    async def cerrar_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        canal = interaction.channel
        guild = interaction.guild
        member = interaction.user

        rol_owner = guild.get_role(ROL_OWNER_ID)
        es_owner = rol_owner in member.roles if rol_owner else False
        if member.id != self.owner_id and not es_owner:
            await interaction.response.send_message(
                "❌ Solo el dueño del ticket o un Owner puede cerrarlo.", ephemeral=True
            )
            return

        # Deshabilitar botón ANTES de responder para evitar error 404
        button.disabled = True
        await interaction.response.edit_message(view=self)

        await canal.send(f"🔒 Ticket cerrado. Este canal se borrará en **{SEGUNDOS_BORRAR} segundos**...")
        
        log_ch = guild.get_channel(LOG_CH_ID)
        if log_ch:
            usuario = guild.get_member(self.owner_id)
            nombre = usuario.mention if usuario else f"<@{self.owner_id}>"
            await log_ch.send(f"🔒 **Ticket cerrado** — era de {nombre}, cerrado por {member.mention}.")

        if self.owner_id in tickets_abiertos:
            del tickets_abiertos[self.owner_id]

        await asyncio.sleep(SEGUNDOS_BORRAR)
        await canal.delete(reason="Ticket cerrado")


bot.run(TOKEN)
