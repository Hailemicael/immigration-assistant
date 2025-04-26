package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"

	"github.com/gocolly/colly/v2"
)

type FormMetadata struct {
	ID          string         `json:"id"`
	Title       string         `json:"title"`
	Link        string         `json:"link"`
	Description string         `json:"description"`
	FileOnline  bool           `json:"file-online"`
	Forms       []FormMetadata `json:"forms,omitempty"`
}

func (f FormMetadata) String() string {
	data, _ := json.MarshalIndent(f, "", "	")
	return string(data)
}

func writeToFile(dir, name string, data []byte) error {
	// Create the parent directories if they don't exist
	err := os.MkdirAll(dir, 0755) // 0755 is the permission for the directory
	if err != nil {
		return fmt.Errorf("error creating directories: %w", err)
	}

	// Write JSON data to the file
	err = os.WriteFile(filepath.Join(dir, name), data, 0644) // 0644 is the file permission
	if err != nil {
		return fmt.Errorf("error writing to file: %w", err)
	}

	return nil
}

func loadMetadataFromFile(path string) (metadata *FormMetadata, err error) {
	// Open the file
	file, err := os.Open(filepath.Join(path, "metadata.json"))
	if err != nil {
		return nil, fmt.Errorf("error opening file: %w", err)
	}
	defer file.Close() // Ensure the file is closed when done
	metadata = new(FormMetadata)
	// Decode the JSON data into the provided data structure
	decoder := json.NewDecoder(file)
	err = decoder.Decode(metadata)
	if err != nil {
		return metadata, fmt.Errorf("error decoding JSON: %w", err)
	}

	return metadata, nil
}

func downloadContent(url, dir, name string, retryCount int) (err error) {
	if retryCount <= 0 {
		return
	}
	resp, err := http.Get(url)
	if err != nil {
		return
	}
	if resp.StatusCode != http.StatusOK {
		log.Printf("Failed to download %s - %v\n", resp.Request.URL.Path, resp.Status)
		return downloadContent(url, dir, name, retryCount-1)
	}

	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return
	}
	err = writeToFile(dir, name, body)
	return
}

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

	})

	//Find and visit all PDFs
	c.OnHTML("span.file.file--mime-application-pdf.file--application-pdf", func(e *colly.HTMLElement) {
		dir := filepath.Join(contentDir, e.Request.URL.Path)
		metadata, err := loadMetadataFromFile(dir)
		if err != nil {
			log.Fatal(err)
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

	// Start scraping from the main forms page
	startURL := "https://www.uscis.gov/forms/all-forms"
	if err := c.Visit(startURL); err != nil {
		log.Fatal(err)
	}
	return c
}

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
func crawLegistlation(parentDir string) *colly.Collector {
	contentDir := filepath.Join(parentDir, "legistlation")

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

func main() {
	dir := filepath.Join(".", "documents")
	formCrawler := crawlImmigrationForms(dir)
	legistlationCrawler := crawLegistlation(dir)
	formCrawler.Wait()
	legistlationCrawler.Wait()
}
