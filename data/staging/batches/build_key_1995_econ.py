import csv

SRC = 'key-1995-Economics.csv'

answers = {
'ECO-J00211': ('B', "Economics is fundamentally about scarcity and choice, so its ultimate objective is to make the best use of scarce resources to satisfy unlimited wants."),
'ECO-J00212': ('C', "When faced with unlimited wants and one item to buy, the rational first step is to draw up a scale of preference ranking needs in order of urgency."),
'ECO-J00213': ('A', "In a market system, 'what to produce' is signalled by consumer spending (expenditure) on different commodities, i.e. consumer sovereignty."),
'ECO-J00214': ('A', "Government intervention in the economy is generally justified by the failure of market forces to allocate resources or produce outcomes that are socially satisfactory."),
'ECO-J00215': ('A', "A high rate of rural-urban migration makes census-taking difficult because people are not settled at their usual place of residence, leading to double-counting or omission."),
'ECO-J00216': ('C', "An ageing population is one in which the number/proportion of old persons in the population is increasing over time."),
'ECO-J00218': ('D', "Labour supply refers to the total labour input available, measured as the size of the workforce multiplied by the number of hours each person works."),
'ECO-J00219': ('A', "Advantages a firm gains directly from expanding its own scale of operation are internal economies of scale, as opposed to external economies which come from the growth of the whole industry."),
'ECO-J00220': ('C', "Economic rent is any payment to a factor of production above the minimum (transfer earnings) needed to keep it in its current use."),
'ECO-J00221': ('B', "The opportunity cost of using a producer's own resources (for which no cash payment is made) is an implicit cost."),
'ECO-J00222': ('D', "A change in the conditions of demand (e.g. tastes, income) at a constant price shifts the whole demand curve, rather than causing a movement along it."),
'ECO-J00223': ('D', "Basic demand-supply analysis: an increase in supply, with demand unchanged, lowers price and raises the quantity bought and sold."),
'ECO-J00224': ('D', "In a free market economy, resources are allocated through the price system, where prices of goods and factors coordinate decisions of consumers and producers."),
'ECO-J00225': ('B', "With highly elastic demand, a small price cut leads to a proportionately larger rise in quantity sold, raising total revenue and profit, so the firm should slightly reduce price."),
'ECO-J00226': ('A', "%change in quantity = 20/80 = 25%; %change in price = -5/25 = -20%. Price elasticity of demand = 25%/-20%, giving a magnitude of 1.25."),
'ECO-J00227': ('C', "4Y - 300 > 500 gives 4Y > 800, so Y > 200."),
'ECO-J00228': ('A', "A firm maximizes profit, whether in the short run or long run, at the output where marginal cost equals marginal revenue (MC = MR)."),
'ECO-J00229': ('C', "Retailers buy in bulk from wholesalers/manufacturers and break them down, stocking small quantities of a wide variety of goods for final consumers."),
'ECO-J00230': ('B', "Preference shareholders receive a fixed rate of dividend and have first claim on company profits ahead of ordinary shareholders."),
'ECO-J00231': ('C', "Small shops survive competition from big businesses mainly because of their personalized local services and longer/more flexible operating hours."),
'ECO-J00232': ('B', "Public enterprises are often defended on the grounds that, even where inefficient, they are among the largest employers of labour, serving a social/employment objective."),
'ECO-J00233': ('B', "Commercialization of a public enterprise means it is expected to operate as a commercial venture with the primary aim of making profit, rather than relying on subsidies."),
'ECO-J00234': ('B', "Agriculture provides food for the population (i), employs a large share of the workforce (ii), and supplies raw materials to local industries (iii); it does not supply heavy equipment to industry (iv is false)."),
'ECO-J00235': ('C', "Governments commonly stabilize agricultural prices by operating buffer stock schemes and stabilization funds that buy up surplus in good years and release stock in lean years."),
'ECO-J00236': ('B', "Nigeria's refineries (e.g. Kaduna) were sited partly on political/strategic grounds to spread industry across regions, in addition to availability of raw materials, rather than purely on economic/logistic grounds."),
'ECO-J00237': ('B', "Infant industries are newly established industries that are still too young/small to compete effectively with established foreign competitors and so may need temporary protection."),
'ECO-J00238': ('D', "A capital-intensive industry relies more heavily on machinery/equipment relative to workers, compared with a labour-intensive industry."),
'ECO-J00239': ('C', "Since the 1970s, crude oil exports have been by far the largest source of Nigeria's foreign exchange earnings."),
'ECO-J00240': ('B', "Expansionary monetary policy (increasing money supply/credit) is appropriate during an economic depression with low capacity utilization, to stimulate demand and output."),
'ECO-J00241': ('C', "The introduction of Value-Added Tax (VAT) in Nigeria (effective January 1994) raised the prices of many goods and services, driving the sharp price increases seen in late 1994."),
'ECO-J00242': ('B', "The most durable way to curb inflation, especially where it stems from scarcity of goods, is to increase the general level of production so supply can meet demand."),
'ECO-J00243': ('D', "A bank is described as distressed when it faces a serious liquidity crisis and cannot meet its obligations to depositors and other creditors."),
'ECO-J00244': ('A', "By demanding increased special deposits from commercial banks, the Central Bank locks away funds and restricts the banks' ability to expand credit."),
'ECO-J00245': ('B', "A targeted income supplement raises the income of those who need it most without the broad, universal cost of subsidizing goods for everyone, making it a cheaper way to improve welfare."),
'ECO-J00246': ('B', "The Consumer Price Index (CPI), which tracks the cost of a fixed basket of goods and services bought by typical households, is the standard measure of the cost of living."),
'ECO-J00247': ('C', "The university allowance was a transfer payment, not counted in national income, whereas the ₦7,000 wage is a factor payment for productive work and is counted; so national income rises by ₦7,000."),
'ECO-J00248': ('C', "Population growth benefits an economy when it raises the proportion of people of working age, lowering the dependency ratio and boosting the productive labour force."),
'ECO-J00249': ('A', "The mutual demands that agriculture and industry place on each other as an economy develops are described as backward and forward linkages."),
'ECO-J00250': ('C', "In a free/floating exchange rate system, the foreign exchange rate is determined by the market forces of demand for and supply of foreign currency."),
'ECO-J00251': ('B', "International economic organizations are primarily set up to promote economic co-operation among members for their mutual benefit."),
'ECO-J00252': ('C', "Profit is total revenue minus total cost: since TR = AR x Q, profit = (AR x Q) - TC."),
}

needs_data = {
'ECO-J00217': "Stem is grammatically truncated ('...but 5% of the L.G.A. in December 1981?') — missing the clause describing what happened to that 5% (died / emigrated / etc.), so the scenario cannot be reconstructed with confidence despite one option matching a plausible guess.",
}

with open(SRC, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

keyed_rows = []
review_rows = []
data_rows = []

fieldnames_keyed = ['question_id','subject','year','question_text','option_a','option_b','option_c','option_d','correct_option','explanation']
fieldnames_review = fieldnames_keyed + ['reason']

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
        base['correct_option'] = opt
        base['explanation'] = expl
        keyed_rows.append(base)
    elif qid in needs_data:
        base['correct_option'] = ''
        base['explanation'] = ''
        base['reason'] = needs_data[qid]
        data_rows.append(base)
    else:
        base['correct_option'] = ''
        base['explanation'] = ''
        base['reason'] = 'UNCLASSIFIED - needs manual check'
        review_rows.append(base)

print('keyed:', len(keyed_rows))
print('review:', len(review_rows))
print('data:', len(data_rows))
print('total:', len(keyed_rows)+len(review_rows)+len(data_rows))

with open('key-1995-Economics_keyed.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames_keyed)
    w.writeheader()
    for r in keyed_rows:
        w.writerow(r)

with open('key-1995-Economics_needs_review.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames_review)
    w.writeheader()
    for r in review_rows:
        w.writerow(r)

with open('key-1995-Economics_needs_data.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames_review)
    w.writeheader()
    for r in data_rows:
        w.writerow(r)
