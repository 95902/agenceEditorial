"""Configuration optimisée pour la recherche de concurrents."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class CompetitorSearchConfig:
    """Configuration complète pour la recherche de concurrents optimisée."""

    # Paramètres de recherche
    max_results_tavily: int = 20
    max_results_duckduckgo: int = 20
    max_queries: int = 50
    max_candidates_to_enrich: int = 50

    # Seuils de filtrage
    min_relevance_score: float = 0.45
    min_confidence_score: float = 0.35
    min_combined_score: float = 0.35

    # Poids pour scoring multi-critères
    weight_llm_score: float = 0.50
    weight_semantic_similarity: float = 0.25
    bonus_cross_validation: float = 0.15
    bonus_geographic: float = 0.10

    # Catégories ESN - termes de détection
    esn_keywords: List[str] = None
    esn_patterns: List[str] = None
    esn_activity_keywords: List[str] = None

    # === LISTES D'EXCLUSION PAR CATÉGORIE ===
    
    # Domaines exclus (liste principale)
    excluded_domains: Set[str] = None
    
    # TLDs exclus
    excluded_tlds: Set[str] = None
    
    # Outils SEO/Analytics
    excluded_tools: Set[str] = None
    
    # Médias et presse
    excluded_media: Set[str] = None
    
    # Plateformes de listing/classement
    excluded_listing_platforms: Set[str] = None
    
    # Sites d'emploi/recrutement
    excluded_job_sites: Set[str] = None
    
    # Sites e-commerce
    excluded_ecommerce: Set[str] = None
    
    # Universités et écoles
    excluded_universities: Set[str] = None
    
    # Services publics et gouvernementaux
    excluded_public_services: Set[str] = None
    
    # Sites de reprise/vente d'entreprises
    excluded_business_sale: Set[str] = None
    
    # Annuaires d'entreprises
    excluded_directories: Set[str] = None

    # Limites par catégorie (assurance diversité)
    max_per_category: dict = None

    # Optimisation articles
    max_articles_per_domain: int = 500

    def __post_init__(self) -> None:
        """Initialiser les valeurs par défaut."""
        self._init_esn_keywords()
        self._init_excluded_domains()
        self._init_excluded_tlds()
        self._init_excluded_tools()
        self._init_excluded_media()
        self._init_excluded_listing_platforms()
        self._init_excluded_job_sites()
        self._init_excluded_ecommerce()
        self._init_excluded_universities()
        self._init_excluded_public_services()
        self._init_excluded_business_sale()
        self._init_excluded_directories()
        self._init_max_per_category()

    def _init_esn_keywords(self) -> None:
        """Initialiser les mots-clés ESN."""
        if self.esn_keywords is None:
            self.esn_keywords = [
                "ESN",
                "SSII",
                "société services numériques",
                "agence digitale",
                "entreprise services numériques",
                "société informatique",
                "services informatiques",
            ]

        if self.esn_patterns is None:
            self.esn_patterns = [
                r"\bESN\b",
                r"\bSSII\b",
                r"société.*services.*numériques",
                r"agence.*digitale",
                r"entreprise.*services.*numériques",
            ]

        if self.esn_activity_keywords is None:
            self.esn_activity_keywords = [
                "développement",
                "conseil IT",
                "intégration",
                "maintenance",
                "infrastructure",
                "cloud",
                "cybersécurité",
                "transformation digitale",
            ]

    def _init_excluded_job_sites(self) -> None:
        """Initialiser les sites d'emploi à exclure."""
        if self.excluded_job_sites is None:
            self.excluded_job_sites = {
                # Sites d'emploi généralistes France
                "indeed.fr",
                "indeed.com",
                "glassdoor.fr",
                "glassdoor.com",
                "cadremploi.fr",
                "hellowork.com",
                "meteojob.com",
                "monster.fr",
                "monster.com",
                "regionsjob.com",
                "jobintree.com",
                "keljob.com",
                "emploi-store.fr",
                "pole-emploi.fr",
                "francetravail.fr",
                "linkedin.com",
                "welcometothejungle.com",
                "welcometothejungle.fr",
                "talent.com",
                "neuvoo.fr",
                "jooble.org",
                "optioncarriere.com",
                "staffsante.fr",
                "staffsocial.fr",
                "lejdd.fr",
                "leparisien.fr/emploi",
                "emploi.lefigaro.fr",
                "emploi.lemonde.fr",
                # Sites d'emploi IT/Tech
                "lesjeudis.com",
                "chooseyourboss.com",
                "free-work.com",
                "freelance-informatique.fr",
                "malt.fr",
                "comet.co",
                "crème-de-la-crème.com",
                "kicklox.com",
                "talent.io",
                "hired.com",
                # Cabinets de recrutement
                "michaelpage.fr",
                "hays.fr",
                "robertwalters.fr",
                "expectra.fr",
                "manpower.fr",
                "adecco.fr",
                "randstad.fr",
                "synergie.fr",
                "proman-emploi.fr",
                # Sites intérim
                "interim.fr",
                "jobijoba.com",
                "adzuna.fr",
            }

    def _init_excluded_ecommerce(self) -> None:
        """Initialiser les sites e-commerce à exclure."""
        if self.excluded_ecommerce is None:
            self.excluded_ecommerce = {
                # Marketplaces
                "amazon.fr",
                "amazon.com",
                "ebay.fr",
                "ebay.com",
                "aliexpress.com",
                "alibaba.com",
                "rakuten.fr",
                "cdiscount.com",
                "fnac.com",
                "darty.com",
                "boulanger.com",
                "conforama.fr",
                "but.fr",
                "ikea.com",
                "ikea.fr",
                "leroy-merlin.fr",
                "castorama.fr",
                "manomano.fr",
                # Mode et luxe
                "zalando.fr",
                "asos.com",
                "veepee.fr",
                "showroomprive.com",
                "spartoo.com",
                "sarenza.com",
                "galerieslafayette.com",
                "printemps.com",
                # Petites annonces
                "leboncoin.fr",
                "paruvendu.fr",
                "vivastreet.com",
                "marche.fr",
                # Comparateurs
                "idealo.fr",
                "kelkoo.fr",
                "leguide.com",
                "priceminister.com",
                # High-tech
                "ldlc.com",
                "materiel.net",
                "topachat.com",
                "rueducommerce.fr",
                "grosbill.com",
                # Autres
                "vinted.fr",
                "backmarket.fr",
                "refurbed.fr",
            }

    def _init_excluded_universities(self) -> None:
        """Initialiser les universités et écoles à exclure."""
        if self.excluded_universities is None:
            self.excluded_universities = {
                # Grandes écoles
                "sciencespo.fr",
                "hec.edu",
                "hec.fr",
                "essec.edu",
                "essec.fr",
                "polytechnique.edu",
                "polytechnique.fr",
                "centralelille.fr",
                "centralesupelec.fr",
                "centrale-marseille.fr",
                "mines-paristech.fr",
                "mines-paris.org",
                "enpc.fr",
                "telecom-paris.fr",
                "telecom-sudparis.eu",
                # Écoles d'ingénieurs
                "esilv.fr",
                "esme.fr",
                "devinci.fr",
                "epita.fr",
                "epitech.eu",
                "epf.fr",
                "ecam.fr",
                "ece.fr",
                "efrei.fr",
                "esiea.fr",
                "esiee.fr",
                "isep.fr",
                "supinfo.com",
                "insa-lyon.fr",
                "insa-toulouse.fr",
                "insa-rennes.fr",
                "insa-rouen.fr",
                "insa-strasbourg.fr",
                "ensimag.grenoble-inp.fr",
                "grenoble-inp.fr",
                "n7.fr",
                "enseeiht.fr",
                # Universités
                "univ-nantes.fr",
                "univ-lyon1.fr",
                "univ-lyon2.fr",
                "univ-lyon3.fr",
                "univ-paris1.fr",
                "univ-paris-saclay.fr",
                "u-paris.fr",
                "u-pec.fr",
                "u-bordeaux.fr",
                "univ-toulouse.fr",
                "univ-lille.fr",
                "univ-amu.fr",
                "univ-rennes1.fr",
                "univ-rennes2.fr",
                "univ-grenoble-alpes.fr",
                "university.parisnanterre.fr",
                "sorbonne-universite.fr",
                "lescrous.fr",
                "psl.eu",
                # Écoles de commerce
                "em-lyon.com",
                "edhec.edu",
                "audencia.com",
                "skema.edu",
                "neoma-bs.fr",
                "kedge.edu",
                "imt-bs.eu",
                # Autres formations
                "cnam.fr",
                "cned.fr",
                "openclassrooms.com",
                "lewagon.com",
                "wildcodeschool.com",
                "ironhack.com",
                "simplon.co",
                # Musique/Arts
                "cnsmd-lyon.fr",
                "cnsmdp.fr",
                # Erasmus Student Network (pas ESN informatique!)
                "ixesn.fr",
                "esn.org",
                "lyon.ixesn.fr",
                "paris.ixesn.fr",
                "nantes.ixesn.fr",
            }

    def _init_excluded_public_services(self) -> None:
        """Initialiser les services publics à exclure."""
        if self.excluded_public_services is None:
            self.excluded_public_services = {
                # Santé
                "ameli.fr",
                "assurance-maladie.fr",
                "cpam.fr",
                "secu-independants.fr",
                "msa.fr",
                "santepubliquefrance.fr",
                "solidarites-sante.gouv.fr",
                "has-sante.fr",
                # Emploi
                "pole-emploi.fr",
                "francetravail.fr",
                "service-public.fr",
                "travail-emploi.gouv.fr",
                # Social
                "caf.fr",
                "msa.fr",
                "urssaf.fr",
                "cnav.fr",
                "agirc-arrco.fr",
                # Finance/Impôts
                "impots.gouv.fr",
                "economie.gouv.fr",
                "tresor.economie.gouv.fr",
                "banque-france.fr",
                # Éducation
                "education.gouv.fr",
                "parcoursup.fr",
                "monmaster.gouv.fr",
                "enseignementsup-recherche.gouv.fr",
                # Banques publiques
                "labanquepostale.fr",
                "bpifrance.fr",
                "caissedesdepots.fr",
                # Transport
                "ratp.fr",
                "sncf.com",
                "sncf.fr",
                "iledefrance-mobilites.fr",
                "transilien.com",
                # Collectivités
                "paris.fr",
                "lyon.fr",
                "marseille.fr",
                "toulouse.fr",
                "bordeaux.fr",
                "nantes.fr",
                "metropole.nantes.fr",
                "grandlyon.com",
                "iledefrance.fr",
                "auvergne-rhone-alpes.fr",
                # Autres services publics
                "legifrance.gouv.fr",
                "data.gouv.fr",
                "api.gouv.fr",
                "cnil.fr",
                "arcep.fr",
                "anfr.fr",
                "anssi.gouv.fr",
            }

    def _init_excluded_business_sale(self) -> None:
        """Initialiser les sites de reprise/vente d'entreprises à exclure."""
        if self.excluded_business_sale is None:
            self.excluded_business_sale = {
                # Reprise d'entreprise
                "reprise-entreprise.bpifrance.fr",
                "bpifrance.fr",
                "cra.asso.fr",
                "transentreprise.com",
                "fusacq.com",
                "reprendre-en-lorraine.fr",
                "reprendre-en-alsace.fr",
                "reprendre-en-bretagne.fr",
                "reprisedentreprise.fr",
                "cession-entreprise.com",
                "entreprise-et-droit.com",
                "lcl.fr/entreprises/transmission",
                "bnpparibas.com/entreprises/cession",
                # Valorisation/Estimation
                "evaluermonentreprise.fr",
                "scorimmo.com",
                "efidev.com",
                # Franchise
                "franchise-magazine.com",
                "toute-la-franchise.com",
                "observatoiredelafranchise.fr",
                "ac-franchise.com",
                # Création d'entreprise
                "legalstart.fr",
                "legalplace.fr",
                "captaincontrat.com",
                "shine.fr",
                "qonto.com/fr/creation",
                "infogreffe.fr",
            }

    def _init_excluded_directories(self) -> None:
        """Initialiser les annuaires d'entreprises à exclure."""
        if self.excluded_directories is None:
            self.excluded_directories = {
                # Annuaires généralistes
                "pagesjaunes.fr",
                "pagesjaunes.com",
                "118000.fr",
                "118712.fr",
                "annuaire.com",
                "kelannonces.com",
                "mappy.com",
                "justacote.com",
                "yelp.fr",
                "yelp.com",
                "tripadvisor.fr",
                "tripadvisor.com",
                # Annuaires d'entreprises
                "societe.com",
                "infogreffe.fr",
                "pappers.fr",
                "verif.com",
                "manageo.fr",
                "score3.fr",
                "dirigeant.societe.com",
                "bilans.societe.com",
                "bodacc.fr",
                "sirene.fr",
                # Annuaires B2B
                "kompass.com",
                "kompass.fr",
                "europages.fr",
                "europages.com",
                "wer-liefert-was.de",
                "wlw.de",
                "thedirectory.io",
                # Annuaires spécialisés IT
                "annuaire-esn.fr",
                "annuaire-ssii.fr",
                "annuaire-informatique.fr",
                "01annuaire.com",
                "annuairefrancais.fr",
                "one-annuaire.fr",
                "indexa.fr",
                # Avis et notation
                "trustpilot.com",
                "trustpilot.fr",
                "avis-verifies.com",
                "google.com/maps",
                "g.page",
                "goo.gl/maps",
            }

    def _init_excluded_tools(self) -> None:
        """Initialiser les outils SEO/Analytics à exclure."""
        if self.excluded_tools is None:
            self.excluded_tools = {
                # Outils SEO majeurs
                "semrush",
                "ahrefs",
                "moz",
                "majestic",
                "similarweb",
                "alexa",
                "seobserver",
                # Outils SEO secondaires
                "ubersuggest",
                "spyfu",
                "serpstat",
                "seranking",
                "sistrix",
                "mangools",
                "kwfinder",
                "linkresearchtools",
                "cognitiveseo",
                # Outils d'audit
                "screaming-frog",
                "screamingfrog",
                "woorank",
                "sitechecker",
                "seoptimer",
                "gtmetrix",
                "pagespeed",
                "webpagetest",
                "dareboost",
                "yellowlab",
                # Outils de surveillance
                "builtwith",
                "wappalyzer",
                "whatruns",
                "siteprice",
                "worthofweb",
                "nicheprowler",
                "domainiq",
                "domaintools",
                # Analytics
                "analytics",
                "hotjar",
                "crazyegg",
                "mouseflow",
                "matomo",
                "plausible",
                "fathom",
            }

    def _init_excluded_media(self) -> None:
        """Initialiser les médias et presse à exclure."""
        if self.excluded_media is None:
            self.excluded_media = {
                # Presse nationale
                "lemonde.fr",
                "lefigaro.fr",
                "liberation.fr",
                "leparisien.fr",
                "lesechos.fr",
                "latribune.fr",
                "lopinion.fr",
                "humanite.fr",
                "mediapart.fr",
                "lepoint.fr",
                "lexpress.fr",
                "nouvelobs.com",
                "marianne.net",
                "valeursctuelles.com",
                "franceinter.fr",
                "20minutes.fr",
                # Presse économique
                "challenges.fr",
                "capital.fr",
                "bfmtv.com",
                "bfmbusiness.bfmtv.com",
                "economiematin.fr",
                "lafrenchtech.com",
                "maddyness.com",
                "frenchweb.fr",
                "usine-digitale.fr",
                "usinenouvelle.com",
                # Presse tech/informatique
                "journaldunet.com",
                "journaldunet.fr",
                "lesnumeriques.com",
                "01net.com",
                "zdnet.fr",
                "silicon.fr",
                "lemondeinformatique.fr",
                "lemagit.fr",
                "informatiquenews.fr",
                "itforbusiness.fr",
                "itespresso.fr",
                "generation-nt.com",
                "numerama.com",
                "clubic.com",
                "tomsguide.fr",
                "tomshardware.fr",
                "frandroid.com",
                "phonandroid.com",
                "nextimpact.com",
                "nextinpact.com",
                "iphon.fr",
                "macg.co",
                "macgeneration.com",
                # TV et radio
                "tf1.fr",
                "tf1info.fr",
                "france.tv",
                "france2.fr",
                "france3.fr",
                "france24.com",
                "bfmtv.com",
                "cnews.fr",
                "lci.fr",
                "itele.fr",
                "europe1.fr",
                "rtl.fr",
                "rmc.fr",
                "francebleu.fr",
                "radiofrance.fr",
                # Presse régionale
                "ouest-france.fr",
                "sudouest.fr",
                "lavoixdunord.fr",
                "ledauphine.com",
                "midilibre.fr",
                "ladepeche.fr",
                "estrepublicain.fr",
                "leprogres.fr",
                "dna.fr",
                "larepubliquedespyrenees.fr",
                # Blogs tech populaires
                "korben.info",
                "blogdumoderateur.com",
                "siecledigital.fr",
                "webmarketing-conseil.fr",
                "arobasenet.com",
            }

    def _init_excluded_listing_platforms(self) -> None:
        """Initialiser les plateformes de listing/classement à exclure."""
        if self.excluded_listing_platforms is None:
            self.excluded_listing_platforms = {
                # Plateformes de sélection d'agences
                "sortlist",
                "sortlist.fr",
                "sortlist.com",
                "clutch",
                "clutch.co",
                "goodfirms",
                "goodfirms.co",
                "designrush",
                "designrush.com",
                "agency-spotter",
                "agencywip.fr",
                "agenceweb.fr",
                # Plateformes d'inspiration
                "awwwards",
                "awwwards.com",
                "dribbble",
                "dribbble.com",
                "behance",
                "behance.net",
                "cssdesignawards",
                "webdesign-inspiration",
                "siteinspire",
                "landingfolio",
                # Plateformes logiciels/SaaS
                "capterra",
                "capterra.fr",
                "appvizer",
                "appvizer.fr",
                "getapp",
                "getapp.fr",
                "g2",
                "g2.com",
                "g2crowd",
                "softwareadvice",
                "trustradius",
                # Réseaux professionnels
                "viadeo",
                "viadeo.com",
                "xing",
                "xing.com",
                # Comparateurs de services
                "companeo",
                "companeo.com",
                "123presta",
                "redacteur.com",
                "textmaster",
                "textbroker",
            }

    def _init_excluded_domains(self) -> None:
        """Initialiser la liste principale des domaines exclus."""
        if self.excluded_domains is None:
            self.excluded_domains = set()
            # Sera peuplée dynamiquement à partir des autres listes

    def _init_excluded_tlds(self) -> None:
        """Initialiser les TLDs à exclure."""
        if self.excluded_tlds is None:
            self.excluded_tlds = {
                # Gouvernementaux et éducatifs
                ".gouv.fr",
                ".gov.fr",
                ".gov",
                ".edu",
                ".edu.fr",
                ".ac.fr",
                ".mil",
                ".int",
                ".museum",
                ".coop",
                # Services publics français
                ".ameli.fr",
                ".caf.fr",
                ".urssaf.fr",
                # TLDs suspects/spam
                ".xyz",
                ".top",
                ".info",
                ".biz",
                ".online",
                ".site",
                ".shop",
                ".store",
                ".club",
                ".work",
                ".click",
                ".link",
                ".download",
                ".stream",
                ".gdn",
                ".loan",
                ".racing",
                ".win",
                ".bid",
                ".trade",
                ".review",
                ".party",
                ".date",
                ".science",
                ".cricket",
            }

    def _init_max_per_category(self) -> None:
        """Initialiser les limites par catégorie."""
        if self.max_per_category is None:
            self.max_per_category = {
                "ESN": 30,
                "agence_web": 10,
                "agence_marketing": 10,
                "freelancer": 5,
                "autre": 20,
            }

    def is_excluded_domain(self, domain: str) -> bool:
        """Vérifier si un domaine est exclu."""
        reason = self.get_exclusion_reason(domain)
        return reason is not None

    def get_exclusion_reason(self, domain: str) -> Optional[Tuple[str, str]]:
        """
        Retourne la raison d'exclusion d'un domaine.
        
        Args:
            domain: Le domaine à vérifier
            
        Returns:
            Tuple (catégorie, raison) si exclu, None sinon
        """
        domain_lower = domain.lower()
        
        # 1. Vérifier TLDs exclus
        for tld in self.excluded_tlds:
            if domain_lower.endswith(tld):
                return ("tld", f"TLD exclu: {tld}")
        
        # 2. Vérifier domaines exacts dans chaque catégorie
        if self.excluded_job_sites and domain_lower in self.excluded_job_sites:
            return ("job_site", f"Site d'emploi: {domain_lower}")
        
        if self.excluded_ecommerce and domain_lower in self.excluded_ecommerce:
            return ("ecommerce", f"E-commerce: {domain_lower}")
        
        if self.excluded_universities and domain_lower in self.excluded_universities:
            return ("university", f"Université/École: {domain_lower}")
        
        if self.excluded_public_services and domain_lower in self.excluded_public_services:
            return ("public_service", f"Service public: {domain_lower}")
        
        if self.excluded_business_sale and domain_lower in self.excluded_business_sale:
            return ("business_sale", f"Reprise/Vente entreprise: {domain_lower}")
        
        if self.excluded_directories and domain_lower in self.excluded_directories:
            return ("directory", f"Annuaire: {domain_lower}")
        
        if self.excluded_domains and domain_lower in self.excluded_domains:
            return ("domain", f"Domaine exclu: {domain_lower}")
        
        # 3. Vérifier patterns (outils, médias, plateformes)
        if self.excluded_tools:
            for tool in self.excluded_tools:
                if tool in domain_lower:
                    return ("tool", f"Outil SEO/Analytics: {tool}")
        
        if self.excluded_media:
            for media in self.excluded_media:
                if media in domain_lower:
                    return ("media", f"Média/Presse: {media}")
        
        if self.excluded_listing_platforms:
            for platform in self.excluded_listing_platforms:
                if platform in domain_lower:
                    return ("listing_platform", f"Plateforme de listing: {platform}")
        
        # 4. Patterns de détection par contenu du domaine
        # Sites d'emploi
        job_patterns = ["emploi", "job", "recrutement", "carriere", "career"]
        if any(pattern in domain_lower for pattern in job_patterns):
            return ("job_pattern", f"Pattern emploi détecté dans domaine")
        
        # Universités
        univ_patterns = ["univ-", "universite", ".ac-", "ecole-", "ens-", "insa-"]
        if any(pattern in domain_lower for pattern in univ_patterns):
            return ("university_pattern", f"Pattern université détecté dans domaine")
        
        # Services publics
        public_patterns = [".gouv.", "service-public", "servicepublic"]
        if any(pattern in domain_lower for pattern in public_patterns):
            return ("public_pattern", f"Pattern service public détecté dans domaine")
        
        return None

    def get_all_excluded_domains(self) -> Set[str]:
        """
        Retourne l'ensemble de tous les domaines exclus.
        
        Returns:
            Set contenant tous les domaines exclus
        """
        all_excluded = set()
        
        if self.excluded_domains:
            all_excluded.update(self.excluded_domains)
        if self.excluded_job_sites:
            all_excluded.update(self.excluded_job_sites)
        if self.excluded_ecommerce:
            all_excluded.update(self.excluded_ecommerce)
        if self.excluded_universities:
            all_excluded.update(self.excluded_universities)
        if self.excluded_public_services:
            all_excluded.update(self.excluded_public_services)
        if self.excluded_business_sale:
            all_excluded.update(self.excluded_business_sale)
        if self.excluded_directories:
            all_excluded.update(self.excluded_directories)
        
        return all_excluded

    def get_exclusion_stats(self) -> Dict[str, int]:
        """
        Retourne les statistiques des listes d'exclusion.
        
        Returns:
            Dict avec le nombre d'éléments par catégorie
        """
        return {
            "job_sites": len(self.excluded_job_sites) if self.excluded_job_sites else 0,
            "ecommerce": len(self.excluded_ecommerce) if self.excluded_ecommerce else 0,
            "universities": len(self.excluded_universities) if self.excluded_universities else 0,
            "public_services": len(self.excluded_public_services) if self.excluded_public_services else 0,
            "business_sale": len(self.excluded_business_sale) if self.excluded_business_sale else 0,
            "directories": len(self.excluded_directories) if self.excluded_directories else 0,
            "tools": len(self.excluded_tools) if self.excluded_tools else 0,
            "media": len(self.excluded_media) if self.excluded_media else 0,
            "listing_platforms": len(self.excluded_listing_platforms) if self.excluded_listing_platforms else 0,
            "tlds": len(self.excluded_tlds) if self.excluded_tlds else 0,
            "total_domains": len(self.get_all_excluded_domains()),
        }


# Instance globale de configuration
default_config = CompetitorSearchConfig()
