package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"github.com/gocolly/colly/v2"
	"log"
	"path/filepath"
)

type LegislationMetadata struct {
	Act         string `json:"act"`
	Code        string `json:"code"`
	Description string `json:"description"`
	Link        string `json:"link"`
}

func (l LegislationMetadata) String() string {
	data := new(bytes.Buffer)
	encoder := json.NewEncoder(data)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "	")
	encoder.Encode(l)
	return data.String()
}
func crawlLegislation(parentDir string) *colly.Collector {
	contentDir := filepath.Join(parentDir, "legislation")

	c := colly.NewCollector(
		colly.AllowedDomains("www.uscis.gov", "uscis.gov"),
		colly.CacheDir("./usciscache"),
		colly.Async(true),
	)

	c.Limit(&colly.LimitRule{DomainGlob: "*", Parallelism: 2})

	// Set custom headers to mimic a real browser
	c.OnRequest(func(r *colly.Request) {
		r.Headers.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
		r.Headers.Set("Accept-Language", "en-US,en;q=0.9")
	})
	// On every <tr> element, we will scrape its data
	c.OnHTML("tr", func(e *colly.HTMLElement) {
		components := e.ChildTexts("td")
		if len(components) == 0 {
			return
		}
		metadata := LegislationMetadata{
			Act:         components[0],
			Code:        components[1],
			Description: components[2],
			Link:        e.ChildAttr("td>a", "href"),
		}
		if metadata.Link == "" {
			return
		}

		dir := filepath.Join(contentDir, metadata.Act)

		err := writeToFile(dir, "metadata.json", []byte(metadata.String()))
		if err != nil {
			log.Fatal(err)
		}

		fmt.Printf("Dowloading Legistlation: %s - %s\n", metadata.Act, metadata.Link)
		err = downloadContent(metadata.Link, dir, fmt.Sprintf("%s-%s.xhtml", metadata.Act, metadata.Code), 4)
		if err != nil {
			log.Printf("error dowloading: %s - %s\n", metadata, err)
		}

	})

	// Start scraping from the main forms page
	startURL := "https://www.uscis.gov/laws-and-policy/legislation/immigration-and-nationality-act"
	if err := c.Visit(startURL); err != nil {
		log.Fatal(err)
	}

	return c
}
