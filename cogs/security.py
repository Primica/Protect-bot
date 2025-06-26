import discord
from discord.ext import commands
import sqlite3
import asyncio
from datetime import datetime, timedelta

class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'server.db'
        
        # Anti-spam tracking
        self.message_history = {}  # {user_id: [{'content': str, 'timestamp': datetime}, ...]}
        self.spam_warnings = {}  # {user_id: warning_count}
        self.muted_users = {}  # {user_id: {'until': datetime, 'reason': str}}
        
        # Anti-raid tracking
        self.recent_joins = []  # [{'user_id': int, 'join_time': datetime, 'account_age': int}, ...]
        self.raid_detected = False
        self.raid_lockdown = False
        
        # Configuration
        self.spam_config = {
            'max_repeated_messages': 3,  # Nombre max de messages identiques
            'spam_time_window': 10,  # Fenêtre de temps en secondes
            'warn_threshold': 2,  # Nombre d'avertissements avant mute
            'mute_duration': 300,  # Durée du mute en secondes (5 minutes)
            'max_warnings': 3  # Nombre max d'avertissements avant ban
        }
        
        self.raid_config = {
            'max_recent_accounts': 5,  # Nombre max de comptes récents
            'account_age_threshold': 2,  # Âge max du compte en jours
            'join_time_window': 60,  # Fenêtre de temps en secondes
            'auto_ban': True,  # Bannir automatiquement
            'lockdown_duration': 300  # Durée du lockdown en secondes
        }
        
        # Initialiser la base de données
        self.init_database()
        
        # Démarrer les tâches de nettoyage
        self.bot.loop.create_task(self.cleanup_task())

    # -- DATABASE --

    def init_database(self):
        """Initialise la base de données SQLite pour la sécurité"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Créer la table des avertissements
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                moderator_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action_type TEXT DEFAULT 'warn'
            )
        ''')
        
        # Créer la table des raids détectés
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS raid_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raid_type TEXT NOT NULL,
                accounts_involved INTEGER,
                detection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action_taken TEXT,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def log_warning(self, user_id, reason, moderator_id=None, action_type='warn'):
        """Enregistre un avertissement dans la base de données"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO security_warnings (user_id, reason, moderator_id, action_type)
            VALUES (?, ?, ?, ?)
        ''', (user_id, reason, moderator_id, action_type))
        
        conn.commit()
        conn.close()

    def log_raid(self, raid_type, accounts_involved, action_taken, details):
        """Enregistre un raid détecté"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO raid_logs (raid_type, accounts_involved, action_taken, details)
            VALUES (?, ?, ?, ?)
        ''', (raid_type, accounts_involved, action_taken, details))
        
        conn.commit()
        conn.close()

    def get_user_warnings(self, user_id):
        """Récupère les avertissements d'un utilisateur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT reason, moderator_id, timestamp, action_type 
            FROM security_warnings 
            WHERE user_id = ? 
            ORDER BY timestamp DESC
        ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        return results

    # -- ANTI-SPAM SYSTEM --

    @commands.Cog.listener()
    async def on_message(self, message):
        """Gère la détection de spam"""
        if message.author.bot or message.content.startswith('+'):
            return
        
        user_id = message.author.id
        current_time = datetime.now()
        
        # Initialiser l'historique si nécessaire
        if user_id not in self.message_history:
            self.message_history[user_id] = []
        
        # Ajouter le message à l'historique
        self.message_history[user_id].append({
            'content': message.content.lower().strip(),
            'timestamp': current_time
        })
        
        # Nettoyer l'historique (garder seulement les messages récents)
        cutoff_time = current_time - timedelta(seconds=self.spam_config['spam_time_window'])
        self.message_history[user_id] = [
            msg for msg in self.message_history[user_id] 
            if msg['timestamp'] > cutoff_time
        ]
        
        # Vérifier le spam
        await self.check_spam(message)

    async def check_spam(self, message):
        """Vérifie si un message est du spam"""
        user_id = message.author.id
        current_time = datetime.now()
        
        # Compter les messages identiques
        content = message.content.lower().strip()
        repeated_count = sum(1 for msg in self.message_history[user_id] if msg['content'] == content)
        
        if repeated_count >= self.spam_config['max_repeated_messages']:
            # Spam détecté
            await self.handle_spam(message, repeated_count)

    async def handle_spam(self, message, repeated_count):
        """Gère le spam détecté"""
        user_id = message.author.id
        member = message.author
        
        # Initialiser le compteur d'avertissements
        if user_id not in self.spam_warnings:
            self.spam_warnings[user_id] = 0
        
        self.spam_warnings[user_id] += 1
        warning_count = self.spam_warnings[user_id]
        
        # Créer l'embed d'avertissement
        embed = discord.Embed(
            title="🚨 Spam détecté",
            description=f"{member.mention} a envoyé le même message **{repeated_count}** fois !",
            color=discord.Color.red()
        )
        embed.add_field(name="Avertissement", value=f"{warning_count}/{self.spam_config['max_warnings']}", inline=True)
        embed.add_field(name="Action", value=self.get_action_for_warning(warning_count), inline=True)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"ID: {user_id}")
        
        # Enregistrer l'avertissement
        self.log_warning(user_id, f"Spam: {repeated_count} messages identiques", action_type='spam_warning')
        
        # Appliquer les actions selon le nombre d'avertissements
        if warning_count >= self.spam_config['max_warnings']:
            # Bannir l'utilisateur
            await self.ban_user(member, "Spam répété - Trop d'avertissements")
            embed.add_field(name="🚫 Action", value="**BANNI** - Trop d'avertissements", inline=False)
        elif warning_count >= self.spam_config['warn_threshold']:
            # Muter l'utilisateur
            await self.mute_user(member, self.spam_config['mute_duration'])
            embed.add_field(name="🔇 Action", value=f"**MUTÉ** pour {self.spam_config['mute_duration']} secondes", inline=False)
        
        # Envoyer l'avertissement
        await message.channel.send(embed=embed)
        
        # Supprimer le message spam
        try:
            await message.delete()
        except:
            pass

    def get_action_for_warning(self, warning_count):
        """Retourne l'action pour un nombre d'avertissements donné"""
        if warning_count >= self.spam_config['max_warnings']:
            return "🚫 BAN"
        elif warning_count >= self.spam_config['warn_threshold']:
            return "🔇 MUTE"
        else:
            return "⚠️ WARN"

    async def mute_user(self, member, duration):
        """Mute un utilisateur temporairement"""
        try:
            # Créer ou récupérer le rôle Muted
            muted_role = discord.utils.get(member.guild.roles, name="Muted")
            if not muted_role:
                muted_role = await member.guild.create_role(
                    name="Muted",
                    color=discord.Color.dark_grey(),
                    reason="Rôle pour les utilisateurs mutés"
                )
                
                # Configurer les permissions du rôle
                for channel in member.guild.channels:
                    if isinstance(channel, discord.TextChannel):
                        await channel.set_permissions(muted_role, send_messages=False)
                    elif isinstance(channel, discord.VoiceChannel):
                        await channel.set_permissions(muted_role, speak=False)
            
            # Appliquer le rôle
            await member.add_roles(muted_role, reason="Spam détecté")
            
            # Programmer la suppression du rôle
            self.bot.loop.create_task(self.unmute_user_after(member, muted_role, duration))
            
            # Enregistrer le mute
            self.muted_users[member.id] = {
                'until': datetime.now() + timedelta(seconds=duration),
                'reason': 'Spam détecté'
            }
            
        except Exception as e:
            print(f"Erreur lors du mute de {member.name}: {e}")

    async def unmute_user_after(self, member, muted_role, duration):
        """Retire le rôle Muted après la durée spécifiée"""
        await asyncio.sleep(duration)
        
        try:
            if muted_role in member.roles:
                await member.remove_roles(muted_role, reason="Fin du mute automatique")
                
                embed = discord.Embed(
                    title="🔊 Mute terminé",
                    description=f"{member.mention} a été démuté automatiquement.",
                    color=discord.Color.green()
                )
                
                # Envoyer dans le premier canal disponible
                for channel in member.guild.text_channels:
                    if channel.permissions_for(member.guild.me).send_messages:
                        await channel.send(embed=embed)
                        break
        except:
            pass

    async def ban_user(self, member, reason):
        """Bannit un utilisateur"""
        try:
            await member.ban(reason=reason)
            
            embed = discord.Embed(
                title="🚫 Utilisateur banni",
                description=f"{member.mention} a été banni pour spam répété.",
                color=discord.Color.red()
            )
            embed.add_field(name="Raison", value=reason, inline=False)
            
            # Envoyer dans le premier canal disponible
            for channel in member.guild.text_channels:
                if channel.permissions_for(member.guild.me).send_messages:
                    await channel.send(embed=embed)
                    break
        except Exception as e:
            print(f"Erreur lors du ban de {member.name}: {e}")

    # -- ANTI-RAID SYSTEM --

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Gère la détection de raid"""
        if member.bot:
            return
        
        current_time = datetime.now()
        account_age = (current_time - member.created_at).days
        
        # Ajouter le membre à la liste des arrivées récentes
        self.recent_joins.append({
            'user_id': member.id,
            'join_time': current_time,
            'account_age': account_age
        })
        
        # Nettoyer les anciennes entrées
        cutoff_time = current_time - timedelta(seconds=self.raid_config['join_time_window'])
        self.recent_joins = [
            join for join in self.recent_joins 
            if join['join_time'] > cutoff_time
        ]
        
        # Vérifier le raid
        await self.check_raid(member, account_age)

    async def check_raid(self, member, account_age):
        """Vérifie si un raid est en cours"""
        if self.raid_lockdown:
            return
        
        # Compter les comptes récents
        recent_accounts = [
            join for join in self.recent_joins 
            if join['account_age'] <= self.raid_config['account_age_threshold']
        ]
        
        if len(recent_accounts) >= self.raid_config['max_recent_accounts']:
            # Raid détecté
            await self.handle_raid(recent_accounts)

    async def handle_raid(self, recent_accounts):
        """Gère un raid détecté"""
        self.raid_detected = True
        self.raid_lockdown = True
        
        embed = discord.Embed(
            title="🚨 RAID DÉTECTÉ !",
            description=f"**{len(recent_accounts)}** comptes de moins de {self.raid_config['account_age_threshold']} jours ont rejoint en moins de {self.raid_config['join_time_window']} secondes !",
            color=discord.Color.red()
        )
        
        # Lister les comptes suspects
        suspect_list = ""
        for i, account in enumerate(recent_accounts[:5], 1):
            try:
                user = await self.bot.fetch_user(account['user_id'])
                suspect_list += f"{i}. {user.name}#{user.discriminator} (Compte: {account['account_age']}j)\n"
            except:
                suspect_list += f"{i}. Utilisateur {account['user_id']} (Compte: {account['account_age']}j)\n"
        
        embed.add_field(name="📋 Comptes suspects", value=suspect_list, inline=False)
        
        # Action automatique
        if self.raid_config['auto_ban']:
            banned_count = 0
            for account in recent_accounts:
                try:
                    user = await self.bot.fetch_user(account['user_id'])
                    guild = None
                    
                    # Trouver le serveur
                    for g in self.bot.guilds:
                        if g.get_member(account['user_id']):
                            guild = g
                            break
                    
                    if guild:
                        member = guild.get_member(account['user_id'])
                        if member:
                            await member.ban(reason="Anti-raid: Compte récent suspect")
                            banned_count += 1
                except:
                    pass
            
            embed.add_field(name="🚫 Action", value=f"**{banned_count}** comptes bannis automatiquement", inline=False)
        
        # Enregistrer le raid
        self.log_raid(
            "recent_accounts",
            len(recent_accounts),
            f"Auto-ban: {banned_count if self.raid_config['auto_ban'] else 0} comptes",
            f"Comptes de moins de {self.raid_config['account_age_threshold']} jours"
        )
        
        # Envoyer l'alerte
        for channel in self.bot.get_all_channels():
            if isinstance(channel, discord.TextChannel) and channel.permissions_for(channel.guild.me).send_messages:
                try:
                    await channel.send(embed=embed)
                    break
                except:
                    continue
        
        # Programmer la fin du lockdown
        self.bot.loop.create_task(self.end_lockdown())

    async def end_lockdown(self):
        """Termine le lockdown anti-raid"""
        await asyncio.sleep(self.raid_config['lockdown_duration'])
        
        self.raid_lockdown = False
        self.raid_detected = False
        
        embed = discord.Embed(
            title="✅ Lockdown terminé",
            description="Le système anti-raid est de nouveau actif.",
            color=discord.Color.green()
        )
        
        # Envoyer la notification
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    try:
                        await channel.send(embed=embed)
                        break
                    except:
                        continue

    # -- COMMANDS --

    @commands.command(name='warnings', aliases=['w'], brief="Affiche les avertissements d'un membre")
    @commands.has_permissions(administrator=True)
    async def warnings(self, ctx, member: discord.Member):
        """Affiche les avertissements d'un membre (Admin uniquement)"""
        warnings = self.get_user_warnings(member.id)
        
        if not warnings:
            embed = discord.Embed(
                title="📋 Avertissements",
                description=f"{member.mention} n'a aucun avertissement.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title=f"📋 Avertissements de {member.display_name}",
                description=f"**{len(warnings)}** avertissement(s)",
                color=discord.Color.orange()
            )
            
            for i, (reason, moderator_id, timestamp, action_type) in enumerate(warnings[:5], 1):
                try:
                    moderator = await self.bot.fetch_user(moderator_id) if moderator_id else None
                    mod_name = moderator.name if moderator else "Système"
                except:
                    mod_name = "Système"
                
                date = datetime.fromisoformat(timestamp).strftime("%d/%m/%Y %H:%M")
                
                embed.add_field(
                    name=f"⚠️ Avertissement #{i}",
                    value=f"**Raison:** {reason}\n**Action:** {action_type}\n**Modérateur:** {mod_name}\n**Date:** {date}",
                    inline=False
                )
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        
        await ctx.send(embed=embed)

    @commands.command(name='clearwarnings', aliases=['cw'], brief="Efface les avertissements d'un membre")
    @commands.has_permissions(administrator=True)
    async def clearwarnings(self, ctx, member: discord.Member):
        """Efface les avertissements d'un membre (Admin uniquement)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM security_warnings WHERE user_id = ?', (member.id,))
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        # Réinitialiser les compteurs
        if member.id in self.spam_warnings:
            del self.spam_warnings[member.id]
        
        embed = discord.Embed(
            title="✅ Avertissements effacés",
            description=f"**{deleted_count}** avertissement(s) effacé(s) pour {member.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Effacé par", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"ID: {member.id}")
        
        await ctx.send(embed=embed)

    @commands.command(name='security', aliases=['sec'], brief="Affiche les informations de sécurité")
    @commands.has_permissions(administrator=True)
    async def security(self, ctx):
        """Affiche les informations du système de sécurité (Admin uniquement)"""
        embed = discord.Embed(
            title="🛡️ Système de sécurité",
            description="Configuration et statut du système de protection",
            color=discord.Color.blue()
        )
        
        # Anti-spam
        embed.add_field(
            name="🚨 Anti-spam",
            value=f"**Messages répétés:** {self.spam_config['max_repeated_messages']}\n**Fenêtre:** {self.spam_config['spam_time_window']}s\n**Avertissements:** {self.spam_config['warn_threshold']}\n**Mute:** {self.spam_config['mute_duration']}s\n**Ban:** {self.spam_config['max_warnings']} warns",
            inline=True
        )
        
        # Anti-raid
        embed.add_field(
            name="🛡️ Anti-raid",
            value=f"**Comptes récents:** {self.raid_config['max_recent_accounts']}\n**Âge max:** {self.raid_config['account_age_threshold']}j\n**Fenêtre:** {self.raid_config['join_time_window']}s\n**Auto-ban:** {'Oui' if self.raid_config['auto_ban'] else 'Non'}\n**Lockdown:** {self.raid_config['lockdown_duration']}s",
            inline=True
        )
        
        # Statut
        status = "🔴 Lockdown actif" if self.raid_lockdown else "🟢 Actif"
        embed.add_field(
            name="📊 Statut",
            value=f"**Anti-raid:** {status}\n**Utilisateurs mutés:** {len(self.muted_users)}\n**Avertissements actifs:** {len(self.spam_warnings)}",
            inline=False
        )
        
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

    @commands.command(name='unmute', aliases=['um'], brief="Démute un membre manuellement")
    @commands.has_permissions(administrator=True)
    async def unmute(self, ctx, member: discord.Member):
        """Démute un membre manuellement (Admin uniquement)"""
        muted_role = discord.utils.get(member.guild.roles, name="Muted")
        
        if not muted_role or muted_role not in member.roles:
            embed = discord.Embed(
                title="⚠️ Pas muté",
                description=f"{member.mention} n'est pas muté.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        try:
            await member.remove_roles(muted_role, reason=f"Démute manuel par {ctx.author.name}")
            
            # Retirer du tracking
            if member.id in self.muted_users:
                del self.muted_users[member.id]
            
            embed = discord.Embed(
                title="🔊 Membre démuté",
                description=f"{member.mention} a été démuté manuellement.",
                color=discord.Color.green()
            )
            embed.add_field(name="Démuté par", value=ctx.author.mention, inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur",
                description=f"Impossible de démuter {member.mention}: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    # -- UTILITY TASKS --

    async def cleanup_task(self):
        """Tâche de nettoyage périodique"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                current_time = datetime.now()
                
                # Nettoyer les utilisateurs mutés expirés
                expired_mutes = [
                    user_id for user_id, data in self.muted_users.items()
                    if data['until'] < current_time
                ]
                
                for user_id in expired_mutes:
                    del self.muted_users[user_id]
                
                # Nettoyer l'historique des messages (garder seulement 1 heure)
                cutoff_time = current_time - timedelta(hours=1)
                for user_id in list(self.message_history.keys()):
                    self.message_history[user_id] = [
                        msg for msg in self.message_history[user_id]
                        if msg['timestamp'] > cutoff_time
                    ]
                    
                    # Supprimer les utilisateurs sans historique
                    if not self.message_history[user_id]:
                        del self.message_history[user_id]
                
                await asyncio.sleep(300)  # Nettoyer toutes les 5 minutes
                
            except Exception as e:
                print(f"Erreur dans cleanup_task: {e}")
                await asyncio.sleep(60)

    # -- ERROR HANDLERS --

    @warnings.error
    @clearwarnings.error
    @unmute.error
    async def warnings(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission refusée",
                description="Vous devez être administrateur pour utiliser cette commande !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Argument manquant",
                description="Vous devez spécifier un utilisateur pour cette commande",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @security.error
    async def security_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission refusée",
                description="Vous devez être administrateur pour utiliser cette commande !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        

def setup(bot):
    bot.add_cog(Security(bot)) 