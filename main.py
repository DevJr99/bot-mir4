import discord
from discord.ext import commands, tasks
from datetime import datetime
import os
import threading
from flask import Flask
import psycopg2 # A biblioteca nova para o PostgreSQL

# --- CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE ---
TOKEN = os.getenv('DISCORD_TOKEN') 
DATABASE_URL = os.getenv('DATABASE_URL') # Puxamos a URL do banco do Render!
ID_CANAL_BEM_VINDO = 123456789012345678  # Substitua pelo ID real
ID_CANAL_LIDERANCA = 987654321098765432  # Substitua pelo ID real

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- FUNÇÃO DE CONEXÃO COM O BANCO (NOVO) ---
# Criamos essa função para ser chamada toda vez que precisarmos do banco.
def get_db_connection():
    try:
        # Tenta conectar usando a URL que você colocou nas configurações
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro crítico ao conectar no banco de dados: {e}")
        return None

def iniciar_db():
    conn = get_db_connection()
    if conn is None:
        return
        
    cursor = conn.cursor()
    # A sintaxe do PostgreSQL é um pouco diferente do SQLite (SERIAL em vez de INTEGER PRIMARY KEY)
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
    print(f'Bot {bot.user} online e conectado ao PostgreSQL!')
    if not relatorio_lideranca.is_running():
        relatorio_lideranca.start()

# --- 1. BOAS VINDAS ---
@bot.event
async def on_member_join(member):
    canal = bot.get_channel(ID_CANAL_BEM_VINDO)
    if canal:
        mensagem = (f"Bem-vindo(a) ao Clã, {member.mention}!\n\n"
                    f"Registre seu personagem digitando:\n"
                    f"`!registrar [SeuNick] [SuaClasse] [Power] [Level]`")
        await canal.send(mensagem)

# --- 2. AUTO-REMOÇÃO ---
@bot.event
async def on_member_remove(member):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # O PostgreSQL prefere %s em vez de ? para as variáveis
        cursor.execute("DELETE FROM membros WHERE user_id = %s", (member.id,))
        conn.commit()
        cursor.close()
        conn.close()

# --- 3. REGISTRAR ---
@bot.command()
async def registrar(ctx, nick: str, classe: str, power: int, lvl: int):
    conn = get_db_connection()
    if not conn:
        await ctx.send("❌ Erro de conexão com o banco de dados. Tente novamente mais tarde.", delete_after=5)
        return

    cursor = conn.cursor()
    # O PostgreSQL usa ON CONFLICT em vez de INSERT OR REPLACE
    cursor.execute('''INSERT INTO membros (user_id, nick, classe, power, lvl, data_registro) 
                      VALUES (%s, %s, %s, %s, %s, %s)
                      ON CONFLICT (user_id) 
                      DO UPDATE SET nick = EXCLUDED.nick, classe = EXCLUDED.classe, power = EXCLUDED.power, lvl = EXCLUDED.lvl, data_registro = EXCLUDED.data_registro''', 
                   (ctx.author.id, nick, classe, power, lvl, datetime.now()))
    conn.commit()
    cursor.close()
    conn.close()

    try:
        novo_apelido = f"{nick} | {classe}"[0:32]
        await ctx.author.edit(nick=novo_apelido)
    except Exception as e:
        print("Aviso: Não consegui mudar o nick.")

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(f"✅ {ctx.author.mention}, registro salvo com segurança!", delete_after=5)

# --- 4. ATUALIZAR STATUS ---
@bot.command()
async def atualizar(ctx, power: int, lvl: int):
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    cursor.execute("SELECT nick FROM membros WHERE user_id = %s", (ctx.author.id,))
    if not cursor.fetchone():
        await ctx.send(f"❌ {ctx.author.mention}, registre-se primeiro com `!registrar`.", delete_after=10)
        cursor.close()
        conn.close()
        return

    cursor.execute('''UPDATE membros SET power = %s, lvl = %s, data_registro = %s 
                      WHERE user_id = %s''', (power, lvl, datetime.now(), ctx.author.id))
    conn.commit()
    cursor.close()
    conn.close()

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(f"✅ {ctx.author.mention}, status atualizado!", delete_after=5)

# --- 5. REMOVER MEMBRO MANUALMENTE ---
@bot.command()
@commands.has_permissions(administrator=True)
async def remover(ctx, membro: discord.Member):
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()
    cursor.execute("DELETE FROM membros WHERE user_id = %s", (membro.id,))
    conn.commit()
    cursor.close()
    conn.close()
    await ctx.send(f"🗑️ Membro removido por {ctx.author.mention}.")

# --- 6. RELATÓRIO A CADA 48 HORAS ---
@tasks.loop(hours=48)
async def relatorio_lideranca():
    canal = bot.get_channel(ID_CANAL_LIDERANCA)
    if not canal:
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()
    cursor.execute("SELECT nick, classe, power, lvl FROM membros ORDER BY power DESC")
    membros = cursor.fetchall()
    cursor.close()
    conn.close()

    if not membros:
        return

    embed = discord.Embed(title="📊 Relatório do Clã (48h)", color=discord.Color.red())
    lista_nicks = ""
    lista_stats = ""
    for m in membros:
        lista_nicks += f"{m[0]} ({m[1]})\n"
        lista_stats += f"Lvl: {m[3]} | PS: {m[2]:,}\n"

    embed.add_field(name="Membro", value=lista_nicks, inline=True)
    embed.add_field(name="Status", value=lista_stats, inline=True)
    await canal.send(embed=embed)


# --- 7. O MINI-SERVIDOR WEB ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot online!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask).start()

bot.run(TOKEN)
