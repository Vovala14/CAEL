"""More everyday topics for advice_library.py: cooking for a vegetarian guest, a chirping smoke alarm, and clover in a
lawn. Same format as the other topic files; general guidance, authored."""
from .advice_library import topic

# ------------------------------------------------------------------------------------------------------------ vegetarian guest
topic('vegetarian', r'vegetarian|vegan|plant-based|meat-free|doesn\'?t eat meat|don\'?t eat meat')(
    (r'day before|ahead|in advance|make it (?:the )?(?:night|day)|prepare (?:it )?early|freeze',
     "Yes, most vegetarian bakes are better made the day before: a lasagne, a vegetable moussaka, a dal or a chickpea and spinach curry all "
     "improve overnight in the fridge. Assemble it, cover it and chill it, then bake or reheat it until piping hot (a lasagne needs about 40 to "
     "45 minutes at 180 °C from cold). Keep anything crisp, like a salad or toasted nuts, separate and add it just before serving."),
    (r'starter|appeti[sz]er|first course|nibbles|canap',
     "A few easy vegetarian starters: burrata or mozzarella with tomatoes, basil and good olive oil; a roasted red pepper or tomato soup; "
     "bruschetta with mushrooms and garlic; or a simple plate of hummus, olives and warm flatbread. Pick something light if the main is rich."),
    (r'check|ask (?:her|him|them)|anything (?:else|i should)|allerg|eat (?:eggs|fish|cheese)|strict',
     "It's worth checking three things: whether she eats eggs and dairy (or is vegan), whether fish is a no (it usually is for vegetarians), and "
     "any allergies. Some cheeses, like traditional Parmesan, are made with animal rennet, so look for a vegetarian version; also watch for stock "
     "cubes, Worcestershire sauce and gelatine in desserts. Most vegetarians are happy to be asked, and it saves guessing."),
    (r'dessert|pudding|sweet',
     "Most desserts are already vegetarian: a chocolate mousse, a fruit crumble with cream, or a lemon tart. Just avoid gelatine (in some "
     "cheesecakes, jellies and marshmallows) unless you use a vegetarian setting agent."),
    (r'main|impress|cook|make|dish|recipe|dinner|meal|what (?:can|should|could) i',
     "A few vegetarian mains that are easy but feel special:\n\n- **Mushroom and spinach lasagne** or a roasted vegetable lasagne.\n"
     "- **Butternut squash risotto** with sage and Parmesan (vegetarian Parmesan).\n- **Chickpea and spinach curry** with rice and naan.\n"
     "- **Stuffed peppers** with rice, feta, herbs and tomatoes.\n- **A mushroom Wellington** if you want a show-stopper.\n\n"
     "The lasagne or the curry can be made the day before, which leaves you free when she arrives."),
)

# ------------------------------------------------------------------------------------------------------------ smoke alarms
topic('smoke_alarm', r'smoke (?:alarm|detector)s?|fire alarm|carbon monoxide (?:alarm|detector)|co alarm')(
    (r'changed the battery|new battery|still (?:doing it|chirping|beeping)|what else|after (?:changing|replacing)',
     "If it still chirps with a new battery, the usual causes are:\n\n1. **It needs resetting**: hold the test button for 15 to 20 seconds "
     "(or take the battery out, press and hold the test button, then refit it). Many alarms keep chirping until reset.\n"
     "2. **The alarm itself is at end of life**: most smoke alarms are designed to last about 10 years, and chirp when they expire. Check the "
     "date on the back; if it's old, replace the whole unit.\n3. **Wrong or weak battery**: use the exact type the alarm asks for, from a fresh pack.\n"
     "4. **It's a different alarm**: chirps are hard to locate; check the others, including carbon monoxide alarms.\n"
     "5. **Mains-powered alarms** also have a backup battery, and chirp when it's low.\n\nDust can also set them off: a gentle vacuum around the vents helps."),
    (r'chirp|beep|every (?:minute|few)|keeps|driving me|why',
     "A single chirp every minute or so almost always means the battery is low. Replace it with the exact type the alarm takes, then press and "
     "hold the test button for about 15 seconds to reset it. If it carries on, check the date on the back: most alarms need replacing after "
     "about 10 years, and chirp when they reach end of life."),
)

# ------------------------------------------------------------------------------------------------------------ clover in lawns
topic('clover_lawn', r'clover')(
    (r'good for|bad for|should i (?:get rid|remove|kill)|keep it|worth|lawn|grass',
     "Clover is generally good for a lawn, unless you want a perfectly uniform look. It stays green in dry spells, needs little or no mowing "
     "or feeding, and takes nitrogen from the air and feeds it to the soil, which helps the grass around it. Bees love the flowers (mow before "
     "it flowers if children play barefoot). A lot of clover is often a sign the soil is low in nitrogen; feeding the lawn tips the balance back "
     "to grass if you'd rather have less of it."),
)
