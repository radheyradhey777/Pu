import discord
from discord.ext import commands
import time
import aiofiles
import json
import re
from fuzzywuzzy import process
from discord.ui import Button, View

KNOWLEDGE_FILE = "knowledge_base.json"

def load_knowledge_base():
    try:
        with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # Empty if starting fresh

def save_knowledge_base(kb):
    with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)

class PlanPaginator(View):
    def __init__(self, plans, send_embed_fn, user):
        super().__init__(timeout=120)
        self.plans = plans
        self.send_embed_fn = send_embed_fn
        self.index = 0
        self.user = user

    async def update_message(self, interaction):
        embed = self.send_embed_fn(self.plans[self.index])
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Only you can control pagination.", ephemeral=True)
            return
        if self.index > 0:
            self.index -= 1
            await self.update_message(interaction)
    
    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Only you can control pagination.", ephemeral=True)
            return
        if self.index < len(self.plans)-1:
            self.index += 1
            await self.update_message(interaction)

class AutoResponderPro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

        # --- KNOWLEDGE BASE ---
        self.knowledge_base = load_knowledge_base()

        # --- KEYWORD MAP (ENGLISH + HINDI) ---
        self.keyword_map = {
            "greeting": ["hello", "hi", "hey", "namaste", "salam", "yo"],
            "all_minecraft_plans": ["all minecraft", "sare minecraft", "mc plans", "सभी minecraft"],
            "all_vps_plans": ["all vps", "sare vps", "vps plans", "सभी vps"],
            "price_inquiry": ["price", "cost", "plan", "rate", "cheap", "सस्ता", "कितने का", "budget"],
            "recommendation": ["recommend", "suggest", "best", "अच्छा", "कौन सा लूं"],
            "comparison": ["compare", "vs", "versus", "or", "मुकाबला", "बनाम"],
            "support": ["support", "help", "ticket", "problem", "issue", "error", "समस्या"],
            "thank_you": ["thanks", "thank you", "शुक्रिया", "धन्यवाद", "ty"],
            "info": ["what is", "क्या है", "मतलब", "explain"],
        }

        # --- STATIC REPLIES ---
        self.static_replies = {
            "support": "Agar aapko koi bhi technical issue aa raha hai, to kripya hamari website par jaakar support ticket banayein. Team madad karegi: https://coramtix.in/submitticket.php",
            "greeting": f"Hello! Main CoRamTix ka AI Assistant hoon. Aap pooch sakte hain '12GB RAM wala minecraft plan' ya '500rs tak ka vps'. Visit: https://coramtix.in/",
            "thank_you": "You're welcome! 😊 Agar aapko aur koi jaankari chahiye to poochiye.",
            "info_vps": "VPS (Virtual Private Server) ek powerful hosting hai. Detailed info: https://coramtix.in/vps-hosting",
            "info_minecraft": "Minecraft Hosting ek optimized service hai. Detailed info: https://coramtix.in/minecraft-hosting",
            "fallback": "Maaf kijiye, main aapki query nahi samajh paya. उदाहरण:
- `8GB RAM wala minecraft plan`
- `500rs tak ka vps`
- `सारे minecraft plans`
- `compare iron vs gold plan`"
        }

    # ------- Dynamic Knowledge Base Admin Commands (Owner Only) --------
    @commands.command(hidden=True)
    @commands.is_owner()
    async def add_plan(self, ctx, *, data):
        """Add plan: JSON object, owner-only"""
        try:
            plan = json.loads(data)
            plan_id = plan.get('id') or plan['name'].lower().replace(' ', '_')
            self.knowledge_base[plan_id] = plan
            save_knowledge_base(self.knowledge_base)
            await ctx.send(f"✅ Plan `{plan['name']}` added/updated.")
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def remove_plan(self, ctx, plan_id):
        try:
            removed = self.knowledge_base.pop(plan_id, None)
            save_knowledge_base(self.knowledge_base)
            await ctx.send(f"✅ Removed: {plan_id}" if removed else f"❌ Not found: {plan_id}")
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    # -------- Plan Formatting --------
    def format_plan_embed(self, plan):
        """Creates an embed for a plan"""
        desc = f"**Type**: {plan['type'].capitalize()}
" if 'type' in plan else ""
        embed = discord.Embed(
            title=plan.get('name', 'Plan'),
            description=desc + (plan.get('desc') or "No description."),
            color=discord.Color.green() if plan.get('type', '') == 'minecraft' else discord.Color.blue()
        )
        embed.add_field(name="Price", value=f"**₹{plan.get('price', '--')}/month**", inline=True)
        embed.add_field(name="RAM", value=f"{plan.get('ram', '--')} GB", inline=True)
        if plan.get('type') == 'vps':
            embed.add_field(name="CPU Cores", value=f"{plan.get('cores', '--')}", inline=True)
        else:
            embed.add_field(name="CPU", value=f"{plan.get('cpu', '--')}%", inline=True)
        embed.add_field(name="Storage", value=f"{plan.get('storage', '--')} GB NVMe", inline=True)
        embed.set_footer(text="Order: CoRamTix.in")
        return embed

    # -------- Fuzzy Plan Matcher --------
    def fuzzy_match_plan(self, user_input):
        plans = list(self.knowledge_base.values())
        if not plans:
            return []
        names = [p['name'].lower() for p in plans]
        match, score = process.extractOne(user_input, names)
        if score > 74:
            ix = names.index(match)
            return [plans[ix]]
        return []

    # --------- Parse Query for RAM, Price, Type ---------
    def parse_query(self, text):
        content = text.lower()
        q = {"type": None, "ram": None, "price": None, "raw": text}

        if "minecraft" in content or "mc" in content:
            q["type"] = "minecraft"
        elif "vps" in content:
            q["type"] = "vps"

        ram = re.search(r'(d{1,2})s*gb', content)
        if ram:
            q["ram"] = int(ram.group(1))
        price = re.search(r'(?:under|tak|upto|less than|below|budget|max|maximum|within)?s*(d{2,6})s*(?:rs|₹|inr)', content)
        if price:
            q["price"] = int(price.group(1))
        return q

    # --------- Filter plans by type/ram/price ---------
    def filter_plans(self, q):
        res = []
        for plan in self.knowledge_base.values():
            match = True
            if q["type"] and q["type"] != plan.get('type', ''): match = False
            if q["ram"] and int(q["ram"]) > int(plan.get('ram', 0)): match = False
            if q["price"] and int(plan.get('price', 0)) > int(q["price"]): match = False
            if match:
                res.append(plan)
        return res

    # -------------- Messaging Helpers ------------------
    async def send_plan_results(self, message, plans):
        """If >1, paginate."""
        plans = sorted(plans, key=lambda x: int(x.get('price', 99999)))
        if not plans:
            await message.channel.send(self.static_replies['fallback'])
            return
        if len(plans) == 1:
            embed = self.format_plan_embed(plans[0])
            await message.channel.send(embed=embed)
            return
        # Pagination with buttons
        embed = self.format_plan_embed(plans[0])
        paginator = PlanPaginator(plans, self.format_plan_embed, message.author)
        await message.channel.send(content=f"Total {len(plans)} plans found. Use Next/Prev ➡️⬅️:", embed=embed, view=paginator)
    
    # ------------- Core Listener --------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or (message.guild and message.content.startswith(self.bot.command_prefix)):
            return
        channel_id = message.channel.id
        now = time.time()
        cooldown_time = 10

        # Cooldown to avoid spam
        if channel_id in self.cooldowns and self.cooldowns[channel_id] > now:
            return

        content = message.content.lower()
        if len(content) < 3:
            return

        # --- High-priority static intents ---
        for intent, keywords in self.keyword_map.items():
            if intent in self.static_replies and any(k in content for k in keywords):
                await message.channel.send(self.static_replies[intent])
                self.cooldowns[channel_id] = now + cooldown_time
                return

        if any(k in content for k in self.keyword_map["info"]):
            if "vps" in content:
                await message.channel.send(self.static_replies['info_vps'])
                self.cooldowns[channel_id] = now + cooldown_time
                return
            if "minecraft" in content:
                await message.channel.send(self.static_replies['info_minecraft'])
                self.cooldowns[channel_id] = now + cooldown_time
                return

        # --- Comparison detection (two plan names in query) ---
        if any(k in content for k in self.keyword_map["comparison"]):
            found = []
            for plan in self.knowledge_base.values():
                if any(kw.lower() in content for kw in plan.get("keywords", [])):
                    found.append(plan)
            if len(found) >= 2:
                await self.send_plan_results(message, found[:2])
                self.cooldowns[channel_id] = now + cooldown_time
                return

        # --- All plans ---
        if any(k in content for k in self.keyword_map["all_minecraft_plans"]):
            mc_plans = [p for p in self.knowledge_base.values() if p.get('type', '') == 'minecraft']
            await self.send_plan_results(message, mc_plans)
            self.cooldowns[channel_id] = now + cooldown_time
            return
        if any(k in content for k in self.keyword_map["all_vps_plans"]):
            vps_plans = [p for p in self.knowledge_base.values() if p.get('type', '') == 'vps']
            await self.send_plan_results(message, vps_plans)
            self.cooldowns[channel_id] = now + cooldown_time
            return

        # --- Main query parsing & fuzzy matching ---
        query = self.parse_query(content)
        found = []

        # Try exact plan name match first
        for plan in self.knowledge_base.values():
            if any(len(kw) > 3 and kw.lower() in content for kw in plan.get("keywords", [])):
                found.append(plan)
        if found:
            await self.send_plan_results(message, found)
            self.cooldowns[channel_id] = now + cooldown_time
            return

        # Fuzzy matching
        if not found:
            found = self.fuzzy_match_plan(content)
            if found:
                await self.send_plan_results(message, found)
                self.cooldowns[channel_id] = now + cooldown_time
                return

        # Feature query filtering
        candidates = self.filter_plans(query)
        if candidates:
            await self.send_plan_results(message, candidates)
            self.cooldowns[channel_id] = now + cooldown_time
            return

        # Fallback (if any intent detected at all)
        if any(x is not None for x in [query["type"], query["ram"], query["price"]]):
            await message.channel.send(self.static_replies['fallback'])
            self.cooldowns[channel_id] = now + cooldown_time

async def setup(bot):
    await bot.add_cog(AutoResponderPro(bot))
