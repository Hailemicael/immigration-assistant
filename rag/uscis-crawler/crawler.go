package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"
)

type FormMetadata struct {
	ID          string         `json:"id"`
	Title       string         `json:"title"`
	Link        string         `json:"link"`
	Description string         `json:"description"`
	FileOnline  bool           `json:"file_online"`
	Forms       []FormMetadata `json:"forms,omitempty"`
	FeeRWMutex  sync.RWMutex   `json:"-"`
	Fees        map[string]Fee `json:"fees,omitempty"`
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

func main() {
	wd, _ := os.Getwd()
	dir := filepath.Join(wd, "documents")
	crawlECFR(dir).Wait()
	//crawlFAQ(dir).Wait()
	//crawlImmigrationForms(dir).Wait()
	//crawlFeeSchedule(dir).Wait()
	//crawlLegislation(dir, "title-8.json")

}
