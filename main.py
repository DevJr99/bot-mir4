import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime
import os
import threading
from flask import Flask
import psycopg2

# --- CONFIGURAÇÕES ---
TOKEN = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ID_CANAL_BEM_VINDO = 1317651351584378930  # Substitua pelo ID real
ID_CANAL_LIDERANCA = 1491190966067921177  # Substitua pelo ID real

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# --- CLASSE DO BOT PARA SINCRONIZAR SLASH COMMANDS ---
class Mir4Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Sincroniza os comandos com o Discord
        await self.tree.sync()
        print(f"Comandos de barra (/) sincronizados com sucesso!")

bot = Mir4Bot()

# --- FUNÇÃO DE CONEXÃO POSTGRESQL ---
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro no banco: {e}")
        return None

def iniciar_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS membros (
                            user_id BIGINT PRIMARY KEY, 
                            nick VARCHAR(255), 
                            classe VARCHAR(50), 
                            power INTEGER, 
                            lvl INTEGER, 
                            data_registro TIMESTAMP
                        )''')
        conn.commit()
        cursor.close()
        conn.close()

@bot.event
async def on_ready():
    iniciar_db()
    print(f'Bot {bot.user} online no PostgreSQL!')
    if not relatorio_lideranca.is_running():
        relatorio_lideranca.start()

# --- 1. SLASH COMMAND: REGISTRAR ---
@bot.tree.command(name="registrar", description="Registra seu personagem no clã")
@app_commands.describe(nick="Seu nome no jogo", classe="Sua classe", power="Seu Power Score", lvl="Seu Level")
async def registrar(interaction: discord.Interaction, nick: str, classe: str, power: int, lvl: int):
    # Responde apenas para o usuário (ephemeral)
    await interaction.response.send_message("Processando seu registro...", ephemeral=True)
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO membros (user_id, nick, classe, power, lvl, data_registro) 
                          VALUES (%s, %s, %s, %s, %s, %s)
                          ON CONFLICT (user_id) 
                          DO UPDATE SET nick = EXCLUDED.nick, classe = EXCLUDED.classe, 
                          power = EXCLUDED.power, lvl = EXCLUDED.lvl, data_registro = EXCLUDED.data_registro''', 
                       (interaction.user.id, nick, classe, power, lvl, datetime.now()))
        conn.commit()
        cursor.close()
        conn.close()

        try:
            novo_apelido = f"{nick} | {classe}"[0:32]
            await interaction.user.edit(nick=novo_apelido)
        except:
            pass
        
        await interaction.edit_original_response(content="✅ Registro salvo e apelido atualizado!")

# --- 2. SLASH COMMAND: ATUALIZAR ---
@bot.tree.command(name="atualizar", description="Atualiza seu Power e Level")
async def atualizar(interaction: discord.Interaction, power: int, lvl: int):
    await interaction.response.send_message("Atualizando dados...", ephemeral=True)
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nick FROM membros WHERE user_id = %s", (interaction.user.id,))
        if not cursor.fetchone():
            await interaction.edit_original_response(content="❌ Você não está registrado! Use /registrar primeiro.")
            return

        cursor.execute("UPDATE membros SET power = %s, lvl = %s, data_registro = %s WHERE user_id = %s", 
                       (power, lvl, datetime.now(), interaction.user.id))
        conn.commit()
        cursor.close()
        conn.close()
        await interaction.edit_original_response(content=f"✅ Status atualizado: PS {power:,} | Lvl {lvl}")

# --- 3. SLASH COMMAND: REMOVER (ADMIN) ---
@bot.tree.command(name="remover", description="Remove um membro do banco de dados (Apenas Liderança)")
@app_commands.checks.has_permissions(administrator=True)
async def remover(interaction: discord.Interaction, membro: discord.Member):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM membros WHERE user_id = %s", (membro.id,))
        conn.commit()
        cursor.close()
        conn.close()
        await interaction.response.send_message(f"🗑️ Membro {membro.display_name} removido do sistema.")

# --- 4. RELATÓRIO 48H ---
@tasks.loop(hours=48)
async def relatorio_lideranca():
    canal = bot.get_channel(ID_CANAL_LIDERANCA)
    if not canal: return

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nick, classe, power, lvl FROM membros ORDER BY power DESC")
        membros = cursor.fetchall()
        cursor.close()
        conn.close()

        if membros:
            embed = discord.Embed(title="📊 Relatório de Progresso do Clã", color=discord.Color.red())
            nicks = "\n".join([f"{m[0]} ({m[1]})" for m in membros])
            stats = "\n".join([f"Lvl: {m[3]} | PS: {m[2]:,}" for m in membros])
            embed.add_field(name="Membro", value=nicks, inline=True)
            embed.add_field(name="Status", value=stats, inline=True)
            await canal.send(embed=embed)

# --- FLASK SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Online!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask).start()
bot.run(TOKEN)
