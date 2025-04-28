package main

import (
	"encoding/json"
	"fmt"
	"github.com/PuerkitoBio/goquery"
	"github.com/gocolly/colly/v2"
	"log"
	"path/filepath"
	"strings"
)

type FAQs []FAQ

func (f *FAQs) AppendQuestion(text string) {
	text = strings.TrimSpace(text)
	if f == nil {
		*f = make(FAQs, 0)
	}

	i := len(*f) - 1
	if i < 0 {
		// Append a new FAQ with the question
		*f = append(*f, FAQ{
			Question: text,
		})
		return
	}

	// If the last FAQ doesn't have an answer yet, append to its question
	if (*f)[i].Answer == "" {
		(*f)[i].Question = strings.TrimSpace((*f)[i].Question + "\n" + text)
	} else {
		// If the last FAQ already has an answer, create a new FAQ
		*f = append(*f, FAQ{
			Question: text,
		})
	}
}

func (f *FAQs) AppendAnswer(text string) {
	i := len(*f) - 1
	(*f)[i].Answer = strings.TrimSpace((*f)[i].Answer + "\n" + strings.TrimPrefix(text, (*f)[i].Question))
}

func (f *FAQs) String() string {
	data, _ := json.MarshalIndent(f, "", "	")
	return string(data)
}

type FAQ struct {
	Question string `json:"question"`
	Answer   string `json:"answer"`
}

func crawlFAQ(parentDir string) *colly.Collector {
	contentDir := filepath.Join(parentDir, "frequently-asked-questions", "uscis")

	c := colly.NewCollector(
		colly.AllowedDomains("www.uscis.gov", "uscis.gov"),
		colly.CacheDir("./usciscache"),
		colly.Async(true),
	)

	c.Limit(&colly.LimitRule{DomainGlob: "*", Parallelism: 1})

	// Set custom headers to mimic a real browser
	c.OnRequest(func(r *colly.Request) {
		r.Headers.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
		r.Headers.Set("Accept-Language", "en-US,en;q=0.9")
	})

	//https://www.uscis.gov/forms/filing-fees/frequently-asked-questions-on-the-uscis-fee-rule
	c.OnHTML("div.container--main", func(e *colly.HTMLElement) {
		var faqs FAQs

		e.ForEach("div.content-accordion", func(_ int, element *colly.HTMLElement) {
			element.DOM.Children().Each(func(_ int, s *goquery.Selection) {
				question := strings.TrimSpace(s.Text())
				if s.Is("div.accordion__header") {
					if strings.HasPrefix(question, "Q") || strings.HasSuffix(question, "?") {
						fmt.Printf("header %s\n", question)
						faqs.AppendQuestion(question)
						return
					}
				}
				if s.Is("div.accordion__panel") {
					s.Find("p").Each(func(_ int, p *goquery.Selection) {
						fmt.Println(p.Text())
						fmt.Println("-------------")
						p.Find("strong").Each(func(_ int, s *goquery.Selection) {
							question = s.Text()
							if strings.HasPrefix(question, "Q") || strings.HasSuffix(question, "?") {
								faqs.AppendQuestion(question)
								return
							}
						})
						i := len(faqs) - 1
						if i < 0 {
							return
						}
						faqs.AppendAnswer(p.Text())
					})
				}
			})
		})

		if len(faqs) == 0 {
			return
		}
		name := strings.TrimPrefix(strings.Join(strings.Split(e.Request.URL.Path, "/"), "_"), "_")
		err := writeToFile(contentDir, fmt.Sprintf("%s.json", name), []byte(faqs.String()))
		if err != nil {
			log.Fatal(err)
		}
	})

	c.OnHTML("div.container--main>div>div.clearfix.text-formatted.field.field--name-body.field__item", func(e *colly.HTMLElement) {
		var faqs FAQs
		if e.DOM.Children().Find("div.accordion__header") != nil {
			return
		}

		e.DOM.Children().Each(func(_ int, s *goquery.Selection) {
			text := s.Text()
			//https://www.uscis.gov/forms/all-forms/questions-and-answers-appeals-and-motions
			if s.Is("h2") || s.Is("h3") {
				if strings.HasSuffix(text, "?") {
					faqs = append(faqs, FAQ{
						Question: text,
					})
				}
				return
			}
			//https://www.uscis.gov/humanitarian/consideration-of-deferred-action-for-childhood-arrivals-daca/frequently-asked-questions
			s.Find("strong").Each(func(_ int, s *goquery.Selection) {
				question := s.Text()
				if strings.HasPrefix(question, "Q") || strings.HasSuffix(question, "?") {
					faqs.AppendQuestion(question)
				}
			})

			i := len(faqs) - 1
			if i < 0 {
				return
			}
			faqs.AppendAnswer(s.Text())
		})
		if len(faqs) == 0 {
			return
		}
		name := strings.TrimPrefix(strings.Join(strings.Split(e.Request.URL.Path, "/"), "_"), "_")
		err := writeToFile(contentDir, fmt.Sprintf("%s.json", name), []byte(faqs.String()))
		if err != nil {
			log.Fatal(err)
		}
	})

	// Start scraping from the main forms page
	urls := []string{
		//"https://www.uscis.gov/forms/filing-fees/frequently-asked-questions-on-the-uscis-fee-rule",
		//"https://www.uscis.gov/keepingfamiliestogether/faq",
		//"https://www.uscis.gov/green-card/green-card-processes-and-procedures/fiscal-year-2023-employment-based-adjustment-of-status-faqs",
		//"https://www.uscis.gov/working-in-the-united-states/temporary-workers/h-1b-specialty-occupations/faqs-for-individuals-in-h-1b-nonimmigrant-status",
		//"https://www.uscis.gov/humanitarian/information-for-afghan-nationals/re-parole-process-for-certain-afghans/afghan-re-parole-faqs",
		//"https://www.uscis.gov/working-in-the-united-states/information-for-employers-and-employees/dhs-support-of-the-enforcement-of-labor-and-employment-laws",
		//"https://www.uscis.gov/working-in-the-united-states/permanent-workers/employment-based-immigration-fourth-preference-eb-4/special-immigrant-juveniles/special-immigrant-juvenile-sij-frequently-asked-questions",
		//"https://www.uscis.gov/working-in-the-united-states/temporary-workers/h-1b-specialty-occupations/h-1b-electronic-registration-process",
		//"https://www.uscis.gov/green-card/green-card-processes-and-procedures/public-charge/public-charge-resources",
		//"https://www.uscis.gov/working-in-the-united-states/permanent-workers/employment-based-immigration-fifth-preference-eb-5/eb-5-questions-and-answers",
		//"https://www.uscis.gov/working-in-the-united-states/information-for-employers-and-employees/options-for-nonimmigrant-workers-following-termination-of-employment",
		//"https://www.uscis.gov/humanitarian/consideration-of-deferred-action-for-childhood-arrivals-daca/additional-information-daca-decision-in-state-of-texas-et-al-v-united-states-of-america-et-al-118-cv",
		//"https://www.uscis.gov/working-in-the-united-states/international-entrepreneur-rule",
		//"https://www.uscis.gov/working-in-the-united-states/entrepreneur-employment-pathways/nonimmigrant-or-parole-pathways-for-entrepreneur-employment-in-the-united-states",
		//"https://www.uscis.gov/forms/all-forms/questions-and-answers-appeals-and-motions",
		//"https://www.uscis.gov/humanitarian/consideration-of-deferred-action-for-childhood-arrivals-daca/frequently-asked-questions",
		//"https://www.uscis.gov/forms/all-forms/n-600-application-for-certificate-of-citizenship-frequently-asked-questions",
		//"https://www.uscis.gov/records/electronic-reading-room/national-engagement-u-visa-and-bona-fide-determination-process-frequently-asked-questions",
		//"https://www.uscis.gov/newsroom/alerts/uscis-reminds-certain-employment-based-petitioners-to-submit-the-correct-required-fees",
		//"https://www.uscis.gov/humanitarian/temporary-protected-status/temporary-protected-status-for-venezuela-2021-extension-and-2023-re-designation-frequently-asked",
		//"https://www.uscis.gov/working-in-the-united-states/temporary-workers/frequently-asked-questions-about-part-6-of-form-i-129-petition-for-a-nonimmigrant-worker",
		//"https://www.uscis.gov/humanitarian/refugees-and-asylum/asylum/questions-and-answers-credible-fear-screening",
		//"https://www.uscis.gov/working-in-the-united-states/permanent-workers/employment-based-immigration-fifth-preference-eb-5/questions-and-answers-eb-5-immigrant-investor-program-visa-availability-approach",
		//"https://www.uscis.gov/working-in-the-united-states/temporary-workers/o-1-individuals-with-extraordinary-ability-or-achievement/o-nonimmigrant-classifications-question-and-answers",
		//"https://www.uscis.gov/humanitarian/refugees-and-asylum/asylum/questions-and-answers-reasonable-fear-screenings",
		//"https://www.uscis.gov/tools/designated-civil-surgeons/vaccination-requirements",
		//"https://www.uscis.gov/about-us/uscis-reemployed-annuitant-program-frequently-asked-questions",
		//"https://www.uscis.gov/organizational-accounts-FAQ",
		//"https://www.uscis.gov/citizenship/learn-about-citizenship/commonly-asked-questions-about-the-naturalization-process",
		//"https://www.uscis.gov/records/genealogy/genealogical-records-help/record-requests-frequently-asked-questions",
		//"https://www.uscis.gov/humanitarian/refugees-and-asylum/asylum/affirmative-asylum-frequently-asked-questions",
		//"https://www.uscis.gov/i-9-central/form-i-9-resources/questions-and-answers",
		//"https://www.uscis.gov/humanitarian/refugees-and-asylum/asylum/affirmative-asylum-frequently-asked-questions/questions-and-answers-affirmative-asylum-eligibility-and-applications",
		//"https://www.uscis.gov/humanitarian/uniting-for-ukraine/re-parole-process-for-certain-ukrainian-citizens-and-their-immediate-family-members/frequently-asked-questions-about-the-re-parole-process-for-certain-ukrainians-and-their-immediate",
		//"https://www.uscis.gov/records/genealogy/genealogical-records-help/genealogy-frequently-asked-questions",
		//"https://www.uscis.gov/humanitarian/afghan-operation-allies-welcome-oaw-parolee-asylum-related-frequently-asked-questions",
		//"https://www.uscis.gov/records/genealogy/genealogical-records-help/request-status-frequently-asked-questions",
		//"https://www.uscis.gov/forms/all-forms/how-do-i-request-premium-processing",
		//"https://www.uscis.gov/citizenship/resources-for-educational-programs/register-for-training/frequently-asked-questions",
		"https://www.uscis.gov/humanitarian/temporary-protected-status",
	}
	/*
	*TODO: "https://www.uscis.gov/humanitarian/humanitarian-or-significant-public-benefit-parole-for-noncitizens-outside-the-united-states/information-for-afghan-nationals-on-requests-to-uscis-for-humanitarian-parole/frequently-asked-questions-about-parole-requests-for-afghans-based-on"
	*TODO: https://www.uscis.gov/i-9-central/form-i-9-resources/handbook-for-employers-m-274/140-some-questions-you-may-have-about-form-i-9
	 */
	for _, url := range urls {
		if err := c.Visit(url); err != nil {
			log.Fatal(err)
		}
	}

	return c
}
