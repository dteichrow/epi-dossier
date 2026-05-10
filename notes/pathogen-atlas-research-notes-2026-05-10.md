# Pathogen Atlas Research Notes

Date: 2026-05-10
Project: The Pathogen Dispatch -> Pathogen Atlas
Purpose: Working evidence notes for a new atlas layer that maps likely origin zones, major spread routes, uncertainty, and linked Edge of Epidemiology writing without hoarding full-text PDFs locally.

## Design direction

- The correct precedent is the maritime disease atlas, not a generic card desk.
- The atlas needs to be geography-first, evidence-first, and explicit about uncertainty.
- The map layer should encode route logic, not just points.
- GPT Image 2 should be used for editorial plates and specimen-style art later, not for the evidence geometry.
- Remotion should stay optional and motion-only. The live atlas must remain HTML plus JS.

## Key structural decisions

- Launch with a small curated cohort, not an auto-generated pathogen dump.
- Prefer pathogens that already have strong disease sheets in `config/outbreak_reference.yml` so atlas links and reference links reinforce one another.
- Avoid storing full-text literature locally; keep compact citation metadata and URLs only.
- Use the Routledge handbook as a geography synthesis source, then add targeted papers where the route/origin claim needs tighter support.

## Routledge handbook takeaways

Source file reviewed:

- `/Users/devinteichrow/Downloads/Knowledge_System/04_Historical_Epidemiology_and_Public_Writing/Blog_and_Source_Material/Handbooks of ID/md/outledge-handbook-of-infectious-diseases-a-geographical-guide-3nbsped-1032550635-9781032550633-k-6632316.md`
- 31,973 lines
- DOI: `10.4324/9781003531425`

What the handbook is especially good for:

- disease spread through shipping, migration, and air travel
- regional infectious-disease ecology
- historical geopolitics of epidemic movement
- emerging infections and climate-linked redistribution

What the handbook is not enough for on its own:

- exact deep-origin arguments for every pathogen
- all pathogen-specific phylogeographic debates
- atlas-ready visual route simplification without additional interpretation

## Disease-specific notes pulled from the handbook

### Yellow fever

- The handbook is strong here.
- It explicitly frames yellow fever as carried from Africa with enslaved people and mosquito ecology.
- It places first reported New World epidemic in 1647, Yucatan in 1649, then spread to Cuba, Hispaniola, mainland America, and Philadelphia in 1793.
- It directly links yellow fever to:
  - the Philadelphia political story
  - the Haitian revolution / French military losses
  - Napoleon's New World collapse
  - French canal failure in Panama before mosquito transmission science

Atlas implication:

- Yellow fever should be a flagship atlas entry.
- It can anchor the maritime-to-political-history side of the atlas.
- It also has the strongest linked Edge of Epidemiology writing so far.

### Cholera

- The handbook places cholera's strong endemic geography in the Bay of Bengal / Ganges region.
- It explicitly says British trade routes and troop movements transformed local cholera outbreaks into epidemics.
- It gives a clean outward chronology:
  - Indian epidemic in 1503
  - 1817 major wave in Calcutta
  - spread through the subcontinent, Far East, Cuba and Mexico in 1833, Europe in 1835-37, Africa in 1837

Atlas implication:

- Cholera is a nearly ideal origin-and-route atlas disease.
- It should get route lines from Bengal outward rather than a vague global burden summary.

### Measles

- The handbook places measles in the colonial spread story with smallpox in the Americas.
- It emphasizes repeated spread into immunologically naive populations.
- It is good on later spread, but the deeper origin timeline still needs a stronger pathogen-specific paper.

Atlas implication:

- The origin pin should be explicitly marked as a reconstructed/divergence model, not a simple known historical event.
- The colonial routes into the Americas and islands are the stronger visual layer.

### Mpox

- The handbook gives a clean high-level route chain:
  - human recognition in DRC in 1970
  - additional West African cases
  - historical confinement to remote forested Central/West African settings
  - 2003 U.S. outbreak tied to imported Gambian pouched rats -> prairie dogs -> humans
  - 2017-18 Nigeria resurgence feeding later travel-linked cases
  - 2022 multinational outbreak tied to the West African clade / later global expansion

Atlas implication:

- Mpox should not be mapped as one static African origin story plus random dots elsewhere.
- It needs at least three route layers:
  - endemic forest-zone history
  - 2003 animal-trade jump
  - 2018-2022 travel/network expansion

### H5N1

- The handbook is strong on the modern route logic:
  - widely found in avian populations in Asia
  - later appearance in Europe and Africa
  - initially disseminated through migratory birds
  - now present in wild bird populations around the world
  - outbreaks in poultry farms and wild carnivores
  - 2024 dairy-cattle spread in the United States emphasized later in the chapter

Atlas implication:

- H5N1 should not be rendered like a human-travel route map.
- It needs a different visual grammar:
  - bird flyways
  - poultry/farm interface
  - mammalian spillover
  - exposed-worker layer

### Hantavirus

- The climate chapter references hantavirus in Latin America and the Caribbean and links infections to climatic factors.
- The handbook is less useful for a single-origin global narrative and more useful for ecology framing.

Atlas implication:

- Hantavirus needs an ecology-first atlas entry, not an empire/shipping route story.
- The key route story is really:
  - rodent-host geography
  - rural exposure settings
  - Andes-virus exception for person-to-person transmission

### Dengue

- The handbook is excellent on vector-driven geographic expansion.
- It highlights:
  - Aedes albopictus distribution through human activity
  - shipping and the reused tire trade
  - urbanization
  - spread across Europe, the Americas, Africa, and other temperate-edge zones

Atlas implication:

- Dengue belongs in the launch cohort because it gives us a modern infrastructure-and-vector atlas, not just a historical route atlas.

## Candidate launch cohort after handbook review

Strongest first-release atlas entries:

1. Yellow fever
2. Cholera
3. Measles
4. Mpox
5. Avian influenza A(H5N1)
6. Hantavirus syndrome
7. Dengue

Why this cohort works:

- all have strong geographic stories
- all have plausible route geometry
- most already have strong reference pages in the dossier
- they span distinct transmission grammars:
  - vector
  - waterborne
  - respiratory
  - wildlife trade
  - bird flyways
  - rodent ecology

## Edge of Epidemiology writing links currently located

Located in:

- `/Users/devinteichrow/Downloads/Work and Statistics/Blogs/edge-of-epidemiology-pitching-context-2026-05-01.md`

Known direct Substack links recovered:

- `The First American Epidemic: How Yellow Fever Exposed the Fault Lines of the Early Republic`
  - `https://theedgeofepidemiology.substack.com/p/the-first-american-epidemic-how-yellow`
- `How Mosquitos Killed Napoleon's North American Empire Dream`
  - `https://theedgeofepidemiology.substack.com/p/how-mosquitos-killed-napoleons-north`
- `Big Epidemiology: Disease at the Scale of Civilization`
  - `https://theedgeofepidemiology.substack.com/p/big-epidemiology-disease-at-the-scale`

Immediate atlas implication:

- Yellow fever is the most fully cross-linkable entry on day one.
- Cholera can likely use `Big Epidemiology` as adjacent context.
- Other entries should explicitly say `No dedicated post yet` instead of faking continuity.

## Citation candidates gathered during search

### Yellow fever

- Routledge handbook DOI: `https://doi.org/10.4324/9781003531425`
- Douam F, Ploss A. *Yellow Fever Virus: Knowledge Gaps Impeding the Fight Against an Old Foe.* Trends Microbiol. 2018.
  - `https://doi.org/10.1016/j.tim.2018.05.012`

### Cholera

- Mutreja A et al. *Evidence for several waves of global transmission in the seventh cholera pandemic.* Nature. 2011.
  - `https://doi.org/10.1038/nature09548`
- Hu D et al. *Origins of the current seventh cholera pandemic.* PNAS. 2016.
  - `https://doi.org/10.1073/pnas.1608732113`

### Measles

- Düx A et al. *Measles virus and rinderpest virus divergence dated to the sixth century BCE.* Science. 2020.
  - `https://doi.org/10.1126/science.aba9411`
- Moss WJ. *Measles.* Lancet. 2017.
  - `https://doi.org/10.1016/S0140-6736(16)31483-1`

### Mpox

- Croft DR et al. *Occupational risks during a monkeypox outbreak, Wisconsin, 2003.* Emerg Infect Dis. 2007.
  - `https://doi.org/10.3201/eid1307.061365`
- Bunge EM et al. *The changing epidemiology of human monkeypox—A potential threat?* PLoS Negl Trop Dis. 2022.
  - `https://doi.org/10.1371/journal.pntd.0010141`
- Mitjà O et al. *Monkeypox.* Lancet. 2023.
  - `https://doi.org/10.1016/S0140-6736(23)01574-0`

### H5N1

- Adlhoch C et al. *Avian influenza overview April-June 2023.* EFSA J. 2023.
  - `https://doi.org/10.2903/j.efsa.2023.8191`
- Briand FX et al. *Highly pathogenic Avian Influenza A(H5N1) Clade 2.3.4.4b Virus in Domestic Cat, France, 2022.* Emerg Infect Dis. 2023.
  - `https://doi.org/10.3201/eid2908.230188`
- Agüero M et al. *Highly pathogenic avian influenza A(H5N1) virus infection in farmed minks, Spain, October 2022.* Euro Surveill. 2023.
  - `https://doi.org/10.2807/1560-7917.ES.2023.28.3.2300001`

### Hantavirus

- Hjelle B, Torres-Pérez F. *Hantaviruses in the Americas and their role as emerging pathogens.* Viruses. 2010.
  - `https://doi.org/10.3390/v2032559`
- Martínez-Valdebenito C et al. *Person-to-person household and nosocomial transmission of Andes hantavirus, southern Chile, 2011.* Emerg Infect Dis. 2014.
  - `https://doi.org/10.3201/eid2008.131936`
- Douglas KO et al. *Influence of climatic factors on human hantavirus infections in Latin America and the Caribbean: A systematic review.* Pathogens. 2022.
  - `https://doi.org/10.3390/pathogens11010015`

### Dengue

- Kraemer MUG et al. *Past and future spread of the arbovirus vectors Aedes aegypti and Aedes albopictus.* Nat Microbiol. 2019.
  - `https://doi.org/10.1038/s41564-019-0376-y`
- Messina JP et al. *The current and future global distribution and population at risk of dengue.* Nat Microbiol. 2019.
  - `https://doi.org/10.1038/s41564-019-0476-8`

## Implementation notes for the atlas UI

- Use the maritime atlas architecture:
  - strong map center
  - evidence panel
  - selector rail
  - route emphasis
- Do not copy the pirate-specific scenario structure.
- Reuse its lessons:
  - route + point GeoJSON logic
  - side-panel storytelling
  - explicit narrative beats
  - map-first interaction

## Things to avoid

- no fake origin certainty for contested deep-history claims
- no decorative AI image used as evidence
- no huge local paper cache
- no turning the atlas into another generic card wall
- no one-size-fits-all route grammar across vector, waterborne, respiratory, and zoonotic diseases

## Next immediate tasks

1. Add `config/pathogen_atlas.yml`.
2. Add `graphics/atlas/manifest.yml`.
3. Add atlas loader + validation.
4. Add atlas export (`app_exports/atlas.json`, `docs/app_exports/atlas.json`).
5. Add `atlas.html` local and public page.
6. Add homepage atlas teaser and disease-sheet `View in Atlas` links.
7. Keep Remotion as scaffold only for now.
