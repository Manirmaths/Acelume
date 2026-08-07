import csv

src = "key-1992-Biology.csv"

KEYED = {
    "BIO-J00079": ("D", "Tissue (cellular) respiration, the breakdown of glucose to release ATP, takes place in the mitochondrion, the cell's powerhouse."),
    "BIO-J00080": ("C", "A tissue is a group of similar cells that are structurally alike and work together to perform the same function."),
    "BIO-J00081": ("D", "The fern life cycle alternates generations: the haploid prothallus bears spermatozoids and egg cells, fertilisation gives the leafy diploid sporophyte, which bears sporangia that release spores, closing the cycle."),
    "BIO-J00082": ("B", "Platyhelminthes are triploblastic (they have a mesoderm between ecto- and endoderm), whereas coelenterates are diploblastic and lack a true mesoderm."),
    "BIO-J00083": ("B", "Hydra (a coelenterate) is diploblastic, built from only ectoderm and endoderm, while the tapeworm (a flatworm) is triploblastic, having a mesoderm layer as well."),
    "BIO-J00084": ("A", "Flowering time in most plants is governed by photoperiodism, the duration of daylight (or darkness) they are exposed to."),
    "BIO-J00085": ("B", "Termites are hemimetabolous insects, developing through egg-nymph-adult stages (incomplete metamorphosis), unlike the mosquito, housefly and moth which undergo complete metamorphosis."),
    "BIO-J00086": ("B", "A bulb such as an onion is a much-reduced underground stem surrounded by thick, fleshy, food-storing leaves."),
    "BIO-J00087": ("D", "Guard cells change shape to open or close the stomatal pore, and this action is what actively controls the movement of air and water vapour into and out of the mesophyll."),
    "BIO-J00088": ("D", "Fungi lack chlorophyll and so cannot photosynthesise; they must obtain organic nutrients from other organisms, making them heterotrophic."),
    "BIO-J00089": ("A", "The palisade parenchyma, packed with chloroplasts and positioned just under the upper epidermis for maximum light capture, is the main site of photosynthesis in a leaf."),
    "BIO-J00090": ("D", "This is the Biuret test: dilute NaOH plus dilute copper sulphate gives a purple/violet colour in the presence of peptide bonds, indicating protein."),
    "BIO-J00092": ("C", "Under anaerobic conditions, plant and yeast cells ferment pyruvic acid into ethanol and carbon dioxide (alcoholic fermentation)."),
    "BIO-J00093": ("B", "Insects excrete nitrogenous waste via Malpighian tubules, which extract wastes from the haemolymph and empty them into the gut."),
    "BIO-J00094": ("C", "The atlas is the first cervical vertebra; its articulation with the occipital condyles of the skull is what allows the head to nod."),
    "BIO-J00095": ("D", "Pancreatic juice contains amylase (starch digestion), lipase (fat digestion) and trypsin (protein digestion); ptyalin and pepsin are salivary/gastric enzymes, not pancreatic."),
    "BIO-J00096": ("B", "Double fertilization in angiosperms produces both the diploid zygote (which becomes the embryo) and the triploid endosperm, from fusion of the two male gametes with the egg and the polar nuclei respectively."),
    "BIO-J00097": ("A", "The yolk (yolk sac) supplies early nutrients to the developing mammalian embryo before the placenta becomes fully functional; shock absorption is the role of amniotic fluid, not yolk."),
    "BIO-J00098": ("D", "In hypogeal germination the cotyledons stay below ground; it is the epicotyl that elongates to push the plumule upward, while the hypocotyl remains short."),
    "BIO-J00099": ("D", "Fruits that develop without fertilization of the ovule are termed parthenocarpic (seedless) fruits."),
    "BIO-J00100": ("A", "Sensory (afferent) neurons carry impulses from receptors in the body/internal organs toward the central nervous system."),
    "BIO-J00101": ("A", "A climax community is a stable, self-perpetuating end-stage of succession that persists unless the environment or climate changes."),
    "BIO-J00102": ("B", "A biological population is a group of organisms of the same species occupying an area that can interbreed freely with one another."),
    "BIO-J00103": ("C", "Moving up a predator food chain, each successive consumer tends to be larger in body size but fewer in number, reflecting the pyramid of numbers/energy loss between trophic levels."),
    "BIO-J00104": ("B", "Mangrove swamps develop in brackish, tidal conditions typically found where a river meets the sea (estuaries)."),
    "BIO-J00105": ("B", "Of the common soil particle grades (gravel, sand, silt, clay from coarsest to finest), clay has the smallest/finest particle size."),
    "BIO-J00106": ("A", "Malaria symptoms (fever, chills) arise mainly from toxins and debris released into the bloodstream when infected red blood cells rupture, releasing merozoites."),
    "BIO-J00107": ("C", "A haemophilic father (X-h Y) crossed with a homozygous normal mother (X-H X-H) gives all sons normal (Y from father carries no allele) and all daughters carriers (one X from each parent)."),
    "BIO-J00109": ("C", "RR (gametes: all R) crossed with Rr (gametes: R or r) gives offspring in a 1:1 ratio, i.e. 2RR : 2Rr out of 4 combinations; option B ('2RR, 2rr, 2rr') is a garbled/corrupted duplicate entry and was disregarded."),
    "BIO-J00110": ("B", "The offspring shows a new combination of traits (red fur with short ears) not present in either parent, the classic sign taught at this level that the two genes assort independently, i.e. are not linked."),
    "BIO-J00111": ("B", "Pawpaw is normally cross-pollinated (dioecious, highly out-crossing), so seeds collected from a good tree are genetically variable; uncontrolled out-crossing can introduce unwanted variation, unlike true-to-type vegetative propagation."),
    "BIO-J00112": ("C", "Colour blindness is a recessive, X-linked trait; because women have two X chromosomes, a single recessive allele is usually masked by a normal dominant allele on the other X, so they rarely show the trait."),
    "BIO-J00113": ("C", "DNA (deoxyribonucleic acid) is the hereditary material that carries genetic information from generation to generation."),
    "BIO-J00114": ("A", "Xerophytes adapt to dry environments by developing fleshy, water-storing tissue and reduced leaf surface area to minimise water loss."),
    "BIO-J00115": ("D", "Salinity is generally negligible and fairly constant in freshwater habitats, unlike turbidity, temperature and pH, which commonly vary and affect freshwater organisms."),
    "BIO-J00116": ("B", "The theory of evolution by natural selection was jointly developed and presented by Charles Darwin and Alfred Russel Wallace in 1858."),
    "BIO-J00117": ("A", "Sedimentary rock strata preserve fossils characteristic of the organisms living when each layer was formed, providing a chronological record supporting evolutionary change over time."),
}

REVIEW_REASON = {
    "BIO-J00091": "None of the options (tracheoles, bronchi, air sacs, trachea) is scientifically the true site of gas exchange in birds (the parabronchi/lung tissue, missing from the option list); 'air sacs' is the commonly assumed textbook answer but is scientifically imprecise (air sacs mainly store/circulate air, lacking the dense capillary beds of parabronchi). Needs human judgment on intended answer.",
    "BIO-J00108": "Question wording is ambiguous between 'genotype' and 'phenotype'. Read literally as genotype, a mother of OO(ii) combined with a father of genotype A, B, or AB would all produce a child genotype different from both parents - three options work. Only under a phenotype (blood-group) reading does father=AB become the unique answer (child would show type A or B, never AB or O). Needs human judgment on which reading was intended.",
}

with open(src, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total source rows: {len(rows)}")

keyed_rows = []
review_rows = []
data_rows = []

out_fields = ["question_id","subject","year","question_text","option_a","option_b","option_c","option_d","correct_option","explanation"]
review_fields = out_fields + ["reason"]

for row in rows:
    qid = row["question_id"]
    base = {
        "question_id": qid,
        "subject": row["subject"],
        "year": row["year"],
        "question_text": row["question_text"],
        "option_a": row["option_a"],
        "option_b": row["option_b"],
        "option_c": row["option_c"],
        "option_d": row["option_d"],
    }
    if qid in REVIEW_REASON:
        r = dict(base)
        r["correct_option"] = ""
        r["explanation"] = ""
        r["reason"] = REVIEW_REASON[qid]
        review_rows.append(r)
    else:
        entry = KEYED.get(qid)
        if entry is None:
            raise SystemExit(f"Missing mapping for {qid}")
        correct, expl = entry
        if not correct:
            raise SystemExit(f"Empty correct_option for keyed row {qid}")
        r = dict(base)
        r["correct_option"] = correct
        r["explanation"] = expl
        keyed_rows.append(r)

print(f"Keyed: {len(keyed_rows)}  Review: {len(review_rows)}  Data: {len(data_rows)}")
assert len(keyed_rows) + len(review_rows) + len(data_rows) == 39

def write_csv(path, fields, data):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in data:
            w.writerow(r)

write_csv("key-1992-Biology_keyed.csv", out_fields, keyed_rows)
write_csv("key-1992-Biology_needs_review.csv", review_fields, review_rows)
write_csv("key-1992-Biology_needs_data.csv", review_fields, data_rows)

print("Done.")
