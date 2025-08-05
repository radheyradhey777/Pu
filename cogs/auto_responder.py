import discord
from discord.ext import commands
import random
import time
import re # Regular Expressions ke liye

class AutoResponderPro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}
        
        # --- KNOWLEDGE BASE (BOT KA GYAAN-KOSH) ---
        # Yahan hum saari jaankari structured format mein rakhenge.
        # Isse bot ke liye jaankari dhundhna aur compare karna aasan hoga.
        self.knowledge_base = {
            # Minecraft Plans
            "dirt": {"name": "Dirt Plan", "type": "minecraft", "price": 100, "ram": 2, "cpu": 100, "storage": 5, "keywords": ["dirt", "100rs", "2gb"]},
            "grass": {"name": "Grass Plan", "type": "minecraft", "price": 150, "ram": 4, "cpu": 150, "storage": 8, "keywords": ["grass", "150rs", "4gb"]},
            "stone": {"name": "Stone Plan", "type": "minecraft", "price": 270, "ram": 6, "cpu": 200, "storage": 15, "keywords": ["stone", "270rs", "6gb"]},
            "coal": {"name": "Coal Plan", "type": "minecraft", "price": 350, "ram": 8, "cpu": 220, "storage": 20, "keywords": ["coal", "350rs", "8gb"]},
            "iron": {"name": "Iron Plan", "type": "minecraft", "price": 540, "ram": 12, "cpu": 300, "storage": 30, "keywords": ["iron", "540rs", "12gb"]},
            "gold": {"name": "Gold Plan", "type": "minecraft", "price": 700, "ram": 16, "cpu": 350, "storage": 40, "keywords": ["gold", "700rs", "16gb"]},
            
            # VPS Plans
            "vps_micro": {"name": "VPS Micro", "type": "vps", "price": 300, "ram": 2, "cores": 1, "storage": 15, "keywords": ["micro", "300rs", "2gb"]},
            "vps_lite": {"name": "VPS Lite", "type": "vps", "price": 450, "ram": 6, "cores": 1, "storage": 20, "keywords": ["lite", "450rs", "6gb"]},
            "vps_start": {"name": "VPS Start", "type": "vps", "price": 600, "ram": 8, "cores": 2, "storage": 25, "keywords": ["start", "600rs", "8gb"]},
            "vps_boost": {"name": "VPS Boost", "type": "vps", "price": 800, "ram": 12, "cores": 3, "storage": 40, "keywords": ["boost", "800rs", "12gb"]},
        }

        # --- KEYWORD MAP (USER KE IRADE SAMAJHNE KE LIYE) ---
        self.keyword_map = {
            "greeting": ["hello", "hi", "hey", "namaste", "salam"],
            "all_minecraft_plans": ["all minecraft", "sare minecraft", "mc plans"],
            "all_vps_plans": ["all vps", "sare vps", "vps plans"],
            "price_inquiry": ["price", "cost", "plan", "rate", "cheap", "sasta", "kitne ka", "budget"],
            "recommendation": ["recommend", "suggest", "best", "acha", "kon sa lu"],
            "support": ["support", "help", "ticket", "problem", "issue"],
        }
        
        # Static replies for general queries
        self.static_replies = {
            "support": "Agar aapko koi bhi technical issue aa raha hai, to कृपया hamari website par jaakar support ticket banayein. Hamari team aapki jald se jald madad karegi: http://coramtix.in/support",
            "greeting": f"Hello! Main CoRamTix ka AI Assistant hoon. Main aapko hamare plans dhundne mein madad kar sakta hoon. Jaise, aap pooch sakte hain '12GB RAM wala minecraft plan' ya '500rs tak ka vps'.",
        }

    def format_minecraft_plan(self, plan_data):
        """Minecraft plan ko format karke Embed banata hai."""
        embed = discord.Embed(
            title=f"💻 {plan_data['name']} - Minecraft Hosting",
            description=f"Ek shandaar plan aapke Minecraft server ke liye.",
            color=discord.Color.green()
        )
        embed.add_field(name="Price", value=f"**₹{plan_data['price']}/month**", inline=True)
        embed.add_field(name="RAM", value=f"{plan_data['ram']} GB", inline=True)
        embed.add_field(name="CPU", value=f"{plan_data['cpu']}%", inline=True)
        embed.add_field(name="Storage", value=f"{plan_data['storage']} GB NVMe", inline=True)
        embed.set_footer(text="Order karne ke liye CoRamTix.in par visit karein.")
        return embed

    def format_vps_plan(self, plan_data):
        """VPS plan ko format karke Embed banata hai."""
        embed = discord.Embed(
            title=f"🚀 {plan_data['name']} - VPS Hosting",
            description=f"Aapke applications aur bots ke liye powerful performance.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Price", value=f"**₹{plan_data['price']}/month**", inline=True)
        embed.add_field(name="RAM", value=f"{plan_data['ram']} GB", inline=True)
        embed.add_field(name="CPU Cores", value=f"{plan_data['cores']}", inline=True)
        embed.add_field(name="Storage", value=f"{plan_data['storage']} GB NVMe", inline=True)
        embed.set_footer(text="Order karne ke liye CoRamTix.in par visit karein.")
        return embed

    def parse_query(self, content):
        """User ke message ko parse karke details nikalta hai."""
        parsed = {"type": None, "ram": None, "price": None, "text": content}
        
        if "minecraft" in content or "mc" in content:
            parsed["type"] = "minecraft"
        elif "vps" in content:
            parsed["type"] = "vps"

        # RAM nikalna (e.g., "8gb", "8 gb ram")
        ram_match = re.search(r'(\d+)\s*gb', content)
        if ram_match:
            parsed["ram"] = int(ram_match.group(1))

        # Price/Budget nikalna (e.g., "500rs", "under 500", "500 tak")
        price_match = re.search(r'(\d+)', content)
        if price_match and ("rs" in content or "under" in content or "budget" in content or "tak" in content):
             parsed["price"] = int(price_match.group(1))
        
        return parsed

    # --- CORE AI LISTENER (QUERY ENGINE) ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.content.startswith(self.bot.command_prefix):
            return

        channel_id = message.channel.id
        now = time.time()
        if channel_id in self.cooldowns and self.cooldowns[channel_id] > now:
            return

        content = message.content.lower().strip()
        if len(content) < 4:
            return

        # --- Query Processing Start ---
        
        # 1. Static replies check (Support, Greeting etc.)
        for intent, keywords in self.keyword_map.items():
            if intent in self.static_replies:
                for keyword in keywords:
                    if keyword in content:
                        await message.channel.send(self.static_replies[intent])
                        self.cooldowns[channel_id] = now + 10
                        return
        
        # 2. Parse the user's query for details
        query = self.parse_query(content)
        
        # 3. Find matching plans from Knowledge Base
        found_plans = []
        for plan_id, plan_data in self.knowledge_base.items():
            match = True
            # Type check (minecraft/vps)
            if query["type"] and query["type"] != plan_data["type"]:
                match = False
            # RAM check
            if query["ram"] and query["ram"] != plan_data["ram"]:
                match = False
            # Price/Budget check
            if query["price"] and plan_data["price"] > query["price"]:
                match = False
            
            # Specific plan name check (e.g., "gold plan")
            for keyword in plan_data["keywords"]:
                 if keyword in content and len(keyword) > 2: # short keywords ignore karein
                      # Agar specific plan name mil gaya, to baki filters ko bypass karke usi ko select karein
                      found_plans = [plan_data]
                      break
            if found_plans: break
            
            if match:
                found_plans.append(plan_data)
        
        # 4. Send the results
        if found_plans:
            # Price ke hisab se sort karein
            found_plans.sort(key=lambda x: x['price'])
            
            response_count = 0
            await message.channel.send(f"✅ Mujhe aapke liye {len(found_plans)} plan(s) miley hain:")
            for plan in found_plans:
                if response_count >= 3: # Ek baar mein max 3 results bhejein
                    await message.channel.send("Aur bhi results hain, कृपया अपनी खोज को और सटीक करें।")
                    break
                
                if plan['type'] == 'minecraft':
                    embed = self.format_minecraft_plan(plan)
                    await message.channel.send(embed=embed)
                elif plan['type'] == 'vps':
                    embed = self.format_vps_plan(plan)
                    await message.channel.send(embed=embed)
                
                response_count += 1
                
            self.cooldowns[channel_id] = now + 10
        # --- Query Processing End ---

async def setup(bot):
    await bot.add_cog(AutoResponderPro(bot))

