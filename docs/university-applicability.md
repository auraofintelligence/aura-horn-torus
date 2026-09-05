# A worldwide university map for the GAJRA Earth invitation

Proposal and source review: 5 September 2026. The scope is **all universities on Earth**, with useful categories for discovering possible contributions to the Global Association for Joyful Responsible Abundance on Earth. Australia, Oceania and treaty relationships are filters within that scope.

The user's chosen reference is [gajra-earth-claude-build](https://github.com/auraofintelligence/gajra-earth-claude-build). Its [current invitation](https://auraofintelligence.github.io/gajra-earth-claude-build/) asks people working with intelligent systems to help define Joyful Responsible Abundance together. The map can help identify institutions and networks to research for that invitation. The categories below describe possible relevance; they do not establish agreement, endorsement or willingness to participate.

## What counts as a university?

Keep three independent sources of evidence:

| Evidence axis | What it establishes | What it does not establish |
| --- | --- | --- |
| **National recognition** | The responsible authority's provider category and current status. Australia's [TEQSA National Register](https://www.teqsa.gov.au/national-register) is one practical starting point; each jurisdiction needs its equivalent. | A single worldwide definition, campus access or membership of an association. |
| **WHED listing** | A higher education institution meets the [World Higher Education Database's published criteria](https://whed.net/home.html), including national recognition, specified degree provision and graduate cohorts. | Every university or higher education provider on Earth: new institutions and providers outside those criteria need other evidence. WHED listing is also separate from IAU membership. |
| **ROR identity** | A stable research-organisation identity, aliases and relationships. [ROR's scope](https://ror.org/registry/) includes many organisation types involved in research. | Accreditation, recognition as a university, global university completeness or detailed campus coordinates. An `education` type should initially read **education organisation**, pending provider classification. |

Preserve recognised universities with no ROR ID using a local stable ID and their regulator's ID. Keep university colleges, institutes and other higher education organisations separately filterable. Avoid classifying from the English name alone. Mergers need predecessor/successor history so an old institution does not silently become a second current university.

Track coverage by jurisdiction: authoritative register, date checked, stated scope, recognised university count where available, matched institutions, unresolved identities and missing coordinates. Until those comparisons are done, use **worldwide university collection in progress** rather than **all universities mapped**. ROR's open dataset can provide a broad starting collection; WHED and other directories need their own reuse terms checked before bulk republication.

## Six useful filters

| Filter a visitor sees | Proposed fields | Evidence needed |
| --- | --- | --- |
| **Where** | Country/territory, locality, region, campus or organisation location; optional Australia agreement context | Source geography and coordinate quality. Agreement context is not an institutional exchange agreement. |
| **Institution and recognition** | Provider type, active/inactive status, recognising authority, national provider ID, WHED ID | Regulator or competent national authority; WHED as complementary evidence. Unknown remains selectable. |
| **Knowledge and capabilities** | Teaching fields, research fields and specific GAJRA-relevant programmes | Current course catalogue, research-centre page or programme page, with dates. Use [UNESCO ISCED-F](https://uis.unesco.org/en/files/isced-fields-education-and-training-2013-en-pdf) for teaching-field codes; keep research classifications explicitly separate. |
| **Ways to take part** | Public lectures, open learning, citizen science, community partnerships, maker facilities, exchange opportunities; online/in-person | A published service or opportunity, intended audience, costs, conditions and application dates. Institutional membership alone does not grant access. |
| **Peak bodies and networks** | Body, membership type, listed status, checked date, evidence URL | The body's membership list or an explicit current institutional statement. Absence from a checked page is not proof of non-membership. |
| **GAJRA invitation progress** | Not assessed, prospect, researched, invited, responded, interested, member; separate contact status where known | A deliberate project record at each step. Default is not assessed: directory inclusion establishes no contact history. Public views expose only information authorised for publication. |

Proposed capability tags are **AI alignment and civic deliberation; teaching and lifelong learning; open knowledge and shared infrastructure; ecology, food, water and energy; community care and accessibility; arts, music and play; co-operative governance and community economics**. Several can apply to one institution. Attach each tag to a named evidenced programme, with a short explanation of its possible contribution. A whole university should not acquire a capability because one paper contains a keyword.

For example, a public maker facility might support repair workshops; an ecology programme might support community observation; an arts programme might support shared celebrations. These are suggested uses to discuss with the people involved, not promises of their time or resources.

## Peak bodies: practical enrichment order

The initial [evidence sample](../data/university-applicability-evidence.json) now contains **15 membership assertions across 13 institutions and three bodies**, checked on 5 September 2026. It retains the original eight Universities Australia listings and adds four PIURN and three APRU listings. These are observed official listings, not a complete membership audit. Continue with these providers using their own lists and reviewing identity matches:

1. **[Universities Australia](https://universitiesaustralia.edu.au/our-universities/):** eight directly listed institutions already present in the Oceania collection.
2. **[PIURN](https://piurn.org/member-universities/):** University of the South Pacific, Fiji National University, University of Papua New Guinea and National University of Samoa. Membership attaches to the institution, including the USP parent organisation, rather than being copied to each campus.
3. **[APRU](https://www.apru.org/members/):** Australian National University, The University of Queensland and University of Auckland. ANU and UQ already have Universities Australia evidence, so the new assertions share those institution records.

For each network, investigate named programmes and their participation rules separately from membership: this is where relevant research, learning and cultural-exchange opportunities can be established.

Then extend through [IAU's member directory](https://www.iau-aiu.net/Members) and the [Association of Commonwealth Universities](https://www.acu.ac.uk/our-members/). These associations provide useful networks but do not cover all universities. Add national and regional associations as individual sources; a university may belong to several.

A peak body may itself become a GAJRA prospect. Its member universities remain independent prospects. Neither the body's interest nor a staff member's response authorises recording all its members as GAJRA participants.

## Interoperability without mixing entities

Use full identifier URLs where available. Maintain one organisation record linked to separate campus, service and event records. A service may be online or span campuses; an event needs a venue or online location plus timezone, dates and organiser. A city centroid remains a city-level location until a campus source supplies stronger evidence.

| Identifier or relationship | Proposed use |
| --- | --- |
| **ROR** | Institution identity; retain supplied parent, child, related, predecessor and successor relationships. |
| **National provider ID / Global WHED ID** | Recognition and higher education cross-references, each with its own source. |
| **ISNI / Wikidata** | Additional organisation identifiers when supplied or explicitly verified; preserve provenance and unresolved conflicts. [ROR's schema documents its identifier mappings](https://ror.readme.io/docs/ror-data-structure). |
| **ORCID** | A person's identifier and explicitly sourced affiliation. [ORCID supports ROR organisation links](https://info.orcid.org/documentation/integration-guide/working-with-organization-identifiers/). An affiliation is not consent to outreach or institutional representation. |
| **DOI** | A research output or dataset linked through deposited metadata. [DataCite documents ROR-supported affiliations and organisational roles](https://support.datacite.org/docs/what-is-the-research-organization-registry-ror). Keep the output distinct from the institution and its research topics. |
| **Local campus/service/event ID** | Stable links for entities without an appropriate external ID; never reuse an institution ID as the ID of every campus. |

Store each assertion as subject, property, value, source, checked date and evidence status. This lets another map consume the data and distinguish a regulator assertion, a network membership and a proposed GAJRA contribution. Record a source's own update date separately from our retrieval date.

## Invitation states need evidence

**Not assessed** is the catalogue default. **Prospect** means deliberately selected for investigation; **researched** means an applicability note exists; **invited** requires an actually sent invitation; **responded** requires a recorded response; **interested** requires explicit interest; **member** requires the association's applicable joining mechanism and confirmation from somebody authorised to represent that institution. Record declined, withdrawn and paused outcomes too, without treating these states as a compulsory linear funnel. Missing contact history must remain unknown.

The current [GAJRA sign-on page](https://auraofintelligence.github.io/gajra-earth-claude-build/sign-on.html) describes signatures by people or systems. A person naming their university does not make that university a member. An institutional joining process therefore remains **to be defined with GAJRA and the institution**. Store a consented personal signature at person level if supplied, leaving the institution's relationship unchanged.

No invitations, messages or membership submissions were sent as part of this research. The 15 evidence assertions establish listings by the three named bodies only; all 13 institutions retain a GAJRA status of not assessed and no capabilities or contact histories are asserted.
