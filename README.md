# 🏛️ VaultBot

Bot de gestión completo para servidores de Discord.  
Incluye: bienvenida, despedida, verificación por reacción y sistema de tickets.

---

## 📁 Archivos

```
VaultBot/
├── bot.py            ← Código principal del bot
├── requirements.txt  ← Librerías necesarias
└── README.md         ← Esta guía
```

---

## ⚙️ Instalación

### 1. Instala Python
Necesitas **Python 3.10 o superior**.  
Descárgalo en: https://www.python.org/downloads/

### 2. Instala las dependencias
Abre una terminal dentro de la carpeta VaultBot y ejecuta:
```
pip install -r requirements.txt
```

### 3. Crea tu bot en Discord
1. Ve a https://discord.com/developers/applications
2. Pulsa **New Application** → ponle nombre
3. Ve a **Bot** → pulsa **Add Bot**
4. Copia el **TOKEN** (lo necesitarás después)
5. En **Privileged Gateway Intents** activa:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
6. Ve a **OAuth2 → URL Generator**:
   - Marca `bot` y `applications.commands`
   - En permisos marca: `Administrator`
   - Copia la URL generada e invita el bot a tu servidor

---

## 🔧 Configuración del bot.py

Abre `bot.py` y rellena la sección **CONFIGURACIÓN** al principio del archivo.

### ¿Cómo obtener los IDs?
En Discord: **Ajustes → Avanzado → Modo desarrollador → ON**  
Luego clic derecho sobre cualquier canal, rol o servidor → **Copiar ID**

---

### TOKEN
```python
TOKEN = "TU_TOKEN_AQUI"
```
> Tu token secreto del bot. Nunca lo compartas con nadie.  
> Lo encuentras en: Discord Developers → Tu app → Bot → Token

---

### GUILD_ID
```python
GUILD_ID = 1496981659655078000
```
> ID de tu servidor de Discord.  
> Clic derecho sobre el nombre del servidor → Copiar ID del servidor.

---

### BIENVENIDA_CH_ID
```python
BIENVENIDA_CH_ID = 1496982319112913086
```
> ID del canal donde aparecerán los mensajes de bienvenida cuando alguien se una.  
> Ejemplo: canal llamado `👋・bienvenida`

---

### DESPEDIDA_CH_ID
```python
DESPEDIDA_CH_ID = 1496982512205828248
```
> ID del canal donde aparecerán los mensajes de despedida cuando alguien se vaya.  
> Ejemplo: canal llamado `👋・despedida`

---

### VERIFICACION_CH_ID
```python
VERIFICACION_CH_ID = 1496988696455413770
```
> ID del canal donde el bot publicará el mensaje de verificación.  
> Ejemplo: canal llamado `✅・verificarse`  
> Los usuarios reaccionarán aquí con ✅ para obtener el rol verificado.

---

### TICKETS_CH_ID
```python
TICKETS_CH_ID = 1496983520726482994
```
> ID del canal donde el bot publicará el panel de tickets con el botón de "Abrir Ticket".  
> Ejemplo: canal llamado `🎫・tickets`

---

### TICKETS_CATEGORY_ID
```python
TICKETS_CATEGORY_ID = 1496982211432415393
```
> ID de la CATEGORÍA donde se crearán los canales de tickets.  
> Clic derecho sobre la categoría → Copiar ID.  
> Ejemplo: categoría llamada `🎫 TICKETS`

---

### LOG_CH_ID
```python
LOG_CH_ID = 1496999027391332452
```
> ID del canal de logs donde el bot notificará cuando se abra o cierre un ticket.  
> Solo el Owner debería ver este canal.  
> Ejemplo: canal llamado `📋・logs`

---

### ROL_NO_VERIFICADO_ID
```python
ROL_NO_VERIFICADO_ID = 1496987179174592712
```
> ID del rol que se asigna automáticamente al entrar al servidor.  
> En tu servidor debería llamarse `❌ Miembro No Verificado`  
> Clic derecho sobre el rol en la lista de miembros → Copiar ID.

---

### ROL_VERIFICADO_ID
```python
ROL_VERIFICADO_ID = 1496987032071700530
```
> ID del rol que se asigna cuando el usuario reacciona con ✅ en el canal de verificación.  
> En tu servidor debería llamarse `✅ Miembro Verificado`

---

### ROL_OWNER_ID
```python
ROL_OWNER_ID = 1496986693457285272
```
> ID del rol de administrador principal.  
> En tu servidor se llama `👑 Owner`  
> Este rol puede ver y cerrar todos los tickets.

---

### FOTO_BIENVENIDA
```python
FOTO_BIENVENIDA = "https://i.imgur.com/TUIMAGEN.png"
```
> URL directa de la imagen que aparece en el embed de bienvenida.  
> Para subir tu imagen: ve a https://imgur.com → sube la foto → clic derecho → Copiar dirección de imagen.  
> La URL debe terminar en `.png`, `.jpg` o `.gif`

---

### SEGUNDOS_BORRAR
```python
SEGUNDOS_BORRAR = 5
```
> Segundos que tarda en borrarse el canal de un ticket tras cerrarlo.  
> Puedes cambiarlo al número que quieras.

---

## 🚀 Ejecutar el bot

Una vez configurado todo, ejecuta en la terminal:
```
python bot.py
```

Si ves `✅ Bot conectado como VaultBot#XXXX` en la terminal, ¡está funcionando!

---

## ✅ Checklist antes de arrancar

- [ ] Token copiado correctamente
- [ ] Todos los IDs rellenados (no dejes ningún `000000000000000000`)
- [ ] Rol `❌ Miembro No Verificado` creado y con pocos permisos
- [ ] Rol `✅ Miembro Verificado` creado con acceso al servidor
- [ ] Categoría para tickets creada
- [ ] Canal de logs creado (solo visible para Owner)
- [ ] Bot invitado al servidor con permisos de Administrador
- [ ] Intents activados en el portal de desarrolladores

---

## ❓ Problemas frecuentes

| Error | Solución |
|---|---|
| `Forbidden` al asignar roles | El rol del bot debe estar POR ENCIMA de los demás roles en la jerarquía |
| El bot no reacciona en verificación | Asegúrate de tener **Message Content Intent** activado |
| No se crean los canales de ticket | Comprueba que el bot tiene permisos en la categoría |
| El bot se desconecta | Usa un servicio de hosting (Railway, Render, VPS) para tenerlo 24/7 |

---

*VaultBot — hecho con discord.py*
