import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── Mocks ─────────────────────────────────────────────────────────

vi.mock("../../utils/haptics.js", () => ({
  triggerSelectionHaptic: vi.fn(),
}));

vi.mock("../../api/client.js", () => ({
  searchAthletes: vi.fn(),
  fetchAthleteProfile: vi.fn(),
}));

vi.mock("../../hooks/useAthleteIdentity.js", () => ({
  useAthleteIdentity: vi.fn(),
}));

import { useAthleteIdentity } from "../../hooks/useAthleteIdentity.js";
import { fetchAthleteProfile, searchAthletes } from "../../api/client.js";
import ProfileMode from "../../pages/ProfileMode.jsx";

// ── Fixtures ──────────────────────────────────────────────────────

const MOCK_IDENTITY = {
  athleteId: "ath_sarah",
  name: "Sarah Johnson",
  setAt: "2025-01-01T00:00:00Z",
};

const MOCK_PROFILE = {
  athlete: {
    name: "Sarah Johnson",
    gender: "Female",
    division: "Open",
    age_group: "F30-34",
    nationality: "USA",
  },
  summary: {
    total_races: 23,
    best_overall_time: 84.55,
    best_age_group_finish: 3,
    first_season: "2022",
  },
  personal_bests: {
    skierg: { time: 4.35, result_id: "r1", location: "Vienna", year: 2025 },
    overall: { time: 84.55, result_id: "r1", location: "Vienna", year: 2025 },
  },
  seasons: [
    { season: "2024", best_time: 86.2, race_count: 5 },
    { season: "2025", best_time: 84.55, race_count: 3 },
  ],
  races: [
    {
      result_id: "r1",
      location: "Vienna",
      year: 2025,
      total_time: 84.55,
      age_group_rank: 3,
    },
    {
      result_id: "r2",
      location: "Berlin",
      year: 2024,
      total_time: 86.2,
      age_group_rank: 7,
    },
  ],
};

const SEARCH_RESULTS = [
  {
    athlete_id: "ath_sarah",
    result_id: "r1",
    athlete_name: "Sarah Johnson",
    division: "Open",
    age_group: "F30-34",
    nationality: "USA",
  },
  {
    athlete_id: "ath_sarah_johnston",
    result_id: "r2",
    athlete_name: "Sarah Johnston",
    division: "Open",
    age_group: "F40-44",
    nationality: "GBR",
  },
];

// ── Helpers ───────────────────────────────────────────────────────

const makeMockIdentityHook = (overrides = {}) => ({
  identity: null,
  setIdentity: vi.fn(),
  clearIdentity: vi.fn(),
  ...overrides,
});

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderProfile(props = {}) {
  const client = makeQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <ProfileMode {...props} />
    </QueryClientProvider>
  );
}

// ── Tests ─────────────────────────────────────────────────────────

describe("ProfileMode — setup view (no identity)", () => {
  beforeEach(() => {
    useAthleteIdentity.mockReturnValue(makeMockIdentityHook());
  });

  it("renders the setup panel when no identity is stored", () => {
    renderProfile();
    expect(screen.getByText("Set up your profile")).toBeInTheDocument();
  });

  it("renders the name search input", () => {
    renderProfile();
    expect(screen.getByRole("textbox", { name: /athlete name/i })).toBeInTheDocument();
  });

  it("renders the Find me button disabled when input is empty", () => {
    renderProfile();
    expect(screen.getByRole("button", { name: /find me/i })).toBeDisabled();
  });

  it("enables the Find me button when name is typed", () => {
    renderProfile();
    const input = screen.getByRole("textbox", { name: /athlete name/i });
    fireEvent.change(input, { target: { value: "Sarah" } });
    expect(screen.getByRole("button", { name: /find me/i })).not.toBeDisabled();
  });

  it("shows search results after a successful search", async () => {
    searchAthletes.mockResolvedValueOnce(SEARCH_RESULTS);
    renderProfile();

    const input = screen.getByRole("textbox", { name: /athlete name/i });
    fireEvent.change(input, { target: { value: "Sarah" } });
    fireEvent.submit(input.closest("form"));

    await waitFor(() => {
      expect(screen.getByText("Sarah Johnson")).toBeInTheDocument();
      expect(screen.getByText("Sarah Johnston")).toBeInTheDocument();
    });
  });

  it("shows search results when API returns a races payload object", async () => {
    searchAthletes.mockResolvedValueOnce({
      query: { name: "Sarah" },
      count: SEARCH_RESULTS.length,
      total: SEARCH_RESULTS.length,
      races: SEARCH_RESULTS,
    });
    renderProfile();

    const input = screen.getByRole("textbox", { name: /athlete name/i });
    fireEvent.change(input, { target: { value: "Sarah" } });
    fireEvent.submit(input.closest("form"));

    await waitFor(() => {
      expect(screen.getByText("Sarah Johnson")).toBeInTheDocument();
      expect(screen.getByText("Sarah Johnston")).toBeInTheDocument();
    });
  });

  it("dedupes results by athlete_id", async () => {
    searchAthletes.mockResolvedValueOnce({
      races: [
        { ...SEARCH_RESULTS[0], result_id: "r1" },
        { ...SEARCH_RESULTS[0], result_id: "r9", year: 2024 },
        { ...SEARCH_RESULTS[1], result_id: "r2" },
      ],
    });
    renderProfile();

    const input = screen.getByRole("textbox", { name: /athlete name/i });
    fireEvent.change(input, { target: { value: "Sarah" } });
    fireEvent.submit(input.closest("form"));

    await waitFor(() => {
      expect(screen.getByText("Sarah Johnson")).toBeInTheDocument();
      expect(screen.getByText("Sarah Johnston")).toBeInTheDocument();
    });
    expect(screen.getAllByText(/this is me/i)).toHaveLength(2);
  });

  it("shows 'Is one of these you?' hint when results arrive", async () => {
    searchAthletes.mockResolvedValueOnce(SEARCH_RESULTS);
    renderProfile();

    const input = screen.getByRole("textbox", { name: /athlete name/i });
    fireEvent.change(input, { target: { value: "Sarah" } });
    fireEvent.submit(input.closest("form"));

    await waitFor(() => {
      expect(screen.getByText(/is one of these you/i)).toBeInTheDocument();
    });
  });

  it("shows no-results message when search returns empty array", async () => {
    searchAthletes.mockResolvedValueOnce([]);
    renderProfile();

    const input = screen.getByRole("textbox", { name: /athlete name/i });
    fireEvent.change(input, { target: { value: "Zyx" } });
    fireEvent.submit(input.closest("form"));

    await waitFor(() => {
      expect(screen.getByText(/no results found/i)).toBeInTheDocument();
    });
  });

  it("shows an error message when the search API fails", async () => {
    searchAthletes.mockRejectedValueOnce(new Error("Network error"));
    renderProfile();

    const input = screen.getByRole("textbox", { name: /athlete name/i });
    fireEvent.change(input, { target: { value: "Sarah" } });
    fireEvent.submit(input.closest("form"));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Network error");
    });
  });

  it("calls setIdentity with athlete_id when 'This is me' is clicked", async () => {
    const mockSetIdentity = vi.fn();
    useAthleteIdentity.mockReturnValue(
      makeMockIdentityHook({ setIdentity: mockSetIdentity })
    );
    fetchAthleteProfile.mockResolvedValueOnce(MOCK_PROFILE);
    searchAthletes.mockResolvedValueOnce(SEARCH_RESULTS);

    renderProfile();

    const input = screen.getByRole("textbox", { name: /athlete name/i });
    fireEvent.change(input, { target: { value: "Sarah" } });
    fireEvent.submit(input.closest("form"));

    await waitFor(() =>
      expect(screen.getAllByText(/this is me/i).length).toBeGreaterThan(0)
    );

    fireEvent.click(screen.getAllByText(/this is me/i)[0]);

    expect(mockSetIdentity).toHaveBeenCalledWith(
      expect.objectContaining({ athleteId: "ath_sarah", name: "Sarah Johnson" })
    );
  });

  it("limits displayed search results to 8", async () => {
    const manyResults = Array.from({ length: 12 }, (_, i) => ({
      result_id: `r${i}`,
      athlete_name: `Athlete ${i}`,
    }));
    searchAthletes.mockResolvedValueOnce(manyResults);
    renderProfile();

    const input = screen.getByRole("textbox", { name: /athlete name/i });
    fireEvent.change(input, { target: { value: "Athlete" } });
    fireEvent.submit(input.closest("form"));

    await waitFor(() =>
      expect(screen.getAllByText(/this is me/i)).toHaveLength(8)
    );
  });
});

describe("ProfileMode — loading state", () => {
  it("renders loading skeleton while fetching profile", () => {
    // fetchAthleteProfile never resolves in this test
    fetchAthleteProfile.mockReturnValueOnce(new Promise(() => {}));
    useAthleteIdentity.mockReturnValue(
      makeMockIdentityHook({ identity: MOCK_IDENTITY })
    );

    renderProfile();
    expect(screen.getByLabelText(/loading profile/i)).toBeInTheDocument();
  });
});

describe("ProfileMode — profile view", () => {
  beforeEach(() => {
    useAthleteIdentity.mockReturnValue(
      makeMockIdentityHook({ identity: MOCK_IDENTITY })
    );
    fetchAthleteProfile.mockResolvedValue(MOCK_PROFILE);
  });

  it("renders athlete name after profile loads", async () => {
    renderProfile();
    await waitFor(() =>
      expect(screen.getByText("Sarah Johnson")).toBeInTheDocument()
    );
  });

  it("renders athlete metadata (gender, age group, nationality)", async () => {
    renderProfile();
    await waitFor(() =>
      expect(screen.getByText(/Female.*F30-34.*USA/i)).toBeInTheDocument()
    );
  });

  it("renders total races in the stats strip", async () => {
    renderProfile();
    await waitFor(() => expect(screen.getByText("23")).toBeInTheDocument());
  });

  it("renders personal best time in the stats strip", async () => {
    renderProfile();
    // 84.55 min = 1:24:33 — appears in multiple places; scope to the stats strip
    await waitFor(() => {
      const pbLabel = screen.getByText("Personal Best");
      const statDiv = pbLabel.closest(".profile-stat");
      expect(within(statDiv).getByText("1:24:33")).toBeInTheDocument();
    });
  });

  it("renders best age group finish with ordinal suffix", async () => {
    renderProfile();
    await waitFor(() => expect(screen.getByText("3rd")).toBeInTheDocument());
  });

  it("renders first season in stats strip", async () => {
    renderProfile();
    await waitFor(() => expect(screen.getByText("2022")).toBeInTheDocument());
  });

  it("renders the Personal Bests section heading", async () => {
    renderProfile();
    await waitFor(() =>
      expect(screen.getByText("Personal Bests")).toBeInTheDocument()
    );
  });

  it("renders PB cards for segments present in personal_bests", async () => {
    renderProfile();
    await waitFor(() => {
      expect(screen.getByText("SkiErg")).toBeInTheDocument();
      expect(screen.getByText("Overall Time")).toBeInTheDocument();
    });
  });

  it("renders the Season Progression section when seasons are present", async () => {
    renderProfile();
    await waitFor(() =>
      expect(screen.getByText("Season Progression")).toBeInTheDocument()
    );
  });

  it("renders the Race History section heading", async () => {
    renderProfile();
    await waitFor(() =>
      expect(screen.getByText("Race History")).toBeInTheDocument()
    );
  });

  it("renders race location names in race history", async () => {
    renderProfile();
    await waitFor(() => {
      expect(screen.getByText("Vienna")).toBeInTheDocument();
      expect(screen.getByText("Berlin")).toBeInTheDocument();
    });
  });

  it("renders age group rank for each race", async () => {
    renderProfile();
    await waitFor(() => {
      expect(screen.getByText("3rd AG")).toBeInTheDocument();
      expect(screen.getByText("7th AG")).toBeInTheDocument();
    });
  });

  it("renders the initials avatar based on athlete name", async () => {
    renderProfile();
    await waitFor(() => expect(screen.getByText("SJ")).toBeInTheDocument());
  });

  it("renders the Change button in the hero card", async () => {
    renderProfile();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /change athlete profile/i })
      ).toBeInTheDocument()
    );
  });

  it("calls clearIdentity and resets to setup view when Change is clicked", async () => {
    const mockClearIdentity = vi.fn();
    useAthleteIdentity.mockReturnValue(
      makeMockIdentityHook({
        identity: MOCK_IDENTITY,
        clearIdentity: mockClearIdentity,
      })
    );
    fetchAthleteProfile.mockResolvedValue(MOCK_PROFILE);

    renderProfile();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /change athlete profile/i })).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: /change athlete profile/i }));

    expect(mockClearIdentity).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.getByText("Set up your profile")).toBeInTheDocument()
    );
  });

  it("calls onOpenRace with result_id when a race row is clicked", async () => {
    const onOpenRace = vi.fn();
    renderProfile({ onOpenRace });

    await waitFor(() => expect(screen.getByText("Vienna")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /open report for vienna 2025/i }));
    expect(onOpenRace).toHaveBeenCalledWith("r1");
  });
});

describe("ProfileMode — error state", () => {
  beforeEach(() => {
    useAthleteIdentity.mockReturnValue(
      makeMockIdentityHook({ identity: MOCK_IDENTITY })
    );
  });

  it("renders an error alert when profile fetch fails", async () => {
    fetchAthleteProfile.mockRejectedValueOnce(new Error("Server error"));
    renderProfile();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Server error")
    );
  });

  it("renders Retry and Change athlete buttons in the error state", async () => {
    fetchAthleteProfile.mockRejectedValueOnce(new Error("Server error"));
    renderProfile();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /change athlete/i })).toBeInTheDocument();
    });
  });

  it("retries loading when Retry is clicked", async () => {
    fetchAthleteProfile
      .mockRejectedValueOnce(new Error("Server error"))
      .mockResolvedValueOnce(MOCK_PROFILE);

    renderProfile();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() =>
      expect(screen.getByText("Sarah Johnson")).toBeInTheDocument()
    );
  });
});

describe("ProfileMode — profile with no PBs", () => {
  it("shows fallback message when personal_bests is empty", async () => {
    useAthleteIdentity.mockReturnValue(
      makeMockIdentityHook({ identity: MOCK_IDENTITY })
    );
    fetchAthleteProfile.mockResolvedValueOnce({
      ...MOCK_PROFILE,
      personal_bests: {},
    });

    renderProfile();

    await waitFor(() =>
      expect(
        screen.getByText(/station personal bests will appear here/i)
      ).toBeInTheDocument()
    );
  });
});

describe("ProfileMode — profile with no races", () => {
  it("shows fallback message when races array is empty", async () => {
    useAthleteIdentity.mockReturnValue(
      makeMockIdentityHook({ identity: MOCK_IDENTITY })
    );
    fetchAthleteProfile.mockResolvedValueOnce({
      ...MOCK_PROFILE,
      races: [],
    });

    renderProfile();

    await waitFor(() =>
      expect(
        screen.getByText(/no race history found/i)
      ).toBeInTheDocument()
    );
  });
});

describe("ProfileMode — season progression section", () => {
  it("does not render the Season Progression section when seasons is empty", async () => {
    useAthleteIdentity.mockReturnValue(
      makeMockIdentityHook({ identity: MOCK_IDENTITY })
    );
    fetchAthleteProfile.mockResolvedValueOnce({
      ...MOCK_PROFILE,
      seasons: [],
    });

    renderProfile();

    await waitFor(() =>
      expect(screen.getByText("Race History")).toBeInTheDocument()
    );

    expect(screen.queryByText("Season Progression")).not.toBeInTheDocument();
  });
});
