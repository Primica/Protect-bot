import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='man', brief='Affiche l\'aide détaillée sur les commandes', usage='+man [commande/catégorie]')
    async def man(self, ctx, *, query=None):
        """Affiche l'aide détaillée sur les commandes et catégories du bot"""
        
        if query is None: 
            # Afficher la page d'accueil avec toutes les catégories
            await self.show_main_help(ctx)
        else:
            # Rechercher une commande ou catégorie spécifique
            await self.show_specific_help(ctx, query)

    async def show_main_help(self, ctx):
        """Affiche la page d'accueil de l'aide"""
        embed = discord.Embed(
            title="📚 Guide d'utilisation du bot",
            description="Bienvenue dans le système d'aide ! Utilisez `+man <catégorie>` pour voir les commandes d'une catégorie spécifique.\n\n**Catégories disponibles :**",
            color=0x3498db
        )

        # Organiser les commandes par catégorie
        categories = {}
        for cog_name, cog in self.bot.cogs.items():
            if cog_name.lower() != 'help':  # Exclure le cog help lui-même
                categories[cog_name] = []
                for command in cog.get_commands():
                    if not command.hidden:
                        categories[cog_name].append(command)

        # Ajouter chaque catégorie à l'embed
        for category, commands_list in categories.items():
            if commands_list:  # Seulement afficher les catégories avec des commandes
                command_count = len(commands_list)
                category_emoji = self.get_category_emoji(category)
                embed.add_field(
                    name=f"{category_emoji} {category} ({command_count} commande{'s' if command_count > 1 else ''})",
                    value=f"`+man {category.lower()}`",
                    inline=True
                )

        embed.add_field(
            name="🔍 Recherche de commande",
            value="Utilisez `+man <nom_commande>` pour voir l'aide d'une commande spécifique",
            inline=False
        )

        embed.set_footer(text="Protect-bot • Système d'aide")
        embed.timestamp = discord.utils.utcnow()

        await ctx.send(embed=embed)

    async def show_specific_help(self, ctx, query):
        """Affiche l'aide pour une commande ou catégorie spécifique"""
        query = query.lower().strip()

        # D'abord, essayer de trouver une catégorie
        category_found = await self.show_category_help(ctx, query)
        if category_found:
            return

        # Si aucune catégorie trouvée, chercher une commande
        command_found = await self.show_command_help(ctx, query)
        if not command_found:
            await ctx.send(f"❌ Aucune commande ou catégorie trouvée pour `{query}`. Utilisez `+man` pour voir toutes les catégories disponibles.")

    async def show_category_help(self, ctx, category_name):
        """Affiche l'aide pour une catégorie spécifique"""
        category_emoji = self.get_category_emoji(category_name)
        
        # Chercher la catégorie
        target_cog = None
        for cog_name, cog in self.bot.cogs.items():
            if cog_name.lower() == category_name.lower():
                target_cog = cog
                break

        if not target_cog:
            return False

        embed = discord.Embed(
            title=f"{category_emoji} Catégorie : {target_cog.__cog_name__}",
            description=f"Commandes disponibles dans cette catégorie :",
            color=0x2ecc71
        )

        commands_list = [cmd for cmd in target_cog.get_commands() if not cmd.hidden]
        
        if not commands_list:
            embed.description = "Aucune commande publique dans cette catégorie."
        else:
            for command in commands_list:
                # Vérifier les permissions de l'utilisateur
                can_use = True
                if command.checks:
                    try:
                        await command.can_run(ctx)
                    except:
                        can_use = False

                status = "✅" if can_use else "❌"
                usage = command.usage if hasattr(command, 'usage') else f"+{command.name}"
                
                embed.add_field(
                    name=f"{status} {command.name}",
                    value=f"**Description :** {command.brief or 'Aucune description'}\n**Usage :** `{usage}`",
                    inline=False
                )

        embed.set_footer(text=f"Utilisez +man <commande> pour plus de détails sur une commande spécifique")
        await ctx.send(embed=embed)
        return True

    async def show_command_help(self, ctx, command_name):
        """Affiche l'aide détaillée pour une commande spécifique"""
        command = self.bot.get_command(command_name)
        
        if not command:
            # Chercher dans les alias
            for cmd in self.bot.walk_commands():
                if command_name in cmd.aliases:
                    command = cmd
                    break

        if not command:
            return False

        embed = discord.Embed(
            title=f"📖 Commande : {command.name}",
            description=command.help or "Aucune description détaillée disponible.",
            color=0xe74c3c
        )

        # Informations de base
        usage = command.usage if hasattr(command, 'usage') else f"+{command.name}"
        embed.add_field(
            name="📝 Usage",
            value=f"`{usage}`",
            inline=False
        )

        # Alias
        if command.aliases:
            aliases_text = ", ".join([f"`+{alias}`" for alias in command.aliases])
            embed.add_field(
                name="🔄 Alias",
                value=aliases_text,
                inline=True
            )

        # Catégorie
        cog_name = command.cog.__cog_name__ if command.cog else "Aucune"
        embed.add_field(
            name="📁 Catégorie",
            value=cog_name,
            inline=True
        )

        # Permissions requises
        if command.checks:
            perms = []
            for check in command.checks:
                if hasattr(check, '__name__'):
                    if check.__name__ == 'has_permissions':
                        # Extraire les permissions si possible
                        perms.append("Permissions spéciales requises")
                    else:
                        perms.append(check.__name__)
            
            if perms:
                embed.add_field(
                    name="🔒 Permissions",
                    value="\n".join(perms),
                    inline=False
                )

        # Vérifier si l'utilisateur peut utiliser la commande
        can_use = True
        try:
            await command.can_run(ctx)
        except:
            can_use = False

        status = "✅ Vous pouvez utiliser cette commande" if can_use else "❌ Vous ne pouvez pas utiliser cette commande"
        embed.add_field(
            name="📊 Statut",
            value=status,
            inline=False
        )

        embed.set_footer(text=f"Protect-bot • Commande {command.name}")
        embed.timestamp = discord.utils.utcnow()

        await ctx.send(embed=embed)
        return True

    def get_category_emoji(self, category_name):
        """Retourne l'emoji approprié pour une catégorie"""
        emoji_map = {
            'utils': '🛠️',
            'backup': '💾',
            'ban': '🔨',
            'banque': '💰',
            'infos': 'ℹ️',
            'levels': '📈',
            'security': '🔒',
            'ticket': '🎫',
            'help': '📚'
        }
        
        category_lower = category_name.lower()
        return emoji_map.get(category_lower, '📁')

    @man.error
    async def man_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send("❌ Une erreur s'est produite lors de l'affichage de l'aide.")
        else:
            await ctx.send(f"❌ Erreur : {str(error)}")

def setup(bot):
    bot.add_cog(Help(bot)) 