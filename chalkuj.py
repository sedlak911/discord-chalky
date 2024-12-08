import json
import os
import re

from dotenv import load_dotenv
import discord
from discord.ext import commands
from openai import OpenAI, RateLimitError

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
PROMPT = (
    "Hoď mi rating pls. Nezapomen dat hodnoceni do zavorek kvuli regexu (x/10). Ostatni udaje nikoliv."
)
SYSTEM_ROLE = (
    "Mluvis jako gen z, hodne anglickej slov. Mel bys byt jako trochu jako Gordon Ramsay."
    "Uzivatele oslovujes jako Petty. Napr. Tyvole Petty notak nebo Hochu, Petty to nemyslis vazne... vymyslej si variace."
    "Jsi ofenzivni drsnak, ale dokazes ocenit kvalitni chalku. "
    "Jidlu rikas chalka, chalec. "
    "Obcas pouzijes reverzní osmóza jako pojmenovani bud neceho negativniho nebo jako univerzalni pojmenovani. "
    "Hlavni hodnoceni je zdravi jidla: 1-10, pis to jako napr (X/10) abych regexem mohl vytahovat hodnoceni. 10 je nejlepsi."
    "Taky reknes kolik ma dane jidlo kalorii, bilkovin, tuku a cukru. "
    "Nezapominas pouzivat spravne gen-z vyrazy a at jsou tve odpovedi poradne ofenzivne funny pls. "
    "Hodne si delas srandu ze situaci na fotkach, pripadne z lidi, pokud tam jsou, hlavne narazky na vzhled. "
)

client = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Cesta k souboru pro uložení hodnocení
RATINGS_FILE = "user_ratings.json"

# Funkce pro načítání hodnocení z JSON souboru
def load_ratings():
    if os.path.exists(RATINGS_FILE):
        with open(RATINGS_FILE, "r") as f:
            return json.load(f)
    return {}

# Funkce pro uložení hodnocení do JSON souboru
def save_ratings():
    with open(RATINGS_FILE, "w") as f:
        json.dump(user_ratings, f)

# Načtení hodnocení při spuštění bota
user_ratings = load_ratings()


@bot.event
async def on_ready():
    print(f"Bot je ready chálkovat {bot.user}")

@bot.command(name="pls")
async def pls(ctx):
    message = (
        "**help**\n\n"
        "!chalka [popis chalky]\n"
        "!rating\n"
        "!billing"
    )
    await ctx.send(message)

@bot.command(name="rating")
async def rating(ctx):
    # Zobrazení průběžného hodnocení všech uživatelů
    message = "**Průběžné hodnocení:**\n"
    for user_id, ratings in user_ratings.items():
        user_avg = sum(ratings) / len(ratings)
        user = bot.get_user(int(user_id))
        message += f"{user.name if user else user_id}: {user_avg:.2f}\n"

    await ctx.send(message)


@bot.command(name="billing")
async def billing(ctx):
    # Vypis toho kdo mi dluzi penize
    message = "**Tolik penez me stojite zmrdi:**\n"
    sum = 0
    for user_id, ratings in user_ratings.items():
        user_cost = len(ratings) * 0.005
        user = bot.get_user(int(user_id))
        message += f"{user.name if user else user_id}: {user_cost:.2f} USD\n"
        sum += user_cost

    await ctx.send(f"{message}\n**Celkem: {sum:.2f} USD**")


@bot.command(name="chalka")
async def chalka(ctx, *, description: str = None):
    user_id = str(ctx.author.id)
    user_name = bot.get_user(int(user_id))

    if not ctx.message.attachments:
        await ctx.send("Neposlals obrázek zmrde.")
        return

    attachment = ctx.message.attachments[0]
    if not any(attachment.filename.lower().endswith(ext) for ext in ["png", "jpg", "jpeg"]):
        await ctx.send("Podporovány jsou pouze formáty PNG, JPG nebo JPEG.")
        return

    food_description = f"Popis jídla: {description}\n" if description else ""

    print(f"Nova chalka! Od: {user_name}")
    print(f"{attachment.url}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # gpt-4o, gpt-4o-mini
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_ROLE,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Popis chalky: {food_description} {PROMPT}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": attachment.url,
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )

        description_result = response.choices[0].message.content

        rating_match = re.search(r"\((\d+)/10\)", description_result)

        if rating_match:
            # Extrahujeme hodnocení z textu
            rating = float(rating_match.group(1))

            # Uložení hodnocení pro uživatele
            if user_id not in user_ratings:
                user_ratings[user_id] = []

            user_ratings[user_id].append(rating)

            # Výpočet průměrného hodnocení
            avg_rating = sum(user_ratings[user_id]) / len(user_ratings[user_id])

            save_ratings()

            message = (
                f"{ctx.author.mention}\n\n"
                f"**Chalkybot hodnoceni:**\n"
                f"{description_result}\n\n"
                f"**Found rating:** {rating}\n"
                f"**Avg rating:** {avg_rating:.2f}"
            )
        else:
            message = f"**Nenaslo to rating.** Chalkabot hodnoceni:\n\n{description_result}"

        print(f"{message}")
        await ctx.send(message)

    except RateLimitError:
        await ctx.send(f"**Pice, ujebali ste mi limit chatgpt.**")
    except Exception as e:
        await ctx.send(f"**Neco se posralo:**\n\n{e}")

bot.run(DISCORD_TOKEN)
