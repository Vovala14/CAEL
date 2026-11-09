"""Small authored CC0 research examples; not benchmark or training data."""
def query(engine,text):return dict(engine=engine,text=text)


def episodes():
    return [
      dict(id='custody',events=['Mira went to the atrium','Mira got the brass key','Mira went to the gallery','Mira dropped the brass key','Mira went to the loft'],logic='',queries=[query('world','Where is the brass key?'),query('world','Where is Mira?'),query('world','Who holds the brass key?')]),
      dict(id='handoff',events=['Tarin went to the workshop','Lena went to the workshop','Tarin got the parcel','Tarin gave the parcel to Lena','Lena went to the courtyard'],logic='',queries=[query('world','Who holds the parcel?'),query('world','Where is the parcel?'),query('world','Who received the parcel?')]),
      dict(id='uncertain',events=['Dara is either in the studio or the cellar','Dara is not in the studio'],logic='',queries=[query('world','Where is Dara?'),query('world','Is Dara in the studio?')]),
      dict(id='rejected-transfer',events=['Sora went to the hall','Enno went to the garden','Sora got the token','Sora gave the token to Enno'],logic='',queries=[query('world','Who holds the token?'),query('world','Where is the token?')]),
      dict(id='rule-chain',events=[],logic='Nika is glimmering. Every glimmering thing is amber. Every amber thing is visible.',queries=[query('logic','Is Nika visible?'),query('logic','Is Nika not visible?')]),
      dict(id='unknown-is-not-false',events=[],logic='Ralo is patient. Every golden thing is quiet.',queries=[query('logic','Is Ralo quiet?')]),
      dict(id='conflict-is-not-certainty',events=[],logic='Vena is ready. Vena is not ready.',queries=[query('logic','Is Vena ready?')]),
      dict(id='cyclic-rules',events=[],logic='Kori is green. Every amber thing is violet. Every violet thing is amber.',queries=[query('logic','Is Kori amber?')]),
      dict(id='bare-category-chain',events=[],logic='Tavi is a wren. Every wren is a bird. Every bird is visible.',queries=[query('logic','Is Tavi visible?'),query('logic','Is Tavi not visible?')])]


EXPECTED=[['gallery','loft','unknown'],['lena','courtyard','lena'],['cellar','no'],['sora','hall'],['true','false'],['unknown'],['conflicting'],['unknown'],['true','false']]
# Original desired entailments above remain unchanged. The bridge must retain
# this released-engine failure, rather than repair its answer or count it right.
KNOWN_PARSER_FAILURES={'rule-chain':['unknown','unknown']}
