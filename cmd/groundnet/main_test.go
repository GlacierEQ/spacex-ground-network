package main

import "testing"

func TestSelectStationRejectsBadLinkAndBalancesLoad(t *testing.T) {
	result, err := selectStation(Request{MaxLoadPercent: 95, Stations: []Station{
		{Name: "high-margin-loaded", ElevationDeg: 20, MinElevation: 5, LinkMarginDB: 10, LoadPercent: 90, Active: true},
		{Name: "balanced", ElevationDeg: 20, MinElevation: 5, LinkMarginDB: 8, LoadPercent: 10, Active: true},
		{Name: "bad-link", ElevationDeg: 40, MinElevation: 5, LinkMarginDB: -1, LoadPercent: 0, Active: true},
	}})
	if err != nil {
		t.Fatal(err)
	}
	if !result.OK || result.Station != "balanced" {
		t.Fatalf("unexpected selection: %+v", result)
	}
	if result.OperationalAuthority {
		t.Fatal("kernel must never claim operational authority")
	}
}

func TestSelectStationNoCoverage(t *testing.T) {
	result, err := selectStation(Request{Stations: []Station{
		{Name: "below", ElevationDeg: 0, MinElevation: 5, LinkMarginDB: 20, Active: true},
		{Name: "down", ElevationDeg: 20, MinElevation: 5, LinkMarginDB: 20, Active: false},
	}})
	if err != nil {
		t.Fatal(err)
	}
	if result.OK || result.Station != "" {
		t.Fatalf("expected no coverage, got %+v", result)
	}
}

func TestDuplicateStationRejected(t *testing.T) {
	_, err := selectStation(Request{Stations: []Station{
		{Name: "dup", ElevationDeg: 20, MinElevation: 5, LinkMarginDB: 1, Active: true},
		{Name: "dup", ElevationDeg: 30, MinElevation: 5, LinkMarginDB: 2, Active: true},
	}})
	if err == nil {
		t.Fatal("expected duplicate station error")
	}
}
