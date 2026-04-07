import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime
import os

# --- CONFIGURAÇÕES ---
# O Token será puxado da configuração segura da Square Cloud
TOKEN = os.getenv('DISCORD_TOKEN') 
ID_CANAL_BEM_VINDO = 123456789012345678  # Substitua pelo ID do canal de entrada
ID_CANAL_LIDERANCA = 987654321098765432  # Substitua pelo ID do canal privado dos líderes

intents = discord.Intents.default()
intents.members = True # Necessário para ler quem entra, quem sai e mudar apelidos
intents.message_content = True # Necessário para ler os comandos

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
                    f"Para liberar seu acesso, registre seu personagem. Fique tranquilo, **seus dados ficarão ocultos** dos outros membros.\n"
                    f"Digite o comando:\n"
                    f"`!registrar [SeuNick] [SuaClasse] [Power] [Level]`\n\n"
                    f"**Exemplo:** `!registrar MagoSupremo Mago 150000 85`")
        await canal.send(mensagem)

# --- 2. AUTO-REMOÇÃO (SE O MEMBRO SAIR DO SERVIDOR) ---
@bot.event
async def on_member_remove(member):
    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM membros WHERE user_id = ?", (member.id,))
    conn.commit()
    conn.close()

    # Opcional: Avisa a liderança que os dados de quem saiu foram apagados
    canal = bot.get_channel(ID_CANAL_LIDERANCA)
    if canal:
        await canal.send(f"⚠️ O membro **{member.display_name}** saiu do Discord e seus dados foram apagados do sistema.")

# --- 3. REGISTRO COM PRIVACIDADE E MUDANÇA DE NICK ---
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
        print(f"Aviso: Não consegui mudar o nick de {ctx.author.name}.")

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(f"✅ {ctx.author.mention}, registro salvo! Seu nick foi atualizado e seus dados foram enviados à liderança.", delete_after=5)

# --- 4. ATUALIZAR STATUS (POWER E LEVEL) ---
@bot.command()
async def atualizar(ctx, power: int, lvl: int):
    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()

    cursor.execute("SELECT nick FROM membros WHERE user_id = ?", (ctx.author.id,))
    resultado = cursor.fetchone()

    if not resultado:
        await ctx.send(f"❌ {ctx.author.mention}, você ainda não está registrado! Use o comando `!registrar` primeiro.", delete_after=10)
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

    await ctx.send(f"✅ {ctx.author.mention}, status atualizado! Lvl: {lvl} | PS: {power:,}", delete_after=5)

# --- 5. REMOVER MEMBRO MANUALMENTE (EXCLUSIVO LIDERANÇA) ---
@bot.command()
@commands.has_permissions(administrator=True) # Apenas administradores do servidor
async def remover(ctx, membro: discord.Member):
    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()

    cursor.execute("SELECT nick FROM membros WHERE user_id = ?", (membro.id,))
    resultado = cursor.fetchone()

    if not resultado:
        await ctx.send(f"❌ {membro.display_name} não está registrado no banco de dados.", delete_after=10)
        conn.close()
        return

    cursor.execute("DELETE FROM membros WHERE user_id = ?", (membro.id,))
    conn.commit()
    conn.close()

    await ctx.send(f"🗑️ O personagem **{resultado[0]}** foi removido do banco de dados por {ctx.author.mention}.")

@remover.error
async def remover_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão da liderança para usar este comando!", delete_after=5)
        try:
            await ctx.message.delete()
        except:
            pass

# --- 6. RELATÓRIO A CADA 48 HORAS (LIDERANÇA) ---
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

    embed = discord.Embed(
        title="📊 Relatório de Progresso do Clã (48h)",
        description="Atualização de Power e Level dos membros registrados.",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )

    lista_nicks = ""
    lista_stats = ""

    for m in membros:
        nick, classe, power, lvl = m
        lista_nicks += f"{nick} ({classe})\n"
        lista_stats += f"Lvl: {lvl} | PS: {power:,}\n"

    embed.add_field(name="Membro", value=lista_nicks, inline=True)
    embed.add_field(name="Status (Power / Lvl)", value=lista_stats, inline=True)
    
    await canal.send(embed=embed)

bot.run(TOKEN)
