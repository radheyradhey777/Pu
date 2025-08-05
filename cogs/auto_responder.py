import discord
from discord.ext import commands
import time
import re  # Regular Expressions for advanced text matching

class AutoResponderPro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}
        
        # --- KNOWLEDGE BASE (BOT KA GYAAN-KOSH) ---
        # Structured data for all hosting plans. More keywords help in direct matching.
        self.knowledge_base = {
            # Minecraft Plans
            "dirt": {"name": "Dirt Plan", "type": "minecraft", "price": 100, "ram": 2, "cpu": 100, "storage": 5, "keywords": ["dirt", "dirt plan", "100rs", "2gb"]},
            "grass": {"name": "Grass Plan", "type": "minecraft", "price": 150, "ram": 4, "cpu": 150, "storage": 8, "keywords": ["grass", "grass plan", "150rs", "4gb"]},
            "stone": {"name": "Stone Plan", "type": "minecraft", "price": 270, "ram": 6, "cpu": 200, "storage": 15, "keywords": ["stone", "stone plan", "270rs", "6gb"]},
            "coal": {"name": "Coal Plan", "type": "minecraft", "price": 350, "ram": 8, "cpu": 220, "storage": 20, "keywords": ["coal", "coal plan", "350rs", "8gb"]},
            "iron": {"name": "Iron Plan", "type": "minecraft", "price": 540, "ram": 12, "cpu": 300, "storage": 30, "keywords": ["iron", "iron plan", "540rs", "12gb"]},
            "gold": {"name": "Gold Plan", "type": "minecraft", "price": 700, "ram": 16, "cpu": 350, "storage": 40, "keywords": ["gold", "gold plan", "700rs", "16gb"]},
            
            # VPS Plans
            "vps_micro": {"name": "VPS Micro", "type": "vps", "price": 300, "ram": 2, "cores": 1, "storage": 15, "keywords": ["micro", "vps micro", "300rs", "2gb"]},
            "vps_lite": {"name": "VPS Lite", "type": "vps", "price": 450, "ram": 6, "cores": 1, "storage": 20, "keywords": ["lite", "vps lite", "450rs", "6gb"]},
            "vps_start": {"name": "VPS Start", "type": "vps", "price": 600, "ram": 8, "cores": 2, "storage": 25, "keywords": ["start", "vps start", "600rs", "8gb"]},
            "vps_boost": {"name": "VPS Boost", "type": "vps", "price": 800, "ram": 12, "cores": 3, "storage": 40, "keywords": ["boost", "vps boost", "800rs", "12gb"]},
        }

        # --- KEYWORD MAP (USER KE IRADE SAMAJHNE KE LIYE) ---
        # Expanded to understand more intents.
        self.keyword_map = {
            "greeting": ["hello", "hi", "hey", "namaste", "salam", "yo"],
            "all_minecraft_plans": ["all minecraft", "sare minecraft", "mc plans"],
            "all_vps_plans": ["all vps", "sare vps", "vps plans"],
            "price_inquiry": ["price", "cost", "plan", "rate", "cheap", "sasta", "kitne ka", "budget"],
            "recommendation": ["recommend", "suggest", "best", "acha", "kon sa lu"],
            "comparison": ["compare", "vs", "versus", "or"],
            "support": ["support", "help", "ticket", "problem", "issue", "error"],
            "thank_you": ["thanks", "thank you", "shukriya", "dhanyawad", "ty"],
            "info": ["what is", "kya hai", "matlab", "explain"],
        }
        
        # --- STATIC & DYNAMIC REPLIES ---
        self.static_replies = {
            "support": "Agar aapko koi bhi technical issue aa raha hai, to kripya hamari website par jaakar support ticket banayein. Hamari team aapki jald se jald madad karegi: https://coramtix.in/submitticket.php",
            "greeting": f"Hello! Main CoRamTix ka AI Assistant hoon. Main aapko hamare plans dhundne mein madad kar sakta hoon. Aap pooch sakte hain '12GB RAM wala minecraft plan' ya '500rs tak ka vps'. Visit us at https://coramtix.in/",
            "thank_you": "You're welcome! 😊 Agar aapko aur koi jaankari chahiye to poochne mein संकोच na karein.",
            "info_vps": "VPS (Virtual Private Server) ek powerful hosting hai jo aapko dedicated resources (RAM, CPU) deti hai. Yeh applications, websites, aur non-Minecraft game servers ke liye perfect hai. Adhik jaankari ke liye visit karein: https://coramtix.in/vps-hosting",
            "info_minecraft": "Minecraft Hosting ek special service hai jo Minecraft servers ke liye optimized hai. Isse aap aasani se apne server ko manage kar sakte hain. Adhik jaankari ke liye visit karein: https://coramtix.in/minecraft-hosting",
            "fallback": "Maaf kijiye, main aapki baat samajh nahi paya. 😕\nAap is tarah se pooch sakte hain:\n- `8GB RAM wala minecraft plan`\n- `500rs tak ka vps`\n- `sare minecraft plans`\n- `compare iron vs gold plan`"
        }

    def format_plan_embed(self, plan_data):
        """Generic function to format an embed for any plan type."""
        if plan_data['type'] == 'minecraft':
            embed = discord.Embed(
                title=f"💻 {plan_data['name']} - Minecraft Hosting",
                description=f"Ek shandaar plan aapke Minecraft server ke liye.",
                color=discord.Color.green(),
                url="https://coramtix.in/minecraft-hosting" # Direct link to the product page
            )
            embed.add_field(name="Price", value=f"**₹{plan_data['price']}/month**", inline=True)
            embed.add_field(name="RAM", value=f"{plan_data['ram']} GB", inline=True)
            embed.add_field(name="CPU", value=f"{plan_data['cpu']}%", inline=True)
            embed.add_field(name="Storage", value=f"{plan_data['storage']} GB NVMe", inline=True)

        elif plan_data['type'] == 'vps':
            embed = discord.Embed(
                title=f"🚀 {plan_data['name']} - VPS Hosting",
                description=f"Aapke applications aur bots ke liye powerful performance.",
                color=discord.Color.blue(),
                url="https://coramtix.in/vps-hosting" # Direct link to the product page
            )
            embed.add_field(name="Price", value=f"**₹{plan_data['price']}/month**", inline=True)
            embed.add_field(name="RAM", value=f"{plan_data['ram']} GB", inline=True)
            embed.add_field(name="CPU Cores", value=f"{plan_data['cores']}", inline=True)
            embed.add_field(name="Storage", value=f"{plan_data['storage']} GB NVMe", inline=True)
        
        embed.set_footer(text="Order karne ke liye CoRamTix.in par visit karein.")
        return embed

    def parse_query(self, content):
        """User ke message ko parse karke details nikalta hai. (Improved Logic)"""
        parsed = {"type": None, "ram": None, "price": None, "text": content}
        
        content = content.lower()
        if "minecraft" in content or "mc" in content:
            parsed["type"] = "minecraft"
        elif "vps" in content:
            parsed["type"] = "vps"

        # RAM nikalna (e.g., "8gb", "8 gb ram")
        ram_match = re.search(r'(\d+)\s*gb', content)
        if ram_match:
            parsed["ram"] = int(ram_match.group(1))

        # Price/Budget nikalna (e.g., "500rs", "under 500", "500 tak", "in 500 budget")
        # This regex is more specific to avoid matching random numbers.
        price_match = re.search(r'(?:under|below|budget|max|upto|tak|less than|<)?\s*(\d{2,})\s*(?:rs|₹|inr)', content)
        if price_match:
             parsed["price"] = int(price_match.group(1))
        
        return parsed

    async def send_plan_results(self, message, plans):
        """Found plans ko format karke bhejta hai."""
        if not plans:
            return

        # Price ke hisab se sort karein
        plans.sort(key=lambda x: x['price'])
        
        await message.channel.send(f"✅ Mujhe aapke liye {len(plans)} plan(s) miley hain:")
        
        response_count = 0
        for plan in plans:
            if response_count >= 3: # Ek baar mein max 3 results bhejein
                await message.channel.send("Aur bhi results hain. Behtar result ke liye, apni zaroorat saaf-saaf likhein (jaise, '8gb ram wala vps').")
                break
            
            embed = self.format_plan_embed(plan)
            await message.channel.send(embed=embed)
            response_count += 1

    # --- CORE AI LISTENER (QUERY ENGINE) ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or (message.guild and message.content.startswith(self.bot.command_prefix)):
            return

        channel_id = message.channel.id
        now = time.time()
        cooldown_time = 10 # seconds

        # Cooldown check
        if channel_id in self.cooldowns and self.cooldowns[channel_id] > now:
            return

        content = message.content.lower().strip()
        if len(content) < 3:
            return

        # --- Intent Processing Pipeline ---
        
        # 1. Check for simple, high-priority intents (greetings, thanks, support)
        for intent, keywords in self.keyword_map.items():
            if intent in self.static_replies:
                if any(keyword in content for keyword in keywords):
                    await message.channel.send(self.static_replies[intent])
                    self.cooldowns[channel_id] = now + cooldown_time
                    return
        
        # 2. Check for informational queries ("what is vps?")
        if any(keyword in content for keyword in self.keyword_map["info"]):
            if "vps" in content:
                await message.channel.send(self.static_replies["info_vps"])
                self.cooldowns[channel_id] = now + cooldown_time
                return
            if "minecraft" in content:
                await message.channel.send(self.static_replies["info_minecraft"])
                self.cooldowns[channel_id] = now + cooldown_time
                return
        
        # 3. Check for comparison queries ("compare iron vs gold")
        if any(keyword in content for keyword in self.keyword_map["comparison"]):
            plans_to_compare = []
            for plan_id, plan_data in self.knowledge_base.items():
                # Find plan names/keywords in the message
                if any(kw in content for kw in plan_data["keywords"] if len(kw) > 2):
                    plans_to_compare.append(plan_data)
            
            if len(plans_to_compare) >= 2:
                await self.send_plan_results(message, plans_to_compare[:2]) # Compare first two found
                self.cooldowns[channel_id] = now + cooldown_time
                return

        # 4. Check for 'all plans' queries
        if any(keyword in content for keyword in self.keyword_map["all_minecraft_plans"]):
            all_mc_plans = [p for p in self.knowledge_base.values() if p['type'] == 'minecraft']
            await self.send_plan_results(message, all_mc_plans)
            self.cooldowns[channel_id] = now + cooldown_time
            return
        
        if any(keyword in content for keyword in self.keyword_map["all_vps_plans"]):
            all_vps_plans = [p for p in self.knowledge_base.values() if p['type'] == 'vps']
            await self.send_plan_results(message, all_vps_plans)
            self.cooldowns[channel_id] = now + cooldown_time
            return

        # 5. Core query parsing for specific plans
        query = self.parse_query(content)
        
        # If no specific features are mentioned, don't proceed unless a plan name is mentioned
        if not query["type"] and not query["ram"] and not query["price"]:
             # Check for specific plan name one last time
             for plan_id, plan_data in self.knowledge_base.items():
                 if any(kw in content for kw in plan_data["keywords"] if len(kw) > 3):
                     await self.send_plan_results(message, [plan_data])
                     self.cooldowns[channel_id] = now + cooldown_time
                     return
             # If nothing found, do nothing. To avoid spamming on random messages.
             return

        # Find matching plans from Knowledge Base
        found_plans = []
        for plan_id, plan_data in self.knowledge_base.items():
            # If a specific plan name is mentioned, show only that plan
            if any(kw in content for kw in plan_data["keywords"] if len(kw) > 3):
                found_plans = [plan_data]
                break

            # General filtering based on parsed query
            match = True
            if query["type"] and query["type"] != plan_data["type"]: match = False
            if query["ram"] and query["ram"] != plan_data["ram"]: match = False
            if query["price"] and plan_data["price"] > query["price"]: match = False
            
            if match:
                found_plans.append(plan_data)
        
        # 6. Send results or fallback message
        if found_plans:
            await self.send_plan_results(message, found_plans)
            self.cooldowns[channel_id] = now + cooldown_time
        else:
            # Send fallback only if the query seemed intentional (had keywords)
            if query["type"] or query["ram"] or query["price"]:
                await message.channel.send(self.static_replies["fallback"])
                self.cooldowns[channel_id] = now + cooldown_time
        
async def setup(bot):
    await bot.add_cog(AutoResponderPro(bot))

