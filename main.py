import discord 
from discord.ext import commands
import os 
import json 

with open('config.json', 'r') as f:
    config = json.load(f)
    token = config['token']

bot = commands.Bot(command_prefix='+', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

def load_cogs(start_dir):
    """Recursively load cogs from the start directory"""
    try:
        for file in os.listdir(start_dir):
            if file.endswith('.py'):
                bot.load_extension(f'{start_dir}.{file[:-3]}')
            elif os.path.isdir(os.path.join(start_dir, file)):
                load_cogs(os.path.join(start_dir, file))
    except Exception as e:
        print(f'Error loading cogs: {e}')

if __name__ == '__main__':
    load_cogs('cogs')
    bot.run(token)