import discord 
from discord.ext import commands 
import datetime
import asyncio

TICKET_CATEGORY_ID = 1387349264237330473

class TicketReasonModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, title="Création de ticket")

        self.add_item(discord.ui.InputText(label="Raison du ticket", placeholder="Décrivez brièvement votre problème", required=True))

    async def callback(self, interaction: discord.Interaction):
        # Si la catégorie des tickets n'existe pas, on la crée, et on fait en sorte que seul le membre qui a créé le ticket puisse y accéder et les modérateurs peuvent y accéder
        ticket_category = interaction.guild.get_channel(TICKET_CATEGORY_ID)
        if not ticket_category:
            ticket_category = await interaction.guild.create_category(name="Tickets", overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            })

        # Sinon on crée un ticket dans la catégorie
        ticket_channel = await ticket_category.create_text_channel(name=f"ticket-{interaction.user.name}", overwrites={
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        })

        # On envoie un message dans le ticket
        embed = discord.Embed(
            title=f"Ticket de {interaction.user.name}",
            description=f"Raison: {self.children[0].value}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Information", value=f"Bonjour {interaction.user.mention}, le staff va vous répondre ici. Merci d’expliquer votre demande en détails.")
        embed.set_footer(text=f"Ticket créé le {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

        await ticket_channel.send(embed=embed)
        await interaction.response.send_message(f"Ticket créé dans {ticket_channel.mention}", ephemeral=True)

class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Créer un ticket", style=discord.ButtonStyle.green, custom_id="ticket_button_open", emoji="🎫")
    async def ticket_button_open(self, button_item: discord.ui.Button, interaction: discord.Interaction):
        modal = TicketReasonModal()
        await interaction.response.send_modal(modal)

class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(TicketButton())

    @commands.command(name="DisplayTicketPanel", aliases=["dtp"], help="Affiche le panneau de tickets", usage="+dtp <channel>")
    @commands.has_permissions(administrator=True)
    async def display_ticket_panel(self, ctx, channel: discord.TextChannel= None):
        if channel is None:
            channel = ctx.channel

        embed = discord.Embed(
            title="Panneau de tickets",
            description="Besoin d’aide ou de contacter le staff ? Clique sur le bouton ci-dessous pour ouvrir un ticket.",
            color=discord.Color.blue()
        )

        embed.set_footer(text=f"Panneau de tickets pour {channel.mention}")

        await channel.send(embed=embed, view=TicketButton())

    @commands.command(name="CloseTicket", aliases=["ct"], help="Ferme le ticket", usage="+ct <channel>")
    @commands.has_permissions(manage_messages=True)
    async def close_ticket(self, ctx, channel: discord.TextChannel=None):
        if channel is None:
            channel = ctx.channel

        # On vérifie si le channel est bien un ticket
        if not channel.name.startswith("ticket-"):
            return await ctx.send("Ce channel n'est pas un ticket.")
        
        # On vérifie si le channel est dans la catégorie des tickets
        ticket_category = ctx.guild.get_channel(TICKET_CATEGORY_ID)
        if not ticket_category:
            return await ctx.send("La catégorie des tickets n'existe pas.")

        # On supprime le channel
        await ctx.send("Le ticket va être fermé dans 5 secondes.", delete_after=4)
        await asyncio.sleep(5)
        await channel.delete()

    # -- ERROR HANDLERS --

    @display_ticket_panel.error
    async def display_ticket_panel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send('❌ You do not have permission to use this command')

    @close_ticket.error
    async def close_ticket_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send('❌ You do not have permission to use this command')

def setup(bot):
    bot.add_cog(Ticket(bot))
        