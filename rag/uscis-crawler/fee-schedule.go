package main

import (
	"fmt"
	"github.com/gocolly/colly/v2"
	"log"
	"net/url"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
)

type Filing struct {
	Category  string `json:"category"`
	PaperFee  string `json:"paper_fee"`
	OnlineFee string `json:"online_fee,omitempty"`
}

type Fee struct {
	Id      string   `json:"id"`
	TopicId string   `json:"topic_id"`
	Link    string   `json:"link"`
	Filings []Filing `json:"filings"`
}

func crawlFeeSchedule(parentDir string) *colly.Collector {
	contentDir := filepath.Join(parentDir, "forms")
	rootUrl, err := url.Parse("https://www.uscis.gov/g-1055")
	if err != nil {
		log.Fatal(err)
	}

	c := colly.NewCollector(
		colly.AllowedDomains(rootUrl.Host),
		colly.CacheDir("./usciscache"),
		colly.Async(true),
	)

	c.Limit(&colly.LimitRule{DomainGlob: "*", Parallelism: 2})

	type FeeLookup struct {
		Id    string `json:"id"`
		Value string `json:"value"`
		Title string `json:"title"`
	}

	lookup, rwmutex := make(map[string]FeeLookup), new(sync.RWMutex)

	// Set custom headers to mimic a real browser
	c.OnRequest(func(r *colly.Request) {
		r.Headers.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
		r.Headers.Set("Accept-Language", "en-US,en;q=0.9")
	})

	c.OnHTML(`select.form-select[name="form-fee-title"]`, func(h *colly.HTMLElement) {
		h.ForEach("option", func(i int, h *colly.HTMLElement) {
			value := h.Attr("value")
			rwmutex.RLock()
			_, ok := lookup[value]
			rwmutex.RUnlock()
			if ok {
				return
			}
			rwmutex.Lock()
			lookup[value] = FeeLookup{
				Id:    strings.ToLower(strings.ReplaceAll(h.Attr("data-marker"), "_", "")),
				Value: value,
				Title: h.Text,
			}
			rwmutex.Unlock()
			//Vist fee scheduling page for form
			link := *rootUrl
			q := link.Query()
			q.Add("topic_id", value)
			link.RawQuery = q.Encode()
			link.Path = "/g-1055"
			c.Visit(link.String())
		})
	})
	rgx := regexp.MustCompile(`[a-z]{1,4}-\d{1,4}(cwr|cw|ez|a|b|d|e|f|g|i|j|k|r)?`)

	c.OnHTML("div.form-fee-items", func(h *colly.HTMLElement) {
		topicId := h.Request.URL.Query().Get("topic_id")
		if topicId == "" {
			return
		}
		rwmutex.RLock()
		feeLookup := lookup[topicId]
		rwmutex.RUnlock()
		fmt.Println(feeLookup.Id, "form", rgx.FindString(feeLookup.Id))
		dir := filepath.Join(contentDir, rgx.FindString(feeLookup.Id))
		metadata, err := loadMetadaFromFile(dir)
		if err != nil {
			log.Println(err)
			return
		}

		fmt.Printf("processing fees for %s - %s\n", feeLookup.Id, h.Request.URL)
		if metadata.Fees == nil {
			metadata.Fees = make(map[string]Fee)
		}
		fee, ok := metadata.Fees[feeLookup.Id]
		if !ok {
			fee = Fee{
				Id:      feeLookup.Id,
				TopicId: topicId,
				Link:    h.Request.URL.String(),
				Filings: make([]Filing, 0),
			}
		}

		h.ForEach("tbody>tr", func(i int, h *colly.HTMLElement) {
			var filing Filing
			texts := h.ChildTexts("td")
			switch len(texts) {
			case 3:
				filing = Filing{
					Category:  texts[0],
					PaperFee:  texts[1],
					OnlineFee: texts[2],
				}
			case 2:
				filing = Filing{
					Category: texts[0],
					PaperFee: texts[1],
				}
			case 1:
				seg := strings.Split(texts[0], ":")
				filing = Filing{
					Category: seg[0],
					PaperFee: seg[1],
				}
			}
			fee.Filings = append(fee.Filings, filing)
			metadata.Fees[feeLookup.Id] = fee
			err = writeToFile(dir, "metadata.json", []byte(metadata.String()))
			if err != nil {
				log.Fatal(err)
			}
		})
	})

	c.OnResponse(func(r *colly.Response) {
		fee, ok := lookup[r.Request.URL.Query().Get("topic_id")]
		if !ok {
			return
		}
		dir := filepath.Join(contentDir, rgx.FindString(fee.Id))

		err = writeToFile(dir, fmt.Sprintf("%s-fee.html", fee.Id), r.Body)
		if err != nil {
			log.Fatal(err)
		}
	})

	// Start scraping from the main forms page
	if err := c.Visit(rootUrl.String()); err != nil {
		log.Fatal(err)
	}
	return c
}
