import discord 
from discord.ext import commands

class Infos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot 

    @commands.command(name='infoprofile', aliases=['ip'], brief='Affiche les informations d\'un membre', usage='+infoprofile <@membre>')
    async def infoprofile(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author

        embed = discord.Embed(
            title=f"Informations de {member.name}",
            description=f"**ID:** {member.id}\n**Date d'inscription:** {member.created_at.strftime('%d/%m/%Y')}\n**Rôles:** {', '.join([role.name for role in member.roles])}",
            color=member.color
        )
        embed.add_field(name="Arrivée sur le serveur", value=f"{member.joined_at.strftime('%d/%m/%Y')}", inline=False)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

    @commands.command(name='serverinfo', aliases=['si'], brief='Affiche les informations du serveur', usage='+serverinfo')
    async def serverinfo(self, ctx):
        """
        Nombre total de membres
        Date de création du serveur
        Nombre de membres
        Pseudo du Propriétaire
        """
        guild = ctx.guild
        embed = discord.Embed(
            title=f"Informations du serveur {guild.name}",
            description=f"**ID:** {guild.id}\n**Date de création:** {guild.created_at.strftime('%d/%m/%Y')}\n**Nombre de membres:** {guild.member_count}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Créateur", value=f"{guild.owner.mention}", inline=False)
        embed.add_field(name="Nombre de boosters", value=f"{guild.premium_subscription_count}", inline=False)
        embed.set_thumbnail(url=guild.icon)
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Infos(bot))