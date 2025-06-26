import discord
from discord.ext import commands
import sqlite3
import json
import os
import asyncio
from datetime import datetime
from typing import Optional

class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'server.db'
        self.backup_dir = 'backups'
        
        # Créer le dossier de sauvegarde s'il n'existe pas
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        
        # Initialiser la base de données
        self.init_database()

    # -- DATABASE --

    def init_database(self):
        """Initialise la base de données SQLite pour les backups"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Créer la table des backups
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                server_id INTEGER NOT NULL,
                server_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def log_backup(self, name, server_id, server_name, created_by, file_path, description=""):
        """Enregistre un backup dans la base de données"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO backups (name, server_id, server_name, created_by, file_path, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, server_id, server_name, created_by, file_path, description))
        
        conn.commit()
        conn.close()

    def get_backups(self, server_id=None):
        """Récupère la liste des backups"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if server_id:
            cursor.execute('''
                SELECT name, server_name, created_at, created_by, description 
                FROM backups 
                WHERE server_id = ? 
                ORDER BY created_at DESC
            ''', (server_id,))
        else:
            cursor.execute('''
                SELECT name, server_name, created_at, created_by, description 
                FROM backups 
                ORDER BY created_at DESC
            ''')
        
        results = cursor.fetchall()
        conn.close()
        return results

    def get_backup_info(self, name):
        """Récupère les informations d'un backup spécifique"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT server_id, server_name, created_at, created_by, file_path, description 
            FROM backups 
            WHERE name = ?
        ''', (name,))
        
        result = cursor.fetchone()
        conn.close()
        return result

    def delete_backup(self, name):
        """Supprime un backup de la base de données"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM backups WHERE name = ?', (name,))
        result = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        return result

    # -- BACKUP FUNCTIONS --

    async def create_backup_data(self, guild):
        """Crée les données de sauvegarde d'un serveur"""
        backup_data = {
            "server_info": {
                "id": guild.id,
                "name": guild.name,
                "description": guild.description,
                "icon_url": str(guild.icon.url) if guild.icon else None,
                "banner_url": str(guild.banner.url) if guild.banner else None,
                "verification_level": str(guild.verification_level),
                "explicit_content_filter": str(guild.explicit_content_filter),
                "default_notifications": str(guild.default_notifications),
                "system_channel_id": guild.system_channel.id if guild.system_channel else None,
                "rules_channel_id": guild.rules_channel.id if guild.rules_channel else None,
                "public_updates_channel_id": guild.public_updates_channel.id if guild.public_updates_channel else None,
                "afk_channel_id": guild.afk_channel.id if guild.afk_channel else None,
                "afk_timeout": guild.afk_timeout,
                "mfa_level": guild.mfa_level,
                "premium_tier": guild.premium_tier,
                "premium_subscription_count": guild.premium_subscription_count,
                "max_presences": guild.max_presences,
                "max_members": guild.max_members,
                "max_video_channel_users": guild.max_video_channel_users,
                "approximate_member_count": guild.approximate_member_count,
                "approximate_presence_count": guild.approximate_presence_count,
                "created_at": guild.created_at.isoformat()
            },
            "roles": [],
            "categories": [],
            "channels": [],
            "emojis": [],
            "backup_created_at": datetime.now().isoformat(),
            "backup_version": "1.0"
        }

        # Sauvegarder les rôles
        for role in guild.roles:
            if role.name != "@everyone":  # Ignorer le rôle @everyone
                role_data = {
                    "name": role.name,
                    "color": role.color.value,
                    "hoist": role.hoist,
                    "mentionable": role.mentionable,
                    "position": role.position,
                    "permissions": role.permissions.value,
                    "icon": str(role.icon.url) if role.icon else None,
                    "unicode_emoji": role.unicode_emoji,
                    "managed": role.managed,
                    "tags": {
                        "bot_id": role.tags.bot_id if role.tags and role.tags.bot_id else None,
                        "integration_id": role.tags.integration_id if role.tags and role.tags.integration_id else None,
                        "premium_subscriber": role.tags.premium_subscriber if role.tags and hasattr(role.tags, 'premium_subscriber') else None
                    }
                }
                backup_data["roles"].append(role_data)

        # Sauvegarder les catégories
        for category in guild.categories:
            category_data = {
                "name": category.name,
                "position": category.position,
                "overwrites": self.get_overwrites(category.overwrites)
            }
            backup_data["categories"].append(category_data)

        # Sauvegarder les salons textuels
        for channel in guild.text_channels:
            channel_data = {
                "name": channel.name,
                "type": "text",
                "position": channel.position,
                "category_id": channel.category.id if channel.category else None,
                "topic": channel.topic,
                "slowmode_delay": channel.slowmode_delay,
                "nsfw": channel.nsfw,
                "overwrites": self.get_overwrites(channel.overwrites)
            }
            backup_data["channels"].append(channel_data)

        # Sauvegarder les salons vocaux
        for channel in guild.voice_channels:
            channel_data = {
                "name": channel.name,
                "type": "voice",
                "position": channel.position,
                "category_id": channel.category.id if channel.category else None,
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit,
                "overwrites": self.get_overwrites(channel.overwrites)
            }
            backup_data["channels"].append(channel_data)

        # Sauvegarder les salons d'annonces
        for channel in guild.channels:
            if channel.type == discord.ChannelType.news:
                channel_data = {
                    "name": channel.name,
                    "type": "news",
                    "position": channel.position,
                    "category_id": channel.category.id if channel.category else None,
                    "topic": channel.topic,
                    "nsfw": channel.nsfw,
                    "overwrites": self.get_overwrites(channel.overwrites)
                }
                backup_data["channels"].append(channel_data)

        # Sauvegarder les salons de forum
        for channel in guild.channels:
            if channel.type == discord.ChannelType.forum:
                channel_data = {
                    "name": channel.name,
                    "type": "forum",
                    "position": channel.position,
                    "category_id": channel.category.id if channel.category else None,
                    "topic": channel.topic,
                    "nsfw": channel.nsfw,
                    "overwrites": self.get_overwrites(channel.overwrites)
                }
                backup_data["channels"].append(channel_data)

        # Sauvegarder les emojis
        for emoji in guild.emojis:
            emoji_data = {
                "name": emoji.name,
                "url": str(emoji.url),
                "animated": emoji.animated,
                "managed": emoji.managed,
                "require_colons": emoji.require_colons,
                "roles": [role.id for role in emoji.roles]
            }
            backup_data["emojis"].append(emoji_data)

        return backup_data

    def get_overwrites(self, overwrites):
        """Convertit les overwrites en format JSON"""
        overwrites_data = {}
        for target, overwrite in overwrites.items():
            overwrites_data[str(target.id)] = {
                "allow": overwrite.pair()[0].value,
                "deny": overwrite.pair()[1].value
            }
        return overwrites_data

    async def save_backup_file(self, backup_data, filename):
        """Sauvegarde les données dans un fichier JSON"""
        file_path = os.path.join(self.backup_dir, f"{filename}.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return file_path

    async def load_backup_file(self, filename):
        """Charge les données depuis un fichier JSON"""
        file_path = os.path.join(self.backup_dir, f"{filename}.json")
        
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # -- RESTORE FUNCTIONS --

    async def restore_server(self, guild, backup_data):
        """Restaure un serveur à partir des données de sauvegarde"""
        try:
            # Sauvegarder les rôles existants pour les permissions
            existing_roles = {role.name: role for role in guild.roles}
            
            # Créer les nouveaux rôles
            created_roles = {}
            for role_data in backup_data["roles"]:
                try:
                    # Vérifier si le rôle existe déjà
                    if role_data["name"] in existing_roles:
                        created_roles[role_data["name"]] = existing_roles[role_data["name"]]
                        continue
                    
                    # Créer le nouveau rôle
                    new_role = await guild.create_role(
                        name=role_data["name"],
                        color=discord.Color(role_data["color"]),
                        hoist=role_data["hoist"],
                        mentionable=role_data["mentionable"],
                        permissions=discord.Permissions(role_data["permissions"]),
                        reason="Restauration de backup"
                    )
                    created_roles[role_data["name"]] = new_role
                    
                    # Ajouter l'emoji si présent
                    if role_data["unicode_emoji"]:
                        await new_role.edit(unicode_emoji=role_data["unicode_emoji"])
                    
                except Exception as e:
                    print(f"Erreur lors de la création du rôle {role_data['name']}: {e}")

            # Créer les catégories
            created_categories = {}
            for category_data in backup_data["categories"]:
                try:
                    new_category = await guild.create_category(
                        name=category_data["name"],
                        reason="Restauration de backup"
                    )
                    created_categories[category_data["name"]] = new_category
                    
                    # Appliquer les overwrites
                    await self.apply_overwrites(new_category, category_data["overwrites"], created_roles)
                    
                except Exception as e:
                    print(f"Erreur lors de la création de la catégorie {category_data['name']}: {e}")

            # Créer les salons
            for channel_data in backup_data["channels"]:
                try:
                    category = None
                    if channel_data["category_id"]:
                        # Trouver la catégorie correspondante
                        for cat_name, cat_obj in created_categories.items():
                            if cat_obj.name == channel_data["name"]:
                                category = cat_obj
                                break
                    
                    if channel_data["type"] == "text":
                        new_channel = await guild.create_text_channel(
                            name=channel_data["name"],
                            category=category,
                            topic=channel_data.get("topic"),
                            slowmode_delay=channel_data.get("slowmode_delay", 0),
                            nsfw=channel_data.get("nsfw", False),
                            reason="Restauration de backup"
                        )
                    elif channel_data["type"] == "voice":
                        new_channel = await guild.create_voice_channel(
                            name=channel_data["name"],
                            category=category,
                            bitrate=channel_data.get("bitrate", 64000),
                            user_limit=channel_data.get("user_limit", 0),
                            reason="Restauration de backup"
                        )
                    elif channel_data["type"] == "news":
                        new_channel = await guild.create_news_channel(
                            name=channel_data["name"],
                            category=category,
                            topic=channel_data.get("topic"),
                            nsfw=channel_data.get("nsfw", False),
                            reason="Restauration de backup"
                        )
                    elif channel_data["type"] == "forum":
                        new_channel = await guild.create_forum_channel(
                            name=channel_data["name"],
                            category=category,
                            topic=channel_data.get("topic"),
                            nsfw=channel_data.get("nsfw", False),
                            reason="Restauration de backup"
                        )
                    
                    # Appliquer les overwrites
                    await self.apply_overwrites(new_channel, channel_data["overwrites"], created_roles)
                    
                except Exception as e:
                    print(f"Erreur lors de la création du salon {channel_data['name']}: {e}")

            # Créer les emojis
            for emoji_data in backup_data["emojis"]:
                try:
                    # Télécharger l'emoji
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(emoji_data["url"]) as resp:
                            if resp.status == 200:
                                emoji_bytes = await resp.read()
                                new_emoji = await guild.create_custom_emoji(
                                    name=emoji_data["name"],
                                    image=emoji_bytes,
                                    reason="Restauration de backup"
                                )
                except Exception as e:
                    print(f"Erreur lors de la création de l'emoji {emoji_data['name']}: {e}")

            return True
            
        except Exception as e:
            print(f"Erreur lors de la restauration: {e}")
            return False

    async def apply_overwrites(self, target, overwrites_data, created_roles):
        """Applique les overwrites à un objet"""
        try:
            for target_id, overwrite_data in overwrites_data.items():
                # Trouver le rôle correspondant
                role = None
                for role_name, role_obj in created_roles.items():
                    if str(role_obj.id) == target_id:
                        role = role_obj
                        break
                
                if role:
                    await target.set_permissions(
                        role,
                        overwrite=discord.PermissionOverwrite.from_pair(
                            discord.Permissions(overwrite_data["allow"]),
                            discord.Permissions(overwrite_data["deny"])
                        ),
                        reason="Restauration de backup"
                    )
        except Exception as e:
            print(f"Erreur lors de l'application des overwrites: {e}")

    # -- COMMANDS --

    @commands.command(name='backup', aliases=['b'], brief="Gère les sauvegardes du serveur")
    @commands.has_permissions(administrator=True)
    async def backup(self, ctx, action: str, *, name: Optional[str] = None, description: str = ""):
        """Gère les sauvegardes du serveur (Admin uniquement)"""
        if action.lower() == "create":
            if not name:
                embed = discord.Embed(
                    title="❌ Nom manquant",
                    description="Veuillez spécifier un nom pour la sauvegarde !\nUsage: `+backup create <nom> [description]`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            await self.create_backup(ctx, name, description)
        
        elif action.lower() == "load":
            if not name:
                embed = discord.Embed(
                    title="❌ Nom manquant",
                    description="Veuillez spécifier le nom de la sauvegarde à charger !\nUsage: `+backup load <nom>`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            await self.load_backup(ctx, name)
        
        elif action.lower() == "list":
            await self.list_backups(ctx)
        
        elif action.lower() == "info":
            if not name:
                embed = discord.Embed(
                    title="❌ Nom manquant",
                    description="Veuillez spécifier le nom de la sauvegarde !\nUsage: `+backup info <nom>`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            await self.backup_info(ctx, name)
        
        elif action.lower() == "delete":
            if not name:
                embed = discord.Embed(
                    title="❌ Nom manquant",
                    description="Veuillez spécifier le nom de la sauvegarde à supprimer !\nUsage: `+backup delete <nom>`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            await self.delete_backup_cmd(ctx, name)
        
        else:
            embed = discord.Embed(
                title="❌ Action invalide",
                description="Actions disponibles : `create`, `load`, `list`, `info`, `delete`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    async def create_backup(self, ctx, name, description=""):
        """Crée une sauvegarde du serveur"""
        # Vérifier si le nom existe déjà
        existing_backup = self.get_backup_info(name)
        if existing_backup:
            embed = discord.Embed(
                title="⚠️ Sauvegarde existante",
                description=f"Une sauvegarde nommée **{name}** existe déjà !",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        # Créer l'embed de progression
        progress_embed = discord.Embed(
            title="🔄 Création de sauvegarde en cours...",
            description=f"Sauvegarde du serveur **{ctx.guild.name}**",
            color=discord.Color.blue()
        )
        progress_embed.add_field(name="Nom", value=name, inline=True)
        progress_embed.add_field(name="Description", value=description or "Aucune", inline=True)
        progress_embed.add_field(name="Statut", value="⏳ Collecte des données...", inline=False)
        
        progress_msg = await ctx.send(embed=progress_embed)

        try:
            # Collecter les données
            backup_data = await self.create_backup_data(ctx.guild)
            
            # Mettre à jour le statut
            progress_embed.set_field_at(2, name="Statut", value="💾 Sauvegarde des données...", inline=False)
            await progress_msg.edit(embed=progress_embed)
            
            # Sauvegarder le fichier
            file_path = await self.save_backup_file(backup_data, name)
            
            # Enregistrer dans la base de données
            self.log_backup(name, ctx.guild.id, ctx.guild.name, ctx.author.id, file_path, description)
            
            # Créer l'embed de succès
            success_embed = discord.Embed(
                title="✅ Sauvegarde créée",
                description=f"La sauvegarde **{name}** a été créée avec succès !",
                color=discord.Color.green()
            )
            success_embed.add_field(name="Serveur", value=ctx.guild.name, inline=True)
            success_embed.add_field(name="Créée par", value=ctx.author.mention, inline=True)
            success_embed.add_field(name="Rôles", value=str(len(backup_data["roles"])), inline=True)
            success_embed.add_field(name="Catégories", value=str(len(backup_data["categories"])), inline=True)
            success_embed.add_field(name="Salons", value=str(len(backup_data["channels"])), inline=True)
            success_embed.add_field(name="Emojis", value=str(len(backup_data["emojis"])), inline=True)
            success_embed.add_field(name="Description", value=description or "Aucune", inline=False)
            success_embed.set_footer(text=f"Fichier: {name}.json")
            
            await progress_msg.edit(embed=success_embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Erreur lors de la sauvegarde",
                description=f"Une erreur s'est produite : {str(e)}",
                color=discord.Color.red()
            )
            await progress_msg.edit(embed=error_embed)

    async def load_backup(self, ctx, name):
        """Charge une sauvegarde"""
        # Vérifier si la sauvegarde existe
        backup_info = self.get_backup_info(name)
        if not backup_info:
            embed = discord.Embed(
                title="❌ Sauvegarde introuvable",
                description=f"Aucune sauvegarde nommée **{name}** n'a été trouvée !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        # Confirmation
        confirm_embed = discord.Embed(
            title="⚠️ Confirmation de restauration",
            description=f"Êtes-vous sûr de vouloir restaurer le serveur avec la sauvegarde **{name}** ?",
            color=discord.Color.orange()
        )
        confirm_embed.add_field(name="⚠️ Attention", value="Cette action va modifier la structure du serveur !", inline=False)
        confirm_embed.add_field(name="Sauvegarde", value=f"**{name}** ({backup_info[1]})", inline=True)
        confirm_embed.add_field(name="Créée le", value=backup_info[2][:10], inline=True)
        confirm_embed.add_field(name="Description", value=backup_info[5] or "Aucune", inline=False)
        
        confirm_msg = await ctx.send(embed=confirm_embed)
        
        # Ajouter les réactions
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        try:
            reaction, user = await self.bot.wait_for(
                'reaction_add',
                timeout=30.0,
                check=lambda r, u: u == ctx.author and r.message.id == confirm_msg.id and str(r.emoji) in ["✅", "❌"]
            )
            
            if str(reaction.emoji) == "❌":
                cancel_embed = discord.Embed(
                    title="❌ Restauration annulée",
                    description="La restauration a été annulée par l'utilisateur.",
                    color=discord.Color.red()
                )
                await confirm_msg.edit(embed=cancel_embed)
                return
                
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Temps écoulé",
                description="La confirmation a expiré. Restauration annulée.",
                color=discord.Color.orange()
            )
            await confirm_msg.edit(embed=timeout_embed)
            return

        # Créer l'embed de progression
        progress_embed = discord.Embed(
            title="🔄 Restauration en cours...",
            description=f"Restauration du serveur avec **{name}**",
            color=discord.Color.blue()
        )
        progress_embed.add_field(name="Statut", value="⏳ Chargement des données...", inline=False)
        
        progress_msg = await ctx.send(embed=progress_embed)

        try:
            # Charger les données
            backup_data = await self.load_backup_file(name)
            if not backup_data:
                error_embed = discord.Embed(
                    title="❌ Fichier introuvable",
                    description=f"Le fichier de sauvegarde **{name}.json** n'a pas été trouvé !",
                    color=discord.Color.red()
                )
                await progress_msg.edit(embed=error_embed)
                return
            
            # Mettre à jour le statut
            progress_embed.set_field_at(0, name="Statut", value="🔨 Restauration de la structure...", inline=False)
            await progress_msg.edit(embed=progress_embed)
            
            # Restaurer le serveur
            success = await self.restore_server(ctx.guild, backup_data)
            
            if success:
                success_embed = discord.Embed(
                    title="✅ Restauration terminée",
                    description=f"Le serveur a été restauré avec la sauvegarde **{name}** !",
                    color=discord.Color.green()
                )
                success_embed.add_field(name="Rôles créés", value=str(len(backup_data["roles"])), inline=True)
                success_embed.add_field(name="Catégories créées", value=str(len(backup_data["categories"])), inline=True)
                success_embed.add_field(name="Salons créés", value=str(len(backup_data["channels"])), inline=True)
                success_embed.add_field(name="Emojis créés", value=str(len(backup_data["emojis"])), inline=True)
                success_embed.set_footer(text=f"Restauré par {ctx.author.name}")
                
                await progress_msg.edit(embed=success_embed)
            else:
                error_embed = discord.Embed(
                    title="❌ Erreur lors de la restauration",
                    description="Une erreur s'est produite lors de la restauration du serveur.",
                    color=discord.Color.red()
                )
                await progress_msg.edit(embed=error_embed)
                
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Erreur lors de la restauration",
                description=f"Une erreur s'est produite : {str(e)}",
                color=discord.Color.red()
            )
            await progress_msg.edit(embed=error_embed)

    async def list_backups(self, ctx):
        """Liste les sauvegardes disponibles"""
        backups = self.get_backups(ctx.guild.id)
        
        if not backups:
            embed = discord.Embed(
                title="📋 Liste des sauvegardes",
                description="Aucune sauvegarde trouvée pour ce serveur.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📋 Liste des sauvegardes",
            description=f"**{len(backups)}** sauvegarde(s) trouvée(s) pour **{ctx.guild.name}**",
            color=discord.Color.blue()
        )
        
        for name, server_name, created_at, created_by, description in backups[:10]:  # Limiter à 10
            try:
                creator = await self.bot.fetch_user(created_by)
                creator_name = creator.name
            except:
                creator_name = f"Utilisateur {created_by}"
            
            date = created_at[:10] if created_at else "Inconnue"
            
            embed.add_field(
                name=f"💾 {name}",
                value=f"**Serveur:** {server_name}\n**Créée par:** {creator_name}\n**Date:** {date}\n**Description:** {description or 'Aucune'}",
                inline=False
            )
        
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

    async def backup_info(self, ctx, name):
        """Affiche les informations d'une sauvegarde"""
        backup_info = self.get_backup_info(name)
        
        if not backup_info:
            embed = discord.Embed(
                title="❌ Sauvegarde introuvable",
                description=f"Aucune sauvegarde nommée **{name}** n'a été trouvée !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Charger les données pour plus d'informations
        backup_data = await self.load_backup_file(name)
        
        embed = discord.Embed(
            title=f"💾 Informations de la sauvegarde",
            description=f"**{name}**",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Serveur", value=backup_info[1], inline=True)
        embed.add_field(name="Créée le", value=backup_info[2][:19], inline=True)
        
        try:
            creator = await self.bot.fetch_user(backup_info[3])
            creator_name = creator.name
        except:
            creator_name = f"Utilisateur {backup_info[3]}"
        
        embed.add_field(name="Créée par", value=creator_name, inline=True)
        
        if backup_data:
            embed.add_field(name="Rôles", value=str(len(backup_data["roles"])), inline=True)
            embed.add_field(name="Catégories", value=str(len(backup_data["categories"])), inline=True)
            embed.add_field(name="Salons", value=str(len(backup_data["channels"])), inline=True)
            embed.add_field(name="Emojis", value=str(len(backup_data["emojis"])), inline=True)
        
        embed.add_field(name="Description", value=backup_info[5] or "Aucune", inline=False)
        embed.add_field(name="Fichier", value=f"{name}.json", inline=False)
        
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

    async def delete_backup_cmd(self, ctx, name):
        """Supprime une sauvegarde"""
        backup_info = self.get_backup_info(name)
        
        if not backup_info:
            embed = discord.Embed(
                title="❌ Sauvegarde introuvable",
                description=f"Aucune sauvegarde nommée **{name}** n'a été trouvée !",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Confirmation
        confirm_embed = discord.Embed(
            title="⚠️ Confirmation de suppression",
            description=f"Êtes-vous sûr de vouloir supprimer la sauvegarde **{name}** ?",
            color=discord.Color.orange()
        )
        confirm_embed.add_field(name="⚠️ Attention", value="Cette action est irréversible !", inline=False)
        confirm_embed.add_field(name="Serveur", value=backup_info[1], inline=True)
        confirm_embed.add_field(name="Créée le", value=backup_info[2][:10], inline=True)
        
        confirm_msg = await ctx.send(embed=confirm_embed)
        
        # Ajouter les réactions
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        try:
            reaction, user = await self.bot.wait_for(
                'reaction_add',
                timeout=30.0,
                check=lambda r, u: u == ctx.author and r.message.id == confirm_msg.id and str(r.emoji) in ["✅", "❌"]
            )
            
            if str(reaction.emoji) == "❌":
                cancel_embed = discord.Embed(
                    title="❌ Suppression annulée",
                    description="La suppression a été annulée par l'utilisateur.",
                    color=discord.Color.red()
                )
                await confirm_msg.edit(embed=cancel_embed)
                return
                
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Temps écoulé",
                description="La confirmation a expiré. Suppression annulée.",
                color=discord.Color.orange()
            )
            await confirm_msg.edit(embed=timeout_embed)
            return

        try:
            # Supprimer le fichier
            file_path = os.path.join(self.backup_dir, f"{name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Supprimer de la base de données
            self.delete_backup(name)
            
            success_embed = discord.Embed(
                title="✅ Sauvegarde supprimée",
                description=f"La sauvegarde **{name}** a été supprimée avec succès !",
                color=discord.Color.green()
            )
            success_embed.add_field(name="Supprimée par", value=ctx.author.mention, inline=False)
            
            await confirm_msg.edit(embed=success_embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Erreur lors de la suppression",
                description=f"Une erreur s'est produite : {str(e)}",
                color=discord.Color.red()
            )
            await confirm_msg.edit(embed=error_embed)

    # -- ERROR HANDLERS --

    @backup.error
    async def backup_error(self, ctx, error):
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
                description="Usage: `+backup <action> [nom] [description]`\nActions: `create`, `load`, `list`, `info`, `delete`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Backup(bot)) 