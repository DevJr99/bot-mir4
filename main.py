import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
from datetime import datetime
import os
import threading
from flask import Flask
import psycopg2

# --- CONFIGURAÇÕES (SUBSTITUA PELOS SEUS IDs) ---
TOKEN = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ID_CANAL_BEM_VINDO = 1317651351584378930         # Canal de recepção
ID_CANAL_LIDERANCA_APROVACAO = 1491190966067921177 # Canal PRIVADO da liderança
ID_CARGO_PENDENTE = 1491227354734006364        # ID do cargo provisório
ID_CARGO_MEMBRO_OFICIAL = 1491227406290129047   # ID do cargo do Clã

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class Mir4Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Sincroniza os comandos / com o Discord
        await self.tree.sync()
        print(f"Comandos sincronizados!")

bot = Mir4Bot()

# --- CONEXÃO BANCO DE DADOS ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def iniciar_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS membros (
                        user_id BIGINT PRIMARY KEY, 
                        nick VARCHAR(255), classe VARCHAR(50), 
                        power INTEGER, lvl INTEGER, 
                        data_registro TIMESTAMP,
                        aprovado BOOLEAN DEFAULT FALSE
                    )''')
    conn.commit()
    cursor.close()
    conn.close()

# --- INTERFACE DE BOTÕES ---
class ViewAprovacao(ui.View):
    def __init__(self, user_id, nick, classe):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.nick = nick
        self.classe = classe

    @ui.button(label="Aceitar", style=discord.ButtonStyle.success)
    async def aceitar(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        membro = guild.get_member(self.user_id)
        
        # 1. Atualiza no Banco
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE membros SET aprovado = TRUE WHERE user_id = %s", (self.user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        # 2. Troca de Cargos e Nick
        if membro:
            cargo_p = guild.get_role(ID_CARGO_PENDENTE)
            cargo_o = guild.get_role(ID_CARGO_MEMBRO_OFICIAL)
            await membro.remove_roles(cargo_p)
            await membro.add_roles(cargo_o)
            try:
                await membro.edit(nick=f"{self.nick} | {self.classe}"[0:32])
            except: pass
            await membro.send(f"⚔️ **{self.nick}**, sua entrada no clã foi APROVADA! Bem-vindo!")

        await interaction.response.edit_message(content=f"✅ {membro.mention} aprovado por {interaction.user.mention}", embed=None, view=None)

    @ui.button(label="Recusar", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction: discord.Interaction, button: ui.Button):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM membros WHERE user_id = %s", (self.user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        membro = interaction.guild.get_member(self.user_id)
        if membro:
            await membro.send("❌ Seu pedido de ingresso no clã foi recusado.")
        
        await interaction.response.edit_message(content=f"❌ Registro de {self.user_id} recusado.", embed=None, view=None)

# --- EVENTOS E COMANDOS ---
@bot.event
async def on_ready():
    iniciar_db()
    print(f'Bot {bot.user} pronto!')

@bot.tree.command(name="registrar", description="Solicita entrada no clã")
async def registrar(interaction: discord.Interaction, nick: str, classe: str, power: int, lvl: int):
    # 1. Salva como pendente
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO membros (user_id, nick, classe, power, lvl, data_registro) 
                      VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (user_id) DO NOTHING''', 
                   (interaction.user.id, nick, classe, power, lvl, datetime.now()))
    conn.commit()
    cursor.close()
    conn.close()

    # 2. Dá o cargo provisório
    cargo_p = interaction.guild.get_role(ID_CARGO_PENDENTE)
    await interaction.user.add_roles(cargo_p)
    await interaction.response.send_message("✅ Solicitação enviada! Aguarde a aprovação da liderança.", ephemeral=True)

    # 3. Manda para a Liderança
    canal_adm = bot.get_channel(ID_CANAL_LIDERANCA_APROVACAO)
    embed = discord.Embed(title="📝 Novo Recruta", color=discord.Color.blue())
    embed.add_field(name="User", value=interaction.user.mention)
    embed.add_field(name="Personagem", value=f"{nick} ({classe})")
    embed.add_field(name="Status", value=f"PS: {power:,} | Lvl: {lvl}")
    
    view = ViewAprovacao(interaction.user.id, nick, classe)
    await canal_adm.send(embed=embed, view=view)

# --- WEB SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Online!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask).start()

bot.run(TOKEN)
