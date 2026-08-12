package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sort"
)

type Station struct {
	Name         string  `json:"name"`
	ElevationDeg float64 `json:"elevation_deg"`
	MinElevation float64 `json:"min_elevation_deg"`
	LinkMarginDB float64 `json:"link_margin_db"`
	LoadPercent  float64 `json:"load_percent"`
	Active       bool    `json:"active"`
}

type Request struct {
	Stations       []Station `json:"stations"`
	MaxLoadPercent float64   `json:"max_load_percent"`
}

type Result struct {
	Station              string   `json:"station,omitempty"`
	Eligible             []string `json:"eligible"`
	OK                   bool     `json:"ok"`
	Score                 float64  `json:"score,omitempty"`
	OperationalAuthority bool     `json:"operational_authority"`
}

func score(s Station) float64 { return s.LinkMarginDB - 0.05*s.LoadPercent }

func validate(req Request) error {
	if len(req.Stations) == 0 {
		return errors.New("at least one station is required")
	}
	if req.MaxLoadPercent == 0 {
		req.MaxLoadPercent = 95
	}
	if req.MaxLoadPercent <= 0 || req.MaxLoadPercent > 100 {
		return errors.New("max_load_percent must be in (0,100]")
	}
	seen := map[string]bool{}
	for _, station := range req.Stations {
		if station.Name == "" {
			return errors.New("station name is required")
		}
		if seen[station.Name] {
			return fmt.Errorf("duplicate station %q", station.Name)
		}
		seen[station.Name] = true
		if station.LoadPercent < 0 || station.LoadPercent > 100 {
			return fmt.Errorf("station %q load outside [0,100]", station.Name)
		}
	}
	return nil
}

func selectStation(req Request) (Result, error) {
	if req.MaxLoadPercent == 0 {
		req.MaxLoadPercent = 95
	}
	if err := validate(req); err != nil {
		return Result{}, err
	}
	eligible := make([]Station, 0, len(req.Stations))
	for _, station := range req.Stations {
		if station.Active && station.ElevationDeg >= station.MinElevation && station.LinkMarginDB >= 0 && station.LoadPercent < req.MaxLoadPercent {
			eligible = append(eligible, station)
		}
	}
	sort.Slice(eligible, func(i, j int) bool {
		si, sj := score(eligible[i]), score(eligible[j])
		if si == sj {
			return eligible[i].Name < eligible[j].Name
		}
		return si > sj
	})
	result := Result{OK: len(eligible) > 0, OperationalAuthority: false, Eligible: make([]string, len(eligible))}
	for i, station := range eligible {
		result.Eligible[i] = station.Name
	}
	if len(eligible) > 0 {
		result.Station = eligible[0].Name
		result.Score = score(eligible[0])
	}
	return result, nil
}

func demo() Request {
	return Request{MaxLoadPercent: 95, Stations: []Station{
		{Name: "alpha", ElevationDeg: 25, MinElevation: 5, LinkMarginDB: 12, LoadPercent: 80, Active: true},
		{Name: "beta", ElevationDeg: 20, MinElevation: 5, LinkMarginDB: 10, LoadPercent: 10, Active: true},
		{Name: "blocked", ElevationDeg: 40, MinElevation: 5, LinkMarginDB: -2, LoadPercent: 0, Active: true},
	}}
}

func main() {
	request := demo()
	if len(os.Args) > 1 && os.Args[1] == "stdin" {
		if err := json.NewDecoder(os.Stdin).Decode(&request); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	}
	result, err := selectStation(request)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
}
