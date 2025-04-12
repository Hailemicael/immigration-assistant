package main

import (
	"encoding/json"
	"fmt"
	"github.com/PuerkitoBio/goquery"
	"log"
	"os"
	"regexp"
	"strings"

	"github.com/gocolly/colly/v2"
)

// FAQItem represents a single question and answer pair
type FAQItem struct {
	Question string `json:"question"`
	Answer   string `json:"answer"`
}

func main() {
	// Create a new collector
	c := colly.NewCollector(
		colly.AllowedDomains("gldlaw.com"),
	)

	var faqItems []FAQItem

	// Find the strong tags that contain questions (they contain question marks)
	c.OnHTML(".fl-rich-text strong", func(e *colly.HTMLElement) {
		questionText := e.Text

		// Check if this is a question (contains a question mark)
		if strings.Contains(questionText, "?") {
			// Clean the question text
			questionText = cleanText(questionText)

			// Find the parent element that contains the question
			parent := e.DOM.Closest("p")

			// Initialize answer text
			var answerText string
			var answerParts []string

			// Look for the answer in the following siblings until we hit another question
			nextElement := parent.Next()
			for nextElement.Length() > 0 {
				// Stop if we find another question
				if nextElement.Find("strong:contains('?')").Length() > 0 {
					break
				}

				// Get the text based on the element type
				if nextElement.Is("p") {
					text := nextElement.Text()
					if text != "" {
						answerParts = append(answerParts, text)
					}
				} else if nextElement.Is("ul") {
					nextElement.Find("li").Each(func(i int, li *goquery.Selection) {
						answerParts = append(answerParts, "• "+li.Text())
					})
				}

				// Move to the next element
				nextElement = nextElement.Next()
			}

			// Join all answer parts
			answerText = strings.Join(answerParts, "\n")
			answerText = cleanText(answerText)

			// Only add if we have both question and answer
			if questionText != "" && answerText != "" {
				faqItems = append(faqItems, FAQItem{
					Question: questionText,
					Answer:   answerText,
				})
			}
		}
	})

	// Set error handler
	c.OnError(func(r *colly.Response, err error) {
		log.Println("Request URL:", r.Request.URL, "failed with response:", r, "\nError:", err)
	})

	// Before making a request
	c.OnRequest(func(r *colly.Request) {
		fmt.Println("Visiting", r.URL)
	})

	// Start scraping
	err := c.Visit("https://gldlaw.com/frequently-asked-immigration-questions/")
	if err != nil {
		log.Fatal("Error visiting page:", err)
	}

	// Print results
	fmt.Printf("Found %d FAQ items\n", len(faqItems))

	// Remove duplicates (some questions appear multiple times on the page)
	faqItems = removeDuplicates(faqItems)
	fmt.Printf("After removing duplicates: %d FAQ items\n", len(faqItems))

	// Save to JSON file
	saveToJSON(faqItems, "immigration_faqs.json")

	// Print a sample of the results
	printSample(faqItems, 5)
}

// Clean text by removing extra whitespace and HTML entities
func cleanText(text string) string {
	// Remove extra whitespace
	text = strings.TrimSpace(text)
	re := regexp.MustCompile(`\s+`)
	text = re.ReplaceAllString(text, " ")

	// Replace common HTML entities
	text = strings.ReplaceAll(text, "&nbsp;", " ")
	text = strings.ReplaceAll(text, "&amp;", "&")
	text = strings.ReplaceAll(text, "&quot;", "\"")
	text = strings.ReplaceAll(text, "&lt;", "<")
	text = strings.ReplaceAll(text, "&gt;", ">")

	return text
}

// Remove duplicate FAQ items based on the question
func removeDuplicates(items []FAQItem) []FAQItem {
	seen := make(map[string]bool)
	var result []FAQItem

	for _, item := range items {
		if !seen[item.Question] {
			seen[item.Question] = true
			result = append(result, item)
		}
	}

	return result
}

// Save FAQ items to a JSON file
func saveToJSON(items []FAQItem, filename string) {
	jsonData, err := json.MarshalIndent(items, "", "  ")
	if err != nil {
		log.Fatal("Error marshaling to JSON:", err)
	}

	err = os.WriteFile(filename, jsonData, 0644)
	if err != nil {
		log.Fatal("Error writing JSON file:", err)
	}

	fmt.Println("FAQ data successfully saved to", filename)
}

// Print a sample of the results
func printSample(items []FAQItem, count int) {
	fmt.Println("\nSample FAQ Items:")
	for i, item := range items {
		if i >= count {
			break
		}
		fmt.Printf("\nQuestion %d: %s\n", i+1, item.Question)

		// Truncate long answers for display
		answer := item.Answer
		if len(answer) > 150 {
			answer = answer[:150] + "..."
		}
		fmt.Printf("Answer: %s\n", answer)
	}
}
