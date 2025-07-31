import discord
from discord.ext import commands
import re

class AutoMod(commands.Cog):
    # Corrected the constructor name from 'init' to '__init__'
    def __init__(self, bot):
        self.bot = bot
        self.bad_words = self._get_bad_words_list()

        # Regular expressions to detect Discord invites and general URLs
        self.invite_regex = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/\S+")
        self.url_regex = re.compile(r"https?://\S+|www\.\S+")

    def _get_bad_words_list(self):
        """
        Returns a hardcoded set of all the bad words.
        This replaces the need to fetch them from an external URL.
        """
        word_list = [
            "spooge", "homodumbshit", "betichod", "lauda", "whack off", "teri maa ka bhosra", "drunk", "virgin", 
            "cockmonkey", "b1tch", "horsetoe", "twink", "shemale", "womanizer", "tea bagging", "assfukka", "piss-off", 
            "dheeli choot", "bhandava", "bitchtits", "gender bender", "phukked", "laudu", "bollocks", "behanchod", 
            "grope", "minger", "fagot", "fagging", "fcuk", "jackass", "f_u_c_k", "laude", "fist fuck", "kum", 
            "callgirl", "turd", "analplug", "tosser", "twunter", "swinger", "vajayjay", "ejaculatings", "ballsack", 
            "circlejerk", "pervert", "fux0r", "bumps", "fuckless", "asshat", "microphallus", "mother fuckers", 
            "mthrfckr", "lund mera muh tera", "najayaz paidaish", "sala", "gandit", "basterddouch", "sali", 
            "child-fucker", "pedophiliac", "minge", "chutiyapa", "suwar ki aulad", "ejaculating", "scrotum", 
            "mere fudi kha ley", "doping", "tit wank", "choot ka baal", "bangbros", "mothafuck", "kunilingus", 
            "dick shy", "dickheads", "mera gota moo may lay", "tit", "knobend", "tush", "randhwa", "maadar", 
            "fuckass", "vaginal", "pollock", "son of a bitch", "tw4t", "bhenchod", "bakchod", "gandoo", 
            "shaved beaver", "girls gone wild", "group sex", "queaf", "jhat lahergaya", "cumtart", "fingering", 
            "shitheads", "cockmaster", "cockface", "knob end", "g-spot", "ejaculation", "sexy", "kafir", 
            "bhai chhod", "faggitt", "muff puff", "c-0-c-k", "chinc", "randi baj", "gaandmasti", "sexo", "kock", 
            "ejaculated", "rundi ka bacha", "menses", "porno", "kumming", "ejaculates", "pee", "donkeypunch", 
            "bums", "randi ka bacha", "brunette action", "fudgepacker", "shitblimp", "faggs", "anal", "fuckwitt", 
            "erotic", "v14gra", "chut maarli", "donkeyribber", "fuck", "cumdumpster", "queef", "bhosadika", 
            "maa ke lavde", "bhosadike", "ball sucking", "clitoris", "beti chod", "bhosadiki", "beef curtain", 
            "f u c k", "teri maa ki sukhi bhos", "kanjar", "choade", "piece of shit", "pimp", "m-fucking", "c0ck", 
            "xxx", "chutadd", "cockknoker", "strip club", "smegma", "cok", "bakrichod", "dopping", 
            "extra marital", "fuckers", "rim jobs", "marijuana", "muthafuckker", "cockmuncher", "pig", "tubgirl", 
            "teri ma ko kutta chode", "bhosadaaa", "jerk0ff", "kutiya", "heroin", "son-of-a-bitch", "fondle", 
            "gandi fuddi ki gandi auladd", "randi ke beej", "loins", "fuct", "numbnuts", "bugger", 
            "teri chute mai chuglee", "bitchy", "chutiya", "fuckheads", "lovemaking", "hentai", "vulgar", 
            "chutiye", "bi*ch", "cunnie", "bhaichod", "doggin", "talk dirty", "tere maa ki choot", "fuck yo mama", 
            "shit ass", "shitface", "wh0reface", "diligaf", "menstruate", "golden shower", "fuckwit", "randi baaz", 
            "nipple", "auto erotic", "assfucker", "pubes", "asslicker", "fatey condom kay natije", "lezbos", 
            "nigg3r", "teri behen ka bhosda faadu", "jerkoff", "mangachinamun", "ball gravy", "lez", "kutte", 
            "fuck you", "cockbite", "poopchute", "jhavadya", "chudpagal", "muthafecker", "kutta", "wank", 
            "knobjokey", "lundoos", "huge fat", "bdsm", "urinal", "rusty trombone", "fuckbag", "clits", "butt", 
            "randi ka choda", "throating", "nudity", "gtfo", "fuks", "poop chute", "dumass", "scissoring", 
            "teri gand mai ghadhe ka lund", "shagger", "lunnd", "assmuncher", "lund pe thand hai", "ullu", 
            "twatty", "bellend", "buttfucker", "nigg4h", "bhayee chod", "c0cksucker", "arse", "bhosdiwale", 
            "rim job", "bur ki chatani", "chodra", "gaand chaat mera", "booobs", "bukkake", "quim", "fuckedup", 
            "bhand khau", "muth maar", "pubis", "chodoo", "bhosadaa", "jerk off", "coonnass", "dirty talks", 
            "maadarbhagat", "fagfucker", "pimpis", "shitass", "pisspig", "fistfuckers", "urethra play", 
            "bhonsri-waalaa", "pubic", "teri maa ki chut", "big black", "asshopper", "c.u.n.t", "mothafucka", 
            "bhains ki aulad", "m45terbate", "ganja", "bust a load", "hooker", "shaggin", "parichod", "peepee", 
            "assbanged", "assbanger", "dog style", "mothafucks", "masterbat", "tharaki", "shitty", "bunghole", 
            "fuck-ass", "bestiality", "gooch", "sh*t", "jerked", "tera gittha", "orgasm", "assmunch", "ecchi", 
            "choo-tia", "teri maa ka bhosada", "assbite", "cockburger", "fuckwad", "fannybandit", "d1ldo", 
            "homoerotic", "muffdiver", "slaves", "fucknugget", "butt plug", "lund pe chad ja", "central prision", 
            "ham flap", "knobead", "shitbag", "fistfucking", "chudai khanaa", "fingerfuckers", "jagoff", 
            "maa ki choot", "kutte ki olad", "asshole", "glans", "hoar", "maadarchod", "wh0re", "suckass", 
            "whorehopper", "chut ke makkhan", "fisty", "cocksmoke", "ball licking", "pen1s", "fecal", "gaand", 
            "douche waffle", "strappado", "coochy", "bakwash", "dickish", "slutkiss", "clit", "maternal copulator", 
            "lesbos", "cockmongruel", "harami", "pusse", "tits", "titt", "pussi", "amma ki chut", "cyberfuck", 
            "phonesex", "gloryhole", "a\ss", "lund chuse", "pussy", "haraam jaada", "chootiya", "choochii", 
            "f@ggot", "titi", "chootiye", "raging boner", "chamche", "anus", "saali randi", 
            "fuckingshitmotherfucker", "raandichya", "kinkster", "reverse cowgirl", "spread legs", "cockmunch", 
            "mothafuckin", "lsd", "gandu", "undressing", "fucknut", "condom", "teri maa ke bable", "tongue in a", 
            "hoer", "cockeye", "clitty", "cuntlick", "zoophilia", "d1ld0", "buttplug", "skullfuck", 
            "gaand maar bhen chod", "pissflaps", "steamy", "bahen chod", "jhaat ka bhaaji", "haramjaada", "c.o.c.k", 
            "teri maa ki choot", "cumming", "dawgie-style", "dookie", "zoophile", "beeyotch", "muthrfucking", 
            "booby", "boobs", "nob jokey", "crabs", "camwhore", "nut sack", "slutbag", "tramp", "cunts", "humped", 
            "gaandu ganesh", "boobe", "gaandu", "bhains ki aankh", "dickmilk", "fuckhead", "maa ke bable", "milf", 
            "chodu bhagat", "date rape", "shittings", "hijda", "big knockers", "cumstain", "lesbian", 
            "cockknocker", "teri ma randi", "cockass", "jhant ke baal", "cockfucker", "phallic", "hot carl", 
            "tushy", "bahanchod", "penispuffer", "gaand ka makhan", "skag", "chick with a dick", "asswipe", 
            "soower ke bachche", "terd", "shitbrains", "c\.0\.c\.k", "jhaant ke pissu", "mother fucker", 
            "escort services", "bang (one's) box", "yellow showers", "asssucker", "teri ma ki choot me bara sa land", 
            "cumdump", "sinak se paida hua", "yiffy", "cuntmama", "gonads", "ejaculate", "shitdick", "tittyfucker", 
            "knobjocky", "dickhole", "polesmoker", "chodika", "maal", "playboy", "ball gag", "piss pig", 
            "bursungha", "hom0", "cum dumpster", "goatse", "wetback", "cyberfucking", "doggiestyle", "cunny", 
            "fanyy", "nude", "bollox", "sodomize", "pegging", "masterbation", "cornhole", "b00bs", "cuntlicker", 
            "dicksucking", "whacked off", "whore", "clit licker", "chod", "homo", "schlong", "ejakulate", 
            "behanchood", "cockshit", "madar chod", "butt-pirate", "ghay", "spank", "two fingers", "babe", 
            "l3i\+ch", "blumpkin", "cocksuck", "jack off", "coochie", "fudge-packer", "chudaker", "goldenshower", 
            "s€x", "cooter", "phuck", "masterbating", "twunt", "boiolas", "douchebags", "p.u.s.s.y", "fvck", 
            "hardcoresex", "bahen ke takke", "bhosadi ke", "choot k pakode", "dog-fucker", "kaala lund", "b17ch", 
            "gaand mara", "fuddu", "uterus", "cha cha chod", "masterb8", "choot ke baal", "mothafucking", "chhed", 
            "femdom", "kuthri", "chutiywpa", "bareback", "beef curtains", "fistfuck", "bloody-fuck", "mthrfucking", 
            "cockjockey", "c-o-c-k", "assclown", "chudai khana", "mader chod", "teri maa ka boba chusu", 
            "behn ke lund", "feck", "fagtard", "rectal", "hore", "cumshot", "cocksucks", "strap on", "tart", 
            "ass holes", "pataka", "lundh", "clitty litter", "chudasi", "ghey", "lodu", "middle finger", "tard", 
            "bhen ke lode maa chuda", "choot ki jhilli", "nutsack", "asswhole", "loda", "genitalia", "mutth", 
            "hot chick", "female squirting", "klan", "choot marani ka", "incest", "batty boy", "jizz bag", 
            "gaandam swaha", "muttha", "sultry women", "cyberfucked", "rimming", "boners", "fuckoff", "autoerotic", 
            "strip", "cuntrag", "cunt", "cumslut", "cyberfucker", "maal chhodna", "shittiest", "blow your load", 
            "ass hat", "vagina", "eat my ass", "lund\xa0", "chodela", "biatch", "fingerfucking", "creampie", "cums", 
            "fuckbrain", "twat", "cocaine", "taste my", "sleep with", "randibaaz", "gaand marau", "wh0ref@ce", 
            "gandi chut mein sadta hua ganda kida", "fanny", "cumguzzler", "nigga", "dick head", "loin", 
            "wrapping men", "aand mat kaha", "douchewaffle", "cunthunter", "chut", "cunthole", "titty", "negro", 
            "two girls one cup", "fuckboy", "randi ka larka", "chodes", "haram zaadaa", "breast", "kuttiya", 
            "cocksuka", "phuks", "ullu ke patha", "gayfuckist", "land ka bheja", "saala", "madar jaat", 
            "cum freak", "bullshit", "ullu ke pathe", "saale", "saali", "cunnilingus", "bang", 
            "chod ke bal ka kida", "punkass", "cyberfuckers", "cunilingus", "rundi ki bachi", "doggy-style", 
            "mutherfucker", "tities", "masterbate", "haraamzaada", "rundi", "bloodclaat", "whorehouse", 
            "chaman chutiya", "bimbos", "clunge", "chakke", "meth", "stiffy", "one guy one jar", "maderchod", 
            "fack", "bhadwagiri", "fuckwhit", "a\$\$h0le", "one cup two girls", "haraami", "womb", "masterbat3", 
            "booty", "bewb", "beatch", "babes", "mooh mein le", "shit fucker", "uzi", "kutte ka aulad", "f\\*king", 
            "penial", "lowde ka bal", "lavde ka baal", "maadher chod", "najayaz", "abortion", "assfuck", 
            "beaver lips", "cumshots", "muth mar", "hijra", "kukarchod", "mothafuckers", "child abuse", 
            "me in relationship", "teri gaand mein haathi ka lund", "asslick", "dickbeaters", "pedobear", "sutta", 
            "sucked", "carnal", "cmen", "chutiyaa", "dickripper", "x-rated", "stfu", "pissoff", "fags", "tatte", 
            "a\s", "bhenkelode", "tatti", "dickwad", "cleveland steamer", "taking the piss", "whoar", "assbangs", 
            "hymen", "moron", "goatcx", "dlck", "rapey", "twinky", "fagbag", "felcher", "pornos", "fagg", "raped", 
            "chutiyap", "gonad", "raper", "masochist", "fudge packer", "rapes", "kutte ki jat", "cock snot", 
            "bum boy", "shitter", "penile", "unclefucker", "f@g", "ass hole", "blow job", 
            "blonde on blonde action", "mome ka pasina chat", "vag", "bhoot-nee ka", "r#ped", "bhen chhod", "doosh", 
            "corksucker", "dickdipper", "faig", "slutdumper", "rectum", "bawdy", "nipples", "lavde ke bal", 
            "pedophilia", "perversion", "t1tt1e5", "cocksukka", "penisbanger", "fellatio", "bhen ke lode", 
            "big breasts", "cocksmoker", "bhosad", "bullish", "mother humper", "sperm", "fannyflaps", "genitals", 
            "va-j-j", "muther", "hand job", "blonde action", "kyke", "dickwod", "honkey", "twinkie", "seduced", 
            "upskirt", "bhosdi", "glory hole", "kummer", "whorealicious", "bhosdu", "lodu chand", "transsexual", 
            "fecker", "bulldyke", "cyberfuc", "choot ka paani", "jackasses", "lardass", "assbandit", 
            "brotherfucker", "najayaz aulaad", "jackoff", "deepthroat", "fcuker", "dumbasses", 
            "moth\\r fu\\*ers", "bosom", "tribadism", "penisfucker", "seducing", "son of a whore", 
            "jhant chaatu", "rectus", "a55hole", "dickweasel", "behenchod", "maa ki chut", "dickmonger", 
            "gand mein louda", "l3itch", "mai chod", "barenaked", "kutta kamina", "jism", "w00se", "wiseass", 
            "mutha", "bhaand me jaao", "footjob", "dickbag", "foot fetish", "seduce", "poontang", 
            "randi ke bacche", "gspot", "fucks", "blowjob", "lezbian", "fartknocker", "teabagging", "fuckr", 
            "corp whore", "fart", "poop", "h0m0", "dykes", "badwa", "fucka", "saali kuttie", "banger", "whoring", 
            "gaand ka khadda", "vjayjay", "teri ma ki chudaye bandar se hui", "fistfucks", "strapon", 
            "cockwaffle", "raping", "analsex", "assholes", "towelhead", "hobag", "xnxx", "porn", "bhosadi", 
            "nobjocky", "assho!e", "fukwit", "bhosada", "h0mo", "knobhead", "splooge", "beastiality", 
            "bloody fucker", "s-l-u-t", "mthrfucker", "jackhole", "nigger", "doochbag", "ma5terb8", "maa chuda", 
            "wanker", "gaa#d", "thharki", "teri ma ki", "fuckin", "queero", "dickweed", "gaysex", "queers", 
            "raand ka jamai", "mothafuckings", "motherfuckka", "j3rk0ff", "shitty people", "dyke", "bhootni ke", 
            "fucktards", "kunt", "zubb", "jizm", "titfuck", "sexworker", "shitbreath", "mtherfucker", "jizz", 
            "fuck off", "bhadavya", "busty", "dumbfuck", "chup ke chut hai", "saale lm", "shite", "thundercunt", 
            "butthole", "muthafuckaz", "kums", "areole", "asswad", "areola", "gangbang", "motherfuckin", 
            "threesome", "baklund", "bsdk", "cocks", "semen", "laude ke baal", "fucker", "smutty", "chodubhagat", 
            "fatay huay lundtopi ka result", "rapist", "f.u.c.k", "tittie5", "chor company", "scum", "doggystyle", 
            "chincs", "niggas", "dick sucker", "niggah", "suck*d", "shiznit", "chuuttiyyaa", "buceta", "niggaz", 
            "fucked", "sex_story", "eat a dick", "c##t", "kaminey", "chesticle", "shirt lifter", "wet back", 
            "poopuncher", "lode jesi shakal ke", "gangbanged", "motherfucker", "sexual encounter", "shag", 
            "booblay", "pagal", "titties", "kinbaku", "dumbass", "dicktickler", "deep throat", "ahole", 
            "lezbians", "queerhole", "bitch tit", "peckerhead", "kutte ki aulad", "cum chugger", "tub girl", 
            "motherfucked", "xrated", "bitchass", "chipkali ki choot ke paseene", "n1gga", "cunt-struck", 
            "titwank", "clitface", "simen", "cocknose", "lund khajoor", "knobed", "shithead", "arsehole", 
            "venus mound", "viagra", "d1ck", "sodomy", "s#exual harrasment", "ball sack", "booooobs", 
            "fingerfucks", "pussy palace", "bhandve", "fuck-bitch", "cockblock", "faggots", "ovary", 
            "teri maa ki", "apeshit", "kissess", "crackwhore", "wench", "labia", "motherfucking", 
            "chut ka maindak", "bigtits", "fellate", "felching", "naked", "fucktoy", "orgasim", 
            "lund ke pasine", "balatkar", "faggot", "lezza lesbo", "pisser", "dickwhipper", "pisses", "gandmasti", 
            "mof0", "pole smoker", "sex-worker", "fcuking", "doggie style", "meri ghand ka baal", "cummin", 
            "cuntbag", "handjob", "teri maa ke bhosade ke baal", "shaved pussy", "choot", "suar ki aulad", 
            "breasts", "faigt", "fcker", "nads", "shitbagger", "gaytard", "rascalas", "b*llsh\ts", "lesbians", 
            "cock sucker", "potty", "lesbo", "teri phuphi ki choot mein", "rimjaw", "pthc", "female molestation", 
            "t1t", "mofo", "douchey", "kraut", "sshole", "chinky", "fuckme", "pissin", "bhosadchod", "cocksmith", 
            "saala kutta", "chinki", "gigolo", "assbag", "ing ge pan di kut teh", "slut bucket", "rascals", 
            "orgasmic", "orgasms", "bloody fuck", "kutte ke tatte", "erect", "b!tch", "pedophile", "assfaces", 
            "beardedclam", "tere maa ka bur", "asshead", "two fingers with tongue", "suar", 
            "sab ka lund teri ma ki chut mein", "asscock", "cummer", "shit hole", "cocklump", "dry hump", 
            "gaandufad", "golliwog", "lolita", "sluts", "booty call", "nigaboo", "phuking", "jerk-off", "bimbo", 
            "assmonkey", "fukwhit", "cumjockey", "dickflipper", "bhadwa", "camgirl", "ass fuck", "penis", 
            "dolcett", "kunja", "jesussucks", "assho1e", "rimjob", "ballbag", "female escort", "wazoo", 
            "fukking", "gaydo", "girl on top", "blowjobs", "bahen ke laude", "bhadva", "chhola phudakna", 
            "brassiere", "pantie", "bhadve", "ass", "kamina", "cockmongler", "kutha sala", "kamine", "choodu", 
            "slut", "kamini", "bhosdi k", "lund k laddu", "chudan chudai", "foad", "mutherfucking", "wankjob", 
            "lund choos", "phuked", "madarchod", "gaand ke dhakan", "t1tties", "p%\\$sy", "hawas", "khaini", 
            "bhosdee kay", "nob", "cumbubble", "boob", "floozy", "faggit", "ponyplay", "hutiya", "nsfw images", 
            "shitfuck", "yaoi", "genital", "pissers", "seamen", "lavadya", "mo-fo", "bootlicking", "hottie", 
            "v1gra", "splooge moose", "fuckup", "nobjokey", "teri maa ki chute", "escorts service", "n1gger", 
            "lundure", "fag", "ball kicking", "f-u-c-k", "shitcanned", "prostitute", "jiz", "nymphomania", 
            "cokmuncher", "gaybob", "d0uche", "twatwaffle", "assmaster", "fagged", "backar chodu", "beotch", 
            "fagots", "cuntass", "muthafucker", "madarchod ke aulaad", "bastard", "hump", "kameeni", "vporn", 
            "gay sex", "chuut ke baal", "cum guzzler", "lezzie", "fck", "voyeur", "assshole", "buttcheeks", 
            "gaylord", "cockhead", "d0uch3", "kameena", "azz", "cervix", "kondums", "fuck wad", "jhantu", 
            "fukkin", "suvar chod", "dickzipper", "sarele lund", "pussies", "f@gg0t", "jizzed", "cuntface", 
            "bitches", "pussy fart", "fuck trophy", "orgasims", "punany", "dick", "fucknutt", "asscracker", 
            "masturbate", "bhaynchod", "assmucus", "bumchod", "fisting", "bloodyfucker", "cawk", "weenie", 
            "fuckface", "cock-sucker", "haram ki bacche", "haramjada", "fistfuckings", "callgirls", "madar", 
            "shitspitter", "whoralicious", "bitched", "fistfucker", "bhosdoo", "boner", "boned", "lube", "chinaal", 
            "bitcher", "tatti ander lele", "bitchers", "camslut", "dickfuck", "fistfucked", "fu*c*k\ers", 
            "sluttish", "c-u-n-t", "p0rn", "bung hole", "duche", "luhnd", "gassy ass", "punanny", "chuddo", 
            "eunuch", "bhosad chod", "fingerfuck", "undies", "fukker", "dickfucker", "stupid superiors", 
            "punani", "vibrator", "tu tera maa ka lauda", "goregasm", "fleshflute", "testicle", "kiss", "lezbo", 
            "choot ke bhoot", "donkey punch", "fucktwat", "assgoblin", "hussy", "rand ki moot", "cocksuckers", 
            "ass munch", "cunillingus", "gand", "boobies", "masturbation", "shitstain", "phone sex", 
            "coprophilia", "cahone", "bhadwachod", "fuck puppet", "teri ma bahar chud rahi he", "coksucka", 
            "mothafucker", "bbw", "bulle ke baal", "clitfuck", "mothafucked", "erotism", "whor", "brothel", 
            "fingerfucked", "looney", "jhaat", "rape", "horse toe", "willy", "shitting", "dumbcunt", 
            "douchebag", "niggers", "frotting", "goo girl", "dogging", "cnut", "sex", "weewee", "zibbi", 
            "topless", "doggy style", "mera mume le", "panties", "bihari", 
            "teri maa ki choot me kutte ka lavda", "fuck-tard", "fxck", "fuckbutter", "chut ke baal", "poonani", 
            "prickteaser", "anilingus", "horniest", "fucktart", "cl1t", "lode ke baal", "nympho", "mothafuckaz", 
            "mothafuckas", "ass-hat", "fucktard", "male squirting", "dike", "weiner", "behen-chod", 
            "baap ke lavde", "faggotcock", "wiseasses", "mahder chod", "dicksipper", "dirty sanchez", 
            "teri gaand mera lauda", "lundfakir", "pillowbiter", "futanari", "lund", "maa-cho", "goodpoop", 
            "aandu", "whores", "tere baap ki gaand", "whacking off", "charas", "panooch", "whorebag", "tittywank", 
            "bhai chod", "whored", "kuthta buraanahe kandaa nahi pattaahe", "ass-fucker", "buttmunch", 
            "need the dick", "slut devil", "shited", "gaand fati ke badve", "masturbating", "cuntlicking", 
            "maa ki aankh", "brown showers", "muff diver", "double penetration", "fuck buttons", "urophilia", 
            "humping", "patakha", "gangbangs", "m0f0", "niglet", "wtf", "chut mari ke", "fu\ck", "boooobs", 
            "fubar", "f u c k e r", "chut ke dhakkan", "phatele nirodh ke natije", "pussys", "xhamster", 
            "dick-sneeze", "pube", "fuckings", "rascal", "fuckhole", "gays", "haraam zaada", "lund ka shorba", 
            "moo may lay mera", "buttmuch", "jhatoo", "pissing", "teri gand mera lauda", "bastards", "m0fo", 
            "bastardo", "cock pocket", "cocksniffer", "jhaat ke baal", "fuc", "master-bate", "fuk", "poonany", 
            "kutte ka beej", "felch", "style doggy", "fuq", "motherfuckings", "ghassad", "fux", "bakchodi", 
            "haramzade", "dicksucker", "bhosadii", "clusterfuck", "asswipes", "bi\+ch", "lust", "pansy", 
            "tittyfuck", "assface", "nucking futs", "shitfull", "gaandfat", "chooche", "choochi", "chootia", "bod", 
            "panty", "fingerfucker", "randwa", "assbang", "chut ke pasine mein talay huye bhajiye", "camel toe", 
            "nobhead", "bhadwe ki nasal", "f\\k off", "gayfuck", "renob", "eat hair pie", "kaali kutti", 
            "bhosdike", "dumb ass", "shit kissing lips", "bumblefuck", "pigfucker", "motherfuck", 
            "behchodini ka bacha", "jhant", "fukkers", "twathead", "boot licking", "female escorts", "testical", 
            "cock", "stripper", "hoare", "motherfucka", "cocksucked", "bootie", "behen ke laude", "blow me", 
            "chutad", "fisted", "intercourse", "fucking", "blow jobs", "saali kutti", "bra", "gayass", "chutan", 
            "dickjuice", "pornofreak", "cocknugget", "douch3", "pornography", "randi rona", "tharki", 
            "motherfucks", "twatlips", "orgy", "fuckstick", "lusty", "lavde ke baal", "kinky", "gashti", 
            "teri bhosri mein aag", "bumclat", "kuttae", "fuckmeat", "coital", "tittiefucker", "doggie-style", 
            "stoned", "vulva", "tranny", "fuckersucker", "pecker", "gang bang", "f0ck", 
            "teri gaand me danda", "bunny fucker", "shitings", "mother f\\er", "dickhead", "dominatrix", 
            "shithole", "paedophile", "molest", "cocksucker", "cunt hair", "bum", "gang-bang", "urine", 
            "big tits", "testis", "ovum", "randi", "maa ki", "orgies", "shitcunt", "lick", "lundtopi", "kawk", 
            "bootee", "fannyfucker", "madarc##d", "mcfagget", "phuq", "fingerbang", "lusting", "toota hua lund", 
            "ghondoo", "phuk", "horny", "muffdiving", "knobbing", "balatkaar", "booooooobs", "shagging", 
            "cockholster", "fcku", "gaywad", "gae", "lund fakeer", "fckr", "kondum", "gasti", "gay", "dildo", 
            "vanchoooooooodddddddddd", "choot k bhoot", "guido", "coke", "phukking", "chi-chi man", 
            "son of a motherless goat", "sumofabiatch", "d\\*k heads", "dick hole", "feltch", "fuker", 
            "tatte masalna", "behen chod", "beaver cleaver", "teets", "fanny bandit", "shitfaced", "testee", 
            "fuck hole", "analprobe", "chode", "seks", "chuche", "puss", "dick-ish", "coprolagnia", "chuchi", 
            "menstruation", "chodu", "ghasti", "whoreface", "madarchoth", "jiggerboo", "butt fuck", "hotsex", 
            "chutia", "raand", "sexual", "shiting", "bampot", "anti hindu culture", "ass licker", "fatass", 
            "maa ka bhosda", "cocain", "tharak", "climax", "bosomy", "bastinado", "gey", "asses", "coon", 
            "lund choosu", "jerkass", "choot ka pissu", "testes", "bhandwe ki aulad", "raunch", "black cock", 
            "cuntsicle", "giant cock", "seductive", "cocksucking", "b@lls", "c\.0ck", "hawas ke pujari", 
            "kinky stuff", "male escorts", "buttfucka", "ma5terbate", "maa ke bhadwe", "bitch", "chod bhangra", 
            "twats", "escort service", "feltcher", "bosadike", "chopre he randi", "douche-fag", "kwif", "flange", 
            "assh0le", "lavda", "masterbations", "balls", "choot marni ka", "shitters", "cameltoe", "wh0r3f@ce", 
            "missionary position", "ovums", "tuzya aaichi kanda puchi", "camina", "booger", "gaand mein kida", 
            "weed", "camel toes", "chuttiya", "teri jaat ka", "foreskin", "douche", "jack-off", 
            "escorts services", "choad", "cuntslut", "clitorus", "sust lund ki padaish", "pussylicking", 
            "pussypounder", "fuckbutt", "call girls", "motherfuckers", "lavdi", "daterape", "buttfuck", 
            "lavde", "dildos"
        ]
        # Return a set of lowercase words for efficient 'in' checking
        return set(word.lower() for word in word_list)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages sent by bots, including ourself
        if message.author.bot:
            return

        # Convert message content to lowercase for case-insensitive matching
        content = message.content.lower()

        # 1. Check for bad words
        if any(bad_word in content for bad_word in self.bad_words):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, watch your language! 🤫", delete_after=5)
            except discord.Forbidden:
                print(f"Could not delete message. Missing Permissions in #{message.channel.name}.")
            except discord.NotFound:
                pass # Message was already deleted
            return # Stop processing after finding a violation

        # 2. Check for Discord invites
        if self.invite_regex.search(content):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, Discord invites are not allowed! 🚫", delete_after=5)
            except discord.Forbidden:
                print(f"Could not delete message. Missing Permissions in #{message.channel.name}.")
            except discord.NotFound:
                pass
            return

        # 3. Check for any other links/URLs
        if self.url_regex.search(content):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, posting links is not allowed! 🔗", delete_after=5)
            except discord.Forbidden:
                print(f"Could not delete message. Missing Permissions in #{message.channel.name}.")
            except discord.NotFound:
                pass
            return

# Standard setup function to load the cog
async def setup(bot):
    await bot.add_cog(AutoMod(bot))

