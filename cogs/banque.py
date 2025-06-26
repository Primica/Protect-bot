import discord
from discord.ext import commands
import sqlite3
import json
from datetime import datetime
import os

class Banque(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'server.db'
        self.logs_file = 'banque_logs.json'
        self.casino_cooldown = {}  # {user_id: last_use_time}
        self.casino_cooldown_duration = 300  # 5 minutes en secondes
        
        # Initialiser la base de données
        self.init_database()
        
        # Créer le fichier de logs s'il n'existe pas
        if not os.path.exists(self.logs_file):
            with open(self.logs_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    # -- DATABASE --

    def init_database(self):
        """Initialise la base de données SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Créer la table des comptes bancaires
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banque (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 1000,
                last_casino TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def log_transaction(self, action, user_id, target_id=None, amount=None, success=True):
        """Enregistre une transaction dans le fichier de logs"""
        try:
            with open(self.logs_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = []
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id,
            "target_id": target_id,
            "amount": amount,
            "success": success
        }
        
        logs.append(log_entry)
        
        with open(self.logs_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

    def get_balance(self, user_id):
        """Récupère le solde d'un utilisateur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance FROM banque WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result is None:
            # Créer un nouveau compte avec 1000 coins
            cursor.execute('INSERT INTO banque (user_id, balance) VALUES (?, ?)', (user_id, 1000))
            conn.commit()
            balance = 1000
        else:
            balance = result[0]
        
        conn.close()
        return balance

    def update_balance(self, user_id, amount):
        """Met à jour le solde d'un utilisateur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance FROM banque WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result is None:
            cursor.execute('INSERT INTO banque (user_id, balance) VALUES (?, ?)', (user_id, 1000 + amount))
        else:
            new_balance = result[0] + amount
            cursor.execute('UPDATE banque SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        
        conn.commit()
        conn.close()

    # -- COMMANDS --

    @commands.command(name='bank', aliases=['bk'], brief="Affiche le solde bancaire d'un membre", usage="+bank [@membre]")
    async def bank(self, ctx, member: discord.Member = None):
        """Affiche le solde bancaire d'un membre"""
        if member is None:
            member = ctx.author
        
        balance = self.get_balance(member.id)
        
        embed = discord.Embed(
            title="🏦 Banque Rubix",
            description=f"**Solde de {member.mention}**",
            color=0x00ff00
        )
        embed.add_field(name="💰 Balance", value=f"**{balance:,}** coins", inline=False)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        
        await ctx.send(embed=embed)

    @commands.command(name='give', aliases=['donner'], brief="Donne de l'argent à un membre", usage="+give <@membre> <montant>")
    @commands.has_permissions(administrator=True)
    async def give(self, ctx, member: discord.Member, amount: int):
        """Donne de l'argent à un membre (Admin uniquement)"""
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Erreur",
                description="Le montant doit être positif !",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        old_balance = self.get_balance(member.id)
        self.update_balance(member.id, amount)
        new_balance = self.get_balance(member.id)
        
        # Log de la transaction
        self.log_transaction("give", ctx.author.id, member.id, amount, True)
        
        embed = discord.Embed(
            title="💰 Don effectué",
            description=f"**{ctx.author.mention}** a donné **{amount:,}** coins à **{member.mention}**",
            color=0x00ff00
        )
        embed.add_field(name="Ancien solde", value=f"{old_balance:,} coins", inline=True)
        embed.add_field(name="Nouveau solde", value=f"{new_balance:,} coins", inline=True)
        embed.set_footer(text=f"Transaction effectuée par {ctx.author.name}")
        
        await ctx.send(embed=embed)

    @give.error
    async def give_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission refusée",
                description="Vous devez être administrateur pour utiliser cette commande !",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @commands.command(name='classement', aliases=['tableau'], brief="Affiche le classement des plus riches", usage="+classement")
    async def top(self, ctx):
        """Affiche le classement des plus riches"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, balance FROM banque ORDER BY balance DESC LIMIT 10')
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            embed = discord.Embed(
                title="🏆 Classement des riches",
                description="Aucun utilisateur trouvé dans la base de données.",
                color=0xffd700
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🏆 Classement des riches",
            description="Les 10 membres les plus riches du serveur",
            color=0xffd700
        )
        
        for i, (user_id, balance) in enumerate(results, 1):
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
                value=f"💰 **{balance:,}** coins",
                inline=False
            )
        
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

    @commands.command(name='casino', aliases=['cas'], brief="Joue au casino pour gagner de l'argent (cooldown 5 minutes)", usage="+casino")
    async def casino(self, ctx):
        """Joue au casino pour gagner de l'argent (cooldown 5 minutes)"""
        user_id = ctx.author.id
        current_time = datetime.now()
        
        # Vérifier le cooldown
        if user_id in self.casino_cooldown:
            time_diff = current_time - self.casino_cooldown[user_id]
            if time_diff.total_seconds() < self.casino_cooldown_duration:
                remaining = self.casino_cooldown_duration - int(time_diff.total_seconds())
                minutes = remaining // 60
                seconds = remaining % 60
                
                embed = discord.Embed(
                    title="⏰ Cooldown actif",
                    description=f"Vous devez attendre encore **{minutes}m {seconds}s** avant de pouvoir rejouer !",
                    color=0xffa500
                )
                await ctx.send(embed=embed)
                return
        
        # Mettre à jour le cooldown
        self.casino_cooldown[user_id] = current_time
        
        # Logique du casino
        import random
        chance = random.random()
        
        if chance < 0.4:  # 40% de chance de gagner
            win_amount = random.randint(50, 200)
            self.update_balance(user_id, win_amount)
            result = "gagné"
            color = 0x00ff00
            emoji = "🎉"
        elif chance < 0.7:  # 30% de chance de perdre peu
            lose_amount = random.randint(10, 50)
            self.update_balance(user_id, -lose_amount)
            result = "perdu"
            color = 0xffa500
            emoji = "😐"
        else:  # 30% de chance de perdre beaucoup
            lose_amount = random.randint(50, 150)
            self.update_balance(user_id, -lose_amount)
            result = "perdu"
            color = 0xff0000
            emoji = "💸"
        
        new_balance = self.get_balance(user_id)
        
        # Log de la transaction
        if result == "gagné":
            self.log_transaction("casino_win", user_id, None, win_amount, True)
        else:
            self.log_transaction("casino_loss", user_id, None, lose_amount, True)
        
        embed = discord.Embed(
            title=f"{emoji} Casino Rubix",
            description=f"**{ctx.author.mention}** a **{result}** !",
            color=color
        )
        
        if result == "gagné":
            embed.add_field(name="💰 Gains", value=f"+{win_amount:,} coins", inline=True)
        else:
            embed.add_field(name="💸 Pertes", value=f"-{lose_amount:,} coins", inline=True)
        
        embed.add_field(name="🏦 Nouveau solde", value=f"{new_balance:,} coins", inline=True)
        embed.set_footer(text=f"Prochain jeu disponible dans 5 minutes")
        
        await ctx.send(embed=embed)

    @commands.command(name='logs', aliases=['lg'], brief="Affiche les derniers logs de transactions (Admin uniquement)", usage="+logs <limite>")
    @commands.has_permissions(administrator=True)
    async def logs(self, ctx, limit: int = 10):
        """Affiche les derniers logs de transactions (Admin uniquement)"""
        try:
            with open(self.logs_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = []
        
        if not logs:
            embed = discord.Embed(
                title="📋 Logs de transactions",
                description="Aucun log trouvé.",
                color=0x808080
            )
            await ctx.send(embed=embed)
            return
        
        # Prendre les derniers logs
        recent_logs = logs[-limit:] if limit > 0 else logs
        
        embed = discord.Embed(
            title="📋 Logs de transactions",
            description=f"Dernières {len(recent_logs)} transactions",
            color=0x808080
        )
        
        for log in recent_logs:
            timestamp = datetime.fromisoformat(log['timestamp']).strftime("%d/%m %H:%M")
            action = log['action']
            user_id = log['user_id']
            amount = log.get('amount', 0)
            
            try:
                user = await self.bot.fetch_user(user_id)
                username = user.name
            except:
                username = f"User {user_id}"
            
            if action == "give":
                target_id = log.get('target_id')
                try:
                    target = await self.bot.fetch_user(target_id)
                    target_name = target.name
                except:
                    target_name = f"User {target_id}"
                description = f"**{username}** → **{target_name}** (+{amount:,})"
            elif action == "casino_win":
                description = f"**{username}** 🎰 (+{amount:,})"
            elif action == "casino_loss":
                description = f"**{username}** 🎰 (-{amount:,})"
            else:
                description = f"**{username}** - {action}"
            
            embed.add_field(
                name=f"📅 {timestamp}",
                value=description,
                inline=False
            )
        
        embed.set_footer(text=f"Demandé par {ctx.author.name}")
        await ctx.send(embed=embed)

    @logs.error
    async def logs_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission refusée",
                description="Vous devez être administrateur pour utiliser cette commande !",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    # -- ERROR HANDLERS --

    @bank.error
    async def bank_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission refusée",
                description="Vous devez être administrateur pour utiliser cette commande !",
                color=0xff0000
            )
            await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Banque(bot))

