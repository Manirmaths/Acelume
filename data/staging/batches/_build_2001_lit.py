import csv

SRC = 'data/staging/batches/key-2001-Literature.csv'

answers = {
"LIT-J00478": ("D", "Addressing the sea directly as \"mother and destroyer\" is the classic rhetorical device of apostrophe (directly addressing an absent or non-human entity)."),
"LIT-J00479": ("D", "\"Shocked by the odour... spat on the floor\" describes an involuntary physical reaction of disgust, i.e. nausea."),
"LIT-J00481": ("D", "The storm is compared to a dog (an animal) and the people to fleas (insects) in its hair, a whimsical, self-deprecating image."),
"LIT-J00482": ("C", "The anaphoric repetition of \"Asleep in...\" is what drives and sustains the rhetorical force of the speech."),
"LIT-J00483": ("A", "Gradgrind's insistence on fact and rigid arithmetic principle (\"two and two, and nothing over\") marks him as dogmatic."),
"LIT-J00485": ("B", "The marlin's picked-clean skeleton, after Santiago's long, heroic struggle, is the classic symbol of the futility of human struggle against nature."),
"LIT-J00486": ("B", "The novella's irony -- a heroic catch reduced to a bare skeleton -- epitomises the vain expectations/efforts of man."),
"LIT-J00487": ("A", "The blood from the marlin's wound trails through the water on the long voyage home and draws the sharks to the boat."),
"LIT-J00488": ("C", "Laye's time with Uncle Mamadou highlights the extended-family support system central to communal African life."),
"LIT-J00489": ("B", "Camara Laye's Guinea setting blends indigenous animist (pre-Islamic) customs with the Islamic faith practiced by his family."),
"LIT-J00490": ("D", "Telling the story in first person as an autobiographical account lends it greater authenticity and believability."),
"LIT-J00491": ("A", "A \"living legend\" status is defined by the accumulation of exaggerated, sometimes conflicting, stories that grow up around a person."),
"LIT-J00492": ("C", "Adah's marriage to Francis breaks down because she pursues education, writing and self-actualisation against his patriarchal expectations."),
"LIT-J00494": ("D", "The play's separate strands of action are tied together by their shared focus on the heroine's (Titubi/Morountodun's) transformation and choices."),
"LIT-J00495": ("B", "Osofisan's peasant-revolt drama, in his characteristic Marxist mode, stages the war as a struggle between the ruling/propertied class and the working peasantry."),
"LIT-J00496": ("C", "The Director's frequent breaking of the fourth wall to address the cast/audience gives the production an informal, presentational feel."),
"LIT-J00497": ("A", "Malvolio's description of Cesario mixes admiration of his good looks with contemptuous mockery of his boyish immaturity."),
"LIT-J00498": ("C", "The song is sung on behalf of the melancholic Duke, lamenting a love that is not returned."),
"LIT-J00499": ("D", "The Duke tells Cesario to press on past ordinary courtesy rather than accept any refusal, i.e. to not take no for an answer."),
"LIT-J00500": ("A", "Verse dialogue is reserved for the noble characters, marking their elevated and dignified (impressive) status compared to the prose-speaking comic characters."),
"LIT-J00501": ("B", "Mistaken identities and disguise (Viola as Cesario) drive the play's constant tension between how things appear and how they really are."),
"LIT-J00504": ("A", "The urn's frozen, unanswerable scenes provoke wonder -- the speaker's rhetorical questions convey admiration and amazement at what is depicted."),
"LIT-J00505": ("C", "Rhythm (the poem's sound/meter) and imagery (its sensory pictures) are the two concepts most central to poetry as a form."),
"LIT-J00506": ("A", "A device that hints at or anticipates a later event in the narrative is, by definition, foreshadowing."),
"LIT-J00507": ("D", "E.M. Forster's flat character is one-dimensional and defined by a single, unchanging quality or trait."),
"LIT-J00508": ("D", "Hubris is the term for the excessive pride that brings about a tragic hero's downfall."),
"LIT-J00509": ("B", "A farce is an exaggerated form of comic drama, built on improbable situations for comic effect."),
"LIT-J00510": ("D", "Catharsis, in Aristotle's sense, is the emotional purging/release the audience feels after watching a tragedy performed."),
"LIT-J00511": ("B", "A novel is defined as an extended, realistic work of fictional prose narrative."),
"LIT-J00512": ("D", "\"Total theatre\" is the term for a production style that uses the whole theatre space -- stage and auditorium alike -- erasing the boundary between performers and audience."),
"LIT-J00513": ("D", "The dramatic monologue reveals the Duke's possessive pride and arrogance through his cold account of the late Duchess."),
"LIT-J00514": ("A", "Ojaide's owl -- traditionally an omen -- signals a society gripped by political instability and unease."),
"LIT-J00515": ("D", "Mapanje's coded critique (written under Malawi's Banda dictatorship) uses the carnival image to satirise sycophancy and bad leadership."),
"LIT-J00516": ("A", "The polite but loaded exchange between the racially prejudiced landlady and the wary speaker is charged with mutual suspicion."),
"LIT-J00517": ("C", "Gray's Elegy argues that death comes equally to rich and poor, levelling worldly achievement and rendering life's glory meaningless for all."),
"LIT-J00518": ("C", "The Duke's pride in his commissioned portrait and statue reveals his connoisseur's appreciation of works of art -- which he extends, chillingly, to people."),
"LIT-J00520": ("D", "The ode's central idea is that art (the urn's frozen scene) endures beyond the brief span of human life."),
"LIT-J00521": ("A", "The tolling curfew bell, lowing herd and homeward plowman are all images of dusk settling over a quiet countryside."),
"LIT-J00522": ("C", "In the poem, darkness conceals the criminal predators who threaten residents of the township."),
"LIT-J00523": ("A", "Osofisan's peasant-revolt drama uses charged political language and persuasive, rhetorical speech throughout."),
"LIT-J00524": ("A", "The vow \"will one day be staunched, I swear!\" strikes a hopeful, optimistic note about ending the pollution described."),
"LIT-J00525": ("A", "The four quoted lines form a single four-line stanza, i.e. a quatrain (the opening quatrain of the sonnet)."),
}

reviews = {
"LIT-J00480": "Quoted dialogue plausibly supports either 'humour and irony' or 'hyperbole and allusion' (the boast about shaving a battalion 'between one coup and the next' is both hyperbolic and situationally ironic); not confident enough to pick the exam's intended pairing without the answer key.",
"LIT-J00484": "Interpretive theme question about the symbolic function of the boy alongside the old man in Hemingway's novella; several options (humiliation, contrast of character types, failing productivity of age) are each defensible without a quoted passage confirming the intended reading.",
"LIT-J00493": "Depends on recalling the specific role of the character 'Marshal', inferred (not stated) to be from Osofisan's Morountodun; not confident enough in the character's exact function to commit to an option.",
"LIT-J00502": "Requires recall of the specific sound devices used in Osundare's 'They Too Are The Earth'; no lines are quoted, and I cannot confidently distinguish repetition/rhyme/assonance for this poem from general knowledge.",
"LIT-J00503": "Requires knowing the exact rhyme scheme and line count of the final stanza of Okigbo's 'Hurrah for Thunder', which is not quoted; cannot confidently classify it as octave/quatrain/couplet/sestet.",
"LIT-J00519": "Requires specific recall of which sensory images (visual/tactile/olfactory/auditory) dominate the hardship passage in Rubadiri's 'Stanley Meets Mutesa'; not confident enough without the quoted lines.",
}

with open(SRC, newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

keyed_rows = []
review_rows = []
data_rows = []

for row in rows:
    qid = row['question_id']
    base = {
        'question_id': qid,
        'subject': row['subject'],
        'year': row['year'],
        'question_text': row['question_text'],
        'option_a': row['option_a'],
        'option_b': row['option_b'],
        'option_c': row['option_c'],
        'option_d': row['option_d'],
    }
    if qid in answers:
        opt, expl = answers[qid]
        r = dict(base)
        r['correct_option'] = opt
        r['explanation'] = expl
        keyed_rows.append(r)
    elif qid in reviews:
        r = dict(base)
        r['reason'] = reviews[qid]
        review_rows.append(r)
    else:
        r = dict(base)
        r['reason'] = 'UNCLASSIFIED - needs manual check'
        data_rows.append(r)

print('keyed', len(keyed_rows))
print('review', len(review_rows))
print('data', len(data_rows))
print('total', len(keyed_rows)+len(review_rows)+len(data_rows))

keyed_fields = ['question_id','subject','year','question_text','option_a','option_b','option_c','option_d','correct_option','explanation']
review_fields = keyed_fields[:-2] + ['reason']  # no correct_option/explanation, but keep same base + reason
# base fields without correct_option/explanation
review_fields = ['question_id','subject','year','question_text','option_a','option_b','option_c','option_d','reason']

with open('data/staging/batches/key-2001-Literature_keyed.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=keyed_fields)
    w.writeheader()
    w.writerows(keyed_rows)

with open('data/staging/batches/key-2001-Literature_needs_review.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=review_fields)
    w.writeheader()
    w.writerows(review_rows)

with open('data/staging/batches/key-2001-Literature_needs_data.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=review_fields)
    w.writeheader()
    w.writerows(data_rows)
