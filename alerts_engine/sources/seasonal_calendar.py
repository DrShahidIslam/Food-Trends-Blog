"""
Seasonal Calendar & Festivity Trend Engine for Pinterest & WordPress.
Calculates active festivity windows and seasonal search demand based on the 45-day Pinterest planning curve.
"""
from datetime import datetime

def get_active_seasonal_themes(target_date=None):
    """
    Determine active Pinterest seasonal themes based on the 45-60 day advance planning window.
    """
    if target_date is None:
        target_date = datetime.now()

    month = target_date.month
    day = target_date.day

    themes = []

    # SEPTEMBER
    if month == 9:
        themes.append({
            "name": "Cozy Fall Comfort",
            "tag": "fall_comfort",
            "priority": 1,
            "keywords": ["crockpot", "pumpkin", "apple cider", "butternut squash", "casserole", "soup", "chili", "cinnamon"],
            "mood": "Warm natural window light, rustic wooden surfaces, cinnamon dusting, steam rising, cozy autumn kitchen vibe",
            "hook_templates": [
                "THE ULTIMATE COZY FALL DINNER",
                "EASY ONE-POT AUTUMN MEAL",
                "MELT-IN-YOUR-MOUTH PUMPKIN PERFECTION",
                "MUST-TRY APPLE CIDER TREAT"
            ]
        })
        themes.append({
            "name": "Game Day & Tailgating",
            "tag": "game_day",
            "priority": 1,
            "keywords": ["buffalo dip", "sliders", "wings", "nachos", "pull apart bread", "finger food", "appetizer"],
            "mood": "Vibrant party spread, golden melted cheese pull, fresh green onion garnish, casual gathering style",
            "hook_templates": [
                "THE #1 GAME DAY CROWD PLEASER",
                "5-MINUTE PARTY APPETIZER",
                "IRRESISTIBLE CHEESY BITES",
                "BETTER THAN TAKEOUT WINGS"
            ]
        })
        if day >= 10:
            themes.append({
                "name": "Spooky Halloween Treats",
                "tag": "halloween",
                "priority": 2,
                "keywords": ["halloween", "spooky", "ghost", "mummy", "pumpkin cookies", "witch hat", "creepy party food"],
                "mood": "Festive, fun, spooky culinary presentation, dramatic side lighting, dark moody background with playful garnishes",
                "hook_templates": [
                    "THE CUTEST HALLOWEEN TREATS",
                    "EASY SPOOKY PARTY SNACK",
                    "VIRAL HALLOWEEN DESSERT",
                    "NO-FAIL SPOOKY HIT"
                ]
            })

    # OCTOBER
    elif month == 10:
        if day <= 31:
            themes.append({
                "name": "Peak Halloween & Spooky Season",
                "tag": "halloween",
                "priority": 1,
                "keywords": ["halloween treats", "spooky snacks", "halloween party", "mummy", "ghost cupcakes", "pumpkin dip"],
                "mood": "Moody dramatic lighting, playful Halloween food styling, rich chocolate, orange and black accents",
                "hook_templates": [
                    "THE #1 VIRAL HALLOWEEN HIT",
                    "SPOOKY & DELICIOUS PARTY FOOD",
                    "KIDS LOVE THESE HALLOWEEN BITES",
                    "EASY LAST-MINUTE HALLOWEEN TREAT"
                ]
            })
        themes.append({
            "name": "Hearty Autumn Comfort & Crockpot",
            "tag": "fall_comfort",
            "priority": 1,
            "keywords": ["slow cooker", "crockpot dump dinner", "pot roast", "butternut squash", "apple crisp", "pecan"],
            "mood": "Warm volumetric lighting, golden brown caramelized edges, cozy autumn comfort food styling",
            "hook_templates": [
                "YOUR NEW GO-TO FALL DINNER",
                "SET IT & FORGET IT CROCKPOT",
                "BETTER THAN GRANDMA'S RECIPE",
                "COZY WEEKEND BAKING"
            ]
        })
        if day >= 15:
            themes.append({
                "name": "Thanksgiving & Friendsgiving Prep",
                "tag": "thanksgiving",
                "priority": 1,
                "keywords": ["thanksgiving sides", "sweet potato casserole", "stuffing", "green bean casserole", "pecan pie", "cranberry"],
                "mood": "Holiday feast styling, golden butter glaze, fresh rosemary and sage, elegant Thanksgiving table",
                "hook_templates": [
                    "THE BEST THANKSGIVING SIDE DISH",
                    "MAKE-AHEAD HOLIDAY FAVORITE",
                    "EVERYONE WILL ASK FOR THIS RECIPE",
                    "EASY THANKSGIVING CROWD PLEASER"
                ]
            })

    # NOVEMBER
    elif month == 11:
        if day <= 28:
            themes.append({
                "name": "Thanksgiving Feast & Holiday Entertaining",
                "tag": "thanksgiving",
                "priority": 1,
                "keywords": ["thanksgiving sides", "stuffing", "cranberry brie", "turkey", "pecan pie", "sweet potato casserole", "dinner rolls"],
                "mood": "Opulent holiday dinner table, warm amber lighting, golden roasted skin, fresh holiday herb garnishes",
                "hook_templates": [
                    "THE ULTIMATE THANKSGIVING SHOWSTOPPER",
                    "MAKE-AHEAD THANKSGIVING PERFECTION",
                    "THE MOST REQUESTED HOLIDAY SIDE",
                    "MELT-IN-YOUR-MOUTH HOLIDAY BAKE"
                ]
            })
        if day >= 10:
            themes.append({
                "name": "Holiday & Christmas Baking",
                "tag": "christmas_baking",
                "priority": 1,
                "keywords": ["christmas cookies", "holiday baking", "gingerbread", "peppermint bark", "crinkle cookies", "cookie box"],
                "mood": "Festive Christmas table, powdered sugar snowfall, evergreen sprigs, red ribbon accents, warm festive glow",
                "hook_templates": [
                    "THE #1 CHRISTMAS COOKIE RECIPE",
                    "HOLIDAY COOKIE BOX FAVORITE",
                    "PURE CHRISTMAS NOSTALGIA",
                    "FESTIVE HOLIDAY INDULGENCE"
                ]
            })

    # DECEMBER
    elif month == 12:
        if day <= 25:
            themes.append({
                "name": "Christmas Baking & Holiday Entertaining",
                "tag": "christmas_baking",
                "priority": 1,
                "keywords": ["christmas cookies", "holiday dinner", "prime rib", "gingerbread", "holiday punch", "christmas breakfast"],
                "mood": "Magical festive Christmas lighting, powdered sugar dusting, warm spiced aromas, holiday centerpiece",
                "hook_templates": [
                    "THE ULTIMATE CHRISTMAS MORNING BAKE",
                    "HOLIDAY PARTY CROWD FAVORITE",
                    "MAGICAL CHRISTMAS DESSERT",
                    "FOOLPROOF HOLIDAY SHOWSTOPPER"
                ]
            })
        if day >= 15:
            themes.append({
                "name": "New Year's Eve Party Appetizers",
                "tag": "nye_party",
                "priority": 1,
                "keywords": ["nye appetizers", "party dip", "crostini", "brie bites", "finger foods", "champagne cocktail"],
                "mood": "Chic celebratory cocktail party styling, golden shimmer, elegant glassware, gourmet finger foods",
                "hook_templates": [
                    "THE BEST NYE PARTY APPETIZER",
                    "ELEGANT 10-MINUTE PARTY BITE",
                    "RING IN THE NEW YEAR WITH THIS",
                    "IRRESISTIBLE FINGER FOOD HIT"
                ]
            })

    # DEFAULT (Spring / Summer / General)
    else:
        themes.append({
            "name": "Viral Food Trends & Easy Meals",
            "tag": "general_viral",
            "priority": 1,
            "keywords": ["easy dinner", "viral recipe", "quick dessert", "sheet pan", "air fryer"],
            "mood": "Bright natural editorial lighting, fresh vibrant garnishes, modern kitchen aesthetic",
            "hook_templates": [
                "READY IN JUST 20 MINUTES",
                "THE VIRAL RECIPE EVERYONE LOVES",
                "PERFECT FOR BUSY WEEKNIGHTS",
                "SIMPLE STEP-BY-STEP RECIPE"
            ]
        })

    return themes


def get_seasonal_pin_context(topic=""):
    """
    Get a formatted prompt snippet to guide Gemini when generating pin hooks, titles, and images.
    Matches active theme according to topic keywords when available.
    """
    themes = get_active_seasonal_themes()
    if not themes:
        return ""
    
    primary = themes[0]
    t_lower = (topic or "").lower()
    for theme in themes:
        if any(kw in t_lower for kw in theme.get("keywords", [])):
            primary = theme
            break

    hooks_str = ", ".join(f"'{h}'" for h in primary.get("hook_templates", []))
    keywords_str = ", ".join(primary.get("keywords", []))

    return f"""
    CURRENT SEASONAL TREND CONTEXT:
    - Active Season / Festivity: {primary['name']} ({primary['tag']})
    - Key Search Concepts: {keywords_str}
    - Visual Photography Mood: {primary['mood']}
    - High-CTR Seasonal Hook Angles (use as inspiration, DO NOT copy verbatim on every pin): {hooks_str}
    *RULE: If the recipe matches fall, comfort, holiday, or game day themes, prioritize seasonal urgency and sensory cravings, but customize specifically to this dish!*
    """


def get_curated_seasonal_queue():
    """
    A curated roster of high-search volume, viral Pinterest recipe topics tailored specifically
    for the current September/Fall Q4 surge.
    """
    return [
        # Fall Comfort & Crockpot (High Search Volume Now)
        {"topic": "Slow Cooker Creamy Chicken and Wild Rice Soup", "intent": "recipe", "category": "Fall Comfort"},
        {"topic": "One-Pot Creamy Butternut Squash Sausage Gnocchi", "intent": "recipe", "category": "Fall Comfort"},
        {"topic": "Crockpot Melt-in-Your-Mouth Mississippi Pot Roast", "intent": "recipe", "category": "Fall Comfort"},
        {"topic": "Cozy Brown Butter Apple Cider Donuts with Cinnamon Sugar", "intent": "recipe", "category": "Fall Baking"},
        {"topic": "Soft Swirled Pumpkin Cream Cheese Loaf with Spiced Glaze", "intent": "recipe", "category": "Fall Baking"},
        {"topic": "Crispy Skillet Apple Crisp with Salted Caramel Drizzle", "intent": "recipe", "category": "Fall Baking"},
        {"topic": "Creamy Tuscan White Bean and Sausage Soup", "intent": "recipe", "category": "Fall Comfort"},
        {"topic": "One-Pan Maple Dijon Roasted Chicken Thighs and Sweet Potatoes", "intent": "recipe", "category": "Fall Comfort"},
        {"topic": "Fudgy Pumpkin Spice Swirl Brownies", "intent": "recipe", "category": "Fall Baking"},
        {"topic": "Slow Cooker Cheesy Crack Chicken Tater Tot Casserole", "intent": "recipe", "category": "Fall Comfort"},

        # Game Day / Football Tailgating (Surging Weekends)
        {"topic": "Slow Cooker Buffalo Chicken Dip with Crispy Tortilla Chips", "intent": "recipe", "category": "Game Day"},
        {"topic": "Cheesy Hot Roast Beef and Cheddar Hawaiian Roll Sliders", "intent": "recipe", "category": "Game Day"},
        {"topic": "Crispy Air Fryer Garlic Parmesan Wings with Ranch Dip", "intent": "recipe", "category": "Game Day"},
        {"topic": "Baked Jalapeño Popper Dip with Bacon Breadcrumb Crust", "intent": "recipe", "category": "Game Day"},
        {"topic": "Sheet Pan Loaded Cheesy Taco Nachos with Fresh Guacamole", "intent": "recipe", "category": "Game Day"},
        {"topic": "Cheesy Garlic Herb Pull-Apart Sourdough Bread", "intent": "recipe", "category": "Game Day"},
        {"topic": "Sweet and Spicy Slow Cooker BBQ Meatballs", "intent": "recipe", "category": "Game Day"},

        # Halloween & Spooky Season (45-Day Advance Surge)
        {"topic": "Spooky Ghost Meringue Cupcakes with Rich Chocolate Base", "intent": "recipe", "category": "Halloween"},
        {"topic": "Crescent Roll Mummy Jalapeño Poppers with Cream Cheese", "intent": "recipe", "category": "Halloween"},
        {"topic": "Fudgy Halloween Graveyard Brownies with Cookie Tombstones", "intent": "recipe", "category": "Halloween"},
        {"topic": "Chewy Monster Eyeball Chocolate Chip Cookies", "intent": "recipe", "category": "Halloween"},
        {"topic": "Warm Spooky Apple Cider Witch's Brew Mocktail", "intent": "recipe", "category": "Halloween"},
        {"topic": "Creamy Spooky Pumpkin Cheesecake Dip with Ginger Snaps", "intent": "recipe", "category": "Halloween"},

        # Early Thanksgiving / Friendsgiving (Planning Peak)
        {"topic": "Brown Sugar Pecan Crunch Sweet Potato Casserole", "intent": "recipe", "category": "Thanksgiving"},
        {"topic": "Classic Herb Sausage and Sourdough Stuffing from Scratch", "intent": "recipe", "category": "Thanksgiving"},
        {"topic": "Creamy Cheddar Green Bean Casserole with Crispy Fried Onions", "intent": "recipe", "category": "Thanksgiving"},
        {"topic": "Warm Baked Cranberry Pecan Brie Bites with Flaky Pastry", "intent": "recipe", "category": "Thanksgiving"},
        {"topic": "Mile-High Classic Southern Pecan Pie with Flaky Butter Crust", "intent": "recipe", "category": "Thanksgiving"},
    ]
