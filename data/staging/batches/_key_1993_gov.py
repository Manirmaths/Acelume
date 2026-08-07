import csv

answers = {
"GOV-J00140": ("C", "Sovereignty combines a legal dimension (supreme lawmaking authority recognized in law) and a political dimension (actual capacity to exercise that authority), i.e. political and legal aspects."),
"GOV-J00141": ("B", "The civil service is the permanent administrative machinery that implements government policy, placing it under the executive arm of government."),
"GOV-J00142": ("D", "In a confederation, member states remain sovereign and delegate only limited powers to a weak central body, so ultimate power stays with the constituent units."),
"GOV-J00143": ("A", "Federalism, per the classical definition, is a constitutional arrangement where national and regional governments each derive their powers directly and independently from the constitution."),
"GOV-J00144": ("C", "A written constitution is one whose fundamental provisions are set down and codified in a single formal document, as opposed to an unwritten constitution based on conventions and scattered statutes."),
"GOV-J00145": ("C", "Federalism only requires division of powers, constitutional supremacy and a rigid amendment procedure; it does not require an executive presidential system, since parliamentary federations like Canada, Australia and India exist."),
"GOV-J00146": ("D", "Communism as an ideology aims at a classless society through collective ownership of the means of production, seeking to eliminate socio-economic inequality."),
"GOV-J00147": ("A", "The legislature's quasi-judicial role stems from its investigative powers, such as summoning witnesses and holding inquiries, which resemble court proceedings."),
"GOV-J00148": ("B", "Nazism (National Socialism) was the doctrine formulated and led by Adolf Hitler in Germany."),
"GOV-J00149": ("D", "Formal legislation in the Westminster system includes Acts of Parliament, Orders in Council and royal proclamations; a ministerial pronouncement is a statement, not a legally binding legislative instrument."),
"GOV-J00150": ("C", "Under the presidential system, the president combines the ceremonial role of head of state with the political role of head of government, unlike parliamentary systems where these are separated."),
"GOV-J00151": ("A", "Delegated legislation allows the executive to make rules with the force of law, blurring the boundary between the executive and legislative arms and eroding separation of powers."),
"GOV-J00152": ("C", "The rule of law holds that all persons, including government officials, are equal before and subject to the law."),
"GOV-J00153": ("D", "An electoral district in which voters elect a representative is commonly called a constituency."),
"GOV-J00154": ("D", "Free and fair elections require impartial electoral administration; a partial (biased) electoral body is incompatible with genuine free and fair elections."),
"GOV-J00155": ("A", "Proportional representation is criticised for perpetuating a multiplicity of parties, since even small parties win seats, often producing unstable coalition governments."),
"GOV-J00156": ("C", "Interest groups matter to democracy because they give voice and representation to sectional or minority interests that might otherwise be excluded from the political process."),
"GOV-J00157": ("D", "In the Hausa-Fulani emirate system, the Galadima was a senior title-holder who assisted the Sarki/Emir with executive and administrative duties, distinct from judicial officials like the Alkali."),
"GOV-J00158": ("B", "Cultural imperialism, external manipulation of local affairs and foreign control of the domestic economy are all negative consequences of colonial rule, unlike the other option sets which mix in positive effects such as education or liberal democracy."),
"GOV-J00159": ("A", "European imperialism was primarily driven by the desire to expand economic markets/resources and extend political influence and control over colonies."),
"GOV-J00160": ("B", "The Colony of Lagos was amalgamated with the Protectorate of Southern Nigeria in 1906 to form the Colony and Protectorate of Southern Nigeria."),
"GOV-J00161": ("B", "Sir George Taubman Goldie is chiefly remembered for merging rival British trading firms on the Niger into a single company (the United African Company, later chartered as the Royal Niger Company)."),
"GOV-J00162": ("C", "The influx of West Indian and American intellectuals was an external influence on Nigerian nationalism, not an internal factor, unlike denial of equal opportunity, political parties/press, and modern education which arose from within the colony."),
"GOV-J00163": ("B", "The 1922 (Clifford) Constitution's Legislative Council had jurisdiction restricted to the Colony of Lagos and the Southern Provinces; Northern Nigeria remained outside its legislative competence."),
"GOV-J00164": ("A", "The 1960 Independence Constitution retained the British monarch as head of state (making it monarchical) and operated on the Westminster cabinet/parliamentary model, prior to Nigeria becoming a republic in 1963."),
"GOV-J00165": ("D", "Sir James Robertson was Governor-General of Nigeria at independence on 1 October 1960, before Nnamdi Azikiwe became the first indigenous Governor-General later that year."),
"GOV-J00166": ("A", "Under the parliamentary First Republic, Prime Minister Tafawa Balewa was head of government and, as an elected member of the House of Representatives, also a law maker; the President was head of state."),
"GOV-J00167": ("D", "The Council of State in Nigeria is a constitutional advisory body that counsels the President on matters such as appointments and the prerogative of mercy."),
"GOV-J00168": ("B", "As the apex court, Supreme Court decisions are final and are not subject to review by any other court of law under military administrations."),
"GOV-J00169": ("A", "Public service commissions under the 1979 Constitution (e.g. Federal Civil Service Commission, Judicial Service Commission) were designed to be independent of the executive to safeguard impartial administration."),
"GOV-J00170": ("D", "The Phillipson Commission (1946) was an early ad hoc commission set up specifically to review and recommend revenue allocation formulas for Nigeria, unlike Ashby (education) and Udoji (civil service reform)."),
"GOV-J00172": ("C", "Public corporations/statutory bodies wholly or partly owned by government in Nigeria are commonly referred to as parastatals."),
"GOV-J00173": ("C", "Local government represents devolution of power, where governmental authority and functions are constitutionally transferred to a lower, semi-autonomous tier of government."),
"GOV-J00174": ("C", "A country's foreign relations are primarily shaped by its national interest, i.e. the pursuit of its own economic, security and political goals."),
"GOV-J00175": ("C", "Nigeria's Africa-centred foreign policy stems from its concern for and attention to African problems, notably decolonisation and anti-apartheid struggles."),
"GOV-J00176": ("A", "ECOWAS (Economic Community of West African States) is the principal organisation through which Nigeria pursues economic, political and social cooperation in West Africa."),
"GOV-J00177": ("B", "Under Article 4 of the UN Charter, a state is admitted to UN membership through recommendation by the Security Council followed by approval of the General Assembly, i.e. concurrent action of both organs."),
"GOV-J00178": ("D", "The Assembly of Heads of State and Government was the supreme policy-making organ of the Organisation of African Unity."),
"GOV-J00179": ("B", "Nigeria belonged to the moderate Monrovia Group of African states, as opposed to the radical Casablanca Group, before the two blocs merged to form the OAU in 1963."),
"GOV-J00180": ("A", "Justice Taslim Olawale Elias was the first Nigerian to be appointed President of the International Court of Justice at The Hague, serving 1982-1985."),
"GOV-J00181": ("C", "The OAU, through its African Liberation Committee, channelled financial contributions from African governments to liberation movements fighting colonial and apartheid rule in Southern Africa."),
"GOV-J00182": ("C", "Prior to the Soviet Union's dissolution in December 1991, the five permanent, veto-wielding members of the UN Security Council were the Soviet Union, the People's Republic of China, Great Britain, France and the United States."),
}

review = {
"GOV-J00171": "Genuinely contested: the phrase 'federal character' is widely credited to Gen. Murtala Mohammed's 1975 speech establishing the Constitution Drafting Committee, but it was formally enshrined and popularised as constitutional doctrine in the 1979 Constitution. Sources disagree on which JAMB intends as 'popularised by', so holding back rather than guessing.",
}

data_issues = {}

infile = '/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches/key-1993-Government.csv'
with open(infile, newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

out_fields = ['question_id','subject','year','question_text','option_a','option_b','option_c','option_d','correct_option','explanation']
review_fields = out_fields + ['reason']

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
        letter, expl = answers[qid]
        base['correct_option'] = letter
        base['explanation'] = expl
        keyed_rows.append(base)
    elif qid in review:
        base['correct_option'] = ''
        base['explanation'] = ''
        base['reason'] = review[qid]
        review_rows.append(base)
    elif qid in data_issues:
        base['correct_option'] = ''
        base['explanation'] = ''
        base['reason'] = data_issues[qid]
        data_rows.append(base)
    else:
        raise ValueError(f"Unhandled question {qid}")

def write_csv(path, fields, data):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in data:
            w.writerow(r)

write_csv('/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches/key-1993-Government_keyed.csv', out_fields, keyed_rows)
write_csv('/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches/key-1993-Government_needs_review.csv', review_fields, review_rows)
write_csv('/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches/key-1993-Government_needs_data.csv', review_fields, data_rows)

print("keyed:", len(keyed_rows))
print("review:", len(review_rows))
print("data:", len(data_rows))
print("total:", len(keyed_rows)+len(review_rows)+len(data_rows))

# verify uppercase and non-empty
bad = [r['question_id'] for r in keyed_rows if r['correct_option'] not in ('A','B','C','D') or not r['explanation'].strip()]
print("bad keyed rows:", bad)
