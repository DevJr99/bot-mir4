import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime
import os
import threading
from flask import Flask
import psycopg2

# --- CONFIGURAÇÕES DE IDs (Mantenha estes IDs que você já validou) ---
TOKEN = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

# IDs de Cargos
ID_CARGO_PENDENTE = 1491232641603735563
ID_CARGO_MEMBRO_OFICIAL = 1317650718458384425

# IDs de Canais
ID_CANAL_REGISTRO = 1491227354734006364    # Onde o bot dá as boas-vindas
ID_CANAL_PENDENTE = 1491227406290129047   # Onde ficam os BOTÕES (Aprovação)
ID_CANAL_LIDERANCA = 1491190966067921177   # Onde ficam os DADOS técnicos

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True

class Mir4Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
        print("Sistema de Slash Commands sincronizado!")

bot = Mir4Bot()

# --- BANCO DE DADOS ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# --- SISTEMA DE BOTÕES DE APROVAÇÃO ---
class ViewAprovacao(ui.View):
    def __init__(self, user_id, nick, classe, power, lvl):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.nick = nick
        self.classe = classe
        self.power = power
        self.lvl = lvl

    @ui.button(label="ACEITAR RECRUTA", style=discord.ButtonStyle.success)
    async def aceitar(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        membro = guild.get_member(self.user_id)
        
        if membro:
            cargo_p = guild.get_role(ID_CARGO_PENDENTE)
            cargo_o = guild.get_role(ID_CARGO_MEMBRO_OFICIAL)
            
            try:
                # Troca de cargos
                if cargo_p in membro.roles:
                    await membro.remove_roles(cargo_p)
                await membro.add_roles(cargo_o)
                
                # Formata o Nick: "Nick | Classe"
                await membro.edit(nick=f"{self.nick} | {self.classe}"[0:32])
                
                # Avisa o membro no privado
                await membro.send(f"⚔️ **{self.nick}**, sua entrada no clã foi APROVADA! O servidor foi liberado.")
            except Exception as e:
                print(f"Erro ao atualizar membro: {e}")

        await interaction.response.edit_message(content=f"✅ {membro.mention if membro else 'Usuário'} foi aprovado por {interaction.user.mention}!", embed=None, view=None)

    @ui.button(label="RECUSAR", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction: discord.Interaction, button: ui.Button):
        membro = interaction.guild.get_member(self.user_id)
        if membro:
            try:
                await membro.send("❌ Seu pedido de registro foi recusado pela liderança.")
            except: pass
        await interaction.response.edit_message(content=f"❌ Registro de {self.user_id} recusado por {interaction.user.mention}.", embed=None, view=None)

# --- EVENTO: QUANDO ALGUÉM ENTRA NO SERVIDOR ---
@bot.event
async def on_member_join(member):
    cargo_p = member.guild.get_role(ID_CARGO_PENDENTE)
    if cargo_p:
        await member.add_roles(cargo_p)
    
    canal_reg = bot.get_channel(ID_CANAL_REGISTRO)
    if canal_reg:
        await canal_reg.send(f"Bem-vindo {member.mention}! Use o comando `/registrar` para iniciar sua aprovação.")

# --- COMANDO SLASH: REGISTRAR ---
@bot.tree.command(name="registrar", description="Inicia seu pedido de registro no clã")
async def registrar(interaction: discord.Interaction, nick: str, classe: str, power: int, lvl: int):
    # Dá tempo ao bot para processar
    await interaction.response.defer(ephemeral=True)

    # 1. Cria a ficha do jogador (Embed)
    embed = discord.Embed(title="📝 Nova Solicitação de Ingresso", color=discord.Color.blue())
    embed.add_field(name="Usuário", value=interaction.user.mention, inline=True)
    embed.add_field(name="Personagem", value=f"{nick} | {classe}", inline=True)
    embed.add_field(name="Status", value=f"PS: {power:,} | Lvl: {lvl}", inline=False)
    embed.set_footer(text=f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    # 2. Envia DADOS TÉCNICOS para o canal de #LIDERANÇA
    canal_lideranca = bot.get_channel(ID_CANAL_LIDERANCA)
    if canal_lideranca:
        await canal_lideranca.send(f"📊 **Log de Registro:**", embed=embed)

    # 3. Envia BOTÕES DE APROVAÇÃO para o canal #PENDENTE
    canal_pendente = bot.get_channel(ID_CANAL_PENDENTE)
    if canal_pendente:
        view = ViewAprovacao(interaction.user.id, nick, classe, power, lvl)
        await canal_pendente.send(content=f"🔔 **Aguardando Decisão:** {interaction.user.mention}", embed=embed, view=view)
    
    await interaction.edit_original_response(content="✅ Seus dados foram enviados! A liderança analisará seu pedido no canal de aprovação.")

# --- FLASK (UPTIME) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Nazarick Bot Online!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask).start()

bot.run(TOKEN)
