import discord
from discord.ext import commands
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
import os

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'server.db'
        self.voice_tracking = {}  # {user_id: {'joined_at': timestamp, 'last_check': timestamp}}
        self.last_messages = {}  # {user_id: last_message_content}
        self.xp_cooldown = {}  # {user_id: last_xp_gain_time}
        self.voice_cooldown = {}  # {user_id: last_voice_xp_time}
        
        # Configuration
        self.message_xp_range = (15, 25)  # XP gagné par message
        self.long_message_bonus = 2  # Multiplicateur pour messages > 4000 caractères
        self.voice_xp_per_minute = 10  # XP gagné par minute en vocal
        self.min_message_length = 20  # Longueur minimale pour gagner de l'XP
        self.message_cooldown = 60  # Cooldown entre gains d'XP (secondes)
        self.voice_check_interval = 60  # Intervalle de vérification vocal (secondes)
        
        # Initialiser la base de données
        self.init_database()
        
        # Démarrer le tracking vocal
        self.bot.loop.create_task(self.voice_xp_tracker())

    # -- DATABASE --

    def init_database(self):
        """Initialise la base de données SQLite pour les niveaux"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Créer la table des niveaux
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS levels (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                total_messages INTEGER DEFAULT 0,
                total_voice_time INTEGER DEFAULT 0,
                last_message_time TIMESTAMP,
                last_voice_xp_time TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def get_user_data(self, user_id):
        """Récupère les données d'un utilisateur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT xp, level, total_messages, total_voice_time 
            FROM levels 
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result is None:
            # Créer un nouveau profil
            self.create_user_profile(user_id)
            return (0, 1, 0, 0)
        
        return result

    def create_user_profile(self, user_id):
        """Crée un nouveau profil utilisateur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO levels (user_id, xp, level, total_messages, total_voice_time)
            VALUES (?, 0, 1, 0, 0)
        ''', (user_id,))
        
        conn.commit()
        conn.close()

    def update_user_xp(self, user_id, xp_gained, message_count=0, voice_time=0):
        """Met à jour l'XP d'un utilisateur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Récupérer les données actuelles
        cursor.execute('''
            SELECT xp, level, total_messages, total_voice_time 
            FROM levels 
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        
        if result is None:
            # Créer un nouveau profil
            cursor.execute('''
                INSERT INTO levels (user_id, xp, level, total_messages, total_voice_time, last_message_time)
                VALUES (?, ?, 1, ?, ?, ?)
            ''', (user_id, xp_gained, message_count, voice_time, datetime.now()))
        else:
            current_xp, current_level, current_messages, current_voice = result
            new_xp = current_xp + xp_gained
            new_level = self.calculate_level(new_xp)
            new_messages = current_messages + message_count
            new_voice = current_voice + voice_time
            
            cursor.execute('''
                UPDATE levels 
                SET xp = ?, level = ?, total_messages = ?, total_voice_time = ?, last_message_time = ?
                WHERE user_id = ?
            ''', (new_xp, new_level, new_messages, new_voice, datetime.now(), user_id))
        
        conn.commit()
        conn.close()
        
        return new_level if result else 1

    def calculate_level(self, xp):
        """Calcule le niveau basé sur l'XP"""
        # Formule : niveau = 1 + sqrt(xp / 100)
        return max(1, int(1 + (xp / 100) ** 0.5))

    def calculate_xp_for_next_level(self, current_level):
        """Calcule l'XP nécessaire pour le niveau suivant"""
        return (current_level ** 2 - 1) * 100

    # -- MESSAGE XP SYSTEM --

    @commands.Cog.listener()
    async def on_message(self, message):
        """Gère le gain d'XP par messages"""
        # Ignorer les messages du bot et les commandes
        if message.author.bot or message.content.startswith('+'):
            return
        
        user_id = message.author.id
        current_time = datetime.now()
        
        # Vérifier le cooldown
        if user_id in self.xp_cooldown:
            time_diff = (current_time - self.xp_cooldown[user_id]).total_seconds()
            if time_diff < self.message_cooldown:
                return
        
        # Vérifier la longueur du message
        if len(message.content) < self.min_message_length:
            return
        
        # Vérifier si le message n'est pas répété
        if user_id in self.last_messages:
            if message.content.lower().strip() == self.last_messages[user_id].lower().strip():
                return
        
        # Calculer l'XP gagné
        import random
        base_xp = random.randint(*self.message_xp_range)
        
        # Bonus pour messages longs
        if len(message.content) > 4000:
            base_xp *= self.long_message_bonus
        
        # Mettre à jour les données
        old_level = self.get_user_data(user_id)[1]
        new_level = self.update_user_xp(user_id, base_xp, 1)
        
        # Mettre à jour les trackers
        self.last_messages[user_id] = message.content
        self.xp_cooldown[user_id] = current_time
        
        # Notification de niveau supérieur
        if new_level > old_level:
            embed = discord.Embed(
                title="🎉 Niveau supérieur !",
                description=f"Félicitations {message.author.mention} ! Tu as atteint le niveau **{new_level}** !",
                color=discord.Color.gold()
            )
            embed.add_field(name="XP gagné", value=f"+{base_xp} XP", inline=True)
            embed.add_field(name="Niveau", value=f"{old_level} → {new_level}", inline=True)
            embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)
            embed.set_footer(text=f"Message #{self.get_user_data(user_id)[2]}")
            
            await message.channel.send(embed=embed)

    # -- VOICE XP SYSTEM --

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Gère le tracking vocal"""
        if member.bot:
            return
        
        user_id = member.id
        
        # Membre rejoint un canal vocal
        if before.channel is None and after.channel is not None:
            self.voice_tracking[user_id] = {
                'joined_at': datetime.now(),
                'last_check': datetime.now()
            }
        
        # Membre quitte un canal vocal
        elif before.channel is not None and after.channel is None:
            if user_id in self.voice_tracking:
                # Calculer le temps passé en vocal
                joined_time = self.voice_tracking[user_id]['joined_at']
                time_spent = (datetime.now() - joined_time).total_seconds()
                
                # Donner de l'XP pour le temps passé
                if time_spent >= 60:  # Au moins 1 minute
                    xp_gained = int(time_spent / 60) * self.voice_xp_per_minute
                    old_level = self.get_user_data(user_id)[1]
                    new_level = self.update_user_xp(user_id, xp_gained, 0, int(time_spent))
                    
                    # Notification de niveau supérieur
                    if new_level > old_level:
                        embed = discord.Embed(
                            title="🎉 Niveau supérieur !",
                            description=f"Félicitations {member.mention} ! Tu as atteint le niveau **{new_level}** en vocal !",
                            color=discord.Color.gold()
                        )
                        embed.add_field(name="Temps en vocal", value=f"{int(time_spent/60)} minutes", inline=True)
                        embed.add_field(name="XP gagné", value=f"+{xp_gained} XP", inline=True)
                        embed.add_field(name="Niveau", value=f"{old_level} → {new_level}", inline=True)
                        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                        
                        # Envoyer dans le canal système ou le premier canal textuel
                        for channel in member.guild.text_channels:
                            if channel.permissions_for(member.guild.me).send_messages:
                                await channel.send(embed=embed)
                                break
                
                del self.voice_tracking[user_id]

    async def voice_xp_tracker(self):
        """Tracker vocal en arrière-plan"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                current_time = datetime.now()
                
                for user_id, data in list(self.voice_tracking.items()):
                    # Vérifier si l'utilisateur est toujours en vocal
                    try:
                        user = await self.bot.fetch_user(user_id)
                        guild = None
                        
                        # Trouver le serveur où l'utilisateur est en vocal
                        for g in self.bot.guilds:
                            member = g.get_member(user_id)
                            if member and member.voice and not member.voice.afk:
                                guild = g
                                break
                        
                        if guild and guild.get_member(user_id).voice and not guild.get_member(user_id).voice.afk:
                            # Utilisateur toujours en vocal et actif
                            time_diff = (current_time - data['last_check']).total_seconds()
                            
                            if time_diff >= self.voice_check_interval:
                                # Donner de l'XP pour le temps passé
                                xp_gained = int(self.voice_check_interval / 60) * self.voice_xp_per_minute
                                old_level = self.get_user_data(user_id)[1]
                                new_level = self.update_user_xp(user_id, xp_gained, 0, self.voice_check_interval)
                                
                                # Mettre à jour le dernier check
                                self.voice_tracking[user_id]['last_check'] = current_time
                                
                                # Notification de niveau supérieur
                                if new_level > old_level:
                                    member = guild.get_member(user_id)
                                    embed = discord.Embed(
                                        title="🎉 Niveau supérieur !",
                                        description=f"Félicitations {member.mention} ! Tu as atteint le niveau **{new_level}** en vocal !",
                                        color=discord.Color.gold()
                                    )
                                    embed.add_field(name="XP gagné", value=f"+{xp_gained} XP", inline=True)
                                    embed.add_field(name="Niveau", value=f"{old_level} → {new_level}", inline=True)
                                    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                                    
                                    # Envoyer dans le premier canal textuel disponible
                                    for channel in guild.text_channels:
                                        if channel.permissions_for(guild.me).send_messages:
                                            await channel.send(embed=embed)
                                            break
                        else:
                            # Utilisateur n'est plus en vocal, le retirer du tracking
                            del self.voice_tracking[user_id]
                    
                    except:
                        # Utilisateur introuvable, le retirer du tracking
                        if user_id in self.voice_tracking:
                            del self.voice_tracking[user_id]
                
                await asyncio.sleep(self.voice_check_interval)
                
            except Exception as e:
                print(f"Erreur dans voice_xp_tracker: {e}")
                await asyncio.sleep(10)

    # -- COMMANDS --

    @commands.command(name='rank', aliases=['r'], brief="Affiche ton niveau et ton XP")
    async def rank(self, ctx, member: discord.Member = None):
        """Affiche le niveau et l'XP d'un membre"""
        if member is None:
            member = ctx.author
        
        xp, level, total_messages, total_voice_time = self.get_user_data(member.id)
        xp_for_next = self.calculate_xp_for_next_level(level)
        progress = xp - self.calculate_xp_for_next_level(level - 1)
        needed = xp_for_next - self.calculate_xp_for_next_level(level - 1)
        percentage = min(100, (progress / needed) * 100) if needed > 0 else 100
        
        # Créer la barre de progression
        bar_length = 20
        filled_length = int(bar_length * percentage / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        embed = discord.Embed(
            title=f"🏆 Niveau de {member.display_name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Statistiques",
            value=f"**Niveau:** {level}\n**XP:** {xp:,} / {xp_for_next:,}\n**Progression:** {progress:,} / {needed:,}",
            inline=True
        )
        
        embed.add_field(
            name="📈 Progression",
            value=f"`{bar}` {percentage:.1f}%",
            inline=True
        )
        
        embed.add_field(
            name="📝 Activité",
            value=f"**Messages:** {total_messages:,}\n**Temps vocal:** {int(total_voice_time/60)} minutes",
            inline=False
        )
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        
        await ctx.send(embed=embed)

    @commands.command(name='top', aliases=['leaderboard'], brief="Affiche le classement des niveaux")
    async def top(self, ctx):
        """Affiche le classement des niveaux"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, xp, level, total_messages, total_voice_time 
            FROM levels 
            ORDER BY xp DESC 
            LIMIT 10
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            embed = discord.Embed(
                title="🏆 Classement des niveaux",
                description="Aucun utilisateur trouvé dans le classement.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🏆 Classement des niveaux",
            description="Les 10 membres avec le plus d'XP",
            color=discord.Color.gold()
        )
        
        for i, (user_id, xp, level, messages, voice_time) in enumerate(results, 1):
            try:
                member = await ctx.guild.fetch_member(user_id)
                username = member.display_name
                avatar = member.avatar.url if member.avatar else member.default_avatar.url
            except:
                username = f"Utilisateur {user_id}"
                avatar = None
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
            
            embed.add_field(
                name=f"{medal} {username}",
                value=f"**Niveau:** {level} | **XP:** {xp:,}\n**Messages:** {messages:,} | **Vocal:** {int(voice_time/60)}min",
                inline=False
            )
        
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

    @commands.command(name='levels', aliases=['l'], brief="Affiche les informations du système de niveaux")
    async def levels(self, ctx):
        """Affiche les informations du système de niveaux"""
        embed = discord.Embed(
            title="📊 Système de niveaux",
            description="Informations sur le système de gain d'XP",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💬 Messages",
            value=f"**XP par message:** {self.message_xp_range[0]}-{self.message_xp_range[1]}\n**Bonus long message:** x{self.long_message_bonus} (>4000 caractères)\n**Longueur minimale:** {self.min_message_length} caractères\n**Cooldown:** {self.message_cooldown} secondes",
            inline=False
        )
        
        embed.add_field(
            name="🎤 Vocal",
            value=f"**XP par minute:** {self.voice_xp_per_minute}\n**Vérification:** {self.voice_check_interval} secondes\n**AFK:** Pas de gain d'XP",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Anti-spam",
            value="• Messages trop courts ignorés\n• Messages répétés ignorés\n• Cooldown entre gains d'XP\n• Vérification de présence active en vocal",
            inline=False
        )
        
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Levels(bot)) 