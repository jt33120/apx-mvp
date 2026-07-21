# 04 — Competitive Landscape: AI Tools Sold to Law Firms (France / Luxembourg / EU)

**Research date: 20 July 2026.** Priority given to sources from the last 12–18 months. Every substantive claim carries a source URL and the date of that source.

## How to read this document

| Tag | Meaning |
|---|---|
| **[VENDOR]** | The vendor's own marketing or documentation. Self-declared. Not independently verified. |
| **[INDEP]** | Independent reporting, regulator/primary institutional document, or court decision. |
| **[UNVERIFIED]** | Could not be confirmed against a credible source. Stated as a gap, not filled with a guess. |
| ⚠️ **SEO** | Source is an SEO/affiliate blog or a competitor's "comparison" page. Directionally useful, not citable as fact. |

**Source-quality warning.** The French-language "comparatif IA juridique" search space is saturated with SEO content, much of it written by vendors about their competitors (`zevra.tech`, `alphadeep.fr`, `foxpilot.io`, `optimumia.fr`, `aivortex.io`, `vaquill.ai`, `bindlegal.com`, `spellbook.com/learn/*`, `gc.ai/blog`, `legalfly.com`). These recycle each other's unsourced numbers. Where a figure below comes only from such a source it is flagged ⚠️ SEO. Trustworthy sources used: vendor primary pages and security/sub-processor documentation, `cnb.avocat.fr`, `ccbe.eu`, `cnil.fr`, `cyber.gouv.fr` (ANSSI), `justice.gouv.fr`, `courdecassation.fr`, `senat.fr`, Le Monde du Droit, LeMagIT, Le Monde Informatique, Artificial Lawyer, Legal IT Insider, Law.com/LawSites, The Lawyer, City AM, TechCrunch, tech.eu, Morgan Lewis, Freshfields, Gibson Dunn.

---

## 0. Executive orientation — what changed in the last 12 months

Five structural facts that reframe the whole exercise:

1. **Capital has decided this is a winner-take-most market.** Harvey raised $200M at an $11B valuation in March 2026 (~$190M ARR, 1,300 organisations, 100,000+ lawyers) — [CNBC, 25 Mar 2026](https://www.cnbc.com/2026/03/25/legal-ai-startup-harvey-raises-200-million-at-11-billion-valuation.html). Legora closed a $600M Series D at $5.6B in April 2026 (~$100M ARR), with Nvidia and Atlassian on the cap table — [TechCrunch, 30 Apr 2026](https://techcrunch.com/2026/04/30/legal-ai-startup-legora-hits-5-6-valuation-and-its-battle-with-harvey-just-got-hotter/); [Tech.eu, 30 Apr 2026](https://tech.eu/2026/04/30/legora-extends-series-d-to-600m-with-backing-from-atlassian-and-nventures-reaching-56b-valuation/).
2. **Both are now physically in Paris.** Harvey opened a Paris base (announced Jan 2026, opened May 2026) with named French clients including Bredin Prat, CMS Francis Lefebvre and August Debouzy — [Artificial Lawyer, 15 Jan 2026](https://www.artificiallawyer.com/2026/01/15/harvey-to-open-paris-base-as-global-growth-continues/); [harvey.ai, 11 May 2026](https://www.harvey.ai/blog/harvey-opens-in-paris). Legora opened Paris, Madrid and Milan in Q3 2026 — [Maddyness, 10 Jun 2026](https://www.maddyness.com/2026/06/10/legora-la-legaltech-suedoise-de-lia-juridique-sinstalle-a-paris/).
3. **The French "sovereign champion" is being bought by a foreign group.** RELX (LexisNexis' parent) signed a put-option agreement to acquire Doctrine on 28 April 2026 — [GlobeNewswire/RELX, 28 Apr 2026](https://www.globenewswire.com/news-release/2026/04/28/3282631/0/en/relx-group-enters-into-agreement-to-acquire-french-legaltech-company-doctrine.html); [Global Legal Post](https://www.globallegalpost.com/news/lexisnexis-owner-relx-agrees-to-acquire-french-legal-ai-platform-doctrine-829269207). Doctrine had itself absorbed Predictice in September 2025 — [Maddyness, 17 Sep 2025](https://www.maddyness.com/2025/09/17/doctrine-absorbe-son-rival-francais-predictice/). French legal-data consolidation is now essentially complete and Anglo-Dutch-owned.
4. **Consolidation has also produced a casualty.** Robin AI — a top-5 name 18 months ago — was listed for distressed sale in October 2025 after a $50M raise fell through, then hit with an HMRC winding-up petition; its managed-services arm went to Scissero and its engineering team to Microsoft — [Legal IT Insider, 28 Oct 2025](https://legaltechnology.com/robin-ai-listed-for-distressed-sale-nine-months-after-making-the-sunday-times-100-tech-list/); [City AM](https://www.cityam.com/nik-storonsky-backed-robin-ai-seeks-rescue-buyer-after-fundraise-falls-short/); [The Lawyer](https://www.thelawyer.com/robin-ai-faces-hmrc-winding-up-petition-as-it-seeks-rescue-buyer/). Being a well-funded legal AI company is not, by itself, survival.
5. **The regulatory tailwind APX may be counting on is weaker than it looks.** Legal AI *sold to law firms* is almost certainly **not** high-risk under the EU AI Act (see §6), and the high-risk regime has in any case been deferred to December 2027. The real regulatory tailwind is **deontological, not statutory**: the CNB's March 2026 guide and the CCBE's March 2026 technical guide. Those are genuinely favourable — but they are guidance, not obligations enforced by a regulator.

---

## 1. Direct competitors — drafting and cited Q&A over a firm's own corpus

### 1.1 Global platforms

| Vendor | What it actually does | Sells to | Public pricing | Hosting / sovereignty | Traction / funding |
|---|---|---|---|---|---|
| **Harvey** (US) | Agentic assistant + workflows over firm documents and licensed content; "Vault" for document sets; deep-research and drafting agents. | Am Law / Magic Circle / large corporates; increasingly Continental firms. | None published. Reported $1,000–2,000/seat/month mid-market; $100–200/seat at Am Law-100 volumes; TCV $50k–$300k+; 25–50 seat minimums — ⚠️ SEO ([costbench](https://costbench.com/software/ai-legal-tools/harvey-ai/), [eesel](https://www.eesel.ai/blog/harvey-ai-pricing)). Treat the *shape* (annual, seat-minimum, six-figure) as reliable; the *numbers* as indicative. | **[VENDOR]** Azure-hosted; "processing in the EU and Switzerland or Australia" for localisation requirements. No on-prem. SOC 2 II, ISO 27001/27701/42001 — [harvey.ai/security](https://www.harvey.ai/security). Models: Anthropic, OpenAI, Google; **Mistral Large 3 in Early Access for EU customers** — [eu.help.harvey.ai](https://eu.help.harvey.ai/articles/what-ai-models-does-harvey-use). | $11B valuation, ~$190M ARR, 1,300 orgs (Mar 2026). |
| **Legora** (SE, ex-Leya) | Collaborative "Tabular Review", drafting in Word, agents over firm corpus + public sources. Acquired Qura (legal research) — [legora.com](https://legora.com/newsroom/legora-acquires-qura-to-build-the-world%E2%80%99s-leading-ai-native-legal-research-platform). | Global firms (White & Case, Linklaters) and corporate legal (Barclays). | None published. Reported ~$3,000/user/yr list with 10-seat minimum (~$30k floor) — ⚠️ SEO. **Verified model change:** moved Agent Pro to **consumption-based pricing** in June 2026, added matter-level cost tracking — [Unfiltered Bits, 23 Jun 2026](https://unfilteredbits.substack.com/p/legal-ai-wont-be-priced-per-seat). | **[VENDOR]** Regional residency (EU/US/APAC), BYOK. **Its own EU sub-processor list names Microsoft, AWS, Google and OpenAI as EU/EEA processors** — [legora.com/legal/eu-pre-approved-sub-processors](https://legora.com/legal/eu-pre-approved-sub-processors). ISO 27001/42001, SOC 2. **No on-prem.** | $5.6B valuation, ~$100M ARR (Apr 2026). |
| **Robin AI** (UK) | Contract review/drafting. | Corporates + firms. | n/a | AWS, region unnamed — [robinai.com/security](https://robinai.com/security). | **Effectively dead as an independent competitor** (see §0.4). |
| **Spellbook** (CA) | Contract drafting/review in Word. | Small and mid-size firms, transactional. | Reported ~$100–200/seat/month ⚠️ SEO. | **[VENDOR]** AWS `ca-central-1`; "data centers in Canada and US". **No EU data residency option stated** — [spellbook.com/security](https://spellbook.com/security). | On track for ~$100M ARR 2026; took a $40M RBCx debt facility in March 2026 to buy small competitors — [BetaKit](https://betakit.com/on-track-to-hit-100-million-usd-arr-spellbook-partners-with-canadian-bar-association/). Not a France play. |
| **Luminance** (UK) | Contract/document analysis, proprietary "Luna Crescent" model. | Mid-to-large firms and corporates. | Not published. | **[VENDOR]** The only mainstream vendor publishing a customer-environment deployment claim: dedicated single-tenant instance "whether hosted within a virtual cloud environment **or deployed within their own environment**" — [luminance.com/security](https://www.luminance.com/security/). **Whether the LLM itself runs on customer hardware, at what price, and at what minimum size: [UNVERIFIED].** | — |
| **LexisNexis — Lexis+ with Protégé** (RELX) | Research + drafting + agentic "skills", Shepard's citation validation. | Firms of all sizes, corporates, public sector. | Quote only. France launch **September 2026** ⚠️ SEO ([alphadeep](https://www.alphadeep.fr/guides/prix-ia-juridique-france-2026), 7 Jul 2026). | **[INDEP]** As of Oct 2024, ran on "dedicated private instances in Microsoft Azure and AWS" with OpenAI + Anthropic; EU hosting was "coming soon" — [LeMagIT, 21 Oct 2024](https://www.lemagit.fr/actualites/366614098/IA-generative-et-droit-dans-les-coulisses-de-lassistant-juridique-de-LexisNexis). **[INDEP, 15 Jul 2026]** LexisNexis announced integration of **Mistral** models into Lexis+ with Protégé in France, encrypted and hosted in Europe, prompts not used for training, conversations auto-deleted after 90 days — [Archimag, 15 Jul 2026](https://www.archimag.com/veille-documentation/2026/07/15/information-juridique-lexisnexis-integre-mistral-plateforme). May 2026 release added customer-held encryption keys — [LawSites, May 2026](https://www.lawnext.com/2026/05/lexisnexis-expands-lexis-with-protege-adding-agentic-skills-collaboration-workrooms-and-customer-held-encryption-keys.html). | Acquiring Doctrine; already owns Case Law Analytics ([lexisnexis.com/fr-fr](https://www.lexisnexis.com/fr-fr/produits/case-law-analytics)). |
| **Thomson Reuters CoCounsel** | Research + drafting, Westlaw/KeyCite-grounded citation checking. | Firms and corporates. | Quote only. | **[UNVERIFIED]** No published EU data-residency commitment or named EU region found. | — |
| **vLex Vincent** (now Clio) | Research + drafting with jurisdiction-aware retrieval. | Firms of all sizes. | Quote only. | **[VENDOR]** Region choice incl. **EU**, customer-held master keys in HSMs; ISO 27001 (Jun 2025), SOC 2 (Jan 2025) — [vlex.com/security](https://vlex.com/security). | — |

### 1.2 French and Continental entrants — this is where APX actually competes

| Vendor | What it does | Sells to | Pricing (public) | Hosting posture | Traction |
|---|---|---|---|---|---|
| **Septeo — Secib / "Brain"** | ⚠️ **The single closest competitor to the APX concept.** AI assistant natively embedded in the Secib practice-management system, reading firm case files **without prior export or anonymisation**, processing up to 100 documents at once, drafting conclusions and actes, extracting fact chronologies. Marketed as "Intelligence métier", **"100% sovereign AI agents"**, with searches run **exclusively on documents internal to the firm** to avoid inventing case law. | French law firms of all sizes, via an installed base of **7,500+ firms** on Secib. | Add-on to Secib Essential/Advanced/Elite; **"contactez notre équipe commerciale"**. | **[VENDOR]** "Données hébergées 100% en France, chez un cloud souverain", HDS-certified infrastructure, AES-256 at rest, TLS 1.2+, no client data used for training. **Cloud provider and LLM provider not named.** — [secib.septeo.com/solutions/ia-avocats](https://www.secib.septeo.com/solutions/ia-avocats) (accessed 20 Jul 2026) | Distribution through the dominant French practice-management incumbent. |
| **Haiku** (ex-Clerk, Bordeaux) | ⚠️ **Second-closest.** Indexes and exploits **all of a firm's internal documents**, natural-language retrieval, synthesis and reuse of accumulated case knowledge; legal research; Word integration. Founded 2023, 18 people. | French firms, solo → multi-lawyer; regional-bar go-to-market. | **[VENDOR]** **€19 HT/month** individual licence; **80% discount for Barreau de Bordeaux members**; multi-licence on quote — [haiku.fr/bordeaux](https://www.haiku.fr/bordeaux) (partnership announced **17 July 2026**). | **[VENDOR] The strongest sovereignty claim in the French market.** Hosted in France on **PREMI3NS — the "Cloud de confiance" from S3NS (Thales–Google Cloud), SecNumCloud-qualified by ANSSI**; ISO 27001 — [haiku.fr](https://www.haiku.fr/) (accessed 20 Jul 2026). ⚠️ **But note the gap:** S3NS's SecNumCloud 3.2 qualification (18 Dec 2025) covers IaaS/PaaS/CaaS and **explicitly excludes Vertex AI and other AI services** — [LeMagIT, 19 Dec 2025](https://www.lemagit.fr/actualites/366636681/S3NS-annonce-lobtention-de-sa-qualification-SecNumCloud). So the *application* may sit on qualified infrastructure while *inference* does not. **Models used: [UNVERIFIED]** — the site does not name them. | Raised **€3M** in 2026 after **€1.3M** end-2024 — [Le Journal des Entreprises](https://www.lejournaldesentreprises.com/breve/la-legaltech-bordelaise-haiku-leve-3-millions-deuros-2145526). Barreau de Bordeaux (2,200+ lawyers) as a live testbed — [French Tech Bordeaux](https://www.frenchtechbordeaux.com/nos-actualites/le-barreau-de-bordeaux-sallie-a-haiku-pour-equiper-ses-avocats-dun-assistant-juridique-intelligent). |
| **Jimini AI** (Paris) | Generative-AI copilot for lawyers and in-house: research over codes/case law **plus the firm's internal documents**, drafting, review. | Law firms and legal departments; explicitly targets 1–20-lawyer firms via the Paris Bar. | Quote only. **3 months free for Paris Bar firms of 1–20 lawyers** — [avocatparis.org](https://www.avocatparis.org/actualites/lia-le-barreau-en-action) (updated 8 Apr 2026). | **[VENDOR]** "100% hosting in France, with a sovereign cloud provider", **HDS-certified** infrastructure, ISO 27001, AES-256/TLS. **The provider is not named**; the widely repeated "Scaleway" attribution appears only in SEO blogs → **[UNVERIFIED]** — [jimini.ai](https://www.jimini.ai/en). | €1.9M seed (Polytechnique Ventures, J12, Evolem, Galion.exe) — [Le Monde du Droit](https://www.lemondedudroit.fr/professions/337-legaltech/89907-jimini-leve-1-900-000-pour-devenir-pour-devenir-le-leader-de-l-ia-juridique-en-europe.html). **Selected under France 2030** for the "Accélérer l'usage de l'IA générative dans l'économie" call — [Le Monde du Droit](https://www.lemondedudroit.fr/professions/337-legaltech/100497-france-2030-etat-choisit-jimini-ai-pour-accelerer-usage-ia-juridique.html). |
| **Ordalie** (Paris, Station F) | Sourced legal Q&A and drafting over certified French sources **plus the user's own documents**; proprietary models trained on French law, some open-sourced. | Solo practitioners, small firms, notaries, in-house. | **[VENDOR]** Free tier (10 queries/wk); Pro **<€60 HT/month**; commonly cited **€57–89/month** and **€69–99 HT/user/month** ⚠️ SEO. | **[VENDOR]** "Everything is hosted in France — both the application and the models we operate"; external model providers bound to no-retention **and** processing in France; SOC 2, ISO 27001 — [ordalie.com](https://ordalie.com/en/). Model providers not named. | €1.8M raised; **370+ clients** incl. TotalEnergies, SNCF, Radio France — [FrenchWeb](https://www.frenchweb.fr/18-million-deuros-pour-ordalie-la-legaltech-francaise-qui-veut-imposer-une-ia-juridique-souveraine-en-europe/455109). Barreau de Paris partner since 2024. |
| **Doctrine** (Paris) | Case law + legislation + editorial corpus with AI research, drafting, analytics. Absorbed **Predictice** (Sept 2025). | 27,000 legal professionals across FR/IT/DE/ES. | Quote only; ~€159/month cited ⚠️ SEO. | **[VENDOR]** "Nos serveurs sont hébergés à **Francfort, en Allemagne**", ISO 27001 since 2025, no transfers outside the EU — [doctrine.fr/securite](https://www.doctrine.fr/securite). Cloud and LLM providers undisclosed. | **Being acquired by RELX** (announced 28 Apr 2026). |
| **Lefebvre Dalloz — GenIA-L** | RAG over 200 years of Dalloz / Francis Lefebvre / Éditions Législatives doctrine + 4.5M decisions + collective agreements; exploration, analysis, drafting. | Lawyers, in-house, accountants. | **[VENDOR — published]** GenIA-L Avocat **from €213 HT/month** to €255.60 HT/month depending on configuration; 7-day trial — [boutique.lefebvre-dalloz.fr](https://boutique.lefebvre-dalloz.fr/genial-avocat.html). **Paris Bar negotiated 2026 rates: GenIA-L for Search €80/month, GenIA-L Assistant €220/month per user** — [avocatparis.org](https://www.avocatparis.org/actualites/lia-le-barreau-en-action). | **[INDEP]** Runs on **OpenAI** LLMs with RAG over Lefebvre Dalloz corpora — [Le Monde Informatique, 10 Mar 2025](https://www.lemondeinformatique.fr/actualites/lire-avec-genia-l-assistant-lefebvre-dalloz-complete-son-offre-ia-96250.html). European hosting claimed; specific provider **[UNVERIFIED]**. | Dominant editorial incumbent; free/unlimited to Paris solo and 2-lawyer firms through 31 Dec 2025 — a deliberate land-grab. |
| **Predictice** | Litigation outcome prediction + research. | Litigators. | ~€250 HT/month (annual) ⚠️ SEO. | EU. | Absorbed into Doctrine, Sept 2025. |
| **Case Law Analytics** | Judicial risk quantification over ~5M decisions. | Litigators, insurers. | Quote only. | **[UNVERIFIED]** LexisNexis France claims French servers; this sits uneasily with LeMagIT's Azure+AWS reporting for the AI layer. | **Owned by LexisNexis (RELX).** |
| **Noxtua / Beck-Noxtua** (DE) | Sovereign German legal AI with its **own** model ("Noxtua 5"), trained on beck-online. | German firms — **explicitly including very small ones**: self-service up to 4 employees, full-service 5+, and from spring 2026 entry **from 3 users** — [beck-noxtua.de](https://www.beck-noxtua.de/en/service/). | User-based; requires a beck-online PREMIUM subscription. | **[VENDOR]** European datacentres (IONOS, Open Telekom Cloud), independent of US hyperscalers; **BSI C5, TISAX, ISO 42001 (claims first German company certified), 27001/27017/27018, SOC** — [noxtua.com](https://www.noxtua.com/). **On-prem was reported in Apr 2025 press but is absent from both vendor sites in July 2026 → [UNVERIFIED].** | ~$92M raised Apr 2025 — [TechCrunch, 22 Apr 2025](https://techcrunch.com/2025/04/22/noxtua-raises-92m-for-its-sovereign-ai-tuned-for-the-german-legal-system/). **The closest thing in Europe to what APX says it wants to be — and it is already three years and $92M ahead.** |
| **Alizé** (LU) | Legal AI for **Luxembourg and Belgian** law (~150k documents, ~90k decisions). Launched Feb 2025, founded by two students. | Luxembourg/Belgian practitioners. | **[UNVERIFIED]** | **[UNVERIFIED]** — no security page found. | [alize.lu](https://alize.lu/); [L'essentiel, 2025](https://www.lessentiel.lu/fr/story/au-luxembourg-ils-creent-un-outil-incroyable-pour-les-professionnels-du-droit-103333739). The only Luxembourg-specific player identified. |

### 1.3 The bar associations are a distribution channel — and they are already taken

The Paris Bar (~35,000 lawyers) has negotiated member offers with **Lefebvre-Dalloz (GenIA-L), Pappers Justice, Doctrine, Ordalie, Jimini, Jarvis Legal and Cedie**, plus library access to JP Intelligence (Lexbase) and Lexis+ AI — [avocatparis.org, updated 8 Apr 2026](https://www.avocatparis.org/actualites/lia-le-barreau-en-action). The Bordeaux Bar (2,200+) signed with Haiku on 17 July 2026. **The "go via the bar" channel is not an open door; it is a queue behind seven incumbents.**

---

## 2. Document review / mass triage — the ordonnance 145 CPC use case

### 2.1 The use case is real but structurally narrow in France

Article 145 CPC ("instruction *in futurum*") lets a party obtain, ex parte, an order authorising a *commissaire de justice* — optionally with a police officer and an IT expert — to copy files held by the opponent. The order **must** specify how seized documents are sorted and released, and courts have built a practice of sorting by an impartial third party, out of the applicant's presence, to protect confidential material — [Squire Patton Boggs, La Revue](https://larevue.squirepattonboggs.com/la-recherche-de-preuves-de-l-article-145-du-code-de-procedure-civile-une-procedure-de-discovery-a-la-francaise_a2345.html); [Actu-Juridique](https://www.actu-juridique.fr/affaires/a-propos-de-larticle-145-du-code-de-procedure-civile-un-outil-moderne-de-lacces-a-la-preuve/). Operations last from two hours to several days and typically end with the bailiff leaving with a USB key or hard drive — [Cabinet Bouchara](https://www.cabinetbouchara.com/lexique/constat-145/).

That sorting step — potentially tens of thousands of documents, under time pressure, with *secret des affaires* and *secret professionnel* at stake, and no party allowed to see everything — is a genuine, underserved workflow. But note the structural constraint: **France has no discovery**, so there is no recurring, high-volume review market of the US kind. Article 145 is episodic. Sizing evidence for a French 145-triage market: **[UNVERIFIED]** — no market data found.

### 2.2 Vendor landscape

| Platform | EU hosting | On-premise | Who it serves | Pricing signal |
|---|---|---|---|---|
| **Relativity / RelativityOne** | RelativityOne offers regional instances incl. EU. | **Being eliminated.** Relativity set **1 Jan 2028** as the date after which all *new* matters must be on RelativityOne; Server sunsets in 2027; matters created before 31 Dec 2027 stay supported; limited geographic/use-case exceptions. **Server pricing rose from 1 April 2026** to reflect dual-environment support cost. >75% of Relativity's business has already moved to cloud — [LawSites, Jan 2025](https://www.lawnext.com/2025/01/putting-a-nail-in-the-coffin-of-its-on-prem-product-relativity-sets-2028-deadline-for-all-new-cases-to-move-to-the-cloud.html); [help.relativity.com/ServerSupport](https://help.relativity.com/ServerSupport/) | Large-scale litigation, service providers, corporates. Not sold to 30-lawyer firms directly. | Per-GB hosting + user fees, via partners. |
| **Everlaw** | GDPR/CCPA plus SOC 2 II, ISO 27001/27017/27018 claimed ⚠️ SEO for the EU-region specifics. | No. | Document-intensive litigation; mid-to-large. | Not published. |
| **DISCO (CS Disco)** | **[UNVERIFIED]** for EU regions. | No. | Litigation teams; markets "predictable pricing". | Not published. |
| **Reveal** | **[UNVERIFIED]** | **Explicitly marketing itself as the on-prem destination for Relativity Server refugees** — [revealdata.com](https://www.revealdata.com/blog/relativity-server-sunset-your-on-prem-ediscovery-path-forward-with-reveal) (vendor blog). | Enterprise/large litigation. | Not published. |
| **Casepoint, Exterro, ZyLAB (NL), Venio, Nuix, Logikcull** | Mixed; **[UNVERIFIED]** per-vendor for EU regions. Venio markets Cloud / On-Premise / Air-Gapped hybrid deployment ⚠️ SEO. | Venio (claimed), Nuix (historically). | Enterprise, government, regulators. | Custom quote across the board. |

### 2.3 In France the 145 triage market is a **services** market, not a software market

The named providers doing French document review and digital forensics are consultancies, not software vendors sold to law firms: **FTI Consulting France** ([fticonsulting.com](https://www.fticonsulting.com/fr-fr/france/services/e-discovery-managed-review)), **EY Discovery Services** ([ey.com/fr_fr](https://www.ey.com/fr_fr/services/assurance/discovery-services)), **KLDiscovery** ([kldiscovery.com/fr](https://www.kldiscovery.com/fr/solutions/forensics-informatique)), **Forensic Risk Alliance** ([forensicrisk.com](https://www.forensicrisk.com/expertise/ediscovery-edisclosure-and-digital-forensics)). A 20–40-lawyer firm running a 145 seizure buys **hours**, not a licence.

**Independent pricing benchmark** — ComplexDiscovery Winter 2026 eDiscovery Pricing Survey (fieldwork Dec 2025 – Feb 2026, n=53, **92.5% US respondents** — so read as a US benchmark, not a French one) — [ComplexDiscovery](https://complexdiscovery.com/buyers-guide/a-complete-analysis-of-the-winter-2026-ediscovery-pricing-survey/):

| Service | Modal price |
|---|---|
| Forensic collection (onsite/remote) | **$250–$350/hour** (56.6% of respondents) |
| Data hosting, basic | **<$10/GB/month** (54.7%) |
| Data hosting with analytics | **$15–$25/GB/month** (32.1%) |
| Document review, per document | **$0.50–$1.00** |
| **GenAI-assisted review, per document** | **$0.11–$0.50** — most cited band $0.26–$0.50 |

Two readings matter. First, **basic hosting has commoditised while analytics retains pricing power** — the survey's own framing. Second, **GenAI-assisted review at $0.11–$0.50/document is roughly an order of magnitude below human review at $0.50–$1.00** — which is where any 145-triage value proposition has to live.

### 2.4 What this means

- **Nobody is selling document-triage AI to European firms under 50 lawyers as a product.** Relativity/Everlaw/DISCO/Reveal all sell to large-scale litigation and service providers; French 145 work is absorbed by Big Four and forensics consultancies at consulting rates. **[UNVERIFIED]**: no European platform marketing mass triage specifically to 20–40-lawyer firms was identified.
- **Relativity is actively exiting on-premise.** That is simultaneously validation (on-prem demand exists — Reveal is chasing the refugees) and a warning (the market leader concluded on-prem is not worth supporting).
- **The 145 use case is a wedge, not a market.** Episodic demand, no sizing data, and the incumbent alternative is a forensics consultancy the firm already trusts.

---

## 3. Sovereignty and hosting posture

### 3.1 The honest picture

| Deployment reality | Vendors |
|---|---|
| **US-cloud, no stated EU residency** | Spellbook (`ca-central-1`, Canada/US), Robin AI (AWS, region unnamed), CoCounsel (**[UNVERIFIED]**) |
| **EU region on US hyperscaler infrastructure** | Harvey (Azure, EU + Switzerland), Legora (Microsoft/AWS/Google/OpenAI as EU sub-processors, per its own list), Lexis+ Protégé (Azure + AWS private instances; Mistral integration announced Jul 2026), vLex (EU region + customer-held keys), Doctrine (Frankfurt) |
| **France-hosted SaaS, US models under contract** | Jimini (HDS, provider unnamed), Ordalie (France, models "operated" in France, providers unnamed), Septeo Brain (French sovereign cloud, HDS, provider unnamed), GenIA-L (European hosting, **OpenAI models**) |
| **France-hosted SaaS on SecNumCloud-qualified infrastructure** | **Haiku only** — PREMI3NS / S3NS. Models unnamed; AI services are outside S3NS's qualification scope. |
| **European models + European infrastructure** | **Noxtua only** (own model, IONOS / Open Telekom Cloud) |
| **On-premise / customer hardware, productised for law firms** | **Nobody.** Luminance publishes a "customer's own environment" claim with no published terms or price. |

### 3.2 "EU region" does not equal immunity from extraterritorial access — and this is provable

- **Microsoft France's Director of Public and Legal Affairs, Anton Carniaux, testified under oath to the French Senate on 10 June 2025** that he could not guarantee French citizens' data would never be transmitted to US authorities: *"Non, je ne peux pas le garantir."* — [Sénat, compte rendu semaine du 9 juin 2025](https://www.senat.fr/compte-rendu-commissions/20250609/ce_commande_publique.html); [The Register, 25 Jul 2025](https://www.theregister.com/off-prem/2025/07/25/microsoft_exec_admits_it_cannot_guarantee_data_sovereignty/); [Forbes, 22 Jul 2025](https://www.forbes.com/sites/emmawoollacott/2025/07/22/microsoft-cant-keep-eu-data-safe-from-us-authorities/).
- **The CNIL says the same in writing.** On the EUCS scheme it warned the draft "ne permet plus aux fournisseurs de démontrer qu'ils protègent les données stockées contre tout accès par une puissance étrangère" and called for optional "immunity" criteria against extra-European laws, citing SecNumCloud as the existing model — [CNIL, 19 Jul 2024](https://www.cnil.fr/fr/cloud-les-risques-dune-certification-europeenne-permettant-lacces-des-autorites-etrangeres).
- **Mistral bought via Azure is still Microsoft infrastructure.** Mistral models on Azure AI Foundry deploy in West Europe (Amsterdam) and Sweden Central, but Microsoft operates inference and holds the weights — [Microsoft Tech Community](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/deepening-our-partnership-with-mistral-ai-on-azure-ai-foundry/4434656). Only Mistral's own API or a self-deployed licence puts the model outside US jurisdiction.
- **Correction to a widespread error:** the EU–US Data Privacy Framework has **not** been invalidated. The General Court dismissed the Latombe annulment action on 3 September 2025; a CJEU appeal (C-703/25 P) is pending — [WilmerHale, 1 Dec 2025](https://www.wilmerhale.com/en/insights/blogs/wilmerhale-privacy-and-cybersecurity-law/20251201-european-court-of-justice-to-review-challenge-to-eu-us-data-privacy-framework). Do not build a pitch on the DPF having collapsed.

### 3.3 SecNumCloud — the qualification nobody in legal AI has

- ANSSI's **in-qualification** list (fetched 20 Jul 2026) includes Adista, **Bleu SAS**, BLUE, Cegedim.cloud, Wimi, Ecritel, Free Pro, GIP Mipih, ITS Integra, **NumSpot**, Orange Business, OVH SAS, Prolival, **Scaleway**, Scalingo — [cyber.gouv.fr](https://cyber.gouv.fr/offre-de-service/solutions-certifiees-et-qualifiees/services-de-securite-evalue/solutions-en-cours-de-qualification/prestataires-secnumcloud/). The **qualified** roster (OVHcloud, Outscale, Cloud Temple, Oodrive, Orange Business, S3NS, Worldline, Whaller, Cegedim.cloud, Index Education) is reconstructed from converging secondary sources — ANSSI's own qualified-list URL returned 404 → **[PARTIALLY VERIFIED]**, re-check before quoting.
- **S3NS (Thales/Google) obtained SecNumCloud 3.2 on 18 Dec 2025** for IaaS + PaaS + CaaS in a single decision — but **Vertex AI is explicitly out of scope**: "il faudrait attendre une révision de la qualification pour que les solutions d'IA soient qualifiées SecNumCloud" — [LeMagIT, 19 Dec 2025](https://www.lemagit.fr/actualites/366636681/S3NS-annonce-lobtention-de-sa-qualification-SecNumCloud).
- **Exactly one legal-AI vendor claims SecNumCloud: Haiku**, via PREMI3NS/S3NS — [haiku.fr](https://www.haiku.fr/). Everyone else claims at best HDS (Jimini, Septeo), which is a *health-data hosting* certification, not a sovereignty qualification. **But the Haiku claim is narrower than it reads:** S3NS's qualification excludes AI services, so the claim plausibly covers application hosting and not model inference. **The precise scope of Haiku's SecNumCloud claim is [UNVERIFIED] and is the single most useful thing to pin down before positioning against them.**

### 3.4 Is anyone credibly selling **on-premise** legal AI to mid-size European firms today?

**No — not as a productised, priced offering.** That is the finding, and it is the strongest single piece of evidence for APX's thesis. But the reasons nobody has done it matter as much as the gap itself.

| Candidate | Reality | Source |
|---|---|---|
| **Mistral AI** | Le Chat Enterprise: "Deploy Le Chat anywhere: **self-hosted**, in your public or private cloud, or as a service." Mistral Compute (EU sovereign GPU platform, 40MW Paris-area DC, ~200MW by 2027). **No published pricing, enterprise contracts only, no 20–40-lawyer reference customer.** | [mistral.ai, 7 May 2025](https://mistral.ai/news/le-chat-enterprise/); [mistral.ai/products/compute](https://mistral.ai/products/compute/) |
| **Aleph Alpha / PhariaAI** | On-prem or private cloud, runs on STACKIT (Schwarz Group), no US hyperscaler at any layer, explainability layer. **Enterprise/government only; pricing undisclosed; 4–12 week deployments.** | [aleph-alpha.com/phariaai](https://aleph-alpha.com/phariaai/) |
| **Noxtua** | Sovereignty story is real; **on-prem availability today is [UNVERIFIED]** — reported Apr 2025, absent from vendor sites Jul 2026. Sells sovereign SaaS from 3 users. | [beck-noxtua.de](https://www.beck-noxtua.de/en/product/) |
| **IBM watsonx** | On-prem available; discount steps at $500K / $1.5M / $5M+ annual TCV — two orders of magnitude above a 30-lawyer firm. | [IBM watsonx pricing](https://www.ibm.com/products/watsonx-ai/pricing) |
| **Hardware vendors** | NVIDIA DGX Spark **$4,699** (128GB unified memory); deskside GB300-class **~$97K**. NVIDIA sells hardware, not a legal product. | [NVIDIA DGX platform](https://www.nvidia.com/en-us/data-center/dgx-platform/) |
| **Small integrators** | Real but tiny: e.g. `lawfirmautomate.com` advertises "a fully private, on-premise AI server for law firms"; French consultancies advertise RAG for 8–30-lawyer firms wired into the GED. **Consultancy engagements, not products; no verifiable references, no audited security posture.** ⚠️ vendor blogs. | — |

### 3.5 The CCBE has already written the on-prem manual — including the price list

This is the most important primary source for APX, and it cuts both ways. The **CCBE technical guide on the use of AI tools and models by lawyers, 27 March 2026** ([PDF](https://www.ccbe.eu/fileadmin/speciality_distribution/public/documents/IT_LAW/ITL_Guides_recommendations/EN_ITL_20260327_CCBE-technical-guide-on-the-use-of-AI-tools-and-models-by-lawyers.pdf)) sets out four deployment models in order — (1) on-premises/self-hosted devices, (2) self-hosted in colocation/private datacentre, (3) bring-your-own-model on IaaS, (4) fully managed SaaS — and states for option 1:

> "All data stays within user's infrastructure, which means that nothing is sent to an external cloud provider… The data is stored, processed, and reviewed at the lawyer's premises, and remains within the control of the lawyer. There is no transfer of data to a third person. This option may come with additional protections… against police search warrants."

It then publishes indicative hardware budgets (September 2025 prices, ex-VAT, excluding installation and deployment):

| Budget | What it buys | What it runs |
|---|---|---|
| €0 (existing computer) | Ollama / LM Studio / AnythingLLM as inference engine | Small models (deepseek-r1:1.5b), embedding models; larger models at "patient" speeds (~2.5 tok/s) |
| **~€2,000** | Motherboard, 128GB RAM, fast CPU, 2–4 inexpensive GPUs, 24GB VRAM | **20–40B parameter text models at comfortable speed** |
| Higher | NVIDIA RTX Pro 6000 (96GB) | OpenAI's GPT-OSS-120B; deepseek-r1:14b at ~114 tok/s |
| **~€20,000** | Server/workstation class | 8-bit quantised DeepSeek V3 671B or Qwen3-235B-A22B, "even if slowly" |
| €350k / €3M | DGX H100 / GB300 NVL72 | Frontier-scale |

And its Table 4 gives minimum specs per task: **drafting and revision = 7–8B, CPU sufficient; long-context RAG (200–500 pages) = 13–34B plus embeddings.**

**Read this carefully.** The European bar federation has published, for free, a guide telling every lawyer in Europe that a €2,000 machine runs a 20–40B model and that a 13–34B model plus embeddings handles 200–500-page RAG. That legitimises the on-prem *category* — and simultaneously destroys any pricing narrative built on hardware scarcity or technical mystique.

### 3.6 The on-prem economics objection APX must be able to answer

Independent cost analyses put the on-prem/cloud break-even at **~80% sustained GPU utilisation over three years**; under ~70% utilisation cloud wins TCO, and on-prem implies **0.5–1 FTE of ops per cluster** — [Spheron](https://www.spheron.network/blog/llm-inference-on-premise-vs-cloud/); [PCSP Local LLM Hardware Guide 2026](https://pcserverandparts.com/news/local-llm-hardware-guide-2026-servers-workstations-gpus/) (⚠️ hardware-adjacent sources; treat magnitude, not precision). **A 30-lawyer firm will never approach 80% GPU utilisation.** On-prem in this segment cannot be sold on cost. It can only be sold on *secret professionnel* — and on removing an entire category of risk from the managing partner's desk.

---

## 4. The verified-citation angle — marketing vs mechanism

### 4.1 What vendors claim

| Vendor | Claim | What it actually is |
|---|---|---|
| **Ordalie** | **[VENDOR]** "We maintain an **observed hallucination rate under 1%** in production"; "anchoring answers in verified legal sources… and **refusing to speculate**"; "relies solely on certified legal sources: codes, laws, case law, BOFiP, CNIL… updated daily" — [ordalie.com](https://ordalie.com/en/) | Grounded RAG over a curated corpus plus a refusal policy. **No published methodology, no independent audit, no definition of "hallucination". Unverifiable as stated.** |
| **Septeo Brain** | **[VENDOR]** Avoids inventing case law by searching **exclusively within the firm's own documents**. | A scope restriction, not a verification mechanism. It prevents fabricated *external* authority by never retrieving external authority. |
| **LexisNexis Protégé** | Shepard's Citations integrated to check whether a case remains good law. | Genuine post-hoc citator lookup against a proprietary, maintained database. The strongest mechanism class — and it depends on owning the citator. |
| **Thomson Reuters CoCounsel** | Inline citation check against Westlaw; flags overruled cases and mismatched citations via KeyCite. | Same class as above. Same dependency. |
| **Clearbrief** | "Verifies every citation exists, says what you claim it says, and hasn't been overruled"; Word-workflow integrated; LexisNexis integration. | Closest to a true verification product. US-centric. |
| **Harvey / Legora** | Grounded citations to source documents. | Retrieval provenance, not verification. |

### 4.2 What the evidence actually shows

- **Magesh et al. (Stanford RegLab), tools tested May 2024:** Lexis+ AI hallucinated on **17%** of queries; Westlaw AI-Assisted Research on **33%**; GPT-4 on 43% — despite both legal tools being marketed as hallucination-free — summarised in [AI Law Librarians, 19 Feb 2026](https://www.ailawlibrarians.com/2026/02/19/what-the-science-says-about-hallucinations-in-legal-research/).
- **Dahl et al. (2024):** GPT-4 58%, GPT-3.5 69%, Llama 2 88% hallucination on 800,000+ legal questions — ibid.
- **Vals Legal AI Report (testing Jul 2025, published Oct 2025):** best legal AI tools **78–81% accuracy**; ChatGPT with web search **80%**; human lawyer baseline **69%** — ibid. **The specialist tools' measured advantage over a general model with search was inside the noise.**
- **Curran et al. (2025), "Place Matters":** hallucination rates rose by jurisdiction — Los Angeles 45%, London 55%, Sydney 61% — with **local-law queries reaching 100% error rates**. Directly relevant to French and Luxembourg law.
- **2026 benchmark work:** `LegalCiteBench` and `LePhantomCite` show the best citation-checking agents "reliably detect non-existent cases and case name mismatches, but struggle with verifying pincites, misquotes, and content misrepresentations" — [arXiv 2606.21155](https://arxiv.org/html/2606.21155); [arXiv 2605.10186](https://arxiv.org/pdf/2605.10186).

**Mechanistic conclusion.** "Verified citation" splits into three tiers of increasing difficulty: **(a) the authority exists** — solvable deterministically against a database; **(b) it is still good law** — solvable only if you own or license a citator; **(c) it says what the brief says it says** — still unsolved at scale, and this is where the 2026 benchmarks fail. A vendor claiming "verified citations" without saying which tier is doing marketing.

### 4.3 France's structural advantage on tier (a)

Judilibre exposes Cour de cassation decisions via a free public API on PISTE (~480,000 decisions from 1947, plus first-instance and appellate criminal decisions phased in through 31 Dec 2025) — [Cour de cassation](https://www.courdecassation.fr/acces-rapide-judilibre/donnees-ouvertes-open-data-et-api); [data.gouv.fr](https://www.data.gouv.fr/dataservices/api-judilibre). Combined with Légifrance APIs, **tier (a) verification of French primary sources is a free, deterministic, offline-capable lookup.** This is a genuine and defensible technical claim — and it is also available to every competitor, and to any lawyer with an API key. It is table stakes, not a moat.

### 4.4 Publicised incidents of AI-fabricated citations (last 18 months)

**Scale.** The public AI Hallucination Cases database (Damien Charlotin) grew from ~200 cases in mid-2025 to **1,598 by 9 June 2026** — via [HAQQ](https://www.haqq.ai/blog/ai-legal-hallucination-audit) and [PlatinumIDS](https://blog.platinumids.com/blog/ai-hallucination-crisis-courts-2026) (⚠️ secondary; the database itself at [damiencharlotin.com/hallucinations](https://www.damiencharlotin.com/hallucinations/) returned 403 to automated fetch — verify counts directly before quoting).

**France** — all confirmed by [Morgan Lewis, 18 Mar 2026](https://www.morganlewis.com/pubs/2026/03/the-risks-of-hallucinations-and-misuse-of-generative-artificial-intelligence-before-french-courts):

| Court | Date | Case no. | Outcome |
|---|---|---|---|
| TA Grenoble | 3 & 9 Dec 2025 | 2509827, 2512468 | Noted submissions "clearly drafted using a generative AI tool". No penalty. |
| TJ Périgueux (pôle social) | 18 Dec 2025 | 23/00452 | First French decision noting fictitious case-law references. Warning. |
| **TA Orléans** | **29 Dec 2025** | **2506461** | ~15 entirely false references. Court directed counsel to "verify in the future that the references… do not constitute a 'hallucination'". **Warning only — no financial or professional penalty.** |
| TA Rennes | 28 & 30 Jan 2026 | 2506364, 2600610 | AI-generated motions rejected for legal insufficiency and jurisdictional errors. |
| **CAA Bordeaux** | **26 Feb 2026** | **25BX02906** | Repeated the Orléans language verbatim — the warning is propagating up the appellate chain. |

**Belgium** — [ICT Rechtswijzer](https://www.ictrechtswijzer.be/en/ai-hallucination-briefs/):
- **Commercial Court, Ghent, 15 Dec 2025**: the court itself queried Google's AI mode about three cited Cassation/Constitutional Court rulings and reproduced the answers showing they were fabricated.
- **Antwerp Court of Appeal, 4 Dec 2025**: persistent baseless claims held manifestly reckless; **€7,500 per opposing party**.
- **Antwerp Court of Appeal, 25 Mar 2026**: increased litigation costs awarded against a party whose AI-driven pleadings made proceedings chaotic.

**United States** — **Whiting v. City of Athens (6th Cir., March 2026)**: two attorneys sanctioned for briefs containing 20+ fake or misrepresented citations — **$15,000 punitive fine each plus full reimbursement of the opponent's appellate fees** ⚠️ secondary sources only ([GC AI](https://gc.ai/blog/ai-hallucination-legal-cases), [PlatinumIDS](https://blog.platinumids.com/blog/ai-hallucination-crisis-courts-2026)); verify the docket before citing in client materials.

**Luxembourg** — **[UNVERIFIED]**. No reported Luxembourg decision on AI-fabricated citations was found.

**United Kingdom** — ***Ayinde v London Borough of Haringey* and *Al-Haroun v Qatar National Bank* [2025] EWHC 1383 (Admin), Divisional Court (Dame Victoria Sharp P and Johnson J), 6 June 2025** — heard together under the court's **Hamid jurisdiction** (its inherent power to regulate proceedings and enforce lawyers' duties to the court) — [judiciary.uk, judgment PDF](https://www.judiciary.uk/wp-content/uploads/2025/06/Ayinde-v-London-Borough-of-Haringey-and-Al-Haroun-v-Qatar-National-Bank.pdf).
- A non-existent Court of Appeal authority was cited; a **wasted costs order** was made against the barrister in Haringey's favour.
- The court held the **threshold for contempt was met** — either the citations were deliberately fabricated or the extent of GenAI use was concealed — but declined to issue a contempt summons because knowledge could not be proven to the criminal standard.
- **Both the barrister and the solicitors (Primus Solicitors) were referred to their regulators (BSB / SRA)**, the SRA to consider whether the firm failed to have proper safeguards against filing unsupported legal claims — [Law Society Gazette](https://www.lawgazette.co.uk/news/lawyers-escape-contempt-proceedings-over-fake-case-citations/5123511.article); [DAC Beachcroft analysis](https://www.dacbeachcroft.com/en/What-we-think/AI-hallucinations-hit-the-high-court).

**The UK case is the most useful single artefact for a French sales conversation**, because it establishes the pattern APX should be selling against: not a fine, but a **regulatory referral for having no verification safeguard in the firm's process**. That is precisely the CNB's framing too.

**The commercially important detail: in France the sanction so far is a judicial rebuke on the public record, not money.** For a French avocat the deterrent is reputational and deontological — the CNB confirms that using AI content without proper verification "is likely to be subject to disciplinary proceedings" (guide of 13 March 2026, per Morgan Lewis) — but **no French disciplinary sanction had been pronounced as of early 2026**. Selling verified citation as "avoid a fine" will not land in France. Selling it as "avoid being the avocat named in the next TA decision" will.

---

## 5. Pricing models actually in market

### 5.1 Published or credibly reported prices, French market

| Product | Price | Source quality |
|---|---|---|
| **Haiku** individual licence | **€19 HT/month**; **−80% for Barreau de Bordeaux members** | [VENDOR, published] — [haiku.fr/bordeaux](https://www.haiku.fr/bordeaux), 17 Jul 2026 |
| **Ordalie** Pro | **<€60 HT/month**; free tier permanent | [VENDOR, published] — [ordalie.com](https://ordalie.com/en/) |
| **GenIA-L Avocat** (Lefebvre Dalloz) | **from €213 HT/month** to €255.60 HT/month | [VENDOR, published] — [boutique.lefebvre-dalloz.fr](https://boutique.lefebvre-dalloz.fr/genial-avocat.html) |
| **GenIA-L via Barreau de Paris** | **€80/month** (Search) / **€220/month/user** (Assistant) | [INSTITUTIONAL] — [avocatparis.org](https://www.avocatparis.org/actualites/lia-le-barreau-en-action), 8 Apr 2026 |
| **GenIA-L licence** | €2,000–2,500 HT depending on volume | [INDEP] — [Le Monde Informatique, 10 Mar 2025](https://www.lemondeinformatique.fr/actualites/lire-avec-genia-l-assistant-lefebvre-dalloz-complete-son-offre-ia-96250.html) |
| **Jimini** | Quote only; **3 months free for Paris Bar firms of 1–20 lawyers** | [INSTITUTIONAL] |
| **Doctrine / Predictice / Lexis+ AI / Case Law Analytics / Septeo Brain** | Quote only | vendor sites |
| **Harvey** | No published price. Reported $1,000–2,000/seat/mo mid-market, $100–200 at Am Law scale, TCV $50k–$300k+, 25–50 seat minimums | ⚠️ SEO |
| **Legora** | No published price. Reported ~$3,000/user/yr, 10-seat minimum (~$30k floor) | ⚠️ SEO |

### 5.2 The four models in market

1. **Per-seat subscription** — overwhelmingly dominant. €19–€255/user/month for French tools; $100–$2,000/seat/month for Harvey/Legora depending on volume.
2. **Consumption / agent-usage** — new and spreading. **Legora moved Agent Pro to consumption pricing in June 2026** and added matter-level cost tracking, precisely because agentic workloads break the per-seat cost assumption — [Unfiltered Bits, 23 Jun 2026](https://unfilteredbits.substack.com/p/legal-ai-wont-be-priced-per-seat). Matter-level cost tracking is the interesting part: it makes AI cost **rebillable to the client**.
3. **Enterprise licence with seat minimums** — Harvey, Legora, Lexis, IBM. Effectively excludes 20–40-lawyer firms from Harvey-class tools unless heavily discounted.
4. **Consulting forfait** — **[UNVERIFIED]**. No credible published benchmark was found for what French consultancies charge to deploy a private RAG in a law firm. This is a genuine information gap and APX should treat any internal assumption here as unvalidated.

### 5.3 What a 20–40-lawyer French firm actually pays today

No survey discloses this directly (**[UNVERIFIED]**). But the observable envelope is tight:

- 30 lawyers × GenIA-L Assistant at the Paris Bar rate (€220/mo) = **~€79,000/yr** — the top of the realistic range.
- 30 × GenIA-L list (€213/mo) = ~€77,000/yr.
- 30 × Ordalie (€60/mo) = **~€21,600/yr**.
- 30 × Haiku (€19/mo) = **~€6,800/yr** — and €1,400/yr for a Bordeaux Bar member firm.

**Anchor point for APX:** an on-prem deployment must be argued against **€7k–€79k per year of alternatives, with a realistic mid-point near €20k–€25k/yr**, against a CCBE-published hardware cost of **€2,000–€20,000 one-off**. The room for a services margin exists, but it is not enormous, and the customer can read the CCBE guide too.

### 5.4 Market context on spend and adoption

- Wolters Kluwer Future Ready Lawyer 2026 (n=810, US/China/9 European countries incl. France): **92%** of legal professionals use at least one AI tool; **86%** expect legal-tech spending to rise over three years — [Wolters Kluwer, 10 Mar 2026](https://www.wolterskluwer.com/en/news/wolters-kluwer-releases-2026-future-ready-lawyer-survey-report).
- A separate WK pan-European small-firm study (n=633; **40% solos, 43% firms up to 10 lawyers**) found the top barriers were **ethical/data-privacy concerns (39%)** and lack of training/resources (39%). WK states explicitly: "Most AI vendors are currently located in the United States… **This is causing many firms to look for local models and solutions**" — [Wolters Kluwer](https://www.wolterskluwer.com/en-gb/expert-insights/legal-ai-adoption-growth-small-law-firms-europe).
- Lefebvre Dalloz / CSA Research barometer (Jan–Mar 2026, n=627 French legal and accounting professionals): **72%** already use AI daily; lawyers and accountants highest at ~80%.
- Village de la Justice survey (Feb 2026, n=220): **39%** "can no longer do without" AI; **63%** use specialised or partly specialised legal AI rather than general tools; **69%** want more training — [Village de la Justice, 4 Mar 2026 (upd. 7 May 2026)](https://www.village-justice.com/articles/avocats-juristes-utilisation-intelligence-artificielle).
- CNB / Observatoire survey (March 2025, >4,000 lawyers): roughly **one firm in two** had already tested a legal AI; **confidentiality and legal compliance** were the leading deontological concerns — [CNB](https://cnb.avocat.fr/actualite/premiers-resultats-des-enquetes-sur-lia-generative).

**The market is not un-penetrated. It is already saturated with cheap tools, and the buyer's stated objection is confidentiality — not capability.**

---

## 6. Regulatory state of play (as of 20 July 2026)

### 6.1 EU AI Act — the Digital Omnibus reset the calendar

The Digital Omnibus on AI was adopted by the European Parliament on **16 June 2026** and the Council on **29 June 2026**, entering into force in July 2026 — [Freshfields, 10 Jul 2026](https://www.freshfields.com/en/our-thinking/blogs/technology-quotient/eu-ai-act-unpacked-34-the-final-digital-omnibus-on-ai-key-amendments-to-the-a-102nber); [Council of the EU, 7 May 2026](https://www.consilium.europa.eu/en/press/press-releases/2026/05/07/artificial-intelligence-council-and-parliament-agree-to-simplify-and-streamline-rules/); [Gibson Dunn](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/).

| Obligation | Status as of 20 July 2026 |
|---|---|
| Prohibited practices (Art. 5) | **In force** since 2 Feb 2025. New prohibitions (CSAM/NCII generation) with safeguards required by **2 Dec 2026**. |
| **Art. 4 AI literacy** | **In force** since 2 Feb 2025 — but **softened by the Omnibus** from an obligation to *ensure* a sufficient level of AI literacy to an obligation to *support* its development. An obligation of effort, not result, with hard penalty pressure removed. |
| GPAI model obligations | **In force** since 2 Aug 2025. Applies to model providers, not to law firms. |
| **Art. 50 transparency** | **Applies from 2 Aug 2026 — i.e. in under two weeks.** AI-generated content marking gets a grace period to **2 Dec 2026**; other transparency obligations bite on 2 Aug 2026. |
| **High-risk, Annex III standalone** | **Deferred from 2 Aug 2026 to 2 December 2027.** |
| High-risk, Annex I embedded | Deferred to **2 August 2028**. |
| Regulatory sandboxes | Establishment deadline postponed to **2 Aug 2027**. |

### 6.2 The correction that matters most: legal AI sold to law firms is probably **not** high-risk

Annex III point 8(a) covers AI "intended to be used by a judicial authority **or on their behalf**" to assist in researching and interpreting facts and the law. The Commission's draft classification guidelines indicate that **legal-tech vendors whose customers are law firms are largely out of scope, because attorneys do not act "on behalf of" the court** within the meaning of that use case; the same tool sold to a judge would be in scope — [Commission draft guidelines on classification of high-risk AI, Annex III (2026)](https://table.media/assets/documents/draft_guidelines_on_the_classification_of_high_risk_ai_annex_iii_7mxr3yiz2gw3uppjpwvvndd8ioi_128561.pdf); analysis at [aiactblog.nl](https://www.aiactblog.nl/en/posts/high-risk-ai-justice-democracy).

**Implication for APX: do not build a sales narrative on "we are AI Act high-risk compliant and they are not."** It is very likely inapplicable to both APX and its competitors, the deadline has moved to December 2027, and a sophisticated general counsel or bâtonnier will know this. The defensible regulatory arguments are **GDPR/Art. 32 + Art. 44 transfers**, **secret professionnel (Art. 226-13 Code pénal in France; Art. 458 Code pénal in Luxembourg)**, and **RIN/deontology** — not the AI Act.

### 6.3 Bar-association guidance — this is the real tailwind

**CNB (France) — "La déontologie et l'intelligence artificielle", adopted 17 March 2026** ([CNB](https://cnb.avocat.fr/actualite/le-cnb-adopte-un-guide-sur-la-deontologie-et-l-intelligence-artificielle); the PDF sits behind CNB SSO, so the detail below is from a practitioner reading at [Village de la Justice, 23 Apr 2026](https://www.village-justice.com/articles/deontologie-des-avocats-guide-cnb,56753.html) — **treat the specifics as second-hand until the PDF is obtained**):

- Lawyers must **never transmit information covered by professional secrecy to generative AI tools**.
- Lawyers must verify: **data location (France or EU only); nationality of the server owner (European, excluding entities subject to extraterritorial laws — explicitly referencing US companies); LLM hosting location; LLM provider nationality.**
- **"Vérification systématique des résultats produits par l'IA."**
- Client consent required where client data trains the firm's AI, or where a chatbot answers clients.
- Billing methodology left unresolved.
- Per Morgan Lewis (18 Mar 2026), the guide states that using AI-generated content without proper verification "is likely to be subject to disciplinary proceedings".

If that reading is accurate, **the CNB has effectively written APX's sales deck**: EU-only hosting, non-US ownership of both infrastructure and model, and systematic output verification. Obtaining and quoting the actual PDF should be a priority — the second-hand version is doing a lot of load-bearing work.

**CNB, other 2025–26 actions:** colloquium with Legal Data Space, "IA juridique : quels enjeux de souveraineté pour notre droit ?", 18 June 2025 ([CNB](https://cnb.avocat.fr/conseil-national-des-barreaux-et-legal-data-space/ia-juridique-quels-enjeux-de-souverainete-pour-notre-droit)); AG of 12 Dec 2025 redefined *consultation juridique* so that personalised advice can never be "le simple produit d'une machine" but a co-production between tool and human ([Le Monde du Droit](https://www.lemondedudroit.fr/mag/378-intelligence-artificielle/102290-le-cnb-redefinit-la-consultation-juridique-pour-repondre-aux-defis-de-lia.html)).

**CCBE (EU):**
- **Guide on the use of generative AI by lawyers, 2 October 2025** — confidentiality obligations extend to GenAI use; client data must not enter unsecured models; all AI-generated citations and factual assertions must be independently verified before filing; professional independence from technology providers must be maintained ([PDF](https://www.ccbe.eu/fileadmin/speciality_distribution/public/documents/IT_LAW/ITL_Guides_recommendations/EN_ITL_20251002_CCBE-guide-on-the-use-of-the-use-of-generative-AI-for-lawyers.pdf)).
- **Guidelines on the use of cloud computing by Bars and lawyers, 27 February 2025.**
- **Technical guide on the use of AI tools and models by lawyers, 27 March 2026** — see §3.5. Ranks on-premises as deployment option 1, notes protection against police search warrants, and publishes hardware budgets.

**Luxembourg:** professional secrecy for Luxembourg avocats rests on **Article 458 of the Penal Code** and Article 35 of the Bar's internal regulations — a **criminal** obligation, not merely a GDPR one, which raises the sovereignty bar above France's. The Luxembourg Bar has an AI Commission and the Conférence du Jeune Barreau has run AI events; an "Artificial Intelligence Day in Luxembourg Law" conference including a round table on legal ethics took place in November 2025 ([cf-avocats.lu, 20 Nov 2025](https://www.cf-avocats.lu/en/2025/11/20/artificial-intelligence-day-in-luxembourg-law-conference-participation-in-a-round-table-discussion-on-legal-ethics-in-the-face-of-ai/)). **No published Luxembourg Bar AI guideline was located → [UNVERIFIED].**

**Belgium:** OVB and OBFG adopted joint AI guidelines on **31 January 2025** — via [ICT Rechtswijzer](https://www.ictrechtswijzer.be/en/ai-hallucination-briefs/).

### 6.4 State-level sovereignty push

- **Ministère de la Justice (France):** "L'IA au service de la justice" strategy (Aug 2025); internal GenAI assistant "Mon Assistant Justice" deployed to several thousand agents; a **direction de programme IA created December 2025**; 12 priority use cases from 2026; a **"trustworthy AI" label being created to frame solutions proposed by legal publishers**; explicit plan to deploy on **SecNumCloud sovereign hosting** before migrating internally — [justice.gouv.fr rapport](https://www.justice.gouv.fr/sites/default/files/2025-08/rapport_ia_au_service_de_la_justice.pdf); [justice.gouv.fr, Dec 2025](https://www.justice.gouv.fr/actualites/espace-presse/creation-dune-direction-programme-dediee-lintelligence-artificielle-au-sein-du-ministere).
- **France 2030:** an additional €655M to accelerate the national AI strategy — [info.gouv.fr](https://www.info.gouv.fr/actualite/accelerer-l-ia-dans-l-etat-et-au-service-des-francais). Jimini AI is a laureate.
- **Luxembourg:** "Accelerating Digital Sovereignty 2030" (May 2025) with a **Luxembourg AI Factory**; **MeluXina-AI** (LuxProvide) with **>2,100 GPU accelerators entering service in H2 2026**, explicitly positioned so organisations can fine-tune specialised models **without exporting sensitive data** — [gouvernement.lu](https://gouvernement.lu/dam-assets/images-documents/actualites/2025/05/16-strategies-ai-donnees-quantum/2024115332-ministere-etat-strategy-ai-en-bat-acc-ua.pdf); [aifactory.lu](https://aifactory.lu/about/meluxina-ai). **This is a concrete Luxembourg-specific opening: a national sovereign GPU facility coming online in the same half-year, in a jurisdiction where breaching professional secrecy is a criminal offence.**

---

## 7. The gap — where there is genuinely open space, and where APX gets outgunned

### 7.1 What is genuinely open

| # | Open space | Evidence | Strength |
|---|---|---|---|
| 1 | **Productised on-premise legal AI for 20–40-lawyer firms does not exist.** Mistral and Aleph Alpha have the technology but sell enterprise contracts with no public pricing and no small-firm references. Luminance publishes a customer-environment claim with no terms. Noxtua serves small firms but as sovereign SaaS. | §3.4 | **Strong.** This is a real hole. |
| 2 | **Only one legal-AI vendor (Haiku) is on SecNumCloud-qualified infrastructure, and even that claim excludes AI services by construction.** HDS ≠ sovereignty. | §3.3 | **Weakened but still real.** The qualified clouds exclude AI services from scope, so nobody — including APX — can honestly claim end-to-end SecNumCloud without going fully on-prem. **That is precisely the argument on-prem wins.** |
| 3 | **The CNB's March 2026 criteria (EU location, non-US ownership of infrastructure *and* model provider, systematic verification) are met by essentially nobody.** GenIA-L runs on OpenAI. Legora's own sub-processor list names OpenAI. Lexis has only just added Mistral. Ordalie and Jimini decline to name their model providers. | §1.2, §3.1, §6.3 | **Strong** — and it is a *deontological* argument, which is the argument French avocats actually respond to. |
| 4 | **Article 145 CPC triage is a specific, painful, confidentiality-critical workflow with no French-language, sovereign tool addressing it.** | §2 | **Medium** — real pain, but episodic demand and unproven willingness to pay. |
| 5 | **Luxembourg.** One tiny local player (Alizé), criminal-law professional secrecy (Art. 458), a national sovereign GPU facility (MeluXina-AI) live H2 2026, and no bar guidance yet. | §1.2, §6.3, §6.4 | **Medium-strong and under-exploited.** Small market, but the sovereignty argument is legally sharper there than in France. |
| 6 | **Tier-(c) citation verification — "does the authority actually support the proposition"** — is unsolved by everyone, per the 2026 benchmarks. | §4.2 | **Medium** — genuinely open, and genuinely hard. Do not promise it. |

### 7.2 Where APX gets outgunned — read this part twice

1. **Distribution, decisively.** Septeo reaches **7,500 French firms** through the Secib practice-management system they already pay for, with an AI assistant that reads their case files, claims French sovereign hosting and HDS certification, and restricts retrieval to internal documents. That is APX's product description, sold by the incumbent, through an existing contract, with zero switching cost. A consultancy cold-calling 30-lawyer firms cannot beat that on distribution.
2. **Price floor collapse — and the cheapest competitor also has the best sovereignty story.** Haiku sells corpus-indexing legal AI at **€19/month**, discounted 80% for Bordeaux Bar members, three days before this document was written — **hosted on SecNumCloud-qualified French infrastructure (PREMI3NS / S3NS)**. That combination (French, corpus-indexing, SecNumCloud, bar-partnered, €19) is the hardest single fact in this document for the APX thesis. Ordalie is under €60. Lefebvre Dalloz gave GenIA-L away free to Paris solos through end-2025 and now sells at €80/month through the Paris Bar. Whatever APX charges, the buyer's reference price is €20–€220/user/month — and hardware for the whole thing costs €2,000 per the CCBE.
3. **The CCBE published the recipe.** A 27 March 2026 guide from the European bar federation tells lawyers that Ollama on a €2,000 box runs a 20–40B model and that 13–34B plus embeddings handles 200–500-page RAG. Any technically-minded partner — or their nephew — can now price a DIY alternative. APX's value must be the *service wrapper*: verification against Judilibre/Légifrance, deontological documentation, maintenance, liability. Not the model.
4. **On-prem economics are against APX.** Break-even vs cloud requires ~80% sustained GPU utilisation; a 30-lawyer firm reaches nothing like it, and on-prem implies 0.5–1 FTE of ops. If a prospect's CFO models it, on-prem loses on cost. The only winning frame is *secret professionnel and risk elimination* — never TCO.
5. **The AI Act argument is probably void.** Legal AI sold to law firms is very likely outside Annex III, and the high-risk regime moved to December 2027 anyway. Leading with "AI Act compliance" signals that APX has not read the Omnibus.
6. **The bar channel is occupied.** Paris has seven partner vendors. Bordeaux has Haiku. Regional bars are being picked off one by one.
7. **Corpus depth is unwinnable.** Lefebvre Dalloz has 200 years of doctrine and 4.5M decisions; RELX will own Doctrine's 27,000-user platform plus Case Law Analytics plus Lexis. APX cannot compete on content. It can only compete on **the firm's own corpus plus free open data (Judilibre, Légifrance)** — which is exactly the right strategic choice, but it means APX must never pretend to be a research tool.
8. **The market leader in the adjacent category concluded on-prem was not worth supporting.** Relativity is retiring Server, raised Server pricing on 1 April 2026 to push migration, and requires all new matters on the cloud from 1 January 2028 — after >75% of its business had already moved. APX should have a crisp answer to "if on-prem were viable, why is Relativity killing it?" The honest answer is *different buyer, different risk* — Relativity's customers are service providers optimising cost at scale; APX's are partners optimising for secret professionnel. But the question will be asked.
9. **Capital asymmetry is absolute.** Harvey $11B, Legora $5.6B, Noxtua ~$92M, Haiku €4.3M, Jimini €1.9M, Ordalie €1.8M. Even the smallest French entrants are venture-funded and full-time. A consultancy competes on service depth and proximity, or not at all.

### 7.3 The honest strategic read

The defensible position is **not** "a better legal AI". It is: *the only French provider that will install a legal AI inside your walls, where nothing leaves, verified against free public sources, documented so your bâtonnier and your insurer can both sign off* — sold as an engagement, not a licence, to firms with a specific confidentiality problem (145 CPC triage, sensitive M&A, criminal defence, Luxembourg private wealth) rather than to firms shopping for a productivity tool.

That is a services business with a software artefact, addressing perhaps a few dozen French firms and a smaller number in Luxembourg. **Luxembourg deserves disproportionate attention:** professional secrecy there is a criminal obligation under Art. 458 of the Penal Code rather than a purely deontological one; there is one small local player (Alizé) and no published bar guideline; and MeluXina-AI — a national sovereign GPU facility with >2,100 accelerators explicitly positioned for fine-tuning without exporting sensitive data — enters service in H2 2026. That is a sharper, less contested version of the same argument. It is defensible. It is not scalable in the way a product plan implies, and the current plan should be checked for whether it is priced and staffed as a consultancy or as a SaaS. Those are different companies.

---

## 8. What this means for APX

1. **The closest competitor is not Harvey — it is Septeo.** Septeo Brain does drafting and Q&A over the firm's own case files, claims 100%-France sovereign hosting and HDS certification, restricts retrieval to internal documents to avoid fabricated case law, and reaches 7,500 French firms through software they already pay for. Any positioning document that treats Harvey as the benchmark is aimed at the wrong target. **Every APX deck needs a Septeo Brain slide and a reason why on-prem beats "French sovereign cloud".**

2. **The price ceiling is far lower than an on-prem thesis assumes, and the cheapest competitor also has the strongest sovereignty claim.** Haiku launched corpus-indexing legal AI at €19/month with an 80% bar discount on 17 July 2026 — **on SecNumCloud-qualified French infrastructure (PREMI3NS / S3NS)**. Ordalie is under €60; the Paris Bar sells GenIA-L at €80. A 30-lawyer firm's realistic alternative costs €7k–€79k/yr, mid-point ~€20–25k. Meanwhile the CCBE publicly prices the hardware at €2,000–€20,000. **APX must justify its number against those anchors in one sentence, and must have a specific answer to "why not Haiku?" — the honest one being that S3NS's SecNumCloud qualification explicitly excludes AI services, so Haiku's inference is not qualified. Verify that before using it.**

3. **Drop the EU AI Act from the pitch.** Legal AI sold to law firms is very likely outside Annex III high-risk, and the high-risk regime was deferred to 2 December 2027 by the Digital Omnibus (Parliament 16 June 2026, Council 29 June 2026). What is actually in force and relevant is Art. 50 transparency from 2 Aug 2026 and a *softened* Art. 4 literacy duty. **Replace the AI Act argument with the CNB March 2026 guide, secret professionnel (Art. 226-13 CP / Art. 458 CP Luxembourg), and Carniaux's sworn Senate testimony that Microsoft cannot guarantee data stays out of US hands.** Those are stronger, verifiable, and land with a bâtonnier.

4. **"Verified citation" must be scoped honestly or it becomes a liability.** Tier (a) — the authority exists — is deterministic and free via Judilibre and Légifrance APIs, and is real differentiation only because competitors don't foreground it. Tier (b) — still good law — needs a citator APX does not own. Tier (c) — the authority supports the proposition — is unsolved by everyone per the 2026 LegalCiteBench/LePhantomCite results. **Claim (a), be explicit about (b) and (c), and never publish an unaudited hallucination-rate number** — Ordalie's "under 1%" is exactly the kind of claim that gets dismantled the first time a client tests it.

5. **The on-prem gap is real, but the reason it is empty is economic, not technical.** No 30-lawyer firm reaches the ~80% GPU utilisation where on-prem beats cloud on TCO, and on-prem carries 0.5–1 FTE of ops. **The only sellable frame is risk elimination for a specific confidentiality-critical workflow** — 145 CPC triage, criminal defence, sensitive M&A, Luxembourg private wealth — not general productivity. This also means the business is a **consultancy with a software artefact**, priced per engagement, not a per-seat SaaS. If the current plan assumes SaaS economics and a large addressable base, it is wrong. France has **77,190 lawyers** (Ministère de la Justice, 1 Jan 2025) but **36% practise individually** and only 32% are partners in a structure — [CNB chiffres-clés](https://cnb.avocat.fr/en/the-lawyers-in-numbers). Décideurs' business-law ranking covers **150 firms in total**, of which ~55% have 6–50 lawyers and ~20–23% have 100+ — [Décideurs, "Les 150 : le classement par effectif"](https://www.decideurs-juridiques.com/decideurs-100/62034-les-150-le-classement-par-effectif.html). **A precise census of French firms in the 20–40-lawyer band is [UNVERIFIED], but the order of magnitude is low hundreds at most — and many of them are Paris business-law firms already being sold to by Harvey and Legora.**

6. **Two things to verify before this document is used commercially:** (a) obtain the actual CNB guide PDF — its hosting/nationality criteria are currently second-hand from a practitioner article and are doing a great deal of load-bearing work; (b) re-check the ANSSI SecNumCloud *qualified* roster directly, as the official list URL returned 404 during this research.

---

## Appendix — Items explicitly unverified

1. CoCounsel EU data residency — no published commitment or named EU region found.
2. Jimini's actual sovereign cloud provider — not named on site; the "Scaleway" attribution is SEO-only.
3. Ordalie's cloud provider and model providers — not named on site.
4. GenIA-L's specific hosting provider — "European hosting" claimed; no primary confirmation of which.
5. **Haiku's exact SecNumCloud scope** — the site claims PREMI3NS/S3NS SecNumCloud hosting, but S3NS's qualification excludes AI services; whether inference runs inside or outside the qualified perimeter is unconfirmed. Haiku's LLM providers are also unnamed. **Highest-value open question in this document.**
6. Noxtua on-premise availability in July 2026 — reported Apr 2025, absent from vendor sites now.
7. Luminance on-prem terms, price, minimum size, and whether the LLM runs on customer hardware.
8. Predictice and Case Law Analytics hosting specifics — no primary security documentation.
9. Alizé (Luxembourg) hosting posture, pricing, traction.
10. Any published Luxembourg Bar AI guideline.
11. Any Luxembourg court decision on AI-fabricated citations.
12. Outcome of the BSB/SRA referrals arising from *Ayinde*/*Al-Haroun* — not tracked past the June 2025 judgment.
13. Whiting v. City of Athens (6th Cir., Mar 2026) — secondary sources only; verify the docket.
14. ANSSI's SecNumCloud *qualified* roster — official list URL returned 404.
15. Whether OVHcloud AI Endpoints falls inside SecNumCloud scope.
16. Any quantified European law-firm survey on preferred data-hosting location — appears not to exist publicly.
17. French consulting *forfait* benchmarks for deploying private RAG in a law firm.
18. Market sizing for article 145 CPC document-triage services in France.
19. What 20–40-lawyer French firms actually pay for legal AI — inferred from list prices, not surveyed.
20. EU data-region availability for Everlaw, DISCO, Reveal, Casepoint, Exterro, ZyLAB — not confirmed per-vendor against primary documentation.
21. Whether any European eDiscovery platform markets mass triage to firms under 50 lawyers — none identified, but absence of evidence only.
22. French *commissaire de justice* / forensic-provider practices for 145 seizures beyond the named Big Four and KLDiscovery/FRA — not mapped.
