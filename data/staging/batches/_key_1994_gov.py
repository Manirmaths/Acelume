import csv

SRC = "/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches/key-1994-Government.csv"
OUT_DIR = "/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches"

answers = {
"GOV-J00183": ("D", "A 'polity' is the standard term for a society organized under a system of government."),
"GOV-J00184": ("C", "Power without governmental legitimacy (a recognized right to rule) is naked/coercive force, per the classic authority-vs-power distinction."),
"GOV-J00185": ("B", "A nation implies a culturally/ethnically homogenous people, unlike a state which only requires territory and government."),
"GOV-J00186": ("C", "Judicial independence is secured mainly through permanent (secure) tenure of office, insulating judges from removal pressure."),
"GOV-J00187": ("A", "The classic textbook advantages of federalism cited together are economies of scale, uniform development, and political unity among diverse groups."),
"GOV-J00188": ("C", "Despite its official name 'Swiss Confederation', Switzerland's constitution is functionally federal, with cantons and a central government, and is the standard textbook example of federalism."),
"GOV-J00189": ("C", "Flexible vs rigid constitutions are distinguished chiefly by their amendment procedure (simple ordinary-law process vs special/entrenched process)."),
"GOV-J00190": ("C", "The classic definition of democracy centers on government resting on the free consent/will of the governed."),
"GOV-J00191": ("D", "Capitalism is the economic system where means of production are privately owned/controlled by individuals for profit."),
"GOV-J00192": ("A", "Checks and balances exist to make government function properly while preventing any one arm from exercising arbitrary power."),
"GOV-J00193": ("C", "The power to dissolve the legislature and call elections rests with the head of government (PM) under a parliamentary system."),
"GOV-J00194": ("B", "Accountability requires public officers to render a good account of their stewardship/activities to the public."),
"GOV-J00195": ("B", "Prorogation ends a legislative session while preserving the assembly for a later session (unlike dissolution)."),
"GOV-J00196": ("C", "The rule of law is violated when government itself acts arbitrarily/above the law in its policies."),
"GOV-J00197": ("B", "Restricting the franchise to male adults only is termed male suffrage."),
"GOV-J00198": ("B", "Provision of public utilities (roads, water, electricity, etc.) is a core duty/obligation of government, distinct from citizens' duties like obeying laws or caring for property."),
"GOV-J00199": ("A", "A primary election is the intra-party process where party members choose candidates for elective office."),
"GOV-J00200": ("C", "This describes 'recall' - the process by which constituents can terminate an elected representative's mandate before term end."),
"GOV-J00201": ("B", "Interest aggregation - combining diverse group demands into coherent policy platforms - is a defining function of political parties."),
"GOV-J00202": ("B", "The Oyo Empire (Yoruba) is the classic pre-colonial example of checks and balances, via the Oyo Mesi/Bashorun checking the Alaafin's power."),
"GOV-J00203": ("B", "Benin was a centralized monarchy while the Igbo were largely acephalous/village-based, so this pair does not match administratively (unlike Igbo/Tiv, both acephalous, or Sokoto/Oyo and Benin/Sokoto, both centralized monarchies)."),
"GOV-J00204": ("C", "French assimilation-era administrative policy centralized control tightly and left little room for political agitation, unlike British indirect rule, which allowed nationalist activity to emerge earlier; option D's text appears garbled/truncated but does not change this reasoning."),
"GOV-J00205": ("A", "The elective principle in British West Africa was first introduced in Nigeria under the 1922 Clifford Constitution, allowing Lagos and Calabar to elect members to the Legislative Council."),
"GOV-J00206": ("B", "The 1957/58 constitutional conferences were dominated by the minorities question, leading directly to the setting up of the Willink Commission in 1957."),
"GOV-J00207": ("D", "The 1963 Republican Constitution created a Nigerian President as ceremonial Head of State (Azikiwe) separate from the Prime Minister as Head of Government (Balewa)."),
"GOV-J00208": ("A", "Under the 1963 parliamentary system, ministers were drawn from and remained members of the National Assembly, unlike the 1979 presidential system where ministers came from outside it."),
"GOV-J00209": ("C", "A writ of habeas corpus compels the custodian of a detainee to produce the person and justify the detention."),
"GOV-J00210": ("A", "The armed forces' primary function is to promote and protect the security/territorial integrity of the nation."),
"GOV-J00211": ("D", "The Federal Civil Service Commission was constitutionally established to handle appointment, discipline and removal of civil servants, shielding them from arbitrary political interference."),
"GOV-J00212": ("A", "The Nigerian Youth Movement (NYM) displaced the NNDP as the dominant Lagos nationalist party from 1938, before independence."),
"GOV-J00213": ("B", "Besides debating the draft constitution, the 1977/78 Constituent Assembly was dominated by the controversy over a Federal Sharia Court of Appeal, which caused a walkout by some delegates."),
"GOV-J00214": ("D", "The Mid-West Region, carved out of the Western Region in 1963 for its minority populations, was the first minority state/region created in the federation."),
"GOV-J00215": ("A", "The absence of a generally acceptable revenue allocation formula has been a recurring major constraint on Nigerian federalism."),
"GOV-J00216": ("C", "Standard texts distinguish ministries (creatures of general civil-service administrative arrangements) from public corporations (created by specific enabling statutes/Acts)."),
"GOV-J00217": ("B", "Privatization and commercialization shift enterprises toward private ownership/profit motive, entrenching capitalism."),
"GOV-J00218": ("B", "The 1976 Local Government Reform (single-tier system, statutory allocations) was aimed at and credited with accelerating rural development."),
"GOV-J00220": ("A", "Repeated military intervention politicized the armed forces themselves, a widely cited negative consequence."),
"GOV-J00221": ("D", "The 1975 panel that recommended Abuja as the new Federal Capital Territory was headed by Justice Akinola Aguda."),
"GOV-J00222": ("C", "'Comprador bourgeoisie' describes local (Nigerian) businessmen/elites who serve as intermediaries/agents for foreign capital interests."),
"GOV-J00223": ("D", "The Ajaokuta Steel Project was developed with Soviet/Russian technical and financial assistance."),
"GOV-J00224": ("D", "Professor Bolaji Akinyemi, as External Affairs Minister (1985-87), championed the 'concert of medium powers' foreign policy concept."),
"GOV-J00225": ("D", "Nigeria's First Republic foreign policy independence was constrained chiefly by its economic dependence on Western (former colonial) economies."),
"GOV-J00227": ("B", "Nigeria gave significant financial, diplomatic and material support to the MPLA in Angola's 1975/76 independence/civil war."),
"GOV-J00228": ("B", "Professor Adebayo Adedeji (rendered 'Adeboyo' in the source) served as UN Under-Secretary-General and Executive Secretary of the Economic Commission for Africa (ECA), 1975-1991."),
"GOV-J00229": ("A", "Nigeria was regarded as an honorary Frontline State for its strong financial, diplomatic and material support to Southern African liberation struggles, despite not bordering apartheid states."),
"GOV-J00231": ("D", "The 1990 Gulf crisis (Iraq's invasion of Kuwait) demonstrated the UN's continuing inability to guarantee permanent world peace/prevent aggression."),
"GOV-J00232": ("D", "Political authority is the recognized/legitimate right to exercise political power, distinct from mere capacity or ability (power)."),
}

review_answers = {
"GOV-J00219": ("C", "The Babangida administration's transition to civil rule programme is commonly dated as officially starting in 1987, based on the transition timetable and the local government elections held that year.", "Sources genuinely conflict on which year counts as the 'official start' of the transition programme: Political Bureau set up 1986, transition timetable/local govt elections 1987, originally-targeted handover 1990. Risk of keying the wrong specific year JAMB intends."),
"GOV-J00226": ("A", "Margaret Thatcher, UK Prime Minister through the 1980s, is the option most consistent with opposition to Third World debt cancellation during that era.", "Could not independently verify this specific historical claim with confidence; risk of misattributing the position to the wrong of four listed British PMs."),
"GOV-J00230": ("A", "OPEC's principal strategy for influencing oil prices is agreeing production quotas among members (i.e., determining the quantity of oil produced in a given period).", "Option A reads 'quality' where 'quantity' is almost certainly intended (likely scraping/OCR corruption); since this is the likely-correct option itself, holding back rather than keying a possibly-altered answer text."),
}

rows = []
with open(SRC, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

keyed_out = []
review_out = []
data_out = []

for r in rows:
    qid = r['question_id']
    base = {
        'question_id': qid,
        'subject': r['subject'],
        'year': r['year'],
        'question_text': r['question_text'],
        'option_a': r['option_a'],
        'option_b': r['option_b'],
        'option_c': r['option_c'],
        'option_d': r['option_d'],
    }
    if qid in answers:
        opt, expl = answers[qid]
        row = dict(base)
        row['correct_option'] = opt
        row['explanation'] = expl
        keyed_out.append(row)
    elif qid in review_answers:
        opt, expl, reason = review_answers[qid]
        row = dict(base)
        row['correct_option'] = opt
        row['explanation'] = expl
        row['reason'] = reason
        review_out.append(row)
    else:
        row = dict(base)
        row['correct_option'] = ''
        row['explanation'] = ''
        row['reason'] = 'Not classified by keyer - unexpected miss.'
        data_out.append(row)

print("keyed:", len(keyed_out), "review:", len(review_out), "data:", len(data_out), "total:", len(rows))

fieldnames_keyed = ['question_id','subject','year','question_text','option_a','option_b','option_c','option_d','correct_option','explanation']
fieldnames_flag = fieldnames_keyed + ['reason']

with open(f"{OUT_DIR}/key-1994-Government_keyed.csv", 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames_keyed)
    w.writeheader()
    for row in keyed_out:
        w.writerow(row)

with open(f"{OUT_DIR}/key-1994-Government_needs_review.csv", 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames_flag)
    w.writeheader()
    for row in review_out:
        w.writerow(row)

with open(f"{OUT_DIR}/key-1994-Government_needs_data.csv", 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames_flag)
    w.writeheader()
    for row in data_out:
        w.writerow(row)
