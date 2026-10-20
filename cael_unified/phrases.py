"""Common phrases in about 55 languages, hand-written for the everyday translation reply.

Scripts other than Latin carry a romanisation in brackets. A phrase that is missing for a language is simply not
offered; the reply never guesses. These are everyday forms; many languages have more polite or regional
variants, and a slash marks the most common alternatives (for example the form said to a man / to a woman).
"""
import re
import unicodedata

PHRASES = ['hello', 'goodbye', 'thank you', 'please', 'yes', 'no', 'sorry', 'excuse me', 'good morning', 'good night',
           'how are you', 'i love you', 'welcome', 'water', 'friend', 'cat', 'dog', 'cheers', 'happy birthday', 'good luck']
KEYS = dict(hello='hello', bye='goodbye', thanks='thank you', please='please', yes='yes', no='no', sorry='sorry',
            excuse='excuse me', morning='good morning', night='good night', how='how are you', love='i love you',
            welcome='welcome', water='water', friend='friend', cat='cat', dog='dog', cheers='cheers', birthday='happy birthday',
            luck='good luck')
ALIASES = {'hi': 'hello', 'hey': 'hello', 'hallo': 'hello', 'bye': 'goodbye', 'good bye': 'goodbye', 'see you': 'goodbye',
           'thanks': 'thank you', 'thank you very much': 'thank you', 'thankyou': 'thank you', 'i am sorry': 'sorry',
           "i'm sorry": 'sorry', 'how are you doing': 'how are you', 'good evening': None, 'friends': 'friend',
           'love you': 'i love you', 'i love u': 'i love you', 'happy bday': 'happy birthday'}
LANGUAGE_ALIASES = {'mandarin': 'chinese', 'farsi': 'persian', 'tagalog': 'filipino', 'bahasa': 'indonesian',
                    'castilian': 'spanish', 'gaelic': 'irish', 'kiswahili': 'swahili', 'brazilian': 'portuguese',
                    'flemish': 'dutch', 'bokmal': 'norwegian', 'cantonese': None, 'hawaii': 'hawaiian', 'maori': 'maori',
                    'te reo': 'maori', 'bangla': 'bengali'}


def L(**phrases):
    return {KEYS[k]: v for k, v in phrases.items()}


TABLE = {
    'spanish': L(hello='hola', bye='adiós', thanks='gracias', please='por favor', yes='sí', no='no', sorry='lo siento',
                 excuse='perdón / disculpe', morning='buenos días', night='buenas noches', how='¿cómo estás?', love='te quiero',
                 welcome='bienvenido / bienvenida', water='agua', friend='amigo / amiga', cat='gato', dog='perro', cheers='¡salud!',
                 birthday='feliz cumpleaños', luck='buena suerte'),
    'french': L(hello='bonjour', bye='au revoir', thanks='merci', please="s'il vous plaît", yes='oui', no='non', sorry='désolé(e)',
                excuse='excusez-moi', morning='bonjour', night='bonne nuit', how='comment ça va ?', love="je t'aime",
                welcome='bienvenue', water='eau', friend='ami / amie', cat='chat', dog='chien', cheers='santé !',
                birthday='joyeux anniversaire', luck='bonne chance'),
    'german': L(hello='hallo', bye='auf Wiedersehen / tschüss', thanks='danke', please='bitte', yes='ja', no='nein',
                sorry='Entschuldigung', excuse='entschuldigen Sie', morning='guten Morgen', night='gute Nacht',
                how='wie geht es dir?', love='ich liebe dich', welcome='willkommen', water='Wasser', friend='Freund / Freundin',
                cat='Katze', dog='Hund', cheers='prost!', birthday='alles Gute zum Geburtstag', luck='viel Glück'),
    'italian': L(hello='ciao', bye='arrivederci', thanks='grazie', please='per favore', yes='sì', no='no', sorry='scusa',
                 excuse='mi scusi', morning='buongiorno', night='buonanotte', how='come stai?', love='ti amo',
                 welcome='benvenuto / benvenuta', water='acqua', friend='amico / amica', cat='gatto', dog='cane', cheers='salute!',
                 birthday='buon compleanno', luck='buona fortuna'),
    'portuguese': L(hello='olá', bye='adeus / tchau', thanks='obrigado / obrigada', please='por favor', yes='sim', no='não',
                    sorry='desculpa', excuse='com licença', morning='bom dia', night='boa noite', how='como você está?',
                    love='eu te amo', welcome='bem-vindo / bem-vinda', water='água', friend='amigo / amiga', cat='gato',
                    dog='cão / cachorro', cheers='saúde!', birthday='feliz aniversário', luck='boa sorte'),
    'dutch': L(hello='hallo', bye='tot ziens', thanks='dank je', please='alsjeblieft', yes='ja', no='nee', sorry='sorry',
               excuse='pardon', morning='goedemorgen', night='goedenacht', how='hoe gaat het?', love='ik hou van je',
               welcome='welkom', water='water', friend='vriend / vriendin', cat='kat', dog='hond', cheers='proost!',
               birthday='gefeliciteerd', luck='veel succes'),
    'catalan': L(hello='hola', bye='adéu', thanks='gràcies', please='si us plau', yes='sí', no='no', sorry='ho sento',
                 excuse='perdoni', morning='bon dia', night='bona nit', how='com estàs?', love="t'estimo", welcome='benvingut / benvinguda',
                 water='aigua', friend='amic / amiga', cat='gat', dog='gos', cheers='salut!'),
    'romanian': L(hello='salut / bună', bye='la revedere', thanks='mulțumesc', please='vă rog', yes='da', no='nu',
                  sorry='îmi pare rău', excuse='scuzați-mă', morning='bună dimineața', night='noapte bună', how='ce mai faci?',
                  love='te iubesc', welcome='bine ai venit', water='apă', friend='prieten / prietenă', cat='pisică', dog='câine',
                  cheers='noroc!', birthday='la mulți ani', luck='baftă / noroc'),
    'latin': L(hello='salve', bye='vale', thanks='gratias tibi ago', please='quaeso', yes='ita', no='minime', sorry='ignosce mihi',
               morning='bonum mane', night='bonam noctem', how='quid agis?', love='te amo', water='aqua', friend='amicus / amica',
               cat='feles', dog='canis'),
    'esperanto': L(hello='saluton', bye='ĝis revido', thanks='dankon', please='bonvolu', yes='jes', no='ne', sorry='pardonon',
                   morning='bonan matenon', night='bonan nokton', how='kiel vi fartas?', love='mi amas vin', welcome='bonvenon',
                   water='akvo', friend='amiko', cat='kato', dog='hundo', birthday='feliĉan naskiĝtagon'),
    'english': L(hello='hello', bye='goodbye', thanks='thank you', please='please', yes='yes', no='no', sorry='sorry',
                 excuse='excuse me', morning='good morning', night='good night', how='how are you?', love='I love you',
                 welcome='welcome', water='water', friend='friend', cat='cat', dog='dog', cheers='cheers', birthday='happy birthday',
                 luck='good luck'),
    'swedish': L(hello='hej', bye='hej då', thanks='tack', please='snälla', yes='ja', no='nej', sorry='förlåt', excuse='ursäkta',
                 morning='god morgon', night='god natt', how='hur mår du?', love='jag älskar dig', welcome='välkommen',
                 water='vatten', friend='vän', cat='katt', dog='hund', cheers='skål!', birthday='grattis på födelsedagen',
                 luck='lycka till'),
    'norwegian': L(hello='hei', bye='ha det', thanks='takk', please='vær så snill', yes='ja', no='nei', sorry='unnskyld',
                   excuse='unnskyld meg', morning='god morgen', night='god natt', how='hvordan har du det?', love='jeg elsker deg',
                   welcome='velkommen', water='vann', friend='venn', cat='katt', dog='hund', cheers='skål!',
                   birthday='gratulerer med dagen', luck='lykke til'),
    'danish': L(hello='hej', bye='farvel', thanks='tak', please='vær så venlig', yes='ja', no='nej', sorry='undskyld',
                morning='godmorgen', night='godnat', how='hvordan har du det?', love='jeg elsker dig', welcome='velkommen',
                water='vand', friend='ven', cat='kat', dog='hund', cheers='skål!', birthday='tillykke med fødselsdagen',
                luck='held og lykke'),
    'icelandic': L(hello='halló', bye='bless', thanks='takk', please='vinsamlegast', yes='já', no='nei', sorry='fyrirgefðu',
                   morning='góðan daginn', night='góða nótt', how='hvað segirðu?', love='ég elska þig', welcome='velkomin',
                   water='vatn', friend='vinur', cat='köttur', dog='hundur', cheers='skál!'),
    'finnish': L(hello='hei / moi', bye='näkemiin', thanks='kiitos', please='ole hyvä', yes='kyllä', no='ei', sorry='anteeksi',
                 excuse='anteeksi', morning='hyvää huomenta', night='hyvää yötä', how='mitä kuuluu?', love='minä rakastan sinua',
                 welcome='tervetuloa', water='vesi', friend='ystävä', cat='kissa', dog='koira', cheers='kippis!',
                 birthday='hyvää syntymäpäivää', luck='onnea'),
    'estonian': L(hello='tere', bye='head aega', thanks='aitäh', please='palun', yes='jah', no='ei', sorry='vabandust',
                  morning='tere hommikust', night='head ööd', how='kuidas läheb?', love='ma armastan sind', welcome='tere tulemast',
                  water='vesi', friend='sõber', cat='kass', dog='koer'),
    'hungarian': L(hello='szia', bye='viszlát', thanks='köszönöm', please='kérem', yes='igen', no='nem', sorry='bocsánat',
                   excuse='elnézést', morning='jó reggelt', night='jó éjszakát', how='hogy vagy?', love='szeretlek',
                   welcome='üdvözöljük', water='víz', friend='barát', cat='macska', dog='kutya', cheers='egészségedre!',
                   birthday='boldog születésnapot', luck='sok szerencsét'),
    'polish': L(hello='cześć', bye='do widzenia', thanks='dziękuję', please='proszę', yes='tak', no='nie', sorry='przepraszam',
                excuse='przepraszam', morning='dzień dobry', night='dobranoc', how='jak się masz?', love='kocham cię',
                welcome='witamy', water='woda', friend='przyjaciel / przyjaciółka', cat='kot', dog='pies', cheers='na zdrowie!',
                birthday='wszystkiego najlepszego', luck='powodzenia'),
    'czech': L(hello='ahoj', bye='na shledanou', thanks='děkuji', please='prosím', yes='ano', no='ne', sorry='promiňte',
               morning='dobré ráno', night='dobrou noc', how='jak se máš?', love='miluji tě', welcome='vítejte', water='voda',
               friend='přítel / přítelkyně', cat='kočka', dog='pes', cheers='na zdraví!', luck='hodně štěstí'),
    'slovak': L(hello='ahoj', bye='dovidenia', thanks='ďakujem', please='prosím', yes='áno', no='nie', sorry='prepáčte',
                morning='dobré ráno', night='dobrú noc', how='ako sa máš?', love='ľúbim ťa', welcome='vitajte', water='voda',
                friend='priateľ / priateľka', cat='mačka', dog='pes', cheers='na zdravie!'),
    'croatian': L(hello='bok / zdravo', bye='doviđenja', thanks='hvala', please='molim', yes='da', no='ne', sorry='oprostite',
                  morning='dobro jutro', night='laku noć', how='kako si?', love='volim te', welcome='dobrodošli', water='voda',
                  friend='prijatelj / prijateljica', cat='mačka', dog='pas', cheers='živjeli!', birthday='sretan rođendan'),
    'serbian': L(hello='здраво (zdravo)', bye='довиђења (doviđenja)', thanks='хвала (hvala)', please='молим (molim)', yes='да (da)',
                 no='не (ne)', sorry='извините (izvinite)', morning='добро јутро (dobro jutro)', night='лаку ноћ (laku noć)',
                 how='како си? (kako si?)', love='волим те (volim te)', welcome='добродошли (dobrodošli)', water='вода (voda)',
                 friend='пријатељ (prijatelj)', cat='мачка (mačka)', dog='пас (pas)', cheers='живели! (živeli!)'),
    'bulgarian': L(hello='здравей (zdravey)', bye='довиждане (dovizhdane)', thanks='благодаря (blagodarya)', please='моля (molya)',
                   yes='да (da)', no='не (ne)', sorry='съжалявам (sazhalyavam)', morning='добро утро (dobro utro)',
                   night='лека нощ (leka nosht)', how='как си? (kak si?)', love='обичам те (obicham te)',
                   welcome='добре дошли (dobre doshli)', water='вода (voda)', friend='приятел (priyatel)', cat='котка (kotka)',
                   dog='куче (kuche)', cheers='наздраве! (nazdrave!)'),
    'russian': L(hello='привет (privet)', bye='до свидания (do svidaniya)', thanks='спасибо (spasibo)', please='пожалуйста (pozhaluysta)',
                 yes='да (da)', no='нет (net)', sorry='извините (izvinite)', excuse='извините (izvinite)',
                 morning='доброе утро (dobroye utro)', night='спокойной ночи (spokoynoy nochi)', how='как дела? (kak dela?)',
                 love='я тебя люблю (ya tebya lyublyu)', welcome='добро пожаловать (dobro pozhalovat)', water='вода (voda)',
                 friend='друг (drug)', cat='кошка (koshka)', dog='собака (sobaka)', cheers='за здоровье! (za zdorovye!)',
                 birthday='с днём рождения (s dnyom rozhdeniya)', luck='удачи (udachi)'),
    'ukrainian': L(hello='привіт (pryvit)', bye='до побачення (do pobachennia)', thanks='дякую (diakuiu)', please='будь ласка (bud laska)',
                   yes='так (tak)', no='ні (ni)', sorry='вибачте (vybachte)', morning='доброго ранку (dobroho ranku)',
                   night='на добраніч (na dobranich)', how='як справи? (yak spravy?)', love='я тебе кохаю (ya tebe kokhaiu)',
                   welcome='ласкаво просимо (laskavo prosymo)', water='вода (voda)', friend='друг (druh)', cat='кіт (kit)',
                   dog='собака (sobaka)', birthday='з днем народження (z dnem narodzhennia)', luck='удачі (udachi)'),
    'lithuanian': L(hello='labas', bye='viso gero', thanks='ačiū', please='prašau', yes='taip', no='ne', sorry='atsiprašau',
                    morning='labas rytas', night='labanakt', how='kaip sekasi?', love='aš tave myliu', welcome='sveiki atvykę',
                    water='vanduo', friend='draugas', cat='katė', dog='šuo'),
    'latvian': L(hello='sveiki', bye='uz redzēšanos', thanks='paldies', please='lūdzu', yes='jā', no='nē', sorry='atvainojiet',
                 morning='labrīt', night='ar labu nakti', how='kā tev iet?', love='es tevi mīlu', welcome='laipni lūdzam',
                 water='ūdens', friend='draugs', cat='kaķis', dog='suns'),
    'greek': L(hello='γεια σου (geia sou)', bye='αντίο (antío)', thanks='ευχαριστώ (efcharistó)', please='παρακαλώ (parakaló)',
               yes='ναι (nai)', no='όχι (óchi)', sorry='συγγνώμη (signómi)', excuse='συγγνώμη (signómi)', morning='καλημέρα (kaliméra)',
               night='καληνύχτα (kalinýchta)', how='τι κάνεις; (ti káneis?)', love="σ' αγαπώ (s' agapó)",
               welcome='καλώς ήρθατε (kalós írthate)', water='νερό (neró)', friend='φίλος (fílos)', cat='γάτα (gáta)',
               dog='σκύλος (skýlos)', cheers='γεια μας! (geia mas!)', birthday='χρόνια πολλά (chrónia pollá)', luck='καλή τύχη (kalí týchi)'),
    'irish': L(hello='dia duit', bye='slán', thanks='go raibh maith agat', please='le do thoil', sorry='tá brón orm',
               morning='maidin mhaith', night='oíche mhaith', how='conas atá tú?', love='tá grá agam duit', welcome='fáilte',
               water='uisce', friend='cara', cat='cat', dog='madra', cheers='sláinte!', birthday='lá breithe sona duit',
               luck='go n-éirí leat'),
    'welsh': L(hello='helo / shwmae', bye='hwyl fawr', thanks='diolch', please='os gwelwch yn dda', sorry="mae'n ddrwg gen i",
               morning='bore da', night='nos da', how='sut wyt ti?', love="rwy'n dy garu di", welcome='croeso', water='dŵr',
               friend='ffrind', cat='cath', dog='ci', cheers='iechyd da!', birthday='penblwydd hapus'),
    'turkish': L(hello='merhaba', bye='hoşça kal', thanks='teşekkür ederim', please='lütfen', yes='evet', no='hayır',
                 sorry='özür dilerim', excuse='affedersiniz', morning='günaydın', night='iyi geceler', how='nasılsın?',
                 love='seni seviyorum', welcome='hoş geldiniz', water='su', friend='arkadaş', cat='kedi', dog='köpek',
                 cheers='şerefe!', birthday='doğum günün kutlu olsun', luck='iyi şanslar'),
    'arabic': L(hello='مرحبا (marhaban)', bye='مع السلامة (ma\'a as-salama)', thanks='شكرا (shukran)', please='من فضلك (min fadlak)',
                yes='نعم (na\'am)', no='لا (la)', sorry='آسف (asif)', morning='صباح الخير (sabah al-khayr)',
                night='تصبح على خير (tusbih \'ala khayr)', how='كيف حالك؟ (kayfa haluk?)', love='أحبك (uhibbuk)',
                welcome='أهلا وسهلا (ahlan wa sahlan)', water='ماء (ma\')', friend='صديق (sadiq)', cat='قطة (qitta)', dog='كلب (kalb)',
                birthday='عيد ميلاد سعيد (\'id milad sa\'id)', luck='حظا سعيدا (hazzan sa\'idan)'),
    'hebrew': L(hello='שלום (shalom)', bye='להתראות (lehitra\'ot)', thanks='תודה (toda)', please='בבקשה (bevakasha)', yes='כן (ken)',
                no='לא (lo)', sorry='סליחה (slicha)', excuse='סליחה (slicha)', morning='בוקר טוב (boker tov)',
                night='לילה טוב (laila tov)', how='מה שלומך? (ma shlomkha / ma shlomekh?)',
                love='אני אוהב אותך / אני אוהבת אותך (ani ohev otakh / ani ohevet otkha)', welcome='ברוכים הבאים (bruchim haba\'im)',
                water='מים (mayim)', friend='חבר / חברה (chaver / chavera)', cat='חתול (chatul)', dog='כלב (kelev)',
                cheers='לחיים! (lechaim!)', birthday='יום הולדת שמח (yom huledet sameach)', luck='בהצלחה (behatzlacha)'),
    'persian': L(hello='سلام (salâm)', bye='خداحافظ (khodâhâfez)', thanks='ممنون / مرسی (mamnun / mersi)', please='لطفاً (lotfan)',
                 yes='بله (bale)', no='نه (na)', sorry='ببخشید (bebakhshid)', excuse='ببخشید (bebakhshid)', morning='صبح بخیر (sobh bekheyr)',
                 night='شب بخیر (shab bekheyr)', how='حال شما چطور است؟ (hâl-e shomâ chetor ast?)', love='دوستت دارم (dustet dâram)',
                 welcome='خوش آمدید (khosh âmadid)', water='آب (âb)', friend='دوست (dust)', cat='گربه (gorbe)', dog='سگ (sag)',
                 birthday='تولدت مبارک (tavallodet mobârak)'),
    'hindi': L(hello='नमस्ते (namaste)', bye='अलविदा (alvida)', thanks='धन्यवाद (dhanyavaad)', please='कृपया (kripaya)',
               yes='हाँ (haan)', no='नहीं (nahin)', sorry='माफ़ कीजिए (maaf kijiye)', morning='सुप्रभात (suprabhaat)',
               night='शुभ रात्रि (shubh raatri)', how='आप कैसे हैं? (aap kaise hain?)',
               love='मैं तुमसे प्यार करता / करती हूँ (main tumse pyaar karta / karti hoon)', welcome='स्वागत है (swaagat hai)',
               water='पानी (paani)', friend='दोस्त (dost)', cat='बिल्ली (billi)', dog='कुत्ता (kutta)',
               birthday='जन्मदिन मुबारक (janmadin mubaarak)', luck='शुभकामनाएँ (shubhkaamnaayen)'),
    'urdu': L(hello='السلام علیکم (assalam-o-alaikum)', bye='خدا حافظ (khuda hafiz)', thanks='شکریہ (shukriya)',
              please='براہ مہربانی (barah-e-meharbani)', yes='جی ہاں (ji haan)', no='نہیں (nahin)', sorry='معاف کیجیے (maaf kijiye)',
              how='آپ کیسے ہیں؟ (aap kaise hain?)', love='میں تم سے پیار کرتا ہوں (main tum se pyaar karta hoon)',
              welcome='خوش آمدید (khush aamdeed)', water='پانی (paani)', friend='دوست (dost)', cat='بلی (billi)', dog='کتا (kutta)',
              birthday='سالگرہ مبارک (saalgirah mubarak)'),
    'bengali': L(hello='নমস্কার (nomoshkar)', bye='বিদায় (biday)', thanks='ধন্যবাদ (dhonnobad)', please='দয়া করে (doya kore)',
                 yes='হ্যাঁ (hyan)', no='না (na)', sorry='দুঃখিত (dukkhito)', how='কেমন আছেন? (kemon achhen?)',
                 love='আমি তোমাকে ভালোবাসি (ami tomake bhalobashi)', welcome='স্বাগতম (shagotom)', water='জল / পানি (jol / pani)',
                 friend='বন্ধু (bondhu)', cat='বিড়াল (biral)', dog='কুকুর (kukur)', birthday='শুভ জন্মদিন (shubho jonmodin)'),
    'punjabi': L(hello='ਸਤ ਸ੍ਰੀ ਅਕਾਲ (sat sri akal)', bye='ਅਲਵਿਦਾ (alvida)', thanks='ਧੰਨਵਾਦ (dhannvaad)', please='ਕਿਰਪਾ ਕਰਕੇ (kirpa karke)',
                 yes='ਹਾਂ (haan)', no='ਨਹੀਂ (nahin)', sorry='ਮਾਫ਼ ਕਰਨਾ (maaf karna)', how='ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ? (tusi kive ho?)',
                 love='ਮੈਂ ਤੈਨੂੰ ਪਿਆਰ ਕਰਦਾ ਹਾਂ (main tainu pyaar karda haan)', welcome='ਜੀ ਆਇਆਂ ਨੂੰ (ji aayan nu)', water='ਪਾਣੀ (paani)',
                 friend='ਦੋਸਤ (dost)'),
    'marathi': L(hello='नमस्कार (namaskar)', bye='पुन्हा भेटू (punha bhetu)', thanks='धन्यवाद (dhanyavaad)', please='कृपया (kripaya)',
                 yes='हो (ho)', no='नाही (nahi)', sorry='माफ करा (maaf kara)', how='कसे आहात? (kase aahat?)',
                 love='मी तुझ्यावर प्रेम करतो (mi tujhyavar prem karto)', welcome='स्वागत आहे (swagat aahe)', water='पाणी (paani)',
                 friend='मित्र (mitra)'),
    'gujarati': L(hello='નમસ્તે (namaste)', bye='આવજો (aavjo)', thanks='આભાર (aabhaar)', please='કૃપા કરીને (krupa karine)',
                  yes='હા (haa)', no='ના (naa)', sorry='માફ કરશો (maaf karsho)', how='કેમ છો? (kem chho?)',
                  love='હું તને પ્રેમ કરું છું (hun tane prem karun chhun)', welcome='સ્વાગત છે (swagat chhe)', water='પાણી (paani)',
                  friend='મિત્ર (mitra)'),
    'nepali': L(hello='नमस्ते (namaste)', bye='फेरि भेटौंला (pheri bhetaunla)', thanks='धन्यवाद (dhanyabad)', please='कृपया (kripaya)',
                yes='हो (ho)', no='होइन (hoina)', sorry='माफ गर्नुहोस् (maaf garnuhos)', how='तपाईंलाई कस्तो छ? (tapailai kasto chha?)',
                love='म तिमीलाई माया गर्छु (ma timilai maya garchhu)', welcome='स्वागत छ (swagat chha)', water='पानी (pani)',
                friend='साथी (sathi)'),
    'tamil': L(hello='வணக்கம் (vanakkam)', bye='போய் வருகிறேன் (poi varugiren)', thanks='நன்றி (nandri)', please='தயவுசெய்து (thayavuseithu)',
               yes='ஆம் (aam)', no='இல்லை (illai)', sorry='மன்னிக்கவும் (mannikkavum)', morning='காலை வணக்கம் (kaalai vanakkam)',
               how='எப்படி இருக்கிறீர்கள்? (eppadi irukkireergal?)', love='நான் உன்னை காதலிக்கிறேன் (naan unnai kaadhalikkiren)',
               water='தண்ணீர் (thanneer)', friend='நண்பன் (nanban)'),
    'telugu': L(hello='నమస్కారం (namaskaram)', bye='వెళ్ళొస్తాను (vellostanu)', thanks='ధన్యవాదాలు (dhanyavaadaalu)', please='దయచేసి (dayachesi)',
                yes='అవును (avunu)', no='కాదు (kaadu)', sorry='క్షమించండి (kshaminchandi)', how='ఎలా ఉన్నారు? (ela unnaru?)',
                love='నేను నిన్ను ప్రేమిస్తున్నాను (nenu ninnu premistunnanu)', welcome='స్వాగతం (swagatam)', water='నీళ్ళు (neellu)',
                friend='స్నేహితుడు (snehitudu)'),
    'chinese': L(hello='你好 (nǐ hǎo)', bye='再见 (zàijiàn)', thanks='谢谢 (xièxie)', please='请 (qǐng)', yes='是 / 对 (shì / duì)',
                 no='不是 / 不 (bú shì / bù)', sorry='对不起 (duìbuqǐ)', excuse='不好意思 (bù hǎoyìsi)', morning='早上好 (zǎoshang hǎo)',
                 night='晚安 (wǎn\'ān)', how='你好吗？(nǐ hǎo ma?)', love='我爱你 (wǒ ài nǐ)', welcome='欢迎 (huānyíng)', water='水 (shuǐ)',
                 friend='朋友 (péngyou)', cat='猫 (māo)', dog='狗 (gǒu)', cheers='干杯！(gānbēi!)', birthday='生日快乐 (shēngrì kuàilè)',
                 luck='祝你好运 (zhù nǐ hǎo yùn)'),
    'japanese': L(hello='こんにちは (konnichiwa)', bye='さようなら (sayōnara)', thanks='ありがとう (arigatō)', please='お願いします (onegaishimasu)',
                  yes='はい (hai)', no='いいえ (iie)', sorry='ごめんなさい (gomen nasai)', excuse='すみません (sumimasen)',
                  morning='おはようございます (ohayō gozaimasu)', night='おやすみなさい (oyasumi nasai)', how='お元気ですか？(o-genki desu ka?)',
                  love='愛してる (aishiteru)', welcome='ようこそ (yōkoso)', water='水 (mizu)', friend='友達 (tomodachi)', cat='猫 (neko)',
                  dog='犬 (inu)', cheers='乾杯！(kanpai!)', birthday='お誕生日おめでとう (o-tanjōbi omedetō)', luck='頑張って (ganbatte)'),
    'korean': L(hello='안녕하세요 (annyeonghaseyo)', bye='안녕히 가세요 (annyeonghi gaseyo)', thanks='감사합니다 (gamsahamnida)',
                yes='네 (ne)', no='아니요 (aniyo)', sorry='미안합니다 (mianhamnida)', excuse='실례합니다 (sillyehamnida)',
                morning='좋은 아침 (joeun achim)', night='안녕히 주무세요 (annyeonghi jumuseyo)', how='잘 지내세요? (jal jinaeseyo?)',
                love='사랑해요 (saranghaeyo)', welcome='환영합니다 (hwanyeonghamnida)', water='물 (mul)', friend='친구 (chingu)',
                cat='고양이 (goyangi)', dog='개 (gae)', cheers='건배! (geonbae!)', birthday='생일 축하해요 (saengil chukhahaeyo)'),
    'vietnamese': L(hello='xin chào', bye='tạm biệt', thanks='cảm ơn', please='làm ơn', yes='vâng / có', no='không', sorry='xin lỗi',
                    morning='chào buổi sáng', night='chúc ngủ ngon', how='bạn có khỏe không?', love='anh yêu em / em yêu anh',
                    welcome='chào mừng', water='nước', friend='bạn', cat='con mèo', dog='con chó', birthday='chúc mừng sinh nhật'),
    'thai': L(hello='สวัสดี (sawasdee)', bye='ลาก่อน (la gon)', thanks='ขอบคุณ (khop khun)', please='กรุณา (karuna)', yes='ใช่ (chai)',
              no='ไม่ (mai)', sorry='ขอโทษ (kho thot)', night='ราตรีสวัสดิ์ (ratri sawat)', how='สบายดีไหม? (sabai dee mai?)',
              love='ฉันรักคุณ (chan rak khun)', welcome='ยินดีต้อนรับ (yin dee ton rap)', water='น้ำ (nam)', friend='เพื่อน (phuean)',
              cat='แมว (maeo)', dog='หมา (ma)', birthday='สุขสันต์วันเกิด (suk san wan koet)'),
    'indonesian': L(hello='halo', bye='selamat tinggal', thanks='terima kasih', please='tolong / silakan', yes='ya', no='tidak',
                    sorry='maaf', excuse='permisi', morning='selamat pagi', night='selamat malam', how='apa kabar?',
                    love='aku cinta kamu', welcome='selamat datang', water='air', friend='teman', cat='kucing', dog='anjing',
                    birthday='selamat ulang tahun', luck='semoga berhasil'),
    'malay': L(hello='helo', bye='selamat tinggal', thanks='terima kasih', please='tolong / sila', yes='ya', no='tidak', sorry='maaf',
               morning='selamat pagi', night='selamat malam', how='apa khabar?', love='saya cinta awak', welcome='selamat datang',
               water='air', friend='kawan', cat='kucing', dog='anjing', birthday='selamat hari jadi'),
    'filipino': L(hello='kumusta', bye='paalam', thanks='salamat', please='pakiusap', yes='oo', no='hindi', sorry='pasensya na',
                  morning='magandang umaga', night='magandang gabi', how='kumusta ka?', love='mahal kita',
                  welcome='maligayang pagdating', water='tubig', friend='kaibigan', cat='pusa', dog='aso',
                  birthday='maligayang kaarawan'),
    'hawaiian': L(hello='aloha', bye='aloha', thanks='mahalo', yes='ʻae', no='ʻaʻole', love='aloha au iā ʻoe', welcome='e komo mai',
                  water='wai', friend='hoaloha'),
    'maori': L(hello='kia ora', bye='ka kite anō', thanks='kia ora', yes='āe', no='kāo', how='kei te pēhea koe?', welcome='haere mai',
               water='wai', friend='hoa'),
    'swahili': L(hello='jambo / habari', bye='kwaheri', thanks='asante', please='tafadhali', yes='ndiyo', no='hapana', sorry='samahani',
                 morning='habari za asubuhi', night='usiku mwema', how='habari yako?', love='nakupenda', welcome='karibu', water='maji',
                 friend='rafiki', cat='paka', dog='mbwa', birthday='heri ya siku ya kuzaliwa'),
    'amharic': L(hello='ሰላም (selam)', bye='ደህና ሁን (dehna hun)', thanks='አመሰግናለሁ (ameseginalehu)', yes='አዎ (awo)', no='አይ (ay)',
                 sorry='ይቅርታ (yiqirta)', welcome='እንኳን ደህና መጡ (enkwan dehna metu)', water='ውሃ (wiha)', friend='ጓደኛ (gwadegna)'),
    'yoruba': L(hello='báwo ni', bye='ó dàbọ̀', thanks='o ṣeun', yes='bẹ́ẹ̀ni', no='rárá', morning='ẹ káàárọ̀', love='mo nífẹ̀ẹ́ rẹ',
                welcome='ẹ káàbọ̀', water='omi', friend='ọ̀rẹ́'),
    'hausa': L(hello='sannu', bye='sai anjima', thanks='na gode', yes='eh / i', no="a'a", morning='ina kwana', how='yaya kake?',
               welcome='barka da zuwa', water='ruwa', friend='aboki'),
    'zulu': L(hello='sawubona', bye='sala kahle / hamba kahle', thanks='ngiyabonga', please='ngicela', yes='yebo', no='cha',
              sorry='ngiyaxolisa', how='unjani?', love='ngiyakuthanda', welcome='siyakwamukela', water='amanzi', friend='umngane',
              cat='ikati', dog='inja'),
    'afrikaans': L(hello='hallo', bye='totsiens', thanks='dankie', please='asseblief', yes='ja', no='nee', sorry='jammer',
                   morning='goeie môre', night='goeie nag', how='hoe gaan dit?', love='ek is lief vir jou', welcome='welkom',
                   water='water', friend='vriend', cat='kat', dog='hond', birthday='gelukkige verjaarsdag'),
}


def language(name):
    """The table's name for a language the person wrote, or None when it is not covered."""
    key = name.lower().strip()
    key = LANGUAGE_ALIASES.get(key, key)
    return key if key in TABLE else None


def phrase(text):
    key = ' '.join(text.lower().strip(' ?!.,"\'').split())
    key = re.sub(r'^(?:the word|the phrase|saying|say)\s+', '', key)
    key = ALIASES.get(key, key)
    return key if key in PHRASES else None


def forms(value):
    """Every way a stored translation can be written: each alternative, in its own script and romanised."""
    found = set()
    for part in re.split(r'\s+/\s+', re.sub(r'\s*\((.*?)\)', '', value)):
        found.add(part)
    romanised = re.findall(r'\((.*?)\)', value)
    for chunk in romanised:
        for part in re.split(r'\s+/\s+', chunk):
            found.add(part)
    cleaned = {re.sub(r'[!?¡¿？！。.,]+', '', f).strip().lower() for f in found if f.strip()}
    return cleaned | {plain(f) for f in cleaned}


def plain(text):
    """Without accent marks, so "arigato" finds "arigatō"."""
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


REVERSE = {}
for _lang, _table in TABLE.items():
    if _lang == 'english':
        continue
    for _phrase, _value in _table.items():
        for _form in forms(_value):
            REVERSE.setdefault(_form, []).append((_lang, _phrase))


def meaning(word):
    """[(language, english phrase)] for a foreign word or phrase in the table."""
    key = re.sub(r'[!?¡¿？！。.,"\']+', '', word).strip().lower()
    return REVERSE.get(key) or REVERSE.get(plain(key), [])
