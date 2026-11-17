"""Further everyday topics for advice_library.py: minor ailments, computers and phones, long flights, small business, and
the holiday care of houseplants. Same format; replies are general and say when to see a professional."""
from .advice_library import topic

# ------------------------------------------------------------------------------------------------------------ minor ailments
topic('ailment', r'sunburn(?:t|ed)?|burnt|bright red|red skin|peeling|insect bites?|mosquito bites?|bitten|stung|bee sting|blisters?|sore throat|'
      r'hay ?fever|sneez(?:e|ing)|back pain|my back hurts|upset stomach|food poisoning|tummy|nausea|hangover|cramp')(
    (r'sunburn|burnt|bright red|red skin|stings?|peeling|make it hurt less|soothe',
     "For mild sunburn:\n\n- Cool the skin with a cool (not icy) shower or damp cloths for 10 to 15 minutes, a few times a day.\n"
     "- Apply aloe vera or an unperfumed moisturiser while the skin is still a little damp.\n- Drink extra water, and take ibuprofen or paracetamol "
     "for the pain if that's suitable for you.\n- Wear loose, soft clothing and keep it out of the sun until it has healed; don't pop any blisters.\n\n"
     "See a doctor or pharmacist if it blisters badly over a large area, or you feel feverish, dizzy or sick."),
    (r'insect|mosquito|bitten|bite|bee sting|stung',
     "Wash the area with soap and water, hold something cold on it for 10 minutes, and try not to scratch. An antihistamine tablet or cream can help "
     "the itching. For a bee sting, scrape the sting out sideways with a fingernail or card first. Get urgent help for any swelling of the face or "
     "throat, or difficulty breathing."),
    (r'blister',
     "Leave a blister intact if you can: it protects the skin underneath. Cover it with a blister plaster and take pressure off it. If it bursts, "
     "keep it clean, don't peel off the loose skin, and cover it. Signs of infection (spreading redness, warmth, pus) mean see a pharmacist or doctor."),
    (r'sore throat',
     "Most sore throats are viral and get better within a week. Warm drinks, honey and lemon, lozenges and gargling salt water help, as do rest and "
     "paracetamol or ibuprofen if suitable. See a doctor if it's very severe, lasts more than a week, or you have trouble swallowing or breathing."),
    (r'hay ?fever|sneez|pollen|allerg',
     "Antihistamine tablets (non-drowsy ones are available from pharmacies) and a steroid nasal spray started before the season help most. Keep "
     "windows closed when the pollen count is high, shower and change clothes after being outside, and wear wraparound sunglasses."),
    (r'back',
     "Most back pain from a strain gets better within a few weeks. Keep moving gently rather than resting in bed, use heat on the sore area, and take "
     "simple painkillers if suitable. See a doctor urgently for numbness around the bottom or genitals, weakness in the legs, or trouble passing "
     "urine; and soon if it isn't improving after a few weeks."),
)

# ------------------------------------------------------------------------------------------------------------ computers and phones
topic('computer', r'laptop|computer|pc|windows|mac|macbook|ssd|hard drive|ram|memory|wi-?fi|router|internet|phone|iphone|android|battery|backup|back up|password|virus|malware|printer',
      {'computer', 'device'})(
    (r'slow|check first|speed (?:it|this) up|running slow|faster',
     "For a slow Windows laptop, check these in order:\n\n1. **Restart it** properly (Start, Restart), and install any pending updates.\n"
     "2. **Startup apps**: Task Manager (Ctrl+Shift+Esc), Startup tab, disable what you don't need at startup.\n3. **What's using it**: in Task "
     "Manager's Processes tab, sort by CPU, Memory and Disk to see what's hogging it.\n4. **Free space**: keep at least 15 to 20% of the drive free; "
     "uninstall unused programs and run Disk Clean-up.\n5. **Malware**: run a full Windows Security scan.\n\nIf the Disk column often sits near 100% "
     "on an older laptop, the hard drive is the bottleneck, and an SSD is the biggest single upgrade."),
    (r'\bram\b|memory|more memory',
     "More RAM helps if you regularly run out: open Task Manager while you're working normally and look at Memory. If it's often above about 80 to "
     "90%, going to 8 GB (or 16 GB if you keep lots of browser tabs or bigger programs open) will make a noticeable difference. If memory use is low, "
     "more RAM won't speed it up; check the disk and startup apps instead. Many thin laptops have RAM soldered on, so check whether yours can be "
     "upgraded first."),
    (r'ssd|hard drive|replace the drive|solid state',
     "On a laptop that still has a spinning hard drive, an SSD is usually the best value upgrade there is: start-up, opening programs and general "
     "responsiveness often get several times faster. A 500 GB SSD is inexpensive. Check the drive type first (Task Manager, Performance, Disk shows "
     "'HDD' or 'SSD'), and either clone the old drive with free cloning software or do a fresh Windows install. If it already has an SSD, this upgrade "
     "won't help."),
    (r'back ?up|backup|before i change',
     "The simple way: plug in an external drive and copy your user folders (Documents, Pictures, Desktop, Downloads, Videos) onto it, or use "
     "Windows' File History to do it automatically. Also keep a copy in cloud storage (OneDrive, Google Drive, Dropbox) for anything you couldn't "
     "replace. A good rule is three copies, on two different devices, with one away from home. Check that you can open a few files from the backup "
     "before changing anything."),
    (r'battery',
     "To make a battery last: lower the screen brightness, turn off location, Bluetooth and background refresh for apps that don't need it, and "
     "check battery settings to see which apps use the most. Most batteries wear noticeably after two or three years; if it drains very fast or the "
     "device shuts down at 20 to 30%, a battery replacement is usually much cheaper than a new device."),
    (r'wi-?fi|internet|connection|router',
     "Restart the router (off for 30 seconds, then on) and the device. Move closer to the router or put the router somewhere central and raised, away "
     "from thick walls and microwaves. If one device is slow and others are fine, the problem is the device; if everything is slow, run a speed test "
     "and contact your provider if it's far below what you pay for."),
    (r'password',
     "Use a password manager (many are free) so every account gets a long, different password, and turn on two-factor authentication for email, "
     "banking and social media. A memorable passphrase of four or more random words works well for the few you have to remember."),
)

# ------------------------------------------------------------------------------------------------------------ long flights
topic('flight', r'flight|flying|fly to|plane|economy|long[- ]haul|layover|airport|jet ?lag', {'flight'})(
    (r'survive|comfortable|long (?:flight|haul)|economy|hours? (?:on|in) (?:a|the) plane|tips',
     "A few things make a long economy flight much easier:\n\n- **Seat**: an aisle seat lets you get up freely; choose it early.\n- **Comfort kit**: neck "
     "pillow, eye mask, earplugs or noise-cancelling headphones, a warm layer and comfortable loose clothes.\n- **Move**: walk the aisle every hour or two "
     "and do ankle circles in your seat; drink water, go easy on alcohol.\n- **Entertainment**: download films, podcasts and books before you go, and "
     "bring a charger or power bank.\n- **Pace it**: split the flight into chunks (a meal, a film, sleep) so it doesn't feel endless."),
    (r'sleep|stay awake|rest',
     "Base it on the time at your destination: sleep on the plane if it's night there, and stay awake if it's daytime there. For a flight that lands "
     "in the afternoon or evening, try to sleep in the first half and stay awake towards the end, so you're tired at a normal local bedtime. An eye "
     "mask, earplugs and skipping the coffee and alcohol make sleep easier."),
    (r'jet ?lag',
     "Switch to the destination's time as soon as you board: eat and sleep on its schedule, get bright daylight the morning after you land, and stay "
     "up until a normal local bedtime even if you're tired (a short nap under 30 minutes is fine). Most people adjust at about a day per time zone, "
     "and going east is harder than going west."),
)

# ------------------------------------------------------------------------------------------------------------ small business
topic('business', r'business|side hustle|selling|sell (?:my|them|it)|etsy|market stall|customers|handmade|small shop|startup|start-up|self-employed|freelanc')(
    (r'figure out|before i spend|first|where (?:do|should) i start|plan',
     "Before spending much:\n\n- **Check demand**: make a small batch and sell to friends, a local market or online, and see what people actually buy "
     "and at what price.\n- **Cost one unit**: materials, packaging and a fair value for your time.\n- **Look at competitors**: what they charge, how they "
     "present it, what reviews say.\n- **Rules**: what registration, labelling and safety rules apply to your product where you live.\n- **Budget**: "
     "keep most of the money in reserve and spend in small steps as sales come in."),
    (r'where (?:could|can|should) i sell|sell them|selling (?:them|it)|channels?|online',
     "Good places to start: local craft fairs and markets (you get instant feedback), an online shop on a marketplace such as Etsy, Instagram or local "
     "community groups to show your work, and nearby independent shops or cafés that take products on consignment. Start with one or two and add more "
     "once you know what sells."),
    (r'price|charge|how much (?:should|to) (?:i )?(?:charge|sell)',
     "Work it out from your costs, then check the market:\n\n1. Add up materials and packaging for one item.\n2. Add your time at an hourly rate you'd be "
     "happy with.\n3. Add a share of overheads (fees, equipment, stall costs).\n4. Multiply that cost by about 1.5 to 2 for a retail price, so you have "
     "room for profit and for selling to shops at wholesale (often about half the retail price).\n\nThen compare with similar products: if you're far "
     "below them, raise the price; handmade often sells better when it isn't the cheapest."),
    (r'insurance|licen[cs]e|legal|register|tax',
     "It depends on where you live, but the usual things are: registering as self-employed or a sole trader for tax once you're earning, public and "
     "product liability insurance (important for anything with a fire or safety risk, such as candles), and following product safety and labelling "
     "rules (for candles, safety warnings and the ingredients' hazard information). Your local government's small-business pages list the rules for "
     "your country, and craft-business insurance is often available cheaply as a bundle."),
)

# ------------------------------------------------------------------------------------------------------------ keeping in touch
topic('family', r'grandparents?|grandma|grandad|grandpa|granny|my parents|my mum|my mom|my dad|family|relatives|long[- ]distance|live far away|'
      r'hours away|stay in touch|keep in touch|stay closer|stay connected', {'relative'})(
    (r'stay (?:closer|close|in touch|connected)|keep in touch|without (?:going|visiting)|far away|hours away',
     "A few things keep you close between visits:\n\n- **A regular call**: the same day and time each week, so it becomes something everyone looks "
     "forward to. Video calls are lovely if they're comfortable with them.\n- **Little and often**: photos, short messages or a postcard; small "
     "contact counts.\n- **Share something**: the same book, a TV series to talk about, a recipe of theirs to cook, or questions about their life and "
     "old photos.\n- **Plan visits ahead**: fewer but planned visits (a long weekend every month or two) often work better than feeling guilty about "
     "every weekend.\n- **Involve others**: siblings or cousins can take turns."),
    (r'guilty|guilt',
     "That guilt usually comes from caring, not from doing something wrong. Most grandparents value regular contact far more than how often you "
     "visit. A weekly call and planned visits can be more than enough, and telling them you think about them often matters a lot."),
)

# ------------------------------------------------------------------------------------------------------------ houseplants while away
topic('plants_away', r'houseplants?|plants?|succulents?|cact(?:us|i)', {'plant', 'houseplant'})(
    (r'(?:keep|kept) (?:them|it|my \w+) alive|while i(?:\'m| am) (?:gone|away)|going away|holiday|vacation|two weeks|week away',
     "For two weeks away:\n\n- **Water well** the day before you go, and let the excess drain.\n- **Move them** out of direct sun to a cooler, bright "
     "spot, so they use less water.\n- **Group them** together; they keep each other's air more humid.\n- **Self-watering**: a tray of wet pebbles, "
     "water spikes or bottles, or a wick (a strip of cotton from a bowl of water into each pot) keeps the soil moist.\n- **Help**: a neighbour "
     "watering once a week is the most reliable option."),
    (r'bath|tub|sink|tray of water',
     "It can work for a week or two: put an old towel or a few centimetres of water in the bath, stand the plants (in pots with drainage holes) on "
     "it, and leave the bathroom window light on the plants. Don't leave pots sitting in deep water, which can rot the roots, and leave succulents "
     "and cacti out of it, as they're better off dry."),
    (r'succulents?|cact(?:us|i)|need anything different',
     "Yes: succulents and cacti are happy to be left dry for two weeks. Water them as normal the week before you go, then leave them out of any bath "
     "or tray setup and keep them in their sunny spot."),
    (r'neighbou?r|tell (?:her|him|them)|instructions|someone (?:to )?water',
     "Leave a short note so it's easy for them:\n\n- Which plants need watering and which don't (put a sticker on the succulents: 'no water').\n- "
     "How to check: water only if the top of the soil feels dry, until it drains, and empty saucers after.\n- Roughly how often: about once a week.\n"
     "- Where the watering can is, and your number in case anything looks wrong.\n\nA small thank-you when you get back is always appreciated."),
)
