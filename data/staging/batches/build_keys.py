import csv

decisions = {
"GEO-J00037": ("keyed","A","Map area = 12x7 = 84 cm2. New area 336 cm2 is 4x the original area (336/84=4). Since area scales with the square of the linear scale factor, the linear enlargement factor is sqrt(4)=2, i.e. the map is enlarged twice (each dimension doubled: 24cm x 14cm = 336 cm2). Agrees with external candidate."),
"GEO-J00038": ("keyed","A","Summing the five listed outputs (139.82+64.82+48.77+46.78+36.00) gives 336.19 ('000 tonnes), matching the stated five-country total of ~335.990 (the '3335,990' in the source is a digitisation artifact/decimal-comma rendering of 335.990, not three-thousand-plus). USSR's share = 139.82/335.990 = 41.6%, matching option A (41.614%) almost exactly. Agrees with external candidate."),
"GEO-J00039": ("keyed","A","The table compares discrete quantities across five named countries (best shown as bars for direct comparison) and could also show each country's share of total output (best shown as a pie chart for proportion-of-whole). Pie chart and bar graph are the standard complementary diagrams for this kind of categorical data. Agrees with external candidate."),
"GEO-J00040": ("keyed","D","New York (75 W) and Baghdad (45 E) differ by 120 degrees of longitude = 120/15 = 8 hours, with Baghdad ahead. 7pm ET on 15 Jan in New York + 8 hours = 3am on 16 January in Baghdad. This matches the historical UN deadline given to Iraq (expiring midnight EST 15/16 Jan 1991, i.e. early morning of the 16th in Baghdad). Agrees with external candidate."),
"GEO-J00041": ("keyed","A","The four basic spheres of the physical environment are the atmosphere (air), lithosphere (solid earth), hydrosphere (water) and biosphere (living things) - standard physical geography classification. Agrees with external candidate."),
"GEO-J00042": ("keyed","A","Petroleum is a fluid that migrates and accumulates where it is trapped under an impermeable cap rock at the crest of an upward fold (anticline) in sedimentary rock sequences - this is the classic 'anticlinal trap' taught in petroleum geology. A syncline (downward fold) would trap water at its base, not oil, since oil/gas float above water in the reservoir. OVERRIDE: external candidate (C, synclinal structures) reverses this basic fact; the correct answer is anticlinal structures of sedimentary rocks."),
"GEO-J00043": ("keyed","C","Ocean surface currents are driven mainly by prevailing surface winds dragging the water in their direction of flow (modified by the Coriolis effect and coastlines), which is the standard explanation for wind-driven ocean circulation. Agrees with external candidate."),
"GEO-J00044": ("keyed","A","The Coriolis effect, caused by the earth's rotation, deflects moving air to the right in the Northern Hemisphere and to the left in the Southern Hemisphere, producing the characteristic NE and SW trending wind flows (e.g. NE trade winds, SW monsoon) in the northern tropics. Agrees with external candidate."),
"GEO-J00045": ("keyed","B","Of the given options, only the ozone-layer effect fits as a large-scale atmospheric consequence taught alongside rising CO2/greenhouse gas concerns in basic geography texts of this era (the other options - falling temperature, rising air pressure, reduced visibility - do not describe recognised effects of CO2 buildup). Agrees with external candidate, though noting strict atmospheric chemistry attributes ozone depletion mainly to CFCs rather than CO2; this is the intended textbook-level answer among the choices given."),
"GEO-J00046": ("keyed","D","Nimbostratus is the thick, low, grey rain-cloud type specifically associated with continuous, steady precipitation, as opposed to cumulus (fair weather/showery), stratus (drizzle/overcast) or stratocumulus (patchy, little rain). Agrees with external candidate."),
"GEO-J00047": ("keyed","D","Tropical rainforest is markedly more diverse in plant/tree species (structurally complex, multi-layered canopy) than savannah, which is dominated by grasses with scattered trees and far fewer species - a standard structural/compositional contrast between the two biomes. Agrees with external candidate."),
"GEO-J00048": ("keyed","C","Tropical rainforest is the principal source of commercial tropical hardwoods (e.g. iroko, mahogany, obeche) due to its vast stock of mature broadleaved trees, unlike montane or mangrove forest (limited extent/species) or coniferous forest (source of softwood, not hardwood). Agrees with external candidate."),
"GEO-J00049": ("keyed","A","In humid regions, high rainfall percolating through the soil dissolves and carries away (leaches) soluble plant nutrients/minerals, leaving soils less fertile - a classic soil-management problem of humid climates. Agrees with external candidate."),
"GEO-J00050": ("keyed","A","Laterization (formation of laterite, iron/aluminium-oxide-rich soil) results from intense leaching and chemical weathering under high temperature and heavy rainfall, conditions characteristic of the humid tropics. Agrees with external candidate."),
"GEO-J00051": ("keyed","D","Shifting cultivation is defined by farmers clearing and cropping one plot for a few seasons, then abandoning it to move to (and clear) another plot, allowing the original land to lie fallow and regenerate its fertility - the defining 'shifting' element among the options. Agrees with external candidate."),
"GEO-J00052": ("keyed","B","Power supply, market access and raw materials are all direct, tangible pulls on where an industry locates; climate has comparatively little direct bearing on industrial location decisions (aside from a few climate-sensitive industries), making it the least important of the four. Agrees with external candidate."),
"GEO-J00053": ("keyed","D","Iron and steel manufacture requires iron ore and coal (coke) as the core inputs, plus limestone, which is charged into the blast furnace as a flux to combine with impurities and form slag - limestone is the raw material among the options genuinely used in this industry (copper, bauxite and columbite are unrelated to steelmaking). Agrees with external candidate."),
"GEO-J00054": ("keyed","C","Industrial development, soil fertility and transport development all directly shape where people concentrate; a place's longitude (east-west position) by itself has no inherent bearing on population distribution (unlike latitude, which correlates with climate), making it the least relevant factor. Agrees with external candidate."),
"GEO-J00055": ("keyed","D","In 1991, Southeast Asian countries were widely characterised in development/population geography as having high rates of natural increase (high birth rates against falling death rates), producing rapid population growth that strained resources and services - the dominant demographic concern of the period for the region. Agrees with external candidate."),
"GEO-J00056": ("keyed","C","The rate of natural increase (births minus deaths) becomes the overall rate of population growth once it is adjusted for net migration (immigration minus emigration); 'fertility rate' refers specifically to average births per woman and is unrelated to migration adjustment. OVERRIDE: external candidate (A, fertility rate) misapplies this term; the correct definitional match is rate of population growth."),
"GEO-J00057": ("keyed","C","Rural-urban migration removes people (often working-age) from the rural source area, reducing its population - i.e. rural depopulation. Urban congestion/depopulation describe effects at the destination, not the source region. Agrees with external candidate."),
"GEO-J00058": ("keyed","C","Nucleated (clustered) rural settlements classically arise under traditional subsistence farming, where farmers with fragmented small landholdings live together in a compact village for social/security/cooperative reasons and walk out daily to scattered surrounding plots. Large-scale/mechanized farming, by contrast, typically produces dispersed settlement (isolated farmsteads on large consolidated holdings), since there is no need to cluster. OVERRIDE: external candidate (B, large-scale farming) points to the pattern associated with dispersed settlement, not nucleated; subsistence farming is the better fit."),
"GEO-J00059": ("keyed","D","Classical urban-evolution theory (e.g. Childe's 'urban revolution') identifies agricultural food surplus (freeing part of the population from farming), division of labour/specialisation, and the need for defence as the core drivers of city formation; climate is not one of the standard factors cited in this theory. OVERRIDE: external candidate (C, transport/defence/climate) substitutes climate for food surplus and division of labour, which are the textbook factors; the correct combination is food surplus, defence and division of labour."),
"GEO-J00060": ("keyed","C","Read as asking for the Far East terminal ports on the Atlantic-to-Far-East shipping route, Hong Kong, Singapore, Manila and Tokyo are the recognised major Far East terminus ports for this route (the other options mix in ports - Bombay/Colombo/Vancouver, or Rotterdam/London/Hamburg - that belong to different routes/regions). Agrees with external candidate."),
"GEO-J00061": ("keyed","D","Mediterranean African fruit-exporting countries (e.g. Morocco, Tunisia, Algeria) inherited colonial-era transport infrastructure (ports, railways, shipping lines) built to link them to Western Europe, while transport links across Africa itself remained (and remain) poorly developed - a standard explanation in African economic geography for export orientation toward former colonial partners rather than neighbouring African markets. OVERRIDE: external candidate (C, higher demand in Western Europe) is a plausible-sounding but secondary explanation; the textbook 'best' answer for this classic pattern is the transport-infrastructure orientation."),
"GEO-J00062": ("keyed","B","Fishing, lumbering, farming and mining are all primary-sector activities (direct extraction/production from nature); every other option mixes in a secondary or tertiary activity (manufacturing, transportation, banking or trading), so only this set is 'completely primary'. Agrees with external candidate."),
"GEO-J00063": ("keyed","D","Coal's relative decline as an energy source is mainly attributed to the rise of alternative energy sources (oil, natural gas, hydroelectricity, nuclear power) that are cheaper, cleaner or more convenient to use and transport, not to declining demand per se or unavailability of coal. Agrees with external candidate."),
"GEO-J00064": ("keyed","B","Off Canada's east coast (Grand Banks), the mixing of the cold Labrador Current with the warmer Gulf Stream creates conditions that support an abundance of plankton, which in turn sustains large fish populations and hence large-scale commercial fishing - plankton abundance is the direct biological driver of the rich fishing grounds. Agrees with external candidate."),
"GEO-J00065": ("keyed","A","Crop distribution across Nigeria's ecological zones is primarily governed by climate (rainfall amount/distribution, temperature) and soil type/fertility, which together determine which crops can be grown where. Agrees with external candidate."),
"GEO-J00066": ("keyed","D","Anambra and Abia States lie within Nigeria's humid forest zone, which harbours the tsetse fly - the vector for trypanosomiasis (a fatal cattle disease) - making large-scale cattle rearing there impractical; this is a standard textbook explanation for the concentration of cattle rearing in the drier, tsetse-free northern savanna. Agrees with external candidate."),
"GEO-J00067": ("keyed","A","The Niger Delta (swampy, difficult terrain) and parts of Niger State (semi-arid interior with poor soils/limited water) are recognised areas of sparse population in Nigeria; the alternative options all pair in Kano, Ibadan or Osun, which are among Nigeria's most densely populated areas, ruling those options out. Agrees with external candidate."),
"GEO-J00068": ("review","","Genuinely uncertain which soil description is correct for cotton cultivation in Northern Nigeria. Cotton generally favours well-drained sandy loam soils (a widely taught agronomic fact, supporting option A), and this is what I lean towards, but I cannot rule out the more specific 'well drained dark clay loam' (B) or 'light, loose sandy soils' (C, the external candidate) without a definitive regional soils reference. Holding for review - candidates under consideration: A (own reasoning, moderate confidence) vs C (external_candidate)."),
"GEO-J00069": ("keyed","D","Mineral resource occurrence is fundamentally a function of the geological history and rock formations of an area (igneous, sedimentary, metamorphic processes, ore-forming events), not of surface vegetation cover, which has no causal bearing on subsurface mineral deposits. OVERRIDE: external candidate (C, vegetation) is a basic-level error; the correct answer is geology."),
"GEO-J00070": ("keyed","C","Lake Chad and its basin support both fishing (in the lake and its rivers) and irrigation agriculture (e.g. the South Chad Irrigation Project drawing on lake/river water for crops such as wheat and rice), a well-established pairing in Nigerian regional geography. Agrees with external candidate."),
"GEO-J00071": ("keyed","C","Zaire (now DR Congo) contains the vast Congo Basin rainforest and is the African country most noted for lumbering/timber extraction among the options given (Chad, Uganda and Kenya are not major timber-producing countries). Agrees with external candidate."),
"GEO-J00072": ("keyed","C","Warmest month (July) = 19C, coldest month (January) = -11C; annual temperature range = 19 - (-11) = 30C, directly computable from the data given in the question text. Agrees with external candidate."),
"GEO-J00073": ("keyed","B","A large annual range (30C), a very cold winter minimum (-11C in January), and a precipitation maximum in summer (peaking July/August) are diagnostic of a continental 'cold temperate' climate (e.g. interior Russia/Canada type), rather than a milder maritime 'cool temperate' climate (which has much smaller ranges and rarely such low winter minima) or a Mediterranean climate (mild wet winters, dry summers - the opposite pattern). OVERRIDE: external candidate (C, cool temperate) understates the severity of the winter and the size of the range shown in the data; cold temperate is the better fit."),
"GEO-J00074": ("keyed","C","Africa's plateau-like relief means many rivers descend abruptly from the interior highlands to the coastal lowlands, creating rapids, cataracts and waterfalls (e.g. on the Congo and Zambezi) that interrupt navigation - the standard textbook reason African rivers are poor for through-navigation. Agrees with external candidate."),
"GEO-J00075": ("keyed","C","West African climate is controlled by the meeting of the dry Tropical Continental air mass (from the Sahara, bringing the harmattan) and the moist Tropical Maritime air mass (from the Atlantic, bringing the SW monsoon rains) along the Inter-Tropical Discontinuity - the standard air-mass terminology used in West African climatology. Agrees with external candidate."),
"GEO-J00076": ("keyed","B","The Gezira Plains scheme in Sudan (between the Blue and White Nile) is the classic, most cited example of large-scale irrigation agriculture in Africa (notably for cotton), taught as the standard textbook case. Agrees with external candidate."),
}

with open('key-1991-Geography_with_candidate.csv', newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

keyed_rows = []
review_rows = []
data_rows = []

for r in rows:
    qid = r['question_id']
    status, ans, expl = decisions[qid]
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
    if status == 'keyed':
        base['correct_option'] = ans
        base['explanation'] = expl
        keyed_rows.append(base)
    elif status == 'review':
        base['correct_option'] = ''
        base['explanation'] = ''
        base['reason'] = expl
        review_rows.append(base)
    else:
        base['correct_option'] = ''
        base['explanation'] = ''
        base['reason'] = expl
        data_rows.append(base)

def write_csv(path, rows, fieldnames):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

keyed_fields = ['question_id','subject','year','question_text','option_a','option_b','option_c','option_d','correct_option','explanation']
review_fields = keyed_fields + ['reason']

write_csv('key-1991-Geography_keyed.csv', keyed_rows, keyed_fields)
write_csv('key-1991-Geography_needs_review.csv', review_rows, review_fields)
write_csv('key-1991-Geography_needs_data.csv', data_rows, review_fields)

print("keyed:", len(keyed_rows))
print("review:", len(review_rows))
print("data:", len(data_rows))
print("total:", len(keyed_rows)+len(review_rows)+len(data_rows))

# verify all keyed rows have correct_option in A-D and non-empty explanation
bad = [r['question_id'] for r in keyed_rows if r['correct_option'] not in ('A','B','C','D') or not r['explanation'].strip()]
print("bad keyed rows:", bad)
