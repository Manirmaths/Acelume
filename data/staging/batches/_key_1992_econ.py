import csv

SRC = '/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches/key-1992-Economics.csv'

answers = {
"ECO-J00086": ("C", "Scale of preference is a list of wants/goods arranged in order of priority/urgency, which is exactly what option C describes."),
"ECO-J00087": ("D", "The real (opportunity) cost of producing X is measured by the extra amount of Y that could have been produced instead, i.e. the output of Y forgone."),
"ECO-J00088": ("C", "In a wholly capitalist (free market) economy, resources are allocated through the price mechanism (supply and demand) rather than government direction."),
"ECO-J00089": ("D", "Nigeria's family planning campaign aims to moderate population growth so it does not outpace economic growth, with the ultimate objective of raising the population's standard of living."),
"ECO-J00090": ("C", "Where rural areas have surplus/underemployed labour, migration of some workers to urban areas raises the marginal productivity of those who remain in rural agriculture (classic surplus-labour, dual-economy argument)."),
"ECO-J00091": ("B", "By definition Total Cost = Fixed Cost + Variable Cost, so Variable Cost = Total Cost minus Fixed Cost."),
"ECO-J00092": ("A", "When capital becomes relatively more expensive than labour, firms substitute towards the now relatively cheaper factor, adopting more labour-intensive techniques."),
"ECO-J00093": ("D", "In the long run all factors are variable, so the U-shape of the LRAC curve is explained by economies of scale followed by diseconomies of scale, not by diminishing returns which is a short-run concept."),
"ECO-J00094": ("A", "The price mechanism efficiently allocates resources through the interaction of supply and demand signals, which central planners cannot easily replicate."),
"ECO-J00095": ("B", "With inelastic demand, a price rise causes a proportionately smaller fall in quantity demanded, so total revenue rises even though quantity demanded falls."),
"ECO-J00096": ("C", "A rise in the price of a complementary good reduces demand for that complement and, since the two goods are used together, also shifts demand for the good in question to the left."),
"ECO-J00097": ("D", "Equating marginal cost to marginal revenue is the universal profit-maximising (equilibrium output) rule that applies to firms in any market structure, not just one."),
"ECO-J00098": ("B", "A key function of retailers is to break bulk purchased from wholesalers/producers and sell it in small units suited to individual consumers."),
"ECO-J00099": ("D", "Because it is owned and financed by one person, a sole proprietorship's main handicap is limited/inadequate capital for expansion."),
"ECO-J00100": ("B", "Nigeria's privatization and commercialization programme (from the 1988 SAP-era reforms) was primarily intended to improve efficiency in the performance of formerly loss-making public enterprises."),
"ECO-J00101": ("A", "If foreign demand for the export crop is inelastic, an increase in supply pushes the price down proportionately more than quantity rises, so total farm revenue (income) falls."),
"ECO-J00102": ("D", "Under Nigeria's Structural Adjustment Programme the commodity/marketing boards were abolished and agricultural marketing was liberalised to private investors and individuals."),
"ECO-J00103": ("A", "Landlords, who typically hold economic and political influence, are the main source of opposition that blocks land reform in developing countries."),
"ECO-J00104": ("A", "Consumer-goods industries dominate Nigeria's industrial sector mainly because a large domestic market and most required raw materials (agricultural inputs) are readily available."),
"ECO-J00105": ("B", "The oil boom raised oil's share of GNP so sharply that agriculture's percentage contribution to GNP fell, even though agricultural output itself did not necessarily decline (a 'Dutch disease' effect)."),
"ECO-J00106": ("B", "Since crude oil is exported largely unrefined, Nigeria earns high foreign exchange from its sale but gains little forward linkage (few domestic downstream processing industries), so the two effects are respectively high and low."),
"ECO-J00107": ("A", "Treasury bills are a money-market instrument dealt in by the Central Bank, commercial banks and discount houses; the stock exchange deals mainly in long-term capital market securities, not treasury bills."),
"ECO-J00108": ("C", "The monetization ratio measures the proportion of an economy's total transactions conducted using money rather than barter, i.e. monetary transactions divided by total transactions."),
"ECO-J00109": ("A", "Raising the liquidity (reserve) ratio forces banks to hold more of their assets as reserves and lend less, directly reducing the money supply."),
"ECO-J00111": ("A", "To curb inflation, contractionary fiscal policy is used: raising taxes reduces disposable income/spending, and running a budget surplus withdraws net money from the economy."),
"ECO-J00112": ("D", "When interest rates are high and rising, borrowing (loans or debentures) becomes increasingly costly, so issuing new ordinary shares (equity, with no fixed interest obligation) is the least-cost way to raise additional funds."),
"ECO-J00113": ("A", "Public finance (government taxation and spending) is used as a macroeconomic policy tool to promote full employment, growth of national income, and price stability."),
"ECO-J00114": ("C", "The Federation Account is the pool into which centrally collected revenue is paid and from which allocations are made to the federal, state and local governments in Nigeria."),
"ECO-J00115": ("D", "Percentage increase in GNP = (27,000 - 20,000)/20,000 x 100 = 35.0%."),
"ECO-J00116": ("D", "GNP per head = GNP divided by population: Year 1 = N20,000m / 20m = N1,000; Year 2 = N27,000m / 24m = N1,125."),
"ECO-J00117": ("A", "In national income accounting, aggregate (personal) saving is defined as the part of disposable income that is not spent on consumption."),
"ECO-J00118": ("D", "Low infant mortality, high per capita income and high literacy rates are recognised, mutually consistent indicators of a country's level of development."),
"ECO-J00119": ("B", "The portion of economic growth left unexplained after accounting for increased labour and capital productivity is conventionally attributed to technical progress (the Solow residual)."),
"ECO-J00120": ("C", "Boosting exports of locally made goods earns additional foreign exchange quickly, directly improving a balance of payments deficit in the short run, unlike increased imports or capital/debt outflows which worsen it."),
"ECO-J00121": ("A", "A foreign tourist's spending on hotels and meals in Nigeria is payment for a service rendered to a non-resident, so it is recorded as an invisible export in Nigeria's balance of payments."),
"ECO-J00122": ("C", "The Nigeria Trust Fund, established in 1976, is administered on Nigeria's behalf by the African Development Bank."),
"ECO-J00123": ("B", "A key benefit of regional groupings like ECOWAS for member states is trade creation, i.e. increased trade among members following the removal of internal tariff barriers."),
"ECO-J00124": ("A", "Dependency ratio = (population aged 0-14 + population above 60) / working-age population (15-60) = (25+30):45 = 55:45 = 11:9."),
"ECO-J00125": ("A", "Optimum population is the population size that maximises output (food) per head; per-capita food output is 4.4 tonnes at 50 million people, higher than at 70, 90 or 100 million, so 50 million is optimum."),
"ECO-J00126": ("D", "Variable cost at output 20 = Total Cost (N1,400) - Fixed Cost (N1,000) = N400; variable cost per unit = N400 / 20 units = N20."),
"ECO-J00127": ("D", "Public goods in Nigeria (roads, utilities, etc.) are mainly provided through statutory corporations set up and run by government."),
"ECO-J00128": ("D", "The terms of trade is defined as the index of export prices divided by the index of import prices, multiplied by 100."),
}

review = {
"ECO-J00085": "Ambiguous: the economic problem (scarcity) arises from the interaction of unlimited wants and limited means; options A (unlimited human wants) and C (limited means available) each state one half of this definition, so the single intended answer cannot be determined with confidence.",
"ECO-J00110": "Option set does not cleanly match the standard 'money in circulation' definition: all four options include cash owned by banks (or government), but standard narrow-money definitions count only currency held by the non-bank public plus non-bank current account balances; no option isolates that, so cannot confidently pick a single answer.",
}

needs_data = {}

fieldnames_keyed = ["question_id","subject","year","question_text","option_a","option_b","option_c","option_d","correct_option","explanation"]
fieldnames_other = fieldnames_keyed + ["reason"]

with open(SRC, newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

keyed_rows, review_rows, data_rows = [], [], []

for row in rows:
    qid = row['question_id']
    base = {
        "question_id": qid,
        "subject": row['subject'],
        "year": row['year'],
        "question_text": row['question_text'],
        "option_a": row['option_a'],
        "option_b": row['option_b'],
        "option_c": row['option_c'],
        "option_d": row['option_d'],
    }
    if qid in answers:
        opt, exp = answers[qid]
        r = dict(base)
        r["correct_option"] = opt
        r["explanation"] = exp
        keyed_rows.append(r)
    elif qid in review:
        r = dict(base)
        r["correct_option"] = ""
        r["explanation"] = ""
        r["reason"] = review[qid]
        review_rows.append(r)
    elif qid in needs_data:
        r = dict(base)
        r["correct_option"] = ""
        r["explanation"] = ""
        r["reason"] = needs_data[qid]
        data_rows.append(r)
    else:
        raise Exception("Unhandled question_id: " + qid)

def write_csv(path, fieldnames, data):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in data:
            w.writerow(r)

write_csv('/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches/key-1992-Economics_keyed.csv', fieldnames_keyed, keyed_rows)
write_csv('/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches/key-1992-Economics_needs_review.csv', fieldnames_other, review_rows)
write_csv('/sessions/tender-amazing-davinci/mnt/Acelume/data/staging/batches/key-1992-Economics_needs_data.csv', fieldnames_other, data_rows)

print("keyed:", len(keyed_rows))
print("review:", len(review_rows))
print("data:", len(data_rows))
print("total:", len(keyed_rows)+len(review_rows)+len(data_rows))

# Validate uppercase A-D and non-empty explanation for keyed rows
bad = [r['question_id'] for r in keyed_rows if r['correct_option'] not in ('A','B','C','D') or not r['explanation'].strip()]
print("bad keyed rows:", bad)
