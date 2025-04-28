package main

import (
	"encoding/json"
	"fmt"
	"html"
	"log"
	"net/url"
	"path"
	"strings"
	"sync"
	"time"

	"github.com/gocolly/colly"
)

type Paragraph struct {
	ID    string `json:"id"`
	Title string `json:"title,omitempty"`
	Text  string `json:"text"`
}

type Section struct {
	ID         string      `json:"id"`
	Citation   string      `json:"citation"`
	Title      string      `json:"title"`
	Text       string      `json:"text"`
	Paragraphs []Paragraph `json:"paragraphs,omitempty"`
}

type Part struct {
	Sections map[string]Section `json:"sections,omitempty"`
	SubParts map[string]Part    `json:"subParts,omitempty"`
}

type SubChapter struct {
	Parts map[string]Part `json:"parts"`
}

type Chapter struct {
	SubChapters map[string]SubChapter `json:"sub_chapters"`
}

type Title8 struct {
	Chapters map[string]Chapter `json:"chapters"`
}

func crawlECFR(parentDir string) *colly.Collector {
	//base := "https://www.ecfr.gov/current/title-8/chapter-I/subchapter-A/part-1/section-1.1"
	base := "https://www.ecfr.gov/current/title-8/chapter-I/subchapter-C/part-343b"
	root, err := url.Parse(base)
	if err != nil {
		log.Fatal(err)
	}

	c := colly.NewCollector(
		colly.AllowedDomains("www.ecfr.gov", "ecfr.gov"),
		colly.CacheDir("./ecfr"),
		colly.Async(true),
	)
	c.Limit(&colly.LimitRule{DomainGlob: "*", Parallelism: 1, RandomDelay: 5 * time.Second})

	title8 := Title8{Chapters: make(map[string]Chapter)}
	var sLock sync.Mutex

	c.OnRequest(func(r *colly.Request) {
		r.Headers.Set("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3.1 Safari/605.1.15")
		r.Headers.Set("Accept-Language", "en-US,en;q=0.9")
	})

	c.OnHTML("div.section", func(e *colly.HTMLElement) {
		section := Section{ID: e.Attr("id")}

		e.ForEach("h4", func(_ int, h *colly.HTMLElement) {
			meta := html.UnescapeString(h.Attr("data-hierarchy-metadata"))
			section.Title = strings.TrimSpace(h.Text)
			if strings.Contains(meta, `"citation":"`) {
				section.Citation = extractBetween(meta, `"citation":"`, `"`)
			}
		})

		e.ForEach("p", func(_ int, p *colly.HTMLElement) {
			paragraph := Paragraph{
				ID:    p.Attr("data-title"),
				Title: p.DOM.Find("em.paragraph-heading").Text(),
				Text:  strings.TrimSpace(p.DOM.Clone().ChildrenFiltered("em.paragraph-heading").Remove().End().Text()),
			}
			if paragraph.ID == "" {
				section.Text = strings.TrimSpace(section.Text + "\n" + paragraph.Text)
				return
			}
			section.Paragraphs = append(section.Paragraphs, paragraph)

		})

		// Parse hierarchy from path
		parts := strings.Split(e.Request.URL.Path, "/")
		var chapterID, subChapterID, partID, subPartID string
		for _, part := range parts {
			t := strings.Split(part, "-")
			label := t[0]
			switch label {
			case "chapter":
				chapterID = t[1]
			case "subchapter":
				subChapterID = t[1]
			case "part":
				partID = t[1]
			case "subpart":
				subPartID = t[1]
			}
		}

		// Safely populate Title8
		sLock.Lock()
		defer sLock.Unlock()

		chapter := title8.Chapters[chapterID]
		if chapter.SubChapters == nil {
			chapter.SubChapters = make(map[string]SubChapter)
		}
		subchapter := chapter.SubChapters[subChapterID]
		if subchapter.Parts == nil {
			subchapter.Parts = make(map[string]Part)
		}
		part := subchapter.Parts[partID]
		if part.Sections == nil {
			part.Sections = make(map[string]Section)
		}
		if subPartID != "" {
			if part.SubParts == nil {
				part.SubParts = make(map[string]Part)
			}
			subpart := part.SubParts[subPartID]
			if subpart.Sections == nil {
				subpart.Sections = make(map[string]Section)
			}
			subpart.Sections[section.ID] = section
			part.SubParts[subPartID] = subpart
		} else {
			part.Sections[section.ID] = section
		}
		subchapter.Parts[partID] = part
		chapter.SubChapters[subChapterID] = subchapter
		title8.Chapters[chapterID] = chapter
	})

	c.OnHTML("a#next-content-link", func(e *colly.HTMLElement) {
		href := e.Attr("href")
		title := e.Attr("data-title")
		fmt.Printf("→ Next: %s (%s)\n", title, href)

		nextURL := e.Request.URL.ResolveReference(&url.URL{Path: href})
		if err = c.Visit(nextURL.String()); err != nil {
			log.Fatal(err)
		}
	})

	if err = c.Visit(root.String()); err != nil {
		log.Fatal(err)
	}

	c.Wait()

	// Write final hierarchical struct to JSON
	data, _ := json.MarshalIndent(title8, "", "  ")
	if err = writeToFile(path.Join(parentDir, "legislation"), "title8-nested.json", data); err != nil {
		log.Fatal(err)
	}

	return c
}

func extractBetween(s, start, end string) string {
	startIdx := strings.Index(s, start)
	if startIdx == -1 {
		return ""
	}
	startIdx += len(start)
	endIdx := strings.Index(s[startIdx:], end)
	if endIdx == -1 {
		return ""
	}
	return s[startIdx : startIdx+endIdx]
}
