package main

import (
	"fmt"
	"github.com/gocolly/colly/v2"
	"log"
	"net/url"
	"path/filepath"
	"strings"
)

func crawlImmigrationForms(parentDir string) *colly.Collector {
	contentDir := filepath.Join(parentDir, "forms")

	uri, err := url.Parse("https://www.uscis.gov")
	if err != nil {
		log.Fatal(err)
	}

	c := colly.NewCollector(
		colly.AllowedDomains(uri.Host),
		colly.CacheDir("./usciscache"),
		colly.Async(true),
	)

	c.Limit(&colly.LimitRule{DomainGlob: "*", Parallelism: 2})

	// Set custom headers to mimic a real browser
	c.OnRequest(func(r *colly.Request) {
		r.Headers.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
		r.Headers.Set("Accept-Language", "en-US,en;q=0.9")
	})

	// Define what to do when an element is found
	c.OnHTML(".views-row", func(e *colly.HTMLElement) {
		link := *uri
		link.Path = e.ChildAttr(".views-field-title .field-content a", "href")
		fileOnline := e.ChildAttr("a[aria-label]", "aria-label")
		title := e.ChildText(".views-field-title .field-content a")
		metadata := FormMetadata{
			//Extract ID
			ID: strings.Split(title, "|")[0],
			// Extract the title
			Title: title,
			// Extract the description
			Description: e.ChildText(".views-field-body .field-content"),
			// Extract the link (href attribute)
			Link: link.String(),
			//Check if form can be filed online
			FileOnline: strings.HasPrefix(fileOnline, "File Online"),
		}

		err := writeToFile(filepath.Join(contentDir, link.Path), "metadata.json", []byte(metadata.String()))
		if err != nil {
			log.Printf("error downloading %s - %s", metadata, err)
		}

		//Find and Visit all form pages
		c.Visit(metadata.Link)
		//Vist fee scheduling page for form
		q := link.Query()
		q.Add("form", strings.TrimPrefix(link.Path, "/"))
		link.RawQuery = q.Encode()
		link.Path = "/g-1055"
		c.Visit(link.String())

	})

	//Find and visit all PDFs
	c.OnHTML("span.file.file--mime-application-pdf.file--application-pdf", func(e *colly.HTMLElement) {
		dir := filepath.Join(contentDir, e.Request.URL.Path)
		metadata, err := loadMetadataFromFile(dir)
		if err != nil {
			log.Println(
				"Error loading metadata for form",
				e.Request.URL.Path)
			return
		}
		link := *uri
		link.Path = e.ChildAttr("a", "href")
		fileInfo := e.ChildText("a>span.extra-info")
		_, name := filepath.Split(link.Path)

		metadata.Forms = append(metadata.Forms, FormMetadata{
			ID:          name,
			Title:       strings.TrimSpace(strings.TrimSuffix(e.Text, fileInfo)),
			Description: fileInfo,
			Link:        link.String(),
		})

		err = writeToFile(dir, "metadata.json", []byte(metadata.String()))
		if err != nil {
			log.Fatal(err)
		}

		fmt.Printf("Downloading PDF: %s %s\n", e.Request.URL, link.Path)

		err = downloadContent(link.String(), dir, name, 4)
		if err != nil {
			log.Printf("error downloading: %s - %s\n", metadata.String(), err)
		}

	})

	c.OnResponse(func(r *colly.Response) {
		segments := strings.Split(r.Request.URL.Path, "/")
		if len(segments) != 2 {
			return
		}
		id := segments[1]
		dir := filepath.Join(contentDir, id)
		_, err := loadMetadataFromFile(dir)
		if err != nil {
			return
		}

		err = writeToFile(dir, fmt.Sprintf("%s.html", id), r.Body)
		if err != nil {
			log.Fatal(err)
		}

	})

	// Start scraping from the main forms page
	startURL := "https://www.uscis.gov/forms/all-forms"
	if err := c.Visit(startURL); err != nil {
		log.Fatal(err)
	}
	return c
}
