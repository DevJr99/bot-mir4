import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime
import os
import threading
from flask import Flask

# --- CONFIGURAÇÕES ---
TOKEN = os.getenv('DISCORD_TOKEN') 
ID_CANAL_BEM_VINDO = 1317651351584378930  # Substitua pelo ID real
ID_CANAL_LIDERANCA = 1491190966067921177 # Substitua pelo ID real

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- BANCO DE DADOS ---
def iniciar_db():
    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS membros 
                      (user_id INTEGER PRIMARY KEY, nick TEXT, classe TEXT, power INTEGER, lvl INTEGER, data_registro TIMESTAMP)''')
    conn.commit()
    conn.close()

@bot.event
async def on_ready():
    iniciar_db()
    print(f'Bot {bot.user} online e pronto para o MIR4!')
    if not relatorio_lideranca.is_running():
        relatorio_lideranca.start()

# --- 1. BOAS VINDAS E INSTRUÇÃO ---
@bot.event
async def on_member_join(member):
    canal = bot.get_channel(ID_CANAL_BEM_VINDO)
    if canal:
        mensagem = (f"Bem-vindo(a) ao Clã, {member.mention}!\n\n"
                    f"Registre seu personagem digitando:\n"
                    f"`!registrar [SeuNick] [SuaClasse] [Power] [Level]`")
        await canal.send(mensagem)

# --- 2. AUTO-REMOÇÃO (SE O MEMBRO SAIR DO SERVIDOR) ---
@bot.event
async def on_member_remove(member):
    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM membros WHERE user_id = ?", (member.id,))
    conn.commit()
    conn.close()

# --- 3. REGISTRO COM PRIVACIDADE ---
@bot.command()
async def registrar(ctx, nick: str, classe: str, power: int, lvl: int):
    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO membros (user_id, nick, classe, power, lvl, data_registro) 
                      VALUES (?, ?, ?, ?, ?, ?)''', (ctx.author.id, nick, classe, power, lvl, datetime.now()))
    conn.commit()
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

    await ctx.send(f"✅ {ctx.author.mention}, registro salvo!", delete_after=5)

# --- 4. ATUALIZAR STATUS ---
@bot.command()
async def atualizar(ctx, power: int, lvl: int):
    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()

    cursor.execute("SELECT nick FROM membros WHERE user_id = ?", (ctx.author.id,))
    if not cursor.fetchone():
        await ctx.send(f"❌ {ctx.author.mention}, registre-se primeiro com `!registrar`.", delete_after=10)
        conn.close()
        return

    cursor.execute('''UPDATE membros SET power = ?, lvl = ?, data_registro = ? 
                      WHERE user_id = ?''', (power, lvl, datetime.now(), ctx.author.id))
    conn.commit()
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
    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM membros WHERE user_id = ?", (membro.id,))
    conn.commit()
    conn.close()
    await ctx.send(f"🗑️ Membro removido por {ctx.author.mention}.")

# --- 6. RELATÓRIO A CADA 48 HORAS ---
@tasks.loop(hours=48)
async def relatorio_lideranca():
    canal = bot.get_channel(ID_CANAL_LIDERANCA)
    if not canal:
        return

    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nick, classe, power, lvl FROM membros ORDER BY power DESC")
    membros = cursor.fetchall()
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


# --- 7. O MINI-SERVIDOR WEB (NOVIDADE PARA O RENDER) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot online!"

def run_flask():
    # O Render usa a porta 10000 por padrão, ou puxa da variável de ambiente PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Inicia o servidor Flask em uma "thread" separada para não travar o bot do Discord
threading.Thread(target=run_flask).start()

# Inicia o bot
bot.run(TOKEN)
