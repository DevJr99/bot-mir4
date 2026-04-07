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
intents.members = True # Necessário para ler quem entra e mudar apelidos
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

# --- 2. REGISTRO COM PRIVACIDADE E MUDANÇA DE NICK ---
@bot.command()
async def registrar(ctx, nick: str, classe: str, power: int, lvl: int):
    # Salva no banco de dados
    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO membros (user_id, nick, classe, power, lvl, data_registro) 
                      VALUES (?, ?, ?, ?, ?, ?)''', (ctx.author.id, nick, classe, power, lvl, datetime.now()))
    conn.commit()
    conn.close()

    # Altera o apelido no servidor do Discord
    try:
        novo_apelido = f"{nick} | {classe}"[0:32]
        await ctx.author.edit(nick=novo_apelido)
    except Exception as e:
        print(f"Aviso: Não consegui mudar o nick de {ctx.author.name}. O cargo do bot deve estar acima do cargo do membro nas configurações do servidor.")

    # APAGA a mensagem do usuário para manter o Power em segredo
    try:
        await ctx.message.delete()
    except:
        pass

    # Confirmação temporária (apaga após 5 segundos)
    await ctx.send(f"✅ {ctx.author.mention}, registro salvo! Seu nick foi atualizado e seus dados foram enviados à liderança.", delete_after=5)

# --- 3. RELATÓRIO A CADA 48 HORAS (LIDERANÇA) ---
@tasks.loop(hours=48)
async def relatorio_lideranca():
    canal = bot.get_channel(ID_CANAL_LIDERANCA)
    if not canal:
        return

    conn = sqlite3.connect('clm_mir4.db')
    cursor = conn.cursor()
    # Ordena do maior Power para o menor
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
