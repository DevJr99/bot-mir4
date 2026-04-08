import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime
import os
import threading
from flask import Flask
import psycopg2

# --- CONFIGURAÇÕES DE IDs ---
TOKEN = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
# IDs limpos (sem espaços invisíveis)
ID_CARGO_PENDENTE = 1491232641603735563
ID_CARGO_MEMBRO_OFICIAL = 1317650718458384425
ID_CANAL_REGISTRO = 1491227354734006364
ID_CANAL_LIDERANCA = 1491190966067921177

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
            
            # Troca os cargos e muda o nick
            try:
                if cargo_p in membro.roles:
                    await membro.remove_roles(cargo_p)
                await membro.add_roles(cargo_o)
                await membro.edit(nick=f"{self.nick} | {self.classe}"[0:32])
                await membro.send(f"⚔️ **{self.nick}**, sua entrada foi aprovada! O servidor foi liberado para você.")
            except Exception as e:
                print(f"Erro ao editar membro: {e}")

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
        await canal_reg.send(f"Olá {member.mention}! Para liberar o acesso ao clã, use o comando `/registrar` preenchendo seus dados do MIR4.")

# --- COMANDO SLASH: REGISTRAR ---
@bot.tree.command(name="registrar", description="Envie seus dados para aprovação da liderança")
async def registrar(interaction: discord.Interaction, nick: str, classe: str, power: int, lvl: int):
    # 1. Dá tempo ao bot para processar (Evita o erro de 'aplicativo não respondeu')
    await interaction.response.defer(ephemeral=True)

    # 2. Verifica se o cara já é membro
    if any(role.id == ID_CARGO_MEMBRO_OFICIAL for role in interaction.user.roles):
        await interaction.edit_original_response(content="Você já é um membro oficial!")
        return

    # 3. Envia para a liderança aprovar
    canal_adm = bot.get_channel(ID_CANAL_LIDERANCA)
    if not canal_adm:
        await interaction.edit_original_response(content="❌ Erro: Canal de liderança não encontrado. Avise um admin.")
        return

    embed = discord.Embed(title="🔔 Novo Pedido de Entrada", color=discord.Color.blue())
    embed.add_field(name="Usuário", value=interaction.user.mention)
    embed.add_field(name="Personagem", value=f"{nick} ({classe})")
    embed.add_field(name="Status", value=f"PS: {power:,} | Lvl: {lvl}")
    
    view = ViewAprovacao(interaction.user.id, nick, classe, power, lvl)
    await canal_adm.send(embed=embed, view=view)
    
    # 4. Confirma para o usuário
    await interaction.edit_original_response(content="✅ Seus dados foram enviados! Aguarde um líder liberar seu acesso.")

# --- FLASK (UPTIME) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Online!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask).start()

bot.run(TOKEN)
