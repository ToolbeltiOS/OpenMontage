# easter-island — act 4 provenance repair

2026-10-26. Ledger only: the script and the delivered film are unchanged, by instruction.

## Why

The delivered script's act 4 cites claim ids c32 and c46-c58. The ledger held fifteen data points and carried no `id` field at all, so none of those ids resolved under any reading. Every factual sentence in the act was unattributed in a way that looked like attribution.

## Counts

| verdict | sentences |
|---|---|
| CONFIRMED | 23 |
| IMPRECISE | 3 |
| UNSUPPORTED | 0 |

26 act-4 sentences researched. The two remaining uncovered sentences in the film are the outro sign-off, which make no claim about the world — see below.

## What this does not fix

The script still cites c32 and c46-c58, and none of those ids exist: the repair gives the act's claims sources, it does not make the script's citations resolve, and it is numbered so that it cannot accidentally appear to. Making the fact gate pass on this film would mean editing script.json's source_ref, which was forbidden. The mapping from sentence to repair id is in `repairs_sentence` on each entry.

## IMPRECISE — the script and the source differ

### r01

**Script:** “Fifty-three low stone houses at a village called Orongo, sod-covered and windowless, with doors you would have to crawl through, sitting on the rim of a crater two hundred and fifty metres above the sea.”

**Source** (Orongo — Wikipedia; The Archaeologist, 'Orongo Village'): Orongo is a ceremonial village of 53 low, sod-covered, windowless stone houses on the rim of the Rano Kau caldera; the doorways are about 50 cm high and must be crawled through.

**Difference:** The 53 houses, the sod-covered windowless construction and the crawl-through doorway (~50 cm) all check out verbatim. THE ELEVATION DOES NOT. Sources put Orongo at roughly 290-300 m (Lonely Planet ~300 m; Komoot 290 m) with the Rano Kau summit at 324 m. 250 m appears only in a Wikipedia photo caption and in a Chilean travel page describing a 250-metre STRIP of land, not an altitude. The script's own next sentence is also inconsistent with it: a village 250 m above the sea cannot have a 300 m cliff below it.

<https://en.wikipedia.org/wiki/Orongo>

### r08

**Script:** “His clan took the exclusive right to every egg and every fledgling on those islets for a year, and he himself went into seclusion for a year, under a restriction lasting five months.”

**Source** (Tangata manu — Wikipedia): The new tangata manu's clan held sole rights to collect that season's wild bird eggs and fledglings from Motu Nui; he entered seclusion for a year and was tapu for five months.

**Difference:** The seclusion (a year) and the restriction (five months) are exact. THE EGG RIGHTS ARE NOT: the source gives the clan 'that season's' eggs and fledglings, not a year's, and names Motu Nui alone rather than 'those islets'. The script appears to have carried the one-year term of the TITLE across to the egg rights, which are seasonal.

<https://en.wikipedia.org/wiki/Tangata_manu>

### r12

**Script:** “Two and a half metres, four point two tonnes, cut from dark flow lava rather than the compressed ash everything else came from.”

**Source** (Hoa Hakananai'a — Wikipedia): Hoa Hakananai'a is 2.42 m high, weighs 4.2 tonnes, and is made from a block of dark grey-brown flow lava; most moai are a reddish tuff (compressed volcanic ash).

**Difference:** The weight and the rock type are exact, and 'dark flow lava' is the source's own phrase. THE HEIGHT IS ROUNDED THE WRONG WAY: the statue is 2.42 m, which rounds to two point four, not 'two and a half'. An 8 cm overstatement.

<https://en.wikipedia.org/wiki/Hoa_Hakananai%27a>

## UNSUPPORTED

None. Every factual claim in act 4 was traced to a source.

## The two sentences that are not world claims

These are the film's sign-off and are counted by the gate because they contain numerals. They assert nothing about Easter Island and no source applies:

- “Four open files, and we closed one of them tonight.”
- “If you want the other three followed properly, a like and a subscribe is how that happens.”

Run #1's two uncovered sentences are the same construction. If the gate should exempt a sign-off, that is a whitelist decision and it is the owner's, not the gate's.

## Every sentence, with its verdict

| id | verdict | sentence |
|---|---|---|
| r01 | IMPRECISE | Fifty-three low stone houses at a village called Orongo, sod-covered and windowless, with doors you would have to crawl through, sitting on the rim of |
| r02 | CONFIRMED | Below them the cliff drops three hundred metres into the water. |
| r03 | CONFIRMED | The crater behind them is almost a mile across and holds one of only three natural bodies of fresh water anywhere on the island. |
| r04 | CONFIRMED | Each man competing appointed someone else to do the swimming — a man of lesser status, who went out on a float of bundled reeds and waited on an offsh |
| r05 | CONFIRMED | That rock, Motu Nui, is three point nine hectares of land. |
| r06 | CONFIRMED | It is the summit of a mountain rising more than two kilometres from the seafloor, and the westernmost point of Chile. |
| r07 | CONFIRMED | Sharks, drowning, falls from the cliff on the way back up. |
| r08 | IMPRECISE | His clan took the exclusive right to every egg and every fledgling on those islets for a year, and he himself went into seclusion for a year, under a  |
| r09 | CONFIRMED | Makemake's representative on earth, decided by somebody else's swim. |
| r10 | CONFIRMED | The entire surviving register of the institution is eighty-six names, written down by Katherine Routledge between 1913 and 1915. |
| r11 | CONFIRMED | One object carries the whole change: Hoa Hakananai'a. |
| r12 | IMPRECISE | Two and a half metres, four point two tonnes, cut from dark flow lava rather than the compressed ash everything else came from. |
| r13 | CONFIRMED | It was found standing part-buried inside one of those houses, facing the crater. |
| r14 | CONFIRMED | Its back is covered in carving that was added after the statue was finished: two birdmen facing each other, a sooty tern above them, ceremonial paddle |
| r15 | CONFIRMED | One reading has the statue itself becoming the god. |
| r16 | CONFIRMED | In November of 1868 a Royal Navy crew dug it out, dragged it down on a sledge and rafted it to their ship. |
| r17 | CONFIRMED | It reached Plymouth the following August and went to the British Museum, where it is still. |
| r18 | CONFIRMED | In 2018 the island's governor asked for it back. |
| r19 | CONFIRMED | As for when the swimming stopped: three reference works give three answers. |
| r20 | CONFIRMED | Eighteen eighty-eight. |
| r21 | CONFIRMED | Eighteen sixty-seven. |
| r22 | CONFIRMED | Or simply the eighteen sixties. |
| r23 | CONFIRMED | This is an event inside the living memory of the people Routledge was recording, and we cannot date it. |
| r24 | CONFIRMED | She reached the islet herself in 1914 and found two caves. |
| r25 | CONFIRMED | One was where the swimmers had sheltered. |
| r26 | CONFIRMED | The other had held a small statue called the Boundary of the Land — which was already in Oxford before she got there. |
