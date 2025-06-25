import discord 
from discord.ext import commands
from functools import wraps
from datetime import datetime, timedelta

class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -- ROLES RELATED COMMANDS --

    @commands.command(name='addrole', aliases=['ar'], brief='Add a role to a user', usage='+addrole <user> <role>')
    @commands.has_permissions(manage_roles=True)
    async def addrole(self, ctx, user: discord.Member, role: discord.Role):
        try:
            await user.add_roles(role)
            await ctx.send(f'✅ Added {role.mention} to {user.mention}')
        except discord.Forbidden:
            await ctx.send('❌ I do not have permission to add this role')
        except discord.HTTPException as e:
            await ctx.send(f'❌ Error adding role: {str(e)}')

    @commands.command(name='removerole', aliases=['rr'], brief='Remove a role from a user', usage='+removerole <user> <role>')
    @commands.has_permissions(manage_roles=True)
    async def removerole(self, ctx, user: discord.Member, role: discord.Role):
        try:
            await user.remove_roles(role)
            await ctx.send(f'✅ Removed {role.mention} from {user.mention}')
        except discord.Forbidden:
            await ctx.send('❌ I do not have permission to remove this role')
        except discord.HTTPException as e:
            await ctx.send(f'❌ Error removing role: {str(e)}')

    @commands.command(name='deleterole', aliases=['dr'], brief='Delete a role', usage='+deleterole <role>')
    @commands.has_permissions(manage_roles=True)
    async def deleterole(self, ctx, role: discord.Role):
        try:
            role_name = role.name
            await role.delete()
            await ctx.send(f'✅ Deleted role: {role_name}')
        except discord.Forbidden:
            await ctx.send('❌ I do not have permission to delete this role')
        except discord.HTTPException as e:
            await ctx.send(f'❌ Error deleting role: {str(e)}')

    # -- CHANNEL RELATED COMMANDS --

    @commands.command(name='say', aliases=['s'], brief='Make the bot say something', usage='+say <message>')
    async def say(self, ctx, *, message):
        try:
            await ctx.message.delete()
            await ctx.send(message)
        except discord.Forbidden:
            await ctx.send('❌ I do not have permission to delete messages or send messages in this channel')

    @commands.command(name='clear', aliases=['c'], brief='Clear a number of messages', usage='+clear <number>')
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send('❌ Please specify a positive number of messages to delete')
            return
            
        if amount > 100:
            await ctx.send('❌ You cannot clear more than 100 messages at once')
            return
            
        try:
            deleted_messages = await ctx.channel.purge(limit=amount, check=lambda m: not m.pinned)
            deleted_count = len(deleted_messages)
            
            if deleted_count < amount:
                failed_count = amount - deleted_count
                message = f'✅ Cleared {deleted_count} messages. {failed_count} messages could not be deleted (messages older than 14 days cannot be deleted by Discord).'
                await ctx.send(message, delete_after=10)
                print(f"[WARNING] Failed to delete {failed_count} messages in channel {ctx.channel.name} (likely older than 14 days)")
            else:
                await ctx.send(f'✅ Cleared {deleted_count} messages', delete_after=5)
                
        except discord.Forbidden:
            await ctx.send('❌ I do not have permission to delete messages in this channel')
        except discord.HTTPException as e:
            await ctx.send(f'❌ Error clearing messages: {str(e)}')
            print(f"[ERROR] Error in clear command: {str(e)}")

    @commands.command(name='timeout', aliases=['to'], brief='Timeout a user', usage='+timeout <user> <duration> <reason>')
    @commands.has_permissions(manage_roles=True)
    async def timeout(self, ctx, user: discord.Member, duration: int, *, reason=None):
        try:
            duration_seconds = duration * 60
            timeout_end = datetime.now() + timedelta(seconds=duration_seconds)
            await user.timeout(timeout_end, reason=reason)
            await ctx.send(f'✅ Timed out {user.mention} for {duration} minutes ({reason})')
        except discord.Forbidden:
            await ctx.send('❌ I do not have permission to timeout this user')

    # -- ERROR HANDLERS --

    @addrole.error
    async def addrole_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Usage: {ctx.command.usage}')
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f'Usage: {ctx.command.usage}')
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send('❌ You do not have permission to use this command')

    @removerole.error
    async def removerole_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Usage: {ctx.command.usage}')
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f'Usage: {ctx.command.usage}')
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send('❌ You do not have permission to use this command')

    @deleterole.error
    async def deleterole_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Usage: {ctx.command.usage}')
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f'Usage: {ctx.command.usage}')
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send('❌ You do not have permission to use this command')

    @say.error
    async def say_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Usage: {ctx.command.usage}')

    @clear.error
    async def clear_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Usage: {ctx.command.usage}')
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f'Usage: {ctx.command.usage}')
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send('❌ You do not have permission to use this command')

def setup(bot):
    bot.add_cog(Utils(bot))