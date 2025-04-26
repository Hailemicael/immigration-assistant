package main

import (
	"encoding/json"
	"encoding/xml"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"sync"
)

type MetaData struct {
	Identifier       string     `json:"identifier"`
	Label            string     `json:"label"`
	LabelLevel       string     `json:"label_level"`
	LabelDescription string     `json:"label_description"`
	Reserved         bool       `json:"reserved"`
	Type             string     `json:"type"`
	Size             int        `json:"size"`
	Children         []MetaData `json:"children"`
}

func (m *MetaData) Load(path string) (err error) {
	file, err := os.Open(path)
	if err != nil {
		return
	}
	err = json.NewDecoder(file).Decode(m)
	return
}

type Label struct {
	Level       string `json:"level"`
	Description string `json:"description"`
}

func (l *Label) Build(meta MetaData) {
	l.Level = meta.LabelLevel
	l.Description = meta.LabelDescription
}

type rawParagraph struct {
	XMLName xml.Name `xml:"P"`
	Content string   `xml:",innerxml"`
}

func (r rawParagraph) Parse() (label, italic, text string) {
	raw := strings.TrimSpace(r.Content)

	// Match label like (a), (1), (d)
	labelRegex := regexp.MustCompile(`^\(([a-zA-Z0-9]+)\)`)
	matches := labelRegex.FindStringSubmatch(raw)
	if len(matches) > 0 {
		label = fmt.Sprintf("(%s)", matches[1])
		raw = strings.TrimSpace(strings.TrimPrefix(raw, label))
	}

	// Extract italic text inside <I>
	italicRegex := regexp.MustCompile(`<I>(.*?)</I>`)
	italicMatch := italicRegex.FindStringSubmatch(raw)
	if len(italicMatch) > 0 {
		italic = strings.TrimSpace(italicMatch[1])
		raw = italicRegex.ReplaceAllString(raw, "")
	}

	text = regexp.MustCompile(`<.*?>`).ReplaceAllString(raw, "")
	text = strings.TrimSpace(text)
	return
}

type Subsection struct {
	Id            string      `json:"id"`
	Title         string      `json:"title,omitempty"`
	Text          string      `json:"text"`
	SubSubsection Subsections `json:"sub_subsection,omitempty"`
}

type Subsections map[string]*Subsection

func (s *Subsections) Set(key string, section *Subsection) {
	if *s == nil {
		*s = make(Subsections)
	}
	(*s)[key] = section
}

type Section struct {
	Id          string      `json:"id"`
	Label       Label       `json:"label,omitempty"`
	Subsections Subsections `json:"subsections"`
	Text        string      `json:"text,omitempty"`
}

func (s *Section) Build(wg *sync.WaitGroup, meta MetaData) {
	s.Id = meta.Identifier
	s.Label.Build(meta)
	wg.Add(1)
	s.LoadContent(wg)
}

func (s *Section) LoadContent(wg *sync.WaitGroup) {
	defer wg.Done()
	u, err := url.Parse("https://www.ecfr.gov/api/versioner/v1/full/2025-04-10/title-8.xml")
	if err != nil {
		log.Fatal(err)
	}

	values := url.Values{
		"section": []string{s.Id},
	}
	u.RawQuery = values.Encode()

	resp, err := http.Get(u.String())
	if err != nil {
		log.Fatal(err)
	}

	if resp.StatusCode != http.StatusOK {
		log.Printf("Not Okay: %s\n", s.Id)
		return
	}

	defer resp.Body.Close()
	var raw struct {
		Head       string         `xml:"HEAD"`
		Paragraphs []rawParagraph `xml:"P"`
	}
	if err = xml.NewDecoder(resp.Body).Decode(&raw); err != nil {
		log.Printf("Decode failed: %s-%s\n", s.Id, err.Error())
		return
	}

	var currentSub *Subsection
	for _, p := range raw.Paragraphs {
		label, italic, text := p.Parse()
		switch {
		case regexp.MustCompile(`^\(\d+\)$`).MatchString(label) && currentSub != nil:
			currentSub.SubSubsection.Set(label, &Subsection{
				Id:    label,
				Title: italic,
				Text:  text,
			})

		case regexp.MustCompile(`^\([a-zA-Z]\)$`).MatchString(label):
			sub := &Subsection{Id: label, Title: italic, Text: text}
			s.Subsections.Set(label, sub)
			currentSub = sub

		default:
			s.Text = text
		}
	}

	fmt.Printf("Parsed: %s (%d paragraphs)\n", s.Id, len(raw.Paragraphs))
}

type Sections map[string]*Section

func (s *Sections) Set(key string, section *Section) {
	if *s == nil {
		*s = make(Sections)
	}
	(*s)[key] = section

}

type SubPart struct {
	Id       string   `json:"id"`
	Label    Label    `json:"label"`
	Sections Sections `json:"sections"`
}

func (s *SubPart) Build(meta MetaData) {
	s.Id = meta.Identifier
	s.Label.Build(meta)
	wg := new(sync.WaitGroup)
	defer wg.Wait()
	for _, child := range meta.Children {
		if child.Reserved {
			continue
		}
		switch child.Type {
		case "section":
			section := new(Section)
			section.Build(wg, child)
			s.Sections.Set(child.Identifier, section)
		default:
			fmt.Printf("Unexcpected Type in %s - %s\n", "Subpart", child.Type)
		}
	}
}

type SubParts map[string]*SubPart

func (s *SubParts) Set(key string, part *SubPart) {
	if *s == nil {
		*s = make(SubParts)
	}
	(*s)[key] = part
}

type SubjectGroup struct {
	Id       string   `json:"id"`
	Label    Label    `json:"label"`
	Sections Sections `json:"sections,omitempty"`
}

func (s *SubjectGroup) Build(meta MetaData) {
	s.Id = meta.Identifier
	s.Label.Build(meta)
	wg := new(sync.WaitGroup)
	defer wg.Wait()
	for _, child := range meta.Children {
		if child.Reserved {
			continue
		}
		switch child.Type {
		case "section":
			section := new(Section)
			section.Build(wg, child)
			s.Sections.Set(child.Identifier, section)
		default:
			fmt.Printf("Unexcpected Type in %s - %s\n", "SubjectGroup", child.Type)
		}
	}
}

type SubjectGroups map[string]*SubjectGroup

func (s *SubjectGroups) Set(key string, group *SubjectGroup) {
	if *s == nil {
		*s = make(SubjectGroups)
	}
	(*s)[key] = group
}

type Part struct {
	Id            string        `json:"id"`
	Label         Label         `json:"label"`
	SubParts      SubParts      `json:"sub_parts,omitempty"`
	Sections      Sections      `json:"sections,omitempty"`
	SubjectGroups SubjectGroups `json:"subject_groups,omitempty"`
}

func (p *Part) Build(meta MetaData) {
	p.Id = meta.Identifier
	p.Label.Build(meta)
	wg := new(sync.WaitGroup)
	defer wg.Wait()
	for _, child := range meta.Children {
		if child.Reserved {
			continue
		}
		switch child.Type {
		case "subpart":
			subpart := new(SubPart)
			subpart.Build(child)
			p.SubParts.Set(child.Identifier, subpart)
		case "section":
			section := new(Section)
			section.Build(wg, child)
			p.Sections.Set(child.Identifier, section)
		case "subject_group":
			group := new(SubjectGroup)
			group.Build(child)
			p.SubjectGroups.Set(child.Identifier, group)

		default:
			fmt.Printf("Unexcpected Type in %s - %s\n", "Part", child.Type)
		}
	}
}

type Parts map[string]*Part

func (p *Parts) Set(key string, part *Part) {
	if *p == nil {
		*p = make(Parts)
	}
	(*p)[key] = part

}

type SubChapter struct {
	Id          string      `json:"id"`
	Label       Label       `json:"label"`
	SubChapters SubChapters `json:"sub_chapters,omitempty"`
	Parts       Parts       `json:"parts,omitempty"`
}

func (s *SubChapter) Build(meta MetaData) {
	s.Id = meta.Identifier
	s.Label.Build(meta)
	for _, child := range meta.Children {
		if child.Reserved {
			continue
		}
		switch child.Type {
		case "subchapter":
			subchapter := new(SubChapter)
			subchapter.Build(child)
			s.SubChapters.Set(child.Identifier, subchapter)
		case "part":
			part := new(Part)
			part.Build(child)
			s.Parts.Set(child.Identifier, part)
		default:
			fmt.Printf("Unexcpected Type in %s - %s\n", "SubChapter", child.Type)
		}
	}
}

type SubChapters map[string]*SubChapter

func (s *SubChapters) Set(key string, chapter *SubChapter) {
	if *s == nil {
		*s = make(SubChapters)
	}
	(*s)[key] = chapter
}

type Chapter struct {
	Id          string      `json:"id"`
	Label       Label       `json:"label"`
	SubChapters SubChapters `json:"sub_chapters,omitempty"`
	Parts       Parts       `json:"parts,omitempty"`
}

func (c *Chapter) Build(meta MetaData) {
	c.Id = meta.Identifier
	c.Label.Build(meta)
	for _, child := range meta.Children {
		if child.Reserved {
			continue
		}
		switch child.Type {
		case "subchapter":
			subchapter := new(SubChapter)
			subchapter.Build(child)
			c.SubChapters.Set(child.Identifier, subchapter)
		case "part":
			part := new(Part)
			part.Build(child)
			c.Parts.Set(child.Identifier, part)
		default:
			fmt.Printf("Unexcpected Type in %s - %s\n", "Chapter", child.Type)
		}
	}
}

type Chapters map[string]*Chapter

func (c *Chapters) Set(key string, chapter *Chapter) {
	if *c == nil {
		*c = make(Chapters)
	}
	(*c)[key] = chapter
}

type SubTitle struct {
	Id       string   `json:"id"`
	Label    Label    `json:"label"`
	Chapters Chapters `json:"chapters,omitempty"`
	Parts    Parts    `json:"parts,omitempty"`
}

func (s *SubTitle) Build(meta MetaData) {
	s.Id = meta.Identifier
	s.Label.Build(meta)
	for _, child := range meta.Children {
		if child.Reserved {
			continue
		}
		switch child.Type {
		case "chapter":
			chapter := new(Chapter)
			chapter.Build(child)
			s.Chapters.Set(child.Identifier, chapter)
		case "part":
			part := new(Part)
			part.Build(child)
			s.Parts.Set(child.Identifier, part)
		default:
			fmt.Printf("Unexcpected Type in %s - %s\n", "SubTitle", child.Type)
		}
	}
}

type SubTitles map[string]*SubTitle

func (s *SubTitles) Set(key string, title *SubTitle) {
	if *s == nil {
		*s = make(SubTitles)
	}
	(*s)[key] = title
}

type Title8 struct {
	Label     Label     `json:"label"`
	Chapters  Chapters  `json:"chapters,omitempty"`
	SubTitles SubTitles `json:"sub_titles,omitempty"`
	Parts     Parts     `json:"parts,omitempty"`
}

func (t *Title8) Build(meta MetaData) {
	t.Label.Build(meta)
	for _, child := range meta.Children {
		if child.Reserved {
			continue
		}
		switch child.Type {
		case "chapter":
			chapter := new(Chapter)
			chapter.Build(child)
			t.Chapters.Set(child.Identifier, chapter)
		case "subtitle":
			subtitle := new(SubTitle)
			subtitle.Build(child)
			t.SubTitles.Set(child.Identifier, subtitle)
		case "part":
			part := new(Part)
			part.Build(child)
			t.Parts.Set(child.Identifier, part)
		default:
			fmt.Printf("Unexcpected Type in %s - %s\n", "Title", child.Type)
		}
	}
}

//func crawlLegislation(dir string, name string) {
//	dir = path.Join(dir, "legislation")
//	var metadata MetaData
//	err := metadata.Load(path.Join(dir, name))
//	if err != nil {
//		log.Fatal(err)
//	}
//
//	var title Title8
//	title.Build(metadata)
//
//	data, err := json.MarshalIndent(title, "", "	")
//	if err != nil {
//		log.Fatal(err)
//	}
//	err = writeToFile(dir, "INA.json", data)
//	if err != nil {
//		log.Fatal(err)
//	}
//}
