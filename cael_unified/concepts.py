"""Everyday concepts explained simply, with the follow-ups people ask next (authored, no model).

'Explain inflation in simple terms' -> what it is; then 'Why does it happen?', 'Can you give an example?', 'Is it bad?',
'How does it affect me?' stay on the same concept. Facts are general and stable; nothing here is news.
"""
import re

# name: (pattern, what, why, example, good_or_bad, affects_me)
C = {
    'inflation': (r'\binflation\b',
        "Inflation is when prices in general go up over time, so the same amount of money buys a bit less each year. If inflation is 3%, something that cost $100 last year costs about $103 now.",
        "Mainly three things: people and businesses wanting to buy more than the economy can produce (too much demand), costs going up for producers, such as energy, wages or materials, which they pass on in prices, and a lot of new money or cheap credit in the economy. Expectations matter too: if everyone expects prices to rise, they ask for higher wages and raise prices, which keeps it going.",
        "If a loaf of bread costs $2.00 and inflation is 5% a year, next year it costs about $2.10, and in ten years about $3.26, even though it's the same loaf.",
        "A little is normal and even healthy: most central banks aim for about 2% a year. High inflation is harmful because savings lose value and wages fall behind prices; falling prices (deflation) can be bad too, because people delay spending.",
        "If your pay rises more slowly than prices, you can afford a little less each year. Cash savings lose value unless the interest beats inflation, while fixed-rate debts like a mortgage get slightly easier in real terms."),
    'interest': (r'\b(?:compound )?interest(?: rates?)?\b(?!.*\bin\b.*\b(?:hobby|music|art)\b)',
        "Interest is the price of borrowing money. If you borrow, you pay the lender a percentage on top; if you save, the bank pays you a percentage for using your money. Compound interest means you also earn (or pay) interest on the interest already added.",
        "Lenders charge it because they can't use the money while you have it, it loses value to inflation, and there's a risk you won't pay it back. Central banks set a base rate that the other rates follow; they raise it to cool inflation and lower it to encourage spending.",
        "Save $1,000 at 5% a year compounded: after one year you have $1,050, after two $1,102.50, after ten about $1,629. The extra $2.50 in year two is interest on the first year's interest.",
        "For savers higher rates are good; for borrowers they make loans and mortgages more expensive. Neither is simply good or bad: it depends which side you're on.",
        "It sets what your mortgage, credit card and loans cost, and what your savings earn. On debt, the rate and how long you take to pay matter most."),
    'recession': (r'\brecession\b',
        "A recession is when a country's economy shrinks instead of growing, usually defined as the total output (GDP) falling for two quarters in a row. Businesses sell less, so they hire less, and unemployment usually rises.",
        "Common triggers are a shock (a pandemic, an energy price spike, a financial crisis), interest rates raised sharply to fight inflation, or a bubble bursting, such as in house prices. Then a cycle starts: people spend less, businesses earn less, they cut jobs, people spend even less.",
        "In 2008-2009, many banks were hurt by bad mortgage loans, lending dried up, and most big economies shrank for several quarters.",
        "It's painful while it lasts, mainly through job losses, but most recessions last months rather than years, and economies usually recover.",
        "Jobs can be less secure and pay rises smaller. An emergency fund of a few months' costs and keeping debts manageable help most."),
    'stocks': (r'\b(?:stocks?|shares?|stock market)\b(?!.*\b(?:soup|cube|room)\b)',
        "A share (or stock) is a small piece of ownership in a company. If the company does well, the share usually becomes worth more and may pay you part of the profits (a dividend); if it does badly, it can fall.",
        "Share prices move with what investors expect the company to earn in future, and with the general mood about the economy and interest rates. In the short term they swing a lot; over long periods they've tended to rise with company profits.",
        "If you buy 10 shares at $50 ($500) and the price rises to $60, they're worth $600. If it pays a $1 dividend per share, you also get $10 a year.",
        "Over decades, a broad mix of shares has grown more than cash savings, but with ups and downs along the way. A single company can fail completely, which is why people spread money across many (index funds).",
        "Many pensions are invested in shares, so the stock market affects your retirement savings even if you never buy a share yourself."),
    'credit_score': (r'\bcredit (?:score|rating|history)\b',
        "A credit score is a number lenders use to judge how likely you are to repay borrowed money. It's built from your history of loans, cards and bills: paying on time pushes it up, missed payments push it down.",
        "Lenders can't know you personally, so they look at your track record. Credit reference agencies collect that record and turn it into a score.",
        "Someone who has paid a credit card in full every month for three years usually has a better score than someone who missed two payments last year, and gets offered lower interest rates.",
        "It isn't a judgement of you, just of your borrowing record. A good score saves money on loans and mortgages.",
        "Pay bills on time, keep card balances well below the limit, register to vote at your address (in the UK), and check your report for mistakes; all are free."),
    'mortgage': (r'\bmortgages?\b',
        "A mortgage is a loan to buy a home, paid back monthly over many years (often 25-30), with the home as security: if you stop paying, the lender can take it.",
        "Few people can pay for a house in cash, so a bank lends most of the price and earns interest; the property lowers its risk.",
        "Buy a $300,000 home with a $30,000 deposit and borrow $270,000 over 25 years at 5%: the payment is about $1,580 a month.",
        "It's the usual way to buy a home. The risks are rates rising (on a variable mortgage) and borrowing more than you can comfortably repay.",
        "Your rate, the deposit, and the length of the loan decide the monthly cost; a bigger deposit usually gets a better rate."),
    'climate_change': (r'\bclimate change\b|\bglobal warming\b',
        "Climate change is the long-term warming of the Earth and the changes in weather patterns that come with it. The planet is now about 1.2 °C warmer than before industrial times.",
        "Mostly burning coal, oil and gas, which releases carbon dioxide. CO2 and other greenhouse gases trap heat that would otherwise escape to space, like a blanket. Cutting down forests adds to it.",
        "More frequent heatwaves, heavier downpours in some places and droughts in others, melting glaciers and sea ice, and sea levels rising by about 20 cm since 1900.",
        "Scientists agree it's harmful for people and nature, and that the more it warms, the worse the effects. The good news is that cutting emissions slows it.",
        "Hotter summers, more extreme weather and higher costs for food and insurance over time. Using less energy, travelling lower-carbon and eating less meat are the biggest personal changes."),
    'vaccines': (r'\bvaccines?\b|\bvaccination\b|\bimmunisation\b',
        "A vaccine trains your immune system to recognise a germ without making you ill, so if the real germ arrives later, your body fights it off fast.",
        "It contains a harmless piece or a weakened or inactivated form of the germ (or instructions for your cells to make one harmless piece). The immune system makes antibodies and memory cells against it.",
        "The measles vaccine has made measles rare in countries where most children get it; where vaccination drops, outbreaks return.",
        "Vaccines are among the most effective health measures ever: they've prevented millions of deaths. Side effects are usually mild, like a sore arm for a day.",
        "Keeping up to date protects you and people around you who can't be vaccinated, such as newborn babies. Your doctor or pharmacist can say which ones you need."),
    'ai': (r'\bartificial intelligence\b|\b(?:an? )?ai\b|\bmachine learning\b',
        "Artificial intelligence means computer systems doing tasks that normally need human thinking: recognising speech or images, translating, answering questions, or playing games. Many modern systems learn patterns from large amounts of examples (machine learning).",
        "It has grown fast because computers got much faster, huge amounts of data became available online, and new methods made learning from that data work well.",
        "Spam filters, voice assistants, map apps predicting traffic, and recommendations on streaming sites are all everyday AI.",
        "It's a tool: useful for many things, with real risks such as mistakes, bias learned from data, privacy and misuse. It's best treated as helpful but checkable.",
        "You probably already use it daily. It's worth checking important answers it gives, and being careful what personal information you share with it."),
    'blockchain': (r'\bblockchain\b|\bcrypto(?:currency|currencies)?\b|\bbitcoin\b',
        "A cryptocurrency such as Bitcoin is digital money with no central bank: transactions are recorded in a shared public ledger called a blockchain, which thousands of computers keep copies of.",
        "It was created (Bitcoin in 2009) so people could send value directly without a bank in the middle; the shared ledger and cryptography stop anyone spending the same coin twice.",
        "Sending Bitcoin means broadcasting a signed message; computers on the network check it and add it to the next block, and after that it can't easily be changed.",
        "The technology is clever, but prices swing wildly, scams are common, and lost passwords mean lost money. Many regulators warn it's high risk.",
        "If you're thinking of buying, only use money you could afford to lose completely, and never send crypto to someone who contacted you first: that's the most common scam."),
    'supply_demand': (r'\bsupply and demand\b|\bdemand and supply\b',
        "Supply and demand explains prices: when lots of people want something (high demand) and there isn't much of it (low supply), the price goes up; when there's plenty and few want it, the price falls.",
        "Sellers raise prices when they can sell everything anyway, and cut them when goods aren't selling. Buyers buy less as prices rise. The price settles where the amount people want matches the amount on sale.",
        "Concert tickets for a famous band sell out and resell for more; strawberries are cheap in summer when there's a glut and dearer in winter.",
        "It isn't good or bad, just how markets usually work. Governments sometimes step in when it gives unfair results, such as rent controls or price caps.",
        "It's why flights cost more in school holidays and why buying out of season saves money."),
    'gdp': (r'\bgdp\b|\bgross domestic product\b',
        "GDP (gross domestic product) is the total value of everything a country produces in a year: goods and services. It's the usual measure of the size of an economy, and 'growth' means GDP going up.",
        "It's measured because governments and central banks need to know whether the economy is growing or shrinking to set taxes, spending and interest rates.",
        "If a country produced $2.0 trillion of goods and services last year and $2.04 trillion this year (after removing inflation), its economy grew by 2%.",
        "It's a useful snapshot but not a measure of wellbeing: it ignores inequality, unpaid work and damage to the environment.",
        "Strong growth usually means more jobs and rising pay; shrinking GDP (a recession) usually means the opposite."),
    'black_hole': (r'\bblack holes?\b',
        "A black hole is a place in space where gravity is so strong that nothing, not even light, can escape once it crosses the edge (the event horizon).",
        "Most form when a very massive star runs out of fuel and its core collapses under its own gravity into a tiny space. Giant ones sit at the centres of galaxies, including ours.",
        "The black hole at the centre of our galaxy, Sagittarius A*, has about four million times the mass of the Sun; astronomers photographed its shadow in 2022.",
        "They're not cosmic vacuum cleaners: from far away, a black hole pulls like any other object of the same mass. The nearest known is over a thousand light years away.",
        "Not at all in daily life. They do help scientists test gravity, and some GPS-style corrections come from the same theory (Einstein's relativity)."),
    'dna': (r'\bdna\b|\bgenes?\b|\bgenetics\b',
        "DNA is the long molecule in your cells that carries the instructions for building and running your body. A gene is one section of DNA with the recipe for one thing, usually a protein.",
        "You inherit half your DNA from each parent, which is why children resemble their parents; small changes (mutations) over many generations are what drives evolution.",
        "Eye colour, blood group and some inherited conditions are shaped by genes; most traits, like height, depend on many genes plus environment.",
        "It isn't destiny: for most health conditions, lifestyle and environment matter as much as genes.",
        "Some medical tests read parts of your DNA, for example to check for inherited conditions; your doctor can explain whether one is useful for you."),
    'electricity': (r'\belectricity\b|\belectric current\b',
        "Electricity is the flow of tiny charged particles called electrons through a material such as copper wire. That flow carries energy that can light a bulb, turn a motor or heat a kettle.",
        "A battery or power station pushes the electrons (that push is voltage); they flow when there's a complete loop (a circuit). Switches work by breaking or closing the loop.",
        "Flick a light switch and you close the circuit: electrons flow through the bulb, it heats or excites the filament or LED, and it gives off light.",
        "It's hugely useful but dangerous at mains voltage: water and damaged cables are the main risks.",
        "Your bill counts energy in kilowatt-hours: a 2 kW heater on for one hour uses 2 kWh."),
    'gravity': (r'\bgravity\b',
        "Gravity is the pull that every object with mass has on every other. It keeps your feet on the ground, the Moon going round the Earth and the Earth going round the Sun.",
        "The more mass something has, the stronger its pull, and the pull gets weaker with distance. Einstein explained it as mass bending space and time, so objects follow curved paths.",
        "Drop a ball and it speeds up by about 9.8 metres per second every second; on the Moon, with less mass, it falls about six times more slowly.",
        "Without it there'd be no planets, stars or atmosphere.",
        "It's why things fall, why you weigh what you do, and why tides happen."),
    'democracy': (r'\bdemocracy\b',
        "Democracy is a system of government where the people choose their leaders, usually by voting in free elections, and can vote them out again.",
        "The idea is that power should come from the people being governed, and that regular elections, free speech and courts independent of the government keep leaders accountable.",
        "In a general election, citizens vote for representatives; the party or coalition with most support forms the government, and the next election can replace it.",
        "Most people see it as the fairest system, though it can be slow and depends on informed voters, honest elections and a free press.",
        "Voting, contacting your representative and taking part in local decisions are how you have a say."),
    'pension': (r'\bpensions?\b',
        "A pension is money saved during your working life to live on when you retire. It may come from the state, from your employer, or from your own savings plan.",
        "Most people live many years after they stop working, and saving a little regularly from early on, with tax relief and investment growth, makes that affordable.",
        "If you and your employer together put 8% of a $40,000 salary ($3,200) into a pension each year for 40 years, with modest growth, it can grow to several hundred thousand dollars.",
        "It's one of the most efficient ways to save, because of tax relief and employer contributions, but the money is usually locked away until a set age.",
        "Joining your workplace scheme and taking any employer match is usually worth it: it's extra pay you'd otherwise miss."),
}

FOLLOW = [
    (re.compile(r"(?i)\bwhy (?:does|do|is|are|did|would) (?:it|that|this|they|these|those|we|people)\b|\bwhat causes (?:it|that|this)\b|\bwhy\??\s*$|\bwhat'?s the cause\b|\bhow does (?:it|that) happen\b"), 2),
    (re.compile(r"(?i)\b(?:an? )?example\b|\bfor instance\b|\bshow me\b"), 3),
    (re.compile(r"(?i)\b(?:is|are) (?:it|that|this|they|these|those) (?:bad|good|dangerous|a problem|harmful|safe|risky|worth it|a good idea)\b|\bany (?:side effects|risks?)\b|\bshould i (?:worry|be worried)\b"), 4),
    (re.compile(r"(?i)\b(?:how )?(?:does|do|will|would|could) (?:it|that|this|they) affect (?:me|us|my|our)\b|\bwhat does (?:it|that) mean for (?:me|us)\b|\bwhat should i do\b|\bhow does (?:it|that) impact\b"), 5),
]
ASK = re.compile(r"(?i)\b(?:what (?:is|are|'s)|explain|what does .{1,30} mean|tell me about|how (?:does|do) .{1,30} work|how .{1,20} works?|in simple terms|why (?:do|does|is|are) we (?:need|have|use)|simply|eli5|describe)\b")


def find(text):
    for name, row in C.items():
        if re.search('(?i)' + row[0], text):
            return name
    return None


_index = None


def matched(text):
    global _index
    if _index is None:
        from .phrase_match import Index
        _index = Index({n: n.replace('_', ' ') + ' ' + ' '.join(row[1:]) for n, row in C.items()})
    return _index.best(text, least=6.0, margin=1.3)


def respond(messages):
    text = (messages[-1].get('content') or '').strip()
    if not text or len(text) > 240:
        return None
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    name = find(text)
    if name is None and ASK.search(text):
        name = matched(text)                # a rewording: word overlap with the concepts' own text (phrase_match)
    if name and ASK.search(text):
        for pattern, field in FOLLOW:
            if pattern.search(text) and field != 2:
                break
        else:
            field = 1
        if re.search(r'(?i)\bwhy\b|\bcauses?\b', text):
            field = 2
        if re.search(r'(?i)\bwhy (?:does|do|is|are) (?:it|they|that|this) (?:matter|important)\b|\bwhy (?:should|would) (?:i|we) care\b', text):
            field = 4
        parts = [field]
        if field != 1 and re.search(r"(?i)\bwhat (?:is|are|'s)\b|\bexplain\b", text):
            parts = [1, field]              # "What is a credit score and why does it matter?": both halves
        return dict(route='chat/concept', response=' '.join(C[name][f] for f in parts), sources=[],
                    details=f'Authored concept explanation ({name}; concepts.py).')
    if name is None and len(users) > 1 and len(text.split()) <= 14:
        previous = None
        for m in reversed(messages[:-1]):
            if m.get('role') == 'assistant':
                said = m.get('content') or ''
                previous = next((n for n, row in C.items() if any(said.strip()[:50] == r[:50] for r in row[1:])), None)
                break
        if previous:
            for pattern, field in FOLLOW:
                if pattern.search(text):
                    return dict(route='chat/concept-followup', response=C[previous][field], sources=[],
                                details=f'Authored concept explanation ({previous}; concepts.py).')
    return None
