import discord
from discord.ext import commands
import sqlite3
from datetime import datetime

class Ban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'server.db'
        # Initialiser la base de données
        self.init_database()

    # -- DATABASE --

    def init_database(self):
        """Initialise la base de données SQLite pour la whitelist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Créer la table de whitelist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS whitelist (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def is_whitelisted(self, user_id):
        """Vérifie si un utilisateur est whitelisté"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM whitelist WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None

    def add_to_whitelist(self, user_id, added_by, reason="Aucune raison fournie"):
        """Ajoute un utilisateur à la whitelist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO whitelist (user_id, added_by, added_at, reason) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, added_by, datetime.now(), reason))
        
        conn.commit()
        conn.close()

    def remove_from_whitelist(self, user_id):
        """Retire un utilisateur de la whitelist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM whitelist WHERE user_id = ?', (user_id,))
        result = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        return result

    def get_whitelist(self):
        """Récupère la liste complète des utilisateurs whitelistés"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, added_by, added_at, reason 
            FROM whitelist 
            ORDER BY added_at DESC
        ''')
        results = cursor.fetchall()
        
        conn.close()
        return results

    # -- BAN RELATED --

    @commands.command(name='ban', aliases=['bn'], brief="Bannit un membre", usage="+ban <@membre> <raison>")
    @commands.has_permissions(administrator=True)
    async def ban(self, ctx, member: discord.Member, reason: str = "Aucune raison fournie"):
        # Vérifier si le membre est whitelisté
        if self.is_whitelisted(member.id):
            embed = discord.Embed(
                title="❌ Action impossible",
                description=f"{member.mention} est protégé par la whitelist et ne peut pas être banni !",
                color=discord.Color.red()
            )
            embed.add_field(name="🛡️ Protection", value="Ce membre est whitelisté", inline=False)
            embed.set_footer(text=f"Demandé par {ctx.author.name}")
            await ctx.send(embed=embed)
            return
        
        # Vérifier si l'utilisateur essaie de se bannir lui-même
        if member.id == ctx.author.id:
            embed = discord.Embed(
                title="❌ Action impossible",
                description="Vous ne pouvez pas vous bannir vous-même !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        try:
            await member.ban(reason=reason)
            embed = discord.Embed(
                title="🔨 Membre banni",
                description=f"{member.mention} a été banni du serveur",
                color=discord.Color.red()
            )
            embed.add_field(name="Raison", value=reason, inline=False)
            embed.add_field(name="Banni par", value=ctx.author.mention, inline=False)
            embed.set_footer(text=f"ID: {member.id}")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission insuffisante",
                description="Je n'ai pas les permissions nécessaires pour bannir ce membre.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur",
                description=f"Une erreur s'est produite lors du bannissement : {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='unban', aliases=['ub'], brief="Débannit un membre", usage="+unban <@membre>")
    @commands.has_permissions(administrator=True)
    async def unban(self, ctx, member: discord.Member):
        try:
            await ctx.guild.unban(member)
            await ctx.send(f"{member.mention} a été débanni")
        except discord.NotFound:
            await ctx.send(f"{member.mention} n'est pas banni, ou n'existe pas")

    @commands.command(name='banlist', aliases=['bl'], brief="Affiche la liste des membres bannis", usage="+bl")
    @commands.has_permissions(administrator=True)
    async def banlist(self, ctx):
        try:
            banned_users = []
            async for ban_entry in ctx.guild.bans():
                banned_users.append(ban_entry)
            
            if not banned_users:
                embed = discord.Embed(
                    title="📋 Liste des bannis",
                    description="Aucun membre n'est actuellement banni sur ce serveur",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Demandé par {ctx.author.name}")
                await ctx.send(embed=embed)
                return
            
            embed = discord.Embed(
                title="📋 Liste des membres bannis",
                description=f"**{len(banned_users)}** membre(s) banni(s) sur ce serveur",
                color=discord.Color.red()
            )
            
            for i, ban_entry in enumerate(banned_users, 1):
                user = ban_entry.user
                embed.add_field(
                    name=f"🔨 {i}. {user.name}#{user.discriminator}",
                    value=f"**ID:** {user.id}\n**Raison:** {ban_entry.reason or 'Aucune raison'}\n**Date:** {ban_entry.created_at.strftime('%d/%m/%Y %H:%M')}",
                    inline=False
                )
            
            embed.set_footer(text=f"Demandé par {ctx.author.name}")
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission insuffisante",
                description="Je n'ai pas les permissions nécessaires pour voir la liste des bannis.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur",
                description=f"Une erreur s'est produite lors de la récupération de la liste des bannis : {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='baninfo', aliases=['bi'], brief="Affiche les informations d'un membre banni", usage="+bi <@membre>")
    @commands.has_permissions(administrator=True)
    async def baninfo(self, ctx, member: discord.Member):
        async for ban_entry in ctx.guild.bans():
            if ban_entry.user.id == member.id:
                embed = discord.Embed(title="Informations du membre banni", color=discord.Color.red())
                embed.add_field(name="Membre banni", value=f"{member.name}#{member.discriminator}", inline=False)
                embed.add_field(name="ID", value=member.id, inline=False)
                embed.add_field(name="Date de bannissement", value=ban_entry.created_at.strftime("%d/%m/%Y %H:%M:%S"), inline=False)
                embed.add_field(name="Raison", value=ban_entry.reason, inline=False)
                await ctx.send(embed=embed)
                return
        await ctx.send(f"{member.mention} n'est pas banni, ou n'existe pas")

    # -- WHITELIST RELATED --

    @commands.command(name='whitelist', aliases=['wl'], brief="Ajoute un membre à la whitelist", usage="+wl <@membre> <raison>")
    @commands.has_permissions(administrator=True)
    async def whitelist(self, ctx, member: discord.Member, reason: str = "Aucune raison fournie"):
        """Ajoute un membre à la whitelist (Admin uniquement)"""
        if self.is_whitelisted(member.id):
            embed = discord.Embed(
                title="⚠️ Déjà whitelisté",
                description=f"{member.mention} est déjà dans la whitelist !",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        self.add_to_whitelist(member.id, ctx.author.id, reason)
        
        embed = discord.Embed(
            title="✅ Membre whitelisté",
            description=f"{member.mention} a été ajouté à la whitelist",
            color=discord.Color.green()
        )
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Ajouté par", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"ID: {member.id}")
        await ctx.send(embed=embed)

    @commands.command(name='unwhitelist', aliases=['uwl'], brief="Retire un membre de la whitelist", usage="+uwl <@membre>")
    @commands.has_permissions(administrator=True)
    async def unwhitelist(self, ctx, member: discord.Member):
        """Retire un membre de la whitelist (Admin uniquement)"""
        if not self.is_whitelisted(member.id):
            embed = discord.Embed(
                title="⚠️ Pas dans la whitelist",
                description=f"{member.mention} n'est pas dans la whitelist !",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        self.remove_from_whitelist(member.id)
        
        embed = discord.Embed(
            title="✅ Membre retiré de la whitelist",
            description=f"{member.mention} a été retiré de la whitelist",
            color=discord.Color.green()
        )
        embed.add_field(name="Retiré par", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"ID: {member.id}")
        await ctx.send(embed=embed)

    @commands.command(name='whitelistlist', aliases=['wll'], brief="Affiche la liste des membres whitelistés", usage="+wll")
    @commands.has_permissions(administrator=True)
    async def whitelistlist(self, ctx):
        """Affiche la liste des membres whitelistés (Admin uniquement)"""
        whitelisted_users = self.get_whitelist()
        
        if not whitelisted_users:
            embed = discord.Embed(
                title="📋 Liste de la whitelist",
                description="Aucun membre n'est actuellement whitelisté",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📋 Liste de la whitelist",
            description=f"**{len(whitelisted_users)}** membre(s) whitelisté(s)",
            color=discord.Color.blue()
        )
        
        for user_data in whitelisted_users:
            user_id, added_by, added_at, reason = user_data
            
            try:
                member = await ctx.guild.fetch_member(user_id)
                username = member.display_name
                avatar = member.avatar.url if member.avatar else member.default_avatar.url
            except:
                username = f"Utilisateur {user_id}"
                avatar = None
            
            try:
                added_by_member = await ctx.guild.fetch_member(added_by)
                added_by_name = added_by_member.display_name
            except:
                added_by_name = f"Utilisateur {added_by}"
            
            added_date = datetime.fromisoformat(added_at).strftime("%d/%m/%Y %H:%M")
            
            embed.add_field(
                name=f"🛡️ {username}",
                value=f"**Ajouté par:** {added_by_name}\n**Date:** {added_date}\n**Raison:** {reason}",
                inline=False
            )
        
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

    @commands.command(name='whitelistinfo', aliases=['wli'], brief="Affiche les informations d'un membre whitelisté", usage="+wli <@membre>")
    @commands.has_permissions(administrator=True)
    async def whitelistinfo(self, ctx, member: discord.Member):
        """Affiche les informations d'un membre whitelisté (Admin uniquement)"""
        if not self.is_whitelisted(member.id):
            embed = discord.Embed(
                title="❌ Membre non whitelisté",
                description=f"{member.mention} n'est pas dans la whitelist !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT added_by, added_at, reason 
            FROM whitelist 
            WHERE user_id = ?
        ''', (member.id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            added_by, added_at, reason = result
            
            try:
                added_by_member = await ctx.guild.fetch_member(added_by)
                added_by_name = added_by_member.display_name
            except:
                added_by_name = f"Utilisateur {added_by}"
            
            added_date = datetime.fromisoformat(added_at).strftime("%d/%m/%Y à %H:%M:%S")
            
            embed = discord.Embed(
                title="🛡️ Informations de la whitelist",
                description=f"Informations pour {member.mention}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Membre", value=f"{member.name}#{member.discriminator}", inline=False)
            embed.add_field(name="ID", value=member.id, inline=False)
            embed.add_field(name="Ajouté par", value=added_by_name, inline=False)
            embed.add_field(name="Date d'ajout", value=added_date, inline=False)
            embed.add_field(name="Raison", value=reason, inline=False)
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text=f"Demandé par {ctx.author.name}")
            
            await ctx.send(embed=embed)

    @commands.command(name='checkwhitelist', aliases=['cwl'], brief="Vérifie si un membre est whitelisté", usage="+cwl <@membre>")
    async def checkwhitelist(self, ctx, member: discord.Member = None):
        """Vérifie si un membre est whitelisté"""
        if member is None:
            member = ctx.author
        
        is_whitelisted = self.is_whitelisted(member.id)
        
        if is_whitelisted:
            embed = discord.Embed(
                title="🛡️ Membre protégé",
                description=f"{member.mention} est **whitelisté** et protégé contre les bannissements",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="⚠️ Membre non protégé",
                description=f"{member.mention} n'est **pas whitelisté** et peut être banni",
                color=discord.Color.orange()
            )
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        
        await ctx.send(embed=embed)

    # -- ERROR HANDLERS --

    @whitelist.error
    @unwhitelist.error
    @whitelistlist.error
    @whitelistinfo.error
    async def whitelist_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission refusée",
                description="Vous devez être administrateur pour utiliser cette commande !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @ban.error
    @unban.error
    @banlist.error
    @baninfo.error
    async def ban_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission refusée",
                description="Vous devez être administrateur pour utiliser cette commande !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Argument manquant",
                description="Veuillez spécifier un membre à bannir/débannir !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                title="❌ Membre introuvable",
                description="Le membre spécifié n'a pas été trouvé sur ce serveur !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.CommandInvokeError):
            embed = discord.Embed(
                title="❌ Erreur d'exécution",
                description=f"Une erreur s'est produite lors de l'exécution de la commande : {str(error.original)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Erreur inconnue",
                description=f"Une erreur inattendue s'est produite : {str(error)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Ban(bot))